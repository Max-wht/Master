#!/usr/bin/env python3
"""Contract/source regressions; synthetic AI records do not establish audit recall."""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
JAY = ROOT / "skills/anchor-jay/scripts/anchor_jay.py"
KAI = ROOT / "skills/anchor-kai/scripts/anchor_kai.py"
COLE = ROOT / "skills/anchor-cole/scripts/anchor_cole.py"


def module(name, path):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


jay, kai, cole = module("anchor_jay_test", JAY), module("anchor_kai_test", KAI), module("anchor_cole_test", COLE)


def load(path):
    return json.loads(path.read_text())


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def cli(script, *args, env=None):
    return subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True, env=env)


def fixture(root):
    shutil.copytree(ROOT / "tests/fixtures/anchor-defi", root, dirs_exist_ok=True)


def reviewed_map(root, script=JAY):
    result = cli(script, "build", root)
    if result.returncode:
        raise AssertionError(result.stderr)
    out = root / jay.DEFAULT_OUT
    graph = load(out / "jay-logic.json")
    fn = next(n for n in graph["nodes"] if n["metadata"].get("entry_point"))
    audit = load(out / "audit-map.json")
    audit.update(review_status="complete", completion_notes="Synthetic semantic fixture for CLI contract testing, not an audit verdict.", semantics=[{
        "kind": "protocol-summary", "provenance": "source-fact", "description": "A deposit instruction updates account totals.", "node_ids": [fn["id"]],
        "evidence": [{"file": fn["file"], "start_line": fn["start_line"], "end_line": fn["end_line"]}]}])
    write(out / "audit-map.json", audit)
    return graph, audit


def completed_run(root, script=KAI):
    reviewed_map(root)
    proc = cli(script, "prepare", root, "--run-id", "regression")
    if proc.returncode:
        raise AssertionError(proc.stderr)
    run = root / "MasterWu/Anchor/Kai/runs/regression"
    manifest = load(run / "spawn-manifest.json")
    for agent in manifest["agents"]:
        Path(agent["report_path"]).write_text("# Completed synthetic research fixture\n")
    return run, manifest


def hypothesis(graph, ident="KAI-02-001", kind="vulnerability"):
    fn = next(n for n in graph["nodes"] if n["metadata"].get("entry_point"))
    return {"id": ident, "title": "Synthetic authority relation claim", "claim": "The claimed account relationship needs review.", "category": "authority", "confidence": "medium",
            "review_type": kind, "scenario": "A user supplies an account to a withdrawal instruction.", "applicability": "The supplied account affects recorded funds.", "existing_controls": "Typed owner and explicit signer checks are present.",
            "recommendation": "Verify and enforce the intended account relation.", "tradeoffs": "Additional validation may restrict supported account layouts.", "missing_context": [],
            "evidence": [{"file": fn["file"], "start_line": fn["start_line"], "end_line": fn["end_line"]}], "jay_refs": {"node_ids": [fn["id"]], "edge_ids": []},
            "why_might_be_real": "A specific authority relation could be missing.", "why_might_be_false_positive": "Typed or manual checks may supply it.", "next_validation_steps": ["Trace all account checks and the asset effect."]}


def judge(candidate, pending=False):
    record = {key: candidate[key] for key in ("review_type", "scenario", "applicability", "existing_controls", "recommendation", "tradeoffs")}
    record.update(schema_version="2.0.0", candidate_id=candidate["id"], review_status="needs_context" if pending else "complete", title=candidate["title"], finding_summary="Synthetic review output for merge/resume contract tests.", missing_context=[], poc=cole.empty_poc())
    if pending:
        record["missing_context"] = [{"question": "Which deployed controller constrains this authority?", "required_evidence": "Controller source/address and audited slot."}]
    else:
        classification = "High" if record["review_type"] == "vulnerability" else "Info"
        record.update(classification=classification, verdict=classification, required_conditions=[{"condition": "The synthetic fixture supplies a known actor.", "status": "true", "evidence": "Synthetic source trace."}],
                      reachability="Synthetic reachable path.", code_reality="Synthetic source description.", protocol_semantics="Synthetic affected property.", impact="Synthetic validation-only impact.")
    return record


