import { execFile, spawn } from 'node:child_process';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { promisify } from 'node:util';
import { createServer } from 'node:net';

const execFileAsync = promisify(execFile);
const appRoot = resolve(import.meta.dirname, '..');
const appOrigin = 'http://127.0.0.1:4173';
const chromiumPath = process.env.CHROMIUM_PATH ?? '/repl/tools/bin/chromium';

const pet = {
  id: 'pet-report-test',
  name: 'Mabel',
  species: 'Dog',
  breed: 'Spaniel',
  age: '7',
  weight: '9.4',
  notes: '',
  createdAt: '2026-09-01T12:00:00.000Z',
};

const completeAnalysis = {
  id: 'analysis-report-complete',
  petId: pet.id,
  fileName: 'mabel-garden-walk.mp4',
  durationSeconds: 18,
  createdAt: '2026-09-10T12:00:00.000Z',
  status: 'complete',
  strideSymmetryScore: 86,
  asymmetryPercent: 7,
  confidence: 78,
  observation: 'Mabel’s stride looked broadly even in this clip.',
  limitations: 'This is an educational observation from one camera angle. It is not a diagnosis.',
  measurements: {
    poseKeypoints: [{ name: 'left_hip', x: 0.4, y: 0.5, confidence: 0.9 }],
    frameCount: 50,
    durationSeconds: 18,
    meanKeypointConfidence: 0.9,
    motionMean: 0.1,
    motionStd: 0.02,
    motionCoverage: 0.8,
    symmetryReliable: true,
  },
  framesUsed: 45,
  framesTotal: 50,
  modelConfidence: 0.9,
  source: 'Test video library',
  license: 'CC BY 4.0',
  sourceUrl: 'https://example.com/test-video',
};

const missingOptionalAnalysis = {
  id: 'analysis-report-fallbacks',
  petId: pet.id,
  fileName: 'mabel-living-room.mp4',
  durationSeconds: 9,
  createdAt: '2026-09-11T12:00:00.000Z',
  status: 'complete',
  observation: 'No clear difference was saved for this clip.',
};

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function getFreePort() {
  const server = createServer();
  await new Promise((resolvePromise, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolvePromise);
  });
  const { port } = server.address();
  await new Promise((resolvePromise) => server.close(resolvePromise));
  return port;
}

async function waitForHttp(url, timeoutMs = 30_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // The dev server is still starting.
    }
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 200));
  }
  throw new Error(`Timed out waiting for ${url}`);
}

