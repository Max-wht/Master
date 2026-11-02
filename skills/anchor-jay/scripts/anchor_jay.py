#!/usr/bin/env python3
"""Source-only Anchor AST extraction. Business conclusions are supplied by the AI."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
from graph_io import build_line_links, render_call_graph, render_functions, render_line_links, render_storage_flow

SCHEMA_VERSION = "1.0.0"
DEFAULT_OUT = "MasterWu/Anchor/Jay"
EXCLUDED = {".git", ".anchor", "MasterWu", "target", "node_modules", "vendor", "test", "tests", ".venv", ".venv-check"}
NODE_TYPES = {"function", "statement", "state_var", "guard", "event", "external_symbol", "contract_or_module"}
EDGE_TYPES = {"calls", "reads", "writes", "guards", "emits", "external_call", "transfers_value", "state_transition", "precondition_written_by"}
SEMANTIC_KINDS = {"protocol-summary", "asset-flow", "lifecycle", "state-transition", "invariant", "external-assumption"}
PROVENANCE = {"source-fact", "inference", "unresolved"}


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def digest(data):
    stable = {k: v for k, v in data.items() if k != "generated_at"}
    return hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()


def parser():
    try:
        from tree_sitter import Language, Parser
        from importlib.metadata import version
        import tree_sitter_rust
        if version("tree-sitter") != "0.26.0" or version("tree-sitter-rust") != "0.24.2":
            raise ImportError("AST dependency versions do not match the pinned requirements")
        return Parser(Language(tree_sitter_rust.language()))
    except ImportError as exc:
        raise ValueError("Install AST dependencies with Python 3.11+: python3 -m pip install -r " + str(Path(__file__).with_name("requirements.txt"))) from exc


def walk(node):
    yield node
    for child in node.named_children:
        yield from walk(child)


def txt(node):
    return node.text.decode() if node else ""


def span(node):
    # tree-sitter 0.26.0's Point.row/column getters return borrowed integer
    # references. Tuple indexing avoids heap corruption beyond the small-int cache.
    start, end = node.start_point, node.end_point
    return start[0] + 1, end[0] + (1 if end[1] else 0)


def field(node, name):
    return node.child_by_field_name(name)


def declarations(node):
    attrs = []
    for child in node.named_children:
        if child.type == "attribute_item":
            attrs.append(child)
        elif child.type in {"line_comment", "block_comment", "inner_attribute_item"}:
            continue
        else:
            yield child, attrs
            attrs = []


def attributes(attrs):
    return [txt(a) for a in attrs]


def split_top(text, delimiter=","):
    """Split token expressions without losing nested seeds, calls or quoted commas."""
    parts, start, depth, quoted, escaped = [], 0, [], None, False
    for i, char in enumerate(text):
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quoted:
                quoted = None
            continue
        if char == '"':
            quoted = char
        elif char in "([{":
            depth.append(char)
        elif char == "<" and (text[max(0, i - 2):i] == "::" or (depth and depth[-1] == "<")):
            depth.append(char)
        elif char in ")]}" and depth and depth[-1] == {")": "(", "]": "[", "}": "{"}[char]:
            depth.pop()
        elif char == ">" and depth and depth[-1] == "<":
            depth.pop()
        elif char == delimiter and not depth:
            parts.append(text[start:i].strip())
            start = i + 1
    return [p for p in [*parts, text[start:].strip()] if p]


def constraints(attrs):
    out = []
    for attr in attrs:
        attr_node = next((n for n in attr.named_children if n.type == "attribute"), None)
        if not attr_node or txt(attr_node.named_children[0]) != "account":
            continue
        args = field(attr_node, "arguments")
        for expression in split_top(txt(args)[1:-1]):
            key, sep, value = expression.partition("=")
            out.append({"key": re.sub(r"\s+", "", key), "expression": value.strip() if sep else "", "raw": expression, "start_line": span(attr)[0], "end_line": span(attr)[1]})
    return out


class Extractor:
    def __init__(self, root: Path):
        self.root, self.parser = root, parser()
        self.files, self.crates, self.nodes, self.edges, self.gaps = {}, {}, {}, {}, []
        self.inputs = {}
        self.functions, self.contexts, self.imports = [], {}, defaultdict(dict)

    def gap(self, kind, file, node=None, detail=""):
        start, end = span(node) if node else (1, 1)
        item = {"kind": kind, "file": file, "start_line": start, "end_line": end, "detail": detail, "status": "requires-source-review"}
        if item not in self.gaps:
            self.gaps.append(item)

    def manifest(self, path):
        try:
            if not path.is_file():
                self.inputs[path.relative_to(self.root).as_posix()] = {"exists": False, "sha256": None, "lines": 0}
                return {}
            data = path.read_bytes()
            self.inputs[path.relative_to(self.root).as_posix()] = {"exists": True, "sha256": hashlib.sha256(data).hexdigest(), "lines": len(data.splitlines())}
            return tomllib.loads(data.decode())
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ValueError(f"Cannot read {path}: {exc}") from exc

    def add_crate(self, manifest_path):
        crate_root = manifest_path.parent
        rel = crate_root.relative_to(self.root).as_posix()
        if rel in self.crates:
            return self.crates[rel]
        data = self.manifest(manifest_path)
        root_manifest = self.manifest(self.root / "Cargo.toml")
        workspace_deps = root_manifest.get("workspace", {}).get("dependencies", {})
        # A member may declare its own workspace root.
        for parent in [crate_root, *crate_root.parents]:
            if not parent.is_relative_to(self.root):
                break
            candidate = self.manifest(parent / "Cargo.toml")
            if candidate.get("workspace"):
                workspace_deps = candidate["workspace"].get("dependencies", {})
                workspace_root = parent
                break
        else:
            workspace_root = self.root
        workspace_root = locals().get("workspace_root", self.root)
        package = data.get("package", {})
        name = package.get("name", crate_root.name).replace("-", "_")
        deps = {}
        for table in ("dependencies", "build-dependencies"):
            for alias, raw in data.get(table, {}).items():
                spec = {"version": raw} if isinstance(raw, str) else dict(raw)
                dep_root = crate_root
                if spec.get("workspace"):
                    inherited = workspace_deps.get(alias, {})
                    inherited = {"version": inherited} if isinstance(inherited, str) else dict(inherited)
                    spec = {**inherited, **spec, "features": sorted(set(inherited.get("features", []) + spec.get("features", [])))}
                    dep_root = workspace_root
                if "path" in spec:
                    spec["resolved_path"] = str((dep_root / spec["path"]).resolve())
                deps[alias] = spec
        locked = {}
        lock_path = workspace_root / "Cargo.lock"
        for dep in self.manifest(lock_path).get("package", []):
            locked.setdefault(dep.get("name"), []).append(dep.get("version"))
        crate = {"name": name, "root": rel, "manifest": manifest_path.relative_to(self.root).as_posix() if manifest_path.is_file() else None,
                 "dependencies": deps, "locked_versions": {k: v for k, v in locked.items() if k in {"anchor-lang", "anchor-spl", "spl-token", "spl-token-2022", "solana-program"}},
                 "features": data.get("features", {}), "profiles": root_manifest.get("profile", {}), "lib": data.get("lib", {}),
                 "has_lib_target": "lib" in data or (package.get("autolib", True) and (crate_root / "src/lib.rs").is_file())}
        self.crates[rel] = crate
        return crate

    def source(self, path, crate, module=(), module_base=None):
        if path.is_symlink():
            raise ValueError(f"Symlink source excluded: {path}")
        path = path.resolve()
        if not path.is_relative_to(self.root) or path.is_symlink():
            raise ValueError(f"Source outside project root or symlink: {path}")
        relative = path.relative_to(self.root).as_posix()
        if relative in self.files:
            return
        if not path.is_file() or path.suffix != ".rs":
            raise ValueError(f"Rust source not found: {path}")
        data = path.read_bytes()
        tree = self.parser.parse(data)
        self.files[relative] = {"sha256": hashlib.sha256(data).hexdigest(), "crate": crate["name"], "module": list(module), "lines": len(data.splitlines())}
        if tree.root_node.has_error:
            for item in walk(tree.root_node):
                if item.type == "ERROR" or item.is_missing:
                    self.gap("parse-error", relative, item, txt(item))
        base = module_base or (path.parent if path.name in {"lib.rs", "main.rs", "mod.rs"} else path.with_suffix(""))
        self.parse_declarations(tree.root_node, relative, crate, module, base, path)

    def node(self, kind, name, syntax, file, crate, module, metadata=None, parent=None):
        start, end = span(syntax)
        identifier = f"{kind}:{crate['name']}:{crate['root']}:{'::'.join(module)}:{name}:{file}:{start}:{syntax.start_byte}"
        value = {"id": identifier, "type": kind, "language": "anchor", "file": file, "name": name, "signature": txt(syntax), "start_line": start, "end_line": end,
                 "confidence": "high", "source_adapter": "anchor", "metadata": {"crate": crate["name"], "crate_root": crate["root"], "module": list(module), "runtime_profile": "anchor", **(metadata or {})}}
        if parent:
            value["parent_id"] = parent
        self.nodes[identifier] = value
        return value

    def edge(self, kind, source, target, syntax, file, metadata=None, confidence="high"):
        start, end = span(syntax)
        identifier = f"edge:{kind}:{source}:{target}:{file}:{start}:{end}:{syntax.start_byte}"
        self.edges[identifier] = {"id": identifier, "type": kind, "from": source, "to": target, "file": file, "start_line": start, "end_line": end, "label": txt(syntax), "confidence": confidence, "source_adapter": "anchor", "metadata": metadata or {}}

    def parse_declarations(self, container, file, crate, module, module_base, path, program=None):
        for item, attrs in declarations(container):
            raw_attrs = attributes(attrs)
            if any(re.search(r"cfg\s*\(\s*test\s*\)", a) for a in raw_attrs):
                continue
            for attr in attrs:
                if "cfg" in txt(attr):
                    self.gap("conditional-compilation", file, attr, txt(attr))
            name = txt(field(item, "name"))
            if item.type == "mod_item":
                body = field(item, "body")
                is_program = any(re.fullmatch(r"#\[\s*program\s*\]", a) for a in raw_attrs)
                mod_node = self.node("contract_or_module", name, item, file, crate, module, {"kind": "program" if is_program else "module", "attributes": raw_attrs})
                if body:
                    self.parse_declarations(body, file, crate, (*module, name), module_base / name, path, mod_node if is_program else program)
                else:
                    explicit = next((re.search(r'path\s*=\s*"([^"]+)"', a) for a in raw_attrs if "path" in a), None)
                    candidates = [path.parent / explicit.group(1)] if explicit else [module_base / f"{name}.rs", module_base / name / "mod.rs"]
                    found = [p for p in candidates if p.is_file()]
                    if len(found) == 1:
                        self.source(found[0], crate, (*module, name))
                    else:
                        self.gap("unresolved-module", file, item, "; ".join(str(p) for p in candidates))
            elif item.type == "use_declaration":
                argument = txt(field(item, "argument"))
                self.read_imports(argument, crate, module)
            elif item.type == "function_item":
                params = field(item, "parameters")
                context, ctx_arg = None, "ctx"
                for param in params.named_children if params else []:
                    typ = field(param, "type")
                    if typ and typ.type == "generic_type" and txt(field(typ, "type")) == "Context":
                        args = field(typ, "type_arguments")
                        types = [n for n in args.named_children if n.type not in {"lifetime", "lifetime_parameter"}]
                        context = txt(field(types[-1], "type") or types[-1]) if types else None
                        ctx_arg = (txt(field(param, "pattern")) or "ctx").removeprefix("mut ")
                fn = self.node("function", name, item, file, crate, module, {"entry_point": bool(program and context), "context": context, "context_argument": ctx_arg, "attributes": raw_attrs,
                               "parameters": [{"name": txt(field(p, "pattern")), "type": txt(field(p, "type"))} for p in params.named_children if p.type == "parameter"]}, program["id"] if program else None)
                body = field(item, "body")
                fn["signature"] = txt(item).split("{", 1)[0].strip()
                fn["visibility"] = "entry" if fn["metadata"]["entry_point"] else ("public" if any(n.type == "visibility_modifier" for n in item.named_children) else "private")
                self.functions.append((fn, item, body, crate, module))
            elif item.type == "struct_item":
                is_context = any(re.search(r"derive\s*\([^)]*\bAccounts\b", a) for a in raw_attrs)
                is_account = any(re.match(r"#\[\s*account\b", a) for a in raw_attrs)
                struct = self.node("contract_or_module" if is_context else "state_var", name, item, file, crate, module, {"kind": "accounts_context" if is_context else "account_state" if is_account else "struct", "attributes": raw_attrs})
                fields, guards = [], []
                body = field(item, "body")
                for member, member_attrs in declarations(body) if body else []:
                    if member.type != "field_declaration":
                        continue
                    typ = field(member, "type")
                    checks, wrapper, inner = [], None, None
                    for nested in walk(typ):
                        if nested.type != "generic_type":
                            continue
                        typename = txt(field(nested, "type")).split("::")[-1]
                        if typename in {"Account", "AccountLoader", "InterfaceAccount", "Signer", "Program", "Interface", "UncheckedAccount", "AccountInfo", "SystemAccount", "Sysvar"}:
                            wrapper = typename
                            args = field(nested, "type_arguments")
                            types = [n for n in args.named_children if n.type != "lifetime"] if args else []
                            inner = txt(types[-1]) if types else None
                            break
                    if wrapper in {"Account", "AccountLoader"}:
                        checks = ["type-defined owner validation", "type-defined deserialization/discriminator validation; check type and version"]
                    elif wrapper == "InterfaceAccount":
                        checks = ["type-defined accepted owners", "type-defined deserialization; inspect SPL/Anchor type"]
                    elif wrapper == "Signer":
                        checks = ["is_signer"]
                    elif wrapper in {"Program", "Interface"}:
                        checks = ["type-defined program id/accepted ids", "executable"]
                    elif wrapper == "SystemAccount":
                        checks = ["system program owner"]
                    elif wrapper == "Sysvar":
                        checks = ["type-defined sysvar id", "type-defined sysvar deserialization"]
                    cons = constraints(member_attrs)
                    fld = self.node("state_var", txt(field(member, "name")), member, file, crate, module,
                                    {"kind": "account_field" if is_context else "struct_field", "context": name, "account_type": txt(typ), "wrapper": wrapper, "inner_type": inner, "implicit_checks": checks,
                                     "constraints": cons, "mutable": any(c["key"] == "mut" for c in cons), "signer": wrapper == "Signer" or any(c["key"] == "signer" for c in cons), "pda": any(c["key"] == "seeds" for c in cons), "attributes": attributes(member_attrs)}, struct["id"])
                    fields.append(fld)
                    if is_context:
                        for attr in member_attrs:
                            if constraints([attr]):
                                guard = self.node("guard", name + "." + fld["name"], attr, file, crate, module, {"kind": "explicit_account_constraint", "field": fld["name"], "constraints": constraints([attr])}, struct["id"])
                                guards.append(guard)
                if is_context:
                    self.contexts[(crate["root"], module, name)] = {"node": struct, "fields": fields, "guards": guards}
            elif item.type == "impl_item":
                body = field(item, "body")
                if body:
                    self.parse_declarations(body, file, crate, (*module, txt(field(item, "type"))), module_base, path)
            elif item.type in {"macro_invocation", "macro_definition"}:
                self.gap("custom-macro", file, item, txt(item))
            elif item.type in {"expression_statement"}:
                for child in walk(item):
                    if child.type == "macro_invocation" and txt(field(child, "macro")) not in {"declare_id"}:
                        self.gap("custom-macro", file, child, txt(child))

    def read_imports(self, expression, crate, module, prefix=""):
        if "{" in expression:
            head, tail = expression.split("{", 1)
            for part in split_top(tail.rsplit("}", 1)[0]):
                self.read_imports(part, crate, module, prefix + head)
        elif expression != "*":
            original, _, alias = expression.partition(" as ")
            original = prefix + original
            key = "wildcard:" + original if original.endswith("::*") else alias.strip() or original.split("::")[-1]
            self.imports[(crate["root"], module)][key] = original.strip()

    def qualify(self, expression, crate, module):
        parts = expression.split("::")
        imports = self.imports.get((crate["root"], module), {})
        if parts[0] in imports:
            parts = (imports[parts[0]] + ("::" + "::".join(parts[1:]) if len(parts) > 1 else "")).split("::")
        if parts[0] == "crate":
            return crate["name"], tuple(parts[1:])
        if parts[0] == "self":
            return crate["name"], (*module, *parts[1:])
        dep = crate["dependencies"].get(parts[0], {})
        if dep.get("resolved_path"):
            for helper in self.crates.values():
                if self.root / helper["root"] == Path(dep["resolved_path"]):
                    return helper["name"], tuple(parts[1:])
        base = module
        while parts and parts[0] == "super":
            base, parts = base[:-1], parts[1:]
        if not parts:
            return crate["name"], base
        if expression.startswith("super::") or (parts and parts[0] not in {c["name"] for c in self.crates.values()}):
            return crate["name"], (*base, *parts)
        return parts[0], tuple(parts[1:])

    def resolve_symbol(self, expression, crate, module, candidates, visited=None):
        if not expression:
            return None
        visited = set() if visited is None else visited
        key = (crate["root"], module, expression)
        if key in visited:
            return None
        visited.add(key)
        name, qualified = self.qualify(expression, crate, module)
        matches = [c for c in candidates if c["metadata"]["crate"] == name and (*c["metadata"]["module"], c["name"]) == qualified]
        if not matches and "::" not in expression:
            matches = [c for c in candidates if c["metadata"]["crate_root"] == crate["root"] and c["name"] == expression and tuple(c["metadata"]["module"]) in {module, (), module[:-1]}]
        if not matches:
            for import_key, path in self.imports.get((crate["root"], module), {}).items():
                if not import_key.startswith("wildcard:"):
                    continue
                imported_crate, namespace = self.qualify(path[:-3], crate, module)
                owner = next((c for c in self.crates.values() if c["name"] == imported_crate), None)
                if owner:
                    found = self.resolve_symbol(expression, owner, namespace, candidates, visited)
                    if found and found not in matches:
                        matches.append(found)
        return matches[0] if len(matches) == 1 else None

    def extract_edges(self):
        functions = [f[0] for f in self.functions]
        for fn, syntax, body, crate, module in self.functions:
            if not body:
                continue
            file, ctx_arg = fn["file"], fn["metadata"]["context_argument"]
            context_node = self.resolve_symbol(fn["metadata"].get("context") or "", crate, module, [c["node"] for c in self.contexts.values()])
            context = next((c for c in self.contexts.values() if c["node"] == context_node), None)
            if fn["metadata"].get("context") and not context:
                self.gap("unresolved-context", file, syntax, fn["metadata"]["context"])
            account_fields = {f["name"]: f for f in context["fields"]} if context else {}
            for guard in context["guards"] if context else []:
                # Constraint evidence belongs to its declaration file, not the handler file.
                self.edges[f"edge:guards:{fn['id']}:{guard['id']}"] = {"id": f"edge:guards:{fn['id']}:{guard['id']}", "type": "guards", "from": fn["id"], "to": guard["id"], "file": guard["file"], "start_line": guard["start_line"], "end_line": guard["end_line"], "label": guard["signature"], "confidence": "high", "source_adapter": "anchor"}
            aliases = {}
            states = [n for n in self.nodes.values() if n["metadata"].get("kind") in {"account_state", "struct"}]
            for parameter in fn["metadata"].get("parameters", []):
                typ = re.sub(r"^&\s*(?:'\w+\s*)?(?:mut\s+)?", "", parameter["type"])
                state = self.resolve_symbol(typ, crate, module, states)
                if state:
                    aliases[parameter["name"]] = state

            def account_ref(expression):
                clean = re.sub(r"\s+", "", expression).lstrip("&*")
                clean = clean.removeprefix("mut")
                if clean.startswith(ctx_arg + ".accounts."):
                    return account_fields.get(clean.split(".")[2])
                first = clean.split(".")[0]
                return aliases.get(first)

            for node in walk(body):
                if node.type == "let_declaration":
                    value = field(node, "value")
                    ref = account_ref(txt(value))
                    if ref and field(node, "pattern") and field(node, "pattern").type == "identifier":
                        aliases[txt(field(node, "pattern"))] = ref
                if node.type == "field_expression":
                    ref = account_ref(txt(node))
                    if ref:
                        self.edge("reads", fn["id"], ref["id"], node, file)
                        inner = ref["metadata"].get("inner_type")
                        if inner:
                            state = self.resolve_symbol(inner, crate, tuple(context_node["metadata"]["module"]) if context_node else module, states)
                            if state:
                                self.edge("reads", fn["id"], state["id"], node, file, confidence="medium")
                if node.type in {"assignment_expression", "compound_assignment_expr"}:
                    ref = account_ref(txt(field(node, "left")))
                    if ref:
                        self.edge("writes", fn["id"], ref["id"], node, file)
                        self.edge("state_transition", fn["id"], ref["id"], node, file, {"effect": "syntactic assignment; business meaning requires AI review"})
                        if "lamports" in txt(field(node, "left")):
                            self.edge("transfers_value", fn["id"], ref["id"], node, file, {"effect": "direct lamport delta; verify balanced debit/credit and owner permissions"}, "medium")
                        inner = ref["metadata"].get("inner_type")
                        if inner:
                            state = self.resolve_symbol(inner, crate, tuple(context_node["metadata"]["module"]) if context_node else module, states)
                            if state:
                                self.edge("writes", fn["id"], state["id"], node, file, confidence="medium")
                if node.type == "macro_invocation":
                    macro = txt(field(node, "macro"))
                    if macro.startswith("require") or macro in {"err", "assert", "assert_eq"}:
                        guard = self.node("guard", fn["name"] + ":" + macro, node, file, crate, module, {"kind": "manual_guard", "raw_predicate": txt(node)}, fn["id"])
                        self.edge("guards", fn["id"], guard["id"], node, file)
                    elif macro not in {"msg", "emit", "emit_cpi", "format", "vec"}:
                        self.gap("custom-macro", file, node, txt(node))
                if node.type == "if_expression":
                    consequence = field(node, "consequence")
                    if consequence and any(n.type == "return_expression" and ("Err" in txt(n) or "err!" in txt(n)) for n in walk(consequence)):
                        guard = self.node("guard", fn["name"] + ":error-branch", node, file, crate, module, {"kind": "manual_guard", "raw_predicate": txt(field(node, "condition")), "control_flow": "error branch; verify polarity and reachability"}, fn["id"])
                        self.edge("guards", fn["id"], guard["id"], node, file)
                if node.type != "call_expression":
                    continue
                callee, args = txt(field(node, "function")), field(node, "arguments")
                if callee.endswith(("CpiContext::new", "CpiContext::new_with_signer")) or callee.endswith(".with_signer"):
                    values = args.named_children if args else []
                    self.node("statement", fn["name"] + ":cpi-context", node, file, crate, module, {"kind": "cpi_context", "program_expression": txt(values[0]) if values and not callee.endswith(".with_signer") else "", "signer_seeds": txt(values[-1]) if values and ("signer" in callee) else "", "raw": txt(node)}, fn["id"])
                    continue
                target = self.resolve_symbol(callee, crate, module, functions)
                if target:
                    self.edge("calls", fn["id"], target["id"], node, file, confidence="medium")
                    continue
                # Method type inference is deliberately not claimed by a syntax parser.
                if "." in callee:
                    method = callee.rsplit(".", 1)[-1]
                    ref = account_ref(callee.rsplit(".", 1)[0])
                    if ref and method in {"reload", "close", "realloc", "try_borrow_mut_lamports", "borrow_mut"}:
                        self.edge("writes", fn["id"], ref["id"], node, file, {"method": method, "effect": "method requires semantic review"}, "medium")
                    elif method not in {"key", "to_account_info", "as_ref", "clone", "unwrap", "unwrap_or", "ok_or", "checked_add", "checked_sub", "checked_mul", "checked_div", "saturating_add", "saturating_sub", "len", "iter", "into", "get", "map_err", "is_empty"}:
                        self.gap("unresolved-method", file, node, callee)
                    continue
                if callee in {"Ok", "Err", "Some", "None"} or callee.endswith("::default"):
                    continue
                imported = self.imports.get((crate["root"], module), {}).get(callee.split("::")[0], "")
                known_cpi = callee.split("::")[-1] in {"invoke", "invoke_signed"} or ((any(k in callee or k in imported for k in {"token", "system_program", "system_instruction"})) and callee.split("::")[-1] in {"transfer", "transfer_checked", "mint_to", "burn", "close_account", "set_authority", "create_account"})
                ext = self.node("external_symbol", callee, node, file, crate, module, {"kind": "cpi" if known_cpi else "unresolved_call", "is_cpi": known_cpi, "arguments": txt(args), "signer_forwarding": callee.endswith("invoke_signed"), "source_resolution": imported}, fn["id"])
                self.edge("external_call", fn["id"], ext["id"], node, file, confidence="medium" if known_cpi else "low")
                if known_cpi and any(k in callee for k in {"transfer", "mint_to", "burn", "close_account"}):
                    self.edge("transfers_value", fn["id"], ext["id"], node, file, {"effect": "candidate value operation; inspect accounts and actual deltas"}, "medium")
                if not known_cpi:
                    self.gap("unresolved-call", file, node, callee)

    def build(self, explicit=None):
        self.manifest(self.root / "Anchor.toml")
        manifests = sorted(p for p in self.root.rglob("Cargo.toml") if not any(part in EXCLUDED or part.startswith(".") for part in p.relative_to(self.root).parts[:-1]))
        crates = [self.add_crate(p) for p in manifests if self.manifest(p).get("package")]
        selected = []
        if explicit is not None:
            if not explicit:
                raise ValueError("--files must name at least one Rust file")
            for raw in explicit:
                path = Path(raw)
                path = (path if path.is_absolute() else self.root / path).resolve()
                if not path.is_relative_to(self.root) or path.suffix != ".rs" or not path.is_file():
                    raise ValueError(f"Invalid explicit Anchor source: {raw}")
                owners = [c for c in crates if path.is_relative_to(self.root / c["root"])]
                crate = max(owners, key=lambda c: len(c["root"])) if owners else self.add_crate(path.parent / "Cargo.toml")
                if crate not in selected:
                    selected.append(crate)
                self.source(path, crate, (() if path.name in {"lib.rs", "main.rs", "mod.rs"} else (path.stem,)))
        else:
            selected = [c for c in crates if c["has_lib_target"] and any(k == "anchor-lang" or v.get("package") == "anchor-lang" for k, v in c["dependencies"].items())]
            if not selected and (self.root / "Anchor.toml").is_file():
                selected = [self.add_crate(p.parent.parent / "Cargo.toml") for p in sorted((self.root / "programs").glob("*/src/lib.rs"))]
            for crate in selected:
                self.source(self.root / crate["root"] / crate["lib"].get("path", "src/lib.rs"), crate)
        pending = list(selected)
        visited = set()
        while pending:
            crate = pending.pop()
            if crate["root"] in visited:
                continue
            visited.add(crate["root"])
            for alias, spec in crate["dependencies"].items():
                if "resolved_path" not in spec:
                    continue
                dep = Path(spec["resolved_path"])
                if not dep.is_relative_to(self.root):
                    self.gap("external-path-dependency", crate["manifest"] or "Anchor.toml", detail=str(dep))
                    continue
                if (dep / "Cargo.toml").is_file():
                    helper = self.add_crate(dep / "Cargo.toml")
                    lib = dep / helper["lib"].get("path", "src/lib.rs")
                    if helper["has_lib_target"] and lib.is_file():
                        self.source(lib, helper)
                        pending.append(helper)
        if not self.files or not any(n["metadata"].get("kind") in {"program", "accounts_context"} for n in self.nodes.values()):
            raise ValueError("No Anchor program/account context found; native Solana Rust is outside this skill")
        self.extract_edges()
        nodes = sorted(self.nodes.values(), key=lambda n: n["id"])
        edges = sorted(self.edges.values(), key=lambda e: e["id"])
        used = {f["crate"] for f in self.files.values()}
        return {"schema_version": SCHEMA_VERSION, "generated_at": datetime.now(timezone.utc).isoformat(), "project_root": str(self.root), "languages": ["anchor"], "nodes": nodes, "edges": edges,
                "line_links": build_line_links(nodes, edges), "stats": {"nodes": len(nodes), "edges": len(edges), "functions": sum(n["type"] == "function" for n in nodes)},
                "metadata": {"runtime": "anchor", "parser": "tree-sitter 0.26.0 / rust 0.24.2", "source_files": self.files, "input_files": self.inputs, "crates": [c for c in self.crates.values() if c["name"] in used], "coverage_gaps": self.gaps}}


def validate_graph(graph, check_sources=True):
    if not isinstance(graph, dict):
        return ["Graph must be an object"]
    errors = []
    for key in {"schema_version", "generated_at", "project_root", "languages", "nodes", "edges", "line_links", "stats", "metadata"}:
        if key not in graph:
            errors.append("Missing graph field: " + key)
    if errors:
        return errors
    if graph["schema_version"] != SCHEMA_VERSION or graph["languages"] != ["anchor"]:
        errors.append("Expected Anchor graph schema 1.0.0")
    if not isinstance(graph["nodes"], list) or not isinstance(graph["edges"], list) or not isinstance(graph["metadata"], dict):
        return errors + ["nodes/edges must be lists and metadata an object"]
    ids = {"node": set(), "edge": set()}
    sources = graph["metadata"].get("source_files", {})
    if not isinstance(sources, dict) or not sources:
        return errors + ["source_files must be a nonempty object"]
    for file, info in sources.items():
        if not isinstance(file, str) or not isinstance(info, dict) or type(info.get("lines")) is not int or info["lines"] < 1 or not isinstance(info.get("sha256"), str):
            return errors + ["Invalid source file metadata"]
    for group, types in [("node", NODE_TYPES), ("edge", EDGE_TYPES)]:
        for item in graph[group + "s"]:
            if not isinstance(item, dict):
                errors.append(group + " must be an object")
                continue
            identifier = item.get("id")
            if not isinstance(identifier, str) or identifier in ids[group]:
                errors.append("Invalid or duplicate " + group + " id")
                continue
            ids[group].add(identifier)
            required = {"id", "type", "file", "start_line", "end_line", "confidence", "source_adapter"} | ({"language", "name", "signature"} if group == "node" else {"from", "to", "label"})
            if required - item.keys():
                errors.append(f"Missing {group} fields: {identifier}")
            if item.get("confidence") not in {"low", "medium", "high"} or item.get("source_adapter") != "anchor":
                errors.append(f"Invalid extraction metadata: {identifier}")
            if item.get("type") not in types:
                errors.append("Invalid " + group + " type")
            file = item.get("file")
            start, end = item.get("start_line"), item.get("end_line")
            if not isinstance(file, str) or file not in sources or type(start) is not int or type(end) is not int or not 1 <= start <= end <= sources[file]["lines"]:
                errors.append(f"Invalid source range: {identifier}")
            if group == "edge" and (item.get("from") not in ids["node"] or item.get("to") not in ids["node"]):
                errors.append(f"Unknown edge endpoint: {identifier}")
    for node in graph["nodes"]:
        if isinstance(node, dict) and node.get("parent_id") and node["parent_id"] not in ids["node"]:
            errors.append("Unknown node parent")
    if not isinstance(graph["line_links"], list):
        errors.append("line_links must be a list")
    else:
        for link in graph["line_links"]:
            if not isinstance(link, dict) or not isinstance(link.get("file"), str) or link["file"] not in sources or type(link.get("line")) is not int or not 1 <= link["line"] <= sources[link["file"]]["lines"]:
                errors.append("Invalid reverse source index")
                continue
            for group in ("node", "edge"):
                refs = link.get(group + "_ids")
                if not isinstance(refs, list) or any(not isinstance(ref, str) or ref not in ids[group] for ref in refs):
                    errors.append("Unknown id in reverse source index")
    if check_sources:
        root = Path(graph["project_root"])
        for file, info in {**sources, **graph["metadata"].get("input_files", {})}.items():
            path = (root / file).resolve()
            if info.get("exists") is False and not path.exists():
                continue
            if not path.is_relative_to(root.resolve()) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != info.get("sha256"):
                errors.append(f"Source/configuration changed or missing: {file}; rebuild Jay and review semantics again")
    return errors


def validate_audit_map(data, graph, require_semantics=False):
    if not isinstance(data, dict):
        return ["audit-map must be an object"]
    errors = []
    if data.get("schema_version") != SCHEMA_VERSION or data.get("graph_digest") != digest(graph):
        errors.append("audit-map schema or graph digest mismatch")
    if data.get("review_status") not in {"needs_ai_review", "complete"}:
        errors.append("Invalid audit-map review_status")
    if require_semantics and data.get("review_status") != "complete":
        errors.append("Complete the AI business map before Anchor Kai preparation")
    semantics = data.get("semantics")
    if not isinstance(semantics, list):
        return errors + ["semantics must be a list"]
    if data.get("review_status") == "complete" and (not semantics or not isinstance(data.get("completion_notes"), str) or not data["completion_notes"].strip()):
        errors.append("Complete business map requires sourced semantics and completion_notes")
    ids = {n["id"] for n in graph["nodes"]}
    sources = graph["metadata"]["source_files"]
    for item in semantics:
        if not isinstance(item, dict):
            errors.append("Semantic entry must be an object")
            continue
        if {"severity", "classification", "verdict", "confirmed", "final_id"} & item.keys():
            errors.append("Business map cannot contain final audit verdicts")
        if item.get("kind") not in SEMANTIC_KINDS or item.get("provenance") not in PROVENANCE or not isinstance(item.get("description"), str) or not item["description"].strip():
            errors.append("Semantic entries need kind, provenance and description")
        refs = item.get("node_ids")
        if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or ref not in ids for ref in refs):
            errors.append("Semantic entry needs existing graph node ids")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append("Semantic entry needs source evidence")
            continue
        for e in evidence:
            if not isinstance(e, dict):
                errors.append("Semantic evidence must be an object")
                continue
            file, start, end = e.get("file"), e.get("start_line"), e.get("end_line")
            if file not in sources or type(start) is not int or type(end) is not int or not 1 <= start <= end <= sources[file]["lines"]:
                errors.append("Invalid semantic source range")
    return errors


def build(root, out, explicit=None):
    graph = Extractor(root).build(explicit)
    errors = validate_graph(graph)
    if errors:
        raise ValueError("\n".join(errors))
    out.mkdir(parents=True, exist_ok=True)
    audit = {"schema_version": SCHEMA_VERSION, "graph_digest": digest(graph), "review_status": "needs_ai_review", "completion_notes": "", "semantics": []}
    existing = out / "audit-map.json"
    if existing.is_file():
        prior = json.loads(existing.read_text())
        if prior.get("graph_digest") == audit["graph_digest"]:
            audit = prior
        else:
            write_json(out / "audit-map.previous.json", prior)
    write_json(out / "jay-logic.json", graph)
    write_json(out / "audit-map.json", audit)
    (out / "functions.md").write_text(render_functions(graph))
    (out / "line-links.tsv").write_text(render_line_links(graph))
    (out / "call-graph.mmd").write_text(render_call_graph(graph))
    (out / "storage-flow.mmd").write_text(render_storage_flow(graph))
    entries = [n for n in graph["nodes"] if n["metadata"].get("entry_point")]
    (out / "entry-flows.md").write_text("# Anchor Instructions\n\n" + "\n".join(f"- {n['name']}: {n['file']}:{n['start_line']}; context={n['metadata']['context']}" for n in entries) + "\n")
    print(f"Anchor Jay extracted {len(graph['nodes'])} nodes, {len(graph['edges'])} edges; business map: {audit['review_status']}")
    return graph


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest="command", required=True)
    b = commands.add_parser("build")
    b.add_argument("project_root", type=Path)
    b.add_argument("--out", default=DEFAULT_OUT)
    b.add_argument("--files", nargs="+")
    v = commands.add_parser("validate")
    v.add_argument("graph_path", type=Path)
    v.add_argument("--audit-map", type=Path)
    v.add_argument("--require-semantics", action="store_true")
    args = cli.parse_args()
    try:
        if args.command == "build":
            root = args.project_root.resolve()
            if not root.is_dir():
                raise ValueError(f"Project not found: {root}")
            output = Path(args.out)
            build(root, output if output.is_absolute() else root / output, args.files)
            return 0
        graph = json.loads(args.graph_path.read_text())
        errors = validate_graph(graph)
        audit_path = args.audit_map or args.graph_path.with_name("audit-map.json")
        if audit_path.is_file():
            errors += validate_audit_map(json.loads(audit_path.read_text()), graph, args.require_semantics)
        elif args.require_semantics or args.audit_map:
            errors.append(f"Missing business map: {audit_path}")
        if errors:
            raise ValueError("\n".join(errors))
        print("Anchor graph and business map are valid")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
