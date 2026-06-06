module test::vault {
    use std::signer;

    struct Balance has key {
        value: u64,
    }

    public entry fun deposit(account: &signer, amount: u64) acquires Balance {
        assert!(amount > 0, 1);
        if (!exists<Balance>(signer::address_of(account))) {
            move_to(account, Balance { value: 0 });
        };
        let balance = borrow_global_mut<Balance>(signer::address_of(account));
        balance.value = balance.value + amount;
    }

    public fun read(account: address): u64 acquires Balance {
        let balance = borrow_global<Balance>(account);
        balance.value
    }
}
