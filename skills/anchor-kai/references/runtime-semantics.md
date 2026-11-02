# Anchor-Native Research

Identity combines signer bits, pubkeys, account owners, type-defined deserialization/discriminators and protocol authority relationships. Typed Account/AccountLoader/InterfaceAccount/Program/Interface checks must be verified before calling missing explicit constraints a vulnerability. UncheckedAccount, AccountInfo and remaining_accounts require traced manual validation.

PDA identity is the full seeds, bump and deriving program. Separate address derivation from authority, canonical-bump requirements and lifecycle conditions. Read initialization, init_if_needed, realloc, close and recovery together. Duplicate-account handling, discriminator lengths and macro-generated checks depend on the target dependency version/features.

A transaction's privileges bound CPI privileges. A PDA signer may be intentionally forwarded; prove an untrusted target and harmful capability before reporting confused-deputy behavior. Verify runtime nesting/reentrancy restrictions and rollback rather than transplanting EVM assumptions. A constructed CpiContext does not prove the CPI executed.

For SPL/Token-2022 distinguish token-program identity, mint, account authority, delegate/freeze/permanent-delegate privileges, extension policies, transfer fees/withheld fees, transfer hooks, CPI guard and close requirements. Compare recorded amounts to actual balance changes. Interest-bearing UI scaling does not automatically change raw token balances or prove insolvency.

Assess oracle account identity/owner, feed binding, freshness/status/confidence and price units against the actual oracle interface. Reconcile shares, reserves, debt/rewards across ordinary and stressed paths. Availability/compute failures require a reachable harmful state, not merely a loop/unwrap keyword.

Source-only research remains possible without Anchor/Solana CLI. Unresolved macros, calls and features are map limits requiring source expansion; never infer nonexistent guards from parser omissions.

Sources: [Anchor constraints](https://www.anchor-lang.com/docs/references/account-constraints), [Solana CPI](https://solana.com/docs/core/cpi), [Token extensions](https://www.anchor-lang.com/docs/tokens/extensions).
