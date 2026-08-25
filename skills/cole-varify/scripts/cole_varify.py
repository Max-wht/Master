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
VALID_TEST_RESULTS = {"not-run", "passed", "failed", "blocked"}
VALID_RUNTIME_VALUES = {"auto", "solidity", "move", "anchor"}
MAX_JUDGE_PARALLEL = 6
VALID_CLASSIFICATIONS = {"High", "Medium", "Low", "Info", "Gas", "Invalid"}
CLASSIFICATION_PREFIX = {
    "High": "H",
    "Medium": "M",
    "Low": "L",
    "Info": "I",
    "Gas": "G",
    "Invalid": "Invalid",
}
VALID_CONDITION_STATUSES = {"true", "false", "depend on role"}
SECURITY_CLASSIFICATIONS = {"High", "Medium", "Low", "Gas"}
VALID_BOUNTY_RECOMMENDATIONS = {"Submit bounty", "Do not submit"}
AMBIGUOUS_LABEL_RE = re.compile(
    r"\b(conditional|potential|possible|likely|maybe|needs?\s*-?\s*poc|tentative|uncertain|unconfirmed|unproven|unknown|unclear)\b",
    re.IGNORECASE,
)

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
    preflight.add_argument("--runtime", default="auto", choices=sorted(VALID_RUNTIME_VALUES), help="Override runtime build detection")

    collect = subparsers.add_parser("collect", help="Collect, normalize, and deduplicate Kai hypotheses")
    collect.add_argument("project_root", type=Path)
    collect.add_argument("--run", required=True, type=Path, help="Kai run directory")
    collect.add_argument("--out", default=DEFAULT_OUT, help="Cole output root, relative to project root unless absolute")

    validate = subparsers.add_parser("validate-results", help="Validate Cole results.json")
    validate.add_argument("json_path", type=Path)
    validate.add_argument("--candidates", type=Path, default=None, help="Optional candidates.json coverage check")

    render = subparsers.add_parser("render-report", help="Render wreport.md from final results.json")
    render.add_argument("json_path", type=Path)
    render.add_argument("--out", type=Path, default=None, help="Report path; defaults to sibling wreport.md")

    prepare_judges = subparsers.add_parser("prepare-judges", help="Create one strict Judge bundle per deduped finding")
    prepare_judges.add_argument("candidates_path", type=Path)
    prepare_judges.add_argument("--out", type=Path, default=None, help="Judge task directory; defaults to sibling judges/")

    validate_judges = subparsers.add_parser("validate-judges", help="Validate strict Judge outputs")
    validate_judges.add_argument("manifest_path", type=Path, help="judges/manifest.json or judges directory")

    apply_judges = subparsers.add_parser("apply-judges", help="Merge strict Judge outputs into results.json and wreport.md")
    apply_judges.add_argument("candidates_path", type=Path)
    apply_judges.add_argument("--manifest", type=Path, default=None, help="Judge manifest; defaults to sibling judges/manifest.json")
    apply_judges.add_argument("--results-out", type=Path, default=None, help="Final results.json path; defaults to sibling results.json")
    apply_judges.add_argument("--report-out", type=Path, default=None, help="Final wreport.md path; defaults to sibling wreport.md")

    args = parser.parse_args()
    if args.command == "preflight":
        return command_preflight(args)
    if args.command == "collect":
        return command_collect(args)
    if args.command == "validate-results":
        return command_validate_results(args.json_path, args.candidates)
    if args.command == "render-report":
        return command_render_report(args.json_path, args.out)
    if args.command == "prepare-judges":
        return command_prepare_judges(args.candidates_path, args.out)
    if args.command == "validate-judges":
        return command_validate_judges(args.manifest_path)
    if args.command == "apply-judges":
        return command_apply_judges(args.candidates_path, args.manifest, args.results_out, args.report_out)
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
    runtime = resolve_runtime(project_root, kai.get("manifest", {}), args.runtime)

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
            "runtime": runtime,
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

    build = detect_build(project_root, args.build_command, runtime)
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
        "runtime": runtime,
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
    (out_dir / "wreport.md").write_text(render_draft_wreport(payload), encoding="utf-8")
    print(f"Cole collected {len(normalized)} Kai hypotheses into {len(candidates)} candidates")
    print(f"Wrote {out_dir / 'candidates.json'}")
    print(f"Wrote {out_dir / 'wreport.md'}")
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
    report_path = out or (json_path.parent / "wreport.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_final_wreport(data), encoding="utf-8")
    print(f"Wrote {report_path}")
    return 0


def command_prepare_judges(candidates_path: Path, out: Path | None = None) -> int:
    data = load_json(candidates_path)
    errors = validate_candidates_payload(data)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    judges_dir = out or (candidates_path.parent / "judges")
    judges_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "run_id": data.get("run_id", ""),
        "project_root": data.get("project_root", ""),
        "kai_run": data.get("kai_run", ""),
        "candidates_path": str(candidates_path),
        "max_parallel": MAX_JUDGE_PARALLEL,
        "judges": [],
    }
    for candidate in data["candidates"]:
        task_dir = judges_dir / candidate["id"]
        task_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = task_dir / "bundle.md"
        output_json = task_dir / "judge.json"
        output_markdown = task_dir / "judge.md"
        bundle_path.write_text(render_judge_bundle(data, candidate, output_json, output_markdown), encoding="utf-8")
        manifest["judges"].append(
            {
                "candidate_id": candidate["id"],
                "title": candidate["title"],
                "bundle_path": str(bundle_path),
                "output_json": str(output_json),
                "output_markdown": str(output_markdown),
            }
        )
    write_json(judges_dir / "manifest.json", manifest)
    print(f"Wrote {judges_dir / 'manifest.json'}")
    return 0


