# PMU Stats 🏇

PWA d'analyse des arrivées de courses PMU — données Supabase, déploiement Vercel.

## Architecture

```
open-pmu-api (source) → GitHub Actions (cron) → Supabase (BDD) → PWA Vercel (front)
```

## 1. Créer la table Supabase

Dans ton dashboard Supabase → **SQL Editor**, exécute le contenu de `scripts/create-table.sql`.

## 2. Ajouter les secrets GitHub

Dans ton repo GitHub → **Settings → Secrets → Actions**, ajouter :

| Secret | Valeur |
|--------|--------|
| `SUPABASE_URL` | `https://njohmpmbxemeieqakszw.supabase.co` |
| `SUPABASE_SERVICE_KEY` | Ta clé `service_role` (Settings → API dans Supabase) |

> ⚠️ La clé `service_role` est **différente** de la clé `anon`. Elle permet l'écriture. Ne jamais l'exposer dans le front.

## 3. Charger l'historique (une seule fois)

Dans GitHub → **Actions → PMU Init Historique → Run workflow**

Le script charge toutes les courses de 2010 à aujourd'hui (~5 500 jours).  
Durée estimée : 2 à 4 heures.

## 4. Déployer sur Vercel

1. Aller sur [vercel.com](https://vercel.com) → New Project
2. Importer le repo `PMU-STATS`
3. Framework : **Other** (pas de build)
4. Root directory : `/`
5. Deploy → l'URL est prête

## 5. Sync quotidienne automatique

Le fichier `.github/workflows/daily.yml` déclenche automatiquement chaque matin à 6h UTC la sync de la veille.

Pour déclencher manuellement : **Actions → PMU Daily Sync → Run workflow**

## Structure des fichiers

```
├── index.html              ← PWA complète (front)
├── manifest.json           ← Manifest PWA
├── sw.js                   ← Service Worker
├── scripts/
│   ├── create-table.sql    ← Schema Supabase (à exécuter une fois)
│   ├── init-db.js          ← Chargement historique 2010→aujourd'hui
│   └── daily-sync.js       ← Sync quotidienne (J-1 + J-2 rattrapage)
└── .github/workflows/
    ├── init.yml            ← Workflow init (manuel)
    └── daily.yml           ← Workflow quotidien (cron 6h UTC)
```

## Fonctionnalités de l'appli

- 📅 **Journée** : toutes les courses d'une date, arrivées, partants, dotations
- 🔢 **Dossards** : fréquence de victoire par numéro sur période choisie
- 🏟 **Hippodromes** : classement par volume et dotation moyenne
- 📊 **Types** : répartition et stats par type (Attelé, Monté, Plat, Haies, Steeple)
