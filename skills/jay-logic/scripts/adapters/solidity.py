from __future__ import annotations

import re
from pathlib import Path

LANGUAGE = "solidity"
EXCLUDED_DIRS = {
    ".git",
    "Lloyd",
    "MasterWu",
    "artifacts",
    "build",
    "cache",
    "interfaces",
    "jay-logic",
    "lib",
    "mock",
    "mocks",
    "node_modules",
    "out",
    "test",
    "tests",
}

KEYWORD_CALLS = {
    "assert",
    "delete",
    "emit",
    "for",
    "if",
    "mapping",
    "modifier",
    "new",
    "require",
    "return",
    "revert",
    "while",
}

TRANSFER_METHODS = {"call", "delegatecall", "send", "transfer", "transferFrom", "safeTransfer", "safeTransferFrom"}


def detect(project_root: Path, include_files: list[Path] | None = None) -> bool:
    return any(_iter_files(project_root, include_files=include_files))


def collect(project_root: Path, include_files: list[Path] | None = None) -> dict:
    files = list(_iter_files(project_root, include_files=include_files))
    nodes: list[dict] = []
    edges: list[dict] = []
    functions: list[dict] = []
    state_vars: dict[str, dict] = {}
    events: dict[str, dict] = {}
    contracts: list[dict] = []

    for path in files:
        parsed = _parse_file(project_root, path)
        nodes.extend(parsed["nodes"])
        functions.extend(parsed["functions"])
        contracts.extend(parsed["contracts"])
        state_vars.update(parsed["state_vars"])
        events.update(parsed["events"])

    function_by_name: dict[str, list[dict]] = {}
    for fn in functions:
        function_by_name.setdefault(fn["name"], []).append(fn)

    for path in files:
        parsed_edges = _extract_edges(project_root, path, functions, function_by_name, state_vars, events)
        nodes.extend(parsed_edges["nodes"])
        edges.extend(parsed_edges["edges"])

    return {"language": LANGUAGE, "nodes": nodes, "edges": edges}


def _iter_files(project_root: Path, include_files: list[Path] | None = None):
    if include_files is not None:
        for path in include_files:
            if path.suffix == ".sol":
                yield path
        return
    for path in project_root.rglob("*.sol"):
        if any(part in EXCLUDED_DIRS for part in path.relative_to(project_root).parts[:-1]):
            continue
        if path.name.endswith(".t.sol") or "Mock" in path.name or "Test" in path.name:
            continue
        yield path


def _rel(project_root: Path, path: Path) -> str:
    return path.relative_to(project_root).as_posix()


def _stable_id(kind: str, *parts: object) -> str:
    raw = ":".join(str(p).replace(":", "_").replace(" ", "_") for p in parts)
    return f"{kind}:{raw}"


def _node(node_type: str, language: str, file: str, name: str, signature: str, start: int, end: int, confidence: str, adapter: str, **extra) -> dict:
    item = {
        "id": extra.pop("id"),
        "type": node_type,
        "language": language,
        "file": file,
        "name": name,
        "signature": signature,
        "start_line": start,
        "end_line": end,
        "confidence": confidence,
        "source_adapter": adapter,
    }
    item.update(extra)
    return item


