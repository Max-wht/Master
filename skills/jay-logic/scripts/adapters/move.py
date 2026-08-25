from __future__ import annotations

import re
from pathlib import Path

LANGUAGE = "move"
EXCLUDED_DIRS = {".git", "Lloyd", "MasterWu", "build", "jay-logic", "tests", "test"}


def detect(project_root: Path, include_files: list[Path] | None = None) -> bool:
    return any(_iter_files(project_root, include_files=include_files))


def collect(project_root: Path, include_files: list[Path] | None = None) -> dict:
    files = list(_iter_files(project_root, include_files=include_files))
    runtime_profile = _runtime_profile(project_root, files)
    nodes: list[dict] = []
    edges: list[dict] = []
    functions: list[dict] = []
    resources: dict[str, dict] = {}

    for path in files:
        parsed = _parse_file(project_root, path, runtime_profile)
        nodes.extend(parsed["nodes"])
        functions.extend(parsed["functions"])
        resources.update(parsed["resources"])

    function_by_name: dict[str, list[dict]] = {}
    for fn in functions:
        function_by_name.setdefault(fn["name"], []).append(fn)

    for path in files:
        parsed_edges = _extract_edges(project_root, path, functions, function_by_name, resources, runtime_profile)
        nodes.extend(parsed_edges["nodes"])
        edges.extend(parsed_edges["edges"])

    return {"language": LANGUAGE, "nodes": nodes, "edges": edges}


def _iter_files(project_root: Path, include_files: list[Path] | None = None):
    if include_files is not None:
        for path in include_files:
            if path.suffix == ".move":
                yield path
        return
    for path in project_root.rglob("*.move"):
        if any(part in EXCLUDED_DIRS for part in path.relative_to(project_root).parts[:-1]):
            continue
        yield path


def _rel(project_root: Path, path: Path) -> str:
    return path.relative_to(project_root).as_posix()


def _stable_id(kind: str, *parts: object) -> str:
    raw = ":".join(str(p).replace(":", "_").replace(" ", "_") for p in parts)
    return f"{kind}:{raw}"


def _node(node_type: str, file: str, name: str, signature: str, start: int, end: int, confidence: str, **extra) -> dict:
    item = {
        "id": extra.pop("id"),
        "type": node_type,
        "language": LANGUAGE,
        "file": file,
        "name": name,
        "signature": signature,
        "start_line": start,
        "end_line": end,
        "confidence": confidence,
        "source_adapter": LANGUAGE,
    }
    item.update(extra)
    return item


def _edge(edge_type: str, source: str, target: str, file: str, line: int, label: str, confidence: str = "medium") -> dict:
    return {
        "id": _stable_id("edge", edge_type, source, target, file, line, label),
        "type": edge_type,
        "from": source,
        "to": target,
        "file": file,
        "start_line": line,
        "end_line": line,
        "label": label.strip(),
        "confidence": confidence,
        "source_adapter": LANGUAGE,
    }


def _runtime_profile(project_root: Path, files: list[Path]) -> str:
    manifest = project_root / "Move.toml"
    haystack = ""
    if manifest.is_file():
        haystack += manifest.read_text(errors="ignore").lower()
    for path in files[:80]:
        haystack += "\n" + path.read_text(errors="ignore").lower()
    if "sui::" in haystack or "sui-framework" in haystack or "sui-framework" in haystack:
        return "sui-move"
    if "aptos_framework" in haystack or "aptos::" in haystack:
        return "aptos-move"
    return "move"


def _parse_file(project_root: Path, path: Path, runtime_profile: str) -> dict:
    rel = _rel(project_root, path)
    lines = path.read_text(errors="ignore").splitlines()
    nodes: list[dict] = []
    functions: list[dict] = []
    resources: dict[str, dict] = {}
    current_module: dict | None = None

    for idx, raw in enumerate(lines, start=1):
        code = raw.split("//", 1)[0].strip()
        module_match = re.search(r"\bmodule\s+([A-Za-z0-9_]+::)?([A-Za-z_][A-Za-z0-9_]*)\s*\{", code)
        if module_match:
            name = module_match.group(2)
            module_id = _stable_id("module", rel, name, idx)
            current_module = _node(
                "contract_or_module",
                rel,
                name,
                code,
                idx,
                idx,
                "medium",
                id=module_id,
                metadata={"kind": "module", "runtime_profile": runtime_profile},
            )
            nodes.append(current_module)

        resource_match = re.search(r"\bstruct\s+([A-Za-z_][A-Za-z0-9_]*)\b[^{};]*(?:has\s+[^{};]*)?\{?", code)
        if resource_match and current_module:
            name = resource_match.group(1)
            res_id = _stable_id("resource", rel, current_module["name"], name)
            res_node = _node(
                "state_var",
                rel,
                name,
                code,
                idx,
                idx,
                "medium",
                id=res_id,
                parent_id=current_module["id"],
                metadata={
                    "kind": "resource",
                    "runtime_profile": runtime_profile,
                    "abilities": _abilities(code),
                    "capability_like": name.endswith("Cap") or name.endswith("Capability"),
                    "coin_like": name in {"Coin", "Balance", "TreasuryCap"} or "Coin<" in code,
                },
            )
            nodes.append(res_node)
            resources[name] = res_node

        fn_match = re.search(r"\b((?:public\s+)?(?:entry\s+)?fun|fun)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", code)
        if fn_match:
            name = fn_match.group(2)
            end = _find_block_end(lines, idx)
            signature = _scan_signature(lines, idx)
            visibility = "entry" if "entry fun" in signature else ("public" if "public" in signature else "internal")
            fn_id = _stable_id("function", rel, current_module["name"] if current_module else "module", name, idx)
            fn_node = _node(
                "function",
                rel,
                name,
                signature,
                idx,
                end,
                "medium",
                id=fn_id,
                parent_id=current_module["id"] if current_module else None,
                visibility=visibility,
                metadata={
                    "module": current_module["name"] if current_module else None,
                    "entry_point": "entry fun" in signature,
                    "runtime_profile": runtime_profile,
                    "signer_params": len(re.findall(r"&\s*signer\b", signature)),
                    "acquires": re.findall(r"\bacquires\s+([A-Za-z0-9_,\s]+)", signature),
                    "coin_types": re.findall(r"Coin\s*<\s*([^>]+)\s*>", signature),
                },
            )
            nodes.append(fn_node)
            functions.append(fn_node)

    return {"nodes": nodes, "functions": functions, "resources": resources}


