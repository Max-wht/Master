#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

AGENT_SLUGS = [
    "01-math-precision",
    "02-access-control",
    "03-economic-security",
    "04-execution-trace",
    "05-invariant",
    "06-periphery",
    "07-first-principles",
    "08-asymmetry",
    "09-boundary",
    "10-numerical-gap",
    "11-trust-gap",
    "12-flow-gap",
]
EXCLUDED_PREFIXES = ("MasterWu/", "Lloyd/", "interfaces/", "lib/", "mock/", "mocks/", "test/", "tests/")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_valid_hypotheses(path: Path, agent_id: int, agent_name: str) -> None:
    data = load_json(path)
    assert data["schema_version"] == "1.0.0"
    assert data["agent_id"] == agent_id
    assert data["agent_name"] == agent_name
    assert isinstance(data["hypotheses"], list)
    for item in data["hypotheses"]:
        assert item["confidence"] in {"low", "medium", "high"}
        assert "severity" not in item
        assert "verdict" not in item


def check_default_run(run_dir: Path) -> None:
    manifest = load_json(run_dir / "spawn-manifest.json")
    assert manifest["schema_version"] == "1.0.0"
    assert manifest["run_id"] == "check-kai"
    assert manifest["runtime"] == "solidity"
    assert len(manifest["agents"]) == 12

    scope = (run_dir / "scope.txt").read_text(encoding="utf-8").splitlines()
    assert scope == ["src/Vault.sol"], scope
    assert not any(path.startswith(EXCLUDED_PREFIXES) for path in scope)

    source = (run_dir / "source.md").read_text(encoding="utf-8")
    assert "contract Vault" in source
    assert "IgnoredInterface" not in source
    assert "GeneratedLloydArtifact" not in source
    assert "GeneratedMasterWuArtifact" not in source

    slices = sorted((run_dir / "jay-slices").glob("agent-*.md"))
    assert len(slices) == 12

    for idx, slug in enumerate(AGENT_SLUGS, start=1):
        agent_dir = run_dir / "agents" / slug
        assert agent_dir.is_dir()
        bundle = (agent_dir / "bundle.md").read_text(encoding="utf-8")
        assert "## Jay Graph Slice" in bundle
        assert "## Runtime Semantics" in bundle
        assert "## Full In-Scope Source" in bundle
        assert "src/Vault.sol" in bundle
        report = (agent_dir / "report.md").read_text(encoding="utf-8")
        assert "PENDING_KAI_AGENT_OUTPUT" in report
        assert_valid_hypotheses(agent_dir / "hypotheses.json", idx, slug.split("-", 1)[1])


def check_explicit_run(run_dir: Path) -> None:
    manifest = load_json(run_dir / "spawn-manifest.json")
    assert manifest["runtime"] == "solidity"
    scope = (run_dir / "scope.txt").read_text(encoding="utf-8").splitlines()
    assert scope == ["lib/ExplicitLibrary.sol"], scope
    source = (run_dir / "source.md").read_text(encoding="utf-8")
    assert "contract ExplicitLibrary" in source
    assert "explicitValue" in source
    first_slice = (run_dir / "jay-slices" / "agent-01-math-precision.md").read_text(encoding="utf-8")
    assert "ExplicitLibrary" in first_slice
    assert "explicitValue" in first_slice


def check_move_run(run_dir: Path) -> None:
    manifest = load_json(run_dir / "spawn-manifest.json")
    assert manifest["runtime"] == "move"
    scope = (run_dir / "scope.txt").read_text(encoding="utf-8").splitlines()
    assert scope == ["sources/vault.move"], scope
    source = (run_dir / "source.md").read_text(encoding="utf-8")
    assert "```move" in source
    assert "public entry fun deposit" in source
    bundle = (run_dir / "agents" / "02-access-control" / "bundle.md").read_text(encoding="utf-8")
    assert "Runtime Semantics" in bundle
    assert "signer" in bundle


def check_anchor_run(run_dir: Path) -> None:
    manifest = load_json(run_dir / "spawn-manifest.json")
    assert manifest["runtime"] == "anchor"
    scope = (run_dir / "scope.txt").read_text(encoding="utf-8").splitlines()
    assert scope == ["programs/vault/src/lib.rs"], scope
    source = (run_dir / "source.md").read_text(encoding="utf-8")
    assert "```rust" in source
    assert "#[program]" in source
    first_slice = (run_dir / "jay-slices" / "agent-02-access-control.md").read_text(encoding="utf-8")
    assert "Deposit.vault constraint" in first_slice
    assert "token::transfer" in first_slice


def main() -> int:
    if len(sys.argv) != 5:
        print("Usage: test_kai_research.py <default-run-dir> <explicit-run-dir> <move-run-dir> <anchor-run-dir>", file=sys.stderr)
        return 2
    check_default_run(Path(sys.argv[1]))
    check_explicit_run(Path(sys.argv[2]))
    check_move_run(Path(sys.argv[3]))
    check_anchor_run(Path(sys.argv[4]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
