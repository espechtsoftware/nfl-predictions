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
