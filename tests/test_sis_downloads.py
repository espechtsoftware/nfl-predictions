import pytest

from nfl_dfs.ops import sis_downloads as sis


def test_default_profile_is_outside_repository(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert sis.default_profile_dir() == tmp_path / "nfl-dfs" / "sis-playwright"


def test_authenticated_url_requires_protected_sis_host():
    assert sis._authenticated_url("https://pro.sisdatahub.com/NFL/Leaders/Players")
    assert not sis._authenticated_url(
        "https://auth.sportsinfosolutions.com/Account/Login"
    )
    assert not sis._authenticated_url("https://store.sportsinfosolutions.com/Purchase")


def test_cli_help_exits_cleanly():
    with pytest.raises(SystemExit) as exc_info:
        sis.main(["--help"])
    assert exc_info.value.code == 0
