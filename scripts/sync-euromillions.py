#!/usr/bin/env python3
"""
sync-euromillions.py — Synchro Euromillions → Supabase
Scrape les 10 derniers tirages depuis secretsdujeu.com
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

MOIS = {
    'janvier':1,'février':2,'fevrier':2,'mars':3,'avril':4,'mai':5,'juin':6,
    'juillet':7,'août':8,'aout':8,'septembre':9,'octobre':10,'novembre':11,
    'décembre':12,'decembre':12
}

# ── Fetch ─────────────────────────────────────────────────────────────────────
def fetch_page(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode('utf-8', errors='ignore')

# ── Étape 1 : URLs des derniers tirages ──────────────────────────────────────
def get_recent_urls():
    html = fetch_page('https://www.secretsdujeu.com/euromillion/resultat')
    pattern = r'https://www\.secretsdujeu\.com/euromillions/resultat/tirage-euromillions-du-(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)-\d{1,2}-[a-zéûîô]+-\d{4}'
    return list(set(re.findall(pattern, html, re.IGNORECASE)))

# ── Étape 2 : parser une page détail ──────────────────────────────────────────
def parse_draw_page(url):
    # Date depuis URL
    m = re.search(r'du-(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)-(\d{1,2})-([a-zéûîô]+)-(\d{4})', url, re.IGNORECASE)
    if not m: return None
    jour_name = m.group(1).upper()
    day = int(m.group(2))
    month = MOIS.get(m.group(3).lower())
    year = int(m.group(4))
    if not month: return None
    date_str = f'{year:04d}-{month:02d}-{day:02d}'

    try:
        html = fetch_page(url)
    except Exception as e:
        print(f'  ⚠️  Fetch {url}: {e}')
        return None

    # Pattern principal - le plus fiable, toujours présent en bas de page :
    # "La combinaison gagnante à ce tirage est 1, 2, 4, 28, 44 et les numéros Etoile sont 5 et 12"
    p1 = re.search(
        r'combinaison\s+gagnante[^.]*?est\s+(\d{1,2})\s*,\s*(\d{1,2})\s*,\s*(\d{1,2})\s*,\s*(\d{1,2})\s*,?\s*(?:et\s+)?(\d{1,2})[^.]*?[Ee]toiles?\s+(?:sont?\s+)?(\d{1,2})\s+et\s+(\d{1,2})',
        html
    )

    # Backup : "combinaison gagnante... 1-2-4-28-44 et les deux étoiles sont le 5 et le 12"
    p2 = re.search(
        r'combinaison\s+gagnante[^.]*?est\s+(\d{1,2})-(\d{1,2})-(\d{1,2})-(\d{1,2})-(\d{1,2})[^.]*?[ée]toiles?\s+(?:sont?\s+)?(?:le\s+)?(\d{1,2})\s+et\s+(?:le\s+)?(\d{1,2})',
        html
    )

    # Format "les numéros tirés au sort étaient le 1, le 2..."
    p3 = re.search(
        r'num[ée]ros\s+tir[ée]s[^.]*?le\s+(\d{1,2}),\s+le\s+(\d{1,2}),\s+le\s+(\d{1,2}),?\s+le\s+(\d{1,2})\s+et\s+le\s+(\d{1,2})[^.]*?[ée]toiles?\s+(\d{1,2})\s+et\s+(\d{1,2})',
        html, re.IGNORECASE
    )

    match = p1 or p2 or p3
    if not match:
        return None

    try:
        nums = [int(match.group(i)) for i in range(1, 6)]
        stars = [int(match.group(6)), int(match.group(7))]
    except:
        return None

    if not all(1 <= x <= 50 for x in nums): return None
    if not all(1 <= x <= 12 for x in stars): return None

    boules = sorted(nums)
    etoiles = sorted(stars)

    return {
        'date_tirage': date_str,
        'jour': jour_name,
        'boule_1': boules[0], 'boule_2': boules[1], 'boule_3': boules[2],
        'boule_4': boules[3], 'boule_5': boules[4],
        'etoile_1': etoiles[0], 'etoile_2': etoiles[1],
        'boules': json.dumps(boules),
        'etoiles': json.dumps(etoiles)
    }

# ── Supabase ──────────────────────────────────────────────────────────────────
def date_exists(date_str):
    url = f'{SUPABASE_URL}/rest/v1/euromillions_tirages?select=date_tirage&date_tirage=eq.{date_str}'
    req = urllib.request.Request(url, headers={
        'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'
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
    print('🎰  Lucky Thunes — Sync Euromillions')
    print(f'   {datetime.now().isoformat()}\n')

    urls = get_recent_urls()
    print(f'🔍  {len(urls)} URLs de tirages trouvées\n')

    if not urls:
        print('❌  Aucune URL trouvée')
        return

    draws = []
    for url in urls:
        d = parse_draw_page(url)
        if d: draws.append(d)
        else: print(f'   ⚠️  Parse échoué : {url}')

    if not draws:
        print('❌  Aucun tirage parsé')
        return

    unique = {d['date_tirage']: d for d in draws}
    draws = sorted(unique.values(), key=lambda x: x['date_tirage'], reverse=True)

    print(f'\n📊  {len(draws)} tirage(s) parsé(s)\n')
    for d in draws:
        b = [d[f'boule_{i}'] for i in range(1,6)]
        e = [d['etoile_1'], d['etoile_2']]
        print(f'   • {d["date_tirage"]} ({d["jour"]}) — {b} ★ {e}')

    print()
    added = skipped = 0
    for d in draws:
        if date_exists(d['date_tirage']):
            skipped += 1
            continue
        if insert_draw(d):
            print(f'   ✅  {d["date_tirage"]} ajouté')
            added += 1
        else:
            print(f'   ❌  {d["date_tirage"]} échec')

    print(f'\n🎉  Terminé : {added} nouveau(x), {skipped} déjà présent(s)')

if __name__ == '__main__':
    main()
