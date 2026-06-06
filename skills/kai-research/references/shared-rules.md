# Shared Rules

- Search for candidate vulnerabilities only. Do not write PoCs, patch target contracts, or claim final exploit truth.
- Use source lines as evidence. Prefer hypotheses with concrete files, line ranges, state variables, and call paths.
- Treat Jay graph data as navigation, not proof. Confirm every important claim against the source included in the bundle.
- Do not assign severity. Use only `low`, `medium`, or `high` hypothesis confidence.
- Include why each candidate might be a false positive; this is required signal, not optional caution.
- Ignore style issues, gas-only notes, generic centralization complaints, and findings that need only malicious governance unless the assigned specialty explicitly asks for trust-boundary gaps.
