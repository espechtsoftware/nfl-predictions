# Build automation design: from an armed week to an orchestrated week (2026-10-04)

**For:** the operator (decisions) and the reviewer (design review).
**Status:** a proposal, revised (v2) after the reviewer's design review, 10-04 (§10 is binding on the design). Nothing changes before Week 6 (operator, 10-04: "I don't want to change anything in the next
week or two, but eventually it would be nice if the entire build process could be automated so it doesn't need to be
manually done by you. I'll still want you to monitor it however.").

## 1. Goal and non-goals

**Goal.** Each week's build, from the Saturday refresh to Monday's scoring, runs by itself, from one reviewed
description of the week. Every gate is checked and every failure is reported. The agent's role becomes monitoring,
investigating and proposing, not arming and running steps by hand.

**Non-goals.**
- No change to what the system computes (selectors, layouts, models). This is plumbing.
- No automatic DraftKings entry upload. DraftKings has no supported API for it; the operator uploads, as today.
- No move of heavy compute to Cloud Run. It stays local (operator constraint: no heavy Cloud Run).
- No change to the validity laws or the money-path rules. Automation makes them easier to enforce, not optional.

## 2. How a week runs today

- **Data:** Cloud Run jobs (`ingest-props`, `build-features`, `tabpfn-gen`, `project-slate`, `ingest-dk`, ...), some on
  Cloud Scheduler and some executed by the agent (operator 09-29).
- **Builds:** `scripts/arm_week_timers.sh <W> --run` creates about 10 transient `systemd-run --user` timers on the
  laptop. Each runs `run_week_build.sh` / `sunday_build_host.sh` (lab clone pinned by SHA) or the watchers
  (`sunday_after_build.sh`, entries, R4/late swaps).
- **Configuration:** a long environment line (the "arm line") in the take-over document, plus `week_env.sh` defaults
  and private inputs under `~/weekN-sunday/` (`contests.json`, `chosen-dose.env`, ownership files).
- **Gates:** spread across scripts: `check_week_runtime.py`, `check_build_inputs.py`, `check_ownership_lag.py`,
  `check_prospective_gates.py`, `audit_build_levers.py`, `verify_k90`, the vetters, the leakage suite.
- **Fallbacks:** shell branches with `!!!` banners (ownership source, Saturday supply, PMO main, field sleeve, T-70
  refusal, superseded builds).
- **Monitoring:** the agent's session reminders (cron prompts). They live only in the chat session.

### Pain points, each one observed

| Date | What happened | Root cause |
|---|---|---|
| 09-18 | Shadow gates sat PAUSED, and two jobs carried an old policy | Config spread across schedulers and job env; no single source |
| 10-01 | `LEV_CBC_THREADS` never reached the build | An env pass-list in one script not updated |
| 10-02 | The production checkout was 211 commits behind the tested code | No release step; the "frozen checkout" is a convention |
| 10-02 | `sunday_build_host.sh --check` started a real build (O-19) | Checks and actions share entry points with different flag semantics |
| 10-03 | The arm stopped at 10:13 because one validator still expected a single dose (O-20) | A setting validated in one place, defaulted in another; the preflight stops at its first failure |
| all weeks | Arming, refresh and checks done by hand at fixed clock times; reminders die with the session | No orchestrator; time-based, not event-based |

The pattern: **the logic is good and well guarded, but the wiring is manual and duplicated.**

## 3. Requirements

1. One source of truth per week, validated against a schema, reviewed and versioned.
2. Every gate is a first-class, fail-closed check that reports **all** failures, with its evidence.
3. Fallbacks are explicit, visible branches, and alerts say which branch ran.
4. Event-driven where the world is event-driven: inactives, salary refresh, vendor captures, standings imports.
5. Heavy compute stays local; cloud data jobs are called as they are today.
6. Runs from an immutable, pinned release, never a working checkout.
7. Monitoring survives without the agent: run history, a status page, push alerts.
8. Human approvals where they belong: contest plan, dose, any new rule, the upload.
9. Rehearsal and replay of any week with the same graph, into a scratch namespace.
10. Rollback to today's systemd path at any point during migration.

## 4. Options considered

