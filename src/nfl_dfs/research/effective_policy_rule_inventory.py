"""Independent, source-pinned inventory of the adopted Classic policy.

This module is intentionally independent of ``evidence_knowledge_graph`` and
of every graph bootstrap.  It derives the effective baseline from the adopted
production policy, checks the enforcing Python sources byte-for-byte, and
then emits a canonical closed-world inventory for the bounded policy scope.

The inventory is a *source* contract, not a runtime receipt.  A future runner
must still prove that its request-local effective policy equals these rows and
that forbidden ambient process variables are absent before it can claim a
legal-only treatment.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from hashlib import sha256
import inspect
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence


SCHEMA = "nfl-dfs-effective-policy-rule-inventory/v2"
SOURCE_SET_ID = "adopted-classic-policy-20260830-explicit-construction-v2"
POLICY_ENV_SHA256 = (
    "4ffdaf69b32fc719914a96654a56cfee3f99d78053cb6dc375f4f02232ad648b"
)
CLASSIFIED_INPUT_PROJECTION_SHA256 = (
    "d9906366eb4e5bfcc117608e255c506dcea10b33957afe6962802ee4d6231d98"
)
CLASSIFIED_INPUT_KEY_COUNT = 126
DIRECT_INPUT_READ_SITE_COUNT = 273

# These are production/enforcement sources and independent validation
# consumers, never evidence-graph-authored files.  Any byte drift requires a
# conscious inventory revision; silently continuing would reopen the closed
# world while claiming that it remained frozen.
FROZEN_SOURCE_SHA256: Mapping[str, str] = {
    "src/nfl_dfs/app/main.py": (
        "604bc24689aa10535855f6476c66e655043b3ab58f1fb216a490afa2321f44de"
    ),
    "src/nfl_dfs/backtest/engine.py": (
        "c0a8a4c2e66371dda475a0f85a27a900946afc35970687ba686c3a998e80133f"
    ),
    "src/nfl_dfs/backtest/replay.py": (
        "ecc7b00f25e031e9754f2731773e02b74b373afdbe22539666258bf0d3bf39a9"
    ),
    "src/nfl_dfs/inference/live_lineups.py": (
        "cc690d673c6bb5d25a57057b900b19bd608a53998b6ef8f3ecb9352f19d4a81f"
    ),
    "src/nfl_dfs/inference/multiseed_portfolio.py": (
        "692ee5ea13bdbf4e39bc5490808429c100c0779f817515f4d0ea452c604907d8"
    ),
    "src/nfl_dfs/inference/production_policy.py": (
        "88a1e00c681aad19d3ed9559fe890fd72b968a0260e6c9fcf36370964b744099"
    ),
    "src/nfl_dfs/models/game_sim.py": (
        "667e9a8823d976d192a78c5dadfd79be5c8f97c86269b134b03a9833adae3a7c"
    ),
    "src/nfl_dfs/models/simulate.py": (
        "850f33bca392e580a2e73b49aa01289d0404631c479606d67c4c227d42b7f47c"
    ),
    "src/nfl_dfs/optimizer/lineup.py": (
        "efb1e4a203da81d8677deb138e3487a399975177ca8ec42d98a093155b14be7f"
    ),
    "src/nfl_dfs/optimizer/construction_presets.py": (
        "dd107bc451a039e739508f0a759da1f6983f66bb4405d4eb36b4c61866213280"
    ),
    "src/nfl_dfs/research/final_forensic.py": (
        "05ab95d4238eb289a7b997892a56bd366a32a46e420e62bc4f594fcd5ad75468"
    ),
    "src/nfl_dfs/research/lr8_historical_arm.py": (
        "bddae8e3ac27387085544a8b7585f56384993313e38ed3ca472129ac24dd0510"
    ),
}

SOURCE_ROLES: Mapping[str, str] = {
    "src/nfl_dfs/app/main.py": "live_default_activation",
    "src/nfl_dfs/backtest/engine.py": "generation_and_selection_enforcement",
    "src/nfl_dfs/backtest/replay.py": "historical_default_activation",
    "src/nfl_dfs/inference/live_lineups.py": "live_policy_dispatch",
    "src/nfl_dfs/inference/multiseed_portfolio.py": "admission_enforcement",
    "src/nfl_dfs/inference/production_policy.py": "effective_configuration",
    "src/nfl_dfs/models/game_sim.py": "possession_law_enforcement",
    "src/nfl_dfs/models/simulate.py": "simulation_dispatch",
    "src/nfl_dfs/optimizer/lineup.py": "legality_and_soft_rule_enforcement",
    "src/nfl_dfs/optimizer/construction_presets.py": "named_construction_policy",
    "src/nfl_dfs/research/final_forensic.py": "independent_dk_only_validator",
    "src/nfl_dfs/research/lr8_historical_arm.py": (
        "independent_five_rule_relaxation_with_legacy_min_games"
    ),
}

# Only production/configuration/enforcement sources define the runtime input
# boundary.  The forensic and LR8 files are independent validation consumers:
# pinning them proves the DK-only seam, but their research CLI inputs are not
# permitted to enlarge the production input universe.
INPUT_SCAN_PATHS = frozenset({
    path for path, role in SOURCE_ROLES.items()
    # Independent validators/consumers are comparison authorities, not inputs
    # to the adopted policy.  Keep every independently named role out of the
    # production input scan, including the frozen LR8-v1 legacy-construction
    # consumer whose role name intentionally no longer says "dk_only".
    if not role.startswith("independent_")
})

INPUT_CLASSIFICATIONS = frozenset({
    "forbidden_ambient",
    "frozen_mechanism_input",
    "infrastructure_only",
    "typed_parametric_rule",
})

# An input key has exactly one semantic classification.  These mappings are
# deliberately explicit rather than defaulting unknown keys to "frozen":
# after a reviewed source-hash update, a newly read key must still be assigned
# here before an inventory can be emitted.
TYPED_PARAMETRIC_INPUT_RULES: Mapping[str, str] = {
    "FORBID_RB_DST": "rule:forbid-rb-vs-dst",
    "FORBID_TWO_RB_SAME_TEAM": "rule:forbid-two-rb-same-team",
    "MIN_LINEUP_SALARY": "rule:salary-floor-49000",
    "STACK_BRING_BACK": "rule:bring-back-min-one",
    "STACK_QB_MIN": "rule:qb-stack-min-two",
}
INFRASTRUCTURE_INPUT_KEYS = frozenset({
    "ANTHROPIC_API_KEY",
    "CAND_ARTIFACT_BUCKET",
    "CAND_ARTIFACT_PLAYER_WORLDS",
    "CAND_FEATURE_TABLE",
    "CAND_LOG_TABLE",
    "CODE_SHA",
    "GCP_PROJECT",
    "IMAGE_URI",
    "PANEL_RUN_ID",
    "PROSPECTIVE_SHADOW_ID",
    "REPLAY_LINEUPS_TABLE",
    "SEEDS",
})

# Filled from the reviewed AST projection below.  Do not collapse these into
# one "known keys" allowlist: the category itself is part of the contract.
FROZEN_MECHANISM_INPUT_KEYS = frozenset({
    "ARCHETYPE_ALLOCATION_VERSION",
    "ARCHETYPE_TAIL_LINE",
    "ATLAS_BOOM_WORLD_RANKING",
    "BLEND_MODEL_WEIGHT",
    "BOOM_UNIQUE_FILL",
    "CAND_MULT",
    "CE_GAMES",
    "CE_SEED",
    "CONSTRUCTION_PRESET_ID",
    "DST_CORR_DRAWS",
    "EMP_MARGINALS",
    "EMP_POS",
    "ENSEMBLE_WORLD_MODE",
    "ENSEMBLE_WORLD_SEED",
    "EPISTEMIC_FAMILY",
    "GAME_SIM_MODE",
    "GAME_SIM_PACE",
    "GAME_SIM_TEAM_FACTORS",
    "GAME_SIM_USAGE",
    "GEN_POOL_CAP",
    "GEN_POOL_CAP_MAP",
    "GEN_TOTAL_BUDGET",
    "GUMBEL_MODE",
    "GUMBEL_SCALE",
    "GUMBEL_SEED",
    "HYPER_BOOM",
    "LIVE_SIMS",
    "M4_QBLOCK",
    "MAX_PER_GAME",
    "MAX_OVERLAP",
    "MAX_QBS",
    "MIN_LOWOWN",
    "MIN_GAMES",
    "MODEL_ENSEMBLE",
    "MODEL_REGISTRY_VARIANT",
    "MULTISEED_CANDIDATE_ENTRY_BASIS",
    "MULTISEED_PORTFOLIO",
    "MULTISEED_SEED_PAIRS",
    "MULTISEED_SOURCE_LABEL",
    "MULTISEED_WORLDS_PER_BLOCK",
    "N_BOOM",
    "N_CE",
    "N_COVERAGE_TAIL",
    "N_DARKGAME",
    "N_EPISTEMIC",
    "N_GAMESTACK",
    "N_GUMBEL",
    "N_LEV",
    "N_LOWSAL",
    "N_MIDQB",
    "N_NOSTACK",
    "N_QB_VARIANTS",
    "N_ROUTE_TAIL",
    "OPEN_BOOM_SOLVES",
    "OWN_BARBELL",
    "OWN_BARBELL_HIGH",
    "OWN_BARBELL_LOW",
    "OWN_BARBELL_NHIGH",
    "OWN_BARBELL_NLOW",
    "OWN_MODEL",
    "PEAK_SLICE",
    "PUNT_BOOM",
    "PUNT_BOOM_WR",
    "PUNT_MAX",
    "PUNT_MIN",
    "PUNT_STRICT",
    "PROSPECTIVE_GENERATION_EXPOSURE",
    "Q99_WILD",
    "QD_CELLS",
    "REPLACEMENT_SLOTS",
    "REPLAY_PROJECTION_SEED",
    "ROLE_BELIEF_FEATURES",
    "ROLE_BELIEF_SEED",
    "ROOKIE_WIDEN",
    "SELECT_LADDER",
    "SELECT_LSE",
    "SELECT_OBJ",
    "SERVED_POSITION_SCALES",
    "SERVED_TAIL_SCALE",
    "SHAPE_MIX",
    "SIM_WIDEN_DRAWS",
    "SINGLE_STACK_BOOM_SOLVES",
    "SIS_ASOE_BETA",
    "SIS_ASOE_TARGET_ALLOCATION",
    "TABPFN_MARGINALS",
    "TABPFN_MARGINAL_TABLE",
    "TD_LEDGER",
    "TD_LEDGER_RANK_COUPLING",
    "VALUE2_MAX",
    "VALUE2_MIN",
    "WR_BOOM",
})
FORBIDDEN_AMBIENT_INPUT_KEYS = frozenset({
    "ALT_CEIL",
    "BIGPLAY",
    "DIRICHLET_K",
    "DIV_TILT",
    "DST_PUNT_BONUS",
    "EPISTEMIC_W",
    "EXTRA_FEATURES",
    "LEV_PENALTY",
    "LEV_POS_WEIGHTS",
    "LEV_SHAPE",
    "PUNT_SLOPE",
    "PUNT_VALUE",
    "SCHAAKE_DIAG",
    "SCHAAKE_DIAG_ONLY",
    "SCHAAKE_DIAG_STRICT",
    "SCRIPT_FEEDBACK",
    "TABPFN_COMPONENTS",
    "TABPFN_MEAN",
})

CLASSIFICATIONS = frozenset({
    "admission_recipe",
    "dk_hard",
    "generation_recipe",
    "house_soft",
    "selector",
    "simulation_law",
})
STAGES = frozenset({"admission", "generation", "selection", "simulation"})
BASELINE_STATES = frozenset({"active", "inactive"})
PATH_RE = re.compile(r"^[a-z][a-z0-9-]*(?::[a-z][a-z0-9-]*)*$")
ID_RE = re.compile(r"^rule:[a-z][a-z0-9-]*$")

ALL_GENERATION = "generation:all"
LEV = "generation:leverage"
BOOM = "generation:boom"
ROLE = "generation:role"
QBVAR = "generation:qb-variant"
GAME = "generation:projected-game"
DARK = "generation:dark-game"
ADMISSION = "admission:preselection"
CBWU = "admission:cbwu"
SIMULATION = "simulation:production"
SELECTION = "selection:exact-80"
ACTIVE_GENERATION_PATHS = (LEV, BOOM, ROLE, QBVAR, GAME, DARK)

PARAMETRIC_FIELDS: Mapping[str, tuple[str, Any, tuple[Any, ...]]] = {
    "bring_back_min": ("rule:bring-back-min-one", 1, (0, 1)),
    "forbid_rb_vs_dst": ("rule:forbid-rb-vs-dst", True, (False, True)),
    "forbid_two_rb_same_team": (
        "rule:forbid-two-rb-same-team", True, (False, True),
    ),
    "min_lineup_salary": ("rule:salary-floor-49000", 49_000, (0, 49_000)),
    "qb_stack_min": ("rule:qb-stack-min-two", 2, (0, 2)),
}

# Every optional feasibility parameter in StackRules and the shared optimizer
# seam is assigned to at least one independent rule row.  Additions to either
# surface fail the AST checks below before an inventory can be emitted.
STACK_FIELD_RULES: Mapping[str, tuple[str, ...]] = {
    "bring_back_max": ("rule:bring-back-maximum",),
    "bring_back_min": ("rule:bring-back-min-one",),
    "forbid_rb_vs_dst": ("rule:forbid-rb-vs-dst",),
    "forbid_two_rb_same_team": ("rule:forbid-two-rb-same-team",),
    "qb_stack_max": ("rule:qb-stack-maximum",),
    "qb_stack_min": ("rule:qb-stack-min-two",),
    "require_rb_vs_dst": ("rule:require-rb-vs-dst",),
    "require_two_rb_same_team": ("rule:require-two-rb-same-team",),
}
SHARED_CONSTRAINT_PARAMETER_RULES: Mapping[str, tuple[str, ...]] = {
    "banned_lineups": (
        "rule:leverage-overlap-seven",
        "rule:qbvar-overlap-six",
        "rule:game-overlap-seven",
    ),
    "bans": ("rule:player-bans",),
    "budget": ("rule:dk-salary-cap-50000",),
    "env": (
        "rule:salary-floor-49000",
        "rule:punt-minimum",
        "rule:value-two-minimum",
        "rule:ownership-barbell-low",
        "rule:ownership-barbell-high",
        "rule:max-per-game-cap",
        "rule:min-two-games",
        "rule:min-low-ownership",
    ),
    "game_lock": ("rule:game-lock-min-five",),
    "locks": ("rule:player-locks",),
    "max_overlap": (
        "rule:leverage-overlap-seven",
        "rule:qbvar-overlap-six",
        "rule:game-overlap-seven",
    ),
    "max_per_game": ("rule:max-per-game-cap",),
    "min_games": ("rule:min-two-games",),
    "max_salary": ("rule:maximum-salary",),
    "min_salary": ("rule:salary-floor-49000",),
    "players": (
        "rule:dk-position-shape",
        "rule:dk-team-cap-eight",
    ),
    "prob": ("rule:dk-roster-size-nine",),
    "punt_max_salary": ("rule:punt-minimum",),
    "punt_min": ("rule:punt-minimum",),
    "stack": tuple(sorted({
        rule_id for rule_ids in STACK_FIELD_RULES.values() for rule_id in rule_ids
    })),
    "x": ("rule:dk-roster-size-nine",),
}
OPTIMIZE_ONLY_CONSTRAINT_RULES: Mapping[str, tuple[str, ...]] = {
    "interaction_floor": ("rule:interaction-floor",),
    "interaction_floor_weights": ("rule:interaction-floor",),
    "objective_floor": ("rule:objective-floor",),
    "objective_floor_col": ("rule:objective-floor",),
}

CONSTRAINT_ENV_KEYS = frozenset({
    "MIN_GAMES",
    "MAX_PER_GAME",
    "MIN_LINEUP_SALARY",
    "MIN_LOWOWN",
    "OWN_BARBELL",
    "OWN_BARBELL_HIGH",
    "OWN_BARBELL_LOW",
    "OWN_BARBELL_NHIGH",
    "OWN_BARBELL_NLOW",
    "PUNT_STRICT",
    "VALUE2_MAX",
    "VALUE2_MIN",
})

# These experimental process-global switches are outside the adopted policy.
# A legal runtime receipt must prove all of them absent.  Approved mechanisms
# with an ambient fallback are classified separately, but their per-row
# ambient requirement is also absence so a request-local map cannot be
# bypassed.
FORBIDDEN_AMBIENT_KEYS = tuple(sorted(FORBIDDEN_AMBIENT_INPUT_KEYS))


class EffectivePolicyInventoryError(ValueError):
    """Raised when a source, policy value, or inventory invariant drifts."""


@dataclass(frozen=True)
class _Locator:
    path: str
    symbol: str


@dataclass(frozen=True)
class _Rule:
    id: str
    label: str
    classification: str
    stage: str
    baseline_state: str
    default_dose: Any
    normalized_paths: tuple[str, ...]
    locators: tuple[_Locator, ...]
    optional: bool = False
    parametric_field: str | None = None


@dataclass(frozen=True)
class _InputRead:
    access: str
    column: int
    input_key: str
    line: int
    path: str
    receiver_provenance: tuple[str, ...]
    scope: str


def canonical_json_bytes(value: Any) -> bytes:
    """Canonical JSON with type-sensitive, non-finite-safe encoding."""
    try:
        return (json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ) + "\n").encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise EffectivePolicyInventoryError(
            "inventory value is not canonical JSON"
        ) from exc


def canonical_sha256(value: Any) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _strict_same(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            _strict_same(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _strict_same(a, b) for a, b in zip(left, right, strict=True)
        )
    return left == right


def _source_path(root: Path, relative: str) -> Path:
    if Path(relative).is_absolute() or Path(relative).as_posix() != relative:
        raise EffectivePolicyInventoryError("source path is not normalized")
    resolved_root = root.resolve()
    resolved = (root / relative).resolve()
    if resolved_root not in resolved.parents:
        raise EffectivePolicyInventoryError("source path escapes repository root")
    if not resolved.is_file():
        raise EffectivePolicyInventoryError(f"source is absent: {relative}")
    return resolved


def _load_sources(
    root: Path,
) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, ast.Module]]:
    identities: list[dict[str, Any]] = []
    text_by_path: dict[str, str] = {}
    tree_by_path: dict[str, ast.Module] = {}
    if set(FROZEN_SOURCE_SHA256) != set(SOURCE_ROLES):
        raise EffectivePolicyInventoryError("source role coverage differs")
    for relative in sorted(FROZEN_SOURCE_SHA256):
        path = _source_path(root, relative)
        body = path.read_bytes()
        digest = sha256(body).hexdigest()
        if digest != FROZEN_SOURCE_SHA256[relative]:
            raise EffectivePolicyInventoryError(
                f"frozen source SHA-256 differs: {relative}"
            )
        try:
            text = body.decode("utf-8")
            tree = ast.parse(text, filename=relative)
        except (UnicodeDecodeError, SyntaxError) as exc:
            raise EffectivePolicyInventoryError(
                f"frozen source is not valid UTF-8 Python: {relative}"
            ) from exc
        identities.append({
            "bytes": len(body),
            "path": relative,
            "role": SOURCE_ROLES[relative],
            "sha256": digest,
        })
        text_by_path[relative] = text
        tree_by_path[relative] = tree
    return identities, text_by_path, tree_by_path


def _top_level_node(tree: ast.Module, kind: type[ast.AST], name: str) -> ast.AST:
    matches = [
        node for node in tree.body
        if isinstance(node, kind) and getattr(node, "name", None) == name
    ]
    if len(matches) != 1:
        raise EffectivePolicyInventoryError(
            f"source symbol cardinality differs: {kind.__name__}:{name}"
        )
    return matches[0]


def _class_node(tree: ast.Module, name: str) -> ast.ClassDef:
    return _top_level_node(tree, ast.ClassDef, name)  # type: ignore[return-value]


def _function_node(tree: ast.Module, name: str) -> ast.FunctionDef:
    return _top_level_node(tree, ast.FunctionDef, name)  # type: ignore[return-value]


def _validate_symbol(tree: ast.Module, symbol: str) -> None:
    tokens = symbol.split(":")
    if len(tokens) == 2 and tokens[0] == "module":
        name = tokens[1]
        matches = [
            node for node in tree.body
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            and (
                isinstance(getattr(node, "target", None), ast.Name)
                and node.target.id == name
                or isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == name
                        for target in node.targets)
            )
        ]
        if len(matches) != 1:
            raise EffectivePolicyInventoryError(
                f"module locator cardinality differs: {symbol}"
            )
        return
    if len(tokens) == 2 and tokens[0] == "function":
        _function_node(tree, tokens[1])
        return
    if len(tokens) == 4 and tokens[0] == "function" and tokens[2] == "parameter":
        function = _function_node(tree, tokens[1])
        parameters = {
            arg.arg for arg in (
                *function.args.posonlyargs,
                *function.args.args,
                *function.args.kwonlyargs,
            )
        }
        if tokens[3] not in parameters:
            raise EffectivePolicyInventoryError(
                f"function parameter locator is absent: {symbol}"
            )
        return
    if len(tokens) == 4 and tokens[0] == "class" and tokens[2] == "field":
        cls = _class_node(tree, tokens[1])
        matches = [
            node for node in cls.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == tokens[3]
        ]
        if len(matches) != 1:
            raise EffectivePolicyInventoryError(
                f"class field locator cardinality differs: {symbol}"
            )
        return
    if len(tokens) == 4 and tokens[0] == "class" and tokens[2] == "method":
        cls = _class_node(tree, tokens[1])
        matches = [
            node for node in cls.body
            if isinstance(node, ast.FunctionDef) and node.name == tokens[3]
        ]
        if len(matches) != 1:
            raise EffectivePolicyInventoryError(
                f"class method locator cardinality differs: {symbol}"
            )
        return
    raise EffectivePolicyInventoryError(f"unsupported source locator: {symbol}")


def _literal_class_field(tree: ast.Module, class_name: str, field: str) -> Any:
    cls = _class_node(tree, class_name)
    matches = [
        node for node in cls.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == field
    ]
    if len(matches) != 1 or matches[0].value is None:
        raise EffectivePolicyInventoryError(
            f"class field default cardinality differs: {class_name}.{field}"
        )
    try:
        return ast.literal_eval(matches[0].value)
    except (ValueError, TypeError) as exc:
        raise EffectivePolicyInventoryError(
            f"class field default is not literal: {class_name}.{field}"
        ) from exc


def _function_parameter_names(tree: ast.Module, name: str) -> tuple[str, ...]:
    function = _function_node(tree, name)
    return tuple(arg.arg for arg in (
        *function.args.posonlyargs,
        *function.args.args,
        *function.args.kwonlyargs,
    ))


def _mapping_get_keys(
    function: ast.FunctionDef,
    *,
    receiver_names: frozenset[str] | None = None,
) -> frozenset[str]:
    keys: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "get" or not node.args:
            continue
        if receiver_names is not None and (
            not isinstance(node.func.value, ast.Name)
            or node.func.value.id not in receiver_names
        ):
            continue
        key = node.args[0]
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            keys.add(key.value)
    return frozenset(keys)


_INPUT_PARAMETER_NAMES = frozenset({"base", "env", "policy_env", "runtime_env"})
_INPUT_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _scope_nodes(body: Sequence[ast.stmt]) -> tuple[ast.AST, ...]:
    """Walk one lexical scope without leaking reads from nested scopes."""
    output: list[ast.AST] = []
    stack: list[ast.AST] = list(reversed(body))
    while stack:
        node = stack.pop()
        output.append(node)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.Lambda)):
            continue
        stack.extend(reversed(tuple(ast.iter_child_nodes(node))))
    return tuple(output)


def _literal_string_set(
    node: ast.AST | None,
    bindings: Mapping[str, frozenset[str]],
) -> frozenset[str] | None:
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return frozenset({node.value})
    if isinstance(node, ast.Name):
        return bindings.get(node.id)
    if isinstance(node, (ast.List, ast.Set, ast.Tuple)):
        values: set[str] = set()
        for element in node.elts:
            resolved = _literal_string_set(element, bindings)
            if resolved is None:
                return None
            values.update(resolved)
        return frozenset(values)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"frozenset", "set", "tuple"}
        and len(node.args) == 1
        and not node.keywords
    ):
        return _literal_string_set(node.args[0], bindings)
    return None


def _string_bindings(
    nodes: Sequence[ast.AST],
    inherited: Mapping[str, frozenset[str]] | None = None,
) -> dict[str, frozenset[str]]:
    bindings = dict(inherited or {})
    changed = True
    while changed:
        changed = False
        for node in nodes:
            target: ast.AST | None = None
            value: ast.AST | None = None
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target, value = node.targets[0], node.value
            elif isinstance(node, ast.AnnAssign):
                target, value = node.target, node.value
            if isinstance(target, ast.Name):
                resolved = _literal_string_set(value, bindings)
                combined = bindings.get(target.id, frozenset()) | (
                    resolved or frozenset()
                )
                if resolved is not None and bindings.get(target.id) != combined:
                    bindings[target.id] = combined
                    changed = True
            iterator: ast.AST | None = None
            loop_target: ast.AST | None = None
            if isinstance(node, (ast.For, ast.AsyncFor)):
                loop_target, iterator = node.target, node.iter
            elif isinstance(node, ast.comprehension):
                loop_target, iterator = node.target, node.iter
            if isinstance(loop_target, ast.Name):
                resolved = _literal_string_set(iterator, bindings)
                combined = bindings.get(loop_target.id, frozenset()) | (
                    resolved or frozenset()
                )
                if resolved is not None and bindings.get(loop_target.id) != combined:
                    bindings[loop_target.id] = combined
                    changed = True
    return bindings


def _os_names(tree: ast.Module) -> tuple[frozenset[str], frozenset[str]]:
    modules = {"os"}
    environs: set[str] = set()
    # Local imports are common in the replay/engine hot paths; their aliases
    # are still direct process-global seams and must not escape discovery.
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "os":
                    modules.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "os":
            for alias in node.names:
                if alias.name == "environ":
                    environs.add(alias.asname or alias.name)
    return frozenset(modules), frozenset(environs)


def _is_imported_os_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "__import__"
        and len(node.args) >= 1
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "os"
    )


def _is_process_environment(
    node: ast.AST,
    *,
    os_modules: frozenset[str],
    environ_names: frozenset[str],
) -> bool:
    if isinstance(node, ast.Name) and node.id in environ_names:
        return True
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "environ"
        and (
            isinstance(node.value, ast.Name)
            and node.value.id in os_modules
            or _is_imported_os_call(node.value)
        )
    )


def _expression_input_provenance(
    node: ast.AST | None,
    aliases: Mapping[str, frozenset[str]],
    *,
    os_modules: frozenset[str],
    environ_names: frozenset[str],
) -> frozenset[str]:
    if node is None:
        return frozenset()
    if _is_process_environment(
        node, os_modules=os_modules, environ_names=environ_names
    ):
        return frozenset({"ambient_process"})
    if isinstance(node, ast.Name) and node.id in aliases:
        return aliases[node.id]
    # Only expressions that preserve a mapping may create another receiver.
    # A scalar derived from ``env.get(...)`` must not become an alias merely
    # because its expression contains the original mapping.
    branches: Sequence[ast.AST] = ()
    if isinstance(node, ast.IfExp):
        branches = (node.body, node.orelse)
    elif isinstance(node, ast.BoolOp):
        branches = tuple(node.values)
    elif (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "dict"
        and len(node.args) == 1
    ):
        branches = (node.args[0],)
    elif (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "copy"
        and not node.args
    ):
        branches = (node.func.value,)
    elif (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr.endswith("environment")
    ):
        branches = tuple(node.args)
    provenance: set[str] = set()
    for branch in branches:
        provenance.update(_expression_input_provenance(
            branch,
            aliases,
            os_modules=os_modules,
            environ_names=environ_names,
        ))
    return frozenset(provenance)


def _input_aliases(
    scope: ast.Module | ast.FunctionDef | ast.AsyncFunctionDef,
    nodes: Sequence[ast.AST],
    *,
    os_modules: frozenset[str],
    environ_names: frozenset[str],
    inherited: Mapping[str, frozenset[str]] | None = None,
) -> dict[str, frozenset[str]]:
    aliases: dict[str, frozenset[str]] = dict(inherited or {})
    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
        parameters = (
            *scope.args.posonlyargs,
            *scope.args.args,
            *scope.args.kwonlyargs,
        )
        for parameter in parameters:
            if parameter.arg in _INPUT_PARAMETER_NAMES:
                aliases[parameter.arg] = frozenset({"request_mapping"})
    changed = True
    while changed:
        changed = False
        for node in nodes:
            targets: tuple[ast.AST, ...] = ()
            value: ast.AST | None = None
            if isinstance(node, ast.Assign):
                targets, value = tuple(node.targets), node.value
            elif isinstance(node, ast.AnnAssign):
                targets, value = (node.target,), node.value
            elif isinstance(node, ast.NamedExpr):
                targets, value = (node.target,), node.value
            if value is None:
                continue
            provenance = _expression_input_provenance(
                value,
                aliases,
                os_modules=os_modules,
                environ_names=environ_names,
            )
            if not provenance:
                continue
            for target in targets:
                if isinstance(target, ast.Name):
                    combined = aliases.get(target.id, frozenset()) | provenance
                    if aliases.get(target.id) != combined:
                        aliases[target.id] = combined
                        changed = True
    return aliases


def _receiver_provenance(
    receiver: ast.AST,
    aliases: Mapping[str, frozenset[str]],
    *,
    os_modules: frozenset[str],
    environ_names: frozenset[str],
) -> frozenset[str]:
    if _is_process_environment(
        receiver, os_modules=os_modules, environ_names=environ_names
    ):
        return frozenset({"ambient_process"})
    if isinstance(receiver, ast.Name):
        return aliases.get(receiver.id, frozenset())
    return frozenset()


def _discover_scope_input_reads(
    *,
    path: str,
    scope_label: str,
    scope: ast.Module | ast.FunctionDef | ast.AsyncFunctionDef,
    nodes: Sequence[ast.AST],
    inherited_bindings: Mapping[str, frozenset[str]],
    os_modules: frozenset[str],
    environ_names: frozenset[str],
    inherited_aliases: Mapping[str, frozenset[str]] | None = None,
) -> tuple[_InputRead, ...]:
    bindings = _string_bindings(nodes, inherited_bindings)
    aliases = _input_aliases(
        scope,
        nodes,
        os_modules=os_modules,
        environ_names=environ_names,
        inherited=inherited_aliases,
    )
    reads: set[_InputRead] = set()

    def add(
        node: ast.AST,
        *,
        key_node: ast.AST,
        receiver: ast.AST,
        access: str,
    ) -> None:
        provenance = _receiver_provenance(
            receiver,
            aliases,
            os_modules=os_modules,
            environ_names=environ_names,
        )
        if not provenance:
            return
        keys = _literal_string_set(key_node, bindings)
        if keys is None:
            raise EffectivePolicyInventoryError(
                f"unresolved direct input key: {path}:{getattr(node, 'lineno', 0)}"
            )
        for key in keys:
            if not _INPUT_KEY_RE.fullmatch(key):
                raise EffectivePolicyInventoryError(
                    f"noncanonical direct input key: {path}:{key}"
                )
            reads.add(_InputRead(
                access=access,
                column=int(getattr(node, "col_offset", 0)),
                input_key=key,
                line=int(getattr(node, "lineno", 0)),
                path=path,
                receiver_provenance=tuple(sorted(provenance)),
                scope=scope_label,
            ))

    for node in nodes:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            receiver = node.func.value
            if node.func.attr in {"get", "pop"} and node.args:
                add(
                    node,
                    key_node=node.args[0],
                    receiver=receiver,
                    access=f"mapping_{node.func.attr}",
                )
            elif (
                node.func.attr == "getenv"
                and isinstance(receiver, ast.Name)
                and receiver.id in os_modules
                and node.args
            ):
                # Normalize ``os.getenv`` to the same process mapping seam.
                synthetic = ast.Attribute(value=receiver, attr="environ")
                add(
                    node,
                    key_node=node.args[0],
                    receiver=synthetic,
                    access="mapping_get",
                )
        elif isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load):
            add(
                node,
                key_node=node.slice,
                receiver=node.value,
                access="mapping_subscript",
            )
        elif isinstance(node, ast.Compare):
            left = node.left
            for operator, comparator in zip(
                node.ops, node.comparators, strict=True
            ):
                if isinstance(operator, (ast.In, ast.NotIn)):
                    add(
                        node,
                        key_node=left,
                        receiver=comparator,
                        access=("mapping_contains" if isinstance(operator, ast.In)
                                else "mapping_not_contains"),
                    )
                left = comparator
    return tuple(sorted(
        reads,
        key=lambda row: (
            row.path,
            row.line,
            row.column,
            row.input_key,
            row.access,
            row.receiver_provenance,
        ),
    ))


def _discover_direct_input_reads(
    tree_by_path: Mapping[str, ast.Module],
) -> tuple[_InputRead, ...]:
    reads: list[_InputRead] = []
    for path in sorted(INPUT_SCAN_PATHS):
        tree = tree_by_path[path]
        os_modules, environ_names = _os_names(tree)
        module_bindings = _string_bindings(_scope_nodes(tree.body))

        def scan_scope(
            scope: ast.Module | ast.FunctionDef | ast.AsyncFunctionDef,
            *,
            scope_label: str,
            inherited_bindings: Mapping[str, frozenset[str]],
            inherited_aliases: Mapping[str, frozenset[str]],
        ) -> None:
            nodes = _scope_nodes(scope.body)
            bindings = _string_bindings(nodes, inherited_bindings)
            aliases = _input_aliases(
                scope,
                nodes,
                os_modules=os_modules,
                environ_names=environ_names,
                inherited=inherited_aliases,
            )
            reads.extend(_discover_scope_input_reads(
                path=path,
                scope_label=scope_label,
                scope=scope,
                nodes=nodes,
                inherited_bindings=bindings,
                os_modules=os_modules,
                environ_names=environ_names,
                inherited_aliases=inherited_aliases,
            ))
            for child in nodes:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    scan_scope(
                        child,
                        scope_label=f"{scope_label}.function:{child.name}",
                        inherited_bindings=bindings,
                        inherited_aliases=aliases,
                    )
                elif isinstance(child, ast.ClassDef):
                    class_module = ast.Module(
                        body=child.body,
                        type_ignores=[],
                    )
                    scan_scope(
                        class_module,
                        scope_label=f"{scope_label}.class:{child.name}",
                        inherited_bindings=bindings,
                        inherited_aliases=aliases,
                    )

        scan_scope(
            tree,
            scope_label="module",
            inherited_bindings=module_bindings,
            inherited_aliases={},
        )
    unique = set(reads)
    if len(unique) != len(reads):
        raise EffectivePolicyInventoryError("direct input read sites overlap")
    return tuple(sorted(
        unique,
        key=lambda row: (
            row.path,
            row.line,
            row.column,
            row.input_key,
            row.access,
            row.receiver_provenance,
        ),
    ))


def _input_classification_by_key() -> dict[str, str]:
    groups: Mapping[str, frozenset[str]] = {
        "forbidden_ambient": FORBIDDEN_AMBIENT_INPUT_KEYS,
        "frozen_mechanism_input": FROZEN_MECHANISM_INPUT_KEYS,
        "infrastructure_only": INFRASTRUCTURE_INPUT_KEYS,
        "typed_parametric_rule": frozenset(TYPED_PARAMETRIC_INPUT_RULES),
    }
    if set(groups) != set(INPUT_CLASSIFICATIONS):
        raise EffectivePolicyInventoryError("input classification names differ")
    seen: dict[str, str] = {}
    for classification, keys in groups.items():
        for key in keys:
            previous = seen.get(key)
            if previous is not None:
                raise EffectivePolicyInventoryError(
                    f"input key has multiple classifications: {key}"
                )
            seen[key] = classification
    return seen


def _typed_input_metadata(input_key: str) -> dict[str, Any]:
    rule_id = TYPED_PARAMETRIC_INPUT_RULES[input_key]
    matches = [
        (field, baseline)
        for field, (candidate_rule_id, baseline, _) in PARAMETRIC_FIELDS.items()
        if candidate_rule_id == rule_id
    ]
    if len(matches) != 1:
        raise EffectivePolicyInventoryError(
            f"typed input does not bind one parametric field: {input_key}"
        )
    field, baseline = matches[0]
    return {
        "baseline_dose": baseline,
        "parametric_field": field,
        "rule_id": rule_id,
    }


def _classified_input_projection(
    *,
    env: Mapping[str, str],
    reads: Sequence[_InputRead],
    source_by_path: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    classification_by_key = _input_classification_by_key()
    discovered_keys = {read.input_key for read in reads}
    input_universe = discovered_keys | set(env)
    classified_keys = set(classification_by_key)
    if input_universe != classified_keys:
        missing = sorted(input_universe - classified_keys)
        stale = sorted(classified_keys - input_universe)
        raise EffectivePolicyInventoryError(
            "input classification partition differs; "
            f"unclassified={missing}, stale={stale}"
        )
    if len(reads) != DIRECT_INPUT_READ_SITE_COUNT:
        raise EffectivePolicyInventoryError(
            "direct input read-site count differs"
        )

    sites_by_key: dict[str, list[dict[str, Any]]] = {
        key: [] for key in sorted(input_universe)
    }
    for read in reads:
        if read.path not in source_by_path:
            raise EffectivePolicyInventoryError(
                f"input read source is not pinned: {read.path}"
            )
        sites_by_key[read.input_key].append({
            "access": read.access,
            "classification": classification_by_key[read.input_key],
            "column": read.column,
            "line": read.line,
            "path": read.path,
            "receiver_provenance": list(read.receiver_provenance),
            "scope": read.scope,
            "source_sha256": source_by_path[read.path]["sha256"],
        })

    inputs: list[dict[str, Any]] = []
    ambient_absence: list[str] = []
    for input_key in sorted(input_universe):
        classification = classification_by_key[input_key]
        sites = sites_by_key[input_key]
        has_ambient_read = any(
            "ambient_process" in site["receiver_provenance"] for site in sites
        )
        if classification == "infrastructure_only":
            mapping_requirement: dict[str, Any] = {
                "state": "optional_passthrough_or_absent",
            }
            ambient_requirement = (
                "infrastructure_passthrough_or_absent"
                if has_ambient_read else "not_directly_read"
            )
        else:
            mapping_requirement = (
                {"state": "present", "value": env[input_key]}
                if input_key in env else {"state": "absent"}
            )
            ambient_requirement = (
                "absent" if has_ambient_read else "not_directly_read"
            )
            if has_ambient_read:
                ambient_absence.append(input_key)
        row: dict[str, Any] = {
            "ambient_process_requirement": ambient_requirement,
            "baseline_effective_policy": (
                {"state": "present", "value": env[input_key]}
                if input_key in env else {"state": "absent"}
            ),
            "classification": classification,
            "direct_read_site_count": len(sites),
            "direct_read_sites": sites,
            "direct_read_sites_sha256": canonical_sha256(sites),
            "input_key": input_key,
            "request_mapping_requirement": mapping_requirement,
        }
        if classification == "typed_parametric_rule":
            row.update(_typed_input_metadata(input_key))
        inputs.append(row)

    counts = {
        classification: sum(
            row["classification"] == classification for row in inputs
        )
        for classification in sorted(INPUT_CLASSIFICATIONS)
    }
    projection = {
        "ambient_process_keys_requiring_absence": ambient_absence,
        "classification_counts": counts,
        "direct_input_read_site_count": len(reads),
        "input_count": len(inputs),
        "input_keys_sha256": canonical_sha256(
            [row["input_key"] for row in inputs]
        ),
        "inputs": inputs,
    }
    if projection["input_count"] != CLASSIFIED_INPUT_KEY_COUNT:
        raise EffectivePolicyInventoryError("classified input-key count differs")
    return projection


def _require_once(text: str, needle: str, *, label: str) -> None:
    count = text.count(needle)
    if count != 1:
        raise EffectivePolicyInventoryError(
            f"{label} source assertion cardinality differs: {count}"
        )


def _assert_independent_soft_rule_proofs(text_by_path: Mapping[str, str]) -> None:
    lineup = text_by_path["src/nfl_dfs/optimizer/lineup.py"]
    replay = text_by_path["src/nfl_dfs/backtest/replay.py"]
    app = text_by_path["src/nfl_dfs/app/main.py"]
    presets = text_by_path[
        "src/nfl_dfs/optimizer/construction_presets.py"
    ]
    forensic = text_by_path["src/nfl_dfs/research/final_forensic.py"]
    lr8 = text_by_path["src/nfl_dfs/research/lr8_historical_arm.py"]

    # Baseline activation is centralized in the named incumbent preset;
    # replay and live select that base explicitly and receipt effective
    # overrides. Bare StackRules and omitted optimizer env remain neutral.
    for needle, label in (
        ("qb_stack_min=2,", "incumbent QB stack"),
        ("bring_back_min=1,", "incumbent bring-back"),
        ("forbid_rb_vs_dst=True,", "incumbent RB-vs-DST"),
        ("forbid_two_rb_same_team=True,", "incumbent same-team RB"),
        ("min_salary=49_000,", "incumbent salary floor"),
        ("min_games=2,", "incumbent game diversity"),
    ):
        _require_once(presets, needle, label=label)
    for needle, label in (
        ("construction_preset_id: str = Field(", "live named preset"),
        ("qb_stack_min: int | None = Field(None", "live QB override"),
        ("bring_back_min: int | None = Field(None", "live bring-back override"),
        ("forbid_rb_vs_dst: bool | None = None", "live RB-vs-DST override"),
    ):
        _require_once(app, needle, label=label)
    _require_once(
        replay, '"CONSTRUCTION_PRESET_ID", INCUMBENT_GPP_PRESET_ID',
        label="replay named preset",
    )

    # The true DK-only forensic consumer and the separately maintained LR8-v1
    # consumer both remove the complete five-field surface. LR8-v1 retains its
    # historical two-game construction and is not represented as DK-only.
    for needle, label in (
        ("min_salary=0,", "forensic DK-only salary"),
        ("min_games=1,", "forensic DK-only game diversity"),
        ("qb_stack_min=0,", "forensic DK-only QB stack"),
        ("bring_back_min=0,", "forensic DK-only bring-back"),
        ("forbid_two_rb_same_team=False,", "forensic DK-only same-team RB"),
        ("forbid_rb_vs_dst=False,", "forensic DK-only RB-vs-DST"),
    ):
        # Some tokens also occur in other forensic calls; bind the named
        # function body rather than requiring file-wide uniqueness below.
        if needle not in forensic[
            forensic.index("def solve_draftkings_legal_oracle("):
            forensic.index("def recourse_ceiling_slate(")
        ]:
            raise EffectivePolicyInventoryError(f"{label} proof is absent")
    lr8_body = lr8[
        lr8.index("def build_dk_classic_model("):
        lr8.index("def lineup_anatomy(")
    ]
    for needle, label in (
        ("stack=None,", "LR8 DK-only stack"),
        ("min_salary=0,", "LR8 DK-only salary"),
        ("punt_min=0,", "LR8 DK-only punt"),
        ("max_per_game=0,", "LR8 DK-only game cap"),
        ("min_games=rw.MIN_GAMES,", "LR8-v1 legacy game diversity"),
        ("env={},", "LR8 DK-only environment"),
    ):
        if needle not in lr8_body:
            raise EffectivePolicyInventoryError(f"{label} proof is absent")


def _assert_surface_coverage(
    tree_by_path: Mapping[str, ast.Module],
) -> None:
    lineup_tree = tree_by_path["src/nfl_dfs/optimizer/lineup.py"]
    stack_class = _class_node(lineup_tree, "StackRules")
    stack_fields = {
        node.target.id for node in stack_class.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    if stack_fields != set(STACK_FIELD_RULES):
        raise EffectivePolicyInventoryError(
            "StackRules field inventory differs; classify every field explicitly"
        )

    shared = set(_function_parameter_names(
        lineup_tree, "add_classic_lineup_constraints"
    ))
    if shared != set(SHARED_CONSTRAINT_PARAMETER_RULES):
        raise EffectivePolicyInventoryError(
            "shared constraint parameter inventory differs"
        )
    optimizer = set(_function_parameter_names(lineup_tree, "optimize"))
    if not set(OPTIMIZE_ONLY_CONSTRAINT_RULES) <= optimizer:
        raise EffectivePolicyInventoryError(
            "optimizer-only constraint parameter inventory differs"
        )
    env_keys = _mapping_get_keys(
        _function_node(lineup_tree, "add_classic_lineup_constraints"),
        receiver_names=frozenset({"_env"}),
    )
    if env_keys != CONSTRAINT_ENV_KEYS:
        raise EffectivePolicyInventoryError(
            "shared constraint environment-key inventory differs"
        )


def _effective_policy(root: Path) -> tuple[dict[str, str], dict[str, Any]]:
    # Import only after all source hashes have passed.  This module is cheap
    # and offline; nevertheless its resolved path must be the pinned checkout,
    # not a different installed wheel.
    from ..inference import production_policy

    expected = _source_path(
        root, "src/nfl_dfs/inference/production_policy.py"
    ).resolve()
    actual = Path(inspect.getfile(production_policy)).resolve()
    if actual != expected:
        raise EffectivePolicyInventoryError(
            "effective policy import does not resolve to the pinned source"
        )
    policy = production_policy.ADOPTED_CLASSIC_POLICY
    env = dict(sorted(policy.engine_environment({}).items()))
    if len(env) != 73 or canonical_sha256(env) != POLICY_ENV_SHA256:
        raise EffectivePolicyInventoryError(
            "adopted effective policy environment differs"
        )
    identity = policy.public_identity(entries=80, tail_line=194.0)
    receipt = identity.get("engine_environment_receipt", {})
    if receipt.get("values") != env:
        raise EffectivePolicyInventoryError(
            "public policy identity does not bind the effective environment"
        )
    if receipt.get("sha256") != sha256(
        json.dumps(env, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest():
        raise EffectivePolicyInventoryError(
            "public policy environment SHA-256 differs"
        )
    return env, identity


def _loc(path: str, symbol: str) -> _Locator:
    return _Locator(path, symbol)


def _parse_multiseed_seed_pairs(spec: str) -> list[dict[str, int | str]]:
    pairs: list[dict[str, int | str]] = []
    for index, token in enumerate(spec.split(";")):
        match = re.fullmatch(r"R([0-9]+)=([0-9]+):([0-9]+)", token)
        if match is None or int(match.group(1)) != index:
            raise EffectivePolicyInventoryError(
                "adopted multiseed seed-pair specification differs"
            )
        pairs.append({
            "label": f"R{index}",
            "projection_seed": int(match.group(2)),
            "role_seed": int(match.group(3)),
        })
    if len(pairs) != 5:
        raise EffectivePolicyInventoryError(
            "adopted multiseed seed-pair count differs"
        )
    return pairs


def _rules(env: Mapping[str, str]) -> tuple[_Rule, ...]:
    lineup = "src/nfl_dfs/optimizer/lineup.py"
    engine = "src/nfl_dfs/backtest/engine.py"
    replay = "src/nfl_dfs/backtest/replay.py"
    app = "src/nfl_dfs/app/main.py"
    policy = "src/nfl_dfs/inference/production_policy.py"
    presets = "src/nfl_dfs/optimizer/construction_presets.py"
    multiseed = "src/nfl_dfs/inference/multiseed_portfolio.py"
    live = "src/nfl_dfs/inference/live_lineups.py"
    simulate = "src/nfl_dfs/models/simulate.py"
    game_sim = "src/nfl_dfs/models/game_sim.py"
    forensic = "src/nfl_dfs/research/final_forensic.py"
    lr8 = "src/nfl_dfs/research/lr8_historical_arm.py"

    common_soft_locators = (
        _loc(lineup, "function:_apply_stack_rules"),
        _loc(replay, "function:run"),
        _loc(app, "class:LineupRequest:field:qb_stack_min"),
        _loc(forensic, "function:solve_draftkings_legal_oracle"),
        _loc(lr8, "function:build_dk_classic_model"),
    )
    rows: list[_Rule] = [
        # DraftKings Classic legality. Position bounds are one indivisible
        # contest shape but its full exact dose is retained, not summarized.
        _Rule("rule:dk-roster-size-nine", "Exactly nine distinct players",
              "dk_hard", "generation", "active", 9, (ALL_GENERATION,),
              (_loc(lineup, "module:ROSTER_SIZE"),
               _loc(forensic, "function:audit_roster"),
               _loc(lr8, "function:audit_dk_classic_identity"))),
        _Rule("rule:dk-position-shape", "DK Classic position shape",
              "dk_hard", "generation", "active", {
                  "DST": {"max": 1, "min": 1},
                  "QB": {"max": 1, "min": 1},
                  "RB": {"max": 3, "min": 2},
                  "TE": {"max": 2, "min": 1},
                  "WR": {"max": 4, "min": 3},
              }, (ALL_GENERATION,),
              (_loc(lineup, "function:add_classic_lineup_constraints"),
               _loc(forensic, "function:audit_roster"),
               _loc(lr8, "function:audit_dk_classic_identity"))),
        _Rule("rule:dk-salary-cap-50000", "Salary at or below 50000",
              "dk_hard", "generation", "active", 50_000, (ALL_GENERATION,),
              (_loc(lineup, "module:SALARY_CAP"),
               _loc(forensic, "function:solve_draftkings_legal_oracle"),
               _loc(lr8, "function:audit_dk_classic_identity"))),
        _Rule("rule:dk-team-cap-eight", "At most eight players per team",
              "dk_hard", "generation", "active", 8, (ALL_GENERATION,),
              (_loc(lineup, "module:MAX_FROM_TEAM"),
               _loc(lr8, "function:audit_dk_classic_identity"))),
        _Rule("rule:min-two-games", "At least two games represented",
              "house_soft", "generation", "active", 2, (ALL_GENERATION,),
              (_loc(presets, "module:_PRESETS"),
               _loc(lineup, "function:add_classic_lineup_constraints"))),

        # The exact five-field legal-feasibility parameter surface.
        _Rule("rule:salary-floor-49000", "Minimum salary 49000",
              "house_soft", "generation", "active", int(env["MIN_LINEUP_SALARY"]),
              (ALL_GENERATION,),
              (_loc(policy, "class:ClassicProductionPolicy:field:min_lineup_salary"),
               _loc(policy, "class:ClassicProductionPolicy:method:engine_environment"),
               _loc(lineup, "function:add_classic_lineup_constraints"),
               _loc(forensic, "function:solve_draftkings_legal_oracle"),
               _loc(lr8, "function:build_dk_classic_model")),
              parametric_field="min_lineup_salary"),
        _Rule("rule:qb-stack-min-two",
              "QB plus at least two same-team WR/TE", "house_soft",
              "generation", "active", 2, (ALL_GENERATION,),
              common_soft_locators, parametric_field="qb_stack_min"),
        _Rule("rule:bring-back-min-one", "At least one opponent bring-back",
              "house_soft", "generation", "active", 1, (ALL_GENERATION,),
              common_soft_locators, parametric_field="bring_back_min"),
        _Rule("rule:forbid-rb-vs-dst", "Forbid RB against selected DST",
              "house_soft", "generation", "active", True, (ALL_GENERATION,),
              common_soft_locators, parametric_field="forbid_rb_vs_dst"),
        _Rule("rule:forbid-two-rb-same-team", "Forbid two RB from one team",
              "house_soft", "generation", "active", True, (ALL_GENERATION,),
              common_soft_locators,
              parametric_field="forbid_two_rb_same_team"),

        # Active family-specific house constraints.
        _Rule("rule:leverage-overlap-seven",
              "Leverage sequential overlap at most seven", "house_soft",
              "generation", "active", 7, (LEV,),
              (_loc(lineup, "function:optimize_many"),
               _loc(engine, "function:tail_select_lineups"))),
        _Rule("rule:qbvar-overlap-six",
              "QB-variant sequential overlap at most six", "house_soft",
              "generation", "active", 6, (QBVAR,),
              (_loc(engine, "function:tail_select_lineups"),)),
        _Rule("rule:game-overlap-seven",
              "Projected-game sequential overlap at most seven", "house_soft",
              "generation", "active", 7, (GAME,),
              (_loc(engine, "function:tail_select_lineups"),)),
        _Rule("rule:game-lock-min-five", "Family game lock of five players",
              "house_soft", "generation", "active", 5, (GAME, DARK),
              (_loc(lineup, "function:add_classic_lineup_constraints"),
               _loc(engine, "function:tail_select_lineups"))),

        # Every optional feasibility seam gets its own row, even when dormant.
        _Rule("rule:punt-minimum", "Minimum punt-priced players", "house_soft",
              "generation", "inactive", {"maximum_salary": 4000, "minimum": 0},
              (ALL_GENERATION,),
              (_loc(lineup, "function:add_classic_lineup_constraints"),
               _loc(policy, "class:ClassicProductionPolicy:method:engine_environment")),
              optional=True),
        _Rule("rule:value-two-minimum", "Minimum sub-5300 skill players",
              "house_soft", "generation", "inactive",
              {"maximum_salary": 5300, "minimum": 0}, (ALL_GENERATION,),
              (_loc(lineup, "function:add_classic_lineup_constraints"),),
              optional=True),
        _Rule("rule:ownership-barbell-low", "Low-owned player minimum",
              "house_soft", "generation", "inactive",
              {"maximum_ownership": 0.05, "minimum": 3}, (ALL_GENERATION,),
              (_loc(lineup, "function:add_classic_lineup_constraints"),),
              optional=True),
        _Rule("rule:ownership-barbell-high", "High-owned player minimum",
              "house_soft", "generation", "inactive",
              {"minimum": 2, "minimum_ownership": 0.20}, (ALL_GENERATION,),
              (_loc(lineup, "function:add_classic_lineup_constraints"),),
              optional=True),
        _Rule("rule:max-per-game-cap", "Maximum players from one game",
              "house_soft", "generation", "inactive", 0,
              (ALL_GENERATION,),
              (_loc(lineup, "function:add_classic_lineup_constraints"),
               _loc(policy, "class:ClassicProductionPolicy:method:engine_environment")),
              optional=True),
        _Rule("rule:min-low-ownership", "Low-ownership player minimum",
              "house_soft", "generation", "inactive", 0,
              (ALL_GENERATION,),
              (_loc(lineup, "function:add_classic_lineup_constraints"),),
              optional=True),
        _Rule("rule:maximum-salary", "Optional salary ceiling below DK cap",
              "house_soft", "generation", "inactive", None,
              (ALL_GENERATION,),
              (_loc(lineup, "function:add_classic_lineup_constraints"),),
              optional=True),
        _Rule("rule:qb-stack-maximum", "Optional QB stack maximum",
              "house_soft", "generation", "inactive", None,
              (ALL_GENERATION,),
              (_loc(lineup, "class:StackRules:field:qb_stack_max"),
               _loc(lineup, "function:_apply_stack_rules")), optional=True),
        _Rule("rule:bring-back-maximum", "Optional bring-back maximum",
              "house_soft", "generation", "inactive", None,
              (ALL_GENERATION,),
              (_loc(lineup, "class:StackRules:field:bring_back_max"),
               _loc(lineup, "function:_apply_stack_rules")), optional=True),
        _Rule("rule:require-rb-vs-dst", "Require RB against selected DST",
              "house_soft", "generation", "inactive", False,
              (ALL_GENERATION,),
              (_loc(lineup, "class:StackRules:field:require_rb_vs_dst"),
               _loc(lineup, "function:_apply_stack_rules")), optional=True),
        _Rule("rule:require-two-rb-same-team", "Require two same-team RBs",
              "house_soft", "generation", "inactive", False,
              (ALL_GENERATION,),
              (_loc(lineup, "class:StackRules:field:require_two_rb_same_team"),
               _loc(lineup, "function:_apply_stack_rules")), optional=True),
        _Rule("rule:player-locks", "Operator player locks", "house_soft",
              "generation", "inactive", [], (ALL_GENERATION,),
              (_loc(lineup, "function:add_classic_lineup_constraints"),),
              optional=True),
        _Rule("rule:player-bans", "Operator player bans", "house_soft",
              "generation", "inactive", [], (ALL_GENERATION,),
              (_loc(lineup, "function:add_classic_lineup_constraints"),),
              optional=True),
        _Rule("rule:objective-floor", "Optional linear objective floor",
              "house_soft", "generation", "inactive", None,
              (ALL_GENERATION,), (_loc(lineup, "function:optimize"),),
              optional=True),
        _Rule("rule:interaction-floor", "Optional interaction objective floor",
              "house_soft", "generation", "inactive", None,
              (ALL_GENERATION,), (_loc(lineup, "function:optimize"),),
              optional=True),

        # Candidate families and source-free recipes.
        _Rule("rule:leverage-family", "Leverage candidate family",
              "generation_recipe", "generation", "active",
              {"candidate_multiple": int(env["CAND_MULT"]),
               "generation_entry_basis": int(env["MULTISEED_CANDIDATE_ENTRY_BASIS"])},
              (LEV,), (_loc(engine, "function:tail_select_lineups"),
                       _loc(policy, "class:ClassicProductionPolicy:method:engine_environment"))),
        _Rule("rule:boom-family", "Boom-world candidate family",
              "generation_recipe", "generation", "active",
              {"solve_attempts": int(env["N_BOOM"]), "unique_fill": False},
              (BOOM,), (_loc(engine, "function:tail_select_lineups"),
                        _loc(policy, "class:ClassicProductionPolicy:method:engine_environment"))),
        _Rule("rule:role-family", "Direct-role candidate family",
              "generation_recipe", "generation", "active",
              {"family": env["EPISTEMIC_FAMILY"],
               "feature_spec": env["ROLE_BELIEF_FEATURES"],
               "features": env["ROLE_BELIEF_FEATURES"].split(","),
               "seed": int(env["ROLE_BELIEF_SEED"]),
               "solve_slots": int(env["N_EPISTEMIC"])}, (ROLE,),
              (_loc(engine, "function:tail_select_lineups"),
               _loc(policy, "class:ClassicProductionPolicy:method:engine_environment"))),
        _Rule("rule:qb-variant-family", "QB-variant candidate family",
              "generation_recipe", "generation", "active",
              {"per_qb": int(env["N_QB_VARIANTS"]), "qb_count": 8}, (QBVAR,),
              (_loc(engine, "function:tail_select_lineups"),)),
        _Rule("rule:game-stack-family", "Projected-game stack family",
              "generation_recipe", "generation", "active",
              {"candidates_per_game": 3, "games": int(env["N_GAMESTACK"])},
              (GAME,), (_loc(engine, "function:tail_select_lineups"),)),
        _Rule("rule:dark-game-family", "Dark-game stack family",
              "generation_recipe", "generation", "active",
              {"games": int(env["N_DARKGAME"]), "candidates_per_game": 1},
              (DARK,), (_loc(engine, "function:tail_select_lineups"),)),
        _Rule("rule:ce-family", "Cross-entropy candidate family",
              "generation_recipe", "generation", "inactive",
              int(env["N_CE"]), ("generation:cross-entropy",),
              (_loc(engine, "function:tail_select_lineups"),), optional=True),
        _Rule("rule:gumbel-family", "Gumbel candidate family",
              "generation_recipe", "generation", "inactive",
              int(env["N_GUMBEL"]), ("generation:gumbel",),
              (_loc(engine, "function:tail_select_lineups"),), optional=True),
        _Rule("rule:no-stack-family", "No-stack candidate family",
              "generation_recipe", "generation", "inactive",
              int(env["N_NOSTACK"]), ("generation:no-stack",),
              (_loc(engine, "function:tail_select_lineups"),), optional=True),
        _Rule("rule:low-salary-family", "Low-salary candidate family",
              "generation_recipe", "generation", "inactive",
              int(env["N_LOWSAL"]), ("generation:low-salary",),
              (_loc(engine, "function:tail_select_lineups"),), optional=True),
        _Rule("rule:mid-qb-family", "Mid-tier-QB candidate family",
              "generation_recipe", "generation", "inactive",
              int(env["N_MIDQB"]), ("generation:mid-qb",),
              (_loc(engine, "function:tail_select_lineups"),), optional=True),
        _Rule("rule:hyper-boom-family", "Manufactured hyper-boom family",
              "generation_recipe", "generation", "inactive",
              int(env["HYPER_BOOM"]), ("generation:hyper-boom",),
              (_loc(engine, "function:tail_select_lineups"),), optional=True),
        _Rule("rule:q99-wildcard-family", "Q99 wildcard family",
              "generation_recipe", "generation", "inactive",
              int(env["Q99_WILD"]), ("generation:q99-wildcard",),
              (_loc(engine, "function:tail_select_lineups"),), optional=True),
        _Rule("rule:quality-diversity-family", "Quality-diversity cells",
              "generation_recipe", "generation", "inactive",
              int(env["QD_CELLS"]), ("generation:quality-diversity",),
              (_loc(engine, "function:tail_select_lineups"),), optional=True),
        _Rule("rule:open-boom-carve", "Open stack/bring-back boom carve",
              "generation_recipe", "generation", "inactive",
              int(env["OPEN_BOOM_SOLVES"]), (BOOM,),
              (_loc(engine, "function:tail_select_lineups"),), optional=True),
        _Rule("rule:single-stack-boom-carve", "Exact-one-stack boom carve",
              "generation_recipe", "generation", "inactive",
              int(env["SINGLE_STACK_BOOM_SOLVES"]), (BOOM,),
              (_loc(engine, "function:tail_select_lineups"),), optional=True),
        _Rule("rule:boom-unique-fill", "Boom unique-fill traversal",
              "generation_recipe", "generation", "inactive", False, (BOOM,),
              (_loc(engine, "function:tail_select_lineups"),), optional=True),

        # Admission is separate from lineup feasibility.
        _Rule("rule:first-producer-dedup-order",
              "First-producer exact-roster dedup and generation order",
              "admission_recipe", "admission", "active",
              {"identity": "frozenset-player-ids", "order": "first-producer"},
              (ADMISSION,), (_loc(engine, "function:tail_select_lineups"),)),
        _Rule("rule:cbwu-cross-seed-admission",
              "CBWU five-seed quota admission at the R0 budget",
              "admission_recipe", "admission", "active", {
                  "candidate_entry_basis": int(env["MULTISEED_CANDIDATE_ENTRY_BASIS"]),
                  "portfolio": env["MULTISEED_PORTFOLIO"],
                  "seed_pair_spec": env["MULTISEED_SEED_PAIRS"],
                  "seed_pairs": _parse_multiseed_seed_pairs(
                      env["MULTISEED_SEED_PAIRS"]),
                  "worlds_per_block": int(env["MULTISEED_WORLDS_PER_BLOCK"]),
              }, (CBWU,),
              (_loc(multiseed, "function:combine_cbwu_books"),
               _loc(live, "function:build_sim_lineups"),
               _loc(policy, "class:ClassicProductionPolicy:method:engine_environment"))),
        _Rule("rule:candidate-budget-truncation", "Candidate-pool cap",
              "admission_recipe", "admission", "inactive",
              {"global": int(env["GEN_POOL_CAP"]), "per_slate": env["GEN_POOL_CAP_MAP"]},
              (ADMISSION,), (_loc(engine, "function:tail_select_lineups"),),
              optional=True),

        # Simulation-law components remain individually inspectable.
        _Rule("rule:simulation-game-mode", "Possession game simulator",
              "simulation_law", "simulation", "active", env["GAME_SIM_MODE"],
              (SIMULATION,), (_loc(simulate, "function:simulate"),
                              _loc(game_sim, "function:simulate_game_points"))),
        _Rule("rule:simulation-team-factors", "Team-specific game factors",
              "simulation_law", "simulation", "active", True, (SIMULATION,),
              (_loc(simulate, "function:simulate"),
               _loc(game_sim, "function:team_game_factors"))),
        _Rule("rule:simulation-pace-conditioning", "Vegas pace conditioning",
              "simulation_law", "simulation", "inactive", env["GAME_SIM_PACE"],
              (SIMULATION,), (_loc(simulate, "function:simulate"),), optional=True),
        _Rule("rule:simulation-usage-dirichlet", "Dirichlet usage allocation",
              "simulation_law", "simulation", "inactive", env["GAME_SIM_USAGE"],
              (SIMULATION,), (_loc(simulate, "function:simulate"),
                              _loc(game_sim, "function:allocate_drive_usage")),
              optional=True),
        _Rule("rule:simulation-td-ledger", "Passing-TD event ledger",
              "simulation_law", "simulation", "inactive", False,
              (SIMULATION,), (_loc(simulate, "function:simulate"),), optional=True),
        _Rule("rule:simulation-fitted-widen", "Fitted positional draw widening",
              "simulation_law", "simulation", "active", env["SIM_WIDEN_DRAWS"],
              (SIMULATION,), (_loc(replay, "function:replay_projections"),
                              _loc(policy, "class:ClassicProductionPolicy:method:engine_environment"))),
        _Rule("rule:simulation-served-position-scales",
              "Final-served position spread scales", "simulation_law",
              "simulation", "active", env["SERVED_POSITION_SCALES"],
              (SIMULATION,), (_loc(replay, "function:replay_projections"),
                              _loc(policy, "class:ClassicProductionPolicy:method:engine_environment"))),
        _Rule("rule:simulation-script-feedback", "Possession script feedback",
              "simulation_law", "simulation", "inactive", False,
              (SIMULATION,), (_loc(game_sim, "function:simulate_game_points"),),
              optional=True),

        # Selector law and every policy-exposed alternative are separate.
        _Rule("rule:selector-line194", "Greedy binary coverage at line 194",
              "selector", "selection", "active",
              {"entries": 80, "line": 194.0, "lse_alpha": 0.0},
              (SELECTION,), (_loc(lineup, "function:select_tail_entries"),
                             _loc(policy, "class:ClassicProductionPolicy:field:tail_line"))),
        _Rule("rule:selector-ladder", "Multi-threshold ladder selector",
              "selector", "selection", "inactive", env["SELECT_LADDER"],
              (SELECTION,), (_loc(lineup, "function:select_tail_entries"),),
              optional=True),
        _Rule("rule:selector-lse", "Log-sum-exp selector",
              "selector", "selection", "inactive", float(env["SELECT_LSE"]),
              (SELECTION,), (_loc(lineup, "function:select_tail_entries"),),
              optional=True),
        _Rule("rule:selector-dollars", "Expected-dollar selector",
              "selector", "selection", "inactive", env["SELECT_OBJ"],
              (SELECTION,), (_loc(engine, "function:select_dollar_entries"),),
              optional=True),
        _Rule("rule:selector-qb-block", "Single-QB-block selector",
              "selector", "selection", "inactive", int(env["M4_QBLOCK"]),
              (SELECTION,), (_loc(engine, "function:tail_select_lineups"),),
              optional=True),
        _Rule("rule:selector-max-qbs", "Selected-book distinct-QB cap",
              "selector", "selection", "inactive", int(env["MAX_QBS"]),
              (SELECTION,), (_loc(engine, "function:_select_tail_qb_capped"),),
              optional=True),
        _Rule("rule:selector-peak-slice", "Individual-tail peak slice",
              "selector", "selection", "inactive", int(env["PEAK_SLICE"]),
              (SELECTION,), (_loc(engine, "function:tail_select_lineups"),),
              optional=True),
    ]
    return tuple(rows)


def _materialize_rules(
    rules: Iterable[_Rule],
    *,
    source_by_path: Mapping[str, dict[str, Any]],
    tree_by_path: Mapping[str, ast.Module],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rule in rules:
        if not ID_RE.fullmatch(rule.id) or rule.id in seen:
            raise EffectivePolicyInventoryError(
                f"rule id is invalid or duplicated: {rule.id}"
            )
        seen.add(rule.id)
        if rule.classification not in CLASSIFICATIONS:
            raise EffectivePolicyInventoryError(
                f"rule classification differs: {rule.id}"
            )
        if rule.stage not in STAGES or rule.baseline_state not in BASELINE_STATES:
            raise EffectivePolicyInventoryError(f"rule state/stage differs: {rule.id}")
        paths = sorted(set(rule.normalized_paths))
        if not paths or len(paths) != len(rule.normalized_paths) or any(
            not PATH_RE.fullmatch(path) for path in paths
        ):
            raise EffectivePolicyInventoryError(
                f"rule normalized path set differs: {rule.id}"
            )
        locators: list[dict[str, Any]] = []
        locator_keys: set[tuple[str, str]] = set()
        for locator in rule.locators:
            key = (locator.path, locator.symbol)
            if key in locator_keys or locator.path not in source_by_path:
                raise EffectivePolicyInventoryError(
                    f"rule source locator differs: {rule.id}"
                )
            locator_keys.add(key)
            _validate_symbol(tree_by_path[locator.path], locator.symbol)
            locators.append({
                "path": locator.path,
                "source_sha256": source_by_path[locator.path]["sha256"],
                "symbol": locator.symbol,
            })
        locators.sort(key=lambda row: (row["path"], row["symbol"]))
        if not locators:
            raise EffectivePolicyInventoryError(f"rule has no source: {rule.id}")
        output.append({
            "baseline_state": rule.baseline_state,
            "classification": rule.classification,
            "default_dose": rule.default_dose,
            "id": rule.id,
            "label": rule.label,
            "normalized_paths": paths,
            "optional": rule.optional,
            "parametric_field": rule.parametric_field,
            "source_locator_sha256": canonical_sha256(locators),
            "source_locators": locators,
            "stage": rule.stage,
        })
    output.sort(key=lambda row: row["id"])
    return output


def _validate_parametric_surface(rules: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = {row["id"]: row for row in rules}
    observed = {
        str(row["parametric_field"]): str(row["id"])
        for row in rules if row["parametric_field"] is not None
    }
    expected = {field: values[0] for field, values in PARAMETRIC_FIELDS.items()}
    if observed != expected or len(observed) != 5:
        raise EffectivePolicyInventoryError(
            "legal-feasibility parameter surface is not exactly five fields"
        )
    surface: list[dict[str, Any]] = []
    for field in sorted(PARAMETRIC_FIELDS):
        rule_id, baseline, allowed = PARAMETRIC_FIELDS[field]
        row = rows.get(rule_id)
        if row is None or row["classification"] != "house_soft" or (
            row["stage"] != "generation" or row["baseline_state"] != "active"
            or row["normalized_paths"] != [ALL_GENERATION]
            or not _strict_same(row["default_dose"], baseline)
        ):
            raise EffectivePolicyInventoryError(
                f"active soft-constraint proof differs: {field}"
            )
        value_type = "boolean" if type(baseline) is bool else "integer"
        surface.append({
            "allowed_values": list(allowed),
            "baseline": baseline,
            "field": field,
            "rule_id": rule_id,
            "type": value_type,
        })
    return surface


def _validate_constraint_rule_coverage(rules: Sequence[Mapping[str, Any]]) -> None:
    ids = {str(row["id"]) for row in rules}
    referenced = {
        rule_id
        for mapping in (
            STACK_FIELD_RULES,
            SHARED_CONSTRAINT_PARAMETER_RULES,
            OPTIMIZE_ONLY_CONSTRAINT_RULES,
        )
        for rule_ids in mapping.values()
        for rule_id in rule_ids
    }
    missing = sorted(referenced - ids)
    if missing:
        raise EffectivePolicyInventoryError(
            f"optional constraint rules are absent: {missing}"
        )


def generate_effective_policy_rule_inventory(root: Path) -> dict[str, Any]:
    """Generate the canonical independent inventory from frozen local code.

    The function performs local static reads and one dependency-light adopted
    policy import.  It never queries outcomes, starts a solver, or touches any
    cloud service.
    """
    identities, text_by_path, tree_by_path = _load_sources(root)
    _assert_surface_coverage(tree_by_path)
    _assert_independent_soft_rule_proofs(text_by_path)
    env, policy_identity = _effective_policy(root)

    source_by_path = {row["path"]: row for row in identities}
    direct_input_reads = _discover_direct_input_reads(tree_by_path)
    classified_input_projection = _classified_input_projection(
        env=env,
        reads=direct_input_reads,
        source_by_path=source_by_path,
    )
    classified_input_projection_sha256 = canonical_sha256(
        classified_input_projection
    )
    if (
        classified_input_projection_sha256
        != CLASSIFIED_INPUT_PROJECTION_SHA256
    ):
        raise EffectivePolicyInventoryError(
            "classified runtime-input projection SHA-256 differs"
        )
    rules = _materialize_rules(
        _rules(env), source_by_path=source_by_path, tree_by_path=tree_by_path
    )
    _validate_constraint_rule_coverage(rules)
    parametric_surface = _validate_parametric_surface(rules)

    universe_projection = [{
        key: row[key] for key in (
            "baseline_state",
            "classification",
            "default_dose",
            "id",
            "normalized_paths",
            "optional",
            "parametric_field",
            "source_locator_sha256",
            "stage",
        )
    } for row in rules]
    payload: dict[str, Any] = {
        "classified_input_projection": classified_input_projection,
        "classified_input_projection_sha256": (
            classified_input_projection_sha256
        ),
        "complete_for_scope": True,
        "effective_policy": {
            "engine_environment": env,
            "engine_environment_sha256": canonical_sha256(env),
            "policy_id": policy_identity["policy_id"],
            "public_identity_sha256": canonical_sha256(policy_identity),
        },
        "forbidden_ambient_process_keys": list(FORBIDDEN_AMBIENT_KEYS),
        "legal_feasibility_parameters": parametric_surface,
        "rule_count": len(rules),
        "rule_universe_sha256": canonical_sha256(universe_projection),
        "rules": rules,
        "schema": SCHEMA,
        "scope": {
            "candidate_paths": list(ACTIVE_GENERATION_PATHS),
            "description": (
                "Adopted DK Classic legality; all shared optional feasibility "
                "seams; effective candidate generation/admission; production "
                "simulation law; and exact-80 selector law"
            ),
            "excludes": [
                "model fitting and feature construction",
                "contest payout utility",
                "realized outcomes",
                "operator deployment and retry authority",
            ],
            "runtime_receipt_required": True,
        },
        "source_identities": identities,
        "source_set_id": SOURCE_SET_ID,
        "source_set_sha256": canonical_sha256(identities),
    }
    payload["inventory_sha256"] = canonical_sha256(payload)
    return payload


def validate_effective_policy_rule_inventory(
    inventory: Mapping[str, Any], root: Path
) -> dict[str, Any]:
    """Regenerate from source and require exact, type-sensitive equality."""
    regenerated = generate_effective_policy_rule_inventory(root)
    if not _strict_same(dict(inventory), regenerated):
        raise EffectivePolicyInventoryError(
            "retained effective-policy inventory differs from frozen source"
        )
    return regenerated


__all__ = [
    "EffectivePolicyInventoryError",
    "FROZEN_SOURCE_SHA256",
    "PARAMETRIC_FIELDS",
    "SCHEMA",
    "canonical_json_bytes",
    "canonical_sha256",
    "generate_effective_policy_rule_inventory",
    "validate_effective_policy_rule_inventory",
]
