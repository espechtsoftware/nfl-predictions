-- Player-name join key, the SQL twin of dashboard.teams.norm_name: upper
-- case, punctuation out, generational suffixes out, spaces out.
CREATE TEMP FUNCTION norm(s STRING) AS (
  REGEXP_REPLACE(
    REGEXP_REPLACE(
      REGEXP_REPLACE(UPPER(IFNULL(s, '')), r'[^A-Z0-9 ]+', ' '),
      r'(\s+(JR|SR|II|III|IV|V))+\s*$', ''),
    r'\s+', '')
);
