from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_SRC = REPO_ROOT / "packages" / "contracts" / "src"
GATE_PATH = REPO_ROOT / "scripts" / "verify" / "live-document-gate.py"
if str(CONTRACTS_SRC) not in sys.path:
    sys.path.insert(0, str(CONTRACTS_SRC))

from vgo_contracts import (  # noqa: E402
    load_live_governance_contract,
    validate_live_document_workspace,
)


def _load_gate():
    spec = importlib.util.spec_from_file_location("runtime_live_document_gate", GATE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {GATE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_repo_live_document_contract_is_executable() -> None:
    contract = load_live_governance_contract(REPO_ROOT)

    validated = validate_live_document_workspace(contract, REPO_ROOT)

    assert len(validated) <= 30
    assert contract.proof_retention.pull_request_days == 30
    assert contract.proof_retention.main_and_scheduled_days == 90
    assert contract.proof_retention.formal_release == "github_release"


def test_live_document_gate_rejects_new_unregistered_markdown() -> None:
    gate = _load_gate()

    try:
        gate.evaluate(REPO_ROOT, ["docs/new-unregistered-live-document.md"])
    except ValueError as exc:
        assert "not registered" in str(exc)
    else:
        raise AssertionError("unregistered governed Markdown should fail the gate")


def test_live_document_gate_cli_passes_for_the_current_workspace() -> None:
    completed = subprocess.run(
        [sys.executable, str(GATE_PATH), "--repo-root", str(REPO_ROOT)],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, completed.stderr
    assert '"result": "PASS"' in completed.stdout
