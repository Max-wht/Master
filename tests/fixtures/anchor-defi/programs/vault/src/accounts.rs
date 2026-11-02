use anchor_lang::prelude::*;
use anchor_spl::token_interface::{Mint, TokenAccount, TokenInterface};
use crate::state::Vault;

#[derive(Accounts)]
pub struct Deposit<'info> {
    pub user: Signer<'info>,
    #[account(
        mut,
        seeds = [b"vault,domain", user.key().as_ref()],
        bump,
        has_one = authority,
        constraint = vault.total < 1_000_000,
        owner = crate::ID
    )]
    pub vault: Box<Account<'info, Vault>>,
    /// CHECK: authority is constrained by has_one.
    pub authority: UncheckedAccount<'info>,
    #[account(mut, token::mint = mint, token::authority = user, token::token_program = token_program)]
    pub source: InterfaceAccount<'info, TokenAccount>,
    pub mint: InterfaceAccount<'info, Mint>,
    pub token_program: Interface<'info, TokenInterface>,
}

#[derive(Accounts)]
pub struct Withdraw<'info> {
    pub user: Signer<'info>,
    #[account(mut)]
    pub vault: Account<'info, Vault>,
}