def command_validate_judges(manifest_path: Path) -> int:
    manifest = load_judge_manifest(manifest_path)
    errors = validate_judge_outputs(manifest)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("Judge outputs are valid")
    return 0


def command_apply_judges(candidates_path: Path, manifest_path: Path | None = None, results_out: Path | None = None, report_out: Path | None = None) -> int:
    candidates = load_json(candidates_path)
    candidate_errors = validate_candidates_payload(candidates)
    if candidate_errors:
        for error in candidate_errors:
            print(error, file=sys.stderr)
        return 1

    manifest = load_judge_manifest(manifest_path or (candidates_path.parent / "judges" / "manifest.json"))
    judge_errors = validate_judge_outputs(manifest)
    if judge_errors:
        for error in judge_errors:
            print(error, file=sys.stderr)
        return 1

    judge_by_id = {entry["candidate_id"]: load_json(Path(entry["output_json"])) for entry in manifest["judges"]}
    missing = [candidate["id"] for candidate in candidates["candidates"] if candidate["id"] not in judge_by_id]
    if missing:
        for candidate_id in missing:
            print(f"missing Judge output for {candidate_id}", file=sys.stderr)
        return 1

    final_counts = {classification: 0 for classification in VALID_CLASSIFICATIONS}
    findings = []
    for candidate in candidates["candidates"]:
        judge = judge_by_id[candidate["id"]]
        classification = judge["classification"]
        final_counts[classification] += 1
        final_id = f"{CLASSIFICATION_PREFIX[classification]}-{final_counts[classification]}"
        findings.append(finalize_finding(candidate, judge, final_id))

    results = {
        "schema_version": SCHEMA_VERSION,
        "run_id": candidates.get("run_id", ""),
        "project_root": candidates.get("project_root", ""),
        "kai_run": candidates.get("kai_run", ""),
        "generated_at": now(),
        "findings": findings,
    }
    results_path = results_out or (candidates_path.parent / "results.json")
    report_path = report_out or (candidates_path.parent / "wreport.md")
    write_json(results_path, results)
    report_path.write_text(render_final_wreport(results), encoding="utf-8")
    print(f"Wrote {results_path}")
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


