"""Human-readable presentation of a repository analysis."""

from repoagent.analysis.results import RepositoryAnalysis


def render_analysis(analysis: RepositoryAnalysis) -> str:
    """Render a developer-friendly text summary."""
    lines = [
        "RepoAgent Repository Analysis",
        "",
        f"Repository: {analysis.repository_name}",
        f"Root: {analysis.repository_root}",
        f"Discovered files: {analysis.discovered_files}",
        f"Python files: {analysis.python_files}",
        f"Classes: {analysis.class_count}",
        f"Functions: {analysis.function_count}",
        f"Methods: {analysis.method_count}",
        f"Tests: {analysis.test_count}",
    ]
    if analysis.errors:
        lines.append(f"File errors: {len(analysis.errors)}")
    lines.append("")
    lines.append("Modules:")
    lines.extend(f"* {module}" for module in analysis.modules)
    return "\n".join(lines)
