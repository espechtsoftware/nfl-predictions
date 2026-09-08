"""Adversarial tests for the local Week-1 provider-response rehearsal."""

from __future__ import annotations

import ast
import copy
import csv
import inspect
import io
import json
import os
import stat
import traceback
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from nfl_dfs.ingest import week1_a5_capture_contracts as capture
from nfl_dfs.ingest import week1_a5_dk_acquisition as acquisition
from nfl_dfs.ingest import week1_a5_dk_acquisition_pins as live_pins
from nfl_dfs.ingest import week1_a5_governed_capture_v3 as capture_v3
from nfl_dfs.ingest import week1_a5_p0b_provider_reality as subject

COOKIE_NAME_CANARY = "COOKIE_NAME_CANARY"
COOKIE_VALUE_CANARY = "COOKIE_VALUE_CANARY"
QUERY_VALUE_CANARY = "QUERY_VALUE_CANARY"
PATH_VALUE_CANARY = "PATH_VALUE_CANARY"
HEADER_VALUE_CANARY = "HEADER_VALUE_CANARY"
ROW_VALUE_CANARY = "ROW_VALUE_CANARY"
LOCATOR = (
    "https://www.draftkings.com/lineup/getlineups/"
    f"{PATH_VALUE_CANARY}?ticket={QUERY_VALUE_CANARY}"
)
EFFECTIVE = (
    "https://www.draftkings.com/lineup/export/"
    f"{PATH_VALUE_CANARY}?signature={QUERY_VALUE_CANARY}"
)


def _intent(role: str = "milly-5") -> dict[str, object]:
    return subject._seal(
        {
            "schema_version": subject.INTENT_SCHEMA,
            "created_at_utc": "2026-09-08T20:00:00Z",
            "rehearsal_module_sha256": subject._module_sha256(),
            "collector_module_sha256": acquisition._module_sha256(),
            "contest_role": role,
            "http_method": "GET",
            "session_profile": acquisition.COLLECTOR_SESSION_PROFILE,
            "fixed_locator_families": subject._family_rows(),
            "maximum_redirects": acquisition.MAX_REDIRECTS,
            "capture_v3_schema": capture_v3.ACCEPTANCE_PROVIDER_CAPTURE_SCHEMA,
            "provider_contact_authorized": True,
            "cloud_contact_authorized": False,
            "cloud_mutation_authorized": False,
            "gcs_publication_authorized": False,
            "pin_change_authorized": False,
            "contest_entry_authorized": False,
            "outcome_or_standings_access_authorized": False,
            "legacy_v2_live_fallback_authorized": False,
        },
        field="intent_sha256",
    )


def _storage_state() -> bytes:
    return json.dumps(
        {
            "cookies": [
                {
                    "name": COOKIE_NAME_CANARY,
                    "value": COOKIE_VALUE_CANARY,
                    "domain": ".draftkings.com",
                    "path": "/",
                    "secure": True,
                    "httpOnly": True,
                }
            ],
            "origins": [],
        }
    ).encode()


def _active_entry_csv(role: str = "milly-5") -> bytes:
    pin = capture.A5_ROLE_TABLE[role]
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        ["Entry ID", "Contest Name", "Contest ID", "Entry Fee"]
        + list(capture.CLASSIC_SLOTS)
    )
    for ordinal in range(pin.planned_entries):
        first = ordinal * 20 + 1
        writer.writerow(
            [
                str(int(pin.contest_id) * 1_000 + ordinal + 1),
                pin.name,
                pin.contest_id,
                f"${pin.entry_fee_micro // 1_000_000}",
            ]
            + [
                f"{ROW_VALUE_CANARY}-{value} ({value})"
                for value in range(first, first + 9)
            ]
        )
    return output.getvalue().encode()