class JayTests(unittest.TestCase):
    def test_large_source_coordinates_do_not_corrupt_ast(self):
        # Run in a child process: the old Point attribute getters corrupt the
        # native heap once coordinates exceed CPython's small-integer cache.
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); fixture(root)
            for source in root.rglob("*.rs"):
                text = source.read_text()
                if source.name == "accounts.rs":
                    text = text.replace("    pub vault:", " " * 320 + "pub vault:")
                source.write_text("\n" * 320 + text)
            proc = cli(JAY, "build", root)
            self.assertEqual(0, proc.returncode, proc.stderr)
            graph = load(root / jay.DEFAULT_OUT / "jay-logic.json")
            vault = next(n for n in graph["nodes"] if n["name"] == "vault" and n["metadata"].get("context") == "Deposit" and n["metadata"]["crate"] == "vault")
            self.assertGreater(vault["start_line"], 320)
            self.assertEqual(["mut", "seeds", "bump", "has_one", "constraint", "owner"], [c["key"] for c in vault["metadata"]["constraints"]])
            self.assertTrue(any(e["type"] == "calls" and "math::credit" in e["label"] for e in graph["edges"]))
            self.assertEqual([], jay.validate_graph(graph))

    def test_default_scope_skips_binary_anchor_clients(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); fixture(root)
            client = root / "clients/deploy"
            (client / "src").mkdir(parents=True)
            (client / "Cargo.toml").write_text('[package]\nname = "deploy"\nversion = "0.1.0"\nedition = "2021"\n[dependencies]\nanchor-lang = { workspace = true }\n')
            (client / "src/main.rs").write_text("fn main() {}\n")
            manifest = root / "Cargo.toml"
            manifest.write_text(manifest.read_text().replace('"crates/accounting"]', '"crates/accounting", "clients/deploy"]'))
            proc = cli(JAY, "build", root)
            self.assertEqual(0, proc.returncode, proc.stderr)
            graph = load(root / jay.DEFAULT_OUT / "jay-logic.json")
            self.assertTrue(any(n["metadata"].get("entry_point") for n in graph["nodes"]))
            self.assertFalse(any(p.startswith("clients/deploy/") for p in graph["metadata"]["source_files"]))

    def test_multifile_constraints_types_and_helpers(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); fixture(root)
            graph, _ = reviewed_map(root)
            fields = [n for n in graph["nodes"] if n["metadata"].get("kind") == "account_field"]
            vault = next(n for n in fields if n["metadata"]["wrapper"] == "Account" and n["metadata"]["account_type"].startswith("Box"))
            constraints = vault["metadata"]["constraints"]
            self.assertEqual(["mut", "seeds", "bump", "has_one", "constraint", "owner"], [c["key"] for c in constraints])
            self.assertIn('b"vault,domain"', constraints[1]["expression"])
            self.assertIn("<", constraints[4]["expression"])
            self.assertGreater(constraints[0]["end_line"], constraints[0]["start_line"])
            self.assertTrue(vault["metadata"]["implicit_checks"])
            unchecked = next(n for n in fields if n["name"] == "user" and n["metadata"]["wrapper"] == "UncheckedAccount")
            self.assertEqual([], unchecked["metadata"]["implicit_checks"])
            self.assertTrue(any(n["metadata"].get("wrapper") == "InterfaceAccount" for n in fields))
            functions = [n for n in graph["nodes"] if n["type"] == "function"]
            self.assertEqual(2, len([n for n in functions if n["name"] == "deposit" and n["metadata"].get("entry_point")]))
            self.assertTrue(any(n["name"] == "credit" and n["metadata"]["crate"] == "accounting" for n in functions))
            self.assertTrue(any(e["type"] == "calls" and "math::credit" in e["label"] for e in graph["edges"]))
            self.assertTrue(any(e["type"] == "writes" and "v.total" in e["label"] for e in graph["edges"]))
            self.assertFalse(any(g["kind"] == "unresolved-context" for g in graph["metadata"]["coverage_gaps"]))
            self.assertTrue(any(g["kind"] == "custom-macro" for g in graph["metadata"]["coverage_gaps"]))
            self.assertTrue(any(g["kind"] == "conditional-compilation" for g in graph["metadata"]["coverage_gaps"]))
            crate = next(c for c in graph["metadata"]["crates"] if c["name"] == "vault")
            self.assertIn("init-if-needed", crate["dependencies"]["anchor-lang"]["features"])
            self.assertEqual(["0.32.1"], crate["locked_versions"]["anchor-lang"])
            for edge in graph["edges"]:
                if edge["type"] == "guards" and edge["label"].startswith("#[account"):
                    declaration = next(n for n in graph["nodes"] if n["id"] == edge["to"])
                    self.assertEqual(declaration["file"], edge["file"])
                    self.assertEqual(declaration["start_line"], edge["start_line"])
            self.assertEqual([], jay.validate_graph(graph))

    def test_stability_stale_map_and_invalid_references(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw); fixture(root)
            graph, audit=reviewed_map(root)
            self.assertEqual(0, cli(JAY, "build", root).returncode)
            self.assertEqual(audit, load(root / jay.DEFAULT_OUT / "audit-map.json"))
            rebuilt=load(root / jay.DEFAULT_OUT / "jay-logic.json")
            self.assertEqual(graph["nodes"], rebuilt["nodes"])
            self.assertEqual(graph["edges"], rebuilt["edges"])
            bad=copy.deepcopy(audit); bad["semantics"][0]["node_ids"]=["unknown"]
            self.assertTrue(jay.validate_audit_map(bad, graph))
            (root / "programs/vault/src/lib.rs").write_text((root / "programs/vault/src/lib.rs").read_text()+"\npub fn changed() {}\n")
            self.assertTrue(jay.validate_graph(graph))
            self.assertEqual(0, cli(JAY, "build", root).returncode)
            self.assertTrue((root / jay.DEFAULT_OUT / "audit-map.previous.json").is_file())
            self.assertNotEqual(0, cli(JAY, "validate", root / jay.DEFAULT_OUT / "jay-logic.json", "--require-semantics").returncode)

    def test_explicit_scope_and_native_rejection(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw); fixture(root)
            unrelated = root / "crates/unrelated"
            (unrelated / "src").mkdir(parents=True)
            (unrelated / "Cargo.toml").write_text('[package]\nname = "unrelated"\nversion = "0.1.0"\n')
            (unrelated / "src/lib.rs").write_text("pub fn unrelated_helper() {}\n")
            other = root / "programs/other/Cargo.toml"
            other.write_text(other.read_text() + '\nunrelated = { path = "../../crates/unrelated" }\n')
            proc=cli(JAY, "build", root, "--files", "programs/vault/src/lib.rs")
            self.assertEqual(0, proc.returncode, proc.stderr)
            graph=load(root / jay.DEFAULT_OUT / "jay-logic.json")
            self.assertIn("crates/accounting/src/lib.rs", graph["metadata"]["source_files"])
            self.assertFalse(any("programs/other" in p for p in graph["metadata"]["source_files"]))
            self.assertNotIn("crates/unrelated/src/lib.rs", graph["metadata"]["source_files"])
            self.assertNotEqual(0, cli(JAY, "build", root, "--files", "/tmp/outside.rs").returncode)
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw); (root / "lib.rs").write_text("pub fn process_instruction() {}")
            self.assertNotEqual(0, cli(JAY, "build", root, "--files", "lib.rs").returncode)

    def test_configuration_freshness_and_scoped_wildcard_helpers(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);fixture(root)
            path=root / "programs/vault/src/lib.rs"
            path.write_text(path.read_text().replace("mod state;", "mod state;\nmod handlers;").replace("math::credit(&mut v.total, amount);", "math::credit(&mut v.total, amount);\n        handlers::update(v, amount);"))
            (path.parent / "handlers.rs").write_text("use crate::state::Vault;\npub fn update(v: &mut Vault, amount:u64) { v.total += amount; }\n")
            graph,_=reviewed_map(root)
            self.assertTrue(any(e["type"]=="calls" and "handlers::update" in e["label"] for e in graph["edges"]))
            self.assertFalse(any(g["detail"]=="handlers::update" for g in graph["metadata"]["coverage_gaps"]))
            manifest=root / "Cargo.toml"
            manifest.write_text(manifest.read_text().replace("0.32.1","0.30.1"))
            (root / "Cargo.lock").write_text((root / "Cargo.lock").read_text().replace("0.32.1","0.30.1"))
            self.assertTrue(jay.validate_graph(graph))
            result=cli(KAI,"prepare",root,"--run-id","stale-config")
            self.assertNotEqual(0,result.returncode)
            self.assertIn("configuration changed",result.stderr)
            self.assertEqual(0,cli(JAY,"build",root).returncode)
            self.assertEqual("needs_ai_review",load(root / jay.DEFAULT_OUT / "audit-map.json")["review_status"])

    def test_cpi_lifecycle_and_manual_guard(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw); fixture(root)
            path=root / "programs/vault/src/lib.rs"
            source=path.read_text().replace("math::credit(&mut v.total, amount);", '''math::credit(&mut v.total, amount);
        let cpi = CpiContext::new_with_signer(ctx.accounts.token_program.to_account_info(), transfer, seeds);
        token_interface::transfer_checked(cpi, amount, 6)?;
        **ctx.accounts.source.try_borrow_mut_lamports()? -= amount;
        ctx.accounts.source.reload()?;
        invoke_signed(&instruction, infos, seeds)?;
        if amount == 0 { return Err(error); }
        custom_check(ctx)?;''')
            path.write_text(source)
            graph, _=reviewed_map(root)
            self.assertTrue(any(n["metadata"].get("kind") == "cpi_context" and n["metadata"].get("signer_seeds") == "seeds" for n in graph["nodes"]))
            self.assertTrue(any(e["type"] == "transfers_value" for e in graph["edges"]))
            self.assertTrue(any(e["type"] == "transfers_value" and "try_borrow_mut_lamports" in e["label"] for e in graph["edges"]))
            self.assertTrue(any(n["metadata"].get("kind") == "manual_guard" and "error-branch" in n["name"] for n in graph["nodes"]))
            self.assertTrue(any(g["kind"] == "unresolved-call" and g["detail"] == "custom_check" for g in graph["metadata"]["coverage_gaps"]))
            self.assertFalse(any(g["detail"].startswith("CpiContext::") for g in graph["metadata"]["coverage_gaps"]))


