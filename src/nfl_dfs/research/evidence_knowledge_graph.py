"""Auditable research-evidence knowledge graph.

This module is deliberately separate from :mod:`nfl_dfs.graph`, which models
players and teams.  Here the vertices are policies, rules, experiment arms,
populations, endpoints, measurements, gates, licences, and bounded claims.

The graph is an index over immutable evidence.  It never grants authority that
is absent from the referenced protocol/result bytes.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Iterable, Mapping


SCHEMA = "nfl-dfs-research-evidence-graph/v1"
NODE_KINDS = frozenset({
    "arm",
    "batch",
    "claim",
    "corpus",
    "endpoint",
    "execution",
    "gate",
    "license",
    "measurement",
    "parameter",
    "parameter_set",
    "policy",
    "population",
    "rule",
})
EDGE_KINDS = frozenset({
    "ARM_RESULT",
    "BOUND_TO_EXECUTION",
    "COMPARES_WITH",
    "DECIDES_LICENSE",
    "DEPLOYED_AS",
    "EVALUATES_GATE",
    "INHERITS_POLICY",
    "INVALIDATES",
    "MEASURES",
    "MOTIVATED_BY",
    "OBSERVED_ON",
    "RULE_APPLICATION",
    "PART_OF_BATCH",
    "PRODUCES",
    "SETS_PARAMETER",
    "SHARES_POOL_WITH",
    "SUPPORTED_BY",
    "SUPERSEDES",
    "USES_CORPUS",
    "USES_POPULATION",
    "USES_PARAMETER_SET",
    "USES_SELECTOR",
})
RULE_EFFECTS = frozenset({
    "added", "nonoperative", "relaxed", "removed", "replaced", "retained",
    "tightened",
})
APPLICATIONS = frozenset({"direct", "not_applicable", "upstream_inherited"})
STAGES = frozenset({"admission", "generation", "selection", "simulation"})
KNOWLEDGE_CLASSES = frozenset({
    "outcome_blind", "outcome_viewed", "prospective",
})
EVIDENCE_ROLES = frozenset({
    "execution", "implementation", "observation", "specification", "synthesis",
})
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
ID_RE = re.compile(r"^[a-z][a-z0-9_.:-]*$")


class EvidenceGraphError(ValueError):
    """Raised when graph evidence, schema, or derived coverage is invalid."""


@dataclass(frozen=True)
class EvidenceGraph:
    builder_sha256: str
    graph_id: str
    registry_sha256: str
    rule_universe_sha256: str
    artifacts: tuple[dict[str, Any], ...]
    nodes: tuple[dict[str, Any], ...]
    edges: tuple[dict[str, Any], ...]

    def node_map(self) -> dict[str, dict[str, Any]]:
        return {str(row["id"]): row for row in self.nodes}

    def artifact_map(self) -> dict[str, dict[str, Any]]:
        return {str(row["id"]): row for row in self.artifacts}


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ) + "\n").encode("utf-8")


def _strict_json_loads(body: bytes, *, what: str) -> Any:
    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in pairs:
            if key in out:
                raise EvidenceGraphError(f"{what} has a duplicate JSON key: {key}")
            out[key] = value
        return out

    def reject_constant(value: str) -> None:
        raise EvidenceGraphError(f"{what} has a non-finite JSON value: {value}")

    try:
        return json.loads(
            body,
            object_pairs_hook=object_pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceGraphError(f"{what} is invalid JSON") from exc


def _hash_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def _same_type_value(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            _same_type_value(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _same_type_value(a, b) for a, b in zip(left, right, strict=True)
        )
    return left == right


def _parameter_value_matches(value: Any, parameter_type: str) -> bool:
    if parameter_type == "boolean":
        return type(value) is bool
    if parameter_type == "integer":
        return type(value) is int
    if parameter_type in {"category", "string"}:
        return type(value) is str
    return False


def _require_id(value: object, *, what: str) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise EvidenceGraphError(f"{what} has an invalid semantic id")
    return value


def _require_sha(value: object, *, what: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise EvidenceGraphError(f"{what} has an invalid SHA-256")
    return value


def _strict_object(value: object, *, what: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EvidenceGraphError(f"{what} must be an object")
    return value


def _strict_list(value: object, *, what: str) -> list[Any]:
    if not isinstance(value, list):
        raise EvidenceGraphError(f"{what} must be an array")
    return value


def _json_pointer(body: object, pointer: str) -> object:
    if pointer == "":
        return body
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise EvidenceGraphError("JSON pointer must be empty or begin with '/'")
    current = body
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            if not token.isdigit():
                raise EvidenceGraphError(f"non-numeric array pointer token: {token}")
            index = int(token)
            if index >= len(current):
                raise EvidenceGraphError(f"array pointer is out of range: {pointer}")
            current = current[index]
        elif isinstance(current, dict):
            if token not in current:
                raise EvidenceGraphError(f"JSON pointer is absent: {pointer}")
            current = current[token]
        else:
            raise EvidenceGraphError(f"JSON pointer traverses a scalar: {pointer}")
    return current


def _safe_source_path(root: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise EvidenceGraphError("artifact path must be a nonempty relative path")
    resolved_root = root.resolve()
    resolved = (root / relative).resolve()
    if resolved_root != resolved and resolved_root not in resolved.parents:
        raise EvidenceGraphError("artifact path escapes the repository root")
    if not resolved.is_file():
        raise EvidenceGraphError(f"artifact is absent or not a file: {relative}")
    return resolved


def _validate_artifacts(
    root: Path,
    raw: object,
) -> tuple[tuple[dict[str, Any], ...], dict[str, bytes]]:
    rows = _strict_list(raw, what="artifacts")
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    bodies: dict[str, bytes] = {}
    for index, raw_row in enumerate(rows):
        row = _strict_object(raw_row, what=f"artifacts[{index}]")
        if set(row) != {"id", "kind", "path", "sha256"}:
            raise EvidenceGraphError("artifact schema differs")
        artifact_id = _require_id(row["id"], what=f"artifacts[{index}]")
        if artifact_id in seen:
            raise EvidenceGraphError(f"duplicate artifact id: {artifact_id}")
        seen.add(artifact_id)
        if row["kind"] not in {"code", "ledger", "protocol", "result"}:
            raise EvidenceGraphError(f"artifact kind differs: {artifact_id}")
        expected = _require_sha(row["sha256"], what=artifact_id)
        path = _safe_source_path(root, row["path"])
        body = path.read_bytes()
        if _hash_bytes(body) != expected:
            raise EvidenceGraphError(f"artifact SHA-256 differs: {artifact_id}")
        bodies[artifact_id] = body
        out.append(dict(row))
    return tuple(sorted(out, key=lambda item: item["id"])), bodies


def _validate_evidence(
    raw: object,
    *,
    artifacts: Mapping[str, dict[str, Any]],
    bodies: Mapping[str, bytes],
    what: str,
) -> tuple[dict[str, Any], ...]:
    rows = _strict_list(raw, what=f"{what}.evidence")
    if not rows:
        raise EvidenceGraphError(f"{what} has no evidence")
    out: list[dict[str, Any]] = []
    for index, raw_row in enumerate(rows):
        row = _strict_object(raw_row, what=f"{what}.evidence[{index}]")
        allowed = {"artifact_id", "contains", "expected", "json_pointer", "role"}
        if not set(row) <= allowed or not {"artifact_id", "role"} <= set(row):
            raise EvidenceGraphError(f"{what} evidence schema differs")
        artifact_id = _require_id(row["artifact_id"], what=f"{what}.evidence")
        if artifact_id not in artifacts:
            raise EvidenceGraphError(f"{what} cites an unknown artifact")
        if row["role"] not in EVIDENCE_ROLES:
            raise EvidenceGraphError(f"{what} has an invalid evidence role")
        has_pointer = "json_pointer" in row or "expected" in row
        has_contains = "contains" in row
        if has_pointer == has_contains:
            raise EvidenceGraphError(
                f"{what} evidence needs exactly one pointer or text assertion"
            )
        body = bodies[artifact_id]
        if has_pointer:
            if set(row) != {"artifact_id", "expected", "json_pointer", "role"}:
                raise EvidenceGraphError(f"{what} JSON evidence schema differs")
            try:
                parsed = _strict_json_loads(body, what=artifact_id)
            except EvidenceGraphError as exc:
                raise EvidenceGraphError(
                    f"{what} cites non-JSON pointer evidence"
                ) from exc
            actual = _json_pointer(parsed, row["json_pointer"])
            if not _same_type_value(actual, row["expected"]):
                raise EvidenceGraphError(f"{what} JSON evidence value differs")
        else:
            if set(row) != {"artifact_id", "contains", "role"}:
                raise EvidenceGraphError(f"{what} text evidence schema differs")
            needle = row["contains"]
            if not isinstance(needle, str) or not needle:
                raise EvidenceGraphError(f"{what} has empty text evidence")
            try:
                text = body.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise EvidenceGraphError(f"{what} text evidence is not UTF-8") from exc
            if needle not in text:
                raise EvidenceGraphError(f"{what} text evidence is absent")
        out.append(dict(row))
    return tuple(out)


def _rule_universe_hash(rules: Iterable[Mapping[str, Any]]) -> str:
    projection = [{
        "baseline_operational": row["baseline_operational"],
        "classification": row["classification"],
        "id": row["id"],
        "stage": row["stage"],
    } for row in sorted(rules, key=lambda item: item["id"])]
    return _hash_bytes(canonical_json_bytes(projection))


def _validate_scope(raw: object, *, what: str) -> dict[str, Any]:
    row = _strict_object(raw, what=f"{what}.scope")
    required = {"candidate_path", "denominator", "fraction", "numerator", "unit"}
    if set(row) != required:
        raise EvidenceGraphError(f"{what} scope schema differs")
    if not isinstance(row["candidate_path"], str) or not row["candidate_path"]:
        raise EvidenceGraphError(f"{what} candidate path differs")
    numerator, denominator, fraction = row["numerator"], row["denominator"], row["fraction"]
    if type(numerator) is not int or type(denominator) is not int:
        raise EvidenceGraphError(f"{what} scope counts must be integers")
    if denominator <= 0 or not 0 <= numerator <= denominator:
        raise EvidenceGraphError(f"{what} scope counts differ")
    if type(fraction) not in {int, float} or isinstance(fraction, bool):
        raise EvidenceGraphError(f"{what} fraction must be numeric")
    if abs(float(fraction) - numerator / denominator) > 1e-12:
        raise EvidenceGraphError(f"{what} scope fraction differs")
    if not isinstance(row["unit"], str) or not row["unit"]:
        raise EvidenceGraphError(f"{what} scope unit differs")
    return dict(row)


def _evaluate_binding(
    raw: object,
    *,
    artifacts: Mapping[str, dict[str, Any]],
    bodies: Mapping[str, bytes],
    what: str,
) -> tuple[Any, list[dict[str, Any]]]:
    expression = _strict_object(raw, what=what)
    op = expression.get("op")
    if op == "source":
        if set(expression) != {"artifact_id", "json_pointer", "op", "role"}:
            raise EvidenceGraphError(f"{what} source binding schema differs")
        artifact_id = _require_id(expression["artifact_id"], what=what)
        if artifact_id not in artifacts:
            raise EvidenceGraphError(f"{what} source artifact is unknown")
        if expression["role"] not in EVIDENCE_ROLES:
            raise EvidenceGraphError(f"{what} source role differs")
        parsed = _strict_json_loads(bodies[artifact_id], what=artifact_id)
        value = _json_pointer(parsed, expression["json_pointer"])
        return value, [{
            "artifact_id": artifact_id,
            "expected": value,
            "json_pointer": expression["json_pointer"],
            "role": expression["role"],
        }]
    if op == "text_capture":
        required = {
            "artifact_id", "group", "op", "pattern", "role", "value_type",
        }
        if set(expression) != required:
            raise EvidenceGraphError(f"{what} text-capture binding schema differs")
        artifact_id = _require_id(expression["artifact_id"], what=what)
        if artifact_id not in artifacts:
            raise EvidenceGraphError(f"{what} text-capture artifact is unknown")
        if expression["role"] not in EVIDENCE_ROLES:
            raise EvidenceGraphError(f"{what} text-capture role differs")
        pattern = expression["pattern"]
        group = expression["group"]
        value_type = expression["value_type"]
        if not isinstance(pattern, str) or not pattern:
            raise EvidenceGraphError(f"{what} text-capture pattern differs")
        if type(group) is not int or group <= 0:
            raise EvidenceGraphError(f"{what} text-capture group differs")
        if value_type not in {"env_boolean", "integer", "string"}:
            raise EvidenceGraphError(f"{what} text-capture value type differs")
        try:
            text = bodies[artifact_id].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise EvidenceGraphError(
                f"{what} text-capture artifact is not UTF-8"
            ) from exc
        try:
            matches = list(re.finditer(pattern, text, flags=re.MULTILINE | re.DOTALL))
        except re.error as exc:
            raise EvidenceGraphError(f"{what} text-capture pattern is invalid") from exc
        if len(matches) != 1:
            raise EvidenceGraphError(
                f"{what} text-capture match cardinality differs: {len(matches)}"
            )
        match = matches[0]
        try:
            captured = match.group(group)
        except IndexError as exc:
            raise EvidenceGraphError(f"{what} text-capture group is absent") from exc
        if value_type == "integer":
            if re.fullmatch(r"0|[1-9][0-9]*", captured) is None:
                raise EvidenceGraphError(f"{what} captured integer differs")
            value: Any = int(captured)
        elif value_type == "env_boolean":
            if captured not in {"", "0", "1"}:
                raise EvidenceGraphError(f"{what} captured env Boolean differs")
            value = captured == "1"
        else:
            value = captured
        return value, [{
            "artifact_id": artifact_id,
            "contains": match.group(0),
            "role": expression["role"],
        }]
    if op in {"difference", "ratio"}:
        if set(expression) != {"left", "op", "right"}:
            raise EvidenceGraphError(f"{what} derived binding schema differs")
        left, left_evidence = _evaluate_binding(
            expression["left"], artifacts=artifacts, bodies=bodies,
            what=f"{what}.left",
        )
        right, right_evidence = _evaluate_binding(
            expression["right"], artifacts=artifacts, bodies=bodies,
            what=f"{what}.right",
        )
        if (
            type(left) not in {int, float}
            or type(right) not in {int, float}
            or isinstance(left, bool)
            or isinstance(right, bool)
        ):
            raise EvidenceGraphError(f"{what} operands must be numeric")
        if op == "ratio":
            if right == 0:
                raise EvidenceGraphError(f"{what} ratio denominator is zero")
            value = left / right
        else:
            value = left - right
        return value, [*left_evidence, *right_evidence]
    if op == "length":
        if set(expression) != {"op", "value"}:
            raise EvidenceGraphError(f"{what} length binding schema differs")
        value, evidence = _evaluate_binding(
            expression["value"], artifacts=artifacts, bodies=bodies,
            what=f"{what}.value",
        )
        if not isinstance(value, (dict, list, str)):
            raise EvidenceGraphError(f"{what} length operand differs")
        return len(value), evidence
    raise EvidenceGraphError(f"{what} binding operation differs")


def build_graph(root: Path, registry_path: Path) -> EvidenceGraph:
    """Validate a curated registry and materialize its complete property graph."""
    try:
        registry_body = registry_path.read_bytes()
        registry = _strict_json_loads(registry_body, what="registry")
    except (OSError, EvidenceGraphError) as exc:
        raise EvidenceGraphError("registry is unreadable or invalid JSON") from exc
    registry = _strict_object(registry, what="registry")
    required = {
        "arms", "artifacts", "graph_id", "nodes", "rule_universe",
        "measurement_bindings", "schema", "scope",
    }
    if set(registry) != required or registry["schema"] != SCHEMA:
        raise EvidenceGraphError("registry top-level schema differs")
    graph_id = _require_id(registry["graph_id"], what="graph")
    if not isinstance(registry["scope"], str) or not registry["scope"]:
        raise EvidenceGraphError("graph scope differs")

    artifact_rows, bodies = _validate_artifacts(root, registry["artifacts"])
    artifact_map = {row["id"]: row for row in artifact_rows}
    measurement_bindings = _strict_object(
        registry["measurement_bindings"], what="measurement_bindings",
    )

    rule_rows = _strict_list(registry["rule_universe"], what="rule_universe")
    rules: dict[str, dict[str, Any]] = {}
    base_nodes: list[dict[str, Any]] = []
    for index, raw_rule in enumerate(rule_rows):
        row = _strict_object(raw_rule, what=f"rule_universe[{index}]")
        required_rule = {
            "baseline_operational", "classification", "evidence", "id", "label", "stage",
        }
        if set(row) != required_rule:
            raise EvidenceGraphError("rule schema differs")
        rule_id = _require_id(row["id"], what="rule")
        if rule_id in rules:
            raise EvidenceGraphError(f"duplicate rule id: {rule_id}")
        if row["classification"] not in {
            "dk_hard", "generation_recipe", "house_soft", "selector",
            "simulation_law",
        }:
            raise EvidenceGraphError(f"rule classification differs: {rule_id}")
        if row["stage"] not in STAGES:
            raise EvidenceGraphError(f"rule stage differs: {rule_id}")
        if type(row["baseline_operational"]) is not bool:
            raise EvidenceGraphError(f"baseline operational flag differs: {rule_id}")
        if not isinstance(row["label"], str) or not row["label"]:
            raise EvidenceGraphError(f"rule label differs: {rule_id}")
        evidence = _validate_evidence(
            row["evidence"], artifacts=artifact_map, bodies=bodies, what=rule_id,
        )
        rule = {
            "baseline_operational": row["baseline_operational"],
            "classification": row["classification"],
            "evidence": list(evidence),
            "id": rule_id,
            "kind": "rule",
            "knowledge_class": "outcome_blind",
            "label": row["label"],
            "stage": row["stage"],
        }
        rules[rule_id] = rule
        base_nodes.append(rule)

    universe_sha = _rule_universe_hash(rules.values())
    raw_nodes = _strict_list(registry["nodes"], what="nodes")
    measurement_ids: set[str] = set()
    for index, raw_node in enumerate(raw_nodes):
        row = _strict_object(raw_node, what=f"nodes[{index}]")
        required_node = {"evidence", "id", "kind", "knowledge_class", "label", "properties"}
        if set(row) != required_node:
            raise EvidenceGraphError("node schema differs")
        node_id = _require_id(row["id"], what="node")
        if row["kind"] not in NODE_KINDS - {"arm", "rule"}:
            raise EvidenceGraphError(f"node kind differs: {node_id}")
        if row["knowledge_class"] not in KNOWLEDGE_CLASSES:
            raise EvidenceGraphError(f"node knowledge class differs: {node_id}")
        if not isinstance(row["label"], str) or not row["label"]:
            raise EvidenceGraphError(f"node label differs: {node_id}")
        properties = dict(_strict_object(
            row["properties"], what=f"{node_id}.properties",
        ))
        if row["kind"] == "parameter":
            if set(properties) != {"allowed_values", "surface", "type"}:
                raise EvidenceGraphError(f"{node_id} parameter schema differs")
            parameter_type = properties["type"]
            if parameter_type not in {"boolean", "category", "integer", "string"}:
                raise EvidenceGraphError(f"{node_id} parameter type differs")
            if properties["surface"] != "historical_observed_only":
                raise EvidenceGraphError(f"{node_id} parameter surface differs")
            allowed = _strict_list(
                properties["allowed_values"], what=f"{node_id}.allowed_values",
            )
            if not allowed or not all(
                _parameter_value_matches(value, parameter_type) for value in allowed
            ):
                raise EvidenceGraphError(f"{node_id} parameter domain differs")
            if len({canonical_json_bytes(value) for value in allowed}) != len(allowed):
                raise EvidenceGraphError(f"{node_id} parameter domain duplicates")
        evidence = _validate_evidence(
            row["evidence"], artifacts=artifact_map, bodies=bodies, what=node_id,
        )
        if row["kind"] == "measurement":
            measurement_ids.add(node_id)
            bindings = _strict_object(
                measurement_bindings.get(node_id),
                what=f"{node_id}.measurement_bindings",
            )
            decision_properties = set(properties) - {"relations"}
            if set(bindings) != decision_properties:
                raise EvidenceGraphError(
                    f"{node_id} decision-property binding coverage differs"
                )
            bound_evidence = list(evidence)
            for property_name in sorted(decision_properties):
                value, source_evidence = _evaluate_binding(
                    bindings[property_name], artifacts=artifact_map, bodies=bodies,
                    what=f"{node_id}.properties.{property_name}",
                )
                if not _same_type_value(properties[property_name], value):
                    raise EvidenceGraphError(
                        f"{node_id} property differs from source: {property_name}"
                    )
                bound_evidence.extend(source_evidence)
            evidence = tuple(bound_evidence)
        base_nodes.append({**row, "evidence": list(evidence), "properties": properties})
    if set(measurement_bindings) != measurement_ids:
        raise EvidenceGraphError("measurement binding node coverage differs")

    arm_rows = _strict_list(registry["arms"], what="arms")
    arms: dict[str, dict[str, Any]] = {}
    for index, raw_arm in enumerate(arm_rows):
        row = _strict_object(raw_arm, what=f"arms[{index}]")
        required_arm = {
            "corpus_id", "evidence", "id", "inherits", "knowledge_class", "label",
            "parameter_changes", "policy_id", "population_id", "properties",
            "rule_overrides", "selector_rule_id",
        }
        if set(row) != required_arm:
            raise EvidenceGraphError("arm schema differs")
        arm_id = _require_id(row["id"], what="arm")
        if arm_id in arms:
            raise EvidenceGraphError(f"duplicate arm id: {arm_id}")
        if row["knowledge_class"] not in KNOWLEDGE_CLASSES:
            raise EvidenceGraphError(f"arm knowledge class differs: {arm_id}")
        evidence = _validate_evidence(
            row["evidence"], artifacts=artifact_map, bodies=bodies, what=arm_id,
        )
        arms[arm_id] = {**row, "evidence": list(evidence)}

    node_ids = [row["id"] for row in base_nodes] + list(arms)
    if len(node_ids) != len(set(node_ids)):
        raise EvidenceGraphError("node ids are not globally unique")
    preliminary_ids = set(node_ids)
    node_by_id = {row["id"]: row for row in base_nodes}
    for arm_id, arm in arms.items():
        for field in ("corpus_id", "policy_id", "population_id"):
            if arm[field] not in preliminary_ids:
                raise EvidenceGraphError(f"{arm_id} references an unknown {field}")
        if (
            arm["selector_rule_id"] is not None
            and arm["selector_rule_id"] not in preliminary_ids
        ):
            raise EvidenceGraphError(f"{arm_id} references an unknown selector_rule_id")
        parent = arm["inherits"]
        if parent is not None and parent not in arms:
            raise EvidenceGraphError(f"{arm_id} inherits an unknown arm")
        if not isinstance(arm["label"], str) or not arm["label"]:
            raise EvidenceGraphError(f"arm label differs: {arm_id}")
        _strict_object(arm["properties"], what=f"{arm_id}.properties")
        _strict_object(arm["rule_overrides"], what=f"{arm_id}.rule_overrides")
        _strict_list(arm["parameter_changes"], what=f"{arm_id}.parameter_changes")

    expanded: dict[str, dict[str, dict[str, Any]]] = {}
    visiting: set[str] = set()

    def expand(arm_id: str) -> dict[str, dict[str, Any]]:
        if arm_id in expanded:
            return expanded[arm_id]
        if arm_id in visiting:
            raise EvidenceGraphError("arm inheritance cycle")
        visiting.add(arm_id)
        arm = arms[arm_id]
        parent = arm["inherits"]
        if parent:
            matrix = {}
            for key, value in expand(parent).items():
                inherited = dict(value)
                inherited["evidence"] = [*value["evidence"], *arm["evidence"]]
                if (
                    arm["properties"].get("fixed_pool") is True
                    and rules[key]["stage"] in {
                        "admission", "generation", "simulation",
                    }
                ):
                    inherited["application"] = "upstream_inherited"
                matrix[key] = inherited
        else:
            matrix = {}
        if arm["properties"].get("diagnostic_only") is True:
            for key, value in matrix.items():
                value["application"] = "not_applicable"
                value["effect"] = "nonoperative"
                value["scope"] = {
                    "candidate_path": "diagnostic",
                    "denominator": 1,
                    "fraction": 1,
                    "numerator": 1,
                    "unit": "diagnostic_scope",
                }
        for rule_id, raw_application in arm["rule_overrides"].items():
            if rule_id not in rules:
                raise EvidenceGraphError(f"{arm_id} overrides an unknown rule")
            app = _strict_object(raw_application, what=f"{arm_id}.{rule_id}")
            required_application = {"application", "effect", "evidence", "scope"}
            if set(app) != required_application:
                raise EvidenceGraphError(f"{arm_id} rule application schema differs")
            if app["effect"] not in RULE_EFFECTS:
                raise EvidenceGraphError(f"{arm_id} rule effect differs")
            if app["application"] not in APPLICATIONS:
                raise EvidenceGraphError(f"{arm_id} application mode differs")
            scope = _validate_scope(app["scope"], what=f"{arm_id}.{rule_id}")
            evidence = _validate_evidence(
                app["evidence"], artifacts=artifact_map, bodies=bodies,
                what=f"{arm_id}.{rule_id}",
            )
            matrix[rule_id] = {
                "application": app["application"],
                "effect": app["effect"],
                "evidence": list(evidence),
                "scope": scope,
            }
        visiting.remove(arm_id)
        if set(matrix) != set(rules):
            missing = sorted(set(rules) - set(matrix))
            extra = sorted(set(matrix) - set(rules))
            raise EvidenceGraphError(
                f"{arm_id} rule coverage differs; missing={missing}, extra={extra}"
            )
        expanded[arm_id] = matrix
        return matrix

    for arm_id in arms:
        expand(arm_id)

    nodes = list(base_nodes)
    edges: list[dict[str, Any]] = []
    for arm_id, arm in arms.items():
        arm_node = {
            "evidence": arm["evidence"],
            "id": arm_id,
            "kind": "arm",
            "knowledge_class": arm["knowledge_class"],
            "label": arm["label"],
            "properties": {
                **arm["properties"],
                "curated_rule_coverage_complete": True,
                "rule_universe_sha256": universe_sha,
            },
        }
        nodes.append(arm_node)
        core_targets = [
            ("USES_CORPUS", arm["corpus_id"]),
            ("USES_POPULATION", arm["population_id"]),
            ("INHERITS_POLICY", arm["policy_id"]),
        ]
        if arm["selector_rule_id"] is not None:
            core_targets.append(("USES_SELECTOR", arm["selector_rule_id"]))
        for kind, target in core_targets:
            edges.append({
                "evidence": arm["evidence"],
                "from": arm_id,
                "id": f"edge:{arm_id}:{kind.lower()}:{target}",
                "kind": kind,
                "properties": {},
                "to": target,
            })
        for rule_id, application in expanded[arm_id].items():
            edges.append({
                "evidence": application["evidence"],
                "from": arm_id,
                "id": f"edge:{arm_id}:rule:{rule_id}",
                "kind": "RULE_APPLICATION",
                "properties": {
                    "application": application["application"],
                    "effect": application["effect"],
                    "scope": application["scope"],
                    "stage": rules[rule_id]["stage"],
                },
                "to": rule_id,
            })
        for index, raw_change in enumerate(arm["parameter_changes"]):
            change = _strict_object(raw_change, what=f"{arm_id}.parameter_changes[{index}]")
            if set(change) != {"bindings", "control", "parameter_id", "treatment"}:
                raise EvidenceGraphError(f"{arm_id} parameter change schema differs")
            parameter_id = _require_id(change["parameter_id"], what="parameter change")
            if (
                parameter_id not in preliminary_ids
                or node_by_id.get(parameter_id, {}).get("kind") != "parameter"
            ):
                raise EvidenceGraphError(f"{arm_id} references an unknown parameter")
            parameter = node_by_id[parameter_id]["properties"]
            for side in ("control", "treatment"):
                value = change[side]
                if (
                    not _parameter_value_matches(value, parameter["type"])
                    or not any(
                        _same_type_value(value, allowed)
                        for allowed in parameter["allowed_values"]
                    )
                ):
                    raise EvidenceGraphError(
                        f"{arm_id} parameter {side} is outside its frozen domain"
                    )
            bindings = _strict_object(
                change["bindings"], what=f"{arm_id}.{parameter_id}.bindings",
            )
            if set(bindings) != {"control", "treatment"}:
                raise EvidenceGraphError(
                    f"{arm_id} parameter binding side coverage differs"
                )
            evidence: list[dict[str, Any]] = []
            for side in ("control", "treatment"):
                value, source_evidence = _evaluate_binding(
                    bindings[side], artifacts=artifact_map, bodies=bodies,
                    what=f"{arm_id}.{parameter_id}.{side}",
                )
                if not _same_type_value(change[side], value):
                    raise EvidenceGraphError(
                        f"{arm_id} parameter {side} differs from source: "
                        f"{parameter_id}"
                    )
                evidence.extend(source_evidence)
            edges.append({
                "evidence": evidence,
                "from": arm_id,
                "id": f"edge:{arm_id}:sets:{parameter_id}",
                "kind": "SETS_PARAMETER",
                "properties": {
                    "control": change["control"],
                    "treatment": change["treatment"],
                },
                "to": parameter_id,
            })

    node_map = {row["id"]: row for row in nodes}
    for node in nodes:
        properties = node.get("properties", {})
        relations = properties.pop("relations", [])
        for relation in relations:
            relation = _strict_object(relation, what=f"{node['id']}.relation")
            if set(relation) != {"evidence", "kind", "properties", "to"}:
                raise EvidenceGraphError("embedded relation schema differs")
            if relation["kind"] not in EDGE_KINDS:
                raise EvidenceGraphError("embedded relation kind differs")
            if relation["to"] not in node_map:
                raise EvidenceGraphError("embedded relation target is unknown")
            evidence = _validate_evidence(
                relation["evidence"], artifacts=artifact_map, bodies=bodies,
                what=f"{node['id']}.{relation['kind']}",
            )
            edges.append({
                "evidence": list(evidence),
                "from": node["id"],
                "id": f"edge:{node['id']}:{relation['kind'].lower()}:{relation['to']}",
                "kind": relation["kind"],
                "properties": _strict_object(
                    relation["properties"], what="relation properties"
                ),
                "to": relation["to"],
            })

    _validate_materialized(artifact_rows, nodes, edges, universe_sha)
    return EvidenceGraph(
        builder_sha256=_hash_bytes(Path(__file__).resolve().read_bytes()),
        graph_id=graph_id,
        registry_sha256=_hash_bytes(registry_body),
        rule_universe_sha256=universe_sha,
        artifacts=artifact_rows,
        nodes=tuple(sorted(nodes, key=lambda item: item["id"])),
        edges=tuple(sorted(edges, key=lambda item: item["id"])),
    )


def _validate_materialized(
    artifacts: Iterable[Mapping[str, Any]],
    nodes: Iterable[Mapping[str, Any]],
    edges: Iterable[Mapping[str, Any]],
    universe_sha: str,
) -> None:
    artifact_rows = list(artifacts)
    artifact_ids: list[str] = []
    for index, raw in enumerate(artifact_rows):
        row = _strict_object(raw, what=f"materialized artifacts[{index}]")
        if set(row) != {"id", "kind", "path", "sha256"}:
            raise EvidenceGraphError("materialized artifact schema differs")
        artifact_ids.append(_require_id(row["id"], what="materialized artifact"))
        if row["kind"] not in {"code", "ledger", "protocol", "result"}:
            raise EvidenceGraphError("materialized artifact kind differs")
        _require_sha(row["sha256"], what="materialized artifact")
        if not isinstance(row["path"], str) or not row["path"]:
            raise EvidenceGraphError("materialized artifact path differs")
    if len(artifact_ids) != len(set(artifact_ids)):
        raise EvidenceGraphError("materialized artifact ids differ")
    artifact_id_set = set(artifact_ids)

    def validate_evidence_shape(raw: object, *, what: str) -> None:
        for index, evidence in enumerate(_strict_list(raw, what=f"{what}.evidence")):
            row = _strict_object(evidence, what=f"{what}.evidence[{index}]")
            if row.get("artifact_id") not in artifact_id_set:
                raise EvidenceGraphError(f"{what} evidence artifact differs")
            if row.get("role") not in EVIDENCE_ROLES:
                raise EvidenceGraphError(f"{what} evidence role differs")
            pointer_keys = {"artifact_id", "expected", "json_pointer", "role"}
            text_keys = {"artifact_id", "contains", "role"}
            if set(row) == pointer_keys:
                pointer = row["json_pointer"]
                if not isinstance(pointer, str) or (pointer and not pointer.startswith("/")):
                    raise EvidenceGraphError(f"{what} evidence pointer differs")
            elif set(row) == text_keys:
                if not isinstance(row["contains"], str) or not row["contains"]:
                    raise EvidenceGraphError(f"{what} evidence text differs")
            else:
                raise EvidenceGraphError(f"{what} evidence schema differs")

    node_rows = list(nodes)
    node_ids: list[str] = []
    for index, raw in enumerate(node_rows):
        row = _strict_object(raw, what=f"materialized nodes[{index}]")
        node_id = _require_id(row.get("id"), what="materialized node")
        node_ids.append(node_id)
        kind = row.get("kind")
        if kind not in NODE_KINDS:
            raise EvidenceGraphError("materialized node kind differs")
        if row.get("knowledge_class") not in KNOWLEDGE_CLASSES:
            raise EvidenceGraphError("materialized node knowledge class differs")
        if not isinstance(row.get("label"), str) or not row["label"]:
            raise EvidenceGraphError("materialized node label differs")
        if kind == "rule":
            if set(row) != {
                "baseline_operational", "classification", "evidence", "id",
                "kind", "knowledge_class", "label", "stage",
            }:
                raise EvidenceGraphError("materialized rule node schema differs")
            if type(row["baseline_operational"]) is not bool:
                raise EvidenceGraphError("materialized rule operational flag differs")
            if row["classification"] not in {
                "dk_hard", "generation_recipe", "house_soft", "selector",
                "simulation_law",
            }:
                raise EvidenceGraphError("materialized rule classification differs")
            if row["stage"] not in STAGES:
                raise EvidenceGraphError("materialized rule stage differs")
        else:
            if set(row) != {
                "evidence", "id", "kind", "knowledge_class", "label", "properties",
            }:
                raise EvidenceGraphError("materialized node schema differs")
            _strict_object(row["properties"], what=f"{node_id}.properties")
        validate_evidence_shape(row["evidence"], what=node_id)
    if len(node_ids) != len(set(node_ids)):
        raise EvidenceGraphError("materialized node ids differ")
    node_map = {row["id"]: row for row in node_rows}
    edge_rows = list(edges)
    edge_ids: list[str] = []
    endpoint_kinds = {
        "ARM_RESULT": ({"arm"}, {"measurement"}),
        "COMPARES_WITH": ({"measurement"}, {"population"}),
        "INHERITS_POLICY": ({"arm"}, {"policy"}),
        "MEASURES": ({"measurement"}, {"endpoint"}),
        "OBSERVED_ON": ({"measurement"}, {"population"}),
        "RULE_APPLICATION": ({"arm"}, {"rule"}),
        "SETS_PARAMETER": ({"arm"}, {"parameter"}),
        "SHARES_POOL_WITH": ({"arm"}, {"population"}),
        "SUPPORTED_BY": ({"policy"}, {"policy"}),
        "USES_CORPUS": ({"arm", "population"}, {"corpus"}),
        "USES_POPULATION": ({"arm"}, {"population"}),
        "USES_SELECTOR": ({"arm"}, {"rule"}),
    }
    for index, raw in enumerate(edge_rows):
        edge = _strict_object(raw, what=f"materialized edges[{index}]")
        if set(edge) != {"evidence", "from", "id", "kind", "properties", "to"}:
            raise EvidenceGraphError("materialized edge schema differs")
        edge_ids.append(_require_id(edge["id"], what="materialized edge"))
        if edge["kind"] not in EDGE_KINDS:
            raise EvidenceGraphError("materialized edge kind differs")
        if edge["from"] not in node_map or edge["to"] not in node_map:
            raise EvidenceGraphError("materialized edge endpoint is unknown")
        _strict_object(edge["properties"], what=f"{edge['id']}.properties")
        validate_evidence_shape(edge["evidence"], what=edge["id"])
        if edge["kind"] in endpoint_kinds:
            source_kinds, target_kinds = endpoint_kinds[edge["kind"]]
            if (
                node_map[edge["from"]]["kind"] not in source_kinds
                or node_map[edge["to"]]["kind"] not in target_kinds
            ):
                raise EvidenceGraphError(
                    "materialized edge endpoint kind differs: "
                    f"{edge['id']} "
                    f"{node_map[edge['from']]['kind']}->{node_map[edge['to']]['kind']}"
                )
        if edge["kind"] == "RULE_APPLICATION":
            properties = edge["properties"]
            if set(properties) != {"application", "effect", "scope", "stage"}:
                raise EvidenceGraphError("materialized rule edge schema differs")
            if properties["application"] not in APPLICATIONS:
                raise EvidenceGraphError("materialized rule application differs")
            if properties["effect"] not in RULE_EFFECTS:
                raise EvidenceGraphError("materialized rule effect differs")
            if properties["stage"] != node_map[edge["to"]]["stage"]:
                raise EvidenceGraphError("materialized rule stage binding differs")
            _validate_scope(properties["scope"], what=edge["id"])
    if len(edge_ids) != len(set(edge_ids)):
        raise EvidenceGraphError("materialized edge ids differ")
    rule_ids = {row["id"] for row in node_rows if row["kind"] == "rule"}
    if _rule_universe_hash(node_map[rule_id] for rule_id in rule_ids) != universe_sha:
        raise EvidenceGraphError("materialized rule universe hash differs")
    for arm in (row for row in node_rows if row["kind"] == "arm"):
        if arm["properties"].get("rule_universe_sha256") != universe_sha:
            raise EvidenceGraphError("arm rule universe binding differs")
        if arm["properties"].get("curated_rule_coverage_complete") is not True:
            raise EvidenceGraphError("arm materialized coverage flag differs")
        arm_rule_edges = [
            edge for edge in edge_rows
            if edge["kind"] == "RULE_APPLICATION" and edge["from"] == arm["id"]
        ]
        covered = [edge["to"] for edge in arm_rule_edges]
        if len(covered) != len(set(covered)):
            raise EvidenceGraphError(
                f"materialized rule edge cardinality differs: {arm['id']}"
            )
        if set(covered) != rule_ids:
            raise EvidenceGraphError(f"materialized rule coverage differs: {arm['id']}")
        for edge in arm_rule_edges:
            expected_id = f"edge:{arm['id']}:rule:{edge['to']}"
            if edge["id"] != expected_id:
                raise EvidenceGraphError(
                    f"materialized rule edge id differs: {edge['id']}"
                )
        for kind in ("INHERITS_POLICY", "USES_CORPUS", "USES_POPULATION"):
            count = sum(
                edge["kind"] == kind and edge["from"] == arm["id"]
                for edge in edge_rows
            )
            if count != 1:
                raise EvidenceGraphError(
                    f"materialized arm core-edge cardinality differs: "
                    f"{arm['id']} {kind}"
                )
        selector_count = sum(
            edge["kind"] == "USES_SELECTOR" and edge["from"] == arm["id"]
            for edge in edge_rows
        )
        expected_selector_count = (
            0 if arm["properties"].get("diagnostic_only") is True else 1
        )
        if selector_count != expected_selector_count:
            raise EvidenceGraphError(
                f"materialized arm selector cardinality differs: {arm['id']}"
            )
        parameter_targets = [
            edge["to"] for edge in edge_rows
            if edge["kind"] == "SETS_PARAMETER" and edge["from"] == arm["id"]
        ]
        if len(parameter_targets) != len(set(parameter_targets)):
            raise EvidenceGraphError(
                f"materialized parameter edge cardinality differs: {arm['id']}"
            )
    arm_result_measurements = [
        edge["to"] for edge in edge_rows if edge["kind"] == "ARM_RESULT"
    ]
    if len(arm_result_measurements) != len(set(arm_result_measurements)):
        raise EvidenceGraphError("materialized arm-result cardinality differs")
    for measurement_id in arm_result_measurements:
        for kind in ("COMPARES_WITH", "MEASURES", "OBSERVED_ON"):
            count = sum(
                edge["kind"] == kind and edge["from"] == measurement_id
                for edge in edge_rows
            )
            if count != 1:
                raise EvidenceGraphError(
                    "materialized headline edge cardinality differs: "
                    f"{measurement_id} {kind}"
                )


def _jsonl_bytes(rows: Iterable[Mapping[str, Any]]) -> bytes:
    return b"".join(canonical_json_bytes(dict(row)) for row in rows)


def write_graph(graph: EvidenceGraph, output_dir: Path) -> dict[str, Any]:
    """Atomically publish a new materialized graph directory."""
    _require_sha(graph.builder_sha256, what="graph builder")
    _require_sha(graph.registry_sha256, what="graph registry")
    _validate_materialized(
        graph.artifacts, graph.nodes, graph.edges, graph.rule_universe_sha256,
    )
    output_dir = output_dir.resolve()
    parent = output_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    if output_dir.exists():
        raise EvidenceGraphError("refusing to overwrite graph directory")
    claim_path = parent / f".{output_dir.name}.create-claim"
    try:
        claim_fd = os.open(
            claim_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600,
        )
    except FileExistsError as exc:
        raise EvidenceGraphError("graph publication claim already exists") from exc
    staging = Path(tempfile.mkdtemp(
        dir=parent, prefix=f".{output_dir.name}.staging-",
    ))
    published = False
    payloads = {
        "artifacts.jsonl": _jsonl_bytes(graph.artifacts),
        "nodes.jsonl": _jsonl_bytes(graph.nodes),
        "edges.jsonl": _jsonl_bytes(graph.edges),
    }
    file_receipts = {
        name: {"bytes": len(body), "sha256": _hash_bytes(body)}
        for name, body in payloads.items()
    }
    manifest = {
        "artifacts": len(graph.artifacts),
        "builder_sha256": graph.builder_sha256,
        "decision_authority": False,
        "edges": len(graph.edges),
        "files": file_receipts,
        "graph_id": graph.graph_id,
        "licenses": {
            "historical_retry_licensed": False,
            "production_change_licensed": False,
            "prospective_shadow_licensed": False,
        },
        "independent_rule_inventory_sha256": None,
        "nodes": len(graph.nodes),
        "property_binding_scope": (
            "measurement_properties_and_parameter_assignments"
        ),
        "registry_sha256": graph.registry_sha256,
        "rule_universe_sha256": graph.rule_universe_sha256,
        "schema": SCHEMA,
    }
    manifest_body = canonical_json_bytes(manifest)
    try:
        for name, body in {**payloads, "manifest.json": manifest_body}.items():
            with (staging / name).open("xb") as handle:
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
        directory_fd = os.open(staging, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        if output_dir.exists():
            raise EvidenceGraphError("graph directory appeared during publication")
        staging.rename(output_dir)
        parent_fd = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        published = True
        return manifest
    finally:
        os.close(claim_fd)
        if not published and staging.exists():
            shutil.rmtree(staging)
        claim_path.unlink(missing_ok=True)


def read_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    body = path.read_bytes()
    if not body.endswith(b"\n"):
        raise EvidenceGraphError(f"JSONL lacks trailing newline: {path.name}")
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(body.splitlines()):
        row = _strict_json_loads(
            line, what=f"{path.name} row {index}",
        )
        row = _strict_object(row, what=f"{path.name}[{index}]")
        if canonical_json_bytes(row).rstrip(b"\n") != line:
            raise EvidenceGraphError(f"noncanonical JSONL row {index}: {path.name}")
        rows.append(row)
    return tuple(rows)


def load_graph(output_dir: Path) -> EvidenceGraph:
    """Structurally load a graph; callers must also replay its registry."""
    expected_names = {
        "artifacts.jsonl", "edges.jsonl", "manifest.json", "nodes.jsonl",
    }
    try:
        actual_names = {path.name for path in output_dir.iterdir()}
    except OSError as exc:
        raise EvidenceGraphError("graph directory is unreadable") from exc
    if actual_names != expected_names:
        raise EvidenceGraphError("graph directory file set differs")
    if any(
        not (output_dir / name).is_file() or (output_dir / name).is_symlink()
        for name in expected_names
    ):
        raise EvidenceGraphError("graph directory contains a non-regular file")
    manifest_path = output_dir / "manifest.json"
    try:
        manifest_body = manifest_path.read_bytes()
        manifest = _strict_json_loads(manifest_body, what="graph manifest")
    except (OSError, EvidenceGraphError) as exc:
        raise EvidenceGraphError("graph manifest is unreadable") from exc
    if canonical_json_bytes(manifest) != manifest_body:
        raise EvidenceGraphError("graph manifest is not canonical")
    if set(manifest) != {
        "artifacts", "builder_sha256", "decision_authority", "edges", "files",
        "graph_id",
        "independent_rule_inventory_sha256", "licenses", "nodes",
        "property_binding_scope", "registry_sha256", "rule_universe_sha256",
        "schema",
    } or manifest.get("schema") != SCHEMA:
        raise EvidenceGraphError("graph manifest schema differs")
    if manifest.get("decision_authority") is not False:
        raise EvidenceGraphError("graph manifest decision authority differs")
    if manifest.get("property_binding_scope") != (
        "measurement_properties_and_parameter_assignments"
    ):
        raise EvidenceGraphError("graph manifest property-binding scope differs")
    if manifest.get("licenses") != {
        "historical_retry_licensed": False,
        "production_change_licensed": False,
        "prospective_shadow_licensed": False,
    }:
        raise EvidenceGraphError("graph manifest license boundary differs")
    if manifest.get("independent_rule_inventory_sha256") is not None:
        raise EvidenceGraphError("v1 independent rule inventory claim differs")
    if set(manifest.get("files", {})) != {
        "artifacts.jsonl", "edges.jsonl", "nodes.jsonl",
    }:
        raise EvidenceGraphError("graph manifest file set differs")
    artifacts = read_jsonl(output_dir / "artifacts.jsonl")
    nodes = read_jsonl(output_dir / "nodes.jsonl")
    edges = read_jsonl(output_dir / "edges.jsonl")
    for name, rows in (
        ("artifacts.jsonl", artifacts), ("nodes.jsonl", nodes), ("edges.jsonl", edges),
    ):
        body = (output_dir / name).read_bytes()
        receipt = manifest["files"].get(name)
        if receipt != {"bytes": len(body), "sha256": _hash_bytes(body)}:
            raise EvidenceGraphError(f"graph file receipt differs: {name}")
    if manifest.get("artifacts") != len(artifacts):
        raise EvidenceGraphError("artifact count differs")
    if manifest.get("nodes") != len(nodes) or manifest.get("edges") != len(edges):
        raise EvidenceGraphError("node or edge count differs")
    universe_sha = _require_sha(
        manifest.get("rule_universe_sha256"), what="graph manifest"
    )
    builder_sha = _require_sha(
        manifest.get("builder_sha256"), what="graph manifest"
    )
    registry_sha = _require_sha(
        manifest.get("registry_sha256"), what="graph manifest"
    )
    _validate_materialized(artifacts, nodes, edges, universe_sha)
    return EvidenceGraph(
        builder_sha256=builder_sha,
        graph_id=_require_id(manifest.get("graph_id"), what="graph manifest"),
        registry_sha256=registry_sha,
        rule_universe_sha256=universe_sha,
        artifacts=artifacts,
        nodes=nodes,
        edges=edges,
    )


def validate_graph_against_registry(
    root: Path,
    registry_path: Path,
    graph: EvidenceGraph,
) -> None:
    """Replay pinned sources and require exact equality with materialized bytes."""
    expected = build_graph(root, registry_path)
    def projection(value: EvidenceGraph) -> dict[str, Any]:
        return {
            "artifacts": list(value.artifacts),
            "builder_sha256": value.builder_sha256,
            "edges": list(value.edges),
            "graph_id": value.graph_id,
            "nodes": list(value.nodes),
            "registry_sha256": value.registry_sha256,
            "rule_universe_sha256": value.rule_universe_sha256,
        }

    if canonical_json_bytes(projection(graph)) != canonical_json_bytes(
        projection(expected)
    ):
        raise EvidenceGraphError(
            "materialized graph differs from pinned registry/source replay"
        )


def load_validated_graph(
    root: Path,
    registry_path: Path,
    output_dir: Path,
) -> EvidenceGraph:
    """Load a materialized graph and replay every pinned source assertion."""
    graph = load_graph(output_dir)
    validate_graph_against_registry(root, registry_path, graph)
    return graph


def arm_rule_matrix(graph: EvidenceGraph, arm_id: str) -> list[dict[str, Any]]:
    nodes = graph.node_map()
    if arm_id not in nodes or nodes[arm_id]["kind"] != "arm":
        raise EvidenceGraphError(f"unknown arm: {arm_id}")
    rows = []
    for edge in graph.edges:
        if edge["kind"] == "RULE_APPLICATION" and edge["from"] == arm_id:
            rule = nodes[edge["to"]]
            rows.append({
                "application": edge["properties"]["application"],
                "baseline_operational": rule["baseline_operational"],
                "classification": rule["classification"],
                "effect": edge["properties"]["effect"],
                "label": rule["label"],
                "rule_id": rule["id"],
                "scope": edge["properties"]["scope"],
                "stage": rule["stage"],
            })
    return sorted(rows, key=lambda row: (row["stage"], row["rule_id"]))


def full_soft_removal(graph: EvidenceGraph, arm_id: str) -> dict[str, Any]:
    """Return a conservative removal screen; v1 cannot certify a positive."""
    nodes = graph.node_map()
    arm = nodes.get(arm_id)
    if not arm or arm["kind"] != "arm":
        raise EvidenceGraphError(f"unknown arm: {arm_id}")
    blockers: list[dict[str, Any]] = []
    removed: list[str] = []
    for row in arm_rule_matrix(graph, arm_id):
        if row["classification"] not in {"generation_recipe", "house_soft"}:
            continue
        if row["stage"] not in {"generation", "admission"}:
            continue
        scope = row["scope"]
        if row["baseline_operational"]:
            good = (
                row["effect"] == "removed"
                and row["application"] == "direct"
                and scope["fraction"] == 1
                and scope["candidate_path"] == "all"
            )
            if good:
                removed.append(row["rule_id"])
            else:
                blockers.append({
                    "effect": row["effect"],
                    "reason": "baseline-active rule is not removed on every path",
                    "rule_id": row["rule_id"],
                    "scope": scope,
                })
        elif row["effect"] not in {"nonoperative", "removed"}:
            blockers.append({
                "effect": row["effect"],
                "reason": "baseline-inactive house rule was activated",
                "rule_id": row["rule_id"],
                "scope": scope,
            })
    complete = bool(arm["properties"].get("curated_rule_coverage_complete"))
    independent_inventory_bound = False
    blockers.append({
        "reason": "v1 has no independent effective-policy rule inventory",
        "rule_id": None,
    })
    return {
        "arm_id": arm_id,
        "candidate_generation_only": True,
        "coverage_complete": complete,
        "curated_rule_coverage_complete": complete,
        "full_soft_removal": False,
        "independent_policy_rule_inventory_bound": independent_inventory_bound,
        "removed_rules": sorted(removed),
        "blockers": blockers,
        "selector_is_separate_rule": True,
    }


def measurements_for_arm(graph: EvidenceGraph, arm_id: str) -> list[dict[str, Any]]:
    nodes = graph.node_map()
    if arm_id not in nodes or nodes[arm_id]["kind"] != "arm":
        raise EvidenceGraphError(f"unknown arm: {arm_id}")
    measurement_ids = {
        edge["to"] for edge in graph.edges
        if edge["kind"] == "ARM_RESULT" and edge["from"] == arm_id
    }
    return [nodes[node_id] for node_id in sorted(measurement_ids)]


def effects_for_arm(graph: EvidenceGraph, arm_id: str) -> dict[str, Any]:
    """Return an arm's registered interventions and observed effects."""
    nodes = graph.node_map()
    arm = nodes.get(arm_id)
    if not arm or arm["kind"] != "arm":
        raise EvidenceGraphError(f"unknown arm: {arm_id}")
    parameter_changes = []
    for edge in graph.edges:
        if edge["kind"] == "SETS_PARAMETER" and edge["from"] == arm_id:
            parameter_changes.append({
                "control": edge["properties"]["control"],
                "parameter_id": edge["to"],
                "treatment": edge["properties"]["treatment"],
            })
    gate_ids = sorted({
        edge["to"] for edge in graph.edges
        if edge["kind"] == "EVALUATES_GATE" and edge["from"] == arm_id
    })
    license_sources = {arm_id, *gate_ids}
    license_ids = sorted({
        edge["to"] for edge in graph.edges
        if edge["kind"] == "DECIDES_LICENSE" and edge["from"] in license_sources
    })
    return {
        "arm_id": arm_id,
        "attribution_scope": arm["properties"].get(
            "attribution_scope", "not_registered"
        ),
        "decision_authority": False,
        "decision_authority_blocker": (
            "v1 lacks an independent effective-policy inventory and runtime receipt"
        ),
        "gates": [nodes[node_id] for node_id in gate_ids],
        "licenses": [nodes[node_id] for node_id in license_ids],
        "lifecycle": arm["properties"].get("lifecycle"),
        "measurements": measurements_for_arm(graph, arm_id),
        "parameter_binding_status": "source_bound",
        "parameter_changes": sorted(
            parameter_changes, key=lambda row: row["parameter_id"]
        ),
    }


