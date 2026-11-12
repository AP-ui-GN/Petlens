# Day 4 — live backend verification, November 12, 2026

**YES:** the original local S004 dog video passed through the running Express
`POST /api/analyze` endpoint, the actual Python CLI, both API schema checks,
and an HTTP 200 JSON response. No application fix was necessary.

Branch: `feature/canine-gait-v2`. HEAD:
`94e9f56ef66737f171d2e2d80ebad742c577bff9`. Day 3's optional SciPy import,
structured dependency-failure JSON, and RTMPose `videoSha256` fixes are present
as uncommitted changes. All pre-existing tracked edits were copied to
`/tmp/petlens-day4-session1/originals` and verified byte-for-byte unchanged at
completion. Existing untracked work was preserved. No commits or pushes.

## Environment and startup

Node 24.21.0; README-specified pnpm 10.33.4. Missing API dependencies were
installed with the existing lockfile:

```bash
COREPACK_HOME=/tmp/petlens-day4-session1/corepack corepack pnpm@10.33.4 --filter @workspace/api-server... install --frozen-lockfile --store-dir /tmp/petlens-day4-session1/pnpm-store
```

The lockfile and package manifests were unchanged. No Python packages, ML
dependencies, or weights were installed or downloaded. Network access was
needed for Node dependencies; local socket access was needed for Express and
HTTP tests. Sandbox restrictions were retried with approved execution access.

The first live run used the server's default Python 3.14.2 / OpenCV 5.0.0:
`/api/readyz` returned HTTP 200, capability `opencv-motion`, pose unavailable.
S004 then returned HTTP 200 in 2.329191 seconds. The final live run explicitly
used the existing Python 3.11.18 environment, within the README's Python range,
with OpenCV 4.11.0 and the supported motion-only configuration:

```bash
SILVERPAWS_PYTHON=/workspaces/Petlens/.venv-canine-v2/bin/python PETLENS_MOTION_ONLY=true TMPDIR=/tmp/petlens-day4-session1/py311-runtime SILVERPAWS_UPLOAD_DIR=/tmp/petlens-day4-session1/py311-uploads HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 COREPACK_HOME=/tmp/petlens-day4-session1/corepack corepack pnpm@10.33.4 --filter @workspace/api-server run dev > /tmp/petlens-day4-session1/py311-server.log 2>&1
```

These are existing Python environments, not fresh requirements-file installs.
The final server was left running on port 8080 in motion-only mode.

## Exact successful HTTP command

Run from the repository root, after starting Express:

```bash
curl --silent --show-error --fail-with-body --max-time 120 -D /tmp/petlens-day4-session1/s004.headers -o /tmp/petlens-day4-session1/s004.json -w 'HTTP %{http_code}; total %{time_total}s; uploaded %{size_upload} bytes\n' -F 'video=@tests/Quantitative-Phenotyping-of-Duchenne-Muscular-Dystrophy-Dogs-by-Comprehensive-Gait-Analysis-and-pone.0059875.s004.ogv;type=video/ogg' -F 'petName=S004' http://127.0.0.1:8080/api/analyze
```

Python 3.11 run: **HTTP 200; 0.340459 seconds; 402199 multipart bytes**.
The Express log reports `Analysis completed`, request ID `1`, pipeline
`opencv-motion`, and subprocess duration 316 ms. Response values:

- 60 frames, 12 FPS, five seconds, 59 motion trace samples.
- Motion mean `0.005501`, standard deviation `0.000707`, coverage `1`.
- Pose keypoints, stride symmetry and asymmetry remain null.
- Both saved live responses independently passed the generated Zod schema and
  assertions for actual S004 measurements and the Python request ID.

This is picture-motion analysis. No RTMPose inference, canine pose accuracy,
contact prediction, or clinical gait measurement was tested in this session.

## Real HTTP failures and cleanup

Session-only script `/tmp/petlens-day4-session1/live_checks.py` exercised the
actual Express app, not a mocked route:

| Input | HTTP | Structured code |
| --- | --- | --- |
| Text file, `text/plain` | 400 | `UNSUPPORTED_VIDEO` |
| Undecodable bytes, `video/mp4` | 400 | `INVALID_VIDEO` |
| Real S004, Python site packages deliberately unavailable | 502 | `ANALYSIS_FAILED` |

The controlled failure used a second actual Express server on port 8081 and
the real CLI under `python3 -S`. Python started, failed importing `cv2`, emitted
failure JSON and exited 1; Express returned that understandable error. This
server was stopped cleanly. Application code was not modified to inject errors.

After success and each failure, checks waited for cleanup and found no
`petlens-clip-*` upload directories or `petlens-result-*` output directories.
The final Python 3.11 success also left neither. Evidence JSON/logs were saved
separately by the test client and are intentionally retained in `/tmp`.

## Focused verification

- Actual intended Express development build: passed.
- API suite: **59 passed**, including multipart, saved-result schema, readiness,
  upload cleanup, rate/capacity gates, and graceful shutdown. The sandbox run
  failed its two HTTP test files; the socket-enabled rerun passed all 59.
- Library declaration builds and API TypeScript check: passed:
  `node_modules/.bin/tsc -b lib/db lib/api-zod`, then
  `corepack pnpm@10.33.4 --filter @workspace/api-server typecheck`
  with the session's `COREPACK_HOME`.
- Python: **100 passed + 2 subtests** using the existing environment:

```bash
PYTHONPATH=src .venv-canine-v2/bin/python -m pytest -q tests/test_cli.py tests/test_motion_checkpoint.py tests/test_setup_check.py tests/test_features.py tests/test_motion_trace.py tests/test_gait_integration.py tests/test_pose_fallback.py tests/test_contact_features.py
```

An initial Python collection without `PYTHONPATH=src` failed to find
`petlens_gait`; the command above supplies the repository's source directory.
No complete expensive model suite, retraining, UI, or deployment test was run.

## Product readiness

The backend can support a **motion-only Evidence Replay prototype** with
video duration, a timed motion trace, and explicit unavailable pose/gait fields.
Two-video playback and frame-accurate source alignment were not tested. The
motion trace uses nominal FPS; the API does not expose original integer PTS
or RTMPose frame evidence.

**Single next priority:** wire the verified response into two-video Evidence
Replay and verify source-time alignment before claiming frame-accurate replay.
Only this verification document was added to the repository in this session.
