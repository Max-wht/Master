use anchor_lang::prelude::*;
mod accounts;
mod state;
use accounts::*;
use state::Vault;

#[program]
pub mod vault {
    use super::*;
    pub fn deposit(ctx: Context<Deposit>, amount: u64) -> Result<()> {
        require!(amount > 0, ErrorCode::Zero);
        let v = &mut ctx.accounts.vault;
        v.total += amount;
        math::credit(&mut v.total, amount);
        Ok(())
    }
    pub fn withdraw(ctx: Context<Withdraw>, amount: u64) -> Result<()> {
        require_keys_eq!(ctx.accounts.user.key(), ctx.accounts.vault.authority);
        ctx.accounts.vault.total = ctx.accounts.vault.total.checked_sub(amount).unwrap();
        Ok(())
    }
}

#[cfg(feature = "experimental")]
pub fn custom_path() { custom_validation!(); }
