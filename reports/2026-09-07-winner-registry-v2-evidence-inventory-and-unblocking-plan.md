# Winner registry v2 evidence inventory and unblocking plan

- **Date:** 2026-09-07
- **Production base:** `746f98d3530f64c8d95a3e7e9b648dd8cc3400df`

**Disposition:** strict v2 remains blocked on first-party DraftKings result
evidence; LineStar can accelerate contest identification but cannot establish
an official winning score; no alternative authority path is authorized here

## Executive result

Registry v2 is not waiting on its candidate-ledger implementation. It is
waiting on evidence that proves, in one source chain, both the exact target
DraftKings contest and that contest's official winning score.

The bounded inventory found no historical raw DraftKings standings or contest
result export in the inspected production repository, lab repository, common
operator download locations, production GCS prefixes, lab GCS object names, or
the live warehouse. The current strict validator is therefore correct to
accept zero contests and to keep winner-referenced efficacy for experiments
080, 081, and 082 on hold.

The useful new finding is narrower. The legacy LineStar ownership backfill
preserved exact-looking DraftKings contest IDs, contest names, entry counts,
and fees in `nfl_raw.contest_ownership`. It supplies at least one standard
Fantasy Football Millionaire locator for every 2023--2025 week. An immutable,
receipted refetch of those public LineStar responses could efficiently resolve
the target-contest identity side of v2 under an owner-frozen, identity-only
policy. LineStar has no winner rank, winning roster, or winning score in this
feed and cannot satisfy `official_target_winning_score`.

There are consequently two possible owner paths:

1. retain the strict official cohort and recover original DraftKings result
   exports; or
2. if those exports cannot be recovered, explicitly authorize a separately
   named, non-official historical cohort with a frozen authority hierarchy and
   sensitivity analysis.

This report does not make the second decision, weaken the existing validator,
or authorize any 080/081/082 efficacy launch.

## Scope and safety boundary

This was a read-only evidence census. It inspected tracked public/production
artifacts, warehouse metadata and derived ownership rows, GCS object names and
one already-public LineStar source contract. It did not:

- open held or sealed experiment outcomes;
- mutate BigQuery, GCS, Cloud Run, Cloud Build, Neo4j, or any vendor service;
- modify registry validators, candidate data, target policy, or receipts;
- treat an article, roster sum, third-party contest locator, or owner opinion
  as an official DraftKings result; or
- select a historical target contest using its observed score.

The local/GCS search is bounded to the locations listed below. A result export
may still exist in an operator-controlled browser profile, email attachment,
external backup, or other storage not included in this census.

## Frozen implementation and artifact identities

Registry v2 entered production at commit
`b193e54ef53dc71347d693c14acf3b5e68f1e898`. The relevant tracked artifacts
remain unchanged on the production base inspected here:

| Artifact | Git blob | File SHA-256 | Relevant state |
|---|---|---|---|
| `reports/2026-09-01-winner-registry-v2-adjudication-status.md` | `80cf2d1535efe3632f1d4fe45727201b2b82e1ab` | `fd17ec02341b45b90038bfd854818cab935b79fcfb52b719cd874f4ea10d7c3a` | Existing disposition and source reconciliation |
| `reports/winner-registry/winner-registry-v2-candidate-ledger.json` | `6faae509f1b7681db0e6ce5d17b61bec5006d9ff` | `dc11ff9b21b5c4ba60e0d48bc33fdb911af1a1ee18d5a658b38a19675b461c7b` | 117 observations; no official score |
| `reports/winner-registry/winner-registry-v2-target-contest-policy.template.json` | `3b05d5dd12f0ed66ab9089bb4a411ad2600dabe7` | `76dc5ef0b689efa7ee80da47a2cb872fd1869ac1af6f7347a8a175e1723420e9` | Draft and unresolved |
| `reports/winner-registry/winner-registry-v2-adjudication-receipt.template.json` | `d0a5fe8dc0bcaf57e80fcbc8d9f8d4f2694d564f` | `038c96f7cd3c87629f15f2915aba11168ba4b8d35a24417ab27cbcc59d7aa8f9` | Example only; no adjudication |
| `reports/winner-registry/winner-registry-v1.json` | `375fa1100fbe4134698025215930f49532d3ada4` | `13286cd428cecfcdb27544d4f590a970f526a2474f04b83b8a4328859866bdab` | Derived v1; no promotion authority |
| `src/nfl_dfs/research/winner_registry_v2.py` | `bba8a32bcd77ada14aef53ebe8b040806739ac70` | `0fca4136427be09f0698f809bb1435abb119ba70574b262069e63a58ed266c7d` | Strict official-evidence validator |