def population_measurements(
    graph: EvidenceGraph,
    population_ids: Iterable[str],
) -> list[dict[str, Any]]:
    wanted = set(population_ids)
    nodes = graph.node_map()
    measurement_ids = {
        edge["from"] for edge in graph.edges
        if edge["kind"] == "OBSERVED_ON" and edge["to"] in wanted
    }
    return [nodes[node_id] for node_id in sorted(measurement_ids)]


def headline_context(graph: EvidenceGraph, measurement_id: str) -> dict[str, Any]:
    nodes = graph.node_map()
    node = nodes.get(measurement_id)
    if not node or node["kind"] != "measurement":
        raise EvidenceGraphError(f"unknown measurement: {measurement_id}")
    arm_ids = sorted({
        edge["from"] for edge in graph.edges
        if edge["kind"] == "ARM_RESULT" and edge["to"] == measurement_id
    })
    if len(arm_ids) != 1:
        raise EvidenceGraphError(
            f"headline measurement must belong to exactly one arm: {measurement_id}"
        )
    controls = sorted({
        edge["to"] for edge in graph.edges
        if edge["kind"] == "COMPARES_WITH" and edge["from"] == measurement_id
    })
    if len(controls) != 1:
        raise EvidenceGraphError(
            f"headline measurement must have exactly one comparator: {measurement_id}"
        )
    endpoints = sorted({
        edge["to"] for edge in graph.edges
        if edge["kind"] == "MEASURES" and edge["from"] == measurement_id
    })
    populations = sorted({
        edge["to"] for edge in graph.edges
        if edge["kind"] == "OBSERVED_ON" and edge["from"] == measurement_id
    })
    corpora = sorted({
        edge["to"] for edge in graph.edges
        if edge["kind"] == "USES_CORPUS" and edge["from"] in arm_ids
    })
    policies = sorted({
        edge["to"] for edge in graph.edges
        if edge["kind"] == "INHERITS_POLICY" and edge["from"] in arm_ids
    })
    selectors = sorted({
        edge["to"] for edge in graph.edges
        if edge["kind"] == "USES_SELECTOR" and edge["from"] in arm_ids
    })
    return {
        "arm_ids": arm_ids,
        "controls": controls,
        "corpora": corpora,
        "endpoints": endpoints,
        "measurement_id": measurement_id,
        "policies": policies,
        "populations": populations,
        "properties": node["properties"],
        "selectors": selectors,
    }