def _edge(edge_type: str, source: str, target: str, file: str, line: int, label: str, confidence: str = "medium") -> dict:
    edge_id = _stable_id("edge", edge_type, source, target, file, line, label)
    return {
        "id": edge_id,
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


def _strip_comments(line: str, in_block: bool) -> tuple[str, bool]:
    text = line
    if in_block:
        if "*/" not in text:
            return "", True
        text = text.split("*/", 1)[1]
        in_block = False
    while "/*" in text:
        before, after = text.split("/*", 1)
        if "*/" in after:
            after = after.split("*/", 1)[1]
            text = before + after
        else:
            text = before
            in_block = True
            break
    if "//" in text:
        text = text.split("//", 1)[0]
    return text, in_block


def _parse_file(project_root: Path, path: Path) -> dict:
    rel = _rel(project_root, path)
    lines = path.read_text(errors="ignore").splitlines()
    nodes: list[dict] = []
    functions: list[dict] = []
    contracts: list[dict] = []
    state_vars: dict[str, dict] = {}
    events: dict[str, dict] = {}
    brace_depth = 0
    current_contract: dict | None = None
    pending_contract: dict | None = None
    in_block_comment = False
    in_function_until = 0

    for idx, raw in enumerate(lines, start=1):
        line, in_block_comment = _strip_comments(raw, in_block_comment)
        stripped = line.strip()
        contract_match = re.search(r"\b(?:abstract\s+)?(contract|library|interface)\s+([A-Za-z_][A-Za-z0-9_]*)", stripped)
        if contract_match:
            name = contract_match.group(2)
            contract_id = _stable_id("contract", rel, name, idx)
            current_contract = {
                "id": contract_id,
                "name": name,
                "kind": contract_match.group(1),
                "start": idx,
                "depth": brace_depth + line.count("{") - line.count("}"),
            }
            pending_contract = current_contract
            node = _node(
                "contract_or_module",
                LANGUAGE,
                rel,
                name,
                stripped or name,
                idx,
                idx,
                "medium",
                LANGUAGE,
                id=contract_id,
                metadata={"kind": contract_match.group(1)},
            )
            nodes.append(node)
            contracts.append(node)

        if current_contract and idx > in_function_until:
            event_match = re.search(r"\bevent\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", stripped)
            if event_match:
                name = event_match.group(1)
                event_id = _stable_id("event", rel, current_contract["name"], name, idx)
                event_node = _node(
                    "event",
                    LANGUAGE,
                    rel,
                    name,
                    stripped,
                    idx,
                    idx,
                    "medium",
                    LANGUAGE,
                    id=event_id,
                    parent_id=current_contract["id"],
                )
                nodes.append(event_node)
                events[name] = event_node

            state_name = _extract_state_var_name(stripped)
            top_level_in_contract = brace_depth <= 1 and current_contract is not None
            if state_name and top_level_in_contract:
                state_id = _stable_id("state", rel, current_contract["name"], state_name)
                state_node = _node(
                    "state_var",
                    LANGUAGE,
                    rel,
                    state_name,
                    stripped,
                    idx,
                    idx,
                    "medium",
                    LANGUAGE,
                    id=state_id,
                    parent_id=current_contract["id"],
                )
                nodes.append(state_node)
                state_vars[state_name] = state_node

        function_match = re.search(r"\b(function|constructor)\s*([A-Za-z_][A-Za-z0-9_]*)?\s*\(", stripped)
        if function_match:
            if current_contract and current_contract.get("kind") == "interface":
                brace_depth += line.count("{") - line.count("}")
                continue
            fn_name = function_match.group(2) or "constructor"
            signature_lines = [stripped]
            end_line, signature = _scan_function_signature(lines, idx, signature_lines)
            body_end = _find_block_end(lines, idx)
            if body_end < idx:
                body_end = end_line
            visibility = _visibility(signature)
            fn_id = _stable_id("function", rel, current_contract["name"] if current_contract else "file", fn_name, idx)
            fn_node = _node(
                "function",
                LANGUAGE,
                rel,
                fn_name,
                signature.strip(),
                idx,
                body_end,
                "medium",
                LANGUAGE,
                id=fn_id,
                parent_id=current_contract["id"] if current_contract else None,
                visibility=visibility,
                metadata={
                    "contract": current_contract["name"] if current_contract else None,
                    "entry_point": visibility in {"external", "public"} and " view " not in f" {signature} " and " pure " not in f" {signature} ",
                },
            )
            nodes.append(fn_node)
            functions.append(fn_node)
            in_function_until = max(in_function_until, body_end)

        brace_depth += line.count("{") - line.count("}")
        if pending_contract and brace_depth <= 0:
            pending_contract = None
            current_contract = None

    return {"nodes": nodes, "functions": functions, "contracts": contracts, "state_vars": state_vars, "events": events}


def _extract_state_var_name(stripped: str) -> str | None:
    if not stripped or not stripped.endswith(";"):
        return None
    if any(stripped.startswith(prefix) for prefix in ("using ", "import ", "pragma ", "event ", "error ", "modifier ", "function ", "constructor ")):
        return None
    if "(" in stripped and not stripped.startswith("mapping"):
        return None
    statement = stripped[:-1].strip()
    if statement.startswith("mapping"):
        match = re.search(
            r"\)\s+(?:(?:public|private|internal|external|constant|immutable|override)\s+)*([A-Za-z_][A-Za-z0-9_]*)\s*$",
            statement,
        )
        return match.group(1) if match else None
    left = re.split(r"\s=\s", statement, maxsplit=1)[0].strip()
    if not left:
        return None
    match = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\s*(?:\[[^\]]*\]\s*)*$", left)
    if not match:
        return None
    name = match.group(1)
    if name in {"public", "private", "internal", "external", "constant", "immutable", "override"}:
        return None
    return name


def _scan_function_signature(lines: list[str], start: int, signature_lines: list[str]) -> tuple[int, str]:
    idx = start
    paren = signature_lines[0].count("(") - signature_lines[0].count(")")
    while idx < len(lines) and "{" not in signature_lines[-1] and ";" not in signature_lines[-1]:
        if paren <= 0 and (" external" in f" {signature_lines[-1]}" or " public" in f" {signature_lines[-1]}" or " internal" in f" {signature_lines[-1]}" or " private" in f" {signature_lines[-1]}"):
            break
        idx += 1
        piece = lines[idx - 1].strip()
        signature_lines.append(piece)
        paren += piece.count("(") - piece.count(")")
    return idx, " ".join(signature_lines)


def _find_block_end(lines: list[str], start: int) -> int:
    depth = 0
    seen_open = False
    in_block_comment = False
    for idx in range(start, len(lines) + 1):
        line, in_block_comment = _strip_comments(lines[idx - 1], in_block_comment)
        if "{" in line:
            seen_open = True
        depth += line.count("{") - line.count("}")
        if seen_open and depth <= 0:
            return idx
        if ";" in line and not seen_open:
            return idx
    return len(lines)


