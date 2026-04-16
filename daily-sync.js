#!/usr/bin/env node
/**
 * daily-sync.js — Synchronisation quotidienne PMU → Supabase
 * Déclenché chaque matin par GitHub Actions (cron)
 * Récupère J-1 (et éventuellement J-2 en rattrapage)
 */

const SUPABASE_URL = process.env.SUPABASE_URL || 'https://njohmpmbxemeieqakszw.supabase.co';
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY;
const API_BASE     = 'https://open-pmu-api.vercel.app/api/arrivees';

if (!SUPABASE_KEY) {
  console.error('❌  SUPABASE_SERVICE_KEY manquante');
  process.exit(1);
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function isoToFr(iso) {
  const [y, m, d] = iso.split('-');
  return `${d}/${m}/${y}`;
}

function getDateOffset(offset = 0) {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  return d.toISOString().slice(0, 10);
}

function parseRC(rc) {
  const m = (rc || '').match(/^(R\d+)(C\d+)$/i);
  return m ? { reunion: m[1].toUpperCase(), course: m[2].toUpperCase() } : { reunion: rc, course: '' };
}

function toRow(isoDate, item) {
  const rc = (item['r/c'] || item.rc || '').toUpperCase();
  const { reunion, course } = parseRC(rc);
  return {
    date:         isoDate,
    reunion,
    course,
    rc,
    lieu:         item.lieu || null,
    type:         item.type || null,
    prix:         item.prix || item.pix || null,
    distance:     item.distance ? parseInt(item.distance) : null,
    montant:      item.montant  ? parseInt(item.montant)  : null,
    partants:     item.partants ? parseInt(item.partants) : null,
    non_partants: Array.isArray(item.non_partants) ? item.non_partants : null,
    arrivee:      Array.isArray(item.arrivee) ? item.arrivee.slice(0, 5) : null
  };
}

async function fetchDay(isoDate) {
  const url = `${API_BASE}?date=${isoToFr(isoDate)}`;
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(20000) });
    if (!res.ok) return [];
    const json = await res.json();
    if (json.error || !Array.isArray(json.message)) return [];
    return json.message;
  } catch (e) {
    console.error(`  ⚠️  Fetch erreur pour ${isoDate}:`, e.message);
    return [];
  }
}

async function upsertRows(rows) {
  if (!rows.length) return 0;
  const res = await fetch(`${SUPABASE_URL}/rest/v1/courses`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'apikey': SUPABASE_KEY,
      'Authorization': `Bearer ${SUPABASE_KEY}`,
      'Prefer': 'resolution=merge-duplicates,return=minimal'
    },
    body: JSON.stringify(rows)
  });
  if (!res.ok) {
    const err = await res.text();
    console.error('  ⚠️  Supabase error:', err.slice(0, 300));
    return 0;
  }
  return rows.length;
}

async function syncDate(isoDate) {
  console.log(`📅  Sync ${isoDate}...`);
  const items = await fetchDay(isoDate);
  if (!items.length) {
    console.log(`  ℹ️  Aucune course trouvée pour ${isoDate}`);
    return 0;
  }
  const rows = items.map(item => toRow(isoDate, item));
  const n = await upsertRows(rows);
  console.log(`  ✅  ${n} courses upsertées`);
  return n;
}

async function main() {
  console.log('🏇  PMU Daily Sync — ' + new Date().toISOString());

  // J-1 (hier) — données du jour précédent
  const yesterday = getDateOffset(-1);
  await syncDate(yesterday);

  // J-2 en rattrapage (au cas où le cron d'hier aurait raté)
  await sleep(500);
  const dayBefore = getDateOffset(-2);
  await syncDate(dayBefore);

  console.log('\n🎉  Sync terminée');
}

main().catch(e => { console.error(e); process.exit(1); });
