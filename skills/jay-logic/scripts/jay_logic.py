#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

from adapters import anchor, generic, move, solidity

SCHEMA_VERSION = "1.0.0"
NODE_TYPES = {"function", "statement", "state_var", "guard", "event", "external_symbol", "contract_or_module"}
EDGE_TYPES = {
    "calls",
    "reads",
    "writes",
    "guards",
    "emits",
    "external_call",
    "transfers_value",
    "state_transition",
    "precondition_written_by",
}
REQUIRED_NODE_FIELDS = {
    "id",
    "type",
    "language",
    "file",
    "name",
    "signature",
    "start_line",
    "end_line",
    "confidence",
    "source_adapter",
}
REQUIRED_EDGE_FIELDS = {
    "id",
    "type",
    "from",
    "to",
    "file",
    "start_line",
    "end_line",
    "label",
    "confidence",
    "source_adapter",
}
ADAPTERS = {"solidity": solidity, "move": move, "anchor": anchor, "generic": generic}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and validate Jay Logic function-level code maps.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Build jay-logic artifacts")
    build_parser.add_argument("project_root", type=Path)
    build_parser.add_argument("--out", default="MasterWu/Jay", help="Output directory, relative to project root unless absolute")
    build_parser.add_argument("--lang", default="auto", choices=["auto", "solidity", "move", "anchor", "generic"], help="Language adapter")
    build_parser.add_argument("--files", nargs="*", default=None, help="Optional repo-relative or absolute source files to include")

    validate_parser = subparsers.add_parser("validate", help="Validate a jay-logic.json file")
    validate_parser.add_argument("json_path", type=Path)

    args = parser.parse_args()
    if args.command == "build":
        return command_build(args.project_root, args.out, args.lang, args.files)
    if args.command == "validate":
        return command_validate(args.json_path)
    return 1


def command_build(project_root: Path, out: str, lang: str, files: list[str] | None = None) -> int:
    project_root = project_root.resolve()
    if not project_root.exists() or not project_root.is_dir():
        print(f"Project root not found: {project_root}", file=sys.stderr)
        return 2

    output_dir = Path(out)
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    include_files = resolve_include_files(project_root, files)
    selected = select_adapters(project_root, lang, include_files)
    if not selected:
        print("No supported source files found.", file=sys.stderr)
        return 2

    nodes: list[dict] = []
    edges: list[dict] = []
    languages: list[str] = []
    for adapter in selected:
        result = adapter.collect(project_root, include_files=include_files)
        languages.append(result["language"])
        nodes.extend(result["nodes"])
        edges.extend(result["edges"])

    nodes = dedupe_by_id(nodes)
    edges = dedupe_by_id(edges)
    edges.extend(build_precondition_edges(nodes, edges))
    edges = dedupe_by_id(edges)
    line_links = build_line_links(nodes, edges)
    graph = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "project_root": str(project_root),
        "languages": sorted(set(languages)),
        "nodes": nodes,
        "edges": edges,
        "line_links": line_links,
        "stats": {
            "nodes": len(nodes),
            "edges": len(edges),
            "functions": sum(1 for node in nodes if node["type"] == "function"),
            "state_vars": sum(1 for node in nodes if node["type"] == "state_var"),
            "guards": sum(1 for node in nodes if node["type"] == "guard"),
        },
    }

    errors = validate_graph(graph)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    write_json(output_dir / "jay-logic.json", graph)
    (output_dir / "functions.md").write_text(render_functions(graph), encoding="utf-8")
    (output_dir / "line-links.tsv").write_text(render_line_links(graph), encoding="utf-8")
    (output_dir / "call-graph.mmd").write_text(render_call_graph(graph), encoding="utf-8")
    (output_dir / "storage-flow.mmd").write_text(render_storage_flow(graph), encoding="utf-8")
    (output_dir / "entry-flows.md").write_text(render_entry_flows(graph), encoding="utf-8")
    print(f"Wrote Jay Logic artifacts to {output_dir}")
    return 0


