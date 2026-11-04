"""Both runtime handoffs with explicit parent decisions; no inference is mocked."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

import test_anchor_audit as anchor
import test_cole_varify as solidity
from dedup_fixture import complete_dedup

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(path.read_text())


def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


@contextmanager
def scenario(runtime, duplicate_changes=None, empty=False):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        if runtime == "anchor":
            project = root / "project"
            project.mkdir()
            anchor.fixture(project)
            run, manifest = anchor.completed_run(project)
            base = anchor.hypothesis(load(run / "jay-logic.json"))
            script = anchor.COLE
            out = project / "MasterWu/Anchor/Cole/runs" / run.name
            extra_file = "programs/vault/src/state.rs"
        else:
            project = solidity.create_project(root)
            run = solidity.create_kai_run(project)
            manifest = load(run / "spawn-manifest.json")
            base = anchor.hypothesis({"nodes": [{"id": "withdraw", "file": "src/Vault.sol",
                                    "start_line": 1, "end_line": 2, "metadata": {"entry_point": True}}]})
            script = ROOT / "skills/cole-varify/scripts/cole_varify.py"
            out = project / "MasterWu/cole/runs" / run.name
            extra_file = "src/OwnerCheck.sol"
            (project / extra_file).write_text("library OwnerCheck {}\n")
        first = {**base, "title": "Missing vault ownership binding", "claim": "withdraw never binds vault.owner to caller.",
                 "recommendation": "Check vault.owner == caller in the shared withdrawal guard.",
                 "missing_context": [{"question": "Is the guard active?", "required_evidence": "Deployed guard configuration."}],
                 "evidence": [{**base["evidence"][0], "snippet": "withdraw(ctx)"}]}
        duplicate = {**copy.deepcopy(first), "title": "Caller can select another user's vault",
                     "claim": "Any signer reaches another owner's funds because owner binding is missing.",
                     "category": "flow-gap", "confidence": "high",
                     "recommendation": "Enforce the same caller-to-vault relation before debiting funds.",
                     "why_might_be_false_positive": "An independently configured shared guard may bind the owner.",
                     "evidence": first["evidence"] + [{"file": extra_file, "start_line": 1, "end_line": 1}]}
        if duplicate_changes:
            duplicate.update(duplicate_changes(first, extra_file))
        independent = {**copy.deepcopy(base), "title": "Fee settlement uses a mutable rate",
                       "claim": "withdraw recomputes accepted fees from the current rate."}
        condition = {**copy.deepcopy(first), "title": "Replay of an already consumed withdrawal request",
                     "claim": "The same withdraw instruction fails to bind the request consumption state.",
                     "scenario": "An otherwise authorized owner replays a consumed request."}
        trust = {**copy.deepcopy(first), "title": "Trusted owner can redirect vault ownership", "review_type": "trust-risk",
                 "claim": "A trusted vault owner can reassign ownership without independent approval.",
                 "scenario": "An authorized vault owner changes ownership through a management instruction.",
                 "existing_controls": "The ownership-manager role gates this operation.",
                 "recommendation": "Require independent approval for trusted ownership reassignment.",
                 "missing_context": []}
        for idx, entry in enumerate(manifest["agents"]):
            path = Path(entry["hypotheses_path"])
            data = load(path)
            data["schema_version"] = "2.0.0"
            items = [first, independent, condition] if idx == 0 else [duplicate, trust] if idx == 1 else []
            data["hypotheses"] = [] if empty else [
                {**item, "id": f"KAI-{entry['agent_id']:02d}-{j:03d}"} for j, item in enumerate(items, 1)]
            save(path, data)
        proc = anchor.cli(script, "collect", project, "--run", run)
        if proc.returncode:
            raise AssertionError(proc.stderr)
        yield project, run, manifest, script, out


class SemanticDedupTests(unittest.TestCase):
    def test_parent_review_of_mixed_claims(self):
        # Parent-authored review of the full synthetic records: semantic handoff
        # acceptance, not evidence these claims exist in a deployed program.
        reviews = [
            ([0, 3], "Missing vault ownership binding", "withdraw never binds vault.owner to caller.",
             "One missing caller-to-vault ownership constraint in the withdrawal guard.",
             "Both describe the same unauthorized caller selecting another owner's vault. The wording, category and extra evidence differ; one ownership guard repairs both. Retain the shared-guard uncertainty and both recommendations."),
            ([1], "Fee settlement uses a mutable rate", "withdraw recomputes accepted fees from the current rate.",
             "Settlement reads mutable fee configuration instead of request-time terms.",
             "This is independent of ownership and replay checks: even an authorized first withdrawal is affected. Snapshotting accepted fee terms is a separate repair."),
            ([2], "Replay of an already consumed withdrawal request", "withdraw fails to bind request consumption state.",
             "Missing consumed-request state guard in withdrawal.",
             "Although it shares the entry point, it requires an authorized owner replaying a consumed request. Ownership binding does not repair this lifecycle defect."),
            ([4], "Trusted owner can redirect vault ownership", "Trusted authority can redirect ownership without the proposed protection.",
             "A proposed protection for a trusted ownership-management operation.",
             "The actor already has authority and this source is a trust-risk. Preserve it separately from the vulnerability group and leave validity to Cole."),
        ]
        for runtime in ("solidity", "anchor"):
            with self.subTest(runtime=runtime), scenario(runtime) as (_, _, _, script, out):
                raw = load(out / "raw-candidates.json")
                decisions = load(out / "dedup-decisions.json")
                decisions.update(review_status="complete", groups=[
                    dict(member_ids=[raw["raw_candidates"][i]["source_id"] for i in members],
                         title=title, claim=claim, root_cause=cause, rationale=reason)
                    for members, title, claim, cause, reason in reviews])
                save(out / "dedup-decisions.json", decisions)
                proc = anchor.cli(script, "apply-dedup", out / "raw-candidates.json", "--decisions", out / "dedup-decisions.json")
                self.assertEqual(0, proc.returncode, proc.stderr)
                self.assertEqual(4, load(out / "candidates.json")["candidate_count"])
                self.assertEqual(0, anchor.cli(script, "prepare-judges", out / "candidates.json").returncode)
                self.assertEqual(4, len(load(out / "judges/manifest.json")["judges"]))

    def test_semantic_partition_preserves_full_provenance_and_dispatches_one_per_group(self):
        for runtime in ("solidity", "anchor"):
            with self.subTest(runtime=runtime), scenario(runtime) as (_, _, _, script, out):
                raw = load(out / "raw-candidates.json")
                self.assertEqual(5, len(raw["raw_candidates"]))
                self.assertFalse((out / "candidates.json").exists())
                self.assertEqual("needs_review", load(out / "dedup-decisions.json")["review_status"])
                result = complete_dedup(script, out, [[0, 3], [1], [2], [4]])
                self.assertEqual((5, 4), (result["source_hypothesis_count"], result["candidate_count"]))
                self.assertEqual(0.2, result["dedup_stats"]["reduction_ratio"])
                merged = next(c for c in result["candidates"] if len(c["member_ids"]) == 2)
                self.assertEqual("high", merged["confidence"])
                self.assertEqual([raw["raw_candidates"][i] for i in (0, 3)], merged["source_records"])
                self.assertEqual(2, len(merged["source_hypotheses"]))
                self.assertEqual(2, len(merged["review_details"]))
                self.assertTrue(merged["missing_context"])
                self.assertEqual(2, len(merged["evidence"]))
                proc = anchor.cli(script, "prepare-judges", out / "candidates.json")
                self.assertEqual(0, proc.returncode, proc.stderr)
                judges = load(out / "judges/manifest.json")
                self.assertEqual(4, len(judges["judges"]))
                bundle = Path(next(j for j in judges["judges"] if j["candidate_id"] == merged["id"])["bundle_path"]).read_text()
                for record in merged["source_records"]:
                    self.assertIn(record["hypothesis"]["claim"], bundle)
                    self.assertIn(record["hypothesis"]["why_might_be_false_positive"], bundle)
                self.assertIn("withdraw(ctx)", bundle)
                self.assertIn("reduced by 1 (20.0%)", (out / "wreport.md").read_text())

    def test_each_text_difference_can_be_grouped(self):
        variations = {
            "title": lambda original, _: {**copy.deepcopy(original), "title": "An alternate ownership title"},
            "claim": lambda original, _: {**copy.deepcopy(original), "claim": "The caller-to-vault relation is not enforced."},
            "category": lambda original, _: {**copy.deepcopy(original), "category": "execution-trace"},
            "files": lambda original, file: {**copy.deepcopy(original), "evidence": original["evidence"] + [dict(file=file, start_line=1, end_line=1)]},
        }
        for runtime in ("solidity", "anchor"):
            for label, change in variations.items():
                with self.subTest(runtime=runtime, difference=label), scenario(runtime, change) as (_, _, _, script, out):
                    result = complete_dedup(script, out, [[0, 3], [1], [2], [4]])
                    self.assertEqual(4, result["candidate_count"])
                    self.assertEqual(1, sum(len(c["member_ids"]) == 2 for c in result["candidates"]))

    def test_uncertain_duplicates_are_retained_as_separate_groups(self):
        for runtime in ("solidity", "anchor"):
            with self.subTest(runtime=runtime), scenario(runtime) as (_, _, _, script, out):
                complete_dedup(script, out)
                decisions = load(out / "dedup-decisions.json")
                for i in (0, 3):
                    decisions["groups"][i]["rationale"] = (
                        "Ownership claims are related, but available evidence cannot establish whether "
                        "one shared guard or independent configured guards repair both. Retain separately "
                        "until this semantic relationship is established; do not drop either source.")
                save(out / "dedup-decisions.json", decisions)
                proc = anchor.cli(script, "apply-dedup", out / "raw-candidates.json", "--decisions", out / "dedup-decisions.json")
                self.assertEqual(0, proc.returncode, proc.stderr)
                result = load(out / "candidates.json")
                self.assertEqual(5, result["candidate_count"])
                self.assertTrue(all(len(c["source_records"]) == 1 for c in result["candidates"]))
                self.assertEqual(0, anchor.cli(script, "prepare-judges", out / "candidates.json").returncode)
                self.assertEqual(5, len(load(out / "judges/manifest.json")["judges"]))

    def test_invalid_decisions_preserve_good_outputs(self):
        for runtime in ("solidity", "anchor"):
            with self.subTest(runtime=runtime), scenario(runtime) as (_, _, _, script, out):
                complete_dedup(script, out, [[0, 3], [1], [2], [4]])
                good = load(out / "dedup-decisions.json")
                before = {name: (out / name).read_bytes() for name in ("candidates.json", "dedup-record.json", "wreport.md")}
                def invalid(mutator):
                    bad = copy.deepcopy(good)
                    mutator(bad)
                    save(out / "dedup-decisions.json", bad)
                    proc = anchor.cli(script, "apply-dedup", out / "raw-candidates.json", "--decisions", out / "dedup-decisions.json")
                    self.assertNotEqual(0, proc.returncode)
                    for name, content in before.items():
                        self.assertEqual(content, (out / name).read_bytes())
                invalid(lambda d: d["groups"].pop())
                invalid(lambda d: d["groups"].append(copy.deepcopy(d["groups"][0])))
                invalid(lambda d: d["groups"][0]["member_ids"].append("unknown-member"))
                invalid(lambda d: d.update(input_digest="stale"))
                invalid(lambda d: d.update(review_status="needs_review"))
                invalid(lambda d: d["groups"][0].update(rationale=""))
                invalid(lambda d: d["groups"][0].update(severity="High"))
                # A complete partition is still rejected if it mixes review types.
                def cross_type(d):
                    d["groups"][0]["member_ids"].extend(d["groups"].pop()["member_ids"])
                invalid(cross_type)
                invalid(lambda d: d.update(groups=None))
                save(out / "dedup-decisions.json", good)
                self.assertEqual(0, anchor.cli(script, "apply-dedup", out / "raw-candidates.json", "--decisions", out / "dedup-decisions.json").returncode)

    def test_input_changes_and_duplicate_identity_block_apply(self):
        for runtime in ("solidity", "anchor"):
            with self.subTest(runtime=runtime), scenario(runtime) as (project, run, manifest, script, out):
                complete_dedup(script, out)
                old = (out / "candidates.json").read_bytes()
                entry = manifest["agents"][0]
                path = Path(entry["hypotheses_path"])
                original = path.read_bytes()
                data = load(path)
                data["hypotheses"][0]["claim"] += " changed evidence"
                save(path, data)
                proc = anchor.cli(script, "apply-dedup", out / "raw-candidates.json", "--decisions", out / "dedup-decisions.json")
                self.assertNotEqual(0, proc.returncode)
                self.assertEqual(old, (out / "candidates.json").read_bytes())
                data["hypotheses"].append(copy.deepcopy(data["hypotheses"][0]))
                save(path, data)
                self.assertNotEqual(0, anchor.cli(script, "collect", project, "--run", run).returncode)
                path.write_bytes(original)
                # Source snapshot/content changes invalidate the grouping too.
                source = run / "source.md" if runtime == "anchor" else project / "src/Vault.sol"
                source.write_text(source.read_text() + "\n// changed source\n")
                self.assertNotEqual(0, anchor.cli(script, "apply-dedup", out / "raw-candidates.json", "--decisions", out / "dedup-decisions.json").returncode)

    def test_dispatch_gate_and_legacy_opt_in(self):
        for runtime in ("solidity", "anchor"):
            with self.subTest(runtime=runtime), scenario(runtime) as (_, _, _, script, out):
                raw = load(out / "raw-candidates.json")
                # A template cannot be marked complete without accounting for all sources.
                template = load(out / "dedup-decisions.json")
                template["review_status"] = "complete"
                save(out / "dedup-decisions.json", template)
                self.assertNotEqual(0, anchor.cli(script, "apply-dedup", out / "raw-candidates.json", "--decisions", out / "dedup-decisions.json").returncode)
                result = complete_dedup(script, out)
                legacy = {k: v for k, v in result.items() if k not in ("deduplication", "dedup_stats")}
                save(out / "candidates.json", legacy)
                path = out / "candidates.json"
                self.assertNotEqual(0, anchor.cli(script, "prepare-judges", path).returncode)
                self.assertFalse((out / "judges").exists())
                proc = anchor.cli(script, "prepare-judges", path, "--allow-legacy-candidates")
                self.assertEqual(0, proc.returncode, proc.stderr)
                self.assertIn("was not performed", proc.stderr)
                self.assertEqual("not-performed", load(out / "judges/manifest.json")["deduplication"]["status"])
                save(path, {**result, "deduplication": {"status": "needs_review"}})
                self.assertNotEqual(0, anchor.cli(script, "prepare-judges", path, "--allow-legacy-candidates").returncode)
                self.assertEqual(len(raw["raw_candidates"]), len(result["candidates"]))

    def test_custom_dispatch_locks_grouping_and_binds_candidate_contents(self):
        for runtime in ("solidity", "anchor"):
            with self.subTest(runtime=runtime), scenario(runtime) as (project, run, manifest, script, out):
                result = complete_dedup(script, out, [[0, 3], [1], [2], [4]])
                path = out / "candidates.json"
                custom = project / "custom-judges"
                self.assertEqual(0, anchor.cli(script, "prepare-judges", path, "--out", custom).returncode)
                before = (out / "wreport.md").read_bytes()
                decisions = load(out / "dedup-decisions.json")
                changed = copy.deepcopy(decisions)
                changed["groups"][0]["claim"] += " modified after dispatch"
                save(out / "dedup-decisions.json", changed)
                self.assertNotEqual(0, anchor.cli(script, "apply-dedup", out / "raw-candidates.json", "--decisions", out / "dedup-decisions.json").returncode)
                self.assertEqual(before, (out / "wreport.md").read_bytes())
                save(out / "dedup-decisions.json", decisions)
                self.assertEqual(0, anchor.cli(script, "apply-dedup", out / "raw-candidates.json", "--decisions", out / "dedup-decisions.json").returncode)
                save(out / "preflight.json", {"status": "skipped-local-build"})
                self.assertEqual(0, anchor.cli(script, "prepare-judges", path, "--out", custom).returncode)
                self.assertEqual(result, load(path))
                dispatch_manifest = load(custom / "manifest.json")
                without_digest = copy.deepcopy(dispatch_manifest)
                without_digest.pop("candidates_digest")
                save(custom / "manifest.json", without_digest)
                self.assertNotEqual(0, anchor.cli(script, "validate-judges", custom / "manifest.json").returncode)
                save(custom / "manifest.json", dispatch_manifest)
                bad = copy.deepcopy(result)
                bad["candidates"][0]["source_records"][0]["hypothesis"]["claim"] = "tampered source record"
                save(path, bad)
                self.assertNotEqual(0, anchor.cli(script, "apply-judges", path, "--manifest", custom / "manifest.json").returncode)
                self.assertNotEqual(0, anchor.cli(script, "validate-judges", custom / "manifest.json").returncode)
                save(path, result)
                data_path = Path(manifest["agents"][0]["hypotheses_path"])
                data = load(data_path)
                data["hypotheses"][0]["claim"] += " new research"
                save(data_path, data)
                self.assertNotEqual(0, anchor.cli(script, "collect", project, "--run", run).returncode)

    def test_empty_run_and_idempotent_recollection(self):
        for runtime in ("solidity", "anchor"):
            with self.subTest(runtime=runtime), scenario(runtime, empty=True) as (project, run, _, script, out):
                result = load(out / "candidates.json")
                self.assertEqual([], result["candidates"])
                self.assertEqual(0, result["dedup_stats"]["reduction_ratio"])
                self.assertEqual(0, anchor.cli(script, "prepare-judges", out / "candidates.json").returncode)
                self.assertEqual([], load(out / "judges/manifest.json")["judges"])
                self.assertEqual(0, anchor.cli(script, "apply-judges", out / "candidates.json").returncode)
                report = (out / "wreport.md").read_bytes()
                self.assertEqual(0, anchor.cli(script, "collect", project, "--run", run).returncode)
                self.assertEqual(report, (out / "wreport.md").read_bytes())
            with self.subTest(runtime=runtime, repeat="nonempty"), scenario(runtime) as (project, run, _, script, out):
                complete_dedup(script, out)
                decisions = (out / "dedup-decisions.json").read_bytes()
                self.assertEqual(0, anchor.cli(script, "collect", project, "--run", run).returncode)
                self.assertEqual(decisions, (out / "dedup-decisions.json").read_bytes())

    def test_standalone_installed_cole_handoff_in_codex_and_claude(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for runtime, skill in (("solidity", "cole-varify"), ("anchor", "anchor-cole")):
                env = {**os.environ, "MASTERWU_CODEX_SKILLS_DIR": str(root / "codex"),
                       "MASTERWU_CLAUDE_SKILLS_DIR": str(root / "claude")}
                proc = subprocess.run([str(ROOT / "scripts/install.sh"), "all", skill], env=env, capture_output=True, text=True)
                self.assertEqual(0, proc.returncode, proc.stderr)
                for target in ("codex", "claude"):
                    installed = root / target / skill / "scripts" / ("anchor_cole.py" if runtime == "anchor" else "cole_varify.py")
                    with self.subTest(runtime=runtime, target=target), scenario(runtime) as (project, run, _, _, out):
                        proc = anchor.cli(installed, "collect", project, "--run", run)
                        self.assertEqual(0, proc.returncode, proc.stderr)
                        result = complete_dedup(installed, out, [[0, 3], [1], [2], [4]])
                        proc = anchor.cli(installed, "prepare-judges", out / "candidates.json")
                        self.assertEqual(0, proc.returncode, proc.stderr)
                        self.assertEqual(result["candidate_count"], len(load(out / "judges/manifest.json")["judges"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
