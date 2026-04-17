#!/usr/bin/env python3
"""
sync-euromillions.py — Synchro Euromillions → Supabase
Récupère les derniers tirages via scraping puis ajoute dans Supabase.
"""

import os, sys, json, re
from datetime import datetime
import urllib.request, urllib.error

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://njohmpmbxemeieqakszw.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')

if not SUPABASE_KEY:
    print('❌  SUPABASE_SERVICE_KEY manquante')
    sys.exit(1)

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'

MOIS = {'janvier':1,'février':2,'fevrier':2,'mars':3,'avril':4,'mai':5,'juin':6,
        'juillet':7,'août':8,'aout':8,'septembre':9,'octobre':10,'novembre':11,'décembre':12,'decembre':12}

# ── Scraping ──────────────────────────────────────────────────────────────────
def fetch_page(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode('utf-8', errors='ignore')

def scrape_secretsdujeu():
    """Récupère les derniers tirages depuis secretsdujeu.com"""
    draws = []
    try:
        html = fetch_page('https://www.secretsdujeu.com/euromillion/resultat')

        # Chercher "XX MONTH YYYY ... 1, 2, 4, 28 et 44, ainsi que les étoiles 5 et 12"
        pattern = r'(mardi|vendredi)\s+(\d{1,2})\s+(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)\s+(\d{4})[^.]{10,400}?((?:\d{1,2}[,\s\-et]+){4}\d{1,2})[^.]{3,80}?étoiles?\s+(?:sont?\s+)?(?:le\s+)?(\d{1,2})\s+et\s+(?:le\s+)?(\d{1,2})'

        for m in re.finditer(pattern, html, re.IGNORECASE):
            try:
                jour = m.group(1).upper()
                day = int(m.group(2))
                month = MOIS.get(m.group(3).lower())
                year = int(m.group(4))
                if not month: continue

                nums_raw = m.group(5)
                nums = [int(x) for x in re.findall(r'\d+', nums_raw)]
                e1, e2 = int(m.group(6)), int(m.group(7))

                if len(nums) < 5: continue
                nums = nums[:5]
                if not all(1<=x<=50 for x in nums): continue
                if not all(1<=x<=12 for x in [e1,e2]): continue

                date_str = f'{year:04d}-{month:02d}-{day:02d}'
                boules = sorted(nums)
                etoiles = sorted([e1, e2])

                draws.append({
                    'date_tirage': date_str,
                    'jour': jour,
                    'boule_1': boules[0], 'boule_2': boules[1], 'boule_3': boules[2],
                    'boule_4': boules[3], 'boule_5': boules[4],
                    'etoile_1': etoiles[0], 'etoile_2': etoiles[1],
                    'boules': json.dumps(boules),
                    'etoiles': json.dumps(etoiles)
                })
            except Exception as e:
                print(f'  ⚠️  Parse error: {e}')
                continue
    except Exception as e:
        print(f'❌  Erreur scraping: {e}')
    return draws

# ── Supabase ──────────────────────────────────────────────────────────────────
def date_exists(date_str):
    url = f'{SUPABASE_URL}/rest/v1/euromillions_tirages?select=date_tirage&date_tirage=eq.{date_str}'
    req = urllib.request.Request(url, headers={
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}'
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return len(json.loads(r.read())) > 0
    except:
        return False

def insert_draw(row):
    data = json.dumps([row]).encode('utf-8')
    req = urllib.request.Request(
        f'{SUPABASE_URL}/rest/v1/euromillions_tirages',
        data=data,
        headers={
            'Content-Type': 'application/json',
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Prefer': 'return=minimal'
        },
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            return True
    except urllib.error.HTTPError as e:
        if e.code == 409: return False
        print(f'  ⚠️  Erreur {e.code}: {e.read()[:200]}')
        return False

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f'🎰  Lucky Thunes — Sync Euromillions')
    print(f'   {datetime.now().isoformat()}\n')

    draws = scrape_secretsdujeu()
    if not draws:
        print('⚠️  Aucun tirage détecté')
        return

    # Dédoublonner
    unique = {}
    for d in draws: unique[d['date_tirage']] = d
    draws = sorted(unique.values(), key=lambda x: x['date_tirage'], reverse=True)

    print(f'📊  {len(draws)} tirage(s) récent(s) détecté(s)\n')
    for d in draws:
        print(f'   • {d["date_tirage"]} ({d["jour"]}) — boules {d["boules"]} étoiles {d["etoiles"]}')

    print()
    added = skipped = 0
    for d in draws:
        if date_exists(d['date_tirage']):
            print(f'   ⏭️   {d["date_tirage"]} déjà en base')
            skipped += 1
            continue
        if insert_draw(d):
            print(f'   ✅  {d["date_tirage"]} ajouté')
            added += 1
        else:
            print(f'   ❌  {d["date_tirage"]} échec')

    print(f'\n🎉  Terminé : {added} ajouté(s), {skipped} déjà présent(s)')

if __name__ == '__main__':
    main()
