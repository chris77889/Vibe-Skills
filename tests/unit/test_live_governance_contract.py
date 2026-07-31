from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_SRC = REPO_ROOT / "packages" / "contracts" / "src"
if str(CONTRACTS_SRC) not in sys.path:
    sys.path.insert(0, str(CONTRACTS_SRC))

import vgo_contracts  # noqa: E402
from vgo_contracts.live_governance_contract import (  # noqa: E402
    LiveGovernanceContract,
    load_live_governance_contract,
    validate_live_document_workspace,
    validate_run_artifact_workspace,
)


def _write(path: Path, text: str = "# Contract\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _contract_payload(
    *,
    documents: list[dict[str, str]] | None = None,
) -> dict:
    return {
        "schema_version": 1,
        "max_live_documents": 30,
        "governed_roots": [".", "docs", "references"],
        "excluded_paths": ["THIRD_PARTY_LICENSES.md"],
        "excluded_prefixes": ["references/provenance/"],
        "documents": documents
        if documents is not None
        else [
            {
                "id": "project-entry",
                "path": "README.md",
                "owner": "project-entry",
                "lifecycle": "live",
            },
            {
                "id": "runtime-contract",
                "path": "docs/runtime-contract.md",
                "owner": "runtime-contracts",
                "lifecycle": "live",
            },
            {
                "id": "proof-policy",
                "path": "references/proof-policy.md",
                "owner": "verification",
                "lifecycle": "live",
            },
        ],
        "artifact_sink": {
            "schema_version": 1,
            "root": ".vibeskills/runs",
            "required_artifacts": ["requirement", "plan", "status", "proof"],
            "required_metadata": ["commit_sha", "execution_environment"],
        },
    }


def _run_manifest_payload() -> dict:
    return {
        "schema_version": 1,
        "run_id": "run-001",
        "artifact_root": ".vibeskills/runs/run-001",
        "artifacts": {
            "requirement": "requirement.json",
            "plan": "plan.json",
            "status": "status.json",
            "proof": "proof.json",
        },
        "commit_sha": "0123456789abcdef",
        "execution_environment": {
            "os": "windows",
            "python": "3.10",
        },
    }


def test_minimal_live_contract_workspace_emits_a_complete_run_artifact_manifest(tmp_path: Path) -> None:
    contract_payload = _contract_payload()
    _write(
        tmp_path / "config" / "live-document-contract.json",
        json.dumps(contract_payload, indent=2) + "\n",
    )
    for document in contract_payload["documents"]:
        _write(tmp_path / document["path"])

    contract = load_live_governance_contract(tmp_path / "docs")
    validated_paths = validate_live_document_workspace(contract, tmp_path)
    manifest = contract.validate_run_artifact_manifest(_run_manifest_payload())
    artifact_paths = manifest.resolve_artifact_paths(tmp_path)
    for artifact_kind, artifact_path in artifact_paths.items():
        _write(
            artifact_path,
            json.dumps({"artifact_kind": artifact_kind}) + "\n",
        )
    validated_artifact_paths = validate_run_artifact_workspace(
        manifest,
        tmp_path,
    )

    assert validated_paths == [
        tmp_path / "README.md",
        tmp_path / "docs" / "runtime-contract.md",
        tmp_path / "references" / "proof-policy.md",
    ]
    assert manifest.artifacts["proof"] == "proof.json"
    assert manifest.commit_sha == "0123456789abcdef"
    assert manifest.execution_environment == {"os": "windows", "python": "3.10"}
    assert validated_artifact_paths == artifact_paths
    assert all(path.is_file() for path in validated_artifact_paths.values())
    assert artifact_paths["proof"] == (
        tmp_path / ".vibeskills" / "runs" / "run-001" / "proof.json"
    )
    assert not (tmp_path / "docs" / "requirements").exists()
    assert not (tmp_path / "docs" / "plans").exists()


def test_repo_ships_a_valid_live_governance_contract() -> None:
    contract = load_live_governance_contract(REPO_ROOT)

    validated_paths = validate_live_document_workspace(contract, REPO_ROOT)

    assert len(validated_paths) <= 30
    assert validated_paths
    assert all(path.suffix.casefold() == ".md" for path in validated_paths)
    assert contract.artifact_sink.required_artifacts == (
        "requirement",
        "plan",
        "status",
        "proof",
    )
    assert contract.artifact_sink.required_metadata == (
        "commit_sha",
        "execution_environment",
    )


