"""All optional SDK capability mixins, combined for the public facade."""

from repoagent.sdk.audit_capability import AuditCapability
from repoagent.sdk.benchmark_capability import BenchmarkCapability
from repoagent.sdk.repair_capability import RepairCapability
from repoagent.sdk.workflow_capability import WorkflowCapability


class Capabilities(
    RepairCapability, BenchmarkCapability, AuditCapability, WorkflowCapability
):
    """Repair, benchmark, audit and workflow use cases (see each mixin)."""
