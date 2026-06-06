#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "1.0.0"
DEFAULT_OUT = "MasterWu/cole"
PENDING_MARKER = "PENDING_KAI_AGENT_OUTPUT"

CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}
VALID_STATUSES = {"confirmed", "rejected", "needs-poc", "blocked-build", "blocked-missing-context"}
STATUS_PRIORITY = {
    "confirmed": 5,
    "needs-poc": 4,
    "blocked-missing-context": 3,
    "blocked-build": 2,
    "rejected": 1,
}
VALID_REACHABILITY = {
    "ordinary-user-reachable",
    "trusted-role-only",
    "governance-only",
    "configuration-dependent",
    "unreachable",
}
REACHABILITY_PRIORITY = {
    "ordinary-user-reachable": 5,
    "configuration-dependent": 4,
    "trusted-role-only": 3,
    "governance-only": 2,
    "unreachable": 1,
}
VALID_NATURE = {"real-bug", "design-choice", "configuration-risk", "trusted-role-risk", "false-positive"}
NATURE_PRIORITY = {
    "real-bug": 5,
    "configuration-risk": 4,
    "trusted-role-risk": 3,
    "design-choice": 2,
    "false-positive": 1,
}
VALID_TEST_RESULTS = {"not-run", "passed", "failed", "blocked"}

KAI_REQUIRED = {
    "id",
    "title",
    "claim",
    "category",
    "confidence",
    "evidence",
    "jay_refs",
    "attack_sketch",
    "why_might_be_real",
    "why_might_be_false_positive",
    "next_validation_steps",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Cole Varify Kai hypothesis verification helpers.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight", help="Validate Kai run and project build readiness")
    preflight.add_argument("project_root", type=Path)
    preflight.add_argument("--run", required=True, type=Path, help="Kai run directory")
    preflight.add_argument("--out", default=DEFAULT_OUT, help="Cole output root, relative to project root unless absolute")
    preflight.add_argument("--build-command", default=None, help="Override build command for non-standard projects")
    preflight.add_argument("--skip-local-build", action="store_true", help="Validate the Kai run but skip local build checks; logic-only verification mode")

    collect = subparsers.add_parser("collect", help="Collect, normalize, and deduplicate Kai hypotheses")
    collect.add_argument("project_root", type=Path)
    collect.add_argument("--run", required=True, type=Path, help="Kai run directory")
    collect.add_argument("--out", default=DEFAULT_OUT, help="Cole output root, relative to project root unless absolute")

    validate = subparsers.add_parser("validate-results", help="Validate Cole results.json")
    validate.add_argument("json_path", type=Path)
    validate.add_argument("--candidates", type=Path, default=None, help="Optional candidates.json coverage check")

    render = subparsers.add_parser("render-report", help="Render Cole report.md from results.json")
    render.add_argument("json_path", type=Path)
    render.add_argument("--out", type=Path, default=None, help="Report path; defaults to sibling report.md")

    args = parser.parse_args()
    if args.command == "preflight":
        return command_preflight(args)
    if args.command == "collect":
        return command_collect(args)
    if args.command == "validate-results":
        return command_validate_results(args.json_path, args.candidates)
    if args.command == "render-report":
        return command_render_report(args.json_path, args.out)
    return 1


def command_preflight(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project_root)
    run_dir = resolve_under_project(project_root, args.run)
    out_dir = cole_run_dir(project_root, args.out, run_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    kai = load_kai_run(run_dir)
    if kai["errors"]:
        for error in kai["errors"]:
            print(error, file=sys.stderr)
        return 1

    if args.skip_local_build:
        blocker = out_dir / "build-blocker.md"
        if blocker.exists():
            blocker.unlink()
        preflight = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_dir.name,
            "project_root": str(project_root),
            "kai_run": str(run_dir),
            "generated_at": now(),
            "build_system": "skipped",
            "build_command": "",
            "source_hypotheses": kai["hypothesis_count"],
            "agent_count": len(kai["agents"]),
            "status": "skipped-local-build",
            "skip_local_build": True,
            "verification_mode": "logic-only",
        }
        write_json(out_dir / "preflight.json", preflight)
        print("Cole preflight passed with local build skipped; use logic-only verification.")
        print(f"Wrote {out_dir / 'preflight.json'}")
        return 0

    build = detect_build(project_root, args.build_command)
    if build.get("blocked"):
        write_build_blocker(out_dir, run_dir, build, None)
        print(f"Build preflight blocked. See {out_dir / 'build-blocker.md'}", file=sys.stderr)
        return 2

    result = run_build(project_root, build)
    if result["returncode"] != 0:
        write_build_blocker(out_dir, run_dir, build, result)
        print(f"Build preflight failed. See {out_dir / 'build-blocker.md'}", file=sys.stderr)
        return 1

    preflight = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_dir.name,
        "project_root": str(project_root),
        "kai_run": str(run_dir),
        "generated_at": now(),
        "build_system": build["system"],
        "build_command": build["display_command"],
        "source_hypotheses": kai["hypothesis_count"],
        "agent_count": len(kai["agents"]),
        "status": "passed",
        "skip_local_build": False,
        "verification_mode": "local-build",
    }
    write_json(out_dir / "preflight.json", preflight)
    print(f"Cole preflight passed: {build['display_command']}")
    print(f"Wrote {out_dir / 'preflight.json'}")
    return 0


