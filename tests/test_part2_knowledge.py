import pytest
import textwrap
from backend.app.part2_knowledge.graph_builder import KnowledgeGraphBuilder
from backend.app.part2_knowledge.embeddings import CodeEmbeddingEngine
from backend.app.part2_knowledge.hybrid_retrieval import HybridRAGRetriever

def test_knowledge_graph_builder():
    builder = KnowledgeGraphBuilder()
    # Test adding basic module dependencies
    builder.add_dependency("modA", "modB")
    stats = builder.get_graph_stats()
    assert stats["nodes"] == 2
    assert stats["edges"] == 1
    assert stats["is_dag"] is True

    # Test adding more dependencies to verify topological properties
    builder.add_dependency("modB", "modC")
    builder.add_dependency("modC", "modA") # Introduces a cycle
    
    stats2 = builder.get_graph_stats()
    assert stats2["is_dag"] is False
    assert stats2["has_circular_deps"] is True
    assert len(stats2["circular_dependencies"]) >= 1

    # Test neighbor lookup
    successors = builder.get_neighbors("modA", direction="out")
    assert "modB" in successors

    predecessors = builder.get_neighbors("modA", direction="in")
    assert "modC" in predecessors

    # Test shortest path computation
    builder2 = KnowledgeGraphBuilder()
    builder2.add_dependency("A", "B")
    builder2.add_dependency("B", "C")
    path = builder2.get_shortest_path("A", "C")
    assert path == ["A", "B", "C"]

def test_code_chunker_sliding_window():
    engine = CodeEmbeddingEngine()
    # 120 lines total, split every 50 lines -> 3 chunks
    code = "\n".join([f"line_{i}" for i in range(120)])
    chunks = engine.chunk_code(code, max_chunk_lines=50)
    assert len(chunks) == 3
    assert chunks[0].startswith("line_0")
    assert chunks[1].startswith("line_50")
    assert chunks[2].startswith("line_100")

def test_code_chunker_ast_aware():
    engine = CodeEmbeddingEngine()
    python_code = textwrap.dedent("""\
        # Preceding module level comment
        x = 42

        def compute_sum(a, b):
            \"\"\"Adds two numbers.\"\"\"
            result = a + b
            return result

        class Calculator:
            def __init__(self):
                self.value = 0

            def add(self, x):
                self.value += x
    """)
    
    # Chunk with Python language mode
    chunks = engine.chunk_code(python_code, max_chunk_lines=15, language="python")
    
    # Should identify compute_sum function block and Calculator class block
    assert len(chunks) >= 2
    
    # Make sure function definition and class definition are preserved in chunks
    func_chunk_found = any("def compute_sum" in c for c in chunks)
    class_chunk_found = any("class Calculator" in c for c in chunks)
    assert func_chunk_found is True
    assert class_chunk_found is True

def test_code_embedding_generation_and_upsert():
    engine = CodeEmbeddingEngine()
    chunks = ["def foo(): pass", "class Bar: pass"]
    
    # Generate embeddings (will fallback to mock or sentence-transformers)
    embeddings = engine.generate_embeddings(chunks)
    assert len(embeddings) == len(chunks)
    assert len(embeddings[0]) in (384, 1536) # depending on sentence-transformers or mock/openai fallback
    
    # Test indexing in memory client
    filepath = "src/utils.py"
    engine.upsert_chunks(filepath, chunks, embeddings)
    
    # Test semantic retrieval
    hits = engine.search_similar("foo function", top_k=2)
    assert len(hits) > 0
    assert any(h["filepath"] == filepath for h in hits)
    assert any("foo" in h["content"] for h in hits)

def test_hybrid_rag_retriever():
    vector_store = CodeEmbeddingEngine()
    knowledge_graph = KnowledgeGraphBuilder()

    # main.py chunks — semantically about "workflow orchestration"
    # These will match the query directly via vector/BM25.
    chunks_a = [
        "def orchestrate_workflow(steps): return [s() for s in steps]",
        "class WorkflowEngine: pass  # manages orchestration pipelines"
    ]
    embeddings_a = vector_store.generate_embeddings(chunks_a)
    vector_store.upsert_chunks("backend/app/part2_knowledge/main.py", chunks_a, embeddings_a)

    # ast_analyzer.py chunks — semantically about "database schema models"
    # These are deliberately unrelated to the query so they will NOT appear
    # as direct semantic/BM25 hits — only reachable via graph expansion.
    chunks_b = [
        "class SchemaModel(BaseModel): id = Column(Integer)",
        "def migrate_database(engine): engine.execute(schema.create_all)"
    ]
    embeddings_b = vector_store.generate_embeddings(chunks_b)
    vector_store.upsert_chunks("backend/app/part1_parser/ast_analyzer.py", chunks_b, embeddings_b)

    # main.py imports ast_analyzer.py in the knowledge graph
    knowledge_graph.add_dependency(
        "backend.app.part2_knowledge.main",
        "backend.app.part1_parser.ast_analyzer",
        "IMPORTS"
    )

    retriever = HybridRAGRetriever(vector_store=vector_store, knowledge_graph=knowledge_graph)

    # Query only matches main.py (workflow/orchestration); ast_analyzer.py is semantically distant.
    results = retriever.search("workflow orchestration pipeline", top_k=2)

    # Primary results must exist and be tagged with a hybrid retrieval method.
    assert len(results) > 0
    assert any(r["retrieval_method"].startswith("hybrid_") for r in results)

    # ast_analyzer.py chunks must appear via graph expansion from main.py → ast_analyzer.py.
    has_expansion = any(r["retrieval_method"] == "graph_expansion" for r in results)
    assert has_expansion is True
