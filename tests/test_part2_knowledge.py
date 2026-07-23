from backend.app.part2_knowledge.graph_builder import KnowledgeGraphBuilder
from backend.app.part2_knowledge.embeddings import CodeEmbeddingEngine

def test_knowledge_graph_builder():
    builder = KnowledgeGraphBuilder()
    builder.add_dependency("modA", "modB")
    stats = builder.get_graph_stats()
    assert stats["nodes"] == 2
    assert stats["edges"] == 1

def test_code_chunker():
    engine = CodeEmbeddingEngine()
    code = "\n".join([f"line_{i}" for i in range(120)])
    chunks = engine.chunk_code(code, max_chunk_lines=50)
    assert len(chunks) == 3
