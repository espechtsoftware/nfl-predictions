from copy import deepcopy
import pytest
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_catalog_wide_outcome_successor_v1 as s

def oid(body, name):
    return batch.object_identity_for_json(body, uri=f"gs://fixture/{name}.json", generation="1")

def setup(monkeypatch):
    slates, rows = [], []
    for i in range(54):
        season, week = 2023 + i // 18, i % 18 + 1
        skill, dst = f"p-{i:02d}", f"z-{i:02d}"
        slates.append({"season": season, "week": week, "slate_id": f"{season}-w{week:02d}", "catalog": [
            {"id": skill, "pos": "WR", "team": "AAA", "salary": 5000},
            {"id": dst, "pos": "DST", "team": f"T{i:02d}", "salary": 3000}]})
        for player, score in ((skill, 10), (dst, 5)):
            rows.append({"source_ordinal": i, "season": season, "week": week,
                         "slate_id": f"{season}-w{week:02d}", "player_id": player,
                         "realized_score_micro": score})
    later = {"slates": slates, "freeze_sha256": "b" * 64}; later_id = oid(later, "later")
    base = {"rows": rows, "panel_freeze_identity": oid({"x": 1}, "panel"),
            "panel_freeze_sha256": "d"*64, "later_source_freeze_identity": later_id,
            "later_source_freeze_sha256": "b"*64, "outcome_snapshot_sha256": "c"*64}
    base_id = oid(base, "base")
    monkeypatch.setattr(s.later, "validate_source_freeze", lambda value, **_: value)
    monkeypatch.setattr(s.grader, "open_outcome_snapshot_surface_v1", lambda **_: (base, base_id, {}, {}))
    return later, later_id, base, base_id

def projection(monkeypatch, later, later_id, base, base_id):
    monkeypatch.setattr(s.grader, "open_outcome_snapshot_surface_v1", lambda **_: (base, base_id, {}, {}))
    return s.build_catalog_wide_projection_v1(
        later_source=later, later_source_identity=later_id, later_source_sha256="b"*64,
        base_snapshot=base, base_snapshot_identity=base_id, base_snapshot_sha256="c"*64)

def zero():
    return {"skill_zero_completion_law": s.ZERO_LAW,
            "skill_zero_law_source_sha256": s.ZERO_LAW_SOURCE_SHA256,
            "salary_catalog_settlement_bridge": s.ZERO_BRIDGE,
            "salary_catalog_bridge_source_sha256": s.ZERO_BRIDGE_SOURCE_SHA256}

def source_args(proj, base, base_id, delta, later, later_id):
    base_keys = {(r["source_ordinal"], r["player_id"]) for r in base["rows"]}
    queried = [{k: r[k] for k in ("season", "week", "source_kind", "source_key")}
               for r in proj["outcome_keys"]
               if (r["source_ordinal"], r["player_id"]) not in base_keys]
    projection_id = oid(proj, "projection")
    tables, lease = [{"table": "scores", "etag": "fixed"}], {"lease": "fixed"}
    evidence = {
        "schema_version": s.QUERY_EVIDENCE_SCHEMA,
        "outcome_key_projection_identity": projection_id,
        "outcome_key_projection_sha256": proj["outcome_key_projection_sha256"],
        "queried_keys": queried, "queried_key_count": len(queried),
        "queried_keys_sha256": s.digest(queried),
        "registered_request": {"outcome_key_projection_identity": projection_id,
                               "outcome_key_projection_sha256": proj["outcome_key_projection_sha256"]},
        "query_contract": {"query_count": 1, "use_query_cache": False,
                           "source_snapshot_at": s.BASE_SOURCE_SNAPSHOT_AT},
        "query_job_receipt": {"cache_hit": False, "complete": True},
        "source_snapshot_at": s.BASE_SOURCE_SNAPSHOT_AT,
        "table_receipts_before_query": tables, "table_receipts_after_query": tables,
        "table_receipt_set_sha256": s.digest(tables),
        "historical_outcome_lease_before_query": lease,
        "historical_outcome_lease_after_query": lease,
        "historical_outcome_lease_sha256": s.digest(lease),
        "row_fields": sorted(s._REGISTERED_FIELDS), "row_count": len(delta),
        "rows": delta, "rows_sha256": s.digest(delta), "one_exact_query": True,
        "query_cache_used": False, "table_metadata_stable_during_query": True,
        "historical_outcome_lease_unchanged_during_query": True, "complete": True,
    }
    evidence["query_evidence_sha256"] = s.digest(evidence)
    return dict(projection=proj, projection_identity=oid(proj, "projection"),
                later_source=later, later_source_identity=later_id,
                later_source_sha256="b"*64,
                base_snapshot=base, base_snapshot_identity=base_id,
                base_snapshot_sha256="c"*64, query_evidence=evidence,
                query_evidence_identity=oid(evidence, "query"),
                query_provenance={"source_snapshot_at": evidence["source_snapshot_at"],
                                  "query_contract": evidence["query_contract"],
                                  "query_job_receipt": evidence["query_job_receipt"]})

