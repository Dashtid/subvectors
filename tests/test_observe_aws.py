"""Offline coverage for the observed-promotion harness.

The harness talks to AWS, so its live path cannot run in CI -- but everything
around the network hop can, and that is where the failures have actually been.
Two real incidents motivate this file:

1. The 2026-08-29 run lost a whole evening to `--policy-input-list` mis-parsing
   inline JSON; the `--cli-input-json` rewrite that fixed it then shipped
   WITHOUT ever completing a live run, so nothing proved the new invocation was
   even well-formed.
2. The 2026-08-30 creation probe was hand-run and its condition operator was
   never recorded, which forced github-aws 0.3.3 to narrow a headline claim.

So: pin the request shape, pin that the operator is always captured, pin that
transcripts are written and scrubbed, and pin that a creation probe refuses to
run on an implied operator. Responses are recorded fixtures -- verbatim shapes
from the 2026-08-29/30 runs.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "_subvectors_observe_aws", ROOT / "scripts" / "observe_aws.py"
)
observe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(observe)


ALLOWED_RESPONSE = {
    "EvaluationResults": [
        {
            "EvalActionName": "sts:AssumeRoleWithWebIdentity",
            "EvalResourceName": "*",
            "EvalDecision": "allowed",
            "MatchedStatements": [
                {
                    "SourcePolicyId": "PolicyInputList.1",
                    "SourcePolicyType": "IAM Policy",
                }
            ],
        }
    ]
}


def _vector(vector_id: str) -> dict:
    return observe._load_index()[vector_id]


# --- request construction ------------------------------------------------


def test_request_carries_the_policy_as_an_escaped_string() -> None:
    """PolicyInputList is list<string>; a nested object is the 2026-08-29 bug."""
    request = observe._build_request(_vector("gh-aws-org-wide-wildcard-repo"))
    assert isinstance(request["PolicyInputList"], list)
    (policy_text,) = request["PolicyInputList"]
    assert isinstance(policy_text, str), "policy must be an escaped string, not an object"
    policy = json.loads(policy_text)
    assert policy["Statement"][0]["Action"] == "sts:AssumeRoleWithWebIdentity"


def test_request_is_sent_via_cli_input_json() -> None:
    command = observe._build_command(_vector("gh-aws-org-wide-wildcard-repo"))
    assert "--cli-input-json" in command
    assert "--policy-input-list" not in command
    json.loads(command[command.index("--cli-input-json") + 1])


def test_condition_and_context_come_from_the_vector_itself() -> None:
    """Nothing is re-typed: the evidence must map 1:1 onto the vector."""
    vector = _vector("gh-aws-org-wide-wildcard-repo")
    request = observe._build_request(vector)
    policy = json.loads(request["PolicyInputList"][0])
    condition = policy["Statement"][0]["Condition"]
    assert condition == {"StringLike": {observe.CONTEXT_KEY: [vector["condition"]["pattern"]]}}
    entry = request["ContextEntries"][0]
    assert entry["ContextKeyValues"] == [vector["subject"]]
    assert entry["ContextKeyName"] == observe.CONTEXT_KEY


def test_multi_value_pattern_stays_a_list() -> None:
    vector = _vector("gh-aws-multivalue-loose-value-poisons-list")
    policy = json.loads(observe._build_request(vector)["PolicyInputList"][0])
    values = policy["Statement"][0]["Condition"]["StringLike"][observe.CONTEXT_KEY]
    assert values == vector["condition"]["pattern"]
    assert len(values) > 1


def test_stringequals_vector_uses_the_stringequals_operator() -> None:
    vector = _vector("gh-aws-stringequals-treats-star-literally")
    policy = json.loads(observe._build_request(vector)["PolicyInputList"][0])
    assert "StringEquals" in policy["Statement"][0]["Condition"]


def test_every_default_id_exists_and_is_eligible() -> None:
    index = observe._load_index()
    for vector_id in observe.DEFAULT_IDS:
        assert vector_id in index, f"{vector_id} is not in the corpus"
        assert observe._eligible(index[vector_id]) is None


# --- transcripts ---------------------------------------------------------


def test_transcript_is_written_and_stamped(tmp_path: Path) -> None:
    path = observe.write_transcript(tmp_path, "some-vector", {"mode": "test"})
    assert path.exists()
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["mode"] == "test"
    assert document["recorded_utc"].endswith("+00:00")


def test_transcript_scrubs_account_ids_everywhere(tmp_path: Path) -> None:
    """Transcripts are committed, so account ids must never reach disk."""
    record = {
        "arn": "arn:aws:iam::210987654321:oidc-provider/token.actions.githubusercontent.com",
        "nested": {"list": ["account 123456789012 here"]},
    }
    document = json.loads(
        observe.write_transcript(tmp_path, "scrub", record).read_text(encoding="utf-8")
    )
    blob = json.dumps(document)
    assert "210987654321" not in blob
    assert "123456789012" not in blob
    assert blob.count(observe._ACCOUNT_PLACEHOLDER) == 2


def test_transcript_refuses_to_clobber_a_different_probe(tmp_path: Path) -> None:
    """The 2026-08-31 collision, as a guard."""
    first = {"mode": "iam-create-role", "operator": "StringLike", "values": ["repo:acme/x", "*"]}
    second = {"mode": "iam-create-role", "operator": "StringLike", "values": ["*"]}
    observe.write_transcript(tmp_path, "create-role-ad-hoc", first)
    with pytest.raises(SystemExit, match="different probe"):
        observe.write_transcript(tmp_path, "create-role-ad-hoc", second)
    kept = json.loads((tmp_path / "create-role-ad-hoc.json").read_text(encoding="utf-8"))
    assert kept["values"] == ["repo:acme/x", "*"], "the first probe's evidence must survive"


def test_transcript_allows_rerunning_the_same_probe(tmp_path: Path) -> None:
    record = {"mode": "iam-create-role", "operator": "StringLike", "values": ["*"]}
    observe.write_transcript(tmp_path, "create-role-x", record)
    observe.write_transcript(tmp_path, "create-role-x", dict(record, accepted=False))
    kept = json.loads((tmp_path / "create-role-x.json").read_text(encoding="utf-8"))
    assert kept["accepted"] is False


def test_transcript_records_its_probe_identity(tmp_path: Path) -> None:
    path = observe.write_transcript(
        tmp_path, "x", {"mode": "iam-create-role", "operator": "StringLike", "values": ["*"]}
    )
    document = json.loads(path.read_text(encoding="utf-8"))
    assert "probe_identity" in document
    assert "StringLike" in document["probe_identity"]


def test_scrub_leaves_other_numbers_alone() -> None:
    """Repository ids and 13-digit strings are not account ids."""
    assert observe.scrub("repo:owner@123456/name@456789:ref") == "repo:owner@123456/name@456789:ref"
    assert observe.scrub("1234567890123") == "1234567890123"


def test_observation_block_records_operator_and_transcript() -> None:
    vector = _vector("gh-aws-multivalue-loose-value-poisons-list")
    block = observe._observation_block(
        vector, "allowed", "aws-cli/2.36.33", "observations/2026-08-31/x.json"
    )
    assert block["method"] == "aws-iam-policy-simulator"
    assert block["transcript"] == "observations/2026-08-31/x.json"
    assert "StringLike" in block["evidence"], "the operator must be in the evidence"
    assert "EvalDecision=allowed" in block["evidence"]
    assert block["tool_version"] == "aws-cli/2.36.33"


def test_observation_block_satisfies_the_schema() -> None:
    schema = json.loads(
        (ROOT / "vectors" / "schema" / "vector-suite.schema.json").read_text(encoding="utf-8")
    )

    def resolve(node: dict) -> dict:
        while "$ref" in node:
            node = schema["$defs"][node["$ref"].split("/")[-1]]
        return node

    vector_def = resolve(schema["properties"]["vectors"]["items"])
    definition = resolve(vector_def["properties"]["observation"])
    block = observe._observation_block(
        _vector("gh-aws-org-wide-wildcard-repo"),
        "allowed",
        "aws-cli/2.36.33",
        "observations/2026-08-31/gh-aws-org-wide-wildcard-repo.json",
    )
    assert set(block) <= set(definition["properties"]), "harness emits an unknown field"
    assert set(definition["required"]) <= set(block)


def test_decision_parsing_matches_the_recorded_response_shape() -> None:
    decision = ALLOWED_RESPONSE["EvaluationResults"][0]["EvalDecision"]
    assert decision == "allowed"
    assert observe._parse_json(json.dumps(ALLOWED_RESPONSE)) == ALLOWED_RESPONSE


def test_parse_json_keeps_unparseable_output_verbatim() -> None:
    """An AWS error body still has to land in the transcript."""
    assert observe._parse_json("An error occurred (InvalidClientTokenId)\n") == (
        "An error occurred (InvalidClientTokenId)"
    )


# --- creation probe ------------------------------------------------------


def _args(**overrides: object) -> argparse.Namespace:
    base = {
        "creation_probe": None,
        "operator": None,
        "values": None,
        "no_condition": False,
        "label": None,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def test_creation_probe_derives_the_operator_from_the_vector() -> None:
    operator, values, label = observe.resolve_creation_probe(
        _args(creation_probe="gh-aws-multivalue-loose-value-poisons-list"),
        observe._load_index(),
    )
    assert operator == "StringLike"
    assert values == _vector("gh-aws-multivalue-loose-value-poisons-list")["condition"]["pattern"]
    assert label == "gh-aws-multivalue-loose-value-poisons-list"


def test_creation_probe_refuses_an_implied_operator() -> None:
    """The 2026-08-30 defect in one assertion: no operator, no run."""
    with pytest.raises(ValueError, match="operator"):
        observe.resolve_creation_probe(
            _args(creation_probe="", values=["repo:acme/x", "*"]), observe._load_index()
        )


def test_creation_probe_accepts_an_explicit_ad_hoc_operator() -> None:
    operator, values, label = observe.resolve_creation_probe(
        _args(creation_probe="", operator="StringLike", values=["repo:acme/x", "*"]),
        observe._load_index(),
    )
    assert (operator, values) == ("StringLike", ["repo:acme/x", "*"])
    assert label.startswith("ad-hoc-")


def test_ad_hoc_labels_differ_per_probe() -> None:
    """Two ad-hoc probes must not land on one transcript filename.

    On 2026-08-31 ["repo:acme/x","*"] and ["*"] both wrote create-role-ad-hoc.json
    and the first result survived only in git.
    """
    index = observe._load_index()
    _, _, a = observe.resolve_creation_probe(
        _args(creation_probe="", operator="StringLike", values=["repo:acme/x", "*"]), index
    )
    _, _, b = observe.resolve_creation_probe(
        _args(creation_probe="", operator="StringLike", values=["*"]), index
    )
    _, _, c = observe.resolve_creation_probe(
        _args(creation_probe="", operator="StringEquals", values=["repo:acme/x", "*"]), index
    )
    assert len({a, b, c}) == 3, "operator and values must both feed the label"


def test_ad_hoc_label_is_stable_for_the_same_probe() -> None:
    index = observe._load_index()
    args = dict(creation_probe="", operator="StringLike", values=["repo:acme/x", "*"])
    first = observe.resolve_creation_probe(_args(**args), index)[2]
    second = observe.resolve_creation_probe(_args(**args), index)[2]
    assert first == second


def test_explicit_label_wins() -> None:
    _, _, label = observe.resolve_creation_probe(
        _args(creation_probe="", operator="StringLike", values=["*"], label="star-only"),
        observe._load_index(),
    )
    assert label == "star-only"


def test_creation_probe_rejects_an_unknown_vector() -> None:
    with pytest.raises(ValueError, match="unknown vector id"):
        observe.resolve_creation_probe(
            _args(creation_probe="no-such-vector"), observe._load_index()
        )


def test_no_condition_probe_builds_a_policy_without_a_condition() -> None:
    operator, values, label = observe.resolve_creation_probe(
        _args(no_condition=True), observe._load_index()
    )
    assert (operator, values, label) == (None, [], "no-condition")
    policy = observe._trust_policy(None, [], "arn:aws:iam::<ACCOUNT>:oidc-provider/x")
    assert "Condition" not in policy["Statement"][0]


def test_no_condition_is_exclusive() -> None:
    with pytest.raises(ValueError, match="no operator"):
        observe.resolve_creation_probe(
            _args(no_condition=True, operator="StringLike"), observe._load_index()
        )


def test_trust_policy_pins_the_operator_and_the_federated_principal() -> None:
    policy = observe._trust_policy(
        "StringEquals", ["repo:acme/x", "*"], "arn:aws:iam::<ACCOUNT>:oidc-provider/gh"
    )
    statement = policy["Statement"][0]
    assert statement["Principal"] == {"Federated": "arn:aws:iam::<ACCOUNT>:oidc-provider/gh"}
    assert statement["Action"] == "sts:AssumeRoleWithWebIdentity"
    assert statement["Condition"] == {"StringEquals": {observe.CONTEXT_KEY: ["repo:acme/x", "*"]}}


def test_creation_operators_cover_every_operator_aws_names_in_its_guardrail() -> None:
    """MalformedPolicyDocument names exactly these three; a probe must reach all."""
    assert set(observe.CREATION_OPERATORS) == {
        "StringLike",
        "StringEquals",
        "StringEqualsIgnoreCase",
    }


# --- CLI wiring ----------------------------------------------------------


def test_dry_run_calls_nothing_and_prints_the_command(capsys, monkeypatch) -> None:
    monkeypatch.setattr(observe, "_run", lambda *a, **k: pytest.fail("dry run must not call aws"))
    assert observe.main(["gh-aws-org-wide-wildcard-repo", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "DRY-RUN" in out
    assert "simulate-custom-policy" in out


def test_dry_run_creation_probe_calls_nothing(capsys, monkeypatch) -> None:
    monkeypatch.setattr(observe, "_run", lambda *a, **k: pytest.fail("dry run must not call aws"))
    code = observe.main(
        ["--creation-probe", "gh-aws-multivalue-loose-value-poisons-list", "--dry-run"]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "operator=StringLike" in out


def test_unknown_vector_id_exits_two(capsys) -> None:
    assert observe.main(["no-such-vector", "--dry-run"]) == 2
    assert "unknown vector id" in capsys.readouterr().err


def test_creation_probe_rejects_a_positional_vector_id(capsys) -> None:
    code = observe.main(["gh-aws-org-wide-wildcard-repo", "--creation-probe", "--dry-run"])
    assert code == 2
    assert "--creation-probe" in capsys.readouterr().err


def test_transcript_scrubs_aws_unique_ids_not_just_account_digits(tmp_path: Path) -> None:
    """An AWS unique id leaks the account id as surely as the 12-digit form.

    AROA/AKIA/ASIA... ids embed the account id in base32, so redacting only the
    digits was not enough: two committed transcripts carried RoleIds from which
    the account id was trivially recoverable.
    """
    record = {
        "Role": {
            "RoleId": "AROAEXAMPLE1234567890",
            "Arn": "arn:aws:iam::210987654321:role/probe",
        },
        "AccessKeyId": "AKIAEXAMPLE1234567890",
    }
    document = json.loads(
        observe.write_transcript(tmp_path, "unique-ids", record).read_text(encoding="utf-8")
    )
    blob = json.dumps(document)
    assert "AROAEXAMPLE1234567890" not in blob
    assert "AKIAEXAMPLE1234567890" not in blob
    assert "210987654321" not in blob
    assert blob.count(observe._UNIQUE_ID_PLACEHOLDER) == 2


def test_committed_transcripts_carry_no_recoverable_account_id() -> None:
    """Guard the product itself, not just the helper: scan what is on disk."""
    import re

    root = Path(__file__).resolve().parent.parent / "observations"
    leaky = re.compile(r"(?<![0-9])[0-9]{12}(?![0-9])|(?:AROA|AKIA|ASIA|AIDA)[A-Z0-9]{12,}")
    offenders = []
    for path in sorted(root.rglob("*.json")):
        for hit in leaky.findall(path.read_text(encoding="utf-8")):
            if hit not in {"123456789012", "210987654321"}:
                offenders.append(f"{path.name}: {hit}")
    assert not offenders, f"recoverable AWS identifiers in committed transcripts: {offenders}"
