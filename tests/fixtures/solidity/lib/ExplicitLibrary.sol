// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract ExplicitLibrary {
    uint256 public value;

    function explicitValue(uint256 value_) external {
        value = value_;
    }
}
