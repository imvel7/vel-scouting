// Unit tests for the report status workflow helpers inside admin.html (no browser, no network).
// Run: node --test tests/*.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const html = fs.readFileSync(path.join(root, 'admin.html'), 'utf8');

function workflowSource() {
  const start = html.indexOf('// REPORT-WORKFLOW-START');
  const end = html.indexOf('// REPORT-WORKFLOW-END');
  assert.ok(start > 0 && end > start, 'workflow markers present');
  return html.slice(start, end);
}
function load() {
  const ctx = {};
  vm.createContext(ctx);
  vm.runInContext(workflowSource() + '\nthis.api={REPORT_TRANSITIONS,reportActionsFor,canPrepareCorrection,changeReportStatus,correctionDraftFrom,REPORT_STATUS_LABELS};', ctx);
  return ctx.api;
}
// Fake supabase-js client recording the update chain.
function fakeClient(result) {
  const calls = [];
  const chain = {
    update(values) { calls.push(['update', values]); return chain; },
    eq(col, val) { calls.push(['eq', col, val]); return chain; },
    select(cols) { calls.push(['select', cols]); return Promise.resolve(result); },
  };
  return { calls, from(table) { calls.push(['from', table]); return chain; } };
}
const plain = (x) => JSON.parse(JSON.stringify(x));
const report = (status) => ({ id: 'r1', player_id: 'p1', report_status: status });

test('script block of admin.html parses as a module', () => {
  const m = html.match(/<script type="module">([\s\S]*?)<\/script>/);
  assert.ok(m, 'module script found');
  const code = m[1].replace(/^\s*import .*$/m, 'const createClient=()=>({});');
  const tmp = path.join(root, 'tests', '.admin_module_check.mjs');
  fs.writeFileSync(tmp, code);
  try {
    const r = spawnSync(process.execPath, ['--check', tmp]);
    assert.equal(r.status, 0, String(r.stderr));
  } finally { fs.rmSync(tmp, { force: true }); }
});

