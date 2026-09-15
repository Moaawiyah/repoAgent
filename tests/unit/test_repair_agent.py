"""M6 Developer/Validator/Reviewer graph routing with test-only providers."""

from pathlib import Path

from repoagent import RepoAgent, Settings
from repoagent.ai.provider import CompletionResult
from repoagent.domain.repair import RepairStatus
from tests.support.repair_provider import DIFF, RepairProvider

ROOT = Path(__file__).resolve().parents[1] / "fixtures/auth_bug"
ISSUE = "Users with uppercase email addresses cannot log in"


def repair(tmp_path, provider, **kwargs):
    client = RepoAgent(settings=Settings(data_dir=tmp_path / "data"))
    client.index(ROOT)
    return client.repair(ROOT, ISSUE, provider=provider, **kwargs)


def test_developer_validator_reviewer_approve(tmp_path):
    report = repair(tmp_path, RepairProvider())
    assert report.status == RepairStatus.APPROVED_FOR_RUNTIME_VALIDATION
    assert report.validation.valid and report.reviews[-1].decision == "approve"
    assert "email" in report.proposal.unified_diff


def test_revise_loops_to_developer_then_approves(tmp_path):
    provider = RepairProvider(decisions=("revise", "approve"))
    report = repair(tmp_path, provider, max_revisions=2)
    assert report.status == RepairStatus.APPROVED_FOR_RUNTIME_VALIDATION
    assert report.revisions == 1 and len(report.reviews) == 2
    assert [r.prompt_name for r in provider.requests].count("patch_proposal") == 2


def test_reviewer_rejection_is_terminal(tmp_path):
    report = repair(tmp_path, RepairProvider(decisions=("reject",)))
    assert report.status == RepairStatus.REJECTED
    assert report.revisions == 0


def test_max_revisions_is_explicit(tmp_path):
    report = repair(tmp_path, RepairProvider(decisions=("revise",)), max_revisions=0)
    assert report.status == RepairStatus.MAX_REVISIONS
    assert len(report.reviews) == 1


def test_insufficient_investigation_never_proposes_patch(tmp_path):
    report = repair(tmp_path, RepairProvider(rounds=10))
    assert report.status == RepairStatus.INSUFFICIENT_INVESTIGATION
    assert report.proposal is None and not report.reviews


def test_bad_patch_rejected_before_model_review(tmp_path):
    report = repair(tmp_path, RepairProvider(patch="not a diff"))
    assert report.status == RepairStatus.REJECTED
    assert not report.validation.valid and report.reviews[-1].decision == "reject"


def test_repair_does_not_change_target(tmp_path):
    target = ROOT / "app/users/repository.py"
    before = target.read_bytes()
    report = repair(tmp_path, RepairProvider())
    assert report.validation.valid and target.read_bytes() == before
    assert DIFF == report.proposal.unified_diff


def test_developer_failure_short_circuits_with_its_own_message(tmp_path):
    """Validate/review must not run after a failed Developer call and
    overwrite its specific error with a generic downstream symptom."""

    class BrokenDeveloper(RepairProvider):
        def complete(self, request):
            if request.prompt_name == "patch_proposal":
                self.requests.append(request)
                return CompletionResult(text="not json", model=self.name)
            return super().complete(request)

    report = repair(tmp_path, BrokenDeveloper())
    assert report.status == RepairStatus.PROVIDER_ERROR
    assert report.error == "Developer output failed validation"
    assert report.proposal is None and report.validation is None and not report.reviews