def command_validate(json_path: Path) -> int:
    graph = json.loads(json_path.read_text(encoding="utf-8"))
    errors = validate_graph(graph)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("jay-logic.json is valid")
    return 0


def resolve_include_files(project_root: Path, files: list[str] | None) -> list[Path] | None:
    if files is None:
        return None
    resolved = []
    for raw in files:
        path = Path(raw)
        if not path.is_absolute():
            path = project_root / path
        path = path.resolve()
        try:
            path.relative_to(project_root)
        except ValueError:
            raise SystemExit(f"Included file is outside project root: {path}")
        if not path.exists() or not path.is_file():
            raise SystemExit(f"Included file not found: {path}")
        resolved.append(path)
    return resolved


def select_adapters(project_root: Path, lang: str, include_files: list[Path] | None = None):
    if lang != "auto":
        adapter = ADAPTERS[lang]
        return [adapter] if adapter.detect(project_root, include_files=include_files) else []
    selected = []
    for name in ("solidity", "move", "anchor"):
        adapter = ADAPTERS[name]
        if adapter.detect(project_root, include_files=include_files):
            selected.append(adapter)
    if not selected and generic.detect(project_root, include_files=include_files):
        selected.append(generic)
    return selected


def dedupe_by_id(items: list[dict]) -> list[dict]:
    out = {}
    for item in items:
        out[item["id"]] = item
    return list(out.values())


def edge_id(edge_type: str, source: str, target: str, file: str, line: int, label: str) -> str:
    raw = ":".join(str(part).replace(":", "_").replace(" ", "_") for part in (edge_type, source, target, file, line, label))
    return f"edge:{raw}"


def build_precondition_edges(nodes: list[dict], edges: list[dict]) -> list[dict]:
    node_by_id = {node["id"]: node for node in nodes}
    writes_by_state: dict[str, list[dict]] = defaultdict(list)
    guard_state_pairs: list[tuple[dict, dict]] = []

    for edge in edges:
        if edge["type"] == "writes":
            writes_by_state[edge["to"]].append(edge)
        elif edge["type"] == "guards":
            source = node_by_id.get(edge["from"])
            target = node_by_id.get(edge["to"])
            if source and target and source["type"] == "guard" and target["type"] == "state_var":
                guard_state_pairs.append((source, target))

    result = []
    for guard, state in guard_state_pairs:
        guarded_function_id = guard.get("parent_id")
        if not guarded_function_id:
            continue
        for writer in writes_by_state.get(state["id"], []):
            if writer["from"] == guarded_function_id:
                continue
            writer_node = node_by_id.get(writer["from"])
            if not writer_node:
                continue
            result.append(
                {
                    "id": edge_id("precondition_written_by", writer["from"], guarded_function_id, writer["file"], writer["start_line"], state["name"]),
                    "type": "precondition_written_by",
                    "from": writer["from"],
                    "to": guarded_function_id,
                    "file": writer["file"],
                    "start_line": writer["start_line"],
                    "end_line": writer["end_line"],
                    "label": f"writes {state['name']} used by guard at {guard['file']}:{guard['start_line']}",
                    "confidence": min_confidence(writer["confidence"], guard["confidence"]),
                    "source_adapter": writer["source_adapter"],
                }
            )
    return result


def min_confidence(left: str, right: str) -> str:
    order = {"low": 0, "medium": 1, "high": 2}
    reverse = {0: "low", 1: "medium", 2: "high"}
    return reverse[min(order.get(left, 0), order.get(right, 0))]


def build_line_links(nodes: list[dict], edges: list[dict]) -> list[dict]:
    links: dict[tuple[str, int], dict[str, set[str]]] = defaultdict(lambda: {"node_ids": set(), "edge_ids": set()})
    for node in nodes:
        for line in range(int(node["start_line"]), int(node["end_line"]) + 1):
            links[(node["file"], line)]["node_ids"].add(node["id"])
    for edge in edges:
        for line in range(int(edge["start_line"]), int(edge["end_line"]) + 1):
            links[(edge["file"], line)]["edge_ids"].add(edge["id"])
    return [
        {"file": file, "line": line, "node_ids": sorted(value["node_ids"]), "edge_ids": sorted(value["edge_ids"])}
        for (file, line), value in sorted(links.items())
    ]