The candidate ledger's own canonical content identity is
`9e25731886a4a08b1994e83a33f051eda88c6bb8da3c434b397dcf327632eaf3`.
Its audited summary is:

- four source artifacts and 917 physical source rows;
- 117 independent observations over 70 distinct season/week labels;
- zero non-null `official_target_winning_score` values; and
- zero observations eligible to become an accepted official cohort without
  external adjudication evidence.

Registry v1 contains 68 rosters, including a governed 51-roster subset with 17
rows in each of 2023, 2024, and 2025. Its canonical registry identity is
`b8fc84eeeab18f64bdf1b4bef0888301c5c1434227d6b8066baef4fe7597e302`.
It declares `contest-id-absent`, `source-url-absent`, and
`capture-time-absent`, and `promotion_authority` is false.

The immutable GCS copy of v1 is byte-size identical but remains a derivative,
not an original result source:

```text
gs://nfl-predictions-503414-corpus-retrieval/research/
  corpus-r6-winner-registry/
  20260827-adopted-milly-winner-registry-v1/winner-registry-v1.json
generation: 1787857632161809
bytes: 74045
```

## What strict v2 actually requires

The current validator does not merely require a plausible score. For every
accepted observation it requires:

- a frozen target policy with owner, approval time, effective season scope,
  platform, sport, slate scope, contest family, roster format, selection rule,
  and multiple-contest rule;
- `official_score_authority` exactly equal to
  `draftkings_official_contest_export`;
- season, week, exact DraftKings contest ID, contest name, contest family,
  slate date, lock time, Classic roster format, entry fee, and top prize;
- three permanently separate fields:
  `official_target_winning_score`, `captured_roster_points_sum`, and
  `article_or_summary_reported_score`;
- content identity for the original candidate source artifact;
- an official evidence object whose content binds both the same exact contest
  ID and the same official score;
- adjudicator name, role, time, reason, deterministic receipt ID, and receipt
  SHA-256; and
- no duplicate accepted contest ID and no more than one accepted target
  contest per policy season/week.

This is the correct boundary. Editorial pages plus a LineStar locator cannot
pass it, even when their values appear plausible or agree.

## Existing score and roster evidence

The four source artifacts represented in the v2 ledger are:

| Source | Bytes | SHA-256 | Authority retained by v2 |
|---|---:|---|---|
| `reports/milly-winners-2019-2023-2024.csv` | 17,609 | `86359e22fdfbe87e9d1f899dd864038979881db5abbafbf26b40b1ff31985885` | User-supplied roster capture and component sum |
| `reports/milly_rosters_2023_2024.csv` | 12,349 | `b56d0a72db347be0a92a1cde23cf5fd680d9f5a4ff1ba701d1cfb809d9c3599d` | Article-derived roster capture and article score |
| `reports/2025-milly-rosters.csv` | 5,310 | `685db4eb916fb32f64af3138b1893a1b14dfeacd0e55d7ea8b968a2aaa103e3d` | User-supplied roster capture and component sum |
| `reports/2025-milly-winners.csv` | 1,725 | `adeef608421736c13c2ff6b18c84e8df41c8880f1b6576e34d35d85f7e38fbc9` | Summary-reported score |