@dataclass
class FakeResponse:
    url: str
    status_code: int
    headers: dict[str, str]
    content: bytes
    history: tuple[object, ...] = ()
    body_iterated: bool = False

    def iter_content(self, *, chunk_size: int, decode_unicode: bool) -> Iterator[bytes]:
        assert decode_unicode is False
        self.body_iterated = True
        yield from (
            self.content[offset : offset + chunk_size]
            for offset in range(0, len(self.content), chunk_size)
        )


class FakeCookieJar:
    def __init__(self) -> None:
        self.values: list[tuple[str, str, dict[str, object]]] = []

    def set(self, name: str, value: str, **kwargs: object) -> None:
        self.values.append((name, value, kwargs))


class FakeSession:
    def __init__(self, responses: list[FakeResponse | BaseException]) -> None:
        self.responses = list(responses)
        self.cookies = FakeCookieJar()
        self.calls: list[tuple[str, dict[str, object], bool]] = []
        self.returned: list[FakeResponse] = []
        self.trust_env = True
        self.closed = False

    def get(self, locator: str, **kwargs: object) -> FakeResponse:
        self.calls.append((locator, kwargs, self.trust_env))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        self.returned.append(response)
        return response

    def close(self) -> None:
        self.closed = True


class SessionFactory:
    def __init__(self, responses: list[FakeResponse | BaseException]) -> None:
        self.responses = responses
        self.sessions: list[FakeSession] = []

    def __call__(self) -> FakeSession:
        session = FakeSession(copy.deepcopy(self.responses))
        self.sessions.append(session)
        return session


def _response(
    *,
    url: str = LOCATOR,
    status: int = 200,
    body: bytes | None = None,
    content_type: str = "text/csv; charset=utf-8",
    disposition: str | None = None,
    **headers: str,
) -> FakeResponse:
    raw = body if body is not None else _active_entry_csv()
    retained_headers = {
        "Content-Type": content_type,
        "Content-Disposition": (
            disposition or f'attachment; filename="{HEADER_VALUE_CANARY}.csv"'
        ),
        "Content-Length": str(len(raw)),
        **headers,
    }
    if disposition == "ABSENT":
        retained_headers.pop("Content-Disposition")
    return FakeResponse(url, status, retained_headers, raw)


def _success_factory() -> SessionFactory:
    return SessionFactory(
        [
            FakeResponse(
                LOCATOR,
                302,
                {"Location": EFFECTIVE},
                b"",
            ),
            _response(url=EFFECTIVE),
        ]
    )


def _run(factory: SessionFactory | None = None) -> dict[str, dict[str, object]]:
    return subject._rehearse_acceptance_download_v1(
        intent=_intent(),
        storage_state=_storage_state(),
        acceptance_locator=LOCATOR,
        session_factory=factory or _success_factory(),
    )


def _private_file(path: Path, raw: bytes) -> None:
    path.write_bytes(raw)
    path.chmod(0o600)


def _cli_args(tmp_path: Path) -> tuple[list[str], Path, Path]:
    intent_path = tmp_path / "intent.json"
    _private_file(intent_path, subject._canonical_bytes(_intent()))
    state_path = tmp_path / "state.json"
    _private_file(state_path, _storage_state())
    locator_path = tmp_path / "locator"
    _private_file(locator_path, (LOCATOR + "\n").encode())
    evidence = tmp_path / "evidence"
    receipt = tmp_path / "receipt.json"
    return (
        [
            "audit",
            "--confirm",
            subject.CONFIRMATION_PHRASE,
            "--intent",
            str(intent_path),
            "--storage-state-file",
            str(state_path),
            "--acceptance-locator-file",
            str(locator_path),
            "--evidence-directory",
            str(evidence),
            "--receipt",
            str(receipt),
        ],
        evidence,
        receipt,
    )


def test_default_plan_is_inert_and_every_live_pin_is_absent(
    capsysbinary: pytest.CaptureFixture[bytes],
) -> None:
    assert subject.main([]) == 0
    plan = json.loads(capsysbinary.readouterr().out)
    assert plan["mode"] == "no-contact-plan"
    assert plan["provider_contacted"] is False
    assert plan["cloud_contacted"] is False
    assert plan["fixed_locator_families"] == subject._family_rows()
    assert capture.PINNED_ACCEPTANCE_DOWNLOAD_LOCATOR is None
    assert {
        value for name, value in vars(live_pins).items() if name.startswith("PINNED_")
    } == {None}