async function waitForDebugger(port, timeoutMs = 30_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/list`);
      const targets = await response.json();
      const page = targets.find((target) => target.type === 'page' && target.webSocketDebuggerUrl);
      if (page) return page.webSocketDebuggerUrl;
    } catch {
      // Chromium is still starting.
    }
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 200));
  }
  throw new Error('Timed out waiting for Chromium remote debugging');
}

function connectToCdp(webSocketUrl) {
  const socket = new WebSocket(webSocketUrl);
  const pending = new Map();
  let nextId = 0;

  const connected = new Promise((resolvePromise, reject) => {
    socket.addEventListener('open', () => resolvePromise());
    socket.addEventListener('error', reject);
  });

  socket.addEventListener('message', (event) => {
    const message = JSON.parse(event.data);
    if (!message.id) return;
    const request = pending.get(message.id);
    if (!request) return;
    pending.delete(message.id);
    if (message.error) request.reject(new Error(message.error.message));
    else request.resolve(message.result);
  });

  return {
    async send(method, params = {}) {
      await connected;
      const id = ++nextId;
      return new Promise((resolvePromise, reject) => {
        pending.set(id, { resolve: resolvePromise, reject });
        socket.send(JSON.stringify({ id, method, params }));
      });
    },
    close() {
      socket.close();
    },
  };
}

async function evaluate(cdp, expression) {
  const result = await cdp.send('Runtime.evaluate', {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.text ?? 'Browser evaluation failed');
  }
  return result.result?.value;
}

async function waitFor(cdp, expression, timeoutMs = 15_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await evaluate(cdp, expression)) return;
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 150));
  }
  throw new Error(`Timed out waiting for browser condition: ${expression}`);
}

async function waitForDownload(downloadDirectory, beforeFiles, extension = '.pdf') {
  const deadline = Date.now() + 15_000;
  while (Date.now() < deadline) {
    const files = await readdir(downloadDirectory);
    const downloaded = files.find((file) =>
      file.endsWith(extension) && !beforeFiles.has(file),
    );
    if (downloaded) return join(downloadDirectory, downloaded);
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 150));
  }
  throw new Error(`Timed out waiting for the ${extension} download`);
}

function stopProcess(child) {
  return new Promise((resolvePromise) => {
    if (child.exitCode !== null || child.signalCode !== null) {
      resolvePromise();
      return;
    }
    const finish = () => resolvePromise();
    child.once('exit', finish);
    child.kill('SIGTERM');
    setTimeout(() => {
      if (child.exitCode === null && child.signalCode === null) child.kill('SIGKILL');
      resolvePromise();
    }, 2_000);
  });
}

function assertReport(pdfBytes, expected) {
  const pdf = pdfBytes.toString('latin1');
  const searchablePdf = pdf.replace(/\\([()\\])/g, '$1');
  assert(pdf.startsWith('%PDF-1.4'), 'downloaded report is not a PDF');
  assert(pdf.endsWith('%%EOF'), 'downloaded report is missing the PDF trailer');
  assert(pdf.length > 1_000, 'downloaded report is unexpectedly small');

  const rawIndex = searchablePdf.indexOf('Raw measurements');
  const interpretationIndex = searchablePdf.indexOf('Interpretation');
  assert(rawIndex >= 0, 'report is missing the Raw measurements section');
  assert(interpretationIndex > rawIndex, 'Interpretation does not follow Raw measurements');
  assert(searchablePdf.indexOf('Sources and licensing') > interpretationIndex, 'report is missing sources after Interpretation');
  assert(searchablePdf.includes(expected.source), `report is missing source text: ${expected.source}`);
  assert(searchablePdf.includes(expected.license), `report is missing license text: ${expected.license}`);
  assert(searchablePdf.includes('PetLens AI is experimental educational software'), 'report is missing experimental language');
  assert(searchablePdf.includes('not a medical diagnosis'), 'report is missing no-diagnosis language');
  assert(searchablePdf.includes('cannot rule out'), 'report is missing cautious limitation language');
  assert(searchablePdf.includes('pain'), 'report is missing pain caution language');
  assert(searchablePdf.includes('injury'), 'report is missing injury caution language');
  assert(searchablePdf.includes('Pet movement observation report'), 'report is missing the movement observation summary');
  assert(searchablePdf.includes('Pet Name: Mabel'), 'report is missing the pet name');
  assert(searchablePdf.includes('Gait Symmetry Score: 86/100'), 'report is missing the gait symmetry score');
  assert(searchablePdf.includes('Hip Extension Angle: Not measured'), 'report invents or omits the hip extension angle status');
  assert(searchablePdf.includes('Stifle Flexion Angle: Not measured'), 'report invents or omits the stifle flexion angle status');
  assert(searchablePdf.includes('Plain-language observation:'), 'report is missing the plain-language note');
  assert(searchablePdf.includes('Generated by PetLens AI.'), 'report is missing the requested clinical disclaimer');
  assert(searchablePdf.includes('not a veterinary diagnosis or a substitute for veterinary care.'), 'report is missing the disclaimer conclusion');
  for (const fallback of expected.fallbacks ?? []) {
    assert(searchablePdf.includes(fallback), `report is missing fallback text: ${fallback}`);
  }
}

async function assertReportPreview(cdp, expected) {
  await waitFor(cdp, 'Boolean(document.querySelector(".vet-report-print-root"))');
  const previewText = await evaluate(cdp, 'document.querySelector(".vet-report-print-root").innerText');
  for (const text of expected.text) {
    assert(previewText.includes(text), `report preview is missing text: ${text}`);
  }
  assert(await evaluate(cdp, 'document.querySelectorAll(".vet-report-page").length') === 2, 'report preview does not contain two pages');

  const { data } = await cdp.send('Page.printToPDF', { printBackground: true });
  const pdf = Buffer.from(data, 'base64');
  const pageCount = pdf.toString('latin1').match(/\/Type \/Page\b/g)?.length ?? 0;
  assert(pdf.subarray(0, 5).toString() === '%PDF-', 'print preview did not produce a PDF');
  assert(pageCount === 2, `print preview produced ${pageCount} pages instead of two`);
}

async function run() {
  const downloadDirectory = await mkdtemp(join(tmpdir(), 'silverpaws-report-'));
  const serverPort = await getFreePort();
  const debugPort = await getFreePort();
  const server = spawn('pnpm', ['run', 'dev'], {
    cwd: appRoot,
    env: {
      ...process.env,
      BASE_PATH: '/',
      PORT: String(serverPort),
      NODE_ENV: 'test',
    },
    detached: true,
    stdio: ['ignore', 'ignore', 'ignore'],
  });
  const browser = spawn(chromiumPath, [
    '--headless=new',
    '--no-sandbox',
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    `--remote-debugging-port=${debugPort}`,
    `--user-data-dir=${join(downloadDirectory, 'browser-profile')}`,
    'about:blank',
  ], { detached: true, stdio: ['ignore', 'ignore', 'ignore'] });

  let cdp;
  try {
    await waitForHttp(`${appOrigin.replace('4173', String(serverPort))}/`);
    const webSocketUrl = await waitForDebugger(debugPort);
    cdp = connectToCdp(webSocketUrl);
    await cdp.send('Page.enable');
    await cdp.send('Runtime.enable');
    await cdp.send('Page.setDownloadBehavior', {
      behavior: 'allow',
      downloadPath: downloadDirectory,
    });
    const origin = appOrigin.replace('4173', String(serverPort));
    const savedAnalyses = [completeAnalysis, missingOptionalAnalysis];
    await cdp.send('Page.navigate', { url: `${origin}/history/${completeAnalysis.id}` });
    await waitFor(cdp, `location.pathname.endsWith('/history/${completeAnalysis.id}')`);
    await evaluate(cdp, `localStorage.setItem('silverpaws:pets', ${JSON.stringify(JSON.stringify([pet]))}); localStorage.setItem('silverpaws:analyses', ${JSON.stringify(JSON.stringify(savedAnalyses))}); location.reload();`);
    await waitFor(cdp, `Boolean(document.querySelector('[data-testid="button-download-report-${completeAnalysis.id}"]'))`);

    await evaluate(cdp, `document.querySelector('[data-testid="button-vet-summary-report-${completeAnalysis.id}"]').click()`);
    await assertReportPreview(cdp, {
      text: [
        'SILVER PAWS AI — Movement Observation Summary',
        completeAnalysis.fileName,
        completeAnalysis.observation,
        'Important limitations.',
      ],
    });
    await evaluate(cdp, `document.querySelector('[aria-label="Close report preview"]').click()`);

    let filesBefore = new Set(await readdir(downloadDirectory));
    await evaluate(cdp, `document.querySelector('[data-testid="button-download-report-${completeAnalysis.id}"]').click()`);
    let reportPath = await waitForDownload(downloadDirectory, filesBefore);
    assertReport(await readFile(reportPath), {
      source: completeAnalysis.source,
      license: completeAnalysis.license,
    });

    await evaluate(cdp, `document.querySelector('[data-testid="button-export-telemetry-${completeAnalysis.id}"]').click()`);
    await waitFor(cdp, `Boolean(document.querySelector('[data-testid="button-download-telemetry-csv-${completeAnalysis.id}"]'))`);
    filesBefore = new Set(await readdir(downloadDirectory));
    await evaluate(cdp, `document.querySelector('[data-testid="button-download-telemetry-csv-${completeAnalysis.id}"]').click()`);
    const csvPath = await waitForDownload(downloadDirectory, filesBefore, '.csv');
    const csv = await readFile(csvPath, 'utf8');
    assert(csvPath.endsWith(`petlens-telemetry-${completeAnalysis.id}.csv`), 'telemetry CSV has an unexpected filename');
    assert(csv.startsWith('"Timestamp/Frame","Metric","Value","Unit","Status"'), 'telemetry CSV has an unexpected header');
    assert(csv.includes('"Mean across 50 frames","Landmark left_hip x","0.4","normalized coordinate","measured"'), 'telemetry CSV is missing the saved mean landmark');
    assert(csv.includes('"Hip extension angle","Not measured","degrees","not_computed"'), 'telemetry CSV should not invent an angle');

    await evaluate(cdp, `document.querySelector('[data-testid="button-export-telemetry-${completeAnalysis.id}"]').click()`);
    await waitFor(cdp, `Boolean(document.querySelector('[data-testid="button-download-telemetry-json-${completeAnalysis.id}"]'))`);
    filesBefore = new Set(await readdir(downloadDirectory));
    await evaluate(cdp, `document.querySelector('[data-testid="button-download-telemetry-json-${completeAnalysis.id}"]').click()`);
    const jsonPath = await waitForDownload(downloadDirectory, filesBefore, '.json');
    const telemetry = JSON.parse(await readFile(jsonPath, 'utf8'));
    assert(jsonPath.endsWith(`petlens-telemetry-${completeAnalysis.id}.json`), 'telemetry JSON has an unexpected filename');
    assert.equal(telemetry.observation.analysisId, completeAnalysis.id);
    assert.equal(telemetry.measurements.poseKeypoints[0].name, 'left_hip');
    assert.equal(telemetry.computedAngles.stifleFlexion.status, 'not_computed');
    assert.equal(telemetry.timeSeriesMetadata.rawPerFrameSeriesAvailable, false);

    await cdp.send('Page.navigate', { url: `${origin}/history/${missingOptionalAnalysis.id}` });
    await waitFor(cdp, `location.pathname.endsWith('/history/${missingOptionalAnalysis.id}')`);
    await waitFor(cdp, `Boolean(document.querySelector('[data-testid="button-download-report-${missingOptionalAnalysis.id}"]'))`);
    await evaluate(cdp, `document.querySelector('[data-testid="button-vet-summary-report-${missingOptionalAnalysis.id}"]').click()`);
    await assertReportPreview(cdp, {
      text: [
        'SILVER PAWS AI — Movement Observation Summary',
        missingOptionalAnalysis.fileName,
        'No plain-language interpretation was saved for this observation.',
        'Not measured',
      ],
    });
    await evaluate(cdp, `document.querySelector('[aria-label="Close report preview"]').click()`);

    filesBefore = new Set(await readdir(downloadDirectory));
    await evaluate(cdp, `document.querySelector('[data-testid="button-download-report-${missingOptionalAnalysis.id}"]').click()`);
    reportPath = await waitForDownload(downloadDirectory, filesBefore);
    assertReport(await readFile(reportPath), {
      source: 'User-provided local video (not uploaded by PetLens AI)',
      license: 'Not provided; confirm sharing rights before publishing this media',
      fallbacks: [
        'User-provided local video (not uploaded by PetLens AI)',
        'Not provided; confirm sharing rights before publishing this media',
      ],
    });

    console.log('Report preview, PDF download, and telemetry browser tests passed.');
  } finally {
    cdp?.close();
    await Promise.all([stopProcess(browser), stopProcess(server)]);
    await rm(downloadDirectory, { recursive: true, force: true });
  }
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});