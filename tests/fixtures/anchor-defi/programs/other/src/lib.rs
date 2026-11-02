use anchor_lang::prelude::*;
#[program]
pub mod other {
    use super::*;
    pub fn deposit(ctx: Context<Deposit>, amount: u64) -> Result<()> {
        ctx.accounts.vault.total = amount;
        Ok(())
    }
}
#[derive(Accounts)]
pub struct Deposit<'info> {
    /// CHECK: intentionally unconstrained for source-map negative control.
    pub user: UncheckedAccount<'info>,
    #[account(mut, init_if_needed, payer = user, space = 64)]
    pub vault: Account<'info, Vault>,
}
#[account]
pub struct Vault { pub total: u64 }
