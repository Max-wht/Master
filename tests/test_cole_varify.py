#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def hypothesis(hypothesis_id: str, title: str, claim: str, *, extra: dict | None = None) -> dict:
    item = {
        "id": hypothesis_id,
        "title": title,
        "claim": claim,
        "category": "access-control",
        "confidence": "medium",
        "evidence": [{"file": "src/Vault.sol", "start_line": 10, "end_line": 20}],
        "jay_refs": {"node_ids": ["node:Vault.withdraw"], "edge_ids": []},
        "attack_sketch": "An unprivileged caller reaches withdraw.",
        "why_might_be_real": "The cited function is external.",
        "why_might_be_false_positive": "A modifier may block the path.",
        "next_validation_steps": ["Read the modifier and write a PoC."],
    }
    if extra:
        item.update(extra)
    return item


def create_project(root: Path) -> Path:
    project = root / "project"
    (project / "src").mkdir(parents=True)
    (project / "src" / "Vault.sol").write_text(
        "pragma solidity ^0.8.20;\ncontract Vault { function withdraw() external {} }\n",
        encoding="utf-8",
    )
    (project / "foundry.toml").write_text("[profile.default]\nsrc = 'src'\n", encoding="utf-8")
    return project


def create_move_project(root: Path, profile: str) -> Path:
    project = root / f"{profile}-move-project"
    (project / "sources").mkdir(parents=True)
    if profile == "sui":
        (project / "Move.toml").write_text("[package]\nname = 'sui_fixture'\n", encoding="utf-8")
        source = "module test::vault { use sui::coin; public entry fun deposit() {} }\n"
    else:
        (project / "Move.toml").write_text("[package]\nname = 'aptos_fixture'\n[dependencies]\nAptosFramework = { local = '../aptos-framework' }\n", encoding="utf-8")
        source = "module test::vault { use aptos_framework::coin; public entry fun deposit() {} }\n"
    (project / "sources" / "vault.move").write_text(source, encoding="utf-8")
    return project


def create_anchor_project(root: Path) -> Path:
    project = root / "anchor-project"
    (project / "programs" / "vault" / "src").mkdir(parents=True)
    (project / "Anchor.toml").write_text("[programs.localnet]\nvault = 'VaUlt111111111111111111111111111111111111111'\n", encoding="utf-8")
    (project / "programs" / "vault" / "src" / "lib.rs").write_text(
        "use anchor_lang::prelude::*;\n#[program]\npub mod vault { use super::*; pub fn deposit(_ctx: Context<Deposit>) -> Result<()> { Ok(()) } }\n#[derive(Accounts)]\npub struct Deposit<'info> { pub user: Signer<'info> }\n",
        encoding="utf-8",
    )
    return project


def create_kai_run(project: Path, runtime: str = "solidity") -> Path:
    run = project / "MasterWu" / "Kai" / "runs" / "check-cole"
    agent1 = run / "agents" / "01-access-control"
    agent2 = run / "agents" / "02-trust-gap"
    agent1.mkdir(parents=True)
    agent2.mkdir(parents=True)
    (agent1 / "report.md").write_text("# done\n", encoding="utf-8")
    (agent2 / "report.md").write_text("# done\n", encoding="utf-8")

    shared = hypothesis("KAI-01-001", "Anyone can withdraw", "withdraw lacks caller validation")
    duplicate = hypothesis("KAI-02-001", "Anyone can withdraw", "withdraw lacks caller validation", extra={"actor": "user"})
    unique = hypothesis(
        "KAI-02-002",
        "Admin-only sweep is design-sensitive",
        "sweep requires owner and is not ordinary-user reachable",
        extra={"seam": "trust-gap"},
    )

    write_json(
        agent1 / "hypotheses.json",
        {
            "schema_version": "1.0.0",
            "run_id": "check-cole",
            "agent_id": 1,
            "agent_name": "access-control",
            "hypotheses": [shared],
        },
    )
    write_json(
        agent2 / "hypotheses.json",
        {
            "schema_version": "1.0.0",
            "run_id": "check-cole",
            "agent_id": 2,
            "agent_name": "trust-gap",
            "hypotheses": [duplicate, unique],
        },
    )
    write_json(
        run / "spawn-manifest.json",
        {
            "schema_version": "1.0.0",
            "run_id": "check-cole",
            "runtime": runtime,
            "agents": [
                {
                    "agent_id": 1,
                    "agent_name": "access-control",
                    "agent_dir": str(agent1),
                    "report_path": str(agent1 / "report.md"),
                    "hypotheses_path": str(agent1 / "hypotheses.json"),
                },
                {
                    "agent_id": 2,
                    "agent_name": "trust-gap",
                    "agent_dir": str(agent2),
                    "report_path": str(agent2 / "report.md"),
                    "hypotheses_path": str(agent2 / "hypotheses.json"),
                },
            ],
        },
    )
    return run


