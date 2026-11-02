"""Standalone Anchor hypothesis contract (Kai/Cole schema 2.0.0)."""
import re

SCHEMA_VERSION = "2.0.0"
SUPPORTED_SCHEMAS = {SCHEMA_VERSION}
REVIEW_TYPES = {"vulnerability", "trust-risk", "design-risk", "hardening", "engineering-quality"}
REVIEW_TEXT_FIELDS = ("scenario", "applicability", "existing_controls", "recommendation", "tradeoffs")
CONFIDENCE_VALUES = {"low", "medium", "high"}
def _validate_hypotheses(data: dict) -> list[str]:
    if not isinstance(data, dict):
        return ["validate_hypotheses: input must be an object"]
    errors = []
    for field in ("schema_version", "run_id", "agent_id", "agent_name", "hypotheses"):
        if field not in data:
            errors.append(f"missing top-level field: {field}")
    if errors:
        return errors
    if data["schema_version"] not in SUPPORTED_SCHEMAS:
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
    if data["schema_version"] == SCHEMA_VERSION:
        required = (required - {"attack_sketch"}) | {"review_type", "missing_context", *REVIEW_TEXT_FIELDS}
    forbidden = {"severity", "verdict", "final_verdict", "confirmed", "classification", "final_id"}
    for idx, item in enumerate(data["hypotheses"]):
        if not isinstance(item, dict):
            errors.append(f"hypotheses[{idx}] must be an object")
            continue
        missing = required - set(item)
        if missing:
            errors.append(f"hypotheses[{idx}] missing fields: {sorted(missing)}")
        if data["schema_version"] == SCHEMA_VERSION:
            errors.extend(validate_review_fields(item, f"hypotheses[{idx}]"))
            errors.extend(validate_source_evidence(item.get("evidence"), f"hypotheses[{idx}]"))
        present_forbidden = forbidden & set(item)
        if present_forbidden:
            errors.append(f"hypotheses[{idx}] forbidden fields: {sorted(present_forbidden)}")
        if not isinstance(item.get("confidence"), str) or item["confidence"] not in CONFIDENCE_VALUES:
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

def validate_source_evidence(items: object, label: str) -> list[str]:
    if not isinstance(items, list) or not items:
        return [f"{label}: evidence must be a non-empty list"]
    errors = []
    for index, evidence in enumerate(items):
        if not isinstance(evidence, dict):
            errors.append(f"{label}: evidence[{index}] must be an object")
            continue
        start, end = evidence.get("start_line"), evidence.get("end_line")
        if not isinstance(evidence.get("file"), str) or not evidence["file"].strip():
            errors.append(f"{label}: evidence[{index}] requires a file")
        if type(start) is not int or type(end) is not int or start < 1 or end < start:
            errors.append(f"{label}: evidence[{index}] requires a positive ordered line range")
    return errors

def validate_review_fields(item: dict, label: str) -> list[str]:
    errors = []
    if not isinstance(item.get("review_type"), str) or item["review_type"] not in REVIEW_TYPES:
        errors.append(f"{label}: invalid review_type")
    for field in REVIEW_TEXT_FIELDS:
        if not isinstance(item.get(field), str) or not item[field].strip():
            errors.append(f"{label}: {field} must be non-empty text (explain unknown or not applicable)")
    questions = item.get("missing_context")
    if not isinstance(questions, list):
        errors.append(f"{label}: missing_context must be a list")
    else:
        for question in questions:
            if not isinstance(question, dict) or any(not isinstance(question.get(k), str) or not question[k].strip() for k in ("question", "required_evidence")):
                errors.append(f"{label}: context questions require question and required_evidence")
    return errors


def validate_hypotheses(data):
    errors = _validate_hypotheses(data)
    if not isinstance(data, dict) or not isinstance(data.get("hypotheses"), list):
        return errors
    seen = set()
    for item in data["hypotheses"]:
        if not isinstance(item, dict): continue
        ident = item.get("id")
        if not isinstance(ident, str) or not re.fullmatch(r"KAI-\d{2}-\d{3}", ident) or ident in seen:
            errors.append("Candidate ids must be unique KAI-NN-NNN strings")
        elif type(data.get("agent_id")) is not int or not ident.startswith(f"KAI-{data['agent_id']:02d}-"):
            errors.append("Hypothesis id must match assigned agent")
        if isinstance(ident,str): seen.add(ident)
        for key in ("title", "claim", "category", "why_might_be_real", "why_might_be_false_positive"):
            if not isinstance(item.get(key), str) or not item[key].strip(): errors.append(key+" must be nonempty text")
        steps=item.get("next_validation_steps")
        if not isinstance(steps,list) or not steps or any(not isinstance(step,str) or not step.strip() for step in steps):
            errors.append("next_validation_steps requires actionable text")
        refs=item.get("jay_refs", {})
        if isinstance(refs,dict):
            for key in ("node_ids", "edge_ids"):
                if isinstance(refs.get(key),list) and any(not isinstance(ref,str) for ref in refs[key]): errors.append("Jay ids must be strings")
    return errors