def resolve_runtime(project_root: Path, manifest: dict, requested: str) -> str:
    if requested != "auto":
        return requested
    manifest_runtime = manifest.get("runtime")
    if manifest_runtime in {"solidity", "move", "anchor"}:
        return manifest_runtime
    if (project_root / "Anchor.toml").is_file():
        return "anchor"
    if (project_root / "Move.toml").is_file() or any(project_root.rglob("*.move")):
        return "move"
    if (project_root / "foundry.toml").is_file() or any((project_root / name).is_file() for name in ("hardhat.config.js", "hardhat.config.ts", "hardhat.config.cjs", "hardhat.config.mjs")):
        return "solidity"
    return "solidity"


def detect_build(project_root: Path, override: str | None = None, runtime: str = "auto") -> dict:
    if override:
        return {
            "system": "custom",
            "command": override,
            "shell": True,
            "display_command": override,
            "suggestions": ["Re-run the custom build command manually and fix the first compiler or dependency error."],
        }

    if runtime in {"auto", "anchor"} and (project_root / "Anchor.toml").is_file():
        if not shutil.which("anchor"):
            return blocked_build("anchor", "anchor build", ["Install Anchor CLI and Solana toolchain, then run anchor build."])
        return build_plan("anchor", ["anchor", "build"], ["Install dependencies, then run anchor build."])

    if runtime in {"auto", "move"} and ((project_root / "Move.toml").is_file() or any(project_root.rglob("*.move"))):
        return detect_move_build(project_root)

    if runtime in {"auto", "solidity"} and (project_root / "foundry.toml").is_file():
        if not shutil.which("forge"):
            return blocked_build("foundry", "forge build", ["Install Foundry: curl -L https://foundry.paradigm.xyz | bash && foundryup", "Install dependencies, then run forge build."])
        return build_plan("foundry", ["forge", "build"], ["Run forge install if dependencies are missing, then forge build."])

    hardhat_configs = ["hardhat.config.js", "hardhat.config.ts", "hardhat.config.cjs", "hardhat.config.mjs"]
    if runtime in {"auto", "solidity"} and any((project_root / name).is_file() for name in hardhat_configs):
        if not shutil.which("npx"):
            return blocked_build("hardhat", "npx hardhat compile", ["Install Node.js/npm, run npm install, then npx hardhat compile."])
        return build_plan("hardhat", ["npx", "hardhat", "compile"], ["Run npm install, then npx hardhat compile."])

    package_json = project_root / "package.json"
    if runtime in {"auto", "solidity"} and package_json.is_file():
        scripts = {}
        try:
            scripts = json.loads(package_json.read_text(encoding="utf-8")).get("scripts", {})
        except Exception:
            scripts = {}
        if "test" in scripts:
            if not shutil.which("npm"):
                return blocked_build("npm", "npm test", ["Install Node.js/npm, run npm install, then npm test."])
            return build_plan("npm", ["npm", "test"], ["Run npm install, then npm test."])

    if runtime in {"auto", "solidity"} and ((project_root / "truffle-config.js").is_file() or (project_root / "truffle.js").is_file()):
        if not shutil.which("npx"):
            return blocked_build("truffle", "npx truffle compile", ["Install Node.js/npm, run npm install, then npx truffle compile."])
        return build_plan("truffle", ["npx", "truffle", "compile"], ["Run npm install, then npx truffle compile."])

    return blocked_build(
        "unknown",
        "",
        [
            "No supported build system detected.",
            "Expected Anchor.toml, Move.toml, foundry.toml, hardhat.config.*, package.json with a test script, or truffle-config.js.",
        ],
    )


