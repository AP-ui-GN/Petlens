# Host the analysis API

The web app sends a walking clip to this API. The API runs the Python
pipeline and deletes the upload. Nothing here is an account system.

In development the Vite server proxies `/api` to the API (`API_PROXY_TARGET`,
default `http://127.0.0.1:8080`). In production, serve the web build and the
API from one origin, or point the web build at the API URL with the client
base-URL setting. Do not bake server secrets into the web build.

This document prepares a container and the steps for one host. It does not
mean a server is already running, and it does not include a public URL.

## What the image contains

`Dockerfile` uses Node 24 LTS and Debian bookworm's Python 3.11. The same pins
support Python 3.10–3.12. The image installs `opencv-python-headless` (the
laptop file `requirements.txt` uses `opencv-python`, which expects a display),
NumPy, SciPy, CPU torch, and transformers at the versions in
`requirements-docker.txt`.

While the image builds, `scripts/cache_models.py` downloads the dog detector
and the pose model into `/app/models/hf` (`HF_HOME`). A later request reuses
that cache.

The container listens on port 8080 and defaults to a ten-minute `ANALYSIS_TIMEOUT_MS` ceiling, matching the documented API behavior. Invalid timeout values fall back to the ten-minute default; valid overrides are bounded from one second to one hour. `GET /api/healthz` returns `{ "status": "ok" }` and is a liveness check only. `GET /api/readyz` checks the local Python/OpenCV setup using a cached, no-download probe. It returns HTTP 200 when the motion-only fallback is available, even if optional pose weights are absent; the response explains which capabilities are available. It returns HTTP 503 when the required fallback is unavailable. Readiness is cached for up to 60 seconds.
That path stays on plain HTTP so the Docker healthcheck can call localhost.
Every other path requires HTTPS when `NODE_ENV=production`. The host's proxy
sets `X-Forwarded-Proto: https`. Local `docker compose` keeps
`NODE_ENV=development`, so `http://127.0.0.1:8080` works on your machine.

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `PORT` | `8080` | Listen port |
| `NODE_ENV` | unset | `production` turns on the HTTPS check |
| `MAX_UPLOAD_MB` | `60` | Largest clip accepted; configurable integer is bounded to 1–120 MB |
| `TRUST_PROXY` | unset | Set to `1` only behind a proxy that sets `X-Forwarded-Proto` |
| `ALLOWED_ORIGINS` | Development defaults when unset outside production; empty allow-list in production | Comma-separated exact browser origins, e.g. `https://app.example.com`; do not include paths. Production web clients must be listed explicitly. |
| `ANALYSIS_TIMEOUT_MS` | `600000` | Stop the pipeline after this many milliseconds. A motion result written before pose starts is returned if pose is still running |
| `SHUTDOWN_TIMEOUT_MS` | `15000` | Grace period for in-flight requests during SIGTERM/SIGINT before active Python analysis is stopped |
| `ANALYZE_RATE_LIMIT_PER_MINUTE` | `10` | Analyses allowed per client address each minute |
| `ANALYZE_MAX_CONCURRENT` | `1` | Concurrent analysis requests; configured integer is bounded to 1–4. Defaults to one because a CPU pose process measured about 1.6 GB RSS |
| `SILVERPAWS_PYTHON` | `/opt/venv/bin/python` in the image | Python that runs the pipeline |
| `SILVERPAWS_REPO_ROOT` | `/app` in the image | Where `gait_engine` and `scripts` live |
| `HF_HOME` | `/app/models/hf` in the image | Detector and pose weight cache |
| `SILVERPAWS_LLM_URL` | unset | Optional rewrite endpoint. Leave unset to stay on the rule-based note |
| `SILVERPAWS_LLM_KEY` | unset | Bearer token for that endpoint. Keep it on the server |
| `SILVERPAWS_LLM_MODEL` | unset | Model name. Required, with the URL, before a rewrite is attempted |

No API key is required for a clip to be measured.

The optional text-rewrite provider is protected by a small in-process circuit
breaker: after three consecutive transport/provider failures, rewrite calls are
skipped for 30 seconds and one retry probe is permitted after cooldown. The
rule-based observation continues to work while the provider is unavailable.
This is process-local; it is not a shared distributed breaker.


## Browser origins and response headers

The API uses an explicit CORS origin allow-list. In development, the default
origins are `http://127.0.0.1:4173` and `http://localhost:4173`. In production,
set `ALLOWED_ORIGINS` to the exact HTTPS origin(s) of the deployed web app,
separated by commas (for example, `https://app.example.com`). Do not include
URL paths. If production origins are not configured, browser origins are not
allowed to read API responses. Origin-less native clients are not subject to
browser CORS; CORS is not authentication.

The API also sets conservative content-sniffing, framing, referrer, and
cross-domain policy headers. HSTS is returned only for requests recognized as
HTTPS in production. Configure `TRUST_PROXY=1` only when the service sits behind
a trusted proxy that sets forwarded headers correctly.

Copy `.env.example` for the local configuration reference, and replace local
origins with your real web origin before deploying.

## Memory

Measured on this machine (Linux, CPU, Python 3.12) on October 21, 2026.
The clip was not one continuous recording. A 5-second side-view file
(960×544, about 12 fps, CC BY 3.0, Wikimedia Commons, PLOS supplementary
s003) was repeated with ffmpeg to 15.000 seconds at 30 fps (450 frames).

