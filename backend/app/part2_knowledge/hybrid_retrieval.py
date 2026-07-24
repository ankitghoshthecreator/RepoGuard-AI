import math
import logging
from collections import Counter
from typing import List, Dict, Any, Tuple

from .embeddings import CodeEmbeddingEngine
from .graph_builder import KnowledgeGraphBuilder

logger = logging.getLogger("repoguard.part2.hybrid_retrieval")

class MiniBM25:
    """A lightweight, zero-dependency implementation of the BM25 scoring algorithm for local text search."""

    def __init__(self, corpus: List[Dict[str, Any]], k1: float = 1.5, b: float = 0.75):
        self.corpus = corpus
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.doc_lengths = [len(doc["content"].lower().split()) for doc in corpus]
        self.avg_doc_len = sum(self.doc_lengths) / self.corpus_size if self.corpus_size > 0 else 1.0

        # Calculate Document Frequencies (DF)
        self.df = Counter()
        for doc in corpus:
            words = set(doc["content"].lower().split())
            for w in words:
                self.df[w] += 1

    def score(self, query: str) -> List[Tuple[Dict[str, Any], float]]:
        """Scores all corpus documents against a query string."""
        query_words = query.lower().split()
        scored_docs = []

        for idx, doc in enumerate(self.corpus):
            doc_words = doc["content"].lower().split()
            doc_len = len(doc_words)
            word_counts = Counter(doc_words)

            score = 0.0
            for word in query_words:
                if word not in self.df:
                    continue
                
                # IDF formula with smoothing
                df_w = self.df[word]
                idf = math.log((self.corpus_size - df_w + 0.5) / (df_w + 0.5) + 1.0)

                # Term frequency in document
                tf = word_counts[word]

                # BM25 TF adjustment
                tf_adj = (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * (doc_len / self.avg_doc_len)))
                score += idf * tf_adj
                
            scored_docs.append((doc, score))
        return scored_docs


class HybridRAGRetriever:
    """Part 2: Hybrid RAG retriever combining vector search, BM25 keyword matching, and graph topology traversal."""

    def __init__(self, vector_store: CodeEmbeddingEngine = None, knowledge_graph: KnowledgeGraphBuilder = None):
        self.vector_store = vector_store or CodeEmbeddingEngine()
        self.knowledge_graph = knowledge_graph or KnowledgeGraphBuilder()

    def _filepath_to_module(self, filepath: str) -> str:
        """Converts local file paths into dot-separated module notation."""
        p = filepath.replace("\\", "/")
        if p.endswith(".py"):
            p = p[:-3]
        return p.replace("/", ".")

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Performs multi-modal hybrid retrieval for code context.
        Combines Dense Semantic search with Sparse BM25 keyword search,
        fuses ranks via RRF, and performs Graph Expansion to fetch neighboring contexts.
        """
        if not query or not query.strip():
            return []

        # 1. Semantic Vector Search
        vector_results = self.vector_store.search_similar(query, top_k=top_k * 3)
        vector_ranking = {hit["id"]: hit for hit in vector_results}

        # 2. Scroll/Fetch Indexed Chunks for Sparse BM25 Keyword Search
        try:
            scroll_res = self.vector_store.client.scroll(
                collection_name=self.vector_store.collection_name,
                limit=10000,
                with_payload=True,
                with_vectors=False
            )
            records = scroll_res[0]
        except Exception as e:
            logger.warning(f"Could not scroll Qdrant points for BM25: {e}")
            records = []

        all_chunks = []
        for r in records:
            all_chunks.append({
                "id": r.id,
                "filepath": r.payload.get("filepath", ""),
                "content": r.payload.get("content", ""),
                "chunk_index": r.payload.get("chunk_index", 0)
            })

        # 3. BM25 Keyword Matching
        bm25_results = []
        if all_chunks:
            bm25_engine = MiniBM25(all_chunks)
            bm25_scored = bm25_engine.score(query)
            bm25_scored.sort(key=lambda x: x[1], reverse=True)
            # Only keep documents with a non-zero BM25 score
            bm25_results = [item[0] for item in bm25_scored if item[1] > 0]
        
        # 4. Reciprocal Rank Fusion (RRF)
        # RRF formula: Score(d) = sum( 1 / (k + rank_i(d)) )
        k_const = 60
        vector_ranks = {item["id"]: idx + 1 for idx, item in enumerate(vector_results)}
        bm25_ranks = {item["id"]: idx + 1 for idx, item in enumerate(bm25_results)}

        candidate_ids = set(vector_ranks.keys()).union(set(bm25_ranks.keys()))
        rrf_scores = {}

        for cid in candidate_ids:
            score = 0.0
            methods = []
            if cid in vector_ranks:
                score += 1.0 / (k_const + vector_ranks[cid])
                methods.append("vector")
            if cid in bm25_ranks:
                score += 1.0 / (k_const + bm25_ranks[cid])
                methods.append("bm25")

            rrf_scores[cid] = (score, "+".join(methods))

        # Sort candidates by RRF score descending
        sorted_candidates = sorted(candidate_ids, key=lambda x: rrf_scores[x][0], reverse=True)

        # Merge results metadata
        merged_results = []
        for cid in sorted_candidates:
            record = None
            if cid in vector_ranking:
                record = vector_ranking[cid]
            else:
                for doc in all_chunks:
                    if doc["id"] == cid:
                        record = doc
                        break

            if record:
                rrf_val, method_tag = rrf_scores[cid]
                # Normalize RRF value to a 0-1 score scale for UI consistency
                # Rank 1 in both yields max possible RRF: 2 / 61 = 0.032786
                max_possible_rrf = 2.0 / (k_const + 1)
                normalized_score = min(rrf_val / max_possible_rrf, 1.0)

                merged_results.append({
                    "id": cid,
                    "source_file": record.get("filepath", record.get("source_file", "")),
                    "score": round(normalized_score, 4),
                    "content": record["content"],
                    "retrieval_method": f"hybrid_{method_tag}"
                })

        top_results = merged_results[:top_k]

        # 5. Graph-Based Context Expansion
        # For top retrieved files, find neighboring modules in the import tree.
        # Deduplication is done by chunk ID so that a neighbor file's other chunks
        # can still be added even if one of its chunks was already matched directly.
        expansion_results = []
        existing_ids = {item["id"] for item in top_results}

        for item in top_results:
            filepath = item["source_file"]
            module_name = self._filepath_to_module(filepath)

            # Get successors (modules this file imports) and predecessors (modules that import this file)
            neighbors = self.knowledge_graph.get_neighbors(module_name, direction="out") + \
                        self.knowledge_graph.get_neighbors(module_name, direction="in")

            for neighbor_mod in neighbors:
                # Find ALL indexed chunks from the neighbor module
                neighbor_chunks = [
                    c for c in all_chunks
                    if self._filepath_to_module(c["filepath"]) == neighbor_mod
                ]

                for nc in neighbor_chunks:
                    # Only add if not already in primary results and not already in expansion set
                    if nc["id"] not in existing_ids and not any(x["id"] == nc["id"] for x in expansion_results):
                        expansion_results.append({
                            "id": nc["id"],
                            "source_file": nc["filepath"],
                            "score": round(item["score"] * 0.8, 4),  # small score discount for traversal
                            "content": nc["content"],
                            "retrieval_method": "graph_expansion"
                        })

        # Append expansion context items (up to top_k / 2 additional chunks)
        top_results.extend(expansion_results[:max(1, top_k // 2)])

        return top_results