def detect_move_build(project_root: Path) -> dict:
    profile = move_profile(project_root)
    if profile == "sui":
        if shutil.which("sui"):
            return build_plan("sui-move", ["sui", "move", "build"], ["Run sui move build after dependency setup."])
        if shutil.which("aptos"):
            return build_plan("aptos-move", ["aptos", "move", "compile"], ["Run aptos move compile after dependency setup."])
    elif profile == "aptos":
        if shutil.which("aptos"):
            return build_plan("aptos-move", ["aptos", "move", "compile"], ["Run aptos move compile after dependency setup."])
        if shutil.which("sui"):
            return build_plan("sui-move", ["sui", "move", "build"], ["Run sui move build after dependency setup."])
    else:
        if shutil.which("sui"):
            return build_plan("sui-move", ["sui", "move", "build"], ["Run sui move build after dependency setup."])
        if shutil.which("aptos"):
            return build_plan("aptos-move", ["aptos", "move", "compile"], ["Run aptos move compile after dependency setup."])
    return blocked_build(
        "move",
        "sui move build OR aptos move compile",
        ["Install Sui CLI for Sui Move or Aptos CLI for Aptos Move, then re-run preflight."],
    )


def move_profile(project_root: Path) -> str:
    haystack = ""
    manifest = project_root / "Move.toml"
    if manifest.is_file():
        haystack += manifest.read_text(errors="ignore").lower()
    for path in list(project_root.rglob("*.move"))[:80]:
        haystack += "\n" + path.read_text(errors="ignore").lower()
    if "sui::" in haystack or "sui-framework" in haystack:
        return "sui"
    if "aptos_framework" in haystack or "aptos::" in haystack:
        return "aptos"
    return "generic"


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
                "id": f"finding-{idx:03d}",
                "title": primary["title"],
                "claim": primary["claim"],
                "category": primary["category"],
                "confidence": max((item["confidence"] for item in group), key=lambda value: CONFIDENCE_ORDER[value]),
                "dedupe_key": group[0]["dedupe_key"],
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
        "candidate_id",
        "final_id",
        "classification",
        "title",
        "source_hypotheses",
        "evidence",
        "poc",
        "judge",
    }
    candidate_ids = []
    final_ids = []
    for idx, finding in enumerate(data["findings"]):
        if not isinstance(finding, dict):
            errors.append(f"findings[{idx}] must be an object")
            continue
        missing = required - set(finding)
        if missing:
            errors.append(f"findings[{idx}] missing fields: {sorted(missing)}")
            continue
        candidate_id = str(finding["candidate_id"])
        final_id = str(finding["final_id"])
        classification = str(finding["classification"])
        candidate_ids.append(candidate_id)
        final_ids.append(final_id)
        if not is_candidate_id(candidate_id):
            errors.append(f"{candidate_id}: invalid candidate_id")
        if classification not in VALID_CLASSIFICATIONS:
            errors.append(f"{candidate_id}: invalid classification {classification}")
        if ambiguous_label(classification):
            errors.append(f"{candidate_id}: ambiguous classification {classification}")
        if not valid_final_id(final_id, classification):
            errors.append(f"{candidate_id}: final_id {final_id} does not match classification {classification}")
        if not isinstance(finding["source_hypotheses"], list) or not finding["source_hypotheses"]:
            errors.append(f"{candidate_id}: source_hypotheses must be a non-empty list")
        if not isinstance(finding["evidence"], list):
            errors.append(f"{candidate_id}: evidence must be a list")
        poc_errors = validate_poc(finding["poc"], candidate_id)
        errors.extend(poc_errors)
        judge = finding["judge"]
        if not isinstance(judge, dict):
            errors.append(f"{candidate_id}: judge must be an object")
        else:
            errors.extend(validate_judge_result(judge, candidate_id))
    if len(candidate_ids) != len(set(candidate_ids)):
        errors.append("candidate ids must be unique")
    if len(final_ids) != len(set(final_ids)):
        errors.append("final ids must be unique")

    if candidates is not None:
        expected_ids = {item.get("id") for item in candidates.get("candidates", [])}
        result_ids = set(candidate_ids)
        missing = sorted(expected_ids - result_ids)
        extra = sorted(result_ids - expected_ids)
        if missing:
            errors.append(f"results missing candidate ids: {missing}")
        if extra:
            errors.append(f"results contain unknown candidate ids: {extra}")
    return errors


