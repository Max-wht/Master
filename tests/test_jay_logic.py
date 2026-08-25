#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


def load(path: str) -> dict:
    return json.loads(Path(path).read_text())


def assert_has_edge(graph: dict, edge_type: str, target_name: str) -> None:
    nodes = {node["id"]: node for node in graph["nodes"]}
    for edge in graph["edges"]:
        if edge["type"] == edge_type and nodes[edge["to"]]["name"] == target_name:
            return
    raise AssertionError(f"missing edge type {edge_type} to {target_name}")


def assert_has_function(graph: dict, name: str) -> dict:
    for node in graph["nodes"]:
        if node["type"] == "function" and node["name"] == name:
            return node
    raise AssertionError(f"missing function {name}")


def main() -> int:
    if len(sys.argv) != 4:
        print("Usage: test_jay_logic.py <solidity-json> <move-json> <anchor-json>", file=sys.stderr)
        return 2
    solidity = load(sys.argv[1])
    move = load(sys.argv[2])
    anchor = load(sys.argv[3])

    deposit = assert_has_function(solidity, "deposit")
    assert deposit["start_line"] > 0 and deposit["end_line"] >= deposit["start_line"]
    assert_has_edge(solidity, "writes", "balances")
    assert_has_edge(solidity, "guards", "paused")
    assert_has_edge(solidity, "external_call", "asset.transferFrom")
    assert any(item["file"].endswith("Vault.sol") and item["line"] == deposit["start_line"] for item in solidity["line_links"])

    move_deposit = assert_has_function(move, "deposit")
    assert move_deposit.get("metadata", {}).get("entry_point") is True
    move_read = assert_has_function(move, "read")
    assert move_read.get("metadata", {}).get("entry_point") is False
    assert_has_edge(move, "writes", "Balance")
    assert_has_edge(move, "reads", "Balance")
    assert_has_edge(move, "external_call", "signer::address_of")

    anchor_deposit = assert_has_function(anchor, "deposit")
    assert anchor_deposit.get("metadata", {}).get("entry_point") is True
    assert anchor_deposit.get("metadata", {}).get("context") == "Deposit"
    assert_has_edge(anchor, "writes", "Vault")
    assert_has_edge(anchor, "guards", "deposit guard")
    assert_has_edge(anchor, "external_call", "token::transfer")
    assert_has_edge(anchor, "transfers_value", "token::transfer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
