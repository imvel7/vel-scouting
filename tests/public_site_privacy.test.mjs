// Guards against publishing youth-player data or secrets through the static GitHub Pages site.
// Runs on every pull request (see .github/workflows/public-site-privacy.yml).
import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';

const tracked = execFileSync('git', ['ls-files', '-z'], { encoding: 'utf8' }).split('\0').filter(Boolean);
const index = readFileSync('index.html', 'utf8');

const ALLOWED_PUBLIC_TABLES = ['players', 'scout_reports'];
const FORBIDDEN_PUBLIC_FIELDS = [
  'date_of_birth', 'birth', 'private_notes', 'video_url', 'current_club_id',
  'report_snapshot', 'scouting_sessions', 'criterion_scores', 'observations',
  'report_versions', 'user_roles', 'rights_assessment'
];

test('index.html reads only the allowed public tables', () => {
  const tables = [...index.matchAll(/\.from\(\s*['"]([a-z_]+)['"]\s*\)/g)].map(m => m[1]);
  assert.ok(tables.length > 0, 'expected at least one table read');
  for (const t of new Set(tables)) assert.ok(ALLOWED_PUBLIC_TABLES.includes(t), `index.html reads non-public table: ${t}`);
});

test('every public read is filtered to published rows', () => {
  const reads = [...index.matchAll(/\.from\(\s*['"](players|scout_reports)['"]\s*\)[^;\n]*/g)].map(m => m[0]);
  assert.ok(reads.length >= 2);
  for (const r of reads) {
    const wanted = r.includes("from('players')") || r.includes('from("players")') ? 'profile_status' : 'report_status';
    assert.ok(new RegExp(`\\.eq\\(\\s*['"]${wanted}['"]\\s*,\\s*['"]published['"]\\s*\\)`).test(r), `unfiltered public read: ${r.slice(0, 80)}`);
  }
});

test('index.html selects no sensitive fields', () => {
  const selects = [...index.matchAll(/\.select\(\s*(['"`])([\s\S]*?)\1/g)].map(m => m[2]);
  assert.ok(selects.length >= 2);
  for (const s of selects) for (const f of FORBIDDEN_PUBLIC_FIELDS) assert.ok(!s.includes(f), `index.html selects forbidden field "${f}"`);
});

test('no secret keys or private keys in tracked files', () => {
  const b64 = s => { try { return Buffer.from(s.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf8'); } catch { return ''; } };
  for (const f of tracked) {
    let text;
    try { text = readFileSync(f, 'utf8'); } catch { continue; }
    assert.ok(!/sb_secret_[A-Za-z0-9_-]{10,}/.test(text), `secret key in ${f}`);
    assert.ok(!/-----BEGIN [A-Z ]*PRIVATE KEY-----/.test(text), `private key in ${f}`);
    for (const m of text.matchAll(/eyJ[A-Za-z0-9_-]{8,}\.([A-Za-z0-9_-]{8,})\.[A-Za-z0-9_-]{8,}/g)) {
      assert.ok(!/"role"\s*:\s*"service_role"/.test(b64(m[1])), `service_role JWT in ${f}`);
    }
  }
});

test('no raw data, database dumps or media files are tracked', () => {
  const bad = tracked.filter(f => /\.(csv|tsv|jsonl|json|parquet|xlsx?|zip|gz|tar|7z|sqlite3?|db|dump|mp4|mkv|avi|mov|webm|mp3|wav)$/i.test(f));
  assert.deepEqual(bad, [], `tracked data/media files: ${bad.join(', ')}`);
});