def validate_candidates_payload(data: dict) -> list[str]:
    errors = []
    for field in ("schema_version", "run_id", "candidates"):
        if field not in data:
            errors.append(f"missing top-level field: {field}")
    if errors:
        return errors
    if data["schema_version"] != SCHEMA_VERSION:
        errors.append(f"unsupported schema_version: {data['schema_version']}")
    if not isinstance(data["candidates"], list):
        errors.append("candidates must be a list")
        return errors
    ids = []
    for idx, candidate in enumerate(data["candidates"]):
        if not isinstance(candidate, dict):
            errors.append(f"candidates[{idx}] must be an object")
            continue
        missing = {"id", "title", "claim", "source_hypotheses", "evidence"} - set(candidate)
        if missing:
            errors.append(f"candidates[{idx}] missing fields: {sorted(missing)}")
            continue
        ids.append(candidate["id"])
        if not is_candidate_id(str(candidate["id"])):
            errors.append(f"{candidate['id']}: invalid candidate id")
    if len(ids) != len(set(ids)):
        errors.append("candidate ids must be unique")
    return errors


def load_judge_manifest(path: Path) -> dict:
    manifest_path = path / "manifest.json" if path.is_dir() else path
    return load_json(manifest_path)


def validate_judge_outputs(manifest: dict) -> list[str]:
    errors = []
    for field in ("schema_version", "max_parallel", "judges"):
        if field not in manifest:
            errors.append(f"judge manifest missing {field}")
    if errors:
        return errors
    if manifest["schema_version"] != SCHEMA_VERSION:
        errors.append(f"unsupported judge manifest schema_version: {manifest['schema_version']}")
    if manifest["max_parallel"] != MAX_JUDGE_PARALLEL:
        errors.append(f"judge manifest max_parallel must be {MAX_JUDGE_PARALLEL}")
    if not isinstance(manifest["judges"], list):
        errors.append("judge manifest judges must be a list")
        return errors
    for idx, entry in enumerate(manifest["judges"]):
        if not isinstance(entry, dict):
            errors.append(f"judge manifest judges[{idx}] must be an object")
            continue
        for field in ("candidate_id", "output_json"):
            if field not in entry:
                errors.append(f"judge manifest judges[{idx}] missing {field}")
        if "output_json" not in entry:
            continue
        output_json = Path(str(entry["output_json"]))
        if not output_json.is_file():
            errors.append(f"{entry.get('candidate_id', '?')}: missing Judge output {output_json}")
            continue
        try:
            judge = load_json(output_json)
        except Exception as exc:
            errors.append(f"{entry.get('candidate_id', '?')}: invalid Judge JSON: {exc}")
            continue
        errors.extend(validate_judge_result(judge, str(entry.get("candidate_id", ""))))
    return errors


