-- À exécuter dans Supabase SQL Editor
-- https://supabase.com/dashboard/project/njohmpmbxemeieqakszw/sql

CREATE TABLE IF NOT EXISTS courses (
  id            BIGSERIAL PRIMARY KEY,
  date          DATE NOT NULL,
  reunion       TEXT NOT NULL,          -- ex: R1
  course        TEXT NOT NULL,          -- ex: C4
  rc            TEXT NOT NULL,          -- ex: R1C4
  lieu          TEXT,
  type          TEXT,                   -- Attelé, Monté, Plat, Haies, Steeple...
  prix          TEXT,
  distance      INTEGER,
  montant       BIGINT,
  partants      INTEGER,
  non_partants  JSONB,                  -- tableau des numéros non partants
  arrivee       JSONB,                  -- [1er, 2e, 3e, 4e, 5e]
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(date, rc)
);

-- Index pour les requêtes fréquentes
CREATE INDEX IF NOT EXISTS idx_courses_date  ON courses(date DESC);
CREATE INDEX IF NOT EXISTS idx_courses_lieu  ON courses(lieu);
CREATE INDEX IF NOT EXISTS idx_courses_type  ON courses(type);
CREATE INDEX IF NOT EXISTS idx_courses_rc    ON courses(rc);

-- Accès public en lecture seule (anon key)
ALTER TABLE courses ENABLE ROW LEVEL SECURITY;
CREATE POLICY "lecture publique" ON courses FOR SELECT USING (true);
