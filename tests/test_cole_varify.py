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


def create_kai_run(project: Path) -> Path:
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
    bin_dir = root / "bin"
    bin_dir.mkdir()
    forge = bin_dir / "forge"
    forge.write_text(f"#!/usr/bin/env sh\necho fake forge \"$@\"\nexit {exit_code}\n", encoding="utf-8")
    forge.chmod(0o755)
    return bin_dir


def run_cli(script: Path, args: list[str], *, env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run([sys.executable, str(script), *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    if check and proc.returncode != 0:
        raise AssertionError(f"command failed: {proc.args}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


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


def test_collect_validate_and_render(script: Path) -> None:
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

        findings = []
        for idx, candidate in enumerate(candidates["candidates"]):
            findings.append(
                {
                    "id": candidate["id"],
                    "title": candidate["title"],
                    "source_hypotheses": candidate["source_hypotheses"],
                    "verification_status": "confirmed" if idx == 0 else "rejected",
                    "reachability": "ordinary-user-reachable" if idx == 0 else "trusted-role-only",
                    "nature": "real-bug" if idx == 0 else "false-positive",
                    "evidence": candidate["evidence"],
                    "poc": {
                        "path": "test/MasterWuCole/COLE-001.t.sol" if idx == 0 else "",
                        "test_command": "forge test --match-path test/MasterWuCole/COLE-001.t.sol -vvv" if idx == 0 else "",
                        "test_result": "passed" if idx == 0 else "not-run",
                        "notes": "fixture",
                    },
                    "reasoning": "Source path was checked in the fixture.",
                    "final_recommendation": "Keep for report." if idx == 0 else "Reject.",
                }
            )
        results_path = out_dir / "results.json"
        write_json(
            results_path,
            {
                "schema_version": "1.0.0",
                "run_id": "check-cole",
                "project_root": str(project),
                "kai_run": str(run),
                "findings": findings,
                "build_and_test_notes": "fixture notes",
            },
        )
        run_cli(script, ["validate-results", str(results_path), "--candidates", str(candidates_path)])
        run_cli(script, ["render-report", str(results_path), "--out", str(out_dir / "report.md")])
        report = (out_dir / "report.md").read_text(encoding="utf-8")
        assert "# Cole Varify Report" in report
        assert "COLE-001" in report
        assert "confirmed" in report
        assert "rejected" in report


def test_render_report_deduplicates_findings(script: Path) -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        project = create_project(root)
        run = create_kai_run(project)
        out_dir = project / "MasterWu" / "cole" / "runs" / "check-cole"
        evidence = [{"file": "src/Vault.sol", "start_line": 10, "end_line": 20}]
        base_poc = {"path": "", "test_command": "", "test_result": "not-run", "notes": "fixture"}
        findings = [
            {
                "id": "COLE-001",
                "title": "Anyone can withdraw",
                "source_hypotheses": [{"agent_id": 1, "agent_name": "access-control", "hypothesis_id": "KAI-01-001"}],
                "verification_status": "needs-poc",
                "reachability": "ordinary-user-reachable",
                "nature": "real-bug",
                "evidence": evidence,
                "poc": base_poc,
                "reasoning": "First reasoning path.",
                "final_recommendation": "Write a PoC.",
            },
            {
                "id": "COLE-099",
                "title": "Anyone can withdraw",
                "source_hypotheses": [{"agent_id": 11, "agent_name": "trust-gap", "hypothesis_id": "KAI-11-004"}],
                "verification_status": "confirmed",
                "reachability": "trusted-role-only",
                "nature": "real-bug",
                "evidence": evidence,
                "poc": {
                    "path": "test/MasterWuCole/COLE-001.t.sol",
                    "test_command": "forge test --match-path test/MasterWuCole/COLE-001.t.sol -vvv",
                    "test_result": "passed",
                    "notes": "fixture",
                },
                "reasoning": "Second reasoning path.",
                "final_recommendation": "Keep as one merged finding.",
            },
        ]
        results_path = out_dir / "results.json"
        write_json(
            results_path,
            {
                "schema_version": "1.0.0",
                "run_id": "check-cole",
                "project_root": str(project),
                "kai_run": str(run),
                "findings": findings,
            },
        )
        run_cli(script, ["validate-results", str(results_path)])
        run_cli(script, ["render-report", str(results_path), "--out", str(out_dir / "report.md")])
        report = (out_dir / "report.md").read_text(encoding="utf-8")
        assert "- Raw findings/candidates: `2`" in report
        assert "- Deduped report findings: `1`" in report
        assert report.count("### COLE-") == 1
        assert "Merged ids: `COLE-001, COLE-099`" in report
        assert "1-access-control:KAI-01-001" in report
        assert "11-trust-gap:KAI-11-004" in report
        assert "[COLE-001] First reasoning path." in report
        assert "[COLE-099] Second reasoning path." in report


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: test_cole_varify.py <cole_varify.py>", file=sys.stderr)
        return 2
    script = Path(sys.argv[1])
    test_preflight_success(script)
    test_preflight_failure_writes_blocker(script)
    test_preflight_skip_local_build(script)
    test_collect_validate_and_render(script)
    test_render_report_deduplicates_findings(script)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