def test_offline_intent_command_is_canonical_and_network_free(
    capsysbinary: pytest.CaptureFixture[bytes],
) -> None:
    assert (
        subject.main(
            [
                "intent",
                "--created-at-utc",
                "2026-09-08T20:00:00Z",
                "--contest-role",
                "milly-5",
            ]
        )
        == 0
    )
    raw = capsysbinary.readouterr().out
    value = json.loads(raw)
    assert raw == subject._canonical_bytes(value)
    assert subject.validate_intent_v1(value) == value
    assert value["provider_contact_authorized"] is True
    assert value["cloud_contact_authorized"] is False


def test_success_retains_only_redacted_transport_and_structural_facts() -> None:
    factory = _success_factory()
    bundle = _run(factory)
    evidence = bundle["evidence"]
    receipt = bundle["receipt"]

    assert evidence["schema_version"] == subject.EVIDENCE_SCHEMA
    assert receipt["schema_version"] == subject.RECEIPT_SCHEMA
    assert receipt["evidence_sha256"] == evidence["evidence_sha256"]
    assert receipt["release_gate"] == (
        "HOLD_FOR_INDEPENDENT_REVIEW_AND_PIN_ONLY_SUCCESSOR"
    )
    transport = evidence["transport"]
    assert transport["terminal_status"] == 200
    assert transport["redirect_count"] == 1
    assert transport["http_response_count"] == 2
    assert transport["media_type"] == "text/csv"
    assert transport["content_disposition"] == {
        "disposition": "attachment",
        "filename_present": True,
        "filename_extension": ".csv",
        "raw_header_retained": False,
    }
    assert evidence["response_shape"]["observed_role_entry_count"] == 57
    assert "contest_id" not in evidence["response_shape"]
    assert evidence["response_shape"]["exact_header"] == [
        "Entry ID",
        "Contest Name",
        "Contest ID",
        "Entry Fee",
        *capture.CLASSIC_SLOTS,
    ]
    serialized = subject._canonical_bytes(bundle).decode()
    pin = capture.A5_ROLE_TABLE["milly-5"]
    assert pin.contest_id not in serialized
    assert pin.name not in serialized
    assert str(int(pin.contest_id) * 1_000 + 1) not in serialized
    for canary in (
        COOKIE_NAME_CANARY,
        COOKIE_VALUE_CANARY,
        QUERY_VALUE_CANARY,
        PATH_VALUE_CANARY,
        HEADER_VALUE_CANARY,
        ROW_VALUE_CANARY,
    ):
        assert canary not in serialized
    assert factory.sessions[0].cookies.values[0][0:2] == (
        COOKIE_NAME_CANARY,
        COOKIE_VALUE_CANARY,
    )
    for _, kwargs, trust_env in factory.sessions[0].calls:
        assert trust_env is False
        assert kwargs["allow_redirects"] is False
        assert kwargs["stream"] is True
        assert kwargs["verify"] is True
        assert kwargs["headers"]["Accept-Encoding"] == "identity"
    assert factory.sessions[0].closed is True


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("http_method", "POST", "GET only"),
        ("fixed_locator_families", [], "families differ"),
        ("provider_contact_authorized", False, "forbidden operation"),
        ("cloud_contact_authorized", True, "forbidden operation"),
        ("outcome_or_standings_access_authorized", True, "forbidden operation"),
        ("legacy_v2_live_fallback_authorized", True, "forbidden operation"),
    ],
)
def test_intent_is_exact_and_grants_only_one_provider_rehearsal(
    field: str, replacement: object, message: str
) -> None:
    intent = _intent()
    intent[field] = replacement
    intent["intent_sha256"] = subject._canonical_sha(
        {key: value for key, value in intent.items() if key != "intent_sha256"}
    )
    with pytest.raises(subject.Week1A5P0BProviderRealityError, match=message):
        subject.validate_intent_v1(intent)