class KaiTests(unittest.TestCase):
    def test_review_gate_and_snapshots_without_toolchain(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw); fixture(root)
            env={**os.environ, "PATH":""}
            proc=cli(KAI, "prepare", root, "--run-id", "pending", env=env)
            self.assertNotEqual(0, proc.returncode)
            self.assertFalse((root / "MasterWu/Anchor/Kai/runs/pending").exists())
            graph,audit=reviewed_map(root)
            (root / "context.md").write_text("Client-stated multisig custody; verify it.")
            proc=cli(KAI, "prepare", root, "--run-id", "complete", "--context", "context.md", env=env)
            self.assertEqual(0, proc.returncode, proc.stderr)
            run=root / "MasterWu/Anchor/Kai/runs/complete"
            manifest=load(run / "spawn-manifest.json")
            self.assertEqual(12,len(manifest["agents"]))
            self.assertEqual(audit,load(run / "audit-map.json"))
            self.assertIn("Cargo.lock",manifest["audit_context"]["supporting_files"])
            (root / "context.md").write_text("changed")
            for agent in manifest["agents"]:
                bundle=Path(agent["bundle_path"]).read_text()
                self.assertIn("Client-stated multisig",bundle)
                self.assertIn("Complete Anchor Source",bundle)
                self.assertIn("Business Map",bundle)
                self.assertIn("accounting",bundle)
            self.assertNotEqual(0,cli(KAI,"prepare",root,"--run-id","complete").returncode)
            self.assertNotEqual(0,cli(KAI,"prepare",root,"--run-id","../unsafe").returncode)

    def test_hypothesis_contract_and_no_final_verdict(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw); fixture(root)
            graph,_=reviewed_map(root)
            valid={"schema_version":"2.0.0","run_id":"r","agent_id":2,"agent_name":"identity-authority","hypotheses":[hypothesis(graph)]}
            self.assertEqual([],kai.validate_hypotheses(valid))
            for mutation in [{"severity":"High"},{"why_might_be_false_positive":""},{"next_validation_steps":[]},{"review_type":[]},{"confidence":[]}]:
                bad=copy.deepcopy(valid);bad["hypotheses"][0].update(mutation)
                self.assertTrue(kai.validate_hypotheses(bad))


