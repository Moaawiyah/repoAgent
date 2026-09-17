"""AuditService end-to-end: discovery, dedupe, evidence, verification, repair."""

import hashlib
from pathlib import Path

from repoagent.adapters.index_store import JsonIndexStore
from repoagent.application.audit import AuditRequest, AuditService
from repoagent.application.audit_repair import RepairService
from repoagent.domain.investigation import InvestigationReport
from repoagent.domain.repair import RepairReport, RepairStatus
from repoagent.retrieval.embeddings import HashingEmbeddingProvider
from tests.support.scripted import ScriptedLLMProvider

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "audit_repo"
_RESPONSES = [
    {"status": "verified", "reasoning": "TODO left unresolved.", "confidence": 0.6},
    {
        "status": "verified",
        "reasoning": "Cycle confirmed by imports.",
        "confidence": 0.9,
    },
    {
        "status": "uncertain",
        "reasoning": "Cannot confirm reachability.",
        "confidence": 0.4,
    },
    {"status": "rejected", "reasoning": "Literal is safe here.", "confidence": 0.8},
]


def _fingerprint(root: Path) -> dict[str, str]:
    return {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*.py"))
    }


def _service(tmp_path, responses) -> tuple[AuditService, ScriptedLLMProvider]:
    store = JsonIndexStore(tmp_path / "idx")
    embedding = HashingEmbeddingProvider(64)
    provider = ScriptedLLMProvider(responses)
    return AuditService(store, embedding, provider), provider


def test_audit_discovers_verifies_and_never_modifies_the_repository(tmp_path):
    before = _fingerprint(FIXTURE)
    service, _ = _service(tmp_path, list(_RESPONSES))
    report = service.audit(AuditRequest(repository=str(FIXTURE), limit=4))

    assert report.files_scanned == 6
    assert report.metrics.candidates_generated == 9
    assert len(report.candidates) == 4
    assert report.metrics.verified == 2
    assert report.metrics.uncertain == 1
    assert report.metrics.rejected == 1
    assert report.metrics.verification_llm_calls == 4
    assert _fingerprint(FIXTURE) == before


def test_repair_flag_without_a_verified_candidate_skips_repair(tmp_path):
    responses = [{"status": "rejected", "reasoning": "no", "confidence": 0.9}] * 4
    service, _ = _service(tmp_path, responses)
    report = service.audit(AuditRequest(repository=str(FIXTURE), limit=4, repair=True))
    assert report.repair is None
    assert report.metrics.repair_status == "no_verified_candidate"


def test_repair_flag_converts_best_verified_candidate_into_existing_issue(
    tmp_path, monkeypatch
):
    captured = {}

    def fake_repair(self, request):
        captured["issue"] = request.issue
        investigation = InvestigationReport(
            task_id="t",
            repository=request.repository,
            issue=request.issue,
            issue_summary="s",
        )
        return RepairReport(investigation=investigation, status=RepairStatus.REJECTED)

    monkeypatch.setattr(RepairService, "repair", fake_repair)
    service, _ = _service(tmp_path, list(_RESPONSES))
    report = service.audit(AuditRequest(repository=str(FIXTURE), limit=4, repair=True))

    assert report.repair is not None
    assert report.repair.status == "rejected"
    assert report.metrics.repair_status == "rejected"
    assert "Circular module dependency" in captured["issue"].title
