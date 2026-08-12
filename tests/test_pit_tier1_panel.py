from pathlib import Path


def test_pit_tier1_runner_pins_cache_image_and_predeclared_branches():
    text = (
        Path(__file__).parents[1] / "scripts" / "pit_tier1_panel.sh"
    ).read_text(encoding="utf-8")
    assert "sha256:ad50fe19bde366ca11180b561127b09e2c79c97ec7dbbd5507282e33d2d5eb62" in text
    assert "TABPFN_MARGINAL_TABLE=$CACHE" in text
    assert "20260811-pitclean-e80-k3-a12ab31" in text
    assert "20260811-pitclean-e80-k1-a12ab31" in text
    assert "20260811-pitclean-e80-k3-role12union-a12ab31" in text
    assert "20260811-pitclean-e80-k1-role12union-a12ab31" in text
    assert 'PANEL_N_ENTRIES=80' in text
    assert 'PANEL_N_EPISTEMIC="$n_epi"' in text
    assert "mechanical selection is" in text


def test_control_finisher_promotes_only_selected_k1():
    text = (
        Path(__file__).parents[1]
        / "scripts" / "cloud_finish_pit_tier1_controls.sh"
    ).read_text(encoding="utf-8")
    assert '"$K3" promote 80 2' in text
    assert 'if [ "$SELECTED" = k1 ]' in text
    assert '"$K1" promote 80 2' in text
    assert "cloud_compare_pit_tier1.sh" in text


def test_role_finisher_uses_frozen_comparator_and_promotes_only_treatment():
    text = (
        Path(__file__).parents[1]
        / "scripts" / "cloud_finish_pit_tier1_role.sh"
    ).read_text(encoding="utf-8")
    assert '"$TREATMENT" check 80 2' in text
    assert '"$IMG" "$SOURCE" "$TREATMENT" direct-role a12ab31' in text
    assert 'if [ "$SELECTED" = "$TREATMENT" ]' in text
    assert '"$TREATMENT" promote 80 2' in text
    assert "role_selected=" in text


def test_comparator_packaging_repair_is_locked_to_failed_execution():
    root = Path(__file__).parents[1]
    repair = (root / "scripts/cloud_compare_pit_tier1_repair.sh").read_text(
        encoding="utf-8"
    )
    finish = (
        root / "scripts/cloud_finish_pit_tier1_selection_repair.sh"
    ).read_text(encoding="utf-8")
    assert "compare-pit-tier1-ensemble-x8nkn" in repair
    assert "can't open file '/app/scripts/compare_pit_tier1.py'" in repair
    assert 'report.get("disposition") != "valid"' in repair
    assert 'if [ "$SELECTED" = k1 ]' in finish
    assert '"$K1" promote 80 2' in finish