The lab file `results/contest/milly_winners.json` is 877 bytes, Git blob
`10971defb449b2e25cd6e2b7cd9fb043117251e7`, and SHA-256
`4e0d57c2f100cfbed37a026c3273b233f8b09c6a6779a60060564a8b56d6ce3f`
at lab ref `e2f6f8f5a27c5db040302f8441162d850cbe9f24`. It is derivative of the local
article and 2025 summary sources, not an independent official authority.

The September 1 reconciliation remains controlling: the lab's 48 score labels
and production's governed 51 roster labels share 46 season/week labels; only
35 shared scores agree, 11 differ by as much as 30.46 points, and at least four
shared labels contain different nine-player rosters. Season/week therefore
cannot stand in for contest identity.

## Evidence matrix

| Evidence | Exact contest identity | Official winning score | Captured roster sum | Article/summary score | Immutable original receipt | Strict-v2 use |
|---|---|---|---|---|---|---|
| Registry v1 | No | No | Yes, derived | Sometimes, derived | Derived GCS copy only | Candidate/reconciliation context only |
| Registry-v2 candidate ledger | Unresolved | All null | Separate field | Separate field | Exact tracked-source identities | Candidate ledger only |
| Four source CSVs | No | No | Where roster points exist | Where article/summary value exists | Tracked byte identities | Original candidate evidence only |
| Lab 48-score JSON | No | No | No | Derived values | Tracked lab byte identity | Cross-check only |
| BigQuery LineStar ownership | Exact-looking ID/name plus embedded field/fee | No; `fpts` is entirely null | No | No | Derived warehouse rows; raw bytes absent | Identity locator only |
| GCS registry-v1 object | No | No | Derived | Derived | Immutable derivative generation | Reproduction only |
| DK Network recap pages | Usually no recapped contest ID | Editorially reported, not export authority | Screenshot/article context | Yes | Public page, not official-result export | Separately labelled editorial evidence only |
| DraftKings full standings/result export | Yes | Yes | Potentially | Not needed | **Not found** | Missing strict-v2 authority |

## Local, GCS, and warehouse inventory

### Local filenames

A filename-only search covered:

- `/home/erich/projects/nfl-predictions`;
- `/home/erich/projects/nfl2`;
- `/home/erich/Downloads`;
- `/mnt/c/Users/Erich/Downloads`; and
- `/mnt/c/Users/Erich/Desktop`.

The search targeted `DKEntries`, full standings, contest standings, contest
results, and contest export files with CSV, ZIP, XLS/XLSX, or JSON extensions.
It returned exactly one file:

```text
tests/fixtures/week1_contest_capture/contest-standings-12345.csv
```

That file is a synthetic prospective-capture fixture and is not historical
evidence.

### GCS

A read-only exact-prefix listing returned no objects:

```text
gs://nfl-predictions-503414-raw/operator/dk-contest-standings/**
```

Name-only recursive scans for the same standings/export filename classes
returned zero matches in each of:

```text
gs://nfl-predictions-503414-raw/**
gs://nfl-predictions-503414-corpus-retrieval/**
gs://nfl-2-506823-lab/**
```

No result object body under a held or sealed experimental prefix was opened.

### BigQuery

`nfl-predictions-503414.nfl_raw.contest_entries` does not exist. This is
stronger than merely having zero rows.

`nfl-predictions-503414.nfl_raw.contest_ownership` exists with:

- 103,556 rows;
- 1,258 distinct contest IDs;
- 72 distinct season/week labels covering 2022--2025; and
- zero non-null `fpts` rows.

Its live schema has only `imported_at`, `season`, `week`, `contest_id`,
`contest_name`, `display_name`, `roster_position`, `pct_drafted`, and `fpts`.
It does not retain source URI, raw content hash, raw byte count, source capture
time, rank, entry roster, or winning score.

The latest backup found,
`nfl-predictions-503414.nfl_backups.contest_ownership_20260907`, is a
103,556-row snapshot at `2026-09-07T07:02:15.871Z` of the same legacy table and
schema. It proves preservation of the derived rows, not preservation of the
LineStar response bytes or a DraftKings result.