def _visibility(signature: str) -> str:
    for visibility in ("external", "public", "internal", "private"):
        if re.search(rf"\b{visibility}\b", signature):
            return visibility
    return "default"


def _extract_edges(project_root: Path, path: Path, functions: list[dict], function_by_name: dict[str, list[dict]], state_vars: dict[str, dict], events: dict[str, dict]) -> dict:
    rel = _rel(project_root, path)
    lines = path.read_text(errors="ignore").splitlines()
    new_nodes: list[dict] = []
    edges: list[dict] = []
    external_nodes: dict[str, dict] = {}

    for fn in [item for item in functions if item["file"] == rel]:
        body = lines[fn["start_line"] - 1 : fn["end_line"]]
        for offset, raw in enumerate(body, start=fn["start_line"]):
            code = raw.split("//", 1)[0].strip()
            if not code:
                continue

            guard_node = None
            if _is_guard_line(code):
                guard_id = _stable_id("guard", rel, fn["name"], offset)
                guard_node = _node(
                    "guard",
                    LANGUAGE,
                    rel,
                    f"{fn['name']} guard",
                    code,
                    offset,
                    offset,
                    "medium",
                    LANGUAGE,
                    id=guard_id,
                    parent_id=fn["id"],
                )
                new_nodes.append(guard_node)
                edges.append(_edge("guards", fn["id"], guard_id, rel, offset, code))

            for state_name, state_node in state_vars.items():
                if not re.search(rf"\b{re.escape(state_name)}\b", code):
                    continue
                if _is_state_write(code, state_name):
                    edges.append(_edge("writes", fn["id"], state_node["id"], rel, offset, code))
                elif guard_node:
                    edges.append(_edge("guards", guard_node["id"], state_node["id"], rel, offset, state_name, "medium"))
                else:
                    edges.append(_edge("reads", fn["id"], state_node["id"], rel, offset, code))

            transition = _state_transition(code, state_vars)
            if transition:
                state_name, label = transition
                edges.append(_edge("state_transition", fn["id"], state_vars[state_name]["id"], rel, offset, label))

            event_match = re.search(r"\bemit\s+([A-Za-z_][A-Za-z0-9_]*)\b", code)
            if event_match and event_match.group(1) in events:
                edges.append(_edge("emits", fn["id"], events[event_match.group(1)]["id"], rel, offset, code))

            for call_name in _call_names(code):
                base_name = call_name.split(".")[-1]
                if base_name in KEYWORD_CALLS:
                    continue
                if "." in call_name:
                    ext_node = external_nodes.get(call_name)
                    if not ext_node:
                        ext_id = _stable_id("external", rel, call_name)
                        ext_node = _node(
                            "external_symbol",
                            LANGUAGE,
                            rel,
                            call_name,
                            call_name,
                            offset,
                            offset,
                            "low",
                            LANGUAGE,
                            id=ext_id,
                            parent_id=fn["id"],
                        )
                        external_nodes[call_name] = ext_node
                        new_nodes.append(ext_node)
                    edges.append(_edge("external_call", fn["id"], ext_node["id"], rel, offset, code, "low"))
                    if base_name in TRANSFER_METHODS or "{value:" in code or ".value(" in code:
                        edges.append(_edge("transfers_value", fn["id"], ext_node["id"], rel, offset, code, "low"))
                else:
                    candidates = [target for target in function_by_name.get(base_name, []) if target["id"] != fn["id"]]
                    if candidates:
                        edges.append(_edge("calls", fn["id"], candidates[0]["id"], rel, offset, code, "medium"))

    return {"nodes": new_nodes, "edges": edges}


def _is_guard_line(code: str) -> bool:
    return bool(re.search(r"\b(require|assert)\s*\(", code) or re.search(r"\bif\s*\(.*\)\s*revert\b", code) or code.startswith("revert "))


def _is_state_write(code: str, state_name: str) -> bool:
    escaped = re.escape(state_name)
    return bool(
        re.search(rf"\b{escaped}\b\s*(?:\[[^\]]+\]\s*)?(?:=|\+=|-=|\*=|/=|%=)", code)
        or re.search(rf"(?:\+\+|--)\s*\b{escaped}\b|\b{escaped}\b\s*(?:\+\+|--)", code)
        or re.search(rf"\bdelete\s+{escaped}\b", code)
    )


def _state_transition(code: str, state_vars: dict[str, dict]) -> tuple[str, str] | None:
    for state_name in state_vars:
        if re.search(rf"\b{re.escape(state_name)}\b\s*(?:==|!=)\s*[^);]+", code) and re.search(rf"\b{re.escape(state_name)}\b\s*=", code):
            return state_name, code
    return None


def _call_names(code: str) -> list[str]:
    names = []
    for match in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)\s*\(", code):
        name = match.group(1)
        if name in KEYWORD_CALLS:
            continue
        names.append(name)
    return names