| Option | Fit | Cost | Verdict |
|---|---|---|---|
| A. Keep systemd timers, add a week manifest and a single preflight | Fixes config drift and the all-failures check; no orchestration, history or event triggers | Lowest | **Phase 1 of the recommendation**, not the end state |
| B. **Dagster (open source), self-hosted on the laptop** | Assets and asset checks map onto our artifacts and gates; weekly partitions; sensors for events; run history UI; local execution | Free; one always-on service | **Recommended** |
| C. Prefect Cloud (hosted control plane) + a local worker | Good UI, retries, notifications, hosted (survives laptop outages for alerting) | Free tier; a SaaS dependency | A strong alternative if a hosted status page matters more than asset checks |
| D. Cloud Workflows + Cloud Scheduler, laptop as a pull worker | GCP-native, cheap, survives the laptop | Glue to build: a work queue and a laptop agent | More bespoke code than B or C for the same result |
| E. Airflow / Temporal | Capable | Heavy to run and learn for one operator | Rejected: overkill |

**Why Dagster.** The system's culture is artifacts plus gates: receipts, sha256 identities, audits, leakage checks.
Dagster models exactly that.
- **Assets:** each weekly artifact (the projection batch, the Saturday supply, the 09:10 union, the T-70 union, the
  entry bundle, the settlement, Monday's readers) is a named asset with upstream dependencies.
- **Asset checks:** each gate is attached to the asset it guards and blocks downstream materialisation when it fails.
- **Partitions:** one per NFL week, with rehearsal and backfill per partition.
- **Sensors:** a step fires when its real input exists (inactives posted, a salary pull after 10:30, the FP capture
  landed), not at a guessed minute.

## 5. Recommended architecture

```
                 week manifest (YAML, schema-validated, reviewed)
                                   |
                     Dagster (laptop, always-on service)
   sensors: schedule | inactives posted | DK salary refresh | FP capture | standings imported
                                   |
   assets (week partition):
     refresh  --> projections --> saturday_supply --> union_0910 --> entry_bundle --> settlement --> monday_readers
        |                             sunday_supply --/   t70_union --/      ^            |
     (Cloud Run jobs)              (local builds, pinned lab clone)    R4/swap watcher   dashboard publisher
                                   |
   checks on each asset: build inputs, runtime, ownership lag, audit, verify_k90, vetting, leakage, prospective gates
                                   |
   alerts (push/email) + dashboard v2 status page + run history;  the agent monitors and investigates
```

### 5.1 The week manifest

One YAML file per week, private parts referenced by location, never inlined:

```yaml
season: 2026
week: 5
group: 154xxx
release: v2026.10.11-1          # pinned production release: a tag, run as a read-only worktree (§5.5)
lab_clone_sha: 32cdb61...
doses: {saturday: [2560/10240, 1280/5120], sunday_early: 2560/10240, d3200: 0/4800, t70: 0/4800}
threads: 8
ownership: {predictor: fp, tilt: 0.20, fallback: [tabpfn, blend, lag@0.10], fp_max_age_hours: 30}
union: {main: pmo_x50, sleeve_cap: 0.5, sleeve_source: field, field_rows: 1}
layout: {layout: head, order: greedy, small_max_shared: 5}
times: {saturday_supply: "10:30", sunday_early: "05:00", d3200: "09:10", t70_build: "10:50", lock: "12:00"}
private: {contests: gs://.../week-inputs/2026/w05/contests.json, dose: gs://.../chosen-dose.env}
approvals: {contests: operator, dose: operator, new_rules: []}
```

- Every script reads its settings from the manifest (or from an env rendered from it by one function). This removes
  the class behind the 10-01 and 10-03 failures.
- The manifest is validated against a schema, and the validator is the only place a setting's shape is defined.
- The operator's weekly decisions become a diff to this file, reviewed like code.

### 5.2 Checks

- Today's gate scripts become asset checks unchanged at first: same code, called by the orchestrator.
- A failing check blocks downstream assets and records its evidence.
- The runtime preflight is rewritten to collect **every** failure (O-20).
- Training-vs-serve NULL-rate and NULL-support checks (O-22) are added as checks on the feature build.

### 5.3 Fallbacks

Each fallback becomes an explicit branch with its own asset state:
- ownership source: FP → TabPFN → blend → lag;
- supply: D12800 → D6400;
- main: PMO → mean;
- sleeve: field → projection;
- T-70 refused → the 09:10 book stands.

Alerts name the branch taken. The run page shows which path was used.

### 5.4 Events instead of guessed minutes

| Today (fixed time) | Proposed trigger |
|---|---|
| T-70 DK pull at 10:33 | The official inactives are posted (poll), then the salary pull |
| T-70 project at 10:36 | A salary pull newer than the inactives |
| T-70 build at 10:50 | A projection batch newer than the inactives (the 10:30 gate becomes a dependency) |
| FP captures at agent times | A capture schedule plus a freshness check on the asset |
| Monday readers by reminder | The standings import landing |

Fixed deadlines stay as guards: the lock, the 15:20 entries end, the 15:30 freeze. A guard **refuses**; it never falls back to a fixed-time build on stale inputs (§10 A).

### 5.5 Releases

- Each week runs from a tagged release (`v<date>-<n>`): a **read-only git worktree at the tag** plus its own virtualenv. Not a wheel, because the build needs `scripts/` and `sql/` (§10 B6). The lab clone
  stays pinned by SHA.
- No working checkout is involved, so "don't touch the production folder" stops being a manual rule.
- A release is cut after the Wednesday rehearsal passes on it.

### 5.6 Monitoring and alerts

- Dagster run history, plus a status panel on dashboard v2 (current week: each asset, check, branch taken, timings).
- Push alerts (Pushover, or email) on check failures, fallback branches and missed deadlines. These are independent of
  the agent's session.
- The agent's role: watch the run history and alerts, investigate failures, propose fixes, run the Monday analysis.
  Today's session reminders become a backup.

### 5.7 Approvals and the upload

- The contest plan, the dose and any new rule need operator approval, recorded in the manifest. The approval must be given **by the operator himself** (his commit, or a button with his identity), never written by an agent on his behalf (§10 D2). An approval step in
  the graph blocks Saturday materialisation until it is given.
- The DraftKings upload stays manual. The orchestrator produces the bundle and the R4/swap re-publications as today.

### 5.8 Hosting and resilience

- Dagster runs as a systemd user service with linger, so it starts with WSL.
- **The remaining single point of failure is WSL on the laptop** (reboots, sleep, Windows updates). Mitigations:
  - Windows power settings that never sleep on AC;
  - a watchdog alert if the service is down;
  - an **external dead-man's switch** (§10 D1): the laptop pings an outside heartbeat service every few minutes from Saturday arming to Sunday 15:30, and a missed ping alerts the operator. This is the alert Dagster cannot send;
  - longer term, the workstation or a small always-on machine as the build worker, with the laptop as a standby
    (same release, same manifest).
- Secrets stay in Secret Manager and private files (as today), never in the manifest repository.

## 6. Migration plan

| Phase | When | What | Exit criterion | Rollback |
|---|---|---|---|---|
| 0 | Week 5 | Nothing changes. This document is reviewed. | Operator and reviewer agree on the design | — |
| 1 | Weeks 6–7 | Week manifest + schema; today's arm line and `week_env` generated from it; the all-failures preflight (O-20); release tagging | Two weeks armed from a manifest with identical unit environments (diffed) | Arm by hand from the printed line |
| 2 | Weeks 7–8 | Dagster installed; existing scripts wrapped as assets and checks unchanged; **watch-only**: sensors observe and checks run, nothing is triggered | Two weeks where Dagster's view matches the real run step for step | Uninstall; nothing depended on it |
| 3 | Weeks 8–9 | Wednesday rehearsals run through Dagster into a scratch partition | Two rehearsals pass end to end (publish, R4, swap) | Rehearse by hand as today |
| 4 | Weeks 9–10 | Dagster triggers the Saturday refresh and arming; the Sunday timers still come from systemd | Two Saturdays armed by Dagster, with alerts working | Arm with `arm_week_timers.sh` |
| 5 | Weeks 10+ | Dagster runs Sunday (event triggers) and Monday; the systemd path stays documented as the fallback for 3 weeks | Three clean Sundays | Re-arm with systemd from the manifest |

Each phase is reversible and changes plumbing only. Any phase that touches the money path follows the money-path
rules (rehearsed before an entered book).

## 7. Effort (agent working time, rough)

| Phase | Effort |
|---|---|
| 1 Manifest + schema + generator + all-failures preflight + release tagging | 1–2 days |
| 2 Dagster install + wrapping assets/checks (watch-only) | 2–3 days |
| 3 Rehearsal partitions | 1 day |
| 4–5 Triggering, event sensors, alerts, status panel | 2–3 days |
| Total | about 6–9 working days before review; about 8–11 with §10's requirements, spread over Weeks 6–10 |

## 8. Risks

| Risk | Mitigation |
|---|---|
| The orchestrator is a new failure mode on Sunday | Watch-only and rehearsal phases first; the systemd fallback stays for 3 weeks |
| Wrapping scripts hides their behaviour | Wrap unchanged; one asset per existing script; logs kept verbatim |
| Event triggers fire late or not at all (inactives feed down) | At the guard time the T-70 is **refused**, the 09:10 book stands, and a loud alert goes out. Never a build on pre-inactives inputs (§10 A1) |
| WSL outage | Watchdog alert; future standby worker |
| Config migration error | Phase 1 diffs generated environments against today's arm line byte for byte |

## 9. Decisions for the operator (when ready, not now)

1. Dagster (recommended) or Prefect Cloud (hosted status page, a SaaS dependency).
2. Push alert channel: Pushover (about $5 once per device), email, or both.
3. Whether to plan a dedicated always-on build worker (the workstation or a small machine) for the WSL single point of
   failure.
4. Start date: proposed Week 6, after Week 5's results.

## 10. Reviewer requirements (design review 10-04; binding)

### A. The T-70 event chain
1. **Guards refuse, never fall back to the fixed-time path.** If the inactives event has not arrived by the guard time,
   the T-70 is refused, the 09:10 book stands, and a loud alert goes out. The fixed-time 10:33 pull is pre-inactives,
   which is exactly the money-path violation.
2. **"Inactives posted" is a completeness predicate:** every 12:00-window game on the slate has its list, checked
   against the schedule. The first list does not count. Late-window lists arrive after lock and stay with R4. Cover the
   case where the feed is up but one game's list never appears.
3. **DK must have caught up:** every posted-inactive skill player on the slate shows OUT/IR in the salary pull, or the
   pull is retried until the guard.
4. **The guard time comes from measured durations:** latest start = lock − (p95 of T-70 build + union + audit + vet,
   from the receipts) − the operator's upload margin. It is printed in the manifest render.
5. **Run keys and concurrency:** one run per (week, asset); a tag-level limit of one heavy build at a time on the
   laptop (the 05:00 D12800 and the 09:10 D3200 must never overlap if an event shifts one of them); a duplicate trigger
   is a no-op.

### B. Wrapping scripts unchanged keeps fail-closed only if
1. **There is an exit-code contract per script.** Fallbacks exit 0 (the ownership, field-sleeve and own-term
   step-downs) and a T-70 refusal is a correct outcome. Each wrapped script writes a small structured status beside
   its receipt (branch taken, ok/refused, evidence paths) and the asset reads it, never grepping logs. The table
   (script, exit codes, meaning) is written before phase 2.
2. **Environment:** every subprocess gets an explicit environment rendered from the manifest (as BASE_ENV does today),
   never the daemon's inherited one. Phase-2 test: the subprocess env equals the systemd unit's env
   (`systemctl --user show -p Environment`), byte for byte.
3. **Cancellation and partial outputs:** a cancel or timeout kills the whole process group, or CBC workers survive.
   Every "newest" picker (LATEST, `UNION_SATURDAY_RUN=auto`, the watcher's promotion, the publisher's tags) must ignore
   incomplete run dirs. The pickers are listed and each is tested against a killed run.
4. **Retries OFF for every money-path op** (builds, unions, publish, swaps); they are not idempotent. Retries are for
   read-only steps only.
5. **Cloud Run jobs launched by Dagster still go through `launcher_registry.sh` lanes** (rule 6), and
   `check_prospective_gates.py` is a weekly check asset.
6. **Releases are a read-only git worktree at the tag** plus its venv, not a wheel (`scripts/` and `sql/` are needed).

### C. Exit criteria, tightened
- **Phase 1:** the rendered arm line is byte-identical to the take-over document's line, AND the armed units'
  environments are identical (diffed), for two weeks.
- **Phase 2:** every asset's sha256 equals the real artifact's; every fallback branch Dagster reports equals the banner
  that ran; zero writes by Dagster (a file-system audit of the week dirs and the clone); alert delivery tested end to
  end.
- **Phase 3:** forced-failure drills, not only the happy path. The drills: an FP refusal, a supply fallback, a T-70
  refusal (late inactives), a field-sleeve failure, the inactives feed down until the guard, and the Dagster daemon
  killed mid-run and restarted. Exit only when each branch has run once and alerted correctly.
- **Phase 5:** prove equivalence offline first. Rebuild the previous Sunday through Dagster from the same pinned inputs
  and require byte-identical books (the union is deterministic at 8 threads; paper rebuild 10-02). A parallel live
  shadow is not possible on one laptop. Run one rollback drill (re-arm systemd from the manifest) during phase 5.

### D. Gaps closed
1. **External dead-man's switch** (§5.8): an outside heartbeat check, alerting on a missed ping, from Saturday arming
   to Sunday 15:30.
2. **Approvals are given by the operator himself** (§5.7), never relayed.
3. **The manifest holds private items as pointers only;** a schema test rejects inline private values (stakes, entry
   keys, contest lines).

**Effort impact:** about +2 days (the status contract, drills, picker tests, dead-man's switch), so roughly 8–11
agent days over Weeks 6–10.