def fake_forge(root: Path, exit_code: int) -> Path:
    return fake_command(root, "forge", f"fake forge \"$@\"", exit_code)


def fake_command(root: Path, name: str, output: str, exit_code: int) -> Path:
    bin_dir = root / "bin"
    bin_dir.mkdir(exist_ok=True)
    command = bin_dir / name
    command.write_text(f"#!/usr/bin/env sh\necho {output}\nexit {exit_code}\n", encoding="utf-8")
    command.chmod(0o755)
    return bin_dir


def run_cli(script: Path, args: list[str], *, env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run([sys.executable, str(script), *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    if check and proc.returncode != 0:
        raise AssertionError(f"command failed: {proc.args}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def candidate(candidate_id: str, title: str) -> dict:
    return {
        "id": candidate_id,
        "title": title,
        "claim": f"{title} claim",
        "category": "access-control",
        "confidence": "medium",
        "dedupe_key": candidate_id,
        "evidence": [{"file": "src/Vault.sol", "start_line": 10, "end_line": 20}],
        "jay_refs": {"node_ids": ["node:Vault.withdraw"], "edge_ids": []},
        "source_hypotheses": [{"agent_id": 1, "agent_name": "access-control", "hypothesis_id": f"KAI-{candidate_id}"}],
        "convergence": {"source_count": 1, "agents": ["01-access-control"]},
        "attack_sketches": ["An attacker reaches the target function."],
        "why_might_be_real": ["The cited function is external."],
        "why_might_be_false_positive": ["A guard may block it."],
        "next_validation_steps": ["Judge the exact conditions."],
        "extra_fields": [],
    }


def write_judge_output(path: Path, candidate_id: str, classification: str, *, condition_status: str = "true") -> None:
    write_json(
        path,
        {
            "schema_version": "1.0.0",
            "candidate_id": candidate_id,
            "classification": classification,
            "verdict": classification,
            "title": f"{classification} fixture",
            "finding_summary": f"{classification} summary.",
            "required_conditions": [{"condition": "Core condition", "status": condition_status, "evidence": "Fixture evidence."}],
            "reachability": "Direct external call.",
            "code_reality": "Fixture code path exists.",
            "protocol_semantics": "Fixture semantics mismatch.",
            "impact": "Fixture impact is closed.",
            "bounty_recommendation": "Do not submit" if classification in {"Info", "Gas", "Invalid"} else "Submit bounty",
            "poc": {
                "path": f"test/MasterWuCole/{candidate_id}.t.sol" if classification == "High" else "",
                "test_command": f"forge test --match-path test/MasterWuCole/{candidate_id}.t.sol -vvv" if classification == "High" else "",
                "test_result": "passed" if classification == "High" else "not-run",
                "notes": "fixture",
            },
        },
    )


def test_preflight_success(script: Path) -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        project = create_project(root)
        run = create_kai_run(project)
        bin_dir = fake_forge(root, 0)
        env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}
        run_cli(script, ["preflight", str(project), "--run", str(run)], env=env)
        preflight = json.loads((project / "MasterWu" / "cole" / "runs" / "check-cole" / "preflight.json").read_text(encoding="utf-8"))
        assert preflight["status"] == "passed"
        assert preflight["build_command"] == "forge build"


def test_preflight_failure_writes_blocker(script: Path) -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        project = create_project(root)
        run = create_kai_run(project)
        bin_dir = fake_forge(root, 2)
        env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}
        proc = run_cli(script, ["preflight", str(project), "--run", str(run)], env=env, check=False)
        assert proc.returncode != 0
        blocker = project / "MasterWu" / "cole" / "runs" / "check-cole" / "build-blocker.md"
        text = blocker.read_text(encoding="utf-8")
        assert "forge build" in text
        assert "fake forge build" in text
        assert not (project / "test" / "MasterWuCole").exists()


def test_preflight_skip_local_build(script: Path) -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        project = create_project(root)
        run = create_kai_run(project)
        bin_dir = fake_forge(root, 2)
        env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}
        run_cli(script, ["preflight", str(project), "--run", str(run), "--skip-local-build"], env=env)
        out_dir = project / "MasterWu" / "cole" / "runs" / "check-cole"
        preflight = json.loads((out_dir / "preflight.json").read_text(encoding="utf-8"))
        assert preflight["status"] == "skipped-local-build"
        assert preflight["skip_local_build"] is True
        assert preflight["verification_mode"] == "logic-only"
        assert preflight["build_system"] == "skipped"
        assert preflight["build_command"] == ""
        assert not (out_dir / "build-blocker.md").exists()
        assert not (project / "test" / "MasterWuCole").exists()


def test_preflight_aptos_move_success(script: Path) -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        project = create_move_project(root, "aptos")
        run = create_kai_run(project, "move")
        bin_dir = fake_command(root, "aptos", 'fake aptos "$@"', 0)
        env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}
        run_cli(script, ["preflight", str(project), "--run", str(run)], env=env)
        preflight = json.loads((project / "MasterWu" / "cole" / "runs" / "check-cole" / "preflight.json").read_text(encoding="utf-8"))
        assert preflight["runtime"] == "move"
        assert preflight["build_system"] == "aptos-move"
        assert preflight["build_command"] == "aptos move compile"


