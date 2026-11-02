# Extraction and Runtime Facts

AST extraction handles declarations, modules/types, multi-line attributes, helpers, simple account aliases, assignments, manual guards and known CPI calls. It does not expand macros, evaluate cfg, infer Rust types or prove control-flow reachability. Conditional source is retained and flagged. Tests/generated/vendor code are supporting evidence rather than default program scope.

Cargo manifests identify Anchor crates, workspace-inherited dependencies/features, local path dependencies and arithmetic profiles. Cargo.lock supplies resolved versions. Unlocked versions, remote CPI programs and external path dependencies require investigation. Never upgrade the target to fit the audit.

Default discovery requires an Anchor dependency and a Cargo library target: an explicit `[lib]` (including a custom `path`) or an auto-discovered `src/lib.rs` when `autolib` is enabled. Binary-only clients such as `clients/deploy/src/main.rs` are excluded. Explicit `--files` scope follows only the selected crates' local library dependencies.

With the pinned tree-sitter 0.26.0, read Point coordinates through tuple indexing (`point[0]`, `point[1]`). Its [C getters for `Point.row` and `Point.column`](https://github.com/tree-sitter/py-tree-sitter/blob/v0.26.0/tree_sitter/binding/point.c) return borrowed integer references instead of new references. Above CPython's usual small-integer cache limit (256), attribute access can corrupt the heap and cause a later segfault in an unrelated node operation. Retaining trees, replacing parsers or changing Python versions does not correct this reference-counting error. Keep a regression fixture with both rows and columns above 256.

Keep type-implied checks, explicit constraints and manual checks separate:

- Signer validates the signer bit, not its relationship to protocol authority.
- Account<T>/AccountLoader<T> supply type-defined owner/deserialization checks. Inspect T/version; SPL types need not use Anchor discriminators.
- InterfaceAccount<T> accepts type-defined owners. Mint, token authority and token-program relationships still require validation.
- Program<T>/Interface<T> validate type-defined ids and executable status. UncheckedAccount/AccountInfo do not supply equivalent typed checks.
- seeds/bump/seeds::program, has_one, address, owner, token::*, associated_token::*, init/init_if_needed, close, realloc and custom constraints remain distinct raw facts. Explicit owner constraints do not override Account<T>'s implicit check.
- Duplicate-account rules, custom discriminator lengths, zero-copy and close/revival behavior are version/type dependent. Do not assume a universal eight-byte discriminator or duplicate rule.

Known CPI/value edges indicate operations, not proved deltas. CpiContext records target and signer seeds separately. Inspect remaining_accounts, authority forwarding and reload ordering. Check runtime CPI nesting/privilege restrictions before proposing callback/reentrancy paths.

Sources: [Anchor constraints](https://www.anchor-lang.com/docs/references/account-constraints), [account types](https://www.anchor-lang.com/docs/references/account-types), [Solana CPI](https://solana.com/docs/core/cpi).
