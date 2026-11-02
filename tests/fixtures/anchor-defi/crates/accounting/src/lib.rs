pub fn credit(total: &mut u64, amount: u64) {
    *total = total.checked_add(amount).unwrap();
}
