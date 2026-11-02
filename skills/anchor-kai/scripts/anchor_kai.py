#!/usr/bin/env python3
"""Prepare twelve standalone Anchor research bundles from a reviewed Jay map."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
from hypotheses import SCHEMA_VERSION, validate_hypotheses

DEFAULT_OUT = "MasterWu/Anchor/Kai"
DEFAULT_JAY = "MasterWu/Anchor/Jay"
PENDING_MARKER = "PENDING_KAI_AGENT_OUTPUT"
AGENTS = [
    ("math-precision", "Math and Precision", ["checked", "saturating", "cast", "round", "decimal", "timestamp", "slot", "fee", "u64", "u128"]),
    ("identity-authority", "Identity and Authority", ["signer", "owner", "discriminator", "has_one", "authority", "admin", "upgrade"]),
    ("assets-economics", "Assets and Economics", ["token", "mint", "share", "reserve", "reward", "fee", "liquidat", "lamports"]),
    ("execution-trace", "Execution Trace", ["cpi", "reload", "invoke", "settle", "execute", "state_transition"]),
    ("invariants", "Coupled State Invariants", ["total", "supply", "debt", "reserve", "share", "balance", "writes"]),
    ("engineering-resources", "Engineering and Resources", ["panic", "unwrap", "realloc", "space", "len", "compute", "rent"]),
    ("protocol-mechanism", "Protocol Mechanism", ["deposit", "withdraw", "claim", "recover", "pause", "intent", "guarantee"]),
    ("operation-symmetry", "Operation Symmetry", ["deposit", "withdraw", "open", "close", "init", "migrate", "pause"]),
    ("external-inputs", "External Inputs", ["remaining_accounts", "unchecked", "oracle", "price", "sysvar", "duplicate", "constraint"]),
    ("pda-lifecycle", "PDA and Account Lifecycle", ["seeds", "bump", "init", "close", "realloc", "zero", "discriminator"]),
    ("cpi-trust", "CPI Trust Boundaries", ["invoke", "signer", "program", "cpi", "delegate", "authority"]),
    ("instruction-chains", "Cross-Instruction Attack Chains", ["calls", "state_transition", "nonce", "claim", "settle", "transfer", "flow"]),
]


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def under(root, raw):
    path = Path(raw)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def context_index(root, context_file):
    client = None
    if context_file:
        path = under(root, context_file)
        client = {"file": str(path), "text": path.read_text(), "evidence_kind": "client-stated; verify deployment claims"}
    excluded = {".git", ".anchor", "MasterWu", "node_modules", "vendor", "target", "out", "build", "artifacts", ".venv", ".venv-check", "__pycache__"}
    dirs_of_interest = {"docs", "doc", "test", "tests", "spec", "specs", "script", "scripts", "deploy", "deployments", "config", "configs", "migrations"}
    extensions = {".md", ".rst", ".txt", ".rs", ".ts", ".js", ".py", ".json", ".toml", ".yaml", ".yml", ".sh"}
    index = []
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in excluded and not d.startswith(".") and not (Path(base) / d).is_symlink())
        for name in sorted(files):
            path = Path(base) / name
            rel = path.relative_to(root)
            if path.is_symlink() or name.startswith("."):
                continue
            if name in {"Cargo.toml", "Cargo.lock", "Anchor.toml", "package.json"} or (path.suffix in extensions and (name.lower().startswith("readme") or dirs_of_interest.intersection(rel.parts[:-1]) or len(rel.parts) == 1)):
                index.append(rel.as_posix())
    return {"client_context": client, "supporting_files": sorted(index), "index_scope": "Project README, manifests/lockfiles, docs/tests/scripts/deploy/config. Index absence is not proof that tests or controls are missing."}


def prepare(args):
    root = args.project_root.resolve()
    if not root.is_dir():
        raise ValueError(f"Project not found: {root}")
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", run_id):
        raise ValueError("run-id must be a safe directory name")
    run = under(root, args.out_root) / "runs" / run_id
    if run.exists():
        raise ValueError(f"Run already exists: {run}")
    skill = Path(__file__).resolve().parents[1]
    jay_skill = args.jay_skill_dir.resolve() if args.jay_skill_dir else skill.parent / "anchor-jay"
    jay_script = jay_skill / "scripts" / "anchor_jay.py"
    if not jay_script.is_file():
        raise ValueError(f"Install the required sibling anchor-jay skill: {jay_script}")
    jay_dir = under(root, args.jay_out)
    graph_path, map_path = jay_dir / "jay-logic.json", jay_dir / "audit-map.json"
    if args.files or not graph_path.is_file():
        cmd = [sys.executable, str(jay_script), "build", str(root), "--out", str(jay_dir)]
        if args.files:
            cmd += ["--files", *args.files]
        subprocess.run(cmd, check=True)
    subprocess.run([sys.executable, str(jay_script), "validate", str(graph_path), "--audit-map", str(map_path), "--require-semantics"], check=True)
    graph = json.loads(graph_path.read_text())
    if Path(graph["project_root"]).resolve() != root:
        raise ValueError("Jay graph belongs to a different project root")
    business = json.loads(map_path.read_text())
    scope = sorted(graph["metadata"]["source_files"])
    context = context_index(root, args.context)
    context["anchor_metadata"] = graph["metadata"]
    context["business_map"] = business
    source = "# Complete Anchor Source\n\n" + "\n\n".join("## " + file + "\n\n```rust\n" + "\n".join(f"{i}: {line}" for i, line in enumerate((root / file).read_text().splitlines(), 1)) + "\n```" for file in scope)
    references = skill / "references"
    common = "\n\n".join((references / name).read_text() for name in ("shared-rules.md", "runtime-semantics.md", "report-formatting.md"))
    manifest = {"schema_version": SCHEMA_VERSION, "runtime": "anchor", "run_id": run_id, "project_root": str(root), "jay_output": str(jay_dir), "scope_files": scope, "audit_context": context, "agents": []}
    # Snapshots prevent subsequent Jay edits from changing an in-flight research run.
    write_json(run / "jay-logic.json", graph)
    write_json(run / "audit-map.json", business)
    write_json(run / "audit-context.json", context)
    (run / "source.md").write_text(source + "\n")
    (run / "scope.txt").write_text("\n".join(scope) + "\n")
    manifest["source_sha256"] = hashlib.sha256((source + "\n").encode()).hexdigest()
    for i, (slug, title, keywords) in enumerate(AGENTS, 1):
        agent_dir = run / "agents" / f"{i:02d}-{slug}"
        agent_dir.mkdir(parents=True)
        relevant = [n for n in graph["nodes"] if any(k in json.dumps(n, ensure_ascii=False).lower() for k in keywords) or n["metadata"].get("entry_point")]
        ids = {n["id"] for n in relevant}
        edges = [e for e in graph["edges"] if e["from"] in ids or e["to"] in ids]
        slice_path = run / "jay-slices" / f"{i:02d}-{slug}.json"
        write_json(slice_path, {"nodes": relevant, "edges": edges})
        specialist = (references / "specialists" / f"{i:02d}-{slug}.md").read_text()
        bundle = "\n\n".join([f"# Anchor Kai {i:02d}: {title}", f"Research only your specialty. Read this bundle completely, then relevant indexed material. Write report.md and hypotheses.json under {agent_dir}. Do not modify target code or create PoCs.",
                                 common, specialist, "## Jay Business Map\n```json\n" + json.dumps(business, indent=2) + "\n```", "## Specialist Graph Slice\n```json\n" + json.dumps({"nodes": relevant, "edges": edges}, indent=2) + "\n```",
                                 "## Audit Context and Supporting Materials\n```json\n" + json.dumps(context, indent=2, ensure_ascii=False) + "\n```", source])
        (agent_dir / "bundle.md").write_text(bundle + "\n")
        (agent_dir / "report.md").write_text(f"# {title}\n\n{PENDING_MARKER}\n")
        write_json(agent_dir / "hypotheses.json", {"schema_version": SCHEMA_VERSION, "run_id": run_id, "agent_id": i, "agent_name": slug, "hypotheses": []})
        manifest["agents"].append({"agent_id": i, "agent_name": slug, "title": title, "agent_dir": str(agent_dir), "bundle_path": str(agent_dir / "bundle.md"), "report_path": str(agent_dir / "report.md"), "hypotheses_path": str(agent_dir / "hypotheses.json"), "jay_slice_path": str(slice_path),
                                    "spawn_prompt": f"Read {agent_dir / 'bundle.md'} completely first. Read relevant indexed source/docs/tests as needed. Write the configured report.md and hypotheses.json; validate the hypothesis contract before finishing."})
    write_json(run / "spawn-manifest.json", manifest)
    print(f"Prepared 12 Anchor research tasks: {run}")
    return 0


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    p.add_argument("project_root", nargs="?", default=Path("."), type=Path)
    p.add_argument("--context", type=Path)
    p.add_argument("--files", nargs="+")
    p.add_argument("--run-id")
    p.add_argument("--out-root", default=DEFAULT_OUT)
    p.add_argument("--jay-out", default=DEFAULT_JAY)
    p.add_argument("--jay-skill-dir", type=Path)
    v = commands.add_parser("validate-hypotheses")
    v.add_argument("json_path", type=Path)
    args = cli.parse_args()
    try:
        if args.command == "prepare":
            return prepare(args)
        errors = validate_hypotheses(json.loads(args.json_path.read_text()))
        if errors:
            raise ValueError("\n".join(errors))
        print("Anchor hypotheses are valid")
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