The prospective DDL and archive workflow in `sql/raw/004_ownership.sql`,
`docs/dk-full-field-capture.md`, and
`docs/week1-contest-capture-rehearsal.md` describe the missing provenance
contract, but that contract cannot retroactively create historical evidence.

## The LineStar identity-only opportunity

`src/nfl_dfs/ingest/linestar_backfill.py` documents the public endpoint and
shows exactly how the legacy rows were constructed. For every
`Ownership.ContestResults` object it stored:

- `ContestId` as `contest_id`; and
- `ContestName`, `EntryCount`, and `EntryFee` together in `contest_name`.

The live table therefore contains useful contest locators even though the raw
response was not archived. Across distinct contest rows it contains 97 names
with “millionaire” and 79 matching the diagnostic standard-family prefix
`^NFL [$][0-9.]+M Fantasy Football Millionaire`.

For 2023--2025, this diagnostic prefix produces:

| Season | Candidate contests | Covered weeks | Same-week alternatives |
|---:|---:|---:|---:|
| 2023 | 20 | 18 | 2 |
| 2024 | 18 | 18 | 0 |
| 2025 | 23 | 18 | 5 |

Ordering those candidates within season/week by embedded entry count produces
one identity locator for all 54 weeks. This is a completeness diagnostic, not
an adopted target policy. For example, 2023 Week 2 resolves diagnostically to:

```text
contest_id: 150206184
contest_name: NFL $4M Fantasy Football Millionaire
              [$1M to 1st + ToC Semifinal Entry]
entry_count: 236627
entry_fee_usd: 20
```

One unarchived read-only probe through the existing public importer contract
also exposed LineStar group/slate identity, Main slate label, slate start UTC,
purse, salary cap, and nine-slot Classic roster requirements for that period.
Its `Ownership.ContestResults` payload contained contest metadata and player
ownership only; it contained no rank, winning entry, winning lineup, or score.
Because that probe was not captured create-only with a source receipt, it is
diagnostic evidence only.

The direct historical DraftKings URLs tested for contest `150206184` now each
return HTTP 404:

```text
https://www.draftkings.com/contest/exportfullstandingscsv/150206184
https://www.draftkings.com/contest/gamecenter/150206184
https://www.draftkings.com/contest/detail/150206184
```

This does not prove that no owner-controlled copy exists. It does show that
the unauthenticated historical URL is not presently a recovery source.

## Exactly what remains missing

### Policy fields

The owner has not frozen:

- the effective season/week universe, including whether and how Week 18 is
  included;
- the exact Millionaire contest-family/name rule by era;
- the Sunday-main/common-lock and special-slate exclusions;
- entry-fee, top-prize, field-size, or GPP criteria used to define the target;
- the deterministic rule when same-week alternatives exist; or
- cancellation and renamed-family handling.

The selection rule must be based on pre-score contest identity. “Use the
highest winning score” is not admissible.

### Strict evidence fields

For every contest accepted into strict v2, the project still lacks an original
DraftKings result artifact and receipt that jointly support:

- the exact target contest ID and contest name;
- the selected contest's official winning score;
- preferably the winning entry/roster for cross-checking;
- source URI or recovery location;
- exact bytes and content SHA-256;
- capture/recovery time and physical row range; and
- an adjudicator's deterministic acceptance receipt.

LineStar can reduce the identity search space, but cannot fill this score
evidence gap. Owner approval cannot transform a third-party locator, an
article scalar, or a roster-component sum into an official export.

## The two owner paths

### Path A: strict official registry v2

This path preserves the existing validator and intended authority.

The owner freezes an identity-only target policy, production materializes a
receipted LineStar locator map, and the known contest IDs are used to search
operator-controlled backups, browser downloads, email, prior machines, cloud
drives, or another genuine first-party archive. Each recovered DraftKings
export is captured immutably and adjudicated. Only contests with complete
official evidence enter v2; missing contests remain missing rather than being
imputed.