def command_collect(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project_root)
    run_dir = resolve_under_project(project_root, args.run)
    out_dir = cole_run_dir(project_root, args.out, run_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    kai = load_kai_run(run_dir)
    if kai["errors"]:
        for error in kai["errors"]:
            print(error, file=sys.stderr)
        return 1

    normalized = []
    for agent in kai["agents"]:
        data = agent["data"]
        for item in data["hypotheses"]:
            normalized.append(normalize_hypothesis(agent, item))

    candidates = dedupe_candidates(normalized)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_dir.name,
        "project_root": str(project_root),
        "kai_run": str(run_dir),
        "generated_at": now(),
        "source_hypothesis_count": len(normalized),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
    write_json(out_dir / "candidates.json", payload)
    print(f"Cole collected {len(normalized)} Kai hypotheses into {len(candidates)} candidates")
    print(f"Wrote {out_dir / 'candidates.json'}")
    return 0


def command_validate_results(json_path: Path, candidates_path: Path | None = None) -> int:
    data = load_json(json_path)
    candidates = load_json(candidates_path) if candidates_path else None
    errors = validate_results(data, candidates)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("results.json is valid")
    return 0


def command_render_report(json_path: Path, out: Path | None = None) -> int:
    data = load_json(json_path)
    errors = validate_results(data, None)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    report_path = out or (json_path.parent / "report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(data), encoding="utf-8")
    print(f"Wrote {report_path}")
    return 0


def resolve_project_root(raw: Path) -> Path:
    project_root = raw.resolve()
    if not project_root.is_dir():
        raise SystemExit(f"Project root not found: {project_root}")
    return project_root


def resolve_under_project(project_root: Path, raw: Path) -> Path:
    path = raw if raw.is_absolute() else project_root / raw
    return path.resolve()


def path_under_project(project_root: Path, raw: str | Path) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else project_root / path


def cole_run_dir(project_root: Path, out: str, run_dir: Path) -> Path:
    return path_under_project(project_root, out) / "runs" / run_dir.name


def load_kai_run(run_dir: Path) -> dict:
    errors: list[str] = []
    manifest_path = run_dir / "spawn-manifest.json"
    if not run_dir.is_dir():
        return {"errors": [f"Kai run directory not found: {run_dir}"], "agents": [], "hypothesis_count": 0}
    if not manifest_path.is_file():
        return {"errors": [f"Missing Kai manifest: {manifest_path}"], "agents": [], "hypothesis_count": 0}

    try:
        manifest = load_json(manifest_path)
    except Exception as exc:
        return {"errors": [f"Invalid Kai manifest JSON: {exc}"], "agents": [], "hypothesis_count": 0}

    manifest_agents = manifest.get("agents")
    if not isinstance(manifest_agents, list) or not manifest_agents:
        return {"errors": ["Kai manifest must contain a non-empty agents list"], "agents": [], "hypothesis_count": 0}

    agents = []
    hypothesis_count = 0
    for idx, entry in enumerate(manifest_agents):
        if not isinstance(entry, dict):
            errors.append(f"manifest agents[{idx}] must be an object")
            continue
        agent_dir = resolve_manifest_path(run_dir, entry.get("agent_dir"))
        hypotheses_path = resolve_manifest_path(run_dir, entry.get("hypotheses_path")) or (agent_dir / "hypotheses.json" if agent_dir else None)
        report_path = resolve_manifest_path(run_dir, entry.get("report_path")) or (agent_dir / "report.md" if agent_dir else None)

        if not hypotheses_path or not hypotheses_path.is_file():
            errors.append(f"Missing hypotheses.json for manifest agent {idx}: {hypotheses_path}")
            continue
        if report_path and report_path.is_file() and PENDING_MARKER in report_path.read_text(errors="ignore"):
            errors.append(f"Pending Kai report output remains: {report_path}")

        try:
            data = load_json(hypotheses_path)
        except Exception as exc:
            errors.append(f"Invalid hypotheses JSON at {hypotheses_path}: {exc}")
            continue

        validation_errors = validate_kai_hypotheses(data, hypotheses_path)
        errors.extend(validation_errors)
        if validation_errors:
            continue
        hypothesis_count += len(data["hypotheses"])
        agents.append(
            {
                "manifest": entry,
                "data": data,
                "hypotheses_path": hypotheses_path,
                "report_path": report_path,
                "agent_id": data["agent_id"],
                "agent_name": data["agent_name"],
            }
        )

    return {"errors": errors, "manifest": manifest, "agents": agents, "hypothesis_count": hypothesis_count}


def resolve_manifest_path(run_dir: Path, raw: object) -> Path | None:
    if not raw:
        return None
    path = Path(str(raw))
    if path.is_absolute():
        return path
    direct = run_dir / path
    if direct.exists():
        return direct
    return path


def validate_kai_hypotheses(data: dict, path: Path) -> list[str]:
    errors = []
    for field in ("schema_version", "run_id", "agent_id", "agent_name", "hypotheses"):
        if field not in data:
            errors.append(f"{path}: missing top-level field {field}")
    if errors:
        return errors
    if data["schema_version"] != SCHEMA_VERSION:
        errors.append(f"{path}: unsupported schema_version {data['schema_version']}")
    if not isinstance(data["hypotheses"], list):
        errors.append(f"{path}: hypotheses must be a list")
        return errors
    for idx, item in enumerate(data["hypotheses"]):
        if not isinstance(item, dict):
            errors.append(f"{path}: hypotheses[{idx}] must be an object")
            continue
        missing = KAI_REQUIRED - set(item)
        if missing:
            errors.append(f"{path}: hypotheses[{idx}] missing fields {sorted(missing)}")
        if item.get("confidence") not in CONFIDENCE_ORDER:
            errors.append(f"{path}: hypotheses[{idx}] invalid confidence {item.get('confidence')}")
        if not isinstance(item.get("evidence"), list):
            errors.append(f"{path}: hypotheses[{idx}].evidence must be a list")
        jay_refs = item.get("jay_refs")
        if not isinstance(jay_refs, dict) or not isinstance(jay_refs.get("node_ids"), list) or not isinstance(jay_refs.get("edge_ids"), list):
            errors.append(f"{path}: hypotheses[{idx}].jay_refs must contain node_ids and edge_ids lists")
        if not isinstance(item.get("next_validation_steps"), list):
            errors.append(f"{path}: hypotheses[{idx}].next_validation_steps must be a list")
    return errors


def detect_build(project_root: Path, override: str | None = None) -> dict:
    if override:
        return {
            "system": "custom",
            "command": override,
            "shell": True,
            "display_command": override,
            "suggestions": ["Re-run the custom build command manually and fix the first compiler or dependency error."],
        }

    if (project_root / "foundry.toml").is_file():
        if not shutil.which("forge"):
            return blocked_build("foundry", "forge build", ["Install Foundry: curl -L https://foundry.paradigm.xyz | bash && foundryup", "Install dependencies, then run forge build."])
        return build_plan("foundry", ["forge", "build"], ["Run forge install if dependencies are missing, then forge build."])

    hardhat_configs = ["hardhat.config.js", "hardhat.config.ts", "hardhat.config.cjs", "hardhat.config.mjs"]
    if any((project_root / name).is_file() for name in hardhat_configs):
        if not shutil.which("npx"):
            return blocked_build("hardhat", "npx hardhat compile", ["Install Node.js/npm, run npm install, then npx hardhat compile."])
        return build_plan("hardhat", ["npx", "hardhat", "compile"], ["Run npm install, then npx hardhat compile."])

    package_json = project_root / "package.json"
    if package_json.is_file():
        scripts = {}
        try:
            scripts = json.loads(package_json.read_text(encoding="utf-8")).get("scripts", {})
        except Exception:
            scripts = {}
        if "test" in scripts:
            if not shutil.which("npm"):
                return blocked_build("npm", "npm test", ["Install Node.js/npm, run npm install, then npm test."])
            return build_plan("npm", ["npm", "test"], ["Run npm install, then npm test."])

    if (project_root / "truffle-config.js").is_file() or (project_root / "truffle.js").is_file():
        if not shutil.which("npx"):
            return blocked_build("truffle", "npx truffle compile", ["Install Node.js/npm, run npm install, then npx truffle compile."])
        return build_plan("truffle", ["npx", "truffle", "compile"], ["Run npm install, then npx truffle compile."])

    return blocked_build(
        "unknown",
        "",
        [
            "No supported build system detected.",
            "Expected foundry.toml, hardhat.config.*, package.json with a test script, or truffle-config.js.",
        ],
    )


def build_plan(system: str, command: list[str], suggestions: list[str]) -> dict:
    return {
        "system": system,
        "command": command,
        "shell": False,
        "display_command": shlex.join(command),
        "suggestions": suggestions,
    }


def blocked_build(system: str, display_command: str, suggestions: list[str]) -> dict:
    return {
        "system": system,
        "command": None,
        "shell": False,
        "display_command": display_command,
        "suggestions": suggestions,
        "blocked": True,
    }


def run_build(project_root: Path, build: dict) -> dict:
    proc = subprocess.run(
        build["command"],
        cwd=project_root,
        shell=build.get("shell", False),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def write_build_blocker(out_dir: Path, run_dir: Path, build: dict, result: dict | None) -> None:
    command = build.get("display_command") or "(no build command detected)"
    lines = [
        "# Cole Build Blocker",
        "",
        f"- Run id: `{run_dir.name}`",
        f"- Build system: `{build.get('system', 'unknown')}`",
        f"- Command: `{command}`",
    ]
    if result is not None:
        lines.append(f"- Exit code: `{result['returncode']}`")
    lines.extend(["", "## Error Summary", ""])
    if result is None:
        lines.append("Build could not start because the build system or tool is missing.")
    else:
        summary = tail_lines((result.get("stdout") or "") + "\n" + (result.get("stderr") or ""), 80)
        lines.extend(["```text", summary.rstrip() or "(no output)", "```"])
    lines.extend(["", "## Suggested Next Steps", ""])
    for suggestion in build.get("suggestions", []):
        lines.append(f"- {suggestion}")
    (out_dir / "build-blocker.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def normalize_hypothesis(agent: dict, item: dict) -> dict:
    extra = {key: value for key, value in item.items() if key not in KAI_REQUIRED}
    evidence = normalize_evidence(item.get("evidence", []))
    jay_refs = item.get("jay_refs", {})
    return {
        "source_agent_id": agent["agent_id"],
        "source_agent_name": agent["agent_name"],
        "source_hypothesis_id": item["id"],
        "source_hypotheses_path": str(agent["hypotheses_path"]),
        "title": str(item["title"]),
        "claim": str(item["claim"]),
        "category": str(item["category"]),
        "confidence": item["confidence"],
        "evidence": evidence,
        "jay_refs": {
            "node_ids": sorted(set(str(value) for value in jay_refs.get("node_ids", []))),
            "edge_ids": sorted(set(str(value) for value in jay_refs.get("edge_ids", []))),
        },
        "attack_sketch": str(item.get("attack_sketch", "")),
        "why_might_be_real": str(item.get("why_might_be_real", "")),
        "why_might_be_false_positive": str(item.get("why_might_be_false_positive", "")),
        "next_validation_steps": [str(value) for value in item.get("next_validation_steps", [])],
        "extra": extra,
        "dedupe_key": dedupe_key(item, evidence),
    }


def normalize_evidence(items: list[dict]) -> list[dict]:
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "file": str(item.get("file", "")),
                "start_line": int(item.get("start_line", 0)),
                "end_line": int(item.get("end_line", 0)),
            }
        )
    return out


def dedupe_key(item: dict, evidence: list[dict]) -> str:
    files = " ".join(sorted({entry["file"] for entry in evidence}))
    raw = " ".join([str(item.get("category", "")), str(item.get("title", "")), str(item.get("claim", "")), files])
    normalized = re.sub(r"[^a-z0-9]+", " ", raw.lower()).strip()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


def dedupe_candidates(items: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for item in items:
        grouped.setdefault(item["dedupe_key"], []).append(item)

    candidates = []
    for idx, (_key, group) in enumerate(sorted(grouped.items(), key=lambda pair: first_location(pair[1])), start=1):
        primary = sorted(group, key=lambda item: (-CONFIDENCE_ORDER[item["confidence"]], item["source_agent_id"], item["source_hypothesis_id"]))[0]
        source_hypotheses = [
            {
                "agent_id": item["source_agent_id"],
                "agent_name": item["source_agent_name"],
                "hypothesis_id": item["source_hypothesis_id"],
                "hypotheses_path": item["source_hypotheses_path"],
            }
            for item in group
        ]
        candidates.append(
            {
                "id": f"COLE-{idx:03d}",
                "title": primary["title"],
                "claim": primary["claim"],
                "category": primary["category"],
                "confidence": max((item["confidence"] for item in group), key=lambda value: CONFIDENCE_ORDER[value]),
                "evidence": merge_evidence(group),
                "jay_refs": merge_jay_refs(group),
                "source_hypotheses": source_hypotheses,
                "convergence": {
                    "source_count": len(group),
                    "agents": sorted({f"{item['source_agent_id']:02d}-{item['source_agent_name']}" for item in group}),
                },
                "attack_sketches": unique_nonempty(item["attack_sketch"] for item in group),
                "why_might_be_real": unique_nonempty(item["why_might_be_real"] for item in group),
                "why_might_be_false_positive": unique_nonempty(item["why_might_be_false_positive"] for item in group),
                "next_validation_steps": unique_nonempty(step for item in group for step in item["next_validation_steps"]),
                "extra_fields": [item["extra"] for item in group if item["extra"]],
            }
        )
    return candidates


def first_location(group: list[dict]) -> tuple[str, int, str]:
    evidence = group[0].get("evidence", [])
    if evidence:
        return (evidence[0]["file"], evidence[0]["start_line"], group[0]["source_hypothesis_id"])
    return ("", 0, group[0]["source_hypothesis_id"])


def merge_evidence(group: list[dict]) -> list[dict]:
    seen = {}
    for item in group:
        for evidence in item["evidence"]:
            seen[(evidence["file"], evidence["start_line"], evidence["end_line"])] = evidence
    return [seen[key] for key in sorted(seen)]


def merge_jay_refs(group: list[dict]) -> dict:
    node_ids = set()
    edge_ids = set()
    for item in group:
        node_ids.update(item["jay_refs"].get("node_ids", []))
        edge_ids.update(item["jay_refs"].get("edge_ids", []))
    return {"node_ids": sorted(node_ids), "edge_ids": sorted(edge_ids)}


def unique_nonempty(items) -> list[str]:
    seen = []
    present = set()
    for item in items:
        text = str(item).strip()
        if text and text not in present:
            present.add(text)
            seen.append(text)
    return seen


def validate_results(data: dict, candidates: dict | None) -> list[str]:
    errors = []
    for field in ("schema_version", "run_id", "findings"):
        if field not in data:
            errors.append(f"missing top-level field: {field}")
    if errors:
        return errors
    if data["schema_version"] != SCHEMA_VERSION:
        errors.append(f"unsupported schema_version: {data['schema_version']}")
    if not isinstance(data["findings"], list):
        errors.append("findings must be a list")
        return errors

    required = {
        "id",
        "title",
        "source_hypotheses",
        "verification_status",
        "reachability",
        "nature",
        "evidence",
        "poc",
        "reasoning",
        "final_recommendation",
    }
    ids = []
    for idx, finding in enumerate(data["findings"]):
        if not isinstance(finding, dict):
            errors.append(f"findings[{idx}] must be an object")
            continue
        missing = required - set(finding)
        if missing:
            errors.append(f"findings[{idx}] missing fields: {sorted(missing)}")
            continue
        ids.append(finding["id"])
        if finding["verification_status"] not in VALID_STATUSES:
            errors.append(f"{finding['id']}: invalid verification_status {finding['verification_status']}")
        if finding["reachability"] not in VALID_REACHABILITY:
            errors.append(f"{finding['id']}: invalid reachability {finding['reachability']}")
        if finding["nature"] not in VALID_NATURE:
            errors.append(f"{finding['id']}: invalid nature {finding['nature']}")
        if not isinstance(finding["source_hypotheses"], list) or not finding["source_hypotheses"]:
            errors.append(f"{finding['id']}: source_hypotheses must be a non-empty list")
        if not isinstance(finding["evidence"], list):
            errors.append(f"{finding['id']}: evidence must be a list")
        poc = finding["poc"]
        if not isinstance(poc, dict):
            errors.append(f"{finding['id']}: poc must be an object")
        else:
            for field in ("path", "test_command", "test_result", "notes"):
                if field not in poc:
                    errors.append(f"{finding['id']}: poc missing {field}")
            if poc.get("test_result") not in VALID_TEST_RESULTS:
                errors.append(f"{finding['id']}: invalid poc.test_result {poc.get('test_result')}")
    if len(ids) != len(set(ids)):
        errors.append("finding ids must be unique")

    if candidates is not None:
        candidate_ids = {item.get("id") for item in candidates.get("candidates", [])}
        result_ids = set(ids)
        missing = sorted(candidate_ids - result_ids)
        extra = sorted(result_ids - candidate_ids)
        if missing:
            errors.append(f"results missing candidate ids: {missing}")
        if extra:
            errors.append(f"results contain unknown candidate ids: {extra}")
    return errors


def render_report(data: dict) -> str:
    raw_findings = data["findings"]
    findings = dedupe_report_findings(raw_findings)
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding["verification_status"]] = counts.get(finding["verification_status"], 0) + 1

    lines = [
        "# Cole Varify Report",
        "",
        "## Summary",
        "",
        f"- Run id: `{data.get('run_id', '')}`",
        f"- Project root: `{data.get('project_root', '')}`",
        f"- Kai run: `{data.get('kai_run', '')}`",
        f"- Raw findings/candidates: `{len(raw_findings)}`",
        f"- Deduped report findings: `{len(findings)}`",
        "",
        "| verification status | count |",
        "| --- | ---: |",
    ]
    for status in sorted(VALID_STATUSES):
        lines.append(f"| `{status}` | {counts.get(status, 0)} |")

    lines.extend(["", "## Findings", ""])
    for finding in findings:
        lines.extend(
            [
                f"### {finding['id']}: {finding['title']}",
                "",
                f"- Status: `{finding['verification_status']}`",
                f"- Reachability: `{finding['reachability']}`",
                f"- Nature: `{finding['nature']}`",
                f"- Merged ids: `{', '.join(finding.get('merged_ids', [finding['id']]))}`",
                f"- Source hypotheses: `{', '.join(format_source_hypothesis(item) for item in finding['source_hypotheses'])}`",
                f"- PoC: `{finding['poc'].get('path', '')}`",
                f"- Test command: `{finding['poc'].get('test_command', '')}`",
                f"- Test result: `{finding['poc'].get('test_result', '')}`",
                "",
                "**Evidence**",
                "",
            ]
        )
        evidence = finding.get("evidence", [])
        if evidence:
            for item in evidence:
                lines.append(f"- `{item.get('file', '')}:{item.get('start_line', '')}-{item.get('end_line', '')}`")
        else:
            lines.append("- No source evidence recorded.")
        lines.extend(
            [
                "",
                "**Reasoning**",
                "",
                str(finding.get("reasoning", "")).strip() or "No reasoning recorded.",
                "",
                "**Final Recommendation**",
                "",
                str(finding.get("final_recommendation", "")).strip() or "No recommendation recorded.",
                "",
            ]
        )

    lines.extend(["## Build And Test Notes", "", str(data.get("build_and_test_notes", "")).strip() or "No additional notes.", ""])
    return "\n".join(lines)


def dedupe_report_findings(findings: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    order: list[str] = []
    for finding in findings:
        key = report_dedupe_key(finding)
        if key not in grouped:
            order.append(key)
        grouped.setdefault(key, []).append(finding)
    return [merge_report_group(grouped[key]) for key in order]


def report_dedupe_key(finding: dict) -> str:
    explicit = str(finding.get("dedupe_key", "")).strip()
    if explicit:
        return f"manual:{explicit}"
    evidence = finding.get("evidence", [])
    evidence_key = "|".join(
        f"{item.get('file', '')}:{item.get('start_line', '')}-{item.get('end_line', '')}"
        for item in sorted(evidence, key=lambda item: (str(item.get("file", "")), int(item.get("start_line", 0)), int(item.get("end_line", 0))))
    )
    raw = " ".join([str(finding.get("title", "")), str(finding.get("nature", "")), evidence_key])
    return "auto:" + re.sub(r"[^a-z0-9]+", " ", raw.lower()).strip()


def merge_report_group(group: list[dict]) -> dict:
    merged = dict(group[0])
    merged["merged_ids"] = unique_nonempty(item.get("id", "") for item in group)
    merged["source_hypotheses"] = merge_source_hypotheses(group)
    merged["evidence"] = merge_result_evidence(group)
    merged["verification_status"] = highest_value(group, "verification_status", STATUS_PRIORITY)
    merged["reachability"] = highest_value(group, "reachability", REACHABILITY_PRIORITY)
    merged["nature"] = highest_value(group, "nature", NATURE_PRIORITY)
    merged["poc"] = best_poc(group)
    merged["reasoning"] = merge_text_field(group, "reasoning")
    merged["final_recommendation"] = merge_text_field(group, "final_recommendation")
    return merged


def merge_source_hypotheses(group: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for finding in group:
        for item in finding.get("source_hypotheses", []):
            key = json.dumps(item, sort_keys=True)
            seen[key] = item
    return [seen[key] for key in sorted(seen)]


def merge_result_evidence(group: list[dict]) -> list[dict]:
    seen: dict[tuple[str, int, int], dict] = {}
    for finding in group:
        for item in finding.get("evidence", []):
            key = (str(item.get("file", "")), int(item.get("start_line", 0)), int(item.get("end_line", 0)))
            seen[key] = item
    return [seen[key] for key in sorted(seen)]


def highest_value(group: list[dict], field: str, priority: dict[str, int]) -> str:
    return max((str(item.get(field, "")) for item in group), key=lambda value: priority.get(value, 0))


def best_poc(group: list[dict]) -> dict:
    for finding in group:
        poc = finding.get("poc", {})
        if poc.get("path") or poc.get("test_command"):
            return poc
    return group[0].get("poc", {})


def merge_text_field(group: list[dict], field: str) -> str:
    parts = []
    for finding in group:
        text = str(finding.get(field, "")).strip()
        if text:
            parts.append(f"[{finding.get('id', '?')}] {text}")
    return "\n\n".join(parts)


def format_source_hypothesis(item: dict) -> str:
    agent = item.get("agent_id", "?")
    name = item.get("agent_name", "?")
    hypothesis_id = item.get("hypothesis_id", "?")
    return f"{agent}-{name}:{hypothesis_id}"


def load_json(path: Path | None) -> dict:
    if path is None:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def tail_lines(text: str, count: int) -> str:
    return "\n".join(text.splitlines()[-count:])


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