test('editor sees review/back actions but never publish or archive', () => {
  const { reportActionsFor } = load();
  assert.deepEqual(plain(reportActionsFor('draft', 'editor').map(t => t.action)), ['review']);
  assert.deepEqual(plain(reportActionsFor('review', 'editor').map(t => t.action)), ['back_to_draft']);
  assert.deepEqual(plain(reportActionsFor('published', 'editor')), []);
  assert.deepEqual(plain(reportActionsFor('archived', 'editor')), []);
});
test('admin sees publish on review and archive on published; archived is final', () => {
  const { reportActionsFor } = load();
  assert.deepEqual(plain(reportActionsFor('review', 'admin').map(t => t.action)), ['back_to_draft', 'publish']);
  assert.deepEqual(plain(reportActionsFor('published', 'admin').map(t => t.action)), ['archive']);
  assert.deepEqual(plain(reportActionsFor('archived', 'admin')), []);
  assert.deepEqual(plain(reportActionsFor('draft', 'admin').map(t => t.action)), ['review']);
});
test('publish and archive ask for confirmation, review does not', () => {
  const { REPORT_TRANSITIONS } = load();
  const byAction = Object.fromEntries(REPORT_TRANSITIONS.map(t => [t.action, t]));
  assert.ok(byAction.publish.confirm && byAction.archive.confirm);
  assert.equal(byAction.review.confirm, null);
});
test('successful transition sends a guarded update and reports success', async () => {
  const { changeReportStatus } = load();
  const client = fakeClient({ data: [{ id: 'r1', report_status: 'review' }], error: null });
  const r = await changeReportStatus(client, report('draft'), 'review', 'editor');
  assert.equal(r.ok, true);
  assert.equal(r.to, 'review');
  assert.deepEqual(client.calls[0], ['from', 'scout_reports']);
  assert.deepEqual(plain(client.calls[1]), ['update', { report_status: 'review' }]);
  assert.ok(client.calls.some(c => c[0] === 'eq' && c[1] === 'report_status' && c[2] === 'draft'), 'update is guarded by the current status');
});
test('database error is shown, never reported as success', async () => {
  const { changeReportStatus } = load();
  const client = fakeClient({ data: null, error: { message: 'Only an admin can publish or archive a report.' } });
  const r = await changeReportStatus(client, report('review'), 'publish', 'admin');
  assert.equal(r.ok, false);
  assert.match(r.message, /Only an admin/);
});
test('zero rows updated (RLS hidden or stale status) is not reported as success', async () => {
  const { changeReportStatus } = load();
  for (const data of [[], null, [{ id: 'r1', report_status: 'review' }, { id: 'r2', report_status: 'published' }], [{ id: 'r1', report_status: 'review' }]]) {
    const client = fakeClient({ data, error: null });
    const r = await changeReportStatus(client, report('review'), 'publish', 'admin');
    assert.equal(r.ok, false, JSON.stringify(data));
  }
});
test('editor publish is refused client-side without any request', async () => {
  const { changeReportStatus } = load();
  const client = fakeClient({ data: [{ id: 'r1', report_status: 'published' }], error: null });
  const r = await changeReportStatus(client, report('review'), 'publish', 'editor');
  assert.equal(r.ok, false);
  assert.equal(client.calls.length, 0);
});
test('invalid transition for the current status makes no request', async () => {
  const { changeReportStatus } = load();
  const client = fakeClient({ data: [], error: null });
  for (const [status, action] of [['draft', 'publish'], ['published', 'review'], ['archived', 'archive'], ['draft', 'archive']]) {
    const r = await changeReportStatus(client, report(status), action, 'admin');
    assert.equal(r.ok, false, status + '/' + action);
  }
  assert.equal(client.calls.length, 0);
});
test('correction drafts only for reports that left draft; fields come from the stored snapshot', () => {
  const { canPrepareCorrection, correctionDraftFrom } = load();
  assert.equal(canPrepareCorrection('draft'), false);
  for (const s of ['review', 'published', 'archived']) assert.equal(canPrepareCorrection(s), true);
  const d = correctionDraftFrom({ player_id: 'p1', strengths: 'row' }, {
    session_ids: ['s1', 's2'],
    report_fields: { main_role: 'Cover Defender', alternative_roles: ['A', 'B'], main_role_evidence: 'ev', strengths: 'snap', development_areas: null, final_verdict: 'v' },
  });
  assert.equal(d.playerId, 'p1');
  assert.deepEqual(plain(d.sessionIds), ['s1', 's2']);
  assert.equal(d.alternativeRoles, 'A, B');
  assert.equal(d.strengths, 'snap');
  assert.equal(d.developmentAreas, '');
});
test('correction draft tolerates a missing snapshot', () => {
  const { correctionDraftFrom } = load();
  const d = correctionDraftFrom({ player_id: 'p9', strengths: 'x', development_areas: 'y', final_verdict: 'z' }, null);
  assert.deepEqual(plain(d.sessionIds), []);
  assert.equal(d.strengths, 'x');
  assert.equal(d.finalVerdict, 'z');
});

// ---- report history helpers ----
function loadHistory() {
  const start = html.indexOf('// REPORT-HISTORY-START');
  const end = html.indexOf('// REPORT-HISTORY-END');
  assert.ok(start > 0 && end > start, 'history markers present');
  const ctx = {};
  vm.createContext(ctx);
  vm.runInContext(html.slice(start, end) + '\nthis.api={buildReportHistory,renderReportHistory,formatHistoryRating,formatHistoryDate};', ctx);
  return ctx.api;
}
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const snap = (over = {}) => ({
  captured_at: '2026-11-25T10:00:00Z', source: 'vel_scout_admin', methodology_version: 'CB-METH-0.8',
  rubric: { version_code: 'CB-METH-0.8-ANCHORS-1.0', scoring_anchors_version: '1.0' },
  evidence_grade: 'B', general_rating: 6, session_ids: ['a', 'b', 'c'], full_match_count: 3, ...over,
});
const label = (id) => 'etiket-' + id;

