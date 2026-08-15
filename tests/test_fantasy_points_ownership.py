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