def test_preflight_sui_move_success(script: Path) -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        project = create_move_project(root, "sui")
        run = create_kai_run(project, "move")
        bin_dir = fake_command(root, "sui", 'fake sui "$@"', 0)
        env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}
        run_cli(script, ["preflight", str(project), "--run", str(run)], env=env)
        preflight = json.loads((project / "MasterWu" / "cole" / "runs" / "check-cole" / "preflight.json").read_text(encoding="utf-8"))
        assert preflight["runtime"] == "move"
        assert preflight["build_system"] == "sui-move"
        assert preflight["build_command"] == "sui move build"


def test_preflight_anchor_success(script: Path) -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        project = create_anchor_project(root)
        run = create_kai_run(project, "anchor")
        bin_dir = fake_command(root, "anchor", 'fake anchor "$@"', 0)
        env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}
        run_cli(script, ["preflight", str(project), "--run", str(run)], env=env)
        preflight = json.loads((project / "MasterWu" / "cole" / "runs" / "check-cole" / "preflight.json").read_text(encoding="utf-8"))
        assert preflight["runtime"] == "anchor"
        assert preflight["build_system"] == "anchor"
        assert preflight["build_command"] == "anchor build"


def test_collect_writes_draft_wreport_without_old_ids(script: Path) -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        project = create_project(root)
        run = create_kai_run(project)
        run_cli(script, ["collect", str(project), "--run", str(run)])

        out_dir = project / "MasterWu" / "cole" / "runs" / "check-cole"
        candidates_path = out_dir / "candidates.json"
        candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
        assert candidates["source_hypothesis_count"] == 3
        assert candidates["candidate_count"] == 2
        assert any(item["convergence"]["source_count"] == 2 for item in candidates["candidates"])
        assert any(item["extra_fields"] for item in candidates["candidates"])
        assert [item["id"] for item in candidates["candidates"]] == ["finding-001", "finding-002"]
        draft = (out_dir / "wreport.md").read_text(encoding="utf-8")
        assert "# WReport" in draft
        assert "## Finding 1: Anyone can withdraw" in draft
        assert "### Description" in draft
        assert "### Impact" in draft
        assert "COLE-" not in json.dumps(candidates)
        assert "COLE-" not in draft