def test_runtime_config_manifest_packages_live_governance_contract() -> None:
    manifest = json.loads(
        (REPO_ROOT / "config" / "runtime-config-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    relpath = vgo_contracts.LIVE_GOVERNANCE_CONTRACT_RELPATH.as_posix()

    assert relpath in manifest["files"]
    assert relpath in manifest["role_groups"]["files"]["runtime_governance_files"]


def test_live_governance_contract_is_a_public_package_interface() -> None:
    assert (
        vgo_contracts.LIVE_GOVERNANCE_CONTRACT_RELPATH.as_posix()
        == "config/live-document-contract.json"
    )
    assert vgo_contracts.load_live_governance_contract is load_live_governance_contract
    assert (
        vgo_contracts.validate_live_document_workspace
        is validate_live_document_workspace
    )
    assert (
        vgo_contracts.validate_run_artifact_workspace
        is validate_run_artifact_workspace
    )


@pytest.mark.parametrize(
    "document_path",
    [
        "/docs/runtime-contract.md",
        "C:/docs/runtime-contract.md",
        "C:docs/runtime-contract.md",
    ],
)
def test_live_governance_contract_rejects_non_relative_document_paths(
    document_path: str,
) -> None:
    payload = _contract_payload(
        documents=[
            {
                "id": "runtime-contract",
                "path": document_path,
                "owner": "runtime-contracts",
                "lifecycle": "live",
            }
        ]
    )

    with pytest.raises(ValueError, match="relative"):
        LiveGovernanceContract.model_validate(payload)


def test_live_governance_contract_requires_all_governed_document_roots() -> None:
    payload = _contract_payload()
    payload["governed_roots"] = ["docs", "references"]

    with pytest.raises(ValueError, match="missing required governed roots"):
        LiveGovernanceContract.model_validate(payload)


def test_live_governance_contract_rejects_more_than_thirty_registered_documents() -> None:
    documents = [
        {
            "id": f"document-{index}",
            "path": f"docs/document-{index}.md",
            "owner": "governance",
            "lifecycle": "live",
        }
        for index in range(31)
    ]

    with pytest.raises(ValueError, match="configured budget is 30"):
        LiveGovernanceContract.model_validate(_contract_payload(documents=documents))


def test_live_document_budget_counts_every_maintained_registry_entry() -> None:
    documents = [
        {
            "id": f"document-{index}",
            "path": f"docs/document-{index}.md",
            "owner": "governance",
            "lifecycle": "live",
        }
        for index in range(30)
    ]
    documents.append(
        {
            "id": "retained-decision",
            "path": "docs/adr/retained-decision.md",
            "owner": "governance",
            "lifecycle": "retained",
        }
    )

    with pytest.raises(ValueError, match="configured budget is 30"):
        LiveGovernanceContract.model_validate(_contract_payload(documents=documents))


@pytest.mark.parametrize("field", ["owner", "lifecycle"])
def test_live_governance_contract_requires_document_metadata(field: str) -> None:
    document = {
        "id": "runtime-contract",
        "path": "docs/runtime-contract.md",
        "owner": "runtime-contracts",
        "lifecycle": "live",
    }
    document.pop(field)

    with pytest.raises(ValueError, match=field):
        LiveGovernanceContract.model_validate(
            _contract_payload(documents=[document])
        )


def test_live_governance_contract_rejects_an_empty_registry() -> None:
    with pytest.raises(ValueError, match="at least one"):
        LiveGovernanceContract.model_validate(_contract_payload(documents=[]))


def test_run_artifact_manifest_requires_complete_artifact_set() -> None:
    contract = LiveGovernanceContract.model_validate(_contract_payload())
    manifest_payload = _run_manifest_payload()
    manifest_payload["artifacts"].pop("proof")

    with pytest.raises(ValueError, match="proof"):
        contract.validate_run_artifact_manifest(manifest_payload)


def test_run_artifact_manifest_requires_distinct_artifact_paths() -> None:
    contract = LiveGovernanceContract.model_validate(_contract_payload())
    manifest_payload = _run_manifest_payload()
    manifest_payload["artifacts"]["proof"] = "status.json"

    with pytest.raises(ValueError, match="unique"):
        contract.validate_run_artifact_manifest(manifest_payload)


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("commit_sha", "commit_sha"),
        ("execution_environment", "execution_environment"),
    ],
)
def test_run_artifact_manifest_requires_attribution_metadata(
    field: str,
    message: str,
) -> None:
    contract = LiveGovernanceContract.model_validate(_contract_payload())
    manifest_payload = _run_manifest_payload()
    manifest_payload.pop(field)

    with pytest.raises(ValueError, match=message):
        contract.validate_run_artifact_manifest(manifest_payload)


def test_run_artifact_manifest_must_use_the_declared_artifact_sink() -> None:
    contract = LiveGovernanceContract.model_validate(_contract_payload())
    manifest_payload = _run_manifest_payload()
    manifest_payload["artifact_root"] = "outputs/runtime/run-001"

    with pytest.raises(ValueError, match="artifact sink root"):
        contract.validate_run_artifact_manifest(manifest_payload)


@pytest.mark.parametrize(
    "artifact_path",
    ["/tmp/proof.json", "../proof.json", "C:proof.json", "."],
)
def test_run_artifact_manifest_rejects_artifacts_outside_the_run_root(
    artifact_path: str,
) -> None:
    contract = LiveGovernanceContract.model_validate(_contract_payload())
    manifest_payload = _run_manifest_payload()
    manifest_payload["artifacts"]["proof"] = artifact_path

    with pytest.raises(ValueError, match="relative"):
        contract.validate_run_artifact_manifest(manifest_payload)