`python scripts/time_clip.py` on that file:

| Stage | Seconds |
| --- | --- |
| Sample frames | 0.949 |
| Pose, including weight load | 39.162 |
| Gait math | 0.015* |
| Total | 40.127* |

Peak RSS was 1665.3 MB. A separate one-shot `python scripts/analyze_clip.py`
of the same file returned `pipeline: dog-pose` in 37.543 seconds.

**Benchmark correction (October 22, 2026):** the old `time_clip.py` called the
AP-10K gait formulas even though this checkpoint reports `coco-17`. The
`0.015` gait time is therefore not a valid dog-gait measurement, and the
`40.127` total includes that unsupported diagnostic calculation; do not use
it as a production-request latency benchmark. [PR #20](https://github.com/AP-ui-GN/Silver-Paws-AI/pull/20)
adds a schema guard: on the current COCO-17 head, the script prints
`gait_seconds not_measured`. A comparable timing run has not yet been
recorded.

*These are historical measurements from the previous script behavior.*

A new process that only loaded both models, and did not analyze a clip,
took 4.02 seconds of wall time (3.552 seconds after the process had started).
That is under 20 seconds, so the API still starts Python once per request.
No persistent worker was added.

The API handles SIGTERM/SIGINT by stopping new accepts, allowing in-flight requests to drain, and terminating remaining Python analysis processes after `SHUTDOWN_TIMEOUT_MS`. This checkout's local environment does not have the `docker` command, so local image build and memory measurements were not performed. GitHub Actions later built and smoke-tested the image; that synthetic run did not measure hosted memory.
1665 MB is this CPU run, not a measurement from a hosted container.

To see what a real clip uses:

1. Run one analysis against the hosted API.
2. On a machine with Docker, run `docker stats` and read the `MEM USAGE` column while that request is in progress.
3. On Render, open the service metrics and read memory for the same request.

If the process is killed for running out of memory, raise the plan above 2 GB and repeat one clip. Do not guess a higher number until you have seen a kill or a peak.

## Local Docker

From the repository root, when Docker is installed:

```bash
docker compose up --build
```

Then open `http://127.0.0.1:8080/api/healthz`.

This environment did not have a `docker` command, so this image was not built here.

## Hosted Docker/API smoke check

On October 22, 2026, [the main-branch container-smoke workflow](https://github.com/AP-ui-GN/Silver-Paws-AI/actions/runs/39818601906) successfully built the Docker image, checked `/api/healthz` and `/api/readyz`, and submitted a generated synthetic motion clip to `POST /api/analyze`.

The fixture was a moving-shape video, not a dog. This verifies container packaging, readiness, and the API-to-Python response path only. It does not validate canine pose accuracy, a real dog-walk through the browser UI, a production deployment, or peak hosted memory.

## Deploy on Render

Render is the host described here because a Docker web service, a health check, and HTTPS are all in one place. Fly.io or Railway can run the same Dockerfile. None of them has been given this project.

1. Push the repository to GitHub.
2. In Render, create a **Web Service** and choose **Docker**. Set the root to the repository root so `Dockerfile` is used.
3. Set the health check path to `/api/healthz`.
4. Choose an instance with at least 2 GB of RAM.
5. Set `NODE_ENV` to `production` and set any other variables from the table. Leave the language-model variables empty unless you have a provider.
6. Deploy. Render serves HTTPS. The image build caches the detector and the pose model, so the first request should not download them.
7. Copy the `https://` address Render shows. Serve the web build from that origin, or point the web build at it. Do not invent an address in the repo.

## No-cost motion-only Render preview

Render offers a Free web-service plan for hobby projects, but it has only
512 MB of memory and can sleep after 15 minutes without traffic. It is not a
production service tier. The full image above installs large pose models and
requires more memory; do not deploy it on Free.

For a no-cost preview, the repository includes `render.yaml` and
`Dockerfile.motion-only`. In Render, create a new **Blueprint** from this
GitHub repository and select the `petlens-motion-api` service. Confirm the
compute plan is **Free** before applying the Blueprint. The image installs
only OpenCV dependencies, does not download detector/pose weights, and forces
the API to skip pose even if a request is sent with pose enabled. The result
is frame-to-frame picture motion only; stride, joint, and OA measurements
remain unavailable. The free service may take about a minute to wake after
being idle.

After Render finishes deploying, copy the service's HTTPS URL. Check
`<service-url>/api/healthz` and `<service-url>/api/readyz`; readiness should
report `opencv-motion`. Then set that base URL as `EXPO_PUBLIC_API_URL` in the
EAS `production` environment before building the APK. Do not include `/api`
at the end of the base URL. A change to this environment value requires a new
APK build.

Render's Free plan has monthly included usage limits for instance hours,
outbound bandwidth, and build minutes. Review the current limits in the
Render dashboard before applying the Blueprint. Render documents that without
a payment method, services are suspended rather than billed when applicable
included usage is exhausted. Do not select a paid compute plan or add a
payment method just to deploy this preview.

The web build does not contain `SILVERPAWS_LLM_KEY` or any other server secret.