def test_validate_judges_rejects_ambiguous_classification(script: Path) -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        project = create_project(root)
        run = create_kai_run(project)
        out_dir = project / "MasterWu" / "cole" / "runs" / "check-cole"
        candidates_path = out_dir / "candidates.json"
        write_json(
            candidates_path,
            {
                "schema_version": "1.0.0",
                "run_id": "check-cole",
                "project_root": str(project),
                "kai_run": str(run),
                "source_hypothesis_count": 1,
                "candidate_count": 1,
                "candidates": [candidate("finding-001", "Ambiguous fixture")],
            },
        )
        run_cli(script, ["prepare-judges", str(candidates_path)])
        manifest = json.loads((out_dir / "judges" / "manifest.json").read_text(encoding="utf-8"))
        output_json = Path(manifest["judges"][0]["output_json"])
        write_judge_output(output_json, "finding-001", "Conditional Medium")
        proc = run_cli(script, ["validate-judges", str(out_dir / "judges" / "manifest.json")], check=False)
        assert proc.returncode != 0
        assert "classification must be one of" in proc.stderr


def test_apply_judges_merges_only_exact_six_classifications(script: Path) -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        project = create_project(root)
        run = create_kai_run(project)
        out_dir = project / "MasterWu" / "cole" / "runs" / "check-cole"
        candidates_path = out_dir / "candidates.json"
        classifications = ["High", "Medium", "Low", "Info", "Gas", "Invalid"]
        candidates = [candidate(f"finding-{idx:03d}", f"{classification} fixture") for idx, classification in enumerate(classifications, start=1)]
        write_json(
            candidates_path,
            {
                "schema_version": "1.0.0",
                "run_id": "check-cole",
                "project_root": str(project),
                "kai_run": str(run),
                "source_hypothesis_count": len(candidates),
                "candidate_count": len(candidates),
                "candidates": candidates,
            },
        )
        run_cli(script, ["prepare-judges", str(candidates_path)])
        manifest = json.loads((out_dir / "judges" / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["max_parallel"] == 6
        for entry, classification in zip(manifest["judges"], classifications):
            write_judge_output(
                Path(entry["output_json"]),
                entry["candidate_id"],
                classification,
                condition_status="false" if classification == "Invalid" else "true",
            )

        run_cli(script, ["validate-judges", str(out_dir / "judges" / "manifest.json")])
        run_cli(script, ["apply-judges", str(candidates_path)])
        results_path = out_dir / "results.json"
        run_cli(script, ["validate-results", str(results_path), "--candidates", str(candidates_path)])
        run_cli(script, ["render-report", str(results_path)])
        report = (out_dir / "wreport.md").read_text(encoding="utf-8")
        for final_id in ("[H-1]", "[M-1]", "[L-1]", "[I-1]", "[G-1]", "[Invalid-1]"):
            assert final_id in report
        assert "### Finding Summary" in report
        assert "### Required Conditions" in report
        assert "### Verdict" in report
        assert "Needs" not in report
        assert "COLE-" not in report
        results_text = results_path.read_text(encoding="utf-8")
        assert "test/MasterWuCole/h-1.t.sol" in results_text
        assert "finding-001.t.sol" not in results_text
        assert "COLE-" not in results_text


def test_validate_judges_rejects_unproven_condition_status(script: Path) -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        project = create_project(root)
        run = create_kai_run(project)
        out_dir = project / "MasterWu" / "cole" / "runs" / "check-cole"
        candidates_path = out_dir / "candidates.json"
        write_json(
            candidates_path,
            {
                "schema_version": "1.0.0",
                "run_id": "check-cole",
                "project_root": str(project),
                "kai_run": str(run),
                "source_hypothesis_count": 1,
                "candidate_count": 1,
                "candidates": [candidate("finding-001", "Unproven fixture")],
            },
        )
        run_cli(script, ["prepare-judges", str(candidates_path)])
        manifest = json.loads((out_dir / "judges" / "manifest.json").read_text(encoding="utf-8"))
        write_judge_output(Path(manifest["judges"][0]["output_json"]), "finding-001", "Invalid", condition_status="Unproven")
        proc = run_cli(script, ["validate-judges", str(out_dir / "judges" / "manifest.json")], check=False)
        assert proc.returncode != 0
        assert "invalid status Unproven" in proc.stderr


def test_validate_judges_rejects_role_dependent_security_classification(script: Path) -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        project = create_project(root)
        run = create_kai_run(project)
        out_dir = project / "MasterWu" / "cole" / "runs" / "check-cole"
        candidates_path = out_dir / "candidates.json"
        write_json(
            candidates_path,
            {
                "schema_version": "1.0.0",
                "run_id": "check-cole",
                "project_root": str(project),
                "kai_run": str(run),
                "source_hypothesis_count": 1,
                "candidate_count": 1,
                "candidates": [candidate("finding-001", "Role fixture")],
            },
        )
        run_cli(script, ["prepare-judges", str(candidates_path)])
        manifest = json.loads((out_dir / "judges" / "manifest.json").read_text(encoding="utf-8"))
        write_judge_output(Path(manifest["judges"][0]["output_json"]), "finding-001", "Medium", condition_status="depend on role")
        proc = run_cli(script, ["validate-judges", str(out_dir / "judges" / "manifest.json")], check=False)
        assert proc.returncode != 0
        assert "Medium requires every condition to be true" in proc.stderr


def test_info_accepts_role_dependent_condition(script: Path) -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        project = create_project(root)
        run = create_kai_run(project)
        out_dir = project / "MasterWu" / "cole" / "runs" / "check-cole"
        candidates_path = out_dir / "candidates.json"
        write_json(
            candidates_path,
            {
                "schema_version": "1.0.0",
                "run_id": "check-cole",
                "project_root": str(project),
                "kai_run": str(run),
                "source_hypothesis_count": 1,
                "candidate_count": 1,
                "candidates": [candidate("finding-001", "Info role fixture")],
            },
        )
        run_cli(script, ["prepare-judges", str(candidates_path)])
        manifest = json.loads((out_dir / "judges" / "manifest.json").read_text(encoding="utf-8"))
        write_judge_output(Path(manifest["judges"][0]["output_json"]), "finding-001", "Info", condition_status="depend on role")
        run_cli(script, ["validate-judges", str(out_dir / "judges" / "manifest.json")])
        run_cli(script, ["apply-judges", str(candidates_path)])
        report = (out_dir / "wreport.md").read_text(encoding="utf-8")
        assert "[depend on role]" in report
        assert "Unproven" not in report


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: test_cole_varify.py <cole_varify.py>", file=sys.stderr)
        return 2
    script = Path(sys.argv[1])
    test_preflight_success(script)
    test_preflight_failure_writes_blocker(script)
    test_preflight_skip_local_build(script)
    test_preflight_aptos_move_success(script)
    test_preflight_sui_move_success(script)
    test_preflight_anchor_success(script)
    test_collect_writes_draft_wreport_without_old_ids(script)
    test_validate_judges_rejects_ambiguous_classification(script)
    test_apply_judges_merges_only_exact_six_classifications(script)
    test_validate_judges_rejects_unproven_condition_status(script)
    test_validate_judges_rejects_role_dependent_security_classification(script)
    test_info_accepts_role_dependent_condition(script)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
