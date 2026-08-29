from __future__ import annotations

from hashlib import sha256
import importlib.util
import json
from pathlib import Path

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_aggregate_v1 as publisher,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_task_manifest_v1 as task_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_corpus_r6_current_bank_terminal_root_timeout_recovery_v1.py"


def _module():
    spec = importlib.util.spec_from_file_location("terminal_recovery_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _identity(uri: str, raw: bytes) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def test_timeout_recovery_all_wall_checkpoints_agree() -> None:
    recovery = _module()
    assert publisher.MAXIMUM_PUBLISHER_WALL_SECONDS == 5_400
    assert recovery.RECOVERY_CHILD_WALL_SECONDS == 5_400
    assert task_manifest.MAXIMUM_DISPATCHER_WALL_SECONDS == 7_260
    assert recovery.PROVIDER_TASK_WALL_SECONDS == 7_260
    assert recovery.ORIGINAL_CHILD_WALL_SECONDS == 1_800
    terminal = next(
        row for row in task_manifest._LAYER_SPECS
        if row.layer_id == "terminal-root"
    )
    # The original immutable V7 manifest remains a 1,800-second authority;
    # only the exact amendment grants the replacement carrier 5,400 seconds.
    assert terminal.maximum_wall_seconds == 1_800
    assert recovery.RECOVERY_CHILD_WALL_SECONDS < recovery.PROVIDER_TASK_WALL_SECONDS


def test_timeout_change_does_not_change_publisher_science_or_memory_constants() -> None:
    assert publisher.MAXIMUM_SINGLE_SCIENTIFIC_BODY_BYTES == 768_000_000
    assert publisher.MAXIMUM_COMPACT_EVALUATION_STATE_BYTES == 64_000_000
    assert publisher.MAXIMUM_PUBLISHER_PEAK_RSS_BYTES == 24 * 1024**3
    assert publisher.MAXIMUM_PUBLISHER_ADDRESS_SPACE_BYTES == 24 * 1024**3
    assert publisher.REQUIRED_CLOUD_RUN_CONTAINER_MEMORY_BYTES == 32 * 1024**3
    assert publisher.MAXIMUM_PUBLISHER_ENVELOPE_BYTES == 4_000_000
    assert publisher.PUBLISHER_MODES == (
        "publish-nomination",
        "publish-aggregate-finalists",
        "publish-terminal-root",
    )
    assert publisher.MODE_WRITE_ROLES["publish-terminal-root"] == ("root",)


def test_frozen_transport_sources_and_normalized_publisher_source_are_exact() -> None:
    aggregate_path = (
        ROOT / "src/nfl_dfs/research/"
        "corpus_r6_current_bank_crossed_screen_aggregate_v1.py"
    )
    aggregate_raw = aggregate_path.read_bytes()
    normalized = aggregate_raw.replace(
        b"MAXIMUM_PUBLISHER_WALL_SECONDS: Final = 5_400",
        b"MAXIMUM_PUBLISHER_WALL_SECONDS: Final = 1_800",
    )
    assert normalized != aggregate_raw
    assert sha256(normalized).hexdigest() == (
        "075c0b29c17b7d8376a775f80ce7863fd1f060ed2f9522eb10561a2d6f93ff35"
    )
    assert sha256((
        ROOT / "src/nfl_dfs/research/"
        "corpus_r6_current_bank_crossed_screen_task_manifest_v1.py"
    ).read_bytes()).hexdigest() == (
        "c7df1085381496482deb7c732e453964e8018702b3fc5f3ef11d4b8189ef2b1b"
    )
    assert sha256((
        ROOT / "scripts/"
        "run_corpus_r6_current_bank_crossed_screen_task_dispatcher_v1.py"
    ).read_bytes()).hexdigest() == (
        "03900f9601d3f9b1bec268bdcfe6e03b8d8dfcf09ba836287b70e236ab589e08"
    )


def test_preclient_environment_is_exact_and_redirect_free() -> None:
    recovery = _module()
    amendment_raw = b"{}"
    amendment_identity = _identity(
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-current-bank-crossed-screens/20260828-r6-current-bank-"
        "crossed-screen-v7/authorities/terminal-root-timeout-recovery-v1/"
        "amendment.json",
        amendment_raw,
    )
    env = {
        recovery.ENABLE_ENV: "1",
        recovery.AMENDMENT_IDENTITY_ENV: json.dumps(
            amendment_identity, sort_keys=True, separators=(",", ":")
        ),
        recovery.ACTUAL_IMAGE_DIGEST_ENV: "sha256:" + "a" * 64,
        recovery.ACTUAL_CODE_SHA_ENV: "b" * 40,
        "R6_RUNTIME_IMAGE_DIGEST": "sha256:" + "c" * 64,
        "CODE_SHA": "d" * 40,
        "GOOGLE_CLOUD_PROJECT": recovery.FIXED_PROJECT,
        "CLOUD_RUN_JOB": recovery.FIXED_JOB,
        "CLOUD_RUN_EXECUTION": "one-execution",
        "CLOUD_RUN_TASK_INDEX": "0",
        "CLOUD_RUN_TASK_COUNT": "1",
        "CLOUD_RUN_TASK_ATTEMPT": "0",
    }
    observed = [
        "/usr/local/bin/python3.11",
        "-I",
        "/app/scripts/run_corpus_r6_current_bank_terminal_root_timeout_recovery_v1.py",
    ]
    retained = recovery.validate_preclient_environment_v1(
        env, observed_command=observed
    )
    assert retained["amendment_identity"] == amendment_identity
    assert retained["actual_image_digest"] == "sha256:" + "a" * 64
    assert retained["logical_image_digest"] == "sha256:" + "c" * 64


def test_recovery_source_preserves_exact_child_and_process_budget_validation() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "task_manifest.render_child_command_v1" in source
    assert "dispatcher._run_child_bounded_v1" in source
    assert "timeout_seconds=RECOVERY_CHILD_WALL_SECONDS" in source
    assert "task_manifest._exact_task_process_budget_bindings_v1" in source
    assert "read_allowlist_sha256" in source
    assert "write_allowlist_sha256" in source
    assert "transport.prove_exact_identity(publications[0])" in source
    assert '"realized_outcomes_read": False' in source
