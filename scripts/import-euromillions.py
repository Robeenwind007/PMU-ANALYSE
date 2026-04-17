#!/usr/bin/env python3
"""
import-euromillions.py — Import historique Euromillions (CSV FDJ) → Supabase
Usage : python3 scripts/import-euromillions.py

Gère les 3 formats FDJ :
  - Format A : date YYYYMMDD, 52 cols, pas de colonne cycle
  - Format B : date DD/MM/YYYY ou DD/MM/YY, 55 cols, pas de colonne cycle
  - Format C : date DD/MM/YYYY, 75-76 cols, avec colonne numéro_de_tirage_dans_le_cycle
"""

import os, sys, json, csv
from datetime import datetime
from pathlib import Path
import urllib.request, urllib.error

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://njohmpmbxemeieqakszw.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')

if not SUPABASE_KEY:
    print('❌  SUPABASE_SERVICE_KEY manquante')
    sys.exit(1)

# ── Dossier contenant les CSV ─────────────────────────────────────────────────
CSV_DIR = Path(__file__).parent.parent / 'data' / 'euromillions'

# ── Parsing date ──────────────────────────────────────────────────────────────
def parse_date(s):
    s = s.strip()
    for fmt in ['%Y%m%d', '%d/%m/%Y', '%d/%m/%y']:
        try:
            return datetime.strptime(s, fmt).strftime('%Y-%m-%d')
        except ValueError:
            pass
    return None

# ── Détection du format ───────────────────────────────────────────────────────
def detect_format(header_cols):
    """
    Retourne (has_cycle, boule_offset)
    has_cycle=True → colonne numéro_de_tirage_dans_le_cycle présente entre date et boules
    """
    if len(header_cols) >= 75:
        return True, 5   # boule_1 est à l'index 5
    elif len(header_cols) >= 55:
        return False, 4  # boule_1 est à l'index 4
    else:
        return False, 4  # format ancien (52 cols)

# ── Parser une ligne CSV ──────────────────────────────────────────────────────
def parse_row(row, has_cycle, boule_offset):
    """Retourne un dict ou None si ligne invalide"""
    if len(row) < boule_offset + 7:
        return None
    
    date_str = parse_date(row[2])
    if not date_str:
        return None
    
    jour = row[1].strip().upper()[:8]  # MARDI, VENDREDI, VE, etc.
    # Normaliser le jour
    if jour.startswith('MA') or jour == 'MA':
        jour = 'MARDI'
    elif jour.startswith('VE') or jour == 'VE':
        jour = 'VENDREDI'
    
    try:
        b_off = boule_offset
        b1 = int(row[b_off])
        b2 = int(row[b_off + 1])
        b3 = int(row[b_off + 2])
        b4 = int(row[b_off + 3])
        b5 = int(row[b_off + 4])
        e1 = int(row[b_off + 5])
        e2 = int(row[b_off + 6])
    except (ValueError, IndexError):
        return None
    
    boules  = sorted([b1, b2, b3, b4, b5])
    etoiles = sorted([e1, e2])
    
    # Validation plages
    if not all(1 <= b <= 50 for b in boules): return None
    if not all(1 <= e <= 12 for e in etoiles): return None
    
    return {
        'date_tirage': date_str,
        'jour':        jour,
        'boule_1':     b1, 'boule_2': b2, 'boule_3': b3,
        'boule_4':     b4, 'boule_5': b5,
        'etoile_1':    e1, 'etoile_2': e2,
        'boules':      json.dumps(boules),
        'etoiles':     json.dumps(etoiles)
    }

# ── Upsert Supabase ───────────────────────────────────────────────────────────
def upsert_batch(rows):
    if not rows:
        return 0
    data = json.dumps(rows).encode('utf-8')
    req = urllib.request.Request(
        f'{SUPABASE_URL}/rest/v1/euromillions_tirages',
        data=data,
        headers={
            'Content-Type': 'application/json',
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Prefer': 'resolution=merge-duplicates,return=minimal'
        },
        method='POST'
    )
    try:
        with urllib.request.urlopen(req) as r:
            return len(rows)
    except urllib.error.HTTPError as e:
        print(f'  ⚠️  Supabase error {e.code}: {e.read()[:200]}')
        return 0

# ── Parser un fichier CSV ─────────────────────────────────────────────────────
def parse_csv(path):
    rows = []
    for enc in ['utf-8', 'latin-1', 'cp1252']:
        try:
            with open(path, encoding=enc, newline='') as f:
                reader = csv.reader(f, delimiter=';')
                header = next(reader)
                has_cycle, boule_offset = detect_format(header)
                for line in reader:
                    if not line or not line[0].strip():
                        continue
                    row = parse_row(line, has_cycle, boule_offset)
                    if row:
                        rows.append(row)
            break
        except (UnicodeDecodeError, StopIteration):
            continue
    return rows

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    # Chercher les CSV dans data/euromillions/ ou dans le dossier courant
    search_dirs = [CSV_DIR, Path('.'), Path('./data'), Path('./scripts')]
    csv_files = []
    for d in search_dirs:
        if d.exists():
            csv_files.extend(sorted(d.glob('euromillions*.csv')))
    
    if not csv_files:
        print('❌  Aucun fichier CSV euromillions trouvé')
        print(f'   Placez les CSV dans : {CSV_DIR}')
        sys.exit(1)
    
    print(f'🎰  Import Euromillions — {len(csv_files)} fichiers CSV trouvés')
    
    all_rows = {}
    for path in csv_files:
        rows = parse_csv(path)
        print(f'  📄  {path.name} → {len(rows)} tirages parsés')
        for r in rows:
            all_rows[r['date_tirage']] = r  # dédoublonnage par date
    
    rows_list = sorted(all_rows.values(), key=lambda x: x['date_tirage'])
    print(f'\n✅  Total : {len(rows_list)} tirages uniques ({rows_list[0]["date_tirage"]} → {rows_list[-1]["date_tirage"]})')
    
    # Upsert par batch de 200
    BATCH = 200
    inserted = 0
    for i in range(0, len(rows_list), BATCH):
        batch = rows_list[i:i+BATCH]
        n = upsert_batch(batch)
        inserted += n
        pct = round((i + len(batch)) / len(rows_list) * 100)
        print(f'\r  📦  {i+len(batch)}/{len(rows_list)} ({pct}%) — {inserted} insérés', end='')
    
    print(f'\n\n🎉  Terminé ! {inserted} tirages importés dans Supabase')

if __name__ == '__main__':
    main()
