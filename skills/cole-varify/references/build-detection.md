# Build Detection

Cole must prove the target project can build before verifying hypotheses or writing PoCs.

Exception: if the user explicitly passes `--skip-local-build`, Cole validates the Kai run only and writes `preflight.json` with `status: "skipped-local-build"`, `skip_local_build: true`, and `verification_mode: "logic-only"`. This is not a build pass.

Detection priority:

1. Anchor: `Anchor.toml` with runtime `anchor` -> `anchor build`.
2. Move: `Move.toml` or `.move` sources with runtime `move` -> `sui move build` for Sui-looking packages, `aptos move compile` for Aptos-looking packages, otherwise whichever CLI exists.
3. Foundry: `foundry.toml` -> `forge build`.
4. Hardhat: `hardhat.config.js`, `hardhat.config.ts`, `hardhat.config.cjs`, or `hardhat.config.mjs` -> `npx hardhat compile`.
5. npm test fallback: `package.json` with a `test` script -> `npm test`.
6. Truffle: `truffle-config.js` or `truffle.js` -> `npx truffle compile`.

If the build tool is missing or the command fails:

- Stop the skill.
- Do not create runtime PoC directories (`test/MasterWuCole/`, `tests/MasterWuCole/`, or `tests/masterwu/`).
- Do not classify hypotheses from Kai text.
- Report the failed command and the generated `MasterWu/cole/runs/<run-id>/build-blocker.md`.

If `--skip-local-build` is used:

- Do not detect or run the build command.
- Do not create `build-blocker.md`.
- Do not create runtime PoC directories (`test/MasterWuCole/`, `tests/MasterWuCole/`, or `tests/masterwu/`).
- Do not run PoC tests.
- The final report must state: `local build skipped; PoC validation not performed`.

The user can override the runtime or command only when the project has a non-standard build path or the Kai manifest is from an older run:

```bash
python3 "$SKILL_DIR/scripts/cole_varify.py" preflight <project-root> --run <kai-run-dir> --build-command "forge build --root ."
python3 "$SKILL_DIR/scripts/cole_varify.py" preflight <project-root> --run <kai-run-dir> --runtime anchor
```

Logic-only mode:

```bash
python3 "$SKILL_DIR/scripts/cole_varify.py" preflight <project-root> --run <kai-run-dir> --skip-local-build
```