class ColeTests(unittest.TestCase):
    def run_candidates(self, root):
        fixture(root); run,manifest=completed_run(root)
        graph=load(run / "jay-logic.json")
        entry=manifest["agents"][1]
        data=load(Path(entry["hypotheses_path"]))
        data["hypotheses"]=[hypothesis(graph),hypothesis(graph,"KAI-02-002","trust-risk")]
        write(Path(entry["hypotheses_path"]),data)
        proc=cli(COLE,"collect",root,"--run",run)
        self.assertEqual(0,proc.returncode,proc.stderr)
        out=root / "MasterWu/Anchor/Cole/runs/regression"
        return run,manifest,out

    def test_merge_pending_resume_and_exact_poc_provenance(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw); run,_,out=self.run_candidates(root)
            path=out / "candidates.json"
            self.assertEqual(0,cli(COLE,"prepare-judges",path).returncode)
            data=load(path); manifest=load(out / "judges/manifest.json")
            by_id={c["id"]:c for c in data["candidates"]}
            for entry in manifest["judges"]:
                c=by_id[entry["candidate_id"]]
                write(Path(entry["output_json"]),judge(c,pending=c["review_type"]=="trust-risk"))
            self.assertEqual(0,cli(COLE,"apply-judges",path).returncode)
            result=load(out / "results.json")
            self.assertEqual(1,len(result["findings"]))
            self.assertEqual(1,len(result["pending_questions"]))
            self.assertEqual([],cole.validate_results(result,data))
            report=(out / "wreport.md").read_text()
            self.assertIn("Pending Client Questions",report)
            self.assertIn("compute/rent",report)
            self.assertIn("0.32.1",report)
            pending=result["pending_questions"][0]
            entry=next(e for e in manifest["judges"] if e["candidate_id"]==pending["candidate_id"])
            write(Path(entry["output_json"]),judge(by_id[pending["candidate_id"]]))
            self.assertEqual(0,cli(COLE,"apply-judges",path).returncode)
            result=load(out / "results.json")
            self.assertEqual([],result["pending_questions"])
            self.assertEqual(2,len(result["findings"]))
            self.assertEqual(0,cli(COLE,"render-report",out / "results.json").returncode)
            poc={"path":"tests/finding-001.ts","test_command":"npm test -- finding-001","test_result":"passed","notes":"Actual run", "assertions":["vault balance decreased by amount"]}
            self.assertEqual(poc,cole.finalize_poc(poc,"finding-001","H-1"))
            bad=copy.deepcopy(result);bad["findings"][0]["poc"]=poc;bad["findings"][0]["judge"]["poc"]=poc
            self.assertTrue(cole.validate_results(bad,data))
            bad["preflight"]={"status":"passed","test_harness":{"available":True}}
            self.assertEqual([],cole.validate_results(bad,data))

    def test_stale_reports_identities_and_merge_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw); run,manifest,out=self.run_candidates(root)
            entry=manifest["agents"][1]; path=Path(entry["hypotheses_path"])
            prior=path.read_text(); data=load(path);data["agent_id"]=4;write(path,data)
            self.assertNotEqual(0,cli(COLE,"collect",root,"--run",run).returncode)
            path.write_text(prior)
            report=Path(entry["report_path"]);report.write_text(kai.PENDING_MARKER)
            self.assertNotEqual(0,cli(COLE,"collect",root,"--run",run).returncode)
            report.write_text("completed")
            (run / "source.md").write_text("tampered source snapshot")
            self.assertNotEqual(0,cli(COLE,"collect",root,"--run",run).returncode)
            candidates=out / "candidates.json"
            self.assertEqual(0,cli(COLE,"prepare-judges",candidates).returncode)
            before=(out / "wreport.md").read_text()
            self.assertNotEqual(0,cli(COLE,"apply-judges",candidates).returncode)
            self.assertEqual(before,(out / "wreport.md").read_text())

    def test_configuration_change_after_collect_blocks_review(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);run,_,out=self.run_candidates(root)
            lock=root / "Cargo.lock"
            lock.write_text(lock.read_text().replace("0.32.1","0.30.1"))
            result=cli(COLE,"collect",root,"--run",run)
            self.assertNotEqual(0,result.returncode)
            result=cli(COLE,"prepare-judges",out / "candidates.json")
            self.assertNotEqual(0,result.returncode)
            self.assertIn("Source changed",result.stderr)

    def test_preflight_block_failure_and_existing_frameworks(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);run,_,out=self.run_candidates(root)
            with patch.object(cole.shutil,"which",return_value=None):
                build=cole.detect_build(root)
                self.assertTrue(build["blocked"])
            env={**os.environ,"PATH":""}
            proc=cli(COLE,"preflight",root,"--run",run,env=env)
            self.assertEqual(2,proc.returncode,proc.stderr)
            self.assertEqual("blocked",load(out / "preflight.json")["status"])
            self.assertEqual(0,cli(COLE,"collect",root,"--run",run,env=env).returncode)
            false_command=f"'{sys.executable}' -c 'raise SystemExit(3)'"
            proc=cli(COLE,"preflight",root,"--run",run,"--build-command",false_command)
            self.assertEqual(2,proc.returncode)
            self.assertEqual("failed",load(out / "preflight.json")["status"])
            true_command=f"'{sys.executable}' -c 'pass'"
            self.assertEqual(0,cli(COLE,"preflight",root,"--run",run,"--build-command",true_command).returncode)
            preflight=load(out / "preflight.json")
            self.assertFalse(preflight["test_harness"]["available"])
            self.assertIn("validation_blocker",preflight)
            (root / "tests").mkdir();(root / "tests/vault.ts").write_text("describe('vault',()=>{});")
            (root / "Anchor.toml").write_text((root / "Anchor.toml").read_text()+'\n[scripts]\ntest = "yarn ts-mocha tests/*.ts"\n')
            self.assertEqual("anchor-ts",cole.detect_test_harness(root)["kind"])
            (root / "tests/vault.ts").unlink();(root / "tests/vault.rs").write_text("#[test] fn t() {}")
            with (root / "Cargo.toml").open("a") as f:f.write('\n[dev-dependencies]\nmollusk-svm = "0.4"\n')
            self.assertEqual("mollusk",cole.detect_test_harness(root)["kind"])

    def test_classification_gates_and_malformed_outputs(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);fixture(root);graph,_=reviewed_map(root)
            c={**hypothesis(graph),"id":"finding-001"}
            for kind in ("trust-risk","design-risk","hardening","engineering-quality"):
                record=judge({**c,"review_type":kind})
                self.assertEqual([],cole.validate_judge_result(record,"finding-001"))
                record.update(classification="Medium",verdict="Medium")
                self.assertTrue(cole.validate_judge_result(record,"finding-001"))
            record=judge(c,True);record["classification"]=None
            self.assertTrue(cole.validate_judge_result(record,"finding-001"))


