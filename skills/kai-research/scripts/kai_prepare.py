#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "1.0.0"
PENDING_MARKER = "PENDING_KAI_AGENT_OUTPUT"
EXCLUDED_DIRS = {
    ".git",
    "Lloyd",
    "MasterWu",
    "artifacts",
    "build",
    "cache",
    "interfaces",
    "lib",
    "mock",
    "mocks",
    "node_modules",
    "out",
    "test",
    "tests",
}
CONFIDENCE_VALUES = {"low", "medium", "high"}
BASE_REFERENCES = ["shared-rules.md", "judging.md", "report-formatting.md", "senior-auditor-sop.md"]

AGENTS = [
    {
        "id": 1,
        "slug": "math-precision",
        "title": "Math Precision",
        "reference": "subAgents/agent-01-math-precision.md",
        "edge_types": {"reads", "writes", "state_transition"},
        "node_types": {"function", "state_var"},
        "keywords": ["round", "decimal", "scale", "precision", "mulDiv", "wad", "ray", "cast", "uint", "int", "overflow", "underflow", "division", "fee", "bps"],
    },
    {
        "id": 2,
        "slug": "access-control",
        "title": "Access Control",
        "reference": "subAgents/agent-02-access-control.md",
        "edge_types": {"guards", "external_call", "precondition_written_by"},
        "node_types": {"function", "guard", "state_var"},
        "keywords": ["owner", "admin", "role", "auth", "only", "init", "initialize", "upgrade", "delegatecall", "proxy", "permission", "guardian", "governance"],
    },
    {
        "id": 3,
        "slug": "economic-security",
        "title": "Economic Security",
        "reference": "subAgents/agent-03-economic-security.md",
        "edge_types": {"external_call", "transfers_value", "reads", "writes"},
        "node_types": {"function", "state_var", "external_symbol"},
        "keywords": ["token", "transfer", "balance", "price", "oracle", "swap", "fee", "reward", "incentive", "flash", "liquidity", "share", "asset"],
    },
    {
        "id": 4,
        "slug": "execution-trace",
        "title": "Execution Trace",
        "reference": "subAgents/agent-04-execution-trace.md",
        "edge_types": {"calls", "external_call", "writes", "guards", "state_transition", "precondition_written_by"},
        "node_types": {"function", "guard", "state_var"},
        "keywords": ["entry", "execute", "process", "settle", "finalize", "callback", "branch", "state", "phase", "nonce", "queue"],
    },
    {
        "id": 5,
        "slug": "invariant",
        "title": "Invariant",
        "reference": "subAgents/agent-05-invariant.md",
        "edge_types": {"reads", "writes", "state_transition", "precondition_written_by"},
        "node_types": {"function", "state_var", "guard"},
        "keywords": ["total", "supply", "balance", "debt", "asset", "liability", "cap", "limit", "reserve", "share", "accounting", "invariant"],
    },
    {
        "id": 6,
        "slug": "periphery",
        "title": "Periphery",
        "reference": "subAgents/agent-06-periphery.md",
        "edge_types": {"calls", "external_call", "reads", "writes"},
        "node_types": {"function", "contract_or_module", "external_symbol"},
        "keywords": ["helper", "library", "util", "encode", "decode", "wrapper", "adapter", "router", "base", "abstract", "preview", "quote"],
    },
    {
        "id": 7,
        "slug": "first-principles",
        "title": "First Principles",
        "reference": "subAgents/agent-07-first-principles.md",
        "edge_types": {"reads", "writes", "guards", "external_call", "transfers_value", "state_transition"},
        "node_types": {"function", "state_var", "guard", "external_symbol"},
        "keywords": ["assume", "trust", "intent", "model", "solvent", "permissionless", "permissioned", "canonical", "underlying", "source", "truth"],
    },
    {
        "id": 8,
        "slug": "asymmetry",
        "title": "Asymmetry",
        "reference": "subAgents/agent-08-asymmetry.md",
        "edge_types": {"reads", "writes", "guards", "state_transition", "calls"},
        "node_types": {"function", "state_var", "guard"},
        "keywords": ["deposit", "withdraw", "mint", "burn", "buy", "sell", "open", "close", "lock", "unlock", "admin", "user", "pause", "unpause"],
    },
    {
        "id": 9,
        "slug": "boundary",
        "title": "Boundary",
        "reference": "subAgents/agent-09-boundary.md",
        "edge_types": {"external_call", "transfers_value", "guards", "reads", "writes"},
        "node_types": {"function", "guard", "external_symbol"},
        "keywords": ["payable", "address(0)", "zero", "sentinel", "bytes", "decode", "encode", "length", "deadline", "min", "max", "slippage", "fallback"],
    },
    {
        "id": 10,
        "slug": "numerical-gap",
        "title": "Numerical Gap",
        "reference": "subAgents/agent-10-numerical-gap.md",
        "edge_types": {"reads", "writes", "state_transition", "guards"},
        "node_types": {"function", "state_var", "guard"},
        "keywords": ["round", "decimal", "cap", "limit", "total", "balance", "share", "amount", "min", "max", "precision", "boundary"],
    },
    {
        "id": 11,
        "slug": "trust-gap",
        "title": "Trust Gap",
        "reference": "subAgents/agent-11-trust-gap.md",
        "edge_types": {"guards", "external_call", "transfers_value", "reads", "writes", "precondition_written_by"},
        "node_types": {"function", "guard", "state_var", "external_symbol"},
        "keywords": ["role", "admin", "owner", "token", "oracle", "price", "transfer", "reward", "user", "keeper", "trusted", "asymmetry"],
    },
    {
        "id": 12,
        "slug": "flow-gap",
        "title": "Flow Gap",
        "reference": "subAgents/agent-12-flow-gap.md",
        "edge_types": {"calls", "external_call", "writes", "state_transition", "guards", "precondition_written_by"},
        "node_types": {"function", "state_var", "guard", "external_symbol"},
        "keywords": ["execute", "callback", "router", "adapter", "helper", "settle", "claim", "finalize", "intent", "state", "flow"],
    },
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare Kai Research Jay-guided agent bundles.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Prepare Kai run artifacts")
    prepare.add_argument("project_root", nargs="?", default=".", type=Path)
    prepare.add_argument("--files", nargs="*", default=None, help="Explicit Solidity files to scan, relative to project root unless absolute")
    prepare.add_argument("--run-id", default=None, help="Deterministic run id, mostly for tests")
    prepare.add_argument("--out-root", default="MasterWu/Kai", help="Kai output root, relative to project root unless absolute")
    prepare.add_argument("--jay-out", default="MasterWu/Jay", help="Jay output root, relative to project root unless absolute")
    prepare.add_argument("--jay-skill-dir", default=None, type=Path, help="Override sibling jay-logic skill path")

    validate = subparsers.add_parser("validate-hypotheses", help="Validate one Kai hypotheses.json file")
    validate.add_argument("json_path", type=Path)

    args = parser.parse_args()
    if args.command == "prepare":
        return command_prepare(args)
    if args.command == "validate-hypotheses":
        return command_validate_hypotheses(args.json_path)
    return 1


def command_prepare(args: argparse.Namespace) -> int:
    project_root = args.project_root.resolve()
    if not project_root.is_dir():
        print(f"Project root not found: {project_root}", file=sys.stderr)
        return 2

    print(f"Kai Research: preparing {project_root}")
    scope_files = collect_scope(project_root, args.files)
    if not scope_files:
        print("No in-scope Solidity files found.", file=sys.stderr)
        return 2

    skill_dir = Path(__file__).resolve().parents[1]
    references = load_references(skill_dir / "references")

    jay_skill_dir = args.jay_skill_dir.resolve() if args.jay_skill_dir else skill_dir.parent / "jay-logic"
    jay_script = jay_skill_dir / "scripts" / "jay_logic.py"
    if not jay_script.is_file():
        print(f"Required sibling Jay skill not found: {jay_script}", file=sys.stderr)
        return 2

    if not run_jay(project_root, jay_script, args.jay_out, scope_files if args.files is not None else None):
        return 1

    jay_dir = path_under_project(project_root, args.jay_out)
    graph = json.loads((jay_dir / "jay-logic.json").read_text(encoding="utf-8"))

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_dir = path_under_project(project_root, args.out_root) / "runs" / run_id
    if run_dir.exists():
        print(f"Kai run directory already exists: {run_dir}", file=sys.stderr)
        return 2

    source_text = render_source(project_root, scope_files, run_id)
    scoped_rel_paths = [rel(project_root, path) for path in scope_files]

    (run_dir / "jay-slices").mkdir(parents=True, exist_ok=True)
    (run_dir / "agents").mkdir(parents=True, exist_ok=True)
    (run_dir / "scope.txt").write_text("\n".join(scoped_rel_paths) + "\n", encoding="utf-8")
    (run_dir / "source.md").write_text(source_text, encoding="utf-8")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "project_root": str(project_root),
        "jay_output": str(jay_dir),
        "scope_files": scoped_rel_paths,
        "agents": [],
    }

    for agent in AGENTS:
        agent_name = f"{agent['id']:02d}-{agent['slug']}"
        agent_dir = run_dir / "agents" / agent_name
        agent_dir.mkdir(parents=True, exist_ok=True)
        slice_text = render_jay_slice(graph, agent, scoped_rel_paths)
        slice_path = run_dir / "jay-slices" / f"agent-{agent_name}.md"
        slice_path.write_text(slice_text, encoding="utf-8")
        (agent_dir / "bundle.md").write_text(render_bundle(agent, run_id, project_root, agent_dir, references, slice_text, source_text), encoding="utf-8")
        (agent_dir / "report.md").write_text(render_pending_report(agent, run_id), encoding="utf-8")
        write_json(agent_dir / "hypotheses.json", empty_hypotheses(run_id, agent))
        manifest["agents"].append(
            {
                "agent_id": agent["id"],
                "agent_name": agent["slug"],
                "title": agent["title"],
                "agent_dir": str(agent_dir),
                "bundle_path": str(agent_dir / "bundle.md"),
                "report_path": str(agent_dir / "report.md"),
                "hypotheses_path": str(agent_dir / "hypotheses.json"),
                "jay_slice_path": str(slice_path),
                "spawn_prompt": f"Read only {agent_dir / 'bundle.md'} first. Write final output to {agent_dir / 'report.md'} and {agent_dir / 'hypotheses.json'}.",
            }
        )

    write_json(run_dir / "spawn-manifest.json", manifest)
    print(f"Kai Research run prepared at {run_dir}")
    return 0