def baseline_compatibility(
    graph: EvidenceGraph,
    left_measurement_id: str,
    right_measurement_id: str,
) -> dict[str, Any]:
    left = headline_context(graph, left_measurement_id)
    right = headline_context(graph, right_measurement_id)
    fields = ("controls", "corpora", "endpoints", "policies", "selectors")
    differences = {
        field: {"left": left[field], "right": right[field]}
        for field in fields if left[field] != right[field]
    }
    for field in ("entry_count", "slate_count"):
        a, b = left["properties"].get(field), right["properties"].get(field)
        if not _same_type_value(a, b):
            differences[field] = {"left": a, "right": b}
    return {
        "compatible": not differences,
        "differences": differences,
        "left": left_measurement_id,
        "right": right_measurement_id,
        "treatment_populations": {
            "left": left["populations"],
            "right": right["populations"],
        },
    }


def decision_brief(graph: EvidenceGraph) -> dict[str, Any]:
    """Summarize tracked decisions without manufacturing a new license."""
    nodes = graph.node_map()
    arms = sorted(
        (row for row in graph.nodes if row["kind"] == "arm"),
        key=lambda row: row["id"],
    )
    completed = [
        arm for arm in arms
        if str(arm["properties"].get("lifecycle", "")).startswith("completed-")
    ]
    removal = [full_soft_removal(graph, arm["id"]) for arm in completed]
    arm_rows = []
    for arm in completed:
        measurements = measurements_for_arm(graph, arm["id"])
        arm_rows.append({
            "arm_id": arm["id"],
            "knowledge_class": arm["knowledge_class"],
            "lifecycle": arm["properties"]["lifecycle"],
            "measurements": [{
                "id": row["id"],
                "properties": row["properties"],
            } for row in measurements],
        })
    winner_ids = {
        edge["from"] for edge in graph.edges
        if edge["kind"] == "OBSERVED_ON"
        and edge["to"] == "population:milly-winners-2023-2025"
    }
    return {
        "completed_arm_count": len(completed),
        "completed_arms": arm_rows,
        "completed_full_soft_removal_arm_ids": sorted(
            row["arm_id"] for row in removal if row["full_soft_removal"]
        ),
        "graph_id": graph.graph_id,
        "historical_retry_licensed": False,
        "parameter_ids": sorted(
            node_id for node_id, node in nodes.items() if node["kind"] == "parameter"
        ),
        "production_change_licensed": False,
        "prospective_shadow_licensed": False,
        "rule_universe_sha256": graph.rule_universe_sha256,
        "winner_measurements": [{
            "id": node_id,
            "properties": nodes[node_id]["properties"],
        } for node_id in sorted(winner_ids)],
    }
