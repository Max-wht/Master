from __future__ import annotations

import re
from pathlib import Path

LANGUAGE = "anchor"
EXCLUDED_DIRS = {".git", ".anchor", "Lloyd", "MasterWu", "node_modules", "target", "test", "tests"}


def detect(project_root: Path, include_files: list[Path] | None = None) -> bool:
    if include_files is not None:
        return any(path.suffix == ".rs" and _looks_anchor(path, project_root) for path in include_files)
    return (project_root / "Anchor.toml").is_file() and any(_iter_files(project_root))


def collect(project_root: Path, include_files: list[Path] | None = None) -> dict:
    files = list(_iter_files(project_root, include_files=include_files))
    nodes: list[dict] = []
    edges: list[dict] = []
    functions: list[dict] = []
    account_states: dict[str, dict] = {}
    contexts: dict[str, dict] = {}

    for path in files:
        parsed = _parse_file(project_root, path)
        nodes.extend(parsed["nodes"])
        functions.extend(parsed["functions"])
        account_states.update(parsed["account_states"])
        contexts.update(parsed["contexts"])

    for path in files:
        parsed_edges = _extract_edges(project_root, path, functions, account_states, contexts)
        nodes.extend(parsed_edges["nodes"])
        edges.extend(parsed_edges["edges"])

    return {"language": LANGUAGE, "nodes": nodes, "edges": edges}


def _iter_files(project_root: Path, include_files: list[Path] | None = None):
    if include_files is not None:
        for path in include_files:
            if path.suffix == ".rs" and _looks_anchor(path, project_root):
                yield path
        return
    for path in project_root.rglob("*.rs"):
        parts = path.relative_to(project_root).parts
        if any(part in EXCLUDED_DIRS for part in parts[:-1]):
            continue
        if _looks_anchor(path, project_root):
            yield path


def _looks_anchor(path: Path, project_root: Path) -> bool:
    if path.suffix != ".rs":
        return False
    text = path.read_text(errors="ignore")
    if any(marker in text for marker in ("#[program]", "#[derive(Accounts)]", "anchor_lang::prelude", "Context<")):
        return True
    return (project_root / "Anchor.toml").is_file() and "programs" in path.relative_to(project_root).parts


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


