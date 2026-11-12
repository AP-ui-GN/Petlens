/** Real upload -> Express -> Python -> browser video/graph integration, no mocked API. */
import assert from 'node:assert/strict';
import { spawn, execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdtemp, mkdir, readFile, writeFile, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';
import { createServer } from 'node:net';

const exec = promisify(execFile);
const appRoot = resolve(import.meta.dirname, '..');
const repo = resolve(appRoot, '../..');
const source = process.env.PETLENS_REPLAY_VIDEO;
assert(source, 'Set PETLENS_REPLAY_VIDEO to an authorized local browser-playable dog video.');
const chromium = process.env.CHROMIUM_PATH ?? '/repl/tools/bin/chromium';
const evidence = process.env.PETLENS_REPLAY_EVIDENCE ?? await mkdtemp(join(tmpdir(), 'petlens-replay-'));
await mkdir(evidence, { recursive: true });
const owned = [];
let cdp;

async function freePort() {
  const server = createServer();
  await new Promise((yes, no) => { server.once('error', no); server.listen(0, '127.0.0.1', yes); });
  const port = server.address().port;
  await new Promise((yes) => server.close(yes));
  return port;
}
function launch(command, args, options = {}) {
  const child = spawn(command, args, { detached: true, stdio: ['ignore', 'pipe', 'pipe'], ...options });
  const output = [];
  child.stdout.on('data', (chunk) => output.push(chunk.toString()));
  child.stderr.on('data', (chunk) => output.push(chunk.toString()));
  owned.push({ child, output });
  return child;
}
async function until(check, message, ms = 30000) {
  const deadline = Date.now() + ms;
  while (Date.now() < deadline) {
    if (await check()) { console.log(`PASS: ${message}`); return; }
    await new Promise((yes) => setTimeout(yes, 100));
  }
  throw new Error(`Timed out: ${message}`);
}
function connect(url) {
  const socket = new WebSocket(url);
  let id = 0;
  const pending = new Map();
  const ready = new Promise((yes, no) => { socket.addEventListener('open', yes); socket.addEventListener('error', no); });
  socket.addEventListener('message', (event) => {
    const message = JSON.parse(event.data);
    const handler = pending.get(message.id);
    if (!handler) return;
    pending.delete(message.id);
    if (message.error) handler.reject(new Error(message.error.message)); else handler.resolve(message.result);
  });
  return {
    async send(method, params = {}) {
      await ready;
      return new Promise((resolve, reject) => { const requestId = ++id; pending.set(requestId, { resolve, reject }); socket.send(JSON.stringify({ id: requestId, method, params })); });
    },
    close() { socket.close(); },
  };
}
async function evaluate(expression) {
  const value = await cdp.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  assert(!value.exceptionDetails, JSON.stringify(value.exceptionDetails));
  return value.result?.value;
}
const videoSelector = '[data-testid="video-scrubber-video"]';
const video = `document.querySelector('${videoSelector}')`;
const selection = `document.querySelector('[data-testid="replay-selected-time"]')`;
async function screenshot(name) {
  const shot = await cdp.send('Page.captureScreenshot', { captureBeyondViewport: true });
  await writeFile(join(evidence, name), Buffer.from(shot.data, 'base64'));
}

try {
  const [apiPort, webPort, debugPort] = [await freePort(), await freePort(), await freePort()];
  const uploadDir = join(evidence, 'uploads');
  const runtimeDir = join(evidence, 'runtime');
  await mkdir(uploadDir, { recursive: true });
  await mkdir(runtimeDir, { recursive: true });
  launch(process.execPath, ['--enable-source-maps', 'artifacts/api-server/dist/index.mjs'], {
    cwd: repo,
    env: { ...process.env, PORT: String(apiPort), NODE_ENV: 'development', PETLENS_MOTION_ONLY: 'true',
      SILVERPAWS_PYTHON: process.env.SILVERPAWS_PYTHON ?? join(repo, '.venv-canine-v2/bin/python'),
      SILVERPAWS_UPLOAD_DIR: uploadDir, TMPDIR: runtimeDir, HF_HUB_OFFLINE: '1', TRANSFORMERS_OFFLINE: '1' },
  });
  launch(process.execPath, [join(appRoot, 'node_modules/vite/bin/vite.js'), '--config', 'vite.config.ts'], {
    cwd: appRoot, env: { ...process.env, PORT: String(webPort), API_PROXY_TARGET: `http://127.0.0.1:${apiPort}`, NODE_ENV: 'test' },
  });
  const origin = `http://127.0.0.1:${webPort}`;
  await until(async () => { try { return (await fetch(`${origin}/api/healthz`)).ok; } catch { return false; } }, 'Express and Vite ready');
  launch(chromium, ['--headless=new', '--no-sandbox', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--autoplay-policy=no-user-gesture-required', `--remote-debugging-port=${debugPort}`, `--user-data-dir=${join(evidence, 'chromium-profile')}`, 'about:blank']);
  let target;
  await until(async () => { try { target = (await (await fetch(`http://127.0.0.1:${debugPort}/json/list`)).json()).find((page) => page.type === 'page'); return Boolean(target?.webSocketDebuggerUrl); } catch { return false; } }, 'Chromium debugger');
  cdp = connect(target.webSocketDebuggerUrl);
  await cdp.send('Page.enable');
  await cdp.send('Runtime.enable');
  await cdp.send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1100, deviceScaleFactor: 1, mobile: false });
  await cdp.send('Page.navigate', { url: origin });
  await until(() => evaluate('Boolean(document.querySelector(".app-shell"))'), 'App mounted');
  const pet = { id: 'replay-dog', name: 'S004', species: 'Dog', breed: '', age: '', weight: '', notes: '', createdAt: '2026-11-12T00:00:00Z' };
  await evaluate(`localStorage.clear(); localStorage.setItem('silverpaws:pets', ${JSON.stringify(JSON.stringify([pet]))});`);
  await cdp.send('Page.navigate', { url: `${origin}/analyze` });
  await until(() => evaluate('Boolean(document.querySelector("[data-testid=input-walking-video]"))'), 'Upload input');
  const doc = await cdp.send('DOM.getDocument');
  const input = await cdp.send('DOM.querySelector', { nodeId: doc.root.nodeId, selector: '[data-testid="input-walking-video"]' });
  await cdp.send('DOM.setFileInputFiles', { nodeId: input.nodeId, files: [resolve(source)] });
  await until(() => evaluate('Boolean(document.querySelector("[data-testid=button-run-analysis]"))'), 'Review step');
  await evaluate('document.querySelector("[data-testid=button-run-analysis]").click()');
  await until(() => evaluate('Boolean(document.querySelector("[data-testid=evidence-replay]"))'), 'Real analysis result and replay', 60000);
  await until(() => evaluate(`${video}?.readyState >= 2 && !document.querySelector('[data-testid="motion-activity-time"]').disabled`), 'Native video ready and replay enabled');
  const record = await evaluate('JSON.parse(localStorage.getItem("silverpaws:analyses"))[0]');
  await writeFile(join(evidence, 'actual-analysis.json'), JSON.stringify(record, null, 2));
  assert.equal(record.pipeline, 'opencv-motion');
  assert.equal(record.measurements.motionTrace.timingSource, 'decoder');
  assert.equal(record.measurements.motionTrace.sampleCount, record.measurements.frameCount - 1);
  assert.equal(record.measurements.poseKeypoints, null);
  assert.equal(record.measurements.strideSymmetry, null);
  const points = record.measurements.motionTrace.points;
  const probe = JSON.parse((await exec('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-show_frames', '-show_entries', 'frame=best_effort_timestamp_time', '-of', 'json', resolve(source)])).stdout);
  const times = probe.frames.map((frame) => Number(frame.best_effort_timestamp_time));
  assert(times.length >= record.measurements.frameCount);
  let largestTimestampError = 0;
  for (let index = 0; index < points.length; index++) {
    const start = Math.floor(index * record.measurements.motionTrace.sampleCount / points.length);
    const end = Math.floor((index + 1) * record.measurements.motionTrace.sampleCount / points.length);
    const expected = (times[start] + times[end]) / 2;
    const error = Math.abs(points[index].timeSeconds - expected);
    assert(error <= 0.000051, `Sample ${index}: ${points[index].timeSeconds} vs ffprobe ${expected}`);
    largestTimestampError = Math.max(largestTimestampError, error);
  }
  await evaluate(`window.__replayFrames = []; ${video}.requestVideoFrameCallback(function frame(_, metadata) { window.__replayFrames.push({ time: ${video}.currentTime, mediaTime: metadata.mediaTime }); ${video}.requestVideoFrameCallback(frame); });`);
  const duration = await evaluate(`${video}.duration`);
  async function clickGraph(time) {
    await evaluate('document.querySelector("[data-testid=motion-activity-graph]").scrollIntoView({block:"center"})');
    const plot = await evaluate('(() => { const r = document.querySelector("[data-testid=motion-activity-graph] .recharts-cartesian-grid").getBoundingClientRect(); return { x:r.x, y:r.y, width:r.width, height:r.height }; })()');
    const x = plot.x + Math.max(0.001, Math.min(0.999, time / duration)) * plot.width;
    const y = plot.y + plot.height / 2;
    await cdp.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y });
    await cdp.send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 });
    await cdp.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 1 });
    const nearest = points.reduce((a, b) => Math.abs(b.timeSeconds - time) < Math.abs(a.timeSeconds - time) ? b : a);
    await until(() => evaluate(`Math.abs(${video}.currentTime - ${nearest.timeSeconds}) < 0.00015 && ${video}.paused`), `Graph click seeks to ${nearest.timeSeconds}`);
    await until(() => evaluate(`${selection}.textContent.includes('${nearest.timeSeconds.toFixed(4)}')`), 'Graph selection reflects completed seek');
    return nearest;
  }
  await clickGraph(0);
  await clickGraph(duration);
  const middle = await clickGraph(points[Math.floor(points.length / 2)].timeSeconds);
  await until(() => evaluate(`window.__replayFrames.some(f => Math.abs(f.time - ${middle.timeSeconds}) < 0.001)`), 'Rendered video frame after graph selection');
  const rendered = await evaluate(`window.__replayFrames.findLast(f => Math.abs(f.time - ${middle.timeSeconds}) < 0.001)`);
  const nearestFrameError = Math.min(...times.map((time) => Math.abs(time - rendered.mediaTime)));
  assert(nearestFrameError < 0.001, 'Rendered frame uses the original media presentation timeline');
  const nearestSourceTime = times.reduce((a, b) => Math.abs(b - middle.timeSeconds) < Math.abs(a - middle.timeSeconds) ? b : a);
  const maxSourceInterval = Math.max(...times.slice(1).map((time, index) => time - times[index]));
  assert(Math.abs(rendered.mediaTime - nearestSourceTime) <= maxSourceInterval + 0.001);
  await screenshot('evidence-replay.png');
  await evaluate(`${video}.muted = true; ${video}.play()`);
  await until(() => evaluate(`${video}.currentTime > ${middle.timeSeconds + 0.4} && parseFloat(${selection}.textContent.match(/Video ([0-9.]+)/)[1]) > ${middle.timeSeconds + 0.3}`), 'Playback advances graph selection');
  await evaluate(`${video}.pause()`);
  const playback = await evaluate(`({video: ${video}.currentTime, selected: parseFloat(${selection}.textContent.match(/Video ([0-9.]+)/)[1])})`);
  assert(Math.abs(playback.video - playback.selected) < 0.3, 'Graph follows native timeupdate events');
  await clickGraph(duration);
  await evaluate(`${video}.play()`);
  await until(() => evaluate(`${video}.ended`), 'Playback reaches the source boundary');
  await until(() => evaluate(`Math.abs(parseFloat(${selection}.textContent.match(/Video ([0-9.]+)/)[1]) - ${duration}) < 0.01`), 'Graph reaches the end boundary');
  await evaluate('document.querySelector("[data-testid=link-history]").click()');
  await until(() => evaluate('Boolean(document.querySelector("[data-testid^=link-history-analysis-]"))'), 'History list');
  await evaluate('document.querySelector("[data-testid^=link-history-analysis-]").click()');
  await until(() => evaluate(`${video}?.readyState >= 2`), 'Source file survives client navigation');
  await evaluate('window.__replayReloadMarker = true');
  await cdp.send('Page.reload');
  await until(() => evaluate('!window.__replayReloadMarker && Boolean(document.querySelector("[data-testid=evidence-replay]"))'), 'Reloaded saved observation');
  assert(await evaluate('document.querySelector("[data-testid=motion-activity-time]").disabled'));
  assert.equal(await evaluate('Number(document.querySelector("[data-testid=motion-activity-time]").max)'),
    Math.max(record.measurements.durationSeconds, points.at(-1).timeSeconds, 1),
    'The read-only graph includes source times beyond an older nominal-FPS duration estimate');
  assert.equal(await evaluate(`Boolean(${video})`), false, 'Object URL is not persisted as a replacement source file');
  await evaluate(`{ const records=JSON.parse(localStorage.getItem('silverpaws:analyses')); delete records[0].measurements.motionTrace.timingSource; records[0].measurements.motionTrace.points = [records[0].measurements.motionTrace.points[0]]; localStorage.setItem('silverpaws:analyses',JSON.stringify(records)); window.__replayReloadMarker=true; }`);
  await cdp.send('Page.reload');
  await until(() => evaluate('!window.__replayReloadMarker && document.querySelector("[data-testid=evidence-replay]")?.textContent.includes("Source timing is unverified")'), 'Legacy timing and single-sample fallback');
  assert(await evaluate('document.querySelector("[data-testid=motion-activity-time]").disabled'));
  assert(await evaluate('Boolean(document.querySelector("[data-testid=motion-activity-graph] .recharts-line-dot"))'));
  // Older/missing traces use the genuine stored result with unavailable data removed.
  await evaluate(`{ const records=JSON.parse(localStorage.getItem('silverpaws:analyses')); delete records[0].measurements.motionTrace; localStorage.setItem('silverpaws:analyses',JSON.stringify(records)); }`);
  await evaluate('window.__replayReloadMarker = true');
  await cdp.send('Page.reload');
  await until(() => evaluate('!window.__replayReloadMarker && document.querySelector("[data-testid=evidence-replay]")?.textContent.includes("No timed motion samples")'), 'Missing trace fallback');
  await until(async () => (await readdir(uploadDir)).length === 0 && !(await readdir(runtimeDir)).some((name) => name.startsWith('petlens-result-')), 'API temporary file cleanup');
  console.log(JSON.stringify({ status: 'PASS', source: resolve(source), frames: record.measurements.frameCount,
    samples: record.measurements.motionTrace.sampleCount, plotted: points.length, largestTimestampError,
    renderedFrame: rendered, playback, checks: ['actual upload and analysis', 'ffprobe source timestamps', 'graph clicks at start/middle/end', 'native rendered frame', 'playback follows graph', 'end boundary', 'history navigation retains source', 'reload and missing trace fallback', 'temporary upload/result cleanup'], evidence }, null, 2));
} catch (error) {
  if (cdp) { try { await screenshot('failure.png'); } catch {} }
  throw error;
} finally {
  cdp?.close();
  for (const { child } of owned.reverse()) {
    try { process.kill(-child.pid, 'SIGTERM'); } catch {}
  }
  for (let index = 0; index < owned.length; index++) {
    await writeFile(join(evidence, `process-${index}.log`), owned[index].output.join(''));
  }
  await rm(join(evidence, 'chromium-profile'), { recursive: true, force: true, maxRetries: 5, retryDelay: 100 });
}