def test_tampered_intent_fails_before_session_construction() -> None:
    intent = _intent()
    intent["contest_role"] = "large-20max-3"
    factory = SessionFactory([_response()])
    with pytest.raises(subject.Week1A5P0BProviderRealityError, match="hash differs"):
        subject._rehearse_acceptance_download_v1(
            intent=intent,
            storage_state=_storage_state(),
            acceptance_locator=LOCATOR,
            session_factory=factory,
        )
    assert factory.sessions == []


def test_noncanonical_intent_timestamp_fails_before_session_construction() -> None:
    intent = _intent()
    intent["created_at_utc"] = "2026-09-08T15:00:00-05:00"
    intent["intent_sha256"] = subject._canonical_sha(
        {key: value for key, value in intent.items() if key != "intent_sha256"}
    )
    factory = SessionFactory([_response()])
    with pytest.raises(
        subject.Week1A5P0BProviderRealityError, match="not canonical UTC"
    ):
        subject._rehearse_acceptance_download_v1(
            intent=intent,
            storage_state=_storage_state(),
            acceptance_locator=LOCATOR,
            session_factory=factory,
        )
    assert factory.sessions == []


def test_transport_is_get_only_before_session_construction() -> None:
    factory = SessionFactory([_response()])
    transport = subject._LocalAcceptanceTransport(
        subject._playwright_cookies(_storage_state()), factory
    )
    with pytest.raises(subject.Week1A5P0BProviderRealityError, match="GET only"):
        transport.perform(method="POST", locator=LOCATOR)
    assert factory.sessions == []


@pytest.mark.parametrize(
    ("target", "message"),
    [
        ("https://evil.example/steal", "outside the fixed"),
        (
            "https://www.draftkings.com/lineup/login?next=export",
            "auth, action, or outcome surface",
        ),
        (
            "https://www.draftkings.com/lineup/Login.aspx?next=export",
            "auth, action, or outcome surface",
        ),
        (
            "https://www.draftkings.com/lineup/log-in?next=export",
            "auth, action, or outcome surface",
        ),
        (
            "https://www.draftkings.com/mycontests/standings?contest=secret",
            "auth, action, or outcome surface",
        ),
        (
            "https://www.draftkings.com/mycontests/ContestResults.csv",
            "auth, action, or outcome surface",
        ),
        (
            "https://www.draftkings.com/lineup/upload?contest=secret",
            "auth, action, or outcome surface",
        ),
        (
            "https://www.draftkings.com/lineup/entry?contest=secret",
            "auth, action, or outcome surface",
        ),
        (
            "https://www.draftkings.com/lineup/enter-contest?contest=secret",
            "auth, action, or outcome surface",
        ),
        (
            "https://www.draftkings.com/lineup/edit?contest=secret",
            "auth, action, or outcome surface",
        ),
        (
            "https://www.draftkings.com/lineup/create?contest=secret",
            "auth, action, or outcome surface",
        ),
        (
            "https://www.draftkings.com/lineup/join?contest=secret",
            "auth, action, or outcome surface",
        ),
        (
            "https://www.draftkings.com/lineup/../account",
            "ambiguous path encoding",
        ),
        (
            "https://www.draftkings.com/lineup/%2e%2e/login",
            "ambiguous path encoding",
        ),
        (
            "https://www.draftkings.com/lineup/%6cogin",
            "ambiguous path encoding",
        ),
    ],
)
def test_redirect_target_is_rejected_before_second_contact(
    target: str, message: str
) -> None:
    factory = SessionFactory([FakeResponse(LOCATOR, 302, {"Location": target}, b"")])
    with pytest.raises(subject.Week1A5P0BProviderRealityError, match=message):
        _run(factory)
    assert len(factory.sessions) == 1
    assert len(factory.sessions[0].calls) == 1


