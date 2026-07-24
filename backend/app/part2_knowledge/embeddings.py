import os
import uuid
import hashlib
import random
import logging
from typing import List, Dict, Any, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from backend.app.config import settings

logger = logging.getLogger("repoguard.part2.embeddings")

class CodeEmbeddingEngine:
    """Part 2: Code chunking and dense vector embedding generation with Qdrant indexing."""

    def __init__(self, model_name: str = "text-embedding-3-small"):
        self.model_name = model_name
        self.collection_name = "repoguard_code_chunks"
        self._transformer_model = None

        # Attempt connection to Qdrant server
        try:
            self.client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT, timeout=2.0)
            # Ping database to verify connection
            self.client.get_collections()
            logger.info("Connected to remote Qdrant database.")
        except Exception as e:
            logger.warning(f"Could not connect to Qdrant server ({settings.QDRANT_HOST}:{settings.QDRANT_PORT}). "
                           f"Falling back to local in-memory Qdrant client. Detail: {e}")
            self.client = QdrantClient(":memory:")

    def chunk_code(self, code: str, max_chunk_lines: int = 50, language: Optional[str] = None, filepath: Optional[str] = None) -> List[str]:
        """
        Chunks source code. Uses AST-aware block division for Python, 
        and falls back to line-based boundaries or standard size limits.
        """
        if not code or not code.strip():
            return []

        lines = code.split('\n')
        intervals = []

        # Attempt Python AST parsing to find logical block boundaries (functions, classes)
        if language == "python" or (filepath and filepath.endswith(".py")):
            try:
                import ast
                tree = ast.parse(code)
                for node in ast.iter_child_nodes(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        start = node.lineno - 1
                        end = getattr(node, "end_lineno", node.lineno)
                        intervals.append((start, end))
            except Exception:
                pass

        # If no AST intervals found, fall back to simple sliding line chunking
        if not intervals:
            chunks = []
            for i in range(0, len(lines), max_chunk_lines):
                chunk_text = '\n'.join(lines[i:i + max_chunk_lines])
                if chunk_text.strip():
                    chunks.append(chunk_text)
            return chunks

        # Sort and merge AST intervals
        intervals.sort(key=lambda x: x[0])
        chunks = []
        current_pos = 0

        for start, end in intervals:
            # First, chunk any lines preceding the current AST block
            if start > current_pos:
                slice_lines = lines[current_pos:start]
                for i in range(0, len(slice_lines), max_chunk_lines):
                    chunk_text = '\n'.join(slice_lines[i:i + max_chunk_lines])
                    if chunk_text.strip():
                        chunks.append(chunk_text)

            # Then chunk the actual AST block
            slice_lines = lines[start:end]
            for i in range(0, len(slice_lines), max_chunk_lines):
                chunk_text = '\n'.join(slice_lines[i:i + max_chunk_lines])
                if chunk_text.strip():
                    chunks.append(chunk_text)
            current_pos = end

            # Chunk any remaining lines after the last AST block
        if current_pos < len(lines):
            slice_lines = lines[current_pos:]
            for i in range(0, len(slice_lines), max_chunk_lines):
                chunk_text = '\n'.join(slice_lines[i:i + max_chunk_lines])
                if chunk_text.strip():
                    chunks.append(chunk_text)

        return chunks

    def generate_embeddings(self, chunks: List[str]) -> List[List[float]]:
        """Generates embedding vectors for code chunks using OpenAI or SentenceTransformers with mock fallback."""
        if not chunks:
            return []

        # 1. Try OpenAI API if enabled
        if self.model_name == "text-embedding-3-small" and settings.OPENAI_API_KEY:
            try:
                from openai import OpenAI
                openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
                response = openai_client.embeddings.create(input=chunks, model=self.model_name)
                return [item.embedding for item in response.data]
            except Exception as e:
                logger.warning(f"OpenAI API failed: {e}. Trying local SentenceTransformer.")

        # 2. Try SentenceTransformers local model
        try:
            from sentence_transformers import SentenceTransformer
            if self._transformer_model is None:
                self._transformer_model = SentenceTransformer("all-MiniLM-L6-v2")
            embeddings = self._transformer_model.encode(chunks)
            return [emb.tolist() for emb in embeddings]
        except Exception as e:
            logger.warning(f"SentenceTransformer failed: {e}. Falling back to deterministic mock vectors.")

        # 3. Deterministic mock fallback (stable dimension based on configuration)
        dim = 1536 if "3-small" in self.model_name else 384
        results = []
        for chunk in chunks:
            h = hashlib.sha256(chunk.encode("utf-8")).digest()
            rng = random.Random(int.from_bytes(h, "big"))
            results.append([rng.uniform(-0.1, 0.1) for _ in range(dim)])
        return results

    def _ensure_collection(self, vector_size: int):
        """Creates the collection in Qdrant if it does not exist."""
        try:
            collections = [c.name for c in self.client.get_collections().collections]
            if self.collection_name not in collections:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=qmodels.VectorParams(
                        size=vector_size,
                        distance=qmodels.Distance.COSINE
                    )
                )
        except Exception as e:
            logger.error(f"Failed to verify or create Qdrant collection: {e}")

    def upsert_chunks(self, filepath: str, chunks: List[str], embeddings: List[List[float]]):
        """Indexes code chunks and their embeddings in Qdrant."""
        if not chunks or not embeddings:
            return

        vector_size = len(embeddings[0])
        self._ensure_collection(vector_size)

        points = []
        for idx, (chunk, vector) in enumerate(zip(chunks, embeddings)):
            # Deterministic ID to prevent duplication on multiple scans
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{filepath}_{idx}"))
            points.append(
                qmodels.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "filepath": filepath,
                        "content": chunk,
                        "chunk_index": idx
                    }
                )
            )

        try:
            self.client.upsert(collection_name=self.collection_name, points=points)
        except Exception as e:
            logger.error(f"Error upserting points to Qdrant: {e}")

    def search_similar(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Searches Qdrant for semantic similarity using the modern query_points API."""
        if not query:
            return []

        query_vector = self.generate_embeddings([query])[0]

        try:
            collections = [c.name for c in self.client.get_collections().collections]
            if self.collection_name not in collections:
                return []

            result = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=top_k,
                with_payload=True
            )
            return [
                {
                    "id": hit.id,
                    "filepath": hit.payload.get("filepath", ""),
                    "content": hit.payload.get("content", ""),
                    "chunk_index": hit.payload.get("chunk_index", 0),
                    "score": hit.score
                }
                for hit in result.points
            ]
        except Exception as e:
            logger.error(f"Failed semantic query on Qdrant: {e}")
            return []