def validate_judge_result(judge: dict, expected_candidate_id: str) -> list[str]:
    errors = []
    required = {
        "schema_version",
        "candidate_id",
        "classification",
        "verdict",
        "title",
        "finding_summary",
        "required_conditions",
        "reachability",
        "code_reality",
        "protocol_semantics",
        "impact",
        "bounty_recommendation",
    }
    missing = required - set(judge)
    if missing:
        return [f"{expected_candidate_id}: Judge output missing fields: {sorted(missing)}"]
    candidate_id = str(judge["candidate_id"])
    classification = str(judge["classification"])
    verdict = str(judge["verdict"])
    if judge["schema_version"] != SCHEMA_VERSION:
        errors.append(f"{candidate_id}: unsupported Judge schema_version {judge['schema_version']}")
    if expected_candidate_id and candidate_id != expected_candidate_id:
        errors.append(f"{expected_candidate_id}: Judge candidate_id mismatch {candidate_id}")
    if not is_candidate_id(candidate_id):
        errors.append(f"{candidate_id}: invalid Judge candidate_id")
    if classification not in VALID_CLASSIFICATIONS:
        errors.append(f"{candidate_id}: classification must be one of {sorted(VALID_CLASSIFICATIONS)}, got {classification}")
    if verdict != classification:
        errors.append(f"{candidate_id}: verdict must exactly equal classification")
    for label_field in ("classification", "verdict", "severity", "status"):
        if label_field in judge and ambiguous_label(str(judge[label_field])):
            errors.append(f"{candidate_id}: ambiguous {label_field} {judge[label_field]}")
    if str(judge["bounty_recommendation"]) not in VALID_BOUNTY_RECOMMENDATIONS:
        errors.append(f"{candidate_id}: invalid bounty_recommendation {judge['bounty_recommendation']}")
    if ambiguous_label(str(judge["bounty_recommendation"])):
        errors.append(f"{candidate_id}: ambiguous bounty_recommendation {judge['bounty_recommendation']}")
    conditions = judge["required_conditions"]
    if not isinstance(conditions, list) or not conditions:
        errors.append(f"{candidate_id}: required_conditions must be a non-empty list")
    else:
        statuses = []
        for idx, condition in enumerate(conditions):
            if not isinstance(condition, dict):
                errors.append(f"{candidate_id}: required_conditions[{idx}] must be an object")
                continue
            for field in ("condition", "status", "evidence"):
                if field not in condition:
                    errors.append(f"{candidate_id}: required_conditions[{idx}] missing {field}")
            status = str(condition.get("status", ""))
            statuses.append(status)
            if status not in VALID_CONDITION_STATUSES:
                errors.append(f"{candidate_id}: required_conditions[{idx}] invalid status {status}")
            if ambiguous_label(status):
                errors.append(f"{candidate_id}: ambiguous required_conditions[{idx}] status {status}")
        if classification in SECURITY_CLASSIFICATIONS and any(status != "true" for status in statuses):
            errors.append(f"{candidate_id}: {classification} requires every condition to be true")
        if classification == "Info" and any(status == "false" for status in statuses):
            errors.append(f"{candidate_id}: Info cannot include false conditions")
        if classification == "Invalid" and statuses and all(status == "true" for status in statuses):
            errors.append(f"{candidate_id}: Invalid requires at least one false or depend on role condition")
    errors.extend(validate_poc(judge.get("poc", empty_poc()), candidate_id))
    return errors


def validate_poc(poc: object, candidate_id: str) -> list[str]:
    errors = []
    if not isinstance(poc, dict):
        return [f"{candidate_id}: poc must be an object"]
    for field in ("path", "test_command", "test_result", "notes"):
        if field not in poc:
            errors.append(f"{candidate_id}: poc missing {field}")
    if poc.get("test_result") not in VALID_TEST_RESULTS:
        errors.append(f"{candidate_id}: invalid poc.test_result {poc.get('test_result')}")
    path = str(poc.get("path", ""))
    command = str(poc.get("test_command", ""))
    if "COLE-" in path or "COLE-" in command:
        errors.append(f"{candidate_id}: poc path/test command must not contain COLE-")
    return errors