def test_redirect_loop_is_rejected_before_recontact() -> None:
    factory = SessionFactory([FakeResponse(LOCATOR, 302, {"Location": LOCATOR}, b"")])
    with pytest.raises(subject.Week1A5P0BProviderRealityError, match="loop"):
        _run(factory)
    assert len(factory.sessions[0].calls) == 1


def test_adapter_history_is_refused() -> None:
    response = _response()
    response.history = (object(),)
    factory = SessionFactory([response])
    with pytest.raises(
        subject.Week1A5P0BProviderRealityError, match="adapter followed"
    ):
        _run(factory)
    assert len(factory.sessions[0].calls) == 1


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (_response(status=204), "exact HTTP 200"),
        (_response(status=401), "exact HTTP 200"),
        (_response(status=403), "exact HTTP 200"),
        (_response(status=429), "exact HTTP 200"),
        (_response(status=500), "exact HTTP 200"),
        (_response(content_type="text/html"), "media type"),
        (_response(content_type="text/csv; charset=latin-1"), "media type"),
        (_response(disposition="inline; filename=entries.csv"), "not an attachment"),
        (_response(disposition="attachment"), "parameters differ"),
        (_response(disposition="attachment; filename=entries.exe"), "name a CSV"),
        (_response(disposition="ABSENT"), "content disposition"),
        (_response(Content_Encoding="gzip"), "content encoding"),
        (
            _response(Content_Length=str(subject.MAX_RESPONSE_BYTES + 1)),
            "Content-Length",
        ),
        (_response(body=b""), "body is empty"),
        (
            _response(body=b"x" * (subject.MAX_RESPONSE_BYTES + 1)),
            "Content-Length",
        ),
    ],
)
def test_status_content_headers_and_body_fail_closed(
    response: FakeResponse, message: str
) -> None:
    # Keyword spelling is normalized here so parametrized dict expansion can
    # model actual HTTP header names without teaching the production code.
    response.headers = {
        key.replace("_", "-"): value for key, value in response.headers.items()
    }
    factory = SessionFactory([response])
    with pytest.raises(subject.Week1A5P0BProviderRealityError, match=message):
        _run(factory)


def test_login_html_is_rejected_from_headers_before_body_read() -> None:
    response = _response(content_type="text/html; charset=utf-8")
    factory = SessionFactory([response])
    with pytest.raises(subject.Week1A5P0BProviderRealityError, match="media type"):
        _run(factory)
    assert factory.sessions[0].returned[0].body_iterated is False


def test_body_size_cap_does_not_depend_on_content_length() -> None:
    response = _response(body=b"x" * (subject.MAX_RESPONSE_BYTES + 1))
    response.headers.pop("Content-Length")
    factory = SessionFactory([response])
    with pytest.raises(
        subject.Week1A5P0BProviderRealityError, match="body is oversized"
    ):
        _run(factory)


def test_content_length_must_match_body_bytes() -> None:
    response = _response(Content_Length="1")
    response.headers = {
        key.replace("_", "-"): value for key, value in response.headers.items()
    }
    factory = SessionFactory([response])
    with pytest.raises(
        subject.Week1A5P0BProviderRealityError, match="differs from body bytes"
    ):
        _run(factory)


@pytest.mark.parametrize("defect", ["header", "extra", "ragged", "role", "count"])
def test_exact_outcome_free_dkentries_shape_is_required(defect: str) -> None:
    rows = list(csv.reader(io.StringIO(_active_entry_csv().decode())))
    if defect == "header":
        rows[0][0] = "Rank"
    elif defect == "extra":
        rows[0].append("Fantasy Points")
        for row in rows[1:]:
            row.append("0")
    elif defect == "ragged":
        rows[1].pop()
    elif defect == "role":
        rows[1][1] = "Another Contest"
    else:
        rows.pop()
    output = io.StringIO(newline="")
    csv.writer(output).writerows(rows)
    factory = SessionFactory([_response(body=output.getvalue().encode())])
    with pytest.raises((subject.Week1A5P0BProviderRealityError, ValueError)):
        _run(factory)


