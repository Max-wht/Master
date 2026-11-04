"""Parent-authored semantic grouping, lossless provenance and Judge input binding.

Bundled identically in each Cole skill to preserve standalone installation.
This module validates a partition; it does not infer semantic equivalence.
"""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
from pathlib import Path


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected an object")
    return value


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".dedup-", delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(text)
            handle.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def make_raw(api: dict, project_root: Path, run_dir: Path) -> dict:
    kai = api["load_kai_run"](run_dir)
    if kai["errors"]:
        raise ValueError("\n".join(kai["errors"]))
    manifest = kai["manifest"]
    if manifest.get("project_root") and Path(manifest["project_root"]).resolve() != project_root:
        raise ValueError("Research run belongs to a different project root")
    records, files, agent_ids, source_ids = [], {}, set(), set()
    for name in ("source.md", "jay-logic.json", "audit-map.json", "audit-context.json"):
        path = run_dir / name
        if path.is_file():
            files[str(path.resolve())] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in manifest.get("scope_files", []):
        path = (project_root / name).resolve()
        if not path.is_relative_to(project_root) or not path.is_file():
            raise ValueError(f"Missing or invalid scoped source: {name}")
        files[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    for agent in kai["agents"]:
        data = agent["data"]
        entry = agent.get("manifest", {})
        if (data["run_id"] != manifest.get("run_id", run_dir.name)
                or data["agent_id"] != entry.get("agent_id", data["agent_id"])
                or data["agent_name"] != entry.get("agent_name", data["agent_name"])):
            raise ValueError("Research run/agent identity mismatch")
        if agent["agent_id"] in agent_ids:
            raise ValueError("Duplicate research agent id")
        agent_ids.add(agent["agent_id"])
        for key in ("hypotheses_path", "report_path"):
            path = Path(agent[key]).resolve()
            files[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        for item in data["hypotheses"]:
            for evidence in item["evidence"]:
                path = (project_root / evidence["file"]).resolve()
                if path.is_relative_to(project_root) and path.is_file():
                    files[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
            source_id = f"{agent['agent_id']:02d}-{agent['agent_name']}:{item['id']}"
            if source_id in source_ids:
                raise ValueError(f"Duplicate source id: {source_id}")
            source_ids.add(source_id)
            records.append({
                "source_id": source_id,
                "source": {"agent_id": agent["agent_id"], "agent_name": agent["agent_name"],
                           "hypothesis_id": item["id"], "hypotheses_path": str(agent["hypotheses_path"])},
                "hypothesis": copy.deepcopy(item),
                "normalized": api["normalize_hypothesis"](agent, item),
            })
    raw = {"schema_version": "2.0.0", "run_id": run_dir.name,
           "project_root": str(project_root), "kai_run": str(run_dir),
           "audit_context": manifest.get("audit_context", {}),
           "manifest_digest": digest(manifest), "research_files": files,
           "source_hypothesis_count": len(records),
           "raw_candidates": sorted(records, key=lambda r: r["source_id"])}
    raw["input_digest"] = digest(raw)
    return raw


def current_raw(api: dict, raw_path: Path) -> dict:
    stored = read(raw_path)
    current = make_raw(api, Path(stored["project_root"]).resolve(), Path(stored["kai_run"]).resolve())
    if current != stored:
        raise ValueError("Raw input changed or research output is stale; collect again before grouping")
    return stored


def decision_template(raw: dict) -> dict:
    return {"schema_version": "1.0.0", "run_id": raw["run_id"],
            "input_digest": raw["input_digest"],
            "review_status": "needs_review" if raw["raw_candidates"] else "complete", "groups": []}


def render_bundle(raw: dict, raw_path: Path) -> str:
    lines = ["# Global semantic deduplication", "",
             "The parent agent must compare ALL candidates before Judge dispatch. Read each full record",
             "in raw-candidates.json and relevant source/context; this index is navigation, not evidence.",
             "Compare root cause, failure mechanism, necessary conditions and repair site. Wording,",
             "category or evidence-file differences do not establish independence. Merge different",
             "functions only for one shared cause resolved by the same repair. Keep independent causes",
             "and independently necessary conditions separate. Never merge different review_type values.",
             "Keep uncertain duplicates separate and explain why. Do not filter validity, assign severity,",
             "or drop any source. Every source_id must occur in exactly one group, including singletons.",
             "If reading in batches, maintain a global group index and compare across batches; file/category",
             "buckets are navigation aids and must not exclude cross-bucket comparisons.", "",
             "Write dedup-decisions.json with review_status=complete after actual global review.",
             "Each group has member_ids (source ids), title, claim, root_cause and rationale (nonempty text).",
             "Singletons also require an independence or uncertainty rationale. Scripts check structure",
             "and coverage only; the parent is responsible for semantic correctness.", "",
             f"Full records: {raw_path}", f"Input digest: {raw['input_digest']}",
             f"Raw candidates: {raw['source_hypothesis_count']}", "", "## Complete index", ""]
    for record in raw["raw_candidates"]:
        item = record["normalized"]
        lines.extend([f"### {record['source_id']}",
                      json.dumps({"title": item["title"], "claim": item["claim"],
                                  "review_type": item["review_type"], "category": item["category"],
                                  "evidence": item["evidence"], "jay_refs": item["jay_refs"]},
                                 ensure_ascii=False), ""])
    return "\n".join(lines)


def validate_decisions(raw: dict, decisions: dict) -> None:
    required = {"schema_version", "run_id", "input_digest", "review_status", "groups"}
    if set(decisions) != required or decisions.get("schema_version") != "1.0.0":
        raise ValueError("Invalid dedup decisions contract")
    if decisions["run_id"] != raw["run_id"] or decisions["input_digest"] != raw["input_digest"]:
        raise ValueError("Dedup decisions refer to different or stale input")
    if decisions["review_status"] != "complete" or not isinstance(decisions["groups"], list):
        raise ValueError("Global semantic review is not complete")
    by_id = {r["source_id"]: r for r in raw["raw_candidates"]}
    seen = set()
    for group in decisions["groups"]:
        fields = {"member_ids", "title", "claim", "root_cause", "rationale"}
        if not isinstance(group, dict) or set(group) != fields:
            raise ValueError("Each group requires member_ids, title, claim, root_cause and rationale only")
        if any(not isinstance(group[f], str) or not group[f].strip() for f in fields - {"member_ids"}):
            raise ValueError("Group title, claim, root_cause and rationale must be nonempty text")
        members = group["member_ids"]
        if not isinstance(members, list) or not members or any(not isinstance(m, str) for m in members):
            raise ValueError("member_ids must be a nonempty list of source ids")
        types = set()
        for member in members:
            if member not in by_id:
                raise ValueError(f"Unknown member: {member}")
            if member in seen:
                raise ValueError(f"Duplicate membership: {member}")
            seen.add(member)
            types.add(by_id[member]["normalized"]["review_type"])
        if len(types) != 1:
            raise ValueError("Cannot merge different review_type values")
    if seen != set(by_id):
        raise ValueError(f"Missing members: {sorted(set(by_id) - seen)}")


def build_candidates(api: dict, raw: dict, decisions: dict) -> dict:
    validate_decisions(raw, decisions)
    by_id = {r["source_id"]: r for r in raw["raw_candidates"]}
    groups, normalized = {}, []
    for decision in decisions["groups"]:
        members = sorted(decision["member_ids"])
        key = digest(members)
        groups[key] = {**decision, "member_ids": members}
        for member in members:
            item = copy.deepcopy(by_id[member]["normalized"])
            item["dedupe_key"] = key
            normalized.append(item)
    candidates = api["dedupe_candidates"](normalized)
    for candidate in candidates:
        group = groups[candidate["dedupe_key"]]
        candidate.update(title=group["title"], claim=group["claim"], root_cause=group["root_cause"],
                         dedup_rationale=group["rationale"], member_ids=group["member_ids"],
                         source_records=[copy.deepcopy(by_id[m]) for m in group["member_ids"]])
    count, remaining = raw["source_hypothesis_count"], len(candidates)
    return {"schema_version": "2.0.0", "run_id": raw["run_id"],
            "project_root": raw["project_root"], "kai_run": raw["kai_run"],
            "audit_context": raw["audit_context"], "source_hypothesis_count": count,
            "candidate_count": remaining, "candidates": candidates,
            "deduplication": {"status": "complete", "method": "parent-semantic",
                              "input_digest": raw["input_digest"], "decisions_digest": digest(decisions)},
            "dedup_stats": {"raw_count": count, "group_count": remaining,
                            "reduced_count": count - remaining,
                            "reduction_ratio": (count - remaining) / count if count else 0}}


def candidate_digest(data: dict) -> str:
    # Build readiness can be refreshed without changing the research identity.
    return digest({k: v for k, v in data.items() if k not in {"generated_at", "preflight"}})


def check_binding(data: dict, manifest: dict) -> list[str]:
    bound = manifest.get("candidates_digest")
    if bound is None and (data.get("deduplication") or "deduplication" in manifest):
        return ["New Judge manifests require a candidates digest"]
    if bound is not None and bound != candidate_digest(data):
        return ["Judge input changed; use a new Cole run"]
    return []


def verify_candidates(api: dict, data: dict, path: Path, allow_legacy: bool = False) -> None:
    if "deduplication" not in data:
        if allow_legacy:
            return
        raise ValueError("Semantic deduplication is required; use apply-dedup or --allow-legacy-candidates for historical input")
    raw = current_raw(api, path.parent / "raw-candidates.json")
    record = read(path.parent / "dedup-record.json")
    expected = build_candidates(api, raw, record["decisions"])
    if candidate_digest(data) != candidate_digest(expected):
        raise ValueError("Candidates do not match the validated semantic grouping")


def check_lock(directory: Path, data: dict) -> None:
    lock = directory / ".judge-lock.json"
    if lock.is_file() and read(lock).get("candidates_digest") != candidate_digest(data):
        raise ValueError("Judge input is locked; changed grouping requires a new Cole run")


def collect(api: dict, args: object) -> int:
    project_root = api["resolve_project_root"](args.project_root)
    run_dir = api["resolve_under_project"](project_root, args.run)
    out_dir = api["cole_run_dir"](project_root, args.out, run_dir)
    raw = make_raw(api, project_root, run_dir)
    raw_path = out_dir / "raw-candidates.json"
    if (out_dir / ".judge-lock.json").is_file():
        if not raw_path.is_file() or read(raw_path) != raw:
            raise ValueError("Judge input is locked; changed research requires a new Cole run")
    # Recollection with identical input preserves the parent's decisions and final report.
    if not raw_path.is_file() or read(raw_path) != raw:
        write(raw_path, raw)
        write(out_dir / "dedup-decisions.json", decision_template(raw))
    elif not (out_dir / "dedup-decisions.json").is_file():
        write(out_dir / "dedup-decisions.json", decision_template(raw))
    write(out_dir / "dedup-bundle.md", render_bundle(raw, raw_path))
    if not raw["raw_candidates"]:
        apply(api, raw_path, out_dir / "dedup-decisions.json")
    print(f"Collected {raw['source_hypothesis_count']} raw hypotheses; complete global semantic grouping in {out_dir / 'dedup-decisions.json'}")
    return 0


def apply(api: dict, raw_path: Path, decisions_path: Path) -> int:
    raw = current_raw(api, raw_path)
    decisions = read(decisions_path)
    payload = build_candidates(api, raw, decisions)
    errors = api["validate_candidates_payload"](payload)
    if errors:
        raise ValueError("\n".join(errors))
    out_dir = raw_path.parent
    check_lock(out_dir, payload)
    final_path = out_dir / "candidates.json"
    if final_path.is_file() and candidate_digest(read(final_path)) == candidate_digest(payload):
        print(f"Semantic grouping unchanged: {final_path}")
        return 0
    if (out_dir / ".judge-lock.json").is_file():
        raise ValueError("Judge input is locked; cannot replace candidates")
    # All structural, freshness and lock checks precede writes to good outputs.
    record = {"schema_version": "1.0.0", "decisions": decisions,
              "dedup_stats": payload["dedup_stats"],
              "candidate_members": {c["id"]: c["member_ids"] for c in payload["candidates"]}}
    write(out_dir / "dedup-record.json", record)
    write(final_path, payload)
    write(out_dir / "wreport.md", api["render_draft_wreport"](payload))
    print(f"Semantic grouping: {raw['source_hypothesis_count']} hypotheses -> {len(payload['candidates'])} Judge candidates")
    return 0


def summary(data: dict) -> str:
    state = data.get("deduplication", {})
    stats = data.get("dedup_stats")
    if state.get("status") == "complete" and isinstance(stats, dict):
        return (f"\nSemantic deduplication: {stats['raw_count']} raw candidates -> {stats['group_count']} groups; "
                f"reduced by {stats['reduced_count']} ({stats['reduction_ratio']:.1%}).\n")
    return "\nSemantic deduplication was not performed for this historical input.\n"
