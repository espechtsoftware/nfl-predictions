from pathlib import Path


ROOT = Path(__file__).parents[1]
UNIT = ROOT / "deploy/systemd/nfl-host-dk-ingest.service"


def test_host_dk_service_uses_tracked_loop_and_week3_state():
    text = UNIT.read_text()
    assert "ExecStart=%h/projects/nfl-predictions/scripts/host_ingest_dk_loop.sh" in text
    assert "Environment=OUT=%h/week3-sunday" in text
    assert "Environment=GCP_PROJECT=nfl-predictions-503414" in text
    assert "Environment=INTERVAL_SECONDS=3600" in text


def test_host_dk_service_is_restartable_but_not_a_cloud_run_mutation():
    text = UNIT.read_text()
    assert "Restart=on-failure" in text
    assert "RestartSec=60s" in text
    assert "gcloud run" not in text
