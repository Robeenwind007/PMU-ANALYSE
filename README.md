# PMU Stats 🏇

PWA d'analyse des arrivées de courses PMU — données Supabase, déploiement Vercel.

**Version** : v1.0.0  
**Auteur** : Olivier BERNARD  
**URL** : [pmu-courses.vercel.app](https://pmu-courses.vercel.app)

---

## Architecture

```
open-pmu-api (source) → GitHub Actions (cron) → Supabase (BDD) → PWA Vercel (front)
```

## Fonctionnalités

- 📅 **Journée** — toutes les courses d'une date avec arrivées, partants, dotations
- 🔢 **Dossards** — fréquence de victoire par numéro sur période choisie (1 mois → tout)
- 🏟 **Hippodromes** — classement par volume de courses et dotation moyenne
- 📊 **Types** — répartition et stats par type (Attelé, Monté, Plat, Haies, Steeple)
- 💾 **Base de données** — historique depuis le 22/01/2004, mise à jour quotidienne automatique
- 📱 **PWA** — installable sur iOS et Android

## Base de données Supabase

**Projet** : `njohmpmbxemeieqakszw.supabase.co`  
**Table** : `courses`

| Colonne | Type | Description |
|---|---|---|
| `date` | DATE | Date de la course |
| `reunion` | TEXT | Réunion (ex: R1) |
| `course` | TEXT | Course (ex: C4) |
| `rc` | TEXT | Identifiant (ex: R1C4) |
| `lieu` | TEXT | Hippodrome |
| `type` | TEXT | Attelé / Monté / Plat / Haies / Steeple |
| `prix` | TEXT | Nom du prix |
| `distance` | INTEGER | Distance en mètres |
| `montant` | BIGINT | Dotation en euros |
| `partants` | INTEGER | Nombre de partants |
| `non_partants` | JSONB | Numéros non partants |
| `arrivee` | JSONB | 5 premiers (numéros de dossard) |

## Déploiement

### Secrets GitHub requis

Dans **Settings → Secrets → Actions** :

| Secret | Valeur |
|---|---|
| `SUPABASE_URL` | `https://njohmpmbxemeieqakszw.supabase.co` |
| `SUPABASE_SERVICE_KEY` | Clé `service_role` Supabase |

### Workflows GitHub Actions

| Workflow | Déclenchement | Rôle |
|---|---|---|
| `PMU Init Historique` | Manuel | Chargement historique depuis 2004 |
| `PMU Daily Sync` | Cron 6h UTC | Sync quotidienne (J-1 + J-2 rattrapage) |

### Vercel

Importation directe depuis GitHub, framework **Other**, root `/`.  
Redéploiement automatique à chaque push sur `main`.

## Structure des fichiers

```
├── index.html                    ← PWA complète (front)
├── manifest.json                 ← Manifest PWA
├── sw.js                         ← Service Worker
├── favicon.ico                   ← Favicon
├── favicon-32.png                ← Favicon 32px
├── apple-touch-icon.png          ← Icône iOS 180px
├── icon-192.png                  ← Icône PWA 192px
├── icon-512.png                  ← Icône PWA 512px
├── scripts/
│   ├── create-table.sql          ← Schéma Supabase (exécuté une fois)
│   ├── init-db.js                ← Chargement historique 2004 → aujourd'hui
│   └── daily-sync.js             ← Sync quotidienne
└── .github/workflows/
    ├── init.yml                  ← Workflow init (manuel)
    └── daily.yml                 ← Workflow quotidien (cron)
```

## Source des données

[open-pmu-api](https://github.com/nanaelie/open-pmu-api) — API REST open source  
Données disponibles du 22/01/2004 à aujourd'hui, mises à jour régulièrement.

---

© 2026 Olivier BERNARD — Tous droits réservés
