# TabPFN cache and projection provenance follow-up

Read-only checks on September 19 establish that the active cache is **`nfl_features.tabpfn_projections`**, not a predictions-dataset table. It contains 66,383 total rows and was modified September 17 at 10:32:29.938 UTC. The Week 2 partition contains **928 unique player keys**, no missing core mean/quantile values and no nonmonotone quantile rows. It covers **all 405 modeled skill players** in the archived frame. [Support receipt](reviews/evidence/2026-09-19-tabpfn-live-support.json).

The consumers differ:

- Production `run_projections.project` produces component-simulation summaries and market-blended `proj_points`; it does not apply the lab's TabPFN marginal shaping. The absence of the cache in both scratch arms does not by itself invalidate that mean-projection comparison.
- Lab `live_inputs` explicitly reads the features cache and passes it to `apply_draw_shape`. `TABPFN_MARGINALS=1` enables it. An empty `TABPFN_MARGINAL_TABLE` means the default `tabpfn_projections` table, not disabled caching. It replaces player marginal quantiles while preserving rank dependence, before later centering on production means.

The earlier other-agent claims that live lacked a TabPFN cache and that production loads no serialized model were withdrawn after source/warehouse checks. The projection entry point calls `load_latest_component_models`, which loads the component registry. Both scratch outputs independently record **`pooled/components__tail_k1/2026-W32`**: 504 rows / 472 distinct GSIS ids each, generated at 00:54:57.036884 UTC (repair) and 01:01:29.392707 (control). [Query receipt](reviews/evidence/2026-09-19-isolated-projection-model-identities.json). Exact storage-object identities and original runner bytes are still requested; equal version labels alone do not pin mutable objects.

The written Saturday runbook orders **build-features → tabpfn-gen → project-slate**, before the 10:30 CT build. Thus a adopted salary repair needs the cache regenerated after repaired features; keeping the old cache can preserve stale marginal shapes. The live TabPFN job is an immutable-image L4 job with 4 CPUs, 16 GiB and a one-hour timeout; its image digest is `7eeff44e7c225fed62682b3649dfa86d77f86227e3e9858c967d132deff2a10a`. Recent execution durations and deployed source behavior are still being checked.

Isolation caution: `scripts/tabpfn_gen/gen.py` hardcodes the `nfl_features` dataset. Ordinary `BQ_FEATURES_DATASET` overrides do not redirect it. A scratch refresh therefore needs an explicit reviewed adapter/image with asserted input/output destinations; running the ordinary generator with those overrides would risk writing the live cache. No refresh or job mutation has been performed in this review.

The current source supports upcoming-only refresh while preserving historical rows, but that capability must be verified against the deployed image before operational use. The code's upcoming-context selection also relies on available training rows being prior to the target; an isolated comparison must explicitly validate that temporal boundary. Full repaired-entry distribution effects remain distinct from the measured production mean changes and the completed usage-only hsim study.

## Latest successful refresh, verified from provider logs

Execution `tabpfn-gen-5nv4d` ran September 17 from 10:19:21.854633 to 10:32:43.193826 UTC, approximately 13 minutes 21 seconds, with one successful task. It performed a full cache rebuild; the upcoming 2026 Week 2 prediction step itself took 71 seconds for 928 rows. The receipt records 66,383 unique output keys, 28,000 maximum context rows, four estimators, seed 7, and feature-contract SHA `52cc95c500bc3bd4223baacb29be73e3df4d637ce289b6431735cddd46195b83`. Training then contained 102,927 rows spanning 2014–2025; the missing Week 1 salary spine therefore also excluded 2026 context rows. [Sanitized provider receipt](reviews/evidence/2026-09-19-tabpfn-latest-execution.json).

The executed receipt has an empty `code_sha`; the immutable image digest is available, but local-source equivalence and upcoming-only support still need image inspection. A historical full refresh of this duration supports testing an isolated refresh within the remaining preparation window; it does not guarantee future runtime. No refresh has been launched by this audit.