This is the only route to populate `official_target_winning_score` under the
current contract.

### Path B: separately authorized non-official historical cohort

If official exports cannot be recovered promptly, the owner may decide later
to authorize a distinct cohort such as `adjudicated_target_score_v1`. That
decision would need to freeze, before any downstream efficacy read:

- LineStar only as target-identity evidence after a receipted raw refetch;
- first-party DK editorial evidence where it exists;
- article/summary scores and captured roster sums as separately labelled
  axes, never collapsed into an official field;
- an explicit rule for disagreements and missing authorities;
- two-authority or interval sensitivity in every downstream result; and
- `exploratory` or `shadow-only` labels for historical efficacy, with
  prospective 2026 capture remaining the adoption authority.

That path would require a separately named authority/schema contract and fresh
080/081/082 bindings. It must not weaken `winner_registry_v2.py` in place or
populate `official_target_winning_score`. **Nothing in this inventory grants
that authorization.**

## Fastest defensible unblocking sequence

1. Preserve registry v1, the v2 candidate ledger, strict validator, and current
   080/081/082 efficacy holds unchanged.
2. Freeze an owner-approved, identity-only target policy: DraftKings NFL
   Classic, Sunday Main/common-lock, intended Millionaire family, $1 million
   first prize, deterministic largest-field or other declared tie-break, and
   explicit Week 18/special-slate handling. Do not use observed score.
3. Perform one respectful LineStar refetch for the required historical
   periods. Archive each original response create-only with URI, capture time,
   bytes, content SHA-256, period ID, and extraction receipt. Do not treat this
   as score evidence.
4. Materialize and hash the resulting target-contest identity map. Require one
   selected contest per in-scope policy slate and retain every rejected
   same-week alternative with its reason.
5. Search operator-controlled external locations by those exact contest IDs
   for original DraftKings full-standings/result exports.
6. If official exports are recovered, archive them create-only and complete
   one strict adjudication receipt per accepted contest, preserving all three
   score axes.
7. If the search fails, stop the strict path at zero/incomplete official
   acceptance. Ask the owner whether to authorize Path B; do not infer that
   decision from schedule pressure.
8. Only after an accepted cohort has a frozen count/hash should production
   build the corresponding winner CDF and bind fresh 080/081/082 efficacy
   manifests and readers to that exact authority.
9. Keep experiment 081's already separate mechanics work distinct from the
   score-bearing efficacy hold. A mechanics pass does not discharge the
   registry gate.
10. Independently apply and rehearse the prospective Week-1 capture contract
    before live settlement. That prevents recurrence but does not repair the
    historical registry.

## Reproducible read-only evidence queries

These commands disclose no credentials or licensed payload content. They are
included to make the census reproducible; their results above are descriptive
and do not constitute a frozen source receipt.

### Ledger summary

```bash
jq '{
  schema_version,
  ledger_sha256,
  source_artifact_count,
  observation_count,
  distinct_season_week_label_count,
  official_target_score_count,
  physical_rows: ([.source_artifacts[].physical_layout.data_row_count] | add)
}' reports/winner-registry/winner-registry-v2-candidate-ledger.json
```

### Bounded local filename census

```bash
rg --files \
  /home/erich/projects/nfl-predictions \
  /home/erich/projects/nfl2 \
  /home/erich/Downloads \
  /mnt/c/Users/Erich/Downloads \
  /mnt/c/Users/Erich/Desktop 2>/dev/null \
  | rg -i \
    '(^|/)(dkentries|.*(full[-_ ]?standings|contest[-_ ]?(standings|results?|export))).*\.(csv|zip|xlsx?|json)$'
```

Only the synthetic Week-1 fixture listed above matched.

### Warehouse coverage and score absence

```sql
SELECT
  COUNT(*) AS row_count,
  COUNT(DISTINCT contest_id) AS contest_ids,
  COUNT(DISTINCT CONCAT(CAST(season AS STRING), '-', CAST(week AS STRING)))
    AS season_weeks,
  MIN(season) AS first_season,
  MAX(season) AS last_season,
  COUNTIF(fpts IS NOT NULL) AS rows_with_fpts
FROM `nfl-predictions-503414.nfl_raw.contest_ownership`;
```