def _find_block_end(lines: list[str], start: int) -> int:
    depth = 0
    seen_open = False
    for idx in range(start, len(lines) + 1):
        line = lines[idx - 1].split("//", 1)[0]
        if "{" in line:
            seen_open = True
        depth += line.count("{") - line.count("}")
        if seen_open and depth <= 0:
            return idx
    return len(lines)


def _scan_signature(lines: list[str], start: int) -> str:
    pieces = []
    paren = 0
    for idx in range(start, len(lines) + 1):
        piece = lines[idx - 1].strip()
        pieces.append(piece)
        paren += piece.count("(") - piece.count(")")
        if paren <= 0 and ("{" in piece or ";" in piece):
            break
    return " ".join(pieces)


def _abilities(code: str) -> list[str]:
    match = re.search(r"\bhas\s+([^{};]+)", code)
    if not match:
        return []
    return [item.strip() for item in re.split(r"[, ]+", match.group(1)) if item.strip()]


def _extract_edges(project_root: Path, path: Path, functions: list[dict], function_by_name: dict[str, list[dict]], resources: dict[str, dict], runtime_profile: str) -> dict:
    rel = _rel(project_root, path)
    lines = path.read_text(errors="ignore").splitlines()
    nodes: list[dict] = []
    edges: list[dict] = []
    external_nodes: dict[str, dict] = {}

    for fn in [item for item in functions if item["file"] == rel]:
        body = lines[fn["start_line"] - 1 : fn["end_line"]]
        for offset, raw in enumerate(body, start=fn["start_line"]):
            code = raw.split("//", 1)[0].strip()
            if not code:
                continue

            if "assert!" in code or re.search(r"\babort\b", code):
                guard_id = _stable_id("guard", rel, fn["name"], offset)
                guard = _node(
                    "guard",
                    rel,
                    f"{fn['name']} guard",
                    code,
                    offset,
                    offset,
                    "medium",
                    id=guard_id,
                    parent_id=fn["id"],
                    metadata={"runtime_profile": runtime_profile, "kind": "abort_or_assert"},
                )
                nodes.append(guard)
                edges.append(_edge("guards", fn["id"], guard_id, rel, offset, code))

            for res_name in re.findall(r"(?:acquires|borrow_global_mut|borrow_global|move_to|move_from|exists)<\s*([A-Za-z_][A-Za-z0-9_]*)\s*>", code):
                res_node = resources.get(res_name)
                if not res_node:
                    res_id = _stable_id("resource", rel, res_name)
                    res_node = _node(
                        "state_var",
                        rel,
                        res_name,
                        res_name,
                        offset,
                        offset,
                        "low",
                        id=res_id,
                        metadata={"kind": "resource", "runtime_profile": runtime_profile},
                    )
                    resources[res_name] = res_node
                    nodes.append(res_node)
                edge_type = "writes" if any(word in code for word in ("borrow_global_mut", "move_to", "move_from")) else "reads"
                edges.append(_edge(edge_type, fn["id"], res_node["id"], rel, offset, code))

            for call_name in _call_names(code):
                base = call_name.split("::")[-1]
                if base in {"assert", "assert!", "copy", "move", "return"}:
                    continue
                if "::" in call_name:
                    ext = external_nodes.get(call_name)
                    if not ext:
                        ext_id = _stable_id("external", rel, call_name)
                        ext = _node("external_symbol", rel, call_name, call_name, offset, offset, "low", id=ext_id, parent_id=fn["id"])
                        external_nodes[call_name] = ext
                        nodes.append(ext)
                    edges.append(_edge("external_call", fn["id"], ext["id"], rel, offset, code, "low"))
                else:
                    candidates = [target for target in function_by_name.get(base, []) if target["id"] != fn["id"]]
                    if candidates:
                        edges.append(_edge("calls", fn["id"], candidates[0]["id"], rel, offset, code, "medium"))

    return {"nodes": nodes, "edges": edges}


def _call_names(code: str) -> list[str]:
    return [match.group(1) for match in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*(?:::[A-Za-z_][A-Za-z0-9_]*)?)\s*(?:!|)\(", code)]
