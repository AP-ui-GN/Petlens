import assert from 'node:assert/strict';
import { test } from 'node:test';

import { attemptAnalysis, createSubmissionGate, type AttemptDeps } from '../src/lib/analysis-attempt.ts';

type Clip = { uri: string; name: string };
const clip: Clip = { uri: 'content://media/video/42', name: 'walk.mp4' };

function makeDeps(overrides: Partial<AttemptDeps<Clip, string>> = {}) {
  const calls: string[] = [];
  const deps: AttemptDeps<Clip, string> = {
    isReadable: async () => true,
    resolveUrl: async () => 'https://api.example.test',
    request: async (_url, chosen) => {
      calls.push(chosen.uri);
      return 'result';
    },
    describeError: (error) => (error instanceof Error ? error.message : 'unknown'),
    ...overrides,
  };
  return { deps, calls };
}

test('a failed upload followed by a retry makes a second request with the same clip', async () => {
  let attempt = 0;
  const { deps, calls } = makeDeps({
    request: async (_url, chosen) => {
      calls.push(chosen.uri);
      attempt += 1;
      if (attempt === 1) throw new Error('Unable to connect');
      return 'real response';
    },
  });

  const first = await attemptAnalysis(clip, deps);
  assert.deepEqual(first, { kind: 'failed', message: 'Unable to connect' });

  const second = await attemptAnalysis(clip, deps);
  assert.deepEqual(second, { kind: 'done', result: 'real response' });
  assert.deepEqual(calls, [clip.uri, clip.uri]);
});

test('a second failure stays an error', async () => {
  const { deps, calls } = makeDeps({
    request: async (_url, chosen) => {
      calls.push(chosen.uri);
      throw new Error('Unable to connect');
    },
  });
  assert.equal((await attemptAnalysis(clip, deps)).kind, 'failed');
  assert.equal((await attemptAnalysis(clip, deps)).kind, 'failed');
  assert.equal(calls.length, 2);
});

test('an unreadable clip is reported without contacting the server', async () => {
  const { deps, calls } = makeDeps({ isReadable: async () => false });
  assert.deepEqual(await attemptAnalysis(clip, deps), { kind: 'unreadable' });
  assert.equal(calls.length, 0);
});

test('a missing server address is reported without uploading', async () => {
  const { deps, calls } = makeDeps({ resolveUrl: async () => null });
  assert.deepEqual(await attemptAnalysis(clip, deps), { kind: 'no-server' });
  assert.equal(calls.length, 0);
});

test('upload progress is passed through', async () => {
  const seen: number[] = [];
  const { deps } = makeDeps({
    request: async (_url, _clip, onUploadProgress) => {
      onUploadProgress(0.5);
      onUploadProgress(1);
      return 'ok';
    },
  });
  await attemptAnalysis(clip, deps, (fraction) => seen.push(fraction));
  assert.deepEqual(seen, [0.5, 1]);
});

test('the gate refuses a second submission until the first leaves', () => {
  const gate = createSubmissionGate();
  assert.equal(gate.tryEnter(), true);
  assert.equal(gate.tryEnter(), false);
  assert.equal(gate.running, true);
  gate.leave();
  assert.equal(gate.tryEnter(), true);
});

test('rapid taps during the readability check start only one upload', async () => {
  const gate = createSubmissionGate();
  let release: () => void = () => {};
  const readable = new Promise<boolean>((resolve) => {
    release = () => resolve(true);
  });
  const { deps, calls } = makeDeps({ isReadable: () => readable });

  async function tap() {
    if (!gate.tryEnter()) return null;
    try {
      return await attemptAnalysis(clip, deps);
    } finally {
      gate.leave();
    }
  }

  const taps = [tap(), tap(), tap()];
  release();
  const outcomes = await Promise.all(taps);
  assert.equal(outcomes.filter((outcome) => outcome !== null).length, 1);
  assert.equal(calls.length, 1);
});