def collect_scope(project_root: Path, explicit_files: list[str] | None) -> list[Path]:
    if explicit_files is not None:
        files = []
        for raw in explicit_files:
            path = Path(raw)
            if not path.is_absolute():
                path = project_root / path
            path = path.resolve()
            try:
                path.relative_to(project_root)
            except ValueError:
                raise SystemExit(f"Explicit file outside project root: {path}")
            if not path.is_file():
                raise SystemExit(f"Explicit file not found: {path}")
            if path.suffix != ".sol":
                raise SystemExit(f"Explicit file is not Solidity: {path}")
            files.append(path)
        return sorted(dict.fromkeys(files), key=lambda item: rel(project_root, item))

    files = []
    for path in project_root.rglob("*.sol"):
        parts = path.relative_to(project_root).parts
        if any(part in EXCLUDED_DIRS for part in parts[:-1]):
            continue
        if excluded_solidity_name(path.name):
            continue
        files.append(path)
    return sorted(files, key=lambda item: rel(project_root, item))


def excluded_solidity_name(name: str) -> bool:
    return name.endswith(".t.sol") or "Test" in name or "Mock" in name


def run_jay(project_root: Path, jay_script: Path, jay_out: str, scope_files: list[Path] | None) -> bool:
    build_cmd = [sys.executable, str(jay_script), "build", str(project_root), "--out", jay_out, "--lang", "solidity"]
    if scope_files is not None:
        build_cmd.extend(["--files", *[rel(project_root, path) for path in scope_files]])
    if not run_command(build_cmd, "Jay build"):
        return False
    validate_cmd = [sys.executable, str(jay_script), "validate", str(path_under_project(project_root, jay_out) / "jay-logic.json")]
    return run_command(validate_cmd, "Jay validate")


def run_command(cmd: list[str], label: str) -> bool:
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.returncode != 0:
        if proc.stderr:
            print(proc.stderr.rstrip(), file=sys.stderr)
        print(f"{label} failed with exit code {proc.returncode}", file=sys.stderr)
        return False
    return True


def path_under_project(project_root: Path, raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else project_root / path


def load_references(references_dir: Path) -> dict[str, str]:
    required = BASE_REFERENCES + [agent["reference"] for agent in AGENTS]
    out = {}
    for name in required:
        path = references_dir / name
        if not path.is_file():
            raise SystemExit(f"Missing Kai reference: {path}")
        out[name] = path.read_text(encoding="utf-8")
    return out


def render_source(project_root: Path, scope_files: list[Path], run_id: str) -> str:
    lines = [
        "# Kai Source Bundle",
        "",
        f"- Run: `{run_id}`",
        f"- Project root: `{project_root}`",
        f"- Files: `{len(scope_files)}`",
        "",
    ]
    for path in scope_files:
        relative = rel(project_root, path)
        lines.extend([f"## File: `{relative}`", "", "```solidity"])
        lines.append(path.read_text(errors="ignore"))
        lines.extend(["```", ""])
    return "\n".join(lines).rstrip() + "\n"


def render_jay_slice(graph: dict, agent: dict, scope_files: list[str]) -> str:
    scope_set = set(scope_files)
    node_by_id = {node["id"]: node for node in graph.get("nodes", [])}
    scoped_nodes = [node for node in graph.get("nodes", []) if node.get("file") in scope_set]
    scoped_edges = [edge for edge in graph.get("edges", []) if edge.get("file") in scope_set]
    relevant_nodes = [node for node in scoped_nodes if node_is_relevant(node, agent)]
    relevant_edges = [edge for edge in scoped_edges if edge_is_relevant(edge, agent, node_by_id)]
    relevant_node_ids = {node["id"] for node in relevant_nodes}
    relevant_edge_ids = {edge["id"] for edge in relevant_edges}
    for edge in relevant_edges:
        relevant_node_ids.add(edge.get("from"))
        relevant_node_ids.add(edge.get("to"))
    line_links = [
        item
        for item in graph.get("line_links", [])
        if item.get("file") in scope_set
        and (set(item.get("node_ids", [])) & relevant_node_ids or set(item.get("edge_ids", [])) & relevant_edge_ids)
    ]
    entries = [
        node
        for node in scoped_nodes
        if node.get("type") == "function" and (node.get("visibility") in {"public", "external", "entry"} or node.get("metadata", {}).get("entry_point"))
    ]

    lines = [
        f"# Jay Slice: Agent {agent['id']:02d} {agent['slug']}",
        "",
        f"- Agent focus: {agent['title']}",
        f"- Jay schema: `{graph.get('schema_version', 'unknown')}`",
        f"- Scope files: `{len(scope_files)}`",
        f"- Relevant nodes: `{len(relevant_nodes)}`",
        f"- Relevant edges: `{len(relevant_edges)}`",
        "",
        "## Entry Functions",
        "",
    ]
    lines.extend(render_node_rows(entries[:120]))
    lines.extend(["", "## Relevant Nodes", ""])
    lines.extend(render_node_rows(relevant_nodes[:240]))
    lines.extend(["", "## Relevant Edges", ""])
    lines.extend(render_edge_rows(relevant_edges[:320], node_by_id))
    lines.extend(["", "## Line Links", ""])
    lines.extend(render_line_link_rows(line_links[:320]))
    if len(relevant_nodes) > 240 or len(relevant_edges) > 320 or len(line_links) > 320:
        lines.extend(["", "Note: slice output was capped; use `MasterWu/Jay/jay-logic.json` only if the bundle evidence requires expansion."])
    return "\n".join(lines).rstrip() + "\n"


def node_is_relevant(node: dict, agent: dict) -> bool:
    text = " ".join(str(node.get(key, "")) for key in ("type", "name", "signature", "visibility")).lower()
    return node.get("type") in agent["node_types"] or any(keyword.lower() in text for keyword in agent["keywords"])


def edge_is_relevant(edge: dict, agent: dict, node_by_id: dict[str, dict]) -> bool:
    source = node_by_id.get(edge.get("from"), {})
    target = node_by_id.get(edge.get("to"), {})
    text = " ".join(
        [
            str(edge.get("type", "")),
            str(edge.get("label", "")),
            str(source.get("name", "")),
            str(source.get("signature", "")),
            str(target.get("name", "")),
            str(target.get("signature", "")),
        ]
    ).lower()
    return edge.get("type") in agent["edge_types"] or any(keyword.lower() in text for keyword in agent["keywords"])


def render_node_rows(nodes: list[dict]) -> list[str]:
    if not nodes:
        return ["No matching nodes."]
    lines = ["| id | type | name | location | confidence |", "| --- | --- | --- | --- | --- |"]
    for node in nodes:
        lines.append(
            f"| `{md(node.get('id'))}` | `{md(node.get('type'))}` | `{md(node.get('name'))}` | "
            f"`{md(node.get('file'))}:{node.get('start_line')}-{node.get('end_line')}` | `{md(node.get('confidence'))}` |"
        )
    return lines


def render_edge_rows(edges: list[dict], node_by_id: dict[str, dict]) -> list[str]:
    if not edges:
        return ["No matching edges."]
    lines = ["| id | type | from | to | location | label | confidence |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for edge in edges:
        source = node_by_id.get(edge.get("from"), {"name": edge.get("from")})
        target = node_by_id.get(edge.get("to"), {"name": edge.get("to")})
        lines.append(
            f"| `{md(edge.get('id'))}` | `{md(edge.get('type'))}` | `{md(source.get('name'))}` | `{md(target.get('name'))}` | "
            f"`{md(edge.get('file'))}:{edge.get('start_line')}-{edge.get('end_line')}` | {md(edge.get('label'))} | `{md(edge.get('confidence'))}` |"
        )
    return lines


def render_line_link_rows(items: list[dict]) -> list[str]:
    if not items:
        return ["No matching line links."]
    lines = ["| file | line | node ids | edge ids |", "| --- | --- | --- | --- |"]
    for item in items:
        lines.append(
            f"| `{md(item.get('file'))}` | `{item.get('line')}` | `{md(','.join(item.get('node_ids', [])))}` | "
            f"`{md(','.join(item.get('edge_ids', [])))}` |"
        )
    return lines


def render_bundle(agent: dict, run_id: str, project_root: Path, agent_dir: Path, references: dict[str, str], slice_text: str, source_text: str) -> str:
    parts = [
        f"# Kai Agent Bundle: {agent['id']:02d} {agent['slug']}",
        "",
        "## Assignment",
        "",
        f"You are Kai agent {agent['id']:02d}, `{agent['slug']}`. Search only for candidate vulnerability hypotheses in your specialty.",
        "",
        "Write exactly these files:",
        "",
        f"- `{agent_dir / 'report.md'}`",
        f"- `{agent_dir / 'hypotheses.json'}`",
        "",
        f"- Run id: `{run_id}`",
        f"- Project root: `{project_root}`",
        "",
        "## Shared Rules",
        "",
        references["shared-rules.md"],
        "",
        "## Judging",
        "",
        references["judging.md"],
        "",
        "## Report Formatting",
        "",
        references["report-formatting.md"],
        "",
        "## Senior Auditor SOP",
        "",
        references["senior-auditor-sop.md"],
        "",
        "## Specialist Prompt",
        "",
        references[agent["reference"]],
        "",
        "## Jay Graph Slice",
        "",
        slice_text,
        "",
        "## Full In-Scope Source",
        "",
        source_text,
    ]
    return "\n".join(part.rstrip() for part in parts).rstrip() + "\n"


def render_pending_report(agent: dict, run_id: str) -> str:
    return "\n".join(
        [
            f"# Kai Agent {agent['id']:02d}: {agent['title']}",
            "",
            f"- Run: `{run_id}`",
            f"- Status: `{PENDING_MARKER}`",
            "",
            "This file must be replaced by the assigned agent.",
            "",
        ]
    )


def empty_hypotheses(run_id: str, agent: dict) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "agent_id": agent["id"],
        "agent_name": agent["slug"],
        "hypotheses": [],
    }


def command_validate_hypotheses(json_path: Path) -> int:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    errors = validate_hypotheses(data)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("hypotheses.json is valid")
    return 0


def validate_hypotheses(data: dict) -> list[str]:
    errors = []
    for field in ("schema_version", "run_id", "agent_id", "agent_name", "hypotheses"):
        if field not in data:
            errors.append(f"missing top-level field: {field}")
    if errors:
        return errors
    if data["schema_version"] != SCHEMA_VERSION:
        errors.append(f"unsupported schema_version: {data['schema_version']}")
    if not isinstance(data["hypotheses"], list):
        errors.append("hypotheses must be a list")
        return errors
    required = {
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
    forbidden = {"severity", "verdict", "final_verdict", "confirmed"}
    for idx, item in enumerate(data["hypotheses"]):
        if not isinstance(item, dict):
            errors.append(f"hypotheses[{idx}] must be an object")
            continue
        missing = required - set(item)
        if missing:
            errors.append(f"hypotheses[{idx}] missing fields: {sorted(missing)}")
        present_forbidden = forbidden & set(item)
        if present_forbidden:
            errors.append(f"hypotheses[{idx}] forbidden fields: {sorted(present_forbidden)}")
        if item.get("confidence") not in CONFIDENCE_VALUES:
            errors.append(f"hypotheses[{idx}] invalid confidence: {item.get('confidence')}")
        if not isinstance(item.get("evidence"), list):
            errors.append(f"hypotheses[{idx}].evidence must be a list")
        else:
            for ev_idx, evidence in enumerate(item["evidence"]):
                if not isinstance(evidence, dict):
                    errors.append(f"hypotheses[{idx}].evidence[{ev_idx}] must be an object")
                    continue
                for field in ("file", "start_line", "end_line"):
                    if field not in evidence:
                        errors.append(f"hypotheses[{idx}].evidence[{ev_idx}] missing {field}")
        jay_refs = item.get("jay_refs")
        if not isinstance(jay_refs, dict) or not isinstance(jay_refs.get("node_ids"), list) or not isinstance(jay_refs.get("edge_ids"), list):
            errors.append(f"hypotheses[{idx}].jay_refs must contain node_ids and edge_ids lists")
        if not isinstance(item.get("next_validation_steps"), list):
            errors.append(f"hypotheses[{idx}].next_validation_steps must be a list")
    return errors


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(project_root: Path, path: Path) -> str:
    return path.relative_to(project_root).as_posix()


def md(raw: object) -> str:
    return str(raw).replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