class InstallTests(unittest.TestCase):
    def test_isolated_codex_and_claude_dependency_install(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            env={**os.environ,"MASTERWU_CODEX_SKILLS_DIR":str(root / "codex"),"MASTERWU_CLAUDE_SKILLS_DIR":str(root / "claude")}
            proc=subprocess.run([str(ROOT / "scripts/install.sh"),"all","anchor-cole"],env=env,capture_output=True,text=True)
            self.assertEqual(0,proc.returncode,proc.stderr)
            for target in ("codex","claude"):
                names=sorted(p.name for p in (root / target).iterdir())
                self.assertEqual(["anchor-cole","anchor-jay","anchor-kai"],names)
                project=root / (target+"-project");fixture(project)
                reviewed_map(project,root / target / "anchor-jay/scripts/anchor_jay.py")
                result=cli(root / target / "anchor-kai/scripts/anchor_kai.py","prepare",project,"--run-id","installed")
                self.assertEqual(0,result.returncode,result.stderr)
                self.assertFalse((root / target / "jay-logic").exists())


if __name__ == "__main__":
    selection=sys.argv[1] if len(sys.argv)>1 else "all"
    suite=unittest.TestSuite()
    for name,classes in [("jay",[JayTests]),("kai",[KaiTests]),("cole",[ColeTests,InstallTests])]:
        if selection in {"all",name}:
            for cls in classes:suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
