/**
 * HTML for expo-print. The sections follow the web PDF: measurements, then
 * interpretation, then the limits. Nulls stay "Not measured".
 */

import { aiUseResultLines } from './ai-use.ts';
import { EMERGENCY_NOTE, SAFETY_DISCLAIMER } from './disclaimers.ts';
import { PIPELINE_LABELS, formatDateTime, formatMeasure } from './format.ts';
import type { Analysis, Pet } from './types.ts';
import { isDemoWalk } from './walks.ts';

function aiUseSection(analysis: Analysis): string {
  if (isDemoWalk(analysis)) {
    return '<h2>AI use in this report</h2><p>This sample is not a clip, so none of the analysis steps ran.</p>';
  }
  const lines = aiUseResultLines(analysis.aiUse);
  if (lines.length === 0) {
    return '<h2>AI use in this report</h2><p>This saved walk does not list which steps ran.</p>';
  }
  const items = lines.map((line) => `<li>${escapeHtml(line)}</li>`).join('');
  return `<h2>AI use in this report</h2><ul>${items}</ul>`;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function row(label: string, value: string): string {
  return `<tr><th>${escapeHtml(label)}</th><td>${escapeHtml(value)}</td></tr>`;
}

function petName(pets: Pet[], petId: string): string {
  return pets.find((pet) => pet.id === petId)?.name ?? 'Pet';
}

export function walkReportHtml(analysis: Analysis, pets: Pet[]): string {
  const sample = isDemoWalk(analysis);
  const measurements = analysis.measurements;
  const name = sample ? 'Sample pet' : petName(pets, analysis.petId);
  const concerning = analysis.concerningChange
    ? '<p><strong>Worth asking a veterinarian.</strong> This is a prompt to ask a professional, not a diagnosis.</p>'
    : '';
  return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<style>
  body { font-family: -apple-system, sans-serif; color: #0a4267; padding: 28px; font-size: 14px; line-height: 1.4; }
  h1 { font-size: 22px; margin-bottom: 4px; }
  h2 { font-size: 16px; margin-top: 22px; }
  .muted { color: #46606a; }
  .banner { background: #e8f7f5; border: 1px solid #3794a4; padding: 10px 12px; border-radius: 8px; }
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 4px 8px 4px 0; vertical-align: top; }
  th { width: 46%; font-weight: 600; }
  footer { margin-top: 28px; font-size: 12px; color: #46606a; }
</style>
</head>
<body>
  ${sample ? `<p class="banner"><strong>Sample data — not your pet.</strong> These figures were not measured from a clip.</p>` : ''}
  <h1>PETLENS AI — Movement Observation Report</h1>
  <p class="muted">${escapeHtml(name)} · ${escapeHtml(formatDateTime(analysis.createdAt))}</p>
  ${concerning}
  <h2>Raw measurements</h2>
  <p class="muted">What was saved from the clip. "Not measured" does not mean zero.</p>
  <table>
    ${row('Measured with', PIPELINE_LABELS[analysis.pipeline] ?? analysis.pipeline)}
    ${row('Model', analysis.modelInfo ? `${analysis.modelInfo.modelName} ${analysis.modelInfo.modelVersion}` : 'Not measured')}
    ${row('Overall wellness indicator', formatMeasure(analysis.overallScore, '/100', 0))}
    ${row('Movement consistency', formatMeasure(analysis.factors.movementConsistency, '/100', 0))}
    ${row('Stride symmetry', formatMeasure(analysis.factors.symmetry, '/100', 0))}
    ${row('Mobility', formatMeasure(analysis.factors.mobility, '/100', 0))}
    ${row('Activity', formatMeasure(analysis.factors.activity, '/100', 0))}
    ${row('Change from baseline', formatMeasure(analysis.factors.historicalChange, '/100', 0))}
    ${row('Frames read', formatMeasure(measurements.frameCount, '', 0))}
    ${row('Clip length', formatMeasure(measurements.durationSeconds, ' s', 1))}
    ${row('Mean frame motion', formatMeasure(measurements.motionMean))}
    ${row('Hip stability', formatMeasure(measurements.hipStability))}
    ${row('Stride symmetry (raw)', formatMeasure(measurements.strideSymmetry))}
    ${row('Model confidence', formatMeasure(analysis.modelConfidence))}
  </table>
  <h2>Interpretation</h2>
  <p>${escapeHtml(analysis.observation)}</p>
  <p class="muted">${escapeHtml(analysis.limitations)}</p>
  <footer>
    <p>${escapeHtml(SAFETY_DISCLAIMER)}</p>
    <p>${escapeHtml(EMERGENCY_NOTE)}</p>
    ${aiUseSection(analysis)}
  </footer>
</body>
</html>`;
}

export function vetSummaryHtml(walks: Analysis[], pets: Pet[]): string {
  const real = walks.filter((walk) => !isDemoWalk(walk));
  const groups = new Map<string, Analysis[]>();
  for (const walk of real) {
    const list = groups.get(walk.pipeline) ?? [];
    list.push(walk);
    groups.set(walk.pipeline, list);
  }
  const sections = [...groups.entries()]
    .map(([pipeline, rows]) => {
      const body = rows
        .map((walk) => {
          const flag = walk.concerningChange ? ' Worth asking a veterinarian. Not a diagnosis.' : '';
          const steps = aiUseResultLines(walk.aiUse);
          const stepText = steps.length > 0 ? ` ${steps.join(' ')}` : '';
          return `<li><strong>${escapeHtml(formatDateTime(walk.createdAt))}</strong> · ${escapeHtml(petName(pets, walk.petId))} · overall ${escapeHtml(formatMeasure(walk.overallScore, '/100', 0))} · consistency ${escapeHtml(formatMeasure(walk.factors.movementConsistency, '/100', 0))} · symmetry ${escapeHtml(formatMeasure(walk.factors.symmetry, '/100', 0))}.${escapeHtml(flag)}${escapeHtml(stepText)}</li>`;
        })
        .join('');
      return `<h2>${escapeHtml(PIPELINE_LABELS[pipeline] ?? pipeline)}</h2><ul>${body}</ul>`;
    })
    .join('');
  const empty = real.length === 0 ? '<p>No saved walks yet.</p>' : '';
  return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<style>
  body { font-family: -apple-system, sans-serif; color: #0a4267; padding: 28px; font-size: 14px; line-height: 1.4; }
  h1 { font-size: 22px; }
  h2 { font-size: 16px; margin-top: 18px; }
  .muted { color: #46606a; }
  footer { margin-top: 28px; font-size: 12px; color: #46606a; }
</style>
</head>
<body>
  <h1>PETLENS AI — Saved Walk Summary</h1>
  <p class="muted">Recent saved walks. Walks measured in different ways are listed separately and are not averaged together. This is not a diagnosis.</p>
  ${empty}
  ${sections}
  <footer>
    <p>${escapeHtml(SAFETY_DISCLAIMER)}</p>
    <p>${escapeHtml(EMERGENCY_NOTE)}</p>
    <h2>AI use in this report</h2>
    <p>Each walk above names the steps that produced it. Steps are not combined across walks that were measured in different ways.</p>
  </footer>
</body>
</html>`;
}