Observed result:

```text
row_count=103556, contest_ids=1258, season_weeks=72,
first_season=2022, last_season=2025, rows_with_fpts=0
```

### Diagnostic LineStar identity coverage

The broad and standard-prefix counts came from:

```sql
WITH contests AS (
  SELECT season, week, contest_id, contest_name
  FROM `nfl-predictions-503414.nfl_raw.contest_ownership`
  GROUP BY 1, 2, 3, 4
)
SELECT
  COUNTIF(LOWER(contest_name) LIKE '%millionaire%')
    AS broad_millionaire_contests,
  COUNTIF(REGEXP_CONTAINS(
    contest_name,
    r'^NFL [$][0-9.]+M Fantasy Football Millionaire'
  )) AS standard_name_contests
FROM contests;
```

Observed result: `broad_millionaire_contests=97` and
`standard_name_contests=79`.

The per-season diagnostic locator query was:

```sql
WITH contests AS (
  SELECT
    season,
    week,
    contest_id,
    contest_name,
    SAFE_CAST(
      REGEXP_EXTRACT(contest_name, r'[[]([0-9]+) entries, [$]') AS INT64
    ) AS entry_count,
    SAFE_CAST(
      REGEXP_EXTRACT(contest_name, r'entries, [$]([0-9.]+)[]]') AS NUMERIC
    ) AS entry_fee_usd
  FROM `nfl-predictions-503414.nfl_raw.contest_ownership`
  WHERE season BETWEEN 2023 AND 2025
  GROUP BY 1, 2, 3, 4
), candidates AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY season, week
      ORDER BY entry_count DESC,
               SAFE_CAST(contest_id AS INT64) ASC,
               contest_id ASC
    ) AS candidate_rank
  FROM contests
  WHERE REGEXP_CONTAINS(
    contest_name,
    r'^NFL [$][0-9.]+M Fantasy Football Millionaire'
  )
)
SELECT
  season,
  COUNT(*) AS candidate_contests,
  COUNT(DISTINCT week) AS covered_weeks,
  COUNTIF(candidate_rank = 1) AS selected_identity_rows,
  COUNTIF(candidate_rank > 1) AS same_week_alternatives
FROM candidates
GROUP BY season
ORDER BY season;
```

The `candidate_rank` expression is an inventory diagnostic. It is not a
frozen policy and must not be imported into the registry until the owner has
approved the target definition.

### Object-store census

```bash
gcloud storage ls --recursive \
  'gs://nfl-predictions-503414-raw/operator/dk-contest-standings/**'

# Name-only scans; do not open held result bodies.
for bucket_uri in \
  'gs://nfl-predictions-503414-raw/**' \
  'gs://nfl-predictions-503414-corpus-retrieval/**' \
  'gs://nfl-2-506823-lab/**'
do
  gcloud storage ls --recursive "$bucket_uri" \
    | rg -i '/(dkentries|[^/]*(full[-_ ]?standings|contest[-_ ]?(standings|results?|export))[^/]*)\.(csv|zip|xlsx?|json)(#.*)?$'
done
```

The exact production prefix matched no objects, and each name-only bucket scan
matched zero candidate historical export names.

## Final disposition

The inventory improves the path to contest identity but does not change the
scientific gate. Registry v2 has zero official accepted contests because the
official result evidence is absent. Independently authorized outcome-disabled
mechanics work, including the current experiment-081 mechanics chain, remains
separate; winner-referenced efficacy for 080, 081, and 082 must remain held
until either:

- strict official receipts exist and are frozen, or
- the owner explicitly authorizes a separately named non-official historical
  cohort and production builds fresh downstream contracts around that lesser
  authority.

Prospective official Week-1 capture remains the decisive way to ensure this
evidence gap does not recur.
