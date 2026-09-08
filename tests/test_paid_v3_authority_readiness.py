"""Offline contracts for the paid-v3 authority infrastructure path."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import tomllib

import pytest

from nfl_dfs.ops import paid_v3_authority_readiness as readiness


ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = "a" * 40
IMAGE = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs"
    "@sha256:" + "b" * 64
)
RELEASE_ENVIRONMENT = {
    "IMAGE_SOURCE_COMMIT_SHA": SOURCE_COMMIT,
    "IMAGE_URI": IMAGE,
    "IMAGE_DIGEST": "sha256:" + "b" * 64,
}


class _IamConfiguration:
    def __init__(self) -> None:
        self.uniform_bucket_level_access_enabled = False
        self.public_access_prevention = "inherited"


class _SoftDeletePolicy:
    def __init__(self) -> None:
        self.retention_duration_seconds = 0


class _Policy:
    def __init__(self, bindings=None) -> None:
        self.bindings = deepcopy(bindings or [])
        self.version = 3


class _ListedBlob:
    def __init__(self, name: str, generation: str) -> None:
        self.name = name
        self.generation = generation


class _Blob:
    def __init__(
        self,
        bucket: _Bucket,
        name: str,
        generation: int | None = None,
    ) -> None:
        self.bucket = bucket
        self.name = name
        self.generation = generation

    def reload(self) -> None:
        if str(self.generation) not in self.bucket.objects:
            raise FileNotFoundError(self.generation)

    def download_as_bytes(self) -> bytes:
        return self.bucket.objects[str(self.generation)]

    def upload_from_string(self, raw: bytes, **kwargs) -> None:
        self.bucket.upload_calls.append(kwargs)
        if kwargs.get("if_generation_match") != 0 or self.bucket.live:
            raise RuntimeError("conditional create refused")
        self.generation = 101
        self.bucket.live = ["101"]
        self.bucket.versions = ["101"]
        self.bucket.objects["101"] = raw


class _Bucket:
    def __init__(self, *, exists: bool) -> None:
        self.exists = exists
        self.name = readiness.BUCKET
        self.location = "US-CENTRAL1" if exists else None
        self.project_number = readiness.PROJECT_NUMBER if exists else None
        self.metageneration = "1" if exists else None
        self.iam_configuration = _IamConfiguration()
        self.soft_delete_policy = _SoftDeletePolicy()
        if exists:
            self.iam_configuration.uniform_bucket_level_access_enabled = True
            self.iam_configuration.public_access_prevention = "enforced"
            self.soft_delete_policy.retention_duration_seconds = 604800
        self.policy = _Policy()
        self.live: list[str] = []
        self.versions: list[str] = []
        self.soft_deleted: list[str] = []
        self.objects: dict[str, bytes] = {}
        self.list_calls: list[dict[str, object]] = []
        self.upload_calls: list[dict[str, object]] = []
        self.reload_calls = 0
        self.iam_set_calls = 0

    def reload(self) -> None:
        self.reload_calls += 1
        if not self.exists:
            raise FileNotFoundError(self.name)

    def get_iam_policy(self, *, requested_policy_version: int):
        assert requested_policy_version == 3
        return deepcopy(self.policy)

    def set_iam_policy(self, policy: _Policy, *, retry) -> None:
        assert retry is None
        self.iam_set_calls += 1
        self.policy = deepcopy(policy)

    def list_blobs(self, *, prefix: str, **kwargs):
        self.list_calls.append({"prefix": prefix, **kwargs})
        if kwargs.get("soft_deleted"):
            values = self.soft_deleted
        elif kwargs.get("versions"):
            values = self.versions
        else:
            values = self.live
        rows = [_ListedBlob(readiness.PROBE_OBJECT, value) for value in values]
        rows.append(_ListedBlob(readiness.PROBE_OBJECT + ".neighbor", "999"))
        return rows

    def blob(self, name: str, generation: int | None = None) -> _Blob:
        return _Blob(self, name, generation)


class _Client:
    def __init__(self, *, exists: bool = True) -> None:
        self.project = readiness.PROJECT
        self.bucket_value = _Bucket(exists=exists)
        self.create_calls: list[dict[str, object]] = []

    def list_buckets(self, *, project: str, prefix: str):
        assert project == readiness.PROJECT
        assert prefix == readiness.BUCKET
        return [self.bucket_value] if self.bucket_value.exists else []

    def bucket(self, name: str) -> _Bucket:
        assert name == readiness.BUCKET
        return self.bucket_value

    def create_bucket(
        self,
        bucket: _Bucket,
        *,
        project: str,
        location: str,
        retry,
    ):
        assert bucket is self.bucket_value
        self.create_calls.append({
            "project": project,
            "location": location,
            "retry": retry,
        })
        bucket.exists = True
        bucket.location = location.upper()
        bucket.project_number = readiness.PROJECT_NUMBER
        bucket.metageneration = "1"
        return bucket


def _add_required_policy(bucket: _Bucket) -> None:
    by_role: dict[str, set[str]] = {}
    for role, member in readiness.REQUIRED_BINDINGS:
        by_role.setdefault(role, set()).add(member)
    bucket.policy = _Policy([
        {"role": role, "members": members}
        for role, members in by_role.items()
    ])


def _add_probe(bucket: _Bucket, generation: str = "101") -> None:
    bucket.live = [generation]
    bucket.versions = [generation]
    bucket.objects[generation] = readiness.PROBE_BYTES


def _release_identity() -> dict[str, str]:
    return readiness._release_identity_v1(
        SOURCE_COMMIT, IMAGE, RELEASE_ENVIRONMENT
    )


def test_default_plan_has_no_provider_or_mutation_path(capsys) -> None:
    def forbidden():
        pytest.fail("default dry-run must not resolve credentials or Storage")

    assert readiness.main(
        [], storage_client_factory=forbidden, principal_resolver=forbidden
    ) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["mode"] == "dry-run"
    assert plan["cloud_contacted"] is False
    assert plan["cloud_mutation_authorized"] is False
    assert plan["bucket_uri"] == readiness.BUCKET_URI
    assert plan["location"] == "us-central1"
    assert plan["uniform_bucket_level_access"] is True
    assert plan["public_access_prevention"] == "enforced"
    assert plan["soft_delete_retention_seconds"] > 0
    assert "bucket_delete" in plan["forbidden_operations"]
    assert "bucket_recreate" in plan["forbidden_operations"]


def test_apply_requires_separate_exact_confirmation(tmp_path: Path) -> None:
    contacted = False

    def forbidden():
        nonlocal contacted
        contacted = True
        pytest.fail("unconfirmed apply must not contact a provider")

    result = readiness.main(
        [
            "apply",
            "--confirm",
            "wrong",
            "--source-commit",
            SOURCE_COMMIT,
            "--image",
            IMAGE,
            "--receipt",
            str(tmp_path / "receipt.json"),
        ],
        storage_client_factory=forbidden,
        principal_resolver=forbidden,
    )
    assert result == 2
    assert contacted is False
    assert list(tmp_path.iterdir()) == []


def test_apply_requires_running_exact_release_before_intent(tmp_path: Path) -> None:
    def forbidden():
        pytest.fail("release mismatch must precede credentials and Storage")

    changed = dict(RELEASE_ENVIRONMENT)
    changed["IMAGE_DIGEST"] = "sha256:" + "c" * 64
    result = readiness.main(
        [
            "apply",
            "--confirm",
            readiness.CONFIRMATION_PHRASE,
            "--source-commit",
            SOURCE_COMMIT,
            "--image",
            IMAGE,
            "--receipt",
            str(tmp_path / "receipt.json"),
        ],
        storage_client_factory=forbidden,
        principal_resolver=forbidden,
        environment=changed,
    )
    assert result == 2
    assert list(tmp_path.iterdir()) == []


def test_apply_creates_only_fixed_bucket_iam_and_canary() -> None:
    client = _Client(exists=False)
    receipt = readiness.apply_paid_v3_authority_provisioning_v1(
        storage_client=client,
        principal=readiness.DEPLOYER_MEMBER,
        release_identity=_release_identity(),
        observed_at="2026-09-08T12:00:00Z",
    )
    assert client.create_calls == [{
        "project": readiness.PROJECT,
        "location": readiness.REGION,
        "retry": None,
    }]
    bucket = client.bucket_value
    assert bucket.iam_configuration.uniform_bucket_level_access_enabled is True
    assert bucket.iam_configuration.public_access_prevention == "enforced"
    assert bucket.soft_delete_policy.retention_duration_seconds == 604800
    assert bucket.iam_set_calls == 1
    assert bucket.upload_calls == [{
        "content_type": "application/json",
        "if_generation_match": 0,
        "retry": None,
    }]
    assert receipt["required_iam_bindings"] == [
        {"role": role, "member": member}
        for role, member in readiness.REQUIRED_BINDINGS
    ]
    assert receipt["capability_probe"]["list_views"] == [
        "live", "versions", "soft_deleted"
    ]
    assert receipt["capability_probe"]["content_decoded"] is False
    assert receipt["outcome_data_accessed"] is False
    assert receipt["destructive_or_recreate_operation_performed"] is False
    assert receipt["release_identity"] == _release_identity()
    assert receipt["mutations"]["bucket_created_now"] is True
    assert receipt["mutations"]["probe_created_now"] is True
    assert len(bucket.list_calls) == 9


def test_apply_reuses_exact_compliant_state_without_mutation() -> None:
    client = _Client()
    _add_required_policy(client.bucket_value)
    _add_probe(client.bucket_value)
    receipt = readiness.apply_paid_v3_authority_provisioning_v1(
        storage_client=client,
        principal=readiness.DEPLOYER_MEMBER,
        release_identity=_release_identity(),
    )
    assert client.create_calls == []
    assert client.bucket_value.iam_set_calls == 0
    assert client.bucket_value.upload_calls == []
    assert receipt["cloud_mutation_performed"] is False


def test_apply_preserves_unrelated_and_conditional_iam_bindings() -> None:
    client = _Client()
    client.bucket_value.policy = _Policy([
        {
            "role": "roles/storage.legacyBucketReader",
            "members": {"group:operators@example.com"},
        },
        {
            "role": readiness.OBJECT_VIEWER,
            "members": {"serviceAccount:other@example.iam.gserviceaccount.com"},
            "condition": {
                "title": "unrelated",
                "expression": "resource.name.startsWith('other')",
            },
        },
    ])
    _add_probe(client.bucket_value)
    readiness.apply_paid_v3_authority_provisioning_v1(
        storage_client=client,
        principal=readiness.DEPLOYER_MEMBER,
        release_identity=_release_identity(),
    )
    bindings = client.bucket_value.policy.bindings
    assert any(
        binding["role"] == "roles/storage.legacyBucketReader"
        and binding["members"] == {"group:operators@example.com"}
        for binding in bindings
    )
    assert any(
        binding.get("condition", {}).get("title") == "unrelated"
        for binding in bindings
    )


def test_apply_refuses_mismatched_existing_bucket_before_iam_or_probe() -> None:
    client = _Client()
    client.bucket_value.location = "US"
    with pytest.raises(
        readiness.PaidV3AuthorityReadinessError,
        match="metadata differs",
    ):
        readiness.apply_paid_v3_authority_provisioning_v1(
            storage_client=client,
            principal=readiness.DEPLOYER_MEMBER,
            release_identity=_release_identity(),
        )
    assert client.bucket_value.iam_set_calls == 0
    assert client.bucket_value.upload_calls == []


def test_apply_refuses_non_deployer_before_provider_inventory() -> None:
    client = _Client(exists=False)
    with pytest.raises(
        readiness.PaidV3AuthorityReadinessError,
        match="exact reviewed deployer",
    ):
        readiness.apply_paid_v3_authority_provisioning_v1(
            storage_client=client,
            principal=readiness.RUNTIME_MEMBER,
            release_identity=_release_identity(),
        )
    assert client.create_calls == []


def test_deployer_preflight_authenticates_three_views_and_exact_read() -> None:
    client = _Client()
    _add_required_policy(client.bucket_value)
    _add_probe(client.bucket_value)
    receipt = readiness.preflight_paid_v3_authority_v1(
        storage_client=client,
        actor="deployer",
        principal=readiness.DEPLOYER_MEMBER,
        release_identity=_release_identity(),
        observed_at="2026-09-08T12:00:00Z",
    )
    assert receipt["actor"] == "deployer"
    assert receipt["iam_policy_read_by_actor"] is True
    assert receipt["cloud_mutation_performed"] is False
    assert receipt["capability_probe"]["object_identity"] == {
        "uri": readiness.PROBE_URI,
        "generation": "101",
        "sha256": readiness.PROBE_SHA256,
        "bytes": len(readiness.PROBE_BYTES),
    }
    assert client.bucket_value.list_calls == [
        {"prefix": readiness.PROBE_OBJECT},
        {"prefix": readiness.PROBE_OBJECT, "versions": True},
        {"prefix": readiness.PROBE_OBJECT, "soft_deleted": True},
    ] * 2


@pytest.mark.parametrize(
    ("versions", "soft_deleted"),
    [(["100", "101"], []), (["101"], ["100"])],
)
def test_preflight_fails_closed_on_nonunique_or_tombstoned_history(
    versions: list[str],
    soft_deleted: list[str],
) -> None:
    client = _Client()
    _add_required_policy(client.bucket_value)
    _add_probe(client.bucket_value)
    client.bucket_value.versions = versions
    client.bucket_value.soft_deleted = soft_deleted
    with pytest.raises(
        readiness.PaidV3AuthorityReadinessError,
        match="one clean historical generation",
    ):
        readiness.preflight_paid_v3_authority_v1(
            storage_client=client,
            actor="deployer",
            principal=readiness.DEPLOYER_MEMBER,
            release_identity=_release_identity(),
        )


def test_runtime_preflight_binds_exact_deployer_receipt_without_iam_read() -> None:
    deployer_client = _Client()
    _add_required_policy(deployer_client.bucket_value)
    _add_probe(deployer_client.bucket_value)
    deployer = readiness.preflight_paid_v3_authority_v1(
        storage_client=deployer_client,
        actor="deployer",
        principal=readiness.DEPLOYER_MEMBER,
        release_identity=_release_identity(),
    )

    runtime_client = _Client()
    _add_probe(runtime_client.bucket_value)

    def forbidden_iam(*args, **kwargs):
        pytest.fail("runtime Object Viewer must not need getIamPolicy")

    runtime_client.bucket_value.get_iam_policy = forbidden_iam
    runtime = readiness.preflight_paid_v3_authority_v1(
        storage_client=runtime_client,
        actor="runtime",
        principal=readiness.RUNTIME_MEMBER,
        release_identity=_release_identity(),
        paired_deployer_receipt=deployer,
    )
    assert runtime["iam_policy_read_by_actor"] is False
    assert runtime["paired_deployer_receipt_sha256"] == deployer[
        "receipt_sha256"
    ]
    assert runtime["capability_probe"]["object_identity"] == deployer[
        "capability_probe"
    ]["object_identity"]


def test_preflight_rejects_wrong_principal_and_release_environment() -> None:
    client = _Client()
    with pytest.raises(
        readiness.PaidV3AuthorityReadinessError,
        match="authenticated principal differs",
    ):
        readiness.preflight_paid_v3_authority_v1(
            storage_client=client,
            actor="runtime",
            principal=readiness.DEPLOYER_MEMBER,
            release_identity=_release_identity(),
            paired_deployer_receipt={},
        )
    changed = dict(RELEASE_ENVIRONMENT)
    changed["IMAGE_SOURCE_COMMIT_SHA"] = "c" * 40
    with pytest.raises(
        readiness.PaidV3AuthorityReadinessError,
        match="running release environment differs",
    ):
        readiness._release_identity_v1(SOURCE_COMMIT, IMAGE, changed)


def test_storage_api_floor_rejects_pre_soft_delete_client() -> None:
    with pytest.raises(
        readiness.PaidV3AuthorityReadinessError,
        match="below the required 2.16.0",
    ):
        readiness.assert_storage_api_support_v1(installed_version="2.15.0")


def test_dependency_and_exact_paid_release_build_surfaces_pin_floor() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    gcp = project["project"]["optional-dependencies"]["gcp"]
    assert "google-cloud-storage>=2.16.0" in gcp

    direct_build_surfaces = [
        *ROOT.glob("Dockerfile*"),
        *ROOT.glob("cloudbuild*.yaml"),
        *ROOT.glob("scripts/**/Dockerfile"),
        *ROOT.glob("scripts/**/cloudbuild.yaml"),
    ]
    direct_requirement = re.compile(
        r"google-cloud-storage(?P<operator>==|>=)?"
        r"(?P<version>[0-9]+\.[0-9]+\.[0-9]+)?"
    )
    for path in direct_build_surfaces:
        for match in direct_requirement.finditer(path.read_text(encoding="utf-8")):
            assert match.group("operator") in {"==", ">="}, path
            version = tuple(int(part) for part in match.group("version").split("."))
            assert version >= readiness.STORAGE_MINIMUM_VERSION, path

    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    build = (ROOT / "cloudbuild.paid-boundary-v3.yaml").read_text(
        encoding="utf-8"
    )
    assert 'RUN pip install --no-cache-dir ".[gcp,app,graph]"' in dockerfile
    assert "assert_storage_api_support_v1" in build
    assert "tests/test_paid_v3_authority_readiness.py" in build
    assert "--network none" in build
    for lock_name in (
        "requirements.txt",
        "requirements.lock",
        "constraints.txt",
        "Pipfile.lock",
        "poetry.lock",
        "uv.lock",
    ):
        assert not (ROOT / lock_name).exists(), (
            f"new dependency surface {lock_name} needs an explicit Storage floor"
        )


def test_module_contains_no_delete_recreate_or_bucket_update_call() -> None:
    source = (ROOT / "src/nfl_dfs/ops/paid_v3_authority_readiness.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        ".delete(",
        "delete_bucket(",
        "update_bucket(",
        "patch_bucket(",
        "rewrite(",
    )
    assert all(token not in source for token in forbidden)
    assert "if_generation_match=0" in source
    assert source.count("retry=None") == 3