@pytest.mark.parametrize(
    "state",
    [
        b"not-json",
        json.dumps({"cookies": []}).encode(),
        json.dumps(
            {"cookies": [{"name": "x", "value": "y", "domain": "evil.example"}]}
        ).encode(),
    ],
)
def test_invalid_storage_state_fails_before_session(state: bytes) -> None:
    factory = SessionFactory([_response()])
    with pytest.raises(subject.Week1A5P0BProviderRealityError):
        subject._rehearse_acceptance_download_v1(
            intent=_intent(),
            storage_state=state,
            acceptance_locator=LOCATOR,
            session_factory=factory,
        )
    assert factory.sessions == []


def test_network_exception_detail_is_never_exposed() -> None:
    factory = SessionFactory(
        [RuntimeError(f"failed signed URL {QUERY_VALUE_CANARY} {COOKIE_VALUE_CANARY}")]
    )
    with pytest.raises(subject.Week1A5P0BProviderRealityError) as raised:
        _run(factory)
    assert "exception detail was not retained" in str(raised.value)
    assert QUERY_VALUE_CANARY not in str(raised.value)
    assert COOKIE_VALUE_CANARY not in str(raised.value)
    rendered = "".join(
        traceback.format_exception(type(raised.value), raised.value, raised.value.__traceback__)
    )
    assert QUERY_VALUE_CANARY not in rendered
    assert COOKIE_VALUE_CANARY not in rendered


def test_wrong_confirmation_precedes_every_file_and_network_read(
    tmp_path: Path,
) -> None:
    factory = SessionFactory([_response()])
    result = subject.main(
        [
            "audit",
            "--confirm",
            "wrong",
            "--intent",
            str(tmp_path / "absent-intent"),
            "--storage-state-file",
            str(tmp_path / "absent-state"),
            "--acceptance-locator-file",
            str(tmp_path / "absent-locator"),
            "--evidence-directory",
            str(tmp_path / "evidence"),
            "--receipt",
            str(tmp_path / "receipt"),
        ],
        session_factory=factory,
    )
    assert result == 2
    assert factory.sessions == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(("which", "mode"), [("locator", 0o644), ("state", 0o400)])
def test_private_inputs_require_exact_mode_0600_before_network(
    tmp_path: Path, which: str, mode: int
) -> None:
    args, _, _ = _cli_args(tmp_path)
    path = tmp_path / ("locator" if which == "locator" else "state.json")
    path.chmod(mode)
    factory = SessionFactory([_response()])
    assert subject.main(args, session_factory=factory) == 2
    assert factory.sessions == []


@pytest.mark.parametrize("which", ["locator", "state"])
def test_private_inputs_reject_symlinks_before_network(
    tmp_path: Path, which: str
) -> None:
    args, _, _ = _cli_args(tmp_path)
    path = tmp_path / ("locator" if which == "locator" else "state.json")
    target = tmp_path / f"{which}-target"
    path.rename(target)
    path.symlink_to(target)
    factory = SessionFactory([_response()])
    assert subject.main(args, session_factory=factory) == 2
    assert factory.sessions == []


@pytest.mark.parametrize("which", ["locator", "state"])
def test_private_inputs_reject_hardlinks_before_network(
    tmp_path: Path, which: str
) -> None:
    args, _, _ = _cli_args(tmp_path)
    path = tmp_path / ("locator" if which == "locator" else "state.json")
    os.link(path, tmp_path / f"{which}-second-link")
    factory = SessionFactory([_response()])
    assert subject.main(args, session_factory=factory) == 2
    assert factory.sessions == []