def render_draft_wreport(data: dict) -> str:
    lines = [
        "# WReport",
        "",
        f"- Run id: `{data.get('run_id', '')}`",
        f"- Project root: `{data.get('project_root', '')}`",
        f"- Kai run: `{data.get('kai_run', '')}`",
        f"- Deduped findings: `{len(data.get('candidates', []))}`",
        "",
    ]
    for idx, candidate in enumerate(data.get("candidates", []), start=1):
        lines.extend(
            [
                f"## Finding {idx}: {candidate.get('title', '')}",
                f"<!-- candidate_id: {candidate.get('id', '')} -->",
                "",
                "### Description",
                "",
                str(candidate.get("claim", "")).strip() or "No description recorded.",
                "",
            ]
        )
        attack_sketches = candidate.get("attack_sketches", [])
        if attack_sketches:
            lines.append("Attack sketch:")
            for item in attack_sketches:
                lines.append(f"- {item}")
            lines.append("")
        lines.extend(["### Impact", ""])
        impacts = candidate.get("why_might_be_real", []) or candidate.get("next_validation_steps", [])
        if impacts:
            for item in impacts:
                lines.append(f"- {item}")
        else:
            lines.append("- Impact is not yet verified by Judge.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_judge_bundle(data: dict, candidate: dict, output_json: Path, output_markdown: Path) -> str:
    return "\n".join(
        [
            f"# Strict Judge Task: {candidate['id']}",
            "",
            "You are a Judge for exactly one security finding. Your job is not to defend the finding.",
            "Decompose every required condition, read source and protocol docs, and return only an exact final classification.",
            "",
            "## Hard Output Rules",
            "",
            "- The final classification must be exactly one of: `High`, `Medium`, `Low`, `Info`, `Gas`, `Invalid`.",
            "- Do not output any missing-proof bucket, conditional severity, possible severity, likely validity, or other fuzzy label.",
            "- If one pass cannot support an exact classification, ask the parent thread for the missing evidence/context instead of writing `judge.json`.",
            "- `High`, `Medium`, `Low`, and `Gas` require every required condition to be `true`.",
            "- `Info` may use `depend on role` for real trusted-role or design-risk notes, but cannot include `false`.",
            "- `Invalid` requires at least one required condition to be `false` or `depend on role`.",
            "- `bounty_recommendation` must be exactly `Submit bounty` or `Do not submit`.",
            "",
            "## Required Review Flow",
            "",
            "1. Restore the finding: claim, broken invariant/trust boundary, and claimed impact.",
            "2. List all conditions/assumptions and mark each `true`, `false`, or `depend on role`.",
            "3. Decide ordinary-user reachability, including direct calls, flash loans, malicious contracts, privileged roles, config, and hypothetical states.",
            "4. If ordinary users cannot reach it, analyze the trusted-role boundary and whether the action is expected authority.",
            "5. Verify code reality with functions, variables, guards, and execution path evidence.",
            "6. Verify protocol semantics from README/docs/tests where available.",
            "7. Verify impact type and whether the harm is closed-loop proved.",
            "8. Return one exact classification.",
            "",
            "## Output Files",
            "",
            f"- Write strict JSON to `{output_json}`.",
            f"- Write the human-readable Judge report to `{output_markdown}`.",
            "",
            "JSON shape:",
            "",
            "```json",
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "candidate_id": candidate["id"],
                    "classification": "High|Medium|Low|Info|Gas|Invalid",
                    "verdict": "same exact value as classification",
                    "title": candidate["title"],
                    "finding_summary": "",
                    "required_conditions": [{"condition": "", "status": "true|false|depend on role", "evidence": ""}],
                    "reachability": "",
                    "code_reality": "",
                    "protocol_semantics": "",
                    "impact": "",
                    "bounty_recommendation": "Submit bounty|Do not submit",
                    "poc": empty_poc(),
                },
                indent=2,
            ),
            "```",
            "",
            "## Candidate",
            "",
            "```json",
            json.dumps(candidate, indent=2, sort_keys=True),
            "```",
            "",
            "## Run Context",
            "",
            f"- Project root: `{data.get('project_root', '')}`",
            f"- Kai run: `{data.get('kai_run', '')}`",
            f"- Run id: `{data.get('run_id', '')}`",
            "",
        ]
    )


