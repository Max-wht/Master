"""Standalone graph renderers using the Jay 1.0.0 artifact contract."""

import re

from collections import defaultdict

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
