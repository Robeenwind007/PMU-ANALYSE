#!/usr/bin/env node
/**
 * init-db.js — Chargement historique PMU (2004 → aujourd'hui) dans Supabase
 * Usage : node scripts/init-db.js
 * Nécessite : SUPABASE_URL et SUPABASE_SERVICE_KEY dans l'environnement
 *             (utiliser la service_role key pour contourner RLS en écriture)
 */

const SUPABASE_URL = process.env.SUPABASE_URL || 'https://njohmpmbxemeieqakszw.supabase.co';
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY; // service_role key requise
const API_BASE     = 'https://open-pmu-api.vercel.app/api/arrivees';

if (!SUPABASE_KEY) {
  console.error('❌  SUPABASE_SERVICE_KEY manquante');
  process.exit(1);
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function dateRange(startStr, endStr) {
  const dates = [];
  const cur = new Date(startStr);
  const end = new Date(endStr);
  while (cur <= end) {
    dates.push(cur.toISOString().slice(0, 10));
    cur.setDate(cur.getDate() + 1);
  }
  return dates;
}

function fmtDate(iso) {
  // 2024-03-15 → 15/03/2024
  const [y, m, d] = iso.split('-');
  return `${d}/${m}/${y}`;
}

function parseRC(rc) {
  // "R1C4" → { reunion: "R1", course: "C4" }
  const m = (rc || '').match(/^(R\d+)(C\d+)$/i);
  return m ? { reunion: m[1].toUpperCase(), course: m[2].toUpperCase() } : { reunion: rc, course: '' };
}

// ── Fetch une journée depuis open-pmu-api ────────────────────────────────────

async function fetchDay(isoDate, retries = 3) {
  const url = `${API_BASE}?date=${fmtDate(isoDate)}`;
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(15000) });
      if (!res.ok) return [];
      const json = await res.json();
      if (json.error || !Array.isArray(json.message)) return [];
      return json.message;
    } catch (e) {
      if (attempt === retries) return [];
      await sleep(2000 * attempt);
    }
  }
  return [];
}

// ── Upsert batch dans Supabase ───────────────────────────────────────────────

async function upsertRows(rows) {
  if (!rows.length) return;
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
    console.error('  ⚠️  Supabase error:', err.slice(0, 200));
  }
}

// ── Conversion API → ligne Supabase ─────────────────────────────────────────

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

// ── Récupérer les dates déjà chargées ────────────────────────────────────────

async function getAlreadyLoaded() {
  let allDates = [];
  let offset = 0;
  const limit = 1000;

  // Paginer car Supabase limite à 1000 lignes par défaut
  while (true) {
    const res = await fetch(
      `${SUPABASE_URL}/rest/v1/courses?select=date&order=date.asc&limit=${limit}&offset=${offset}`,
      {
        headers: {
          'apikey': SUPABASE_KEY,
          'Authorization': `Bearer ${SUPABASE_KEY}`
        }
      }
    );
    if (!res.ok) break;
    const rows = await res.json();
    if (!rows.length) break;
    allDates = allDates.concat(rows.map(r => r.date));
    if (rows.length < limit) break;
    offset += limit;
  }

  return new Set(allDates);
}

// ── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  const START = '2004-01-01';
  const END   = new Date().toISOString().slice(0, 10);
  const allDates = dateRange(START, END);

  console.log(`🏇  PMU Init — ${allDates.length} jours à traiter (${START} → ${END})`);
  console.log('📡  Vérification des dates déjà chargées...');

  const loaded = await getAlreadyLoaded();
  const todo   = allDates.filter(d => !loaded.has(d));

  console.log(`✅  ${loaded.size} jours déjà en base — ${todo.length} jours restants\n`);

  if (!todo.length) {
    console.log('🎉  Base déjà à jour !');
    return;
  }

  let inserted = 0;
  let empty    = 0;
  const BATCH_DAYS = 10; // jours traités en parallèle
  const PAUSE_MS   = 1200; // pause entre batches (respecter rate limit API)

  for (let i = 0; i < todo.length; i += BATCH_DAYS) {
    const chunk = todo.slice(i, i + BATCH_DAYS);
    const results = await Promise.all(chunk.map(d => fetchDay(d)));

    const rows = [];
    chunk.forEach((d, idx) => {
      const items = results[idx];
      if (!items.length) { empty++; return; }
      items.forEach(item => rows.push(toRow(d, item)));
    });

    if (rows.length) {
      await upsertRows(rows);
      inserted += rows.length;
    }

    const pct = Math.round(((i + chunk.length) / todo.length) * 100);
    process.stdout.write(
      `\r  📦  ${i + chunk.length}/${todo.length} jours (${pct}%) — ${inserted} courses insérées`
    );

    await sleep(PAUSE_MS);
  }

  console.log(`\n\n🎉  Terminé ! ${inserted} courses insérées, ${empty} jours sans courses`);
}

main().catch(e => { console.error(e); process.exit(1); });
