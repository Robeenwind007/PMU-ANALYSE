#!/usr/bin/env python3
"""
sync-euromillions.py — Synchronisation quotidienne Euromillions FDJ → Supabase
Télécharge le fichier ZIP le plus récent de la FDJ et met à jour Supabase.
Déclenché chaque matin par GitHub Actions.
"""

import os, sys, json, csv, io, zipfile
from datetime import datetime
import urllib.request, urllib.error

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://njohmpmbxemeieqakszw.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')

if not SUPABASE_KEY:
    print('❌  SUPABASE_SERVICE_KEY manquante')
    sys.exit(1)

# URL FDJ — le fichier _2 est le plus récent (Euromillions My Million depuis 2020)
# Les anciens fichiers (_0, _1) ne changent plus car historiques figés
FDJ_URLS = [
    'https://media.fdj.fr/generated/game/euromillions/euromillions_202002.zip',
    'https://media.fdj.fr/static/csv/euromillions/euromillions_202002.zip',
]

# ── Parsers ───────────────────────────────────────────────────────────────────
def parse_date(s):
    s = s.strip()
    for fmt in ['%Y%m%d', '%d/%m/%Y', '%d/%m/%y']:
        try: return datetime.strptime(s, fmt).strftime('%Y-%m-%d')
        except ValueError: pass
    return None

def detect_format(header_cols):
    if len(header_cols) >= 75: return True, 5
    return False, 4

def parse_row(row, has_cycle, b_off):
    if len(row) < b_off + 7: return None
    date_str = parse_date(row[2])
    if not date_str: return None
    jour = row[1].strip().upper()[:8]
    if jour.startswith('MA'): jour = 'MARDI'
    elif jour.startswith('VE'): jour = 'VENDREDI'
    try:
        b1,b2,b3,b4,b5 = [int(row[b_off+i]) for i in range(5)]
        e1,e2 = int(row[b_off+5]), int(row[b_off+6])
    except: return None
    boules = sorted([b1,b2,b3,b4,b5])
    etoiles = sorted([e1,e2])
    if not all(1<=x<=50 for x in boules): return None
    if not all(1<=x<=12 for x in etoiles): return None
    return {
        'date_tirage': date_str,
        'jour': jour,
        'boule_1': b1, 'boule_2': b2, 'boule_3': b3,
        'boule_4': b4, 'boule_5': b5,
        'etoile_1': e1, 'etoile_2': e2,
        'boules': json.dumps(boules),
        'etoiles': json.dumps(etoiles)
    }

# ── Téléchargement ZIP FDJ ────────────────────────────────────────────────────
def download_fdj():
    for url in FDJ_URLS:
        print(f'📥  Tentative: {url}')
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; LuckyThunesBot/1.0)'
            })
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except Exception as e:
            print(f'  ⚠️  Échec: {e}')
    return None

# ── Upsert Supabase ───────────────────────────────────────────────────────────
def upsert_batch(rows):
    if not rows: return 0
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

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f'🎰  Lucky Thunes — Sync Euromillions')
    print(f'   {datetime.now().isoformat()}\n')

    zip_data = download_fdj()
    if not zip_data:
        print('❌  Impossible de télécharger le fichier FDJ')
        sys.exit(1)

    print(f'✅  ZIP téléchargé ({len(zip_data)} octets)')

    # Extraire le CSV du ZIP
    try:
        with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
            csv_names = [n for n in z.namelist() if n.endswith('.csv')]
            if not csv_names:
                print('❌  Aucun CSV trouvé dans le ZIP')
                sys.exit(1)
            csv_name = csv_names[0]
            print(f'📄  Lecture: {csv_name}')
            with z.open(csv_name) as f:
                content = f.read()
    except Exception as e:
        print(f'❌  Erreur ZIP: {e}')
        sys.exit(1)

    # Parser le CSV (tenter plusieurs encodages)
    rows = []
    for enc in ['utf-8', 'latin-1', 'cp1252']:
        try:
            text = content.decode(enc)
            reader = csv.reader(io.StringIO(text), delimiter=';')
            header = next(reader)
            has_cycle, b_off = detect_format(header)
            for line in reader:
                if not line or not line[0].strip(): continue
                r = parse_row(line, has_cycle, b_off)
                if r: rows.append(r)
            break
        except (UnicodeDecodeError, StopIteration):
            continue

    if not rows:
        print('❌  Aucun tirage parsé')
        sys.exit(1)

    print(f'📊  {len(rows)} tirages parsés ({rows[-1]["date_tirage"]} → {rows[0]["date_tirage"]})')

    # Upsert (traite merge-duplicates → ne crée que les nouveaux)
    n = upsert_batch(rows)
    print(f'\n🎉  {n} tirages synchronisés dans Supabase')

if __name__ == '__main__':
    main()