def test_hard230_coverage_and_actual_novel_opener(monkeypatch):
    later, _, base, _ = setup(monkeypatch)
    later["slates"][0]["catalog"].insert(0, {"id": "hard230", "pos": "WR", "team": "AAA", "salary": 4200})
    later_id = oid(later, "later2"); base["later_source_freeze_identity"] = later_id; base_id = oid(base, "base2")
    proj = projection(monkeypatch, later, later_id, base, base_id)
    delta = [{"season": 2023, "week": 1, "source_kind": "skill", "source_key": "hard230", "realized_score_micro": 230}]
    args = source_args(proj, base, base_id, delta, later, later_id)
    src = s.build_catalog_wide_realized_source_v1(**args, delta_registered_rows=delta)
    tampered = deepcopy(src); tampered["rows"][-1]["realized_score_micro"] += 1
    tampered["rows_sha256"] = s.digest(tampered["rows"])
    tampered["realized_source_sha256"] = s.digest({k: v for k, v in tampered.items()
                                                   if k != "realized_source_sha256"})
    with pytest.raises(s.CatalogWideOutcomeSuccessorError, match="score replay"):
        s.validate_catalog_wide_realized_source_v1(
            tampered, identity=oid(tampered, "tampered-source"), projection=proj,
            projection_identity=args["projection_identity"], base_snapshot=base,
            query_evidence=args["query_evidence"],
            query_evidence_identity=args["query_evidence_identity"])
    snap = s.build_catalog_wide_snapshot_v1(
        projection=proj, projection_identity=args["projection_identity"], base_snapshot=base,
        later_source=later, later_source_identity=later_id, later_source_sha256="b"*64,
        base_snapshot_identity=base_id, base_snapshot_sha256="c"*64,
        realized_source=src, realized_source_identity=oid(src, "source"),
        query_evidence=args["query_evidence"],
        query_evidence_identity=args["query_evidence_identity"])
    snap_id = oid(snap, "snapshot"); monkeypatch.undo()
    _, scores = s.validate_catalog_wide_snapshot_v1(snap, identity=snap_id)
    assert scores[(0, "hard230")] == 230

def test_duplicate_source_collision(monkeypatch):
    later, _, base, _ = setup(monkeypatch)
    later["slates"][0]["catalog"].insert(0, {"id": "p-00", "pos": "WR", "team": "BBB", "salary": 4000})
    later_id = oid(later, "dup"); base["later_source_freeze_identity"] = later_id; base_id = oid(base, "base-dup")
    with pytest.raises(s.CatalogWideOutcomeSuccessorError, match="collision"):
        projection(monkeypatch, later, later_id, base, base_id)

def test_missing_delta_zero_census_and_missing_dst(monkeypatch):
    later, _, base, _ = setup(monkeypatch)
    later["slates"][0]["catalog"].insert(0, {"id": "new", "pos": "WR", "team": "AAA", "salary": 4000})
    later_id = oid(later, "new"); base["later_source_freeze_identity"] = later_id; base_id = oid(base, "base-new")
    proj = projection(monkeypatch, later, later_id, base, base_id); args = source_args(proj, base, base_id, [], later, later_id)
    with pytest.raises(s.CatalogWideOutcomeSuccessorError, match="zero evidence"):
        s.build_catalog_wide_realized_source_v1(**args, delta_registered_rows=[])
    src = s.build_catalog_wide_realized_source_v1(**args, delta_registered_rows=[], zero_evidence=zero())
    assert src["synthesized_skill_key_count"] == 1 and src["synthesized_skill_keys_sha256"] == s.digest(src["synthesized_skill_keys"])
    no_dst = deepcopy(base); no_dst["rows"] = [r for r in no_dst["rows"] if r["player_id"] != "z-00"]
    no_dst_id = oid(no_dst, "base-no-dst")
    proj_no_dst = projection(monkeypatch, later, later_id, no_dst, no_dst_id)
    no_dst_args = source_args(proj_no_dst, no_dst, no_dst_id, [], later, later_id)
    with pytest.raises(s.CatalogWideOutcomeSuccessorError, match="DST"):
        s.build_catalog_wide_realized_source_v1(**no_dst_args, delta_registered_rows=[], zero_evidence=zero())

