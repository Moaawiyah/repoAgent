"""Graph nodes map to their exact chunks, even for duplicate qualified names."""

from repoagent import RepoAgent, RetrievalStrategy, Settings
from repoagent.analysis.analyzer import RepositoryAnalyzer
from repoagent.domain.repository import RepositorySpec
from repoagent.graph.builder import RepositoryGraphBuilder
from repoagent.graph.expansion import GraphExpander
from repoagent.retrieval.chunking import CodeChunker
from repoagent.retrieval.models import RetrievalResult, RetrievalSource

SOURCE = '''
class Gauge:
    """Pressure telemetry dial."""

    @property
    def level(self):
        return read_sensor_quartz()

    @level.setter
    def level(self, value):
        write_actuator_basalt(value)


if FAST:
    def compute():
        return 1
else:
    def compute():
        return 1


def read_sensor_quartz():
    return 0


def write_actuator_basalt(value):
    return value
'''


def build(tmp_path):
    (tmp_path / "gauge.py").write_text(SOURCE, encoding="utf-8")
    analysis = RepositoryAnalyzer().analyze(RepositorySpec(source=str(tmp_path)))
    chunks = CodeChunker("repo").chunk(analysis, tmp_path)
    store = RepositoryGraphBuilder(chunks).build(analysis)
    return chunks, store, {c.node_id: c for c in chunks}


def test_every_duplicate_gets_its_own_chunk_and_node(tmp_path):
    chunks, store, by_node = build(tmp_path)
    getter, setter = by_node["gauge.Gauge.level"], by_node["gauge.Gauge.level#2"]
    assert getter.qualified_name == setter.qualified_name
    assert getter.start_line < setter.start_line
    for chunk in chunks:
        assert store.get_node(chunk.node_id).chunk_id == chunk.chunk_id


def test_identical_duplicate_sources_never_share_a_chunk_id(tmp_path):
    _, _, by_node = build(tmp_path)
    first, second = by_node["gauge.compute"], by_node["gauge.compute#2"]
    assert first.source.strip() == second.source.strip()
    assert first.chunk_id != second.chunk_id


def expand_from(store, chunks, chunk):
    seed = RetrievalResult(
        rank=1, score=1.0, source=RetrievalSource.HYBRID, chunk=chunk
    )
    return {r.chunk.node_id for r in GraphExpander(store, chunks).expand([seed], 10)}


def test_expansion_starts_from_the_exact_duplicate_node(tmp_path):
    chunks, store, by_node = build(tmp_path)
    from_getter = expand_from(store, chunks, by_node["gauge.Gauge.level"])
    from_setter = expand_from(store, chunks, by_node["gauge.Gauge.level#2"])
    assert "gauge.read_sensor_quartz" in from_getter
    assert "gauge.write_actuator_basalt" not in from_getter
    assert "gauge.write_actuator_basalt" in from_setter
    assert "gauge.read_sensor_quartz" not in from_setter


def test_both_duplicates_reachable_through_graph_expansion(tmp_path):
    chunks, store, by_node = build(tmp_path)
    reached = expand_from(store, chunks, by_node["gauge.Gauge"])
    assert {"gauge.Gauge.level", "gauge.Gauge.level#2"} <= reached


def test_hybrid_graph_search_retrieves_each_duplicate_independently(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "gauge.py").write_text(SOURCE, encoding="utf-8")
    # CONTAINS expansion (class -> both duplicates) is part of "legacy" only.
    settings = Settings(data_dir=tmp_path / "data", graph_policy="legacy")
    agent = RepoAgent(settings=settings)
    agent.index(repo)
    response = agent.search(
        repo, "pressure telemetry dial", strategy=RetrievalStrategy.HYBRID_GRAPH
    )
    by_node = {r.chunk.node_id: r for r in response.results}
    for node_id, line in (("gauge.Gauge.level", 6), ("gauge.Gauge.level#2", 10)):
        result = by_node[node_id]
        assert result.chunk.start_line == line
        graph = [e for e in result.evidence if e.kind == "graph"]
        assert graph and graph[0].path[-1].target_symbol == node_id