def validate_graph(graph: dict) -> list[str]:
    errors: list[str] = []
    for field in ("schema_version", "generated_at", "project_root", "languages", "nodes", "edges", "line_links", "stats"):
        if field not in graph:
            errors.append(f"missing top-level field: {field}")
    if errors:
        return errors

    node_ids = set()
    for idx, node in enumerate(graph["nodes"]):
        missing = REQUIRED_NODE_FIELDS - set(node)
        if missing:
            errors.append(f"node[{idx}] missing fields: {sorted(missing)}")
        if node.get("type") not in NODE_TYPES:
            errors.append(f"node[{idx}] invalid type: {node.get('type')}")
        if node.get("id") in node_ids:
            errors.append(f"duplicate node id: {node.get('id')}")
        node_ids.add(node.get("id"))
        if int(node.get("start_line", 0)) <= 0 or int(node.get("end_line", 0)) < int(node.get("start_line", 0)):
            errors.append(f"node[{idx}] invalid line range: {node.get('id')}")

    edge_ids = set()
    for idx, edge in enumerate(graph["edges"]):
        missing = REQUIRED_EDGE_FIELDS - set(edge)
        if missing:
            errors.append(f"edge[{idx}] missing fields: {sorted(missing)}")
        if edge.get("type") not in EDGE_TYPES:
            errors.append(f"edge[{idx}] invalid type: {edge.get('type')}")
        if edge.get("from") not in node_ids:
            errors.append(f"edge[{idx}] unknown from node: {edge.get('from')}")
        if edge.get("to") not in node_ids:
            errors.append(f"edge[{idx}] unknown to node: {edge.get('to')}")
        if edge.get("id") in edge_ids:
            errors.append(f"duplicate edge id: {edge.get('id')}")
        edge_ids.add(edge.get("id"))
    return errors


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_functions(graph: dict) -> str:
    nodes = graph["nodes"]
    edges = graph["edges"]
    node_by_id = {node["id"]: node for node in nodes}
    functions = [node for node in nodes if node["type"] == "function"]
    edges_from: dict[str, list[dict]] = defaultdict(list)
    for edge in edges:
        edges_from[edge["from"]].append(edge)

    lines = [
        "# Jay Logic Function Map",
        "",
        f"- Schema: `{graph['schema_version']}`",
        f"- Languages: `{', '.join(graph['languages'])}`",
        f"- Functions: `{graph['stats']['functions']}`",
        f"- Edges: `{graph['stats']['edges']}`",
        "",
    ]
    for fn in sorted(functions, key=lambda item: (item["file"], item["start_line"])):
        lines.extend(
            [
                f"## {fn['name']}",
                "",
                f"- Location: `{fn['file']}:{fn['start_line']}-{fn['end_line']}`",
                f"- Signature: `{fn['signature']}`",
                f"- Visibility: `{fn.get('visibility', 'unknown')}`",
                f"- Confidence: `{fn['confidence']}`",
            ]
        )
        for title, edge_types in (
            ("Calls", {"calls"}),
            ("Reads", {"reads"}),
            ("Writes", {"writes", "state_transition"}),
            ("Guards", {"guards"}),
            ("External interactions", {"external_call", "transfers_value"}),
            ("Events", {"emits"}),
        ):
            matches = [edge for edge in edges_from.get(fn["id"], []) if edge["type"] in edge_types]
            if not matches:
                continue
            lines.append(f"- {title}:")
            for edge in matches:
                target = node_by_id.get(edge["to"], {"name": edge["to"]})
                lines.append(f"  - `{target['name']}` via `{edge['type']}` at `{edge['file']}:{edge['start_line']}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_line_links(graph: dict) -> str:
    lines = ["file\tline\tnode_ids\tedge_ids"]
    for item in graph["line_links"]:
        lines.append(
            "\t".join(
                [
                    item["file"],
                    str(item["line"]),
                    ",".join(item["node_ids"]),
                    ",".join(item["edge_ids"]),
                ]
            )
        )
    return "\n".join(lines) + "\n"


def render_call_graph(graph: dict) -> str:
    node_by_id = {node["id"]: node for node in graph["nodes"]}
    lines = ["flowchart LR"]
    function_nodes = [node for node in graph["nodes"] if node["type"] == "function"]
    for node in function_nodes:
        lines.append(f"  {mermaid_id(node['id'])}[\"{escape_label(node['name'])}\"]")
    for edge in graph["edges"]:
        if edge["type"] not in {"calls", "external_call"}:
            continue
        source = node_by_id.get(edge["from"])
        target = node_by_id.get(edge["to"])
        if not source or not target:
            continue
        if target["type"] == "external_symbol":
            lines.append(f"  {mermaid_id(target['id'])}[\"{escape_label(target['name'])}\"]")
        arrow = "-->" if edge["type"] == "calls" else "-. external .->"
        lines.append(f"  {mermaid_id(source['id'])} {arrow} {mermaid_id(target['id'])}")
    return "\n".join(lines) + "\n"


def render_storage_flow(graph: dict) -> str:
    node_by_id = {node["id"]: node for node in graph["nodes"]}
    lines = ["flowchart LR"]
    for edge in graph["edges"]:
        if edge["type"] not in {"reads", "writes", "state_transition"}:
            continue
        source = node_by_id.get(edge["from"])
        target = node_by_id.get(edge["to"])
        if not source or not target:
            continue
        lines.append(f"  {mermaid_id(source['id'])}[\"{escape_label(source['name'])}\"]")
        lines.append(f"  {mermaid_id(target['id'])}[\"{escape_label(target['name'])}\"]")
        if edge["type"] == "reads":
            lines.append(f"  {mermaid_id(target['id'])} -. reads .-> {mermaid_id(source['id'])}")
        elif edge["type"] == "writes":
            lines.append(f"  {mermaid_id(source['id'])} -- writes --> {mermaid_id(target['id'])}")
        else:
            lines.append(f"  {mermaid_id(source['id'])} -- transition --> {mermaid_id(target['id'])}")
    return "\n".join(dedupe_lines(lines)) + "\n"


def render_entry_flows(graph: dict) -> str:
    nodes = graph["nodes"]
    edges = graph["edges"]
    node_by_id = {node["id"]: node for node in nodes}
    edges_from: dict[str, list[dict]] = defaultdict(list)
    for edge in edges:
        edges_from[edge["from"]].append(edge)
    entries = [
        node
        for node in nodes
        if node["type"] == "function"
        and (node.get("metadata", {}).get("entry_point") or node.get("visibility") in {"public", "external", "entry"})
    ]
    lines = ["# Jay Logic Entry Flows", ""]
    if not entries:
        lines.append("No entry functions detected.")
        return "\n".join(lines) + "\n"
    for fn in sorted(entries, key=lambda item: (item["file"], item["start_line"])):
        lines.append(f"## {fn['name']} (`{fn['file']}:{fn['start_line']}`)")
        relevant = [edge for edge in edges_from.get(fn["id"], []) if edge["type"] in {"calls", "writes", "guards", "external_call", "transfers_value", "state_transition"}]
        if not relevant:
            lines.append("- No direct calls, guards, writes, or external interactions detected.")
        else:
            for edge in relevant:
                target = node_by_id.get(edge["to"], {"name": edge["to"]})
                lines.append(f"- `{fn['name']}` --{edge['type']}--> `{target['name']}` at `{edge['file']}:{edge['start_line']}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def mermaid_id(raw: str) -> str:
    return "n_" + re.sub(r"[^A-Za-z0-9_]", "_", raw)


def escape_label(raw: str) -> str:
    return raw.replace('"', "'")


def dedupe_lines(lines: list[str]) -> list[str]:
    seen = set()
    out = []
    for line in lines:
        if line not in seen:
            out.append(line)
            seen.add(line)
    return out


if __name__ == "__main__":
    raise SystemExit(main())