test('history lists versions in order with methodology, rubric, grade, rating and session counts', () => {
  const { buildReportHistory } = loadHistory();
  const rep = { id: 'r1', report_status: 'published', methodology_version: 'CB-METH-0.8' };
  const m = plain(buildReportHistory(rep, [
    { version_number: 2, created_at: '2026-11-26T10:00:00Z', report_snapshot: snap({ general_rating: 7 }) },
    { version_number: 1, created_at: '2026-11-25T10:00:00Z', report_snapshot: snap() },
  ], [], label));
  assert.deepEqual(m.versions.map(v => v.number), [1, 2]);
  assert.equal(m.versions[0].rubricCode, 'CB-METH-0.8-ANCHORS-1.0');
  assert.equal(m.versions[0].anchorsVersion, '1.0');
  assert.equal(m.versions[0].sessionCount, 3);
  assert.equal(m.versions[1].rating, 7);
  assert.deepEqual(m.notes, []);
});
test('history flags a version whose methodology differs from the report record and an empty history', () => {
  const { buildReportHistory } = loadHistory();
  const rep = { id: 'r1', report_status: 'draft', methodology_version: 'CB-METH-0.8' };
  const bad = plain(buildReportHistory(rep, [{ version_number: 1, created_at: 'x', report_snapshot: snap({ methodology_version: 'OTHER' }) }], [], label));
  assert.equal(bad.notes.length, 1);
  assert.match(bad.notes[0], /uyuşmuyor/);
  const empty = plain(buildReportHistory(rep, [], [], label));
  assert.equal(empty.notes.length, 1);
  assert.deepEqual(empty.versions, []);
});
test('history shows the correction chain in both directions', () => {
  const { buildReportHistory } = loadHistory();
  const rep = { id: 'r2', report_status: 'draft', methodology_version: 'M' };
  const m = plain(buildReportHistory(rep,
    [{ version_number: 1, created_at: 'x', report_snapshot: snap({ methodology_version: 'M', supersedes_report_id: 'r1' }) }],
    [{ report_id: 'r3', version_number: 1 }, { report_id: 'r3', version_number: 2 }, { report_id: 'r2', version_number: 1 }], label));
  assert.deepEqual(m.supersedes, { id: 'r1', label: 'etiket-r1' });
  assert.deepEqual(m.supersededBy, [{ id: 'r3', label: 'etiket-r3' }]);
});
test('rating text never invents a number when there is no rating', () => {
  const { formatHistoryRating } = loadHistory();
  assert.match(formatHistoryRating(null), /yok/);
  assert.match(formatHistoryRating(undefined), /yok/);
  assert.equal(formatHistoryRating('6.00'), '6.00/10');
  assert.equal(formatHistoryRating(6), '6.00/10');
});
test('rendered history escapes all dynamic text', () => {
  const { buildReportHistory, renderReportHistory } = loadHistory();
  const rep = { id: 'r1', report_status: '<b>x</b>', methodology_version: '<img src=x onerror=1>' };
  const m = buildReportHistory(rep, [{ version_number: 1, created_at: 'x', report_snapshot: snap({ methodology_version: '<script>1</script>', supersedes_report_id: 'r0' }) }], [], () => '<script>alert(1)</script>');
  const out = renderReportHistory(m, esc);
  assert.ok(!out.includes('<script>'), 'no raw script tag');
  assert.ok(!out.includes('<img'), 'no raw img tag');
  assert.ok(out.includes('&lt;script&gt;'));
  assert.match(out, /Sürümler yalnızca eklenir/);
  assert.match(out, /data-report-action="close-history"/);
});