def _edge(edge_type: str, source: str, target: str, file: str, line: int, label: str, confidence: str = "medium", **extra) -> dict:
    item = {
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
    item.update(extra)
    return item


def _parse_file(project_root: Path, path: Path) -> dict:
    rel = _rel(project_root, path)
    lines = path.read_text(errors="ignore").splitlines()
    nodes: list[dict] = []
    functions: list[dict] = []
    account_states: dict[str, dict] = {}
    contexts: dict[str, dict] = {}
    attrs: list[tuple[int, str]] = []
    program_range: tuple[int, int, str] | None = None

    for idx, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if stripped.startswith("#["):
            attrs.append((idx, stripped))
            continue

        if any("#[program]" in attr for _line, attr in attrs):
            mod_match = re.search(r"\bpub\s+mod\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{", stripped)
            if mod_match:
                name = mod_match.group(1)
                end = _find_block_end(lines, idx)
                program_id = _stable_id("program", rel, name, idx)
                nodes.append(
                    _node(
                        "contract_or_module",
                        rel,
                        name,
                        stripped,
                        idx,
                        end,
                        "medium",
                        id=program_id,
                        metadata={"kind": "program", "runtime_profile": "anchor"},
                    )
                )
                program_range = (idx, end, program_id)
            attrs = []
            continue

        if any("#[account]" in attr for _line, attr in attrs):
            struct_match = re.search(r"\bpub\s+struct\s+([A-Za-z_][A-Za-z0-9_]*)\b", stripped)
            if struct_match:
                name = struct_match.group(1)
                end = _find_block_end(lines, idx)
                node_id = _stable_id("account", rel, name, idx)
                node = _node(
                    "state_var",
                    rel,
                    name,
                    stripped,
                    idx,
                    end,
                    "medium",
                    id=node_id,
                    metadata={"kind": "account_state", "runtime_profile": "anchor"},
                )
                nodes.append(node)
                account_states[name] = node
            attrs = []
            continue

        if any("derive(Accounts)" in attr for _line, attr in attrs):
            context_match = re.search(r"\bpub\s+struct\s+([A-Za-z_][A-Za-z0-9_]*)", stripped)
            if context_match:
                context = _parse_accounts_context(rel, lines, idx, context_match.group(1))
                nodes.append(context["node"])
                nodes.extend(context["fields"])
                nodes.extend(context["guards"])
                contexts[context["name"]] = context
            attrs = []
            continue

        attrs = []

    if program_range:
        start, end, program_id = program_range
        for idx in range(start + 1, end + 1):
            line = lines[idx - 1].split("//", 1)[0]
            fn_match = re.search(r"\bpub\s+fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", line)
            if not fn_match:
                continue
            name = fn_match.group(1)
            signature = _scan_signature(lines, idx)
            body_end = _find_block_end(lines, idx)
            context_name = _context_name(signature)
            fn_id = _stable_id("function", rel, name, idx)
            fn_node = _node(
                "function",
                rel,
                name,
                signature,
                idx,
                body_end,
                "medium",
                id=fn_id,
                parent_id=program_id,
                visibility="public",
                metadata={"entry_point": True, "runtime_profile": "anchor", "context": context_name},
            )
            nodes.append(fn_node)
            functions.append(fn_node)

    return {"nodes": nodes, "functions": functions, "account_states": account_states, "contexts": contexts}


def _parse_accounts_context(rel: str, lines: list[str], start: int, name: str) -> dict:
    end = _find_block_end(lines, start)
    context_id = _stable_id("context", rel, name, start)
    context_node = _node(
        "contract_or_module",
        rel,
        name,
        lines[start - 1].strip(),
        start,
        end,
        "medium",
        id=context_id,
        metadata={"kind": "accounts_context", "runtime_profile": "anchor"},
    )
    fields: list[dict] = []
    guards: list[dict] = []
    pending_attrs: list[tuple[int, str]] = []

    for idx in range(start + 1, end):
        stripped = lines[idx - 1].strip()
        if stripped.startswith("#["):
            pending_attrs.append((idx, stripped))
            continue
        field_match = re.search(r"\bpub\s+([A-Za-z_][A-Za-z0-9_]*):\s*(.+?)(?:,\s*)?$", stripped)
        if not field_match:
            pending_attrs = []
            continue
        field_name = field_match.group(1)
        field_type = field_match.group(2).strip()
        constraints = " ".join(attr for _line, attr in pending_attrs)
        field_id = _stable_id("account_field", rel, name, field_name, idx)
        field_node = _node(
            "state_var",
            rel,
            field_name,
            stripped,
            idx,
            idx,
            "medium",
            id=field_id,
            parent_id=context_id,
            metadata={
                "kind": "account_field",
                "context": name,
                "account_type": field_type,
                "constraints": constraints,
                "mutable": "mut" in constraints,
                "signer": "Signer<" in field_type,
                "pda": "seeds" in constraints,
                "runtime_profile": "anchor",
            },
        )
        fields.append(field_node)
        for attr_line, constraint in pending_attrs:
            if any(token in constraint for token in ("account(", "has_one", "seeds", "constraint", "init", "mut")):
                guard_id = _stable_id("guard", rel, name, field_name, attr_line)
                guards.append(
                    _node(
                        "guard",
                        rel,
                        f"{name}.{field_name} constraint",
                        constraint,
                        attr_line,
                        attr_line,
                        "medium",
                        id=guard_id,
                        parent_id=context_id,
                        metadata={"kind": "account_constraint", "context": name, "field": field_name, "runtime_profile": "anchor"},
                    )
                )
        pending_attrs = []

    return {"name": name, "node": context_node, "fields": fields, "guards": guards}


def _extract_edges(project_root: Path, path: Path, functions: list[dict], account_states: dict[str, dict], contexts: dict[str, dict]) -> dict:
    rel = _rel(project_root, path)
    lines = path.read_text(errors="ignore").splitlines()
    nodes: list[dict] = []
    edges: list[dict] = []
    external_nodes: dict[str, dict] = {}
    state_by_name = {name: node for name, node in account_states.items()}

    for fn in [item for item in functions if item["file"] == rel]:
        context = contexts.get(fn.get("metadata", {}).get("context") or "")
        if context:
            for guard in context["guards"]:
                edges.append(_edge("guards", fn["id"], guard["id"], rel, guard["start_line"], guard["signature"], "medium"))

        body = lines[fn["start_line"] - 1 : fn["end_line"]]
        for offset, raw in enumerate(body, start=fn["start_line"]):
            code = raw.split("//", 1)[0].strip()
            if not code:
                continue

            if any(token in code for token in ("require!", "require_keys_eq!", "require_gt!", "require_gte!", "err!")):
                guard_id = _stable_id("guard", rel, fn["name"], offset)
                guard = _node("guard", rel, f"{fn['name']} guard", code, offset, offset, "medium", id=guard_id, parent_id=fn["id"], metadata={"runtime_profile": "anchor"})
                nodes.append(guard)
                edges.append(_edge("guards", fn["id"], guard_id, rel, offset, code))

            if context:
                for field in context["fields"]:
                    field_name = field["name"]
                    if not re.search(rf"\bctx\.accounts\.{re.escape(field_name)}\b", code):
                        continue
                    edge_type = "writes" if _looks_mutating_account_use(code, field_name, field) else "reads"
                    edges.append(_edge(edge_type, fn["id"], field["id"], rel, offset, code))
                    account_type = _anchor_account_inner_type(field.get("metadata", {}).get("account_type", ""))
                    state_node = state_by_name.get(account_type)
                    if state_node:
                        edges.append(_edge(edge_type, fn["id"], state_node["id"], rel, offset, code))

            for call_name in _external_call_names(code):
                ext = external_nodes.get(call_name)
                if not ext:
                    ext_id = _stable_id("external", rel, call_name)
                    ext = _node(
                        "external_symbol",
                        rel,
                        call_name,
                        call_name,
                        offset,
                        offset,
                        "low",
                        id=ext_id,
                        parent_id=fn["id"],
                        metadata={"kind": "cpi_or_runtime_call", "runtime_profile": "anchor"},
                    )
                    external_nodes[call_name] = ext
                    nodes.append(ext)
                edges.append(_edge("external_call", fn["id"], ext["id"], rel, offset, code, "low"))
                if any(token in call_name for token in ("token::transfer", "system_program", "system_instruction", "transfer_checked")) or "lamports" in code:
                    edges.append(_edge("transfers_value", fn["id"], ext["id"], rel, offset, code, "low"))

    return {"nodes": nodes, "edges": edges}


def _external_call_names(code: str) -> list[str]:
    names = []
    for match in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*::[A-Za-z_][A-Za-z0-9_]*)\s*\(", code):
        name = match.group(1)
        if name.split("::")[-1] in {"new"}:
            continue
        names.append(name)
    for marker in ("invoke", "invoke_signed"):
        if re.search(rf"\b{marker}\s*\(", code):
            names.append(marker)
    return names


def _looks_mutating_account_use(code: str, field_name: str, field: dict) -> bool:
    if field.get("metadata", {}).get("mutable") and re.search(rf"{re.escape(field_name)}\.[A-Za-z0-9_]+\s*(?:=|\+=|-=)", code):
        return True
    return any(token in code for token in ("token::transfer", "token::mint_to", "token::burn", "try_borrow_mut_lamports", ".reload()"))


def _anchor_account_inner_type(raw: str) -> str | None:
    match = re.search(r"Account\s*<\s*'info\s*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*>", raw)
    return match.group(1) if match else None


def _context_name(signature: str) -> str | None:
    match = re.search(r"Context\s*<\s*([A-Za-z_][A-Za-z0-9_]*)\s*>", signature)
    return match.group(1) if match else None


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
        if paren <= 0 and "{" in piece:
            break
    return " ".join(pieces)
