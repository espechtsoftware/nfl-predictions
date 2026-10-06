-- Player-name join key, the SQL twin of dashboard.teams.norm_name: upper
-- case, punctuation out, generational suffixes out, spaces out.
CREATE TEMP FUNCTION norm(s STRING) AS (
  REGEXP_REPLACE(
    REGEXP_REPLACE(
      REGEXP_REPLACE(UPPER(IFNULL(s, '')), r'[^A-Z0-9 ]+', ' '),
      r'(\s+(JR|SR|II|III|IV|V))+\s*$', ''),
    r'\s+', '')
);

-- Team code in the DraftKings / Fantasy Points spelling (LAR, JAX, WAS), so
-- vendor rows join slate rows on name AND team.
CREATE TEMP FUNCTION team_code(t STRING) AS (
  CASE UPPER(IFNULL(t, ''))
    WHEN 'LA' THEN 'LAR' WHEN 'STL' THEN 'LAR' WHEN 'JAC' THEN 'JAX'
    WHEN 'WSH' THEN 'WAS' WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
    ELSE UPPER(IFNULL(t, '')) END
);
