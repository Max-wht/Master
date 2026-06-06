// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IERC20 {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
}

contract Vault {
    IERC20 public asset;
    mapping(address => uint256) public balances;
    bool public paused;

    event Deposit(address indexed user, uint256 amount);

    constructor(IERC20 asset_) {
        asset = asset_;
    }

    function setPaused(bool value) external {
        paused = value;
    }

    function deposit(uint256 amount) external {
        require(!paused, "paused");
        asset.transferFrom(msg.sender, address(this), amount);
        balances[msg.sender] += amount;
        emit Deposit(msg.sender, amount);
    }

    function withdraw(uint256 amount) external {
        require(balances[msg.sender] >= amount, "balance");
        balances[msg.sender] -= amount;
        asset.transfer(msg.sender, amount);
    }
}
