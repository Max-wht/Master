from __future__ import annotations

import re
from pathlib import Path

LANGUAGE = "generic"
EXTENSIONS = {".cairo", ".js", ".py", ".rs", ".ts"}
EXCLUDED_DIRS = {".git", "Lloyd", "MasterWu", "build", "dist", "jay-logic", "node_modules", "target", "test", "tests"}


def detect(project_root: Path, include_files: list[Path] | None = None) -> bool:
    return any(_iter_files(project_root, include_files=include_files))


def collect(project_root: Path, include_files: list[Path] | None = None) -> dict:
    nodes: list[dict] = []
    edges: list[dict] = []
    functions: list[dict] = []
    for path in _iter_files(project_root, include_files=include_files):
        parsed = _parse_file(project_root, path)
        nodes.extend(parsed["nodes"])
        functions.extend(parsed["functions"])

    by_name: dict[str, list[dict]] = {}
    for fn in functions:
        by_name.setdefault(fn["name"], []).append(fn)

    for fn in functions:
        path = project_root / fn["file"]
        lines = path.read_text(errors="ignore").splitlines()
        for offset, raw in enumerate(lines[fn["start_line"] - 1 : fn["end_line"]], start=fn["start_line"]):
            code = raw.split("//", 1)[0].strip()
            for call in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", code):
                if call in {"for", "if", "return", "switch", "while"}:
                    continue
                candidates = [target for target in by_name.get(call, []) if target["id"] != fn["id"]]
                if candidates:
                    edges.append(_edge("calls", fn["id"], candidates[0]["id"], fn["file"], offset, code))

    return {"language": LANGUAGE, "nodes": nodes, "edges": edges}


def _iter_files(project_root: Path, include_files: list[Path] | None = None):
    if include_files is not None:
        for path in include_files:
            if path.suffix in EXTENSIONS:
                yield path
        return
    for path in project_root.rglob("*"):
        if not path.is_file() or path.suffix not in EXTENSIONS:
            continue
        if any(part in EXCLUDED_DIRS for part in path.relative_to(project_root).parts[:-1]):
            continue
        yield path


def _parse_file(project_root: Path, path: Path) -> dict:
    rel = path.relative_to(project_root).as_posix()
    lines = path.read_text(errors="ignore").splitlines()
    nodes: list[dict] = []
    functions: list[dict] = []
    pattern = re.compile(r"\b(?:function|fn|def|func)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
    starts: list[tuple[int, str, str]] = []
    for idx, line in enumerate(lines, start=1):
        match = pattern.search(line)
        if match:
            starts.append((idx, match.group(1), line.strip()))
    for pos, (start, name, signature) in enumerate(starts):
        end = starts[pos + 1][0] - 1 if pos + 1 < len(starts) else len(lines)
        fn_id = _stable_id("function", rel, name, start)
        node = {
            "id": fn_id,
            "type": "function",
            "language": LANGUAGE,
            "file": rel,
            "name": name,
            "signature": signature,
            "start_line": start,
            "end_line": end,
            "confidence": "low",
            "source_adapter": LANGUAGE,
            "visibility": "unknown",
            "metadata": {"entry_point": False},
        }
        nodes.append(node)
        functions.append(node)
    return {"nodes": nodes, "functions": functions}


def _stable_id(kind: str, *parts: object) -> str:
    raw = ":".join(str(p).replace(":", "_").replace(" ", "_") for p in parts)
    return f"{kind}:{raw}"


def _edge(edge_type: str, source: str, target: str, file: str, line: int, label: str) -> dict:
    return {
        "id": _stable_id("edge", edge_type, source, target, file, line, label),
        "type": edge_type,
        "from": source,
        "to": target,
        "file": file,
        "start_line": line,
        "end_line": line,
        "label": label,
        "confidence": "low",
        "source_adapter": LANGUAGE,
    }
