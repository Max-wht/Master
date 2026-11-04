"""Explicit synthetic parent decisions for CLI contract tests, not AI recall tests."""
import json
import subprocess
import sys
from pathlib import Path


def complete_dedup(script: Path, out: Path, member_groups=None) -> dict:
    raw = json.loads((out / "raw-candidates.json").read_text())
    records = raw["raw_candidates"]
    if member_groups is None:
        member_groups = [[i] for i in range(len(records))]
    decisions = json.loads((out / "dedup-decisions.json").read_text())
    decisions["review_status"] = "complete"
    decisions["groups"] = [
        {"member_ids": [records[i]["source_id"] for i in indices],
         "title": records[indices[0]]["hypothesis"]["title"],
         "claim": records[indices[0]]["hypothesis"]["claim"],
         "root_cause": "Synthetic root cause for this contract scenario.",
         "rationale": "The scenario explicitly prescribes these equivalence groups; this is not an AI decision."}
        for indices in member_groups
    ]
    path = out / "dedup-decisions.json"
    path.write_text(json.dumps(decisions, indent=2))
    result = subprocess.run([sys.executable, str(script), "apply-dedup", str(out / "raw-candidates.json"),
                             "--decisions", str(path)], capture_output=True, text=True)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads((out / "candidates.json").read_text())
