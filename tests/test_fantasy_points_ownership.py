import pytest

from nfl_dfs.ops import fantasy_points_ownership as ownership


def test_authenticated_ownership_surface_requires_exact_season_heading():
    result = ownership.validate_surface_state(
        url=ownership.OWNERSHIP_URL,
        headings=["2026 NFL DFS OWNERSHIP PROJECTIONS", "COMPANY"],
        sign_in_visible=False,
        session_uid_present=True,
        expected_season=2026,
    )
    assert result == {
        "version": ownership.SURFACE_VERSION,
        "authenticated": True,
        "season": 2026,
        "source_url": ownership.OWNERSHIP_URL,
    }


def test_ownership_surface_rejects_signed_out_or_wrong_season():
    with pytest.raises(RuntimeError, match="not authenticated"):
        ownership.validate_surface_state(
            url=ownership.OWNERSHIP_URL,
            headings=["2026 NFL DFS OWNERSHIP PROJECTIONS"],
            sign_in_visible=True,
            session_uid_present=False,
            expected_season=2026,
        )
    with pytest.raises(RuntimeError, match="expected season 2026"):
        ownership.validate_surface_state(
            url=ownership.OWNERSHIP_URL,
            headings=["2025 NFL DFS OWNERSHIP PROJECTIONS"],
            sign_in_visible=False,
            session_uid_present=True,
            expected_season=2026,
        )


def test_ownership_surface_requires_positive_api_session_identity():
    with pytest.raises(RuntimeError, match="no authenticated session"):
        ownership.validate_surface_state(
            url=ownership.OWNERSHIP_URL,
            headings=["2026 NFL DFS OWNERSHIP PROJECTIONS"],
            sign_in_visible=False,
            session_uid_present=False,
            expected_season=2026,
        )


def test_ownership_surface_rejects_redirect():
    with pytest.raises(RuntimeError, match="unexpected URL"):
        ownership.validate_surface_state(
            url="https://www.fantasypoints.com/account",
            headings=["2026 NFL DFS OWNERSHIP PROJECTIONS"],
            sign_in_visible=False,
            session_uid_present=True,
            expected_season=2026,
        )


def test_cli_exposes_login_verification_and_safe_inventory():
    parser = ownership._parser()
    login = parser.parse_args(["login", "--terminal-credentials"])
    verify = parser.parse_args(["verify-login"])
    inspect = parser.parse_args(["inspect"])
    assert login.terminal_credentials is True
    assert verify.command == "verify-login"
    assert inspect.command == "inspect"


def _payload(rows, roles=("role_fantasy_pro",), offseason=False, uid="u"):
    return {
        "session": {"uid": uid, "roles": list(roles)},
        "content": {"table": {"title": "2026 NFL DFS Ownership Projections", "isOffseason": offseason, "values": rows}},
    }


def _row(name, operator="DraftKings", pct=12.5, salary=6800, season=2026, week=1, team="HOU", pos="WR"):
    return {"operator": operator, "operatorSalary": salary, "name": name, "fantasyPosition": pos, "season": season,
            "week": week, "team": team, "projectedOwnershipPercentage": pct, "lastUpdated": "2026-09-12T12:26:20.931Z"}


def test_collector_normalizes_unlocked_rows_and_reports_operators():
    rows = [_row(f"P{i}", pct=float(i)) for i in range(60)] + [_row("FD1", operator="FanDuel", pct=3.0)]
    out, receipt = ownership.normalize_ownership_payload(_payload(rows), expected_season=2026, expected_week=1)
    assert len(out) == 61 and receipt["rows"] == 61 and receipt["locked_rows"] == 0
    assert receipt["operators"] == ["DraftKings", "FanDuel"] and receipt["session_roles"] == ["role_fantasy_pro"]
    assert out[0] == {"season": 2026, "week": 1, "operator": "DraftKings", "name": "P0", "position": "WR", "team": "HOU",
                      "salary": 6800, "projected_ownership_pct": 0.0, "last_updated": "2026-09-12T12:26:20.931Z"}


