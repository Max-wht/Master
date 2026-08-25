# Runtime Semantics

Use this map before writing a hypothesis. Do not translate Solidity terms literally into Move or Anchor. First reduce the code to the audit question, then use the runtime-native mechanism.

| Abstract semantic | Solidity | Move | Anchor |
| --- | --- | --- | --- |
| Runtime profile | `.sol`, Foundry, Hardhat | `.move`, `Move.toml`, Aptos/Sui packages | `Anchor.toml`, `#[program]`, `Context<...>`, `anchor-lang` |
| Entry point | non-view `external` / `public` function | `entry fun` or `public entry fun` | `pub fn(ctx: Context<...>)` under `#[program]` |
| Caller identity | `msg.sender` | `&signer`, signer address, object owner | `Signer<'info>`, signer bit, account pubkey |
| Authority model | modifiers, owner, role storage | capabilities, signer/resource owner, `public(friend)` | account constraints, PDA seeds/bump, `has_one`, explicit signer |
| Persistent state | storage variables, mappings, slots | resources, objects, tables, fields | account data, PDA accounts, token accounts |
| Value/resource flow | native value, ERC20/ERC721 transfer | `Coin<T>`, object transfer, `TreasuryCap` | lamports, SPL Token/Token-2022, token accounts |
| Guard predicate | `require`, `revert`, modifier body | `assert!`, `abort`, resource existence | `require!`, `err!`, `#[account(...)]` constraints |
| Cross boundary | external call, token call, delegatecall | module/friend call, object/coin transfer | CPI, `invoke_signed`, remaining accounts |
| Upgrade/layout | proxy/admin/storage layout | package upgrade/resource migration | upgrade authority/account layout/realloc |
| Observability | events, ABI, metadata | events, type path, metadata | logs, IDL, account discriminator |

Rules:

- Treat `public`, `pub fn`, and `public fun` as entry points only when the runtime makes them externally reachable and state/resources can change.
- In Move, capabilities and resources are first-class authority. Type identity is the asset identity; metadata symbols are not enough.
- In Anchor, account owner, discriminator, signer bit, PDA seeds, bump, `has_one`, token program, mint, and token account owner are core authority boundaries.
- In mixed repos, do not invent a global call graph. Connect components only through explicit bridge messages, bindings, CPI, FFI, generated interfaces, or cross-chain adapters.
- Hypotheses must cite runtime-native evidence: source lines, Jay nodes/edges, guard predicates, state/resource deltas, account/resource ownership, or external boundary assumptions.