def finalize_finding(candidate: dict, judge: dict, final_id: str) -> dict:
    classification = judge["classification"]
    poc = finalize_poc(judge.get("poc", empty_poc()), candidate["id"], final_id)
    final_judge = dict(judge)
    final_judge["poc"] = poc
    return {
        "candidate_id": candidate["id"],
        "final_id": final_id,
        "classification": classification,
        "title": judge.get("title") or candidate["title"],
        "source_hypotheses": candidate["source_hypotheses"],
        "evidence": candidate["evidence"],
        "poc": poc,
        "judge": final_judge,
    }


def finalize_poc(poc: dict, candidate_id: str, final_id: str) -> dict:
    out = {
        "path": str(poc.get("path", "")),
        "test_command": str(poc.get("test_command", "")),
        "test_result": str(poc.get("test_result", "not-run")),
        "notes": str(poc.get("notes", "")),
    }
    if not out["path"] and not out["test_command"]:
        return out
    final_slug = final_id.lower().replace("-", "_")
    dash_slug = final_id.lower()
    for old, new in (
        (candidate_id, dash_slug),
        (candidate_id.replace("-", "_"), final_slug),
    ):
        out["path"] = out["path"].replace(old, new)
        out["test_command"] = out["test_command"].replace(old, new)
    return out


def render_final_wreport(data: dict) -> str:
    counts = {classification: 0 for classification in sorted(VALID_CLASSIFICATIONS)}
    for finding in data.get("findings", []):
        counts[finding["classification"]] = counts.get(finding["classification"], 0) + 1
    lines = [
        "# WReport",
        "",
        f"- Run id: `{data.get('run_id', '')}`",
        f"- Project root: `{data.get('project_root', '')}`",
        f"- Kai run: `{data.get('kai_run', '')}`",
        "",
        "| classification | count |",
        "| --- | ---: |",
    ]
    for classification in ("High", "Medium", "Low", "Info", "Gas", "Invalid"):
        lines.append(f"| `{classification}` | {counts.get(classification, 0)} |")
    lines.append("")

    for finding in data.get("findings", []):
        judge = finding["judge"]
        lines.extend(
            [
                f"## [{finding['final_id']}] {finding['title']}",
                f"<!-- candidate_id: {finding['candidate_id']} -->",
                "",
                "### Finding Summary",
                "",
                text_or_default(judge.get("finding_summary"), "No finding summary recorded."),
                "",
                "### Required Conditions",
                "",
            ]
        )
        for condition in judge.get("required_conditions", []):
            lines.append(f"- [{condition.get('status', '')}] {condition.get('condition', '')} Evidence: {condition.get('evidence', '')}")
        lines.extend(
            [
                "",
                "### Reachability",
                "",
                text_or_default(judge.get("reachability"), "No reachability analysis recorded."),
                "",
                "### Code Reality",
                "",
                text_or_default(judge.get("code_reality"), "No code reality analysis recorded."),
                "",
                "### Protocol Semantics",
                "",
                text_or_default(judge.get("protocol_semantics"), "No protocol semantics analysis recorded."),
                "",
                "### Impact",
                "",
                text_or_default(judge.get("impact"), "No impact analysis recorded."),
                "",
                "### Verdict",
                "",
                finding["classification"],
                "",
                "### Bounty Recommendation",
                "",
                text_or_default(judge.get("bounty_recommendation"), "Do not submit"),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def text_or_default(value: object, default: str) -> str:
    text = str(value or "").strip()
    return text or default


def empty_poc() -> dict:
    return {"path": "", "test_command": "", "test_result": "not-run", "notes": ""}


def is_candidate_id(value: str) -> bool:
    return bool(re.fullmatch(r"finding-\d{3}", value))


def valid_final_id(final_id: str, classification: str) -> bool:
    prefix = CLASSIFICATION_PREFIX.get(classification)
    if not prefix:
        return False
    return bool(re.fullmatch(rf"{re.escape(prefix)}-\d+", final_id))


def ambiguous_label(value: str) -> bool:
    return bool(AMBIGUOUS_LABEL_RE.search(value))


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