def test_collector_fails_closed_on_anonymous_session_soft_gate_preview():
    preview = [_row(n, operator=None, pct=None, salary=None) for n in ("Nico Collins", "Rico Dowdle", "X")]
    with pytest.raises(RuntimeError, match="anonymous"):
        ownership.normalize_ownership_payload(_payload(preview, roles=("role_anonymous",)), expected_season=2026, expected_week=1)


def test_collector_fails_closed_on_locked_values_offseason_and_wrong_week():
    locked = [_row(f"P{i}", pct=None) for i in range(60)]
    with pytest.raises(RuntimeError, match="locked or truncated"):
        ownership.normalize_ownership_payload(_payload(locked), expected_season=2026, expected_week=1)
    with pytest.raises(RuntimeError, match="offseason"):
        ownership.normalize_ownership_payload(_payload([_row("A")], offseason=True), expected_season=2026, expected_week=1)
    with pytest.raises(RuntimeError, match="expected 2026/2"):
        ownership.normalize_ownership_payload(_payload([_row(f"P{i}") for i in range(60)]), expected_season=2026, expected_week=2)
    with pytest.raises(RuntimeError, match="no session"):
        ownership.normalize_ownership_payload(_payload([_row("A")], uid=""), expected_season=2026, expected_week=1)


def test_collector_redaction_drops_session_identity_but_keeps_roles():
    red = ownership._redacted(_payload([_row("A")], roles=("role_fantasy_pro",), uid="secret"))
    assert red["session"] == {"uid_present": True, "roles": ["role_fantasy_pro"]} and "secret" not in str(red)


def test_archive_addresses_each_object_by_its_own_hash(tmp_path, monkeypatch):
    """A re-capture with an identical CSV must not collide with the previous capture's raw JSON or manifest."""
    import hashlib
    from google.api_core.exceptions import PreconditionFailed
    from google.cloud import storage
    from nfl_dfs.ops import fantasy_points_ownership as own

    store: dict[str, bytes] = {}

    class Blob:
        def __init__(self, name): self.name = name
        def upload_from_filename(self, path, content_type=None, if_generation_match=None):
            if self.name in store:
                raise PreconditionFailed("exists")
            store[self.name] = open(path, "rb").read()
        def download_as_bytes(self): return store[self.name]

    class Client:
        def bucket(self, name): return type("B", (), {"blob": lambda _self, n: Blob(n)})()

    monkeypatch.setattr(storage, "Client", Client)
    for i, text in enumerate(("raw-saturday", "raw-t70")):              # the same CSV, two different raw payloads
        raw = tmp_path / f"cap{i}" / "ownership-raw.json"; raw.parent.mkdir(); raw.write_text(text)
        own._archive_create_once(raw, hashlib.sha256(raw.read_bytes()).hexdigest(), 2026, 4)
    assert len(store) == 2 and all(f"sha256={hashlib.sha256(v).hexdigest()}/" in k for k, v in store.items())


def test_the_week_5_heading_form_is_accepted_and_a_named_week_must_match():
    """2026-10-09: FP's heading became "2026 WEEK 5 NFL DFS OWNERSHIP PROJECTIONS" and every capture failed closed. Both forms
    pass; a named week must be the requested one when the caller knows it; the season rule is unchanged."""
    ok = dict(url=ownership.OWNERSHIP_URL, sign_in_visible=False, session_uid_present=True, expected_season=2026)
    heads = ["2026 WEEK 5 NFL DFS OWNERSHIP PROJECTIONS", "CONTENT AND MEDIA", "COMPANY"]
    assert ownership.validate_surface_state(headings=heads, **ok)["season"] == 2026
    assert ownership.validate_surface_state(headings=heads, expected_week=5, **ok)["season"] == 2026
    assert ownership.validate_surface_state(headings=["2026 Week 12 NFL DFS Ownership Projections"], expected_week=12, **ok)
    with pytest.raises(RuntimeError, match="names week \\[4\\], expected week 5"):
        ownership.validate_surface_state(headings=["2026 WEEK 4 NFL DFS OWNERSHIP PROJECTIONS"], expected_week=5, **ok)
    with pytest.raises(RuntimeError, match="expected season 2026"):
        ownership.validate_surface_state(headings=["2025 WEEK 5 NFL DFS OWNERSHIP PROJECTIONS"], expected_week=5, **ok)
