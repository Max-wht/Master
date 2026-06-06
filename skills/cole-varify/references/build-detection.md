# Build Detection

Cole must prove the target project can build before verifying hypotheses or writing PoCs.

Exception: if the user explicitly passes `--skip-local-build`, Cole validates the Kai run only and writes `preflight.json` with `status: "skipped-local-build"`, `skip_local_build: true`, and `verification_mode: "logic-only"`. This is not a build pass.

Detection priority:

1. Foundry: `foundry.toml` -> `forge build`.
2. Hardhat: `hardhat.config.js`, `hardhat.config.ts`, `hardhat.config.cjs`, or `hardhat.config.mjs` -> `npx hardhat compile`.
3. npm test fallback: `package.json` with a `test` script -> `npm test`.
4. Truffle: `truffle-config.js` or `truffle.js` -> `npx truffle compile`.

If the build tool is missing or the command fails:

- Stop the skill.
- Do not create `test/MasterWuCole/`.
- Do not classify hypotheses from Kai text.
- Report the failed command and the generated `MasterWu/cole/runs/<run-id>/build-blocker.md`.

If `--skip-local-build` is used:

- Do not detect or run the build command.
- Do not create `build-blocker.md`.
- Do not create `test/MasterWuCole/`.
- Do not run PoC tests.
- The final report must state: `local build skipped; PoC validation not performed`.

The user can override the command only when the project has a non-standard build path:

```bash
python3 "$SKILL_DIR/scripts/cole_varify.py" preflight <project-root> --run <kai-run-dir> --build-command "forge build --root ."
```

Logic-only mode:

```bash
python3 "$SKILL_DIR/scripts/cole_varify.py" preflight <project-root> --run <kai-run-dir> --skip-local-build
```