def test_noncanonical_slate_fails(monkeypatch):
    later, _, base, _ = setup(monkeypatch); later["slates"][0]["slate_id"] = "bad"
    later_id = oid(later, "bad"); base["later_source_freeze_identity"] = later_id; base_id = oid(base, "base-bad")
    with pytest.raises(s.CatalogWideOutcomeSuccessorError):
        projection(monkeypatch, later, later_id, base, base_id)

def test_swapped_base_body_and_omitted_nonzero_query_result_fail(monkeypatch):
    later, _, base, _ = setup(monkeypatch)
    later["slates"][0]["catalog"].insert(0, {"id": "new", "pos": "WR", "team": "AAA", "salary": 4000})
    later_id = oid(later, "later-evidence"); base["later_source_freeze_identity"] = later_id
    base_id = oid(base, "base-evidence")
    proj = projection(monkeypatch, later, later_id, base, base_id)
    nonzero = [{"season": 2023, "week": 1, "source_kind": "skill",
                "source_key": "new", "realized_score_micro": 99}]
    args = source_args(proj, base, base_id, nonzero, later, later_id)
    swapped = deepcopy(base); swapped["rows"][0]["realized_score_micro"] = 999
    with pytest.raises(s.CatalogWideOutcomeSuccessorError, match="SHA-256 differs"):
        s.build_catalog_wide_realized_source_v1(
            **{**args, "base_snapshot": swapped}, delta_registered_rows=nonzero)
    with pytest.raises(s.CatalogWideOutcomeSuccessorError, match="persisted normalized"):
        s.build_catalog_wide_realized_source_v1(**args, delta_registered_rows=[])
    incomplete = deepcopy(args["query_evidence"]); incomplete["complete"] = False
    incomplete["query_evidence_sha256"] = s.digest({k: v for k, v in incomplete.items()
                                                     if k != "query_evidence_sha256"})
    with pytest.raises(s.CatalogWideOutcomeSuccessorError, match="query evidence replay"):
        s.build_catalog_wide_realized_source_v1(
            **{**args, "query_evidence": incomplete,
               "query_evidence_identity": oid(incomplete, "incomplete")},
            delta_registered_rows=nonzero)

def test_projection_omission_rehashed_still_fails_later_source_replay(monkeypatch):
    later, later_id, base, base_id = setup(monkeypatch)
    proj = projection(monkeypatch, later, later_id, base, base_id)
    bad = deepcopy(proj); bad["outcome_keys"].pop()
    bad["outcome_key_count"] -= 1; bad["outcome_keys_sha256"] = s.digest(bad["outcome_keys"])
    bad["outcome_key_projection_sha256"] = s.digest({k: v for k, v in bad.items()
                                                      if k != "outcome_key_projection_sha256"})
    with pytest.raises(s.CatalogWideOutcomeSuccessorError, match="coverage/order"):
        s.validate_catalog_wide_projection_v1(
            bad, identity=oid(bad, "omitted-projection"), later_source=later,
            later_source_identity=later_id, later_source_sha256="b"*64)

def test_self_hashed_conflicting_duplicate_query_source_fails(monkeypatch):
    later, _, base, _ = setup(monkeypatch)
    later["slates"][0]["catalog"].insert(0, {"id": "new", "pos": "WR", "team": "AAA", "salary": 4000})
    later_id = oid(later, "later-conflict"); base["later_source_freeze_identity"] = later_id
    base_id = oid(base, "base-conflict")
    proj = projection(monkeypatch, later, later_id, base, base_id)
    duplicate = [
        {"season": 2023, "week": 1, "source_kind": "skill", "source_key": "new", "realized_score_micro": 10},
        {"season": 2023, "week": 1, "source_kind": "skill", "source_key": "new", "realized_score_micro": 99},
    ]
    args = source_args(proj, base, base_id, duplicate, later, later_id)
    evidence = args["query_evidence"]
    with pytest.raises(s.CatalogWideOutcomeSuccessorError, match="queried-key census"):
        s.validate_catalog_wide_query_evidence_v1(
            evidence, identity=args["query_evidence_identity"], projection=proj,
            projection_identity=args["projection_identity"], base_snapshot=base)
