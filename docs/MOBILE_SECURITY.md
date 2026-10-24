# Mobile dependency security

Snapshot checked October 24, 2026 with `npm audit` against the checked-in
`mobile/package-lock.json`. This is a dependency-tree review, not a claim that
the mobile dependency audit is clean.

## Current findings

| Package in lockfile | Dependency path | Advisory and impact | Status |
| --- | --- | --- | --- |
| `node-forge@1.4.0` | `expo-updates@57.0.26` → `@expo/code-signing-certificates@0.0.6` → `node-forge`; also `expo@57.0.31` → `@expo/cli@57.0.32` → `node-forge` | [GHSA-86w9-cpqp-85rv](https://github.com/advisories/GHSA-86w9-cpqp-85rv), high. RSA PKCS#1 v1.5 verification can accept forged signatures with malformed nested digest-algorithm data. The advisory has no published first-patched version. | Unresolved. The upstream fix, [forge PR #1152](https://github.com/digitalbazaar/forge/pull/1152), was still open when checked; npm did not have `node-forge@1.4.1`. `mobile/app.json` configures an EAS Updates URL but no code-signing certificate, so actual exposure depends on whether signed updates are configured for a build. Do not enable signed updates that rely on this verifier until a patched release is available and tested. |
| `decode-uri-component@0.2.2` | `expo-router@57.0.29` → `query-string@7.1.3` → `decode-uri-component` | [GHSA-vcc3-ghjq-m6fr](https://github.com/advisories/GHSA-vcc3-ghjq-m6fr), moderate. Malformed percent-encoded input can cause excessive CPU use; patched releases are `0.5.0` and later. | Unresolved. `0.5.1` is published, but the patched package is ESM-only while the installed `query-string@7.1.3` is CommonJS and calls the dependency synchronously. The audit fix requires a major Expo Router upgrade; no override was committed without compatible bundle/runtime checks. |
| `zod` | `expo@57.0.31` → `@expo/cli@57.0.32` → `zod` | [GHSA-mrhx-c7xc-m3w5](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5), high. Oversized constrained collections can exhaust memory during validation. | Unresolved. This path is used by Expo CLI tooling rather than the app's request validation. npm's suggested fix downgrades Expo across major SDK versions; it is not a safe automatic update. |

The lockfile also contains `braces@3.0.3` and `shell-quote@1.12.0`.
GitHub withdrew the October 2026 `braces` stack-exhaustion advisory as not
practically exploitable. The current `shell-quote` release is above the
advisory's fixed version `1.11.0`.

## Verification

- `npm audit` completed on October 24, 2026: 9 vulnerability instances
  (6 high, 3 moderate, 0 critical). The findings above cover the affected
  package paths; the audit also counts intermediate Expo packages in those
  chains.
- `npm ci --dry-run --ignore-scripts --no-audit` passed for the mobile lockfile.
- The repository's Dependabot alerts endpoint is disabled, so it could not
  provide an independent report.

The available automatic upgrades require major Expo SDK changes, and the
patched URI decoder is incompatible with the current CommonJS dependency.
Do not apply `npm audit fix --force` or downgrade Expo to the versions npm
suggests. Revisit these findings with a tested Expo SDK upgrade and compatible
runtime dependencies; a successful Expo build is not a substitute for that
audit.