def test_invalid_locator_precedes_secret_state_read_and_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args, _, _ = _cli_args(tmp_path)
    _private_file(tmp_path / "locator", b"https://evil.example/steal\n")
    original = subject._read_private_regular

    def guarded(path: Path, *, label: str) -> bytes:
        if "storage-state" in label:
            raise AssertionError("secret state must not be opened")
        return original(path, label=label)

    monkeypatch.setattr(subject, "_read_private_regular", guarded)
    factory = SessionFactory([_response()])
    assert subject.main(args, session_factory=factory) == 2
    assert factory.sessions == []


def test_existing_output_fails_before_private_input_read_or_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args, evidence, _ = _cli_args(tmp_path)
    evidence.mkdir()

    def bomb(*args: object, **kwargs: object) -> bytes:
        raise AssertionError((args, kwargs))

    monkeypatch.setattr(subject, "_read_private_regular", bomb)
    factory = SessionFactory([_response()])
    assert subject.main(args, session_factory=factory) == 2
    assert factory.sessions == []


def test_nonprivate_output_parent_fails_before_private_input_read_or_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args, _, _ = _cli_args(tmp_path)
    tmp_path.chmod(0o755)

    def bomb(*args: object, **kwargs: object) -> bytes:
        raise AssertionError((args, kwargs))

    monkeypatch.setattr(subject, "_read_private_regular", bomb)
    factory = SessionFactory([_response()])
    assert subject.main(args, session_factory=factory) == 2
    assert factory.sessions == []


def test_cli_success_is_private_create_once_and_canary_free(
    tmp_path: Path, capsysbinary: pytest.CaptureFixture[bytes]
) -> None:
    args, evidence, receipt = _cli_args(tmp_path)
    factory = _success_factory()
    assert subject.main(args, session_factory=factory) == 0
    stdout = capsysbinary.readouterr().out
    evidence_path = evidence / "rehearsal-evidence.json"
    intent_path = evidence / "intent.json"
    assert stat.S_IMODE(evidence.stat().st_mode) == 0o700
    for path in (evidence_path, intent_path, receipt):
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    persisted = stdout + evidence_path.read_bytes() + receipt.read_bytes()
    for canary in (
        COOKIE_NAME_CANARY,
        COOKIE_VALUE_CANARY,
        QUERY_VALUE_CANARY,
        PATH_VALUE_CANARY,
        HEADER_VALUE_CANARY,
        ROW_VALUE_CANARY,
    ):
        assert canary.encode() not in persisted
    session_count = len(factory.sessions)
    assert subject.main(args, session_factory=factory) == 2
    assert len(factory.sessions) == session_count


def test_runtime_module_has_no_cloud_gcloud_or_subprocess_surface() -> None:
    source = Path(subject.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not {"subprocess", "google", "google.cloud"}.intersection(imports)
    assert "subprocess.run" not in source
    assert "storage buckets" not in source
    assert "run jobs" not in source
    assert "analyze-iam-policy" not in source
    parsers = [subject._parser()]
    cli_surface: list[str] = []
    while parsers:
        parser = parsers.pop()
        for action in parser._actions:
            cli_surface.extend(action.option_strings)
            cli_surface.append(action.dest)
            if action.__class__.__name__ == "_SubParsersAction":
                parsers.extend(action.choices.values())
    rendered_surface = " ".join(cli_surface).casefold()
    assert not any(
        marker in rendered_surface
        for marker in ("gcloud", "cloud", "bucket", "iam", "job", "secret")
    )


def test_no_public_or_default_real_network_rehearsal_callable_exists() -> None:
    assert not hasattr(subject, "rehearse_acceptance_download_v1")
    assert "rehearse_acceptance_download_v1" not in subject.__all__
    rehearsal_parameters = inspect.signature(
        subject._rehearse_acceptance_download_v1
    ).parameters
    transport_parameters = inspect.signature(
        subject._LocalAcceptanceTransport
    ).parameters
    assert rehearsal_parameters["session_factory"].default is inspect.Parameter.empty
    assert transport_parameters["session_factory"].default is inspect.Parameter.empty
