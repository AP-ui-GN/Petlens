# Mobile dependency security

Snapshot checked October 23, 2026 against the checked-in
`mobile/package-lock.json` and the GitHub Advisory Database. This is a
dependency-tree review, not a claim that the complete npm audit is clean.

## Current findings

| Package in lockfile | Dependency path | Advisory and impact | Status |
| --- | --- | --- | --- |
| `node-forge@1.4.0` | `expo-updates@57.0.26` → `@expo/code-signing-certificates@0.0.6` → `node-forge`; also `expo@57.0.31` → `@expo/cli@57.0.32` → `node-forge` | [GHSA-86w9-cpqp-85rv](https://github.com/advisories/GHSA-86w9-cpqp-85rv), high. RSA PKCS#1 v1.5 verification can accept forged signatures with malformed nested digest-algorithm data. The advisory has no published first-patched version. | Unresolved. The upstream fix, [forge PR #1152](https://github.com/digitalbazaar/forge/pull/1152), was still open when checked; npm did not have `node-forge@1.4.1`. `mobile/app.json` configures an EAS Updates URL but no code-signing certificate, so actual exposure depends on whether signed updates are configured for a build. Do not enable signed updates that rely on this verifier until a patched release is available and tested. |
| `decode-uri-component@0.2.2` | `expo-router@57.0.29` → `query-string@7.1.3` → `decode-uri-component` | [GHSA-vcc3-ghjq-m6fr](https://github.com/advisories/GHSA-vcc3-ghjq-m6fr), moderate. Malformed percent-encoded input can cause excessive CPU use; the advisory patches versions through `0.4.2` in `0.5.0`. | Unresolved. The patched `0.5.0` package is ESM-only, while the installed `query-string@7.1.3` is CommonJS and calls the dependency as a function. No override was committed without a reproducible install and Expo bundle/runtime compatibility checks. |

The lockfile also contains `braces@3.0.3` and `shell-quote@1.12.0`.
GitHub withdrew the October 2026 `braces` stack-exhaustion advisory as not
practically exploitable. The current `shell-quote` release is above the
advisory's fixed version `1.11.0`.

## Verification limitations

- `npm ci --dry-run --ignore-scripts --no-audit` passed for the mobile lockfile.
- `npm audit` could not reach the npm security endpoint in this environment
  (`ECONNRESET` before TLS establishment). It did not produce a full current
  advisory report.
- The repository's Dependabot alerts endpoint is disabled, so it could not
  provide a second complete report.
- A lockfile-only attempt to try the decoder upgrade also stalled while npm
  retried registry requests; it was stopped without retaining a manifest or
  lockfile change.

Re-run `npm audit` from `mobile/` when the npm registry is reachable. Revisit
both unresolved packages when Expo or the upstream maintainers publish
compatible patched releases. Do not treat a successful Expo build as a
substitute for dependency auditing.
