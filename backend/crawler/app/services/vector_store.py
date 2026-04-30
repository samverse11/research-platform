"""
Optional: Vector database integration using FAISS for scalable semantic search.
Only needed if you want to persist embeddings and search millions of papers.

Install: pip install faiss-cpu (or faiss-gpu)
"""

import faiss
import numpy as np
import pickle
import re
from pathlib import Path
from typing import List, Optional, Set

from crawler.app.models import Paper, RankedPaper
from crawler.app.config import get_settings

settings = get_settings()


class VectorStore:
    """
    FAISS-based vector store for efficient similarity search.
    Stores paper embeddings and metadata for fast retrieval.
    """

    def __init__(self, dimension: int = 768):
        self.dimension = dimension
        self.index = None
        self.papers: List[Paper] = []
        self.seen_keys: Set[str] = set()

        self.index_path = Path(settings.VECTOR_DB_PATH)
        self.index_path.mkdir(parents=True, exist_ok=True)

        # Initialize or load index
        self._initialize_index()

    def _normalize_text(self, text: str) -> str:
        text = (text or "").strip().lower()
        text = re.sub(r"\s+", " ", text)
        return text

    def _paper_key(self, paper: Paper) -> str:
        # Best: DOI (stable across sources)
        if paper.doi:
            return "doi:" + self._normalize_text(paper.doi)

        # Fallback: title + year (good enough for most dedup)
        title = self._normalize_text(paper.title)
        year = str(paper.year or "")
        return f"title_year:{title}|{year}"

    def _initialize_index(self):
        """Initialize or load existing FAISS index"""
        index_file = self.index_path / "papers.index"
        metadata_file = self.index_path / "papers.pkl"

        if index_file.exists() and metadata_file.exists():
            # Load existing index
            print(f"📂 Loading existing vector store from {self.index_path}")
            self.index = faiss.read_index(str(index_file))

            with open(metadata_file, "rb") as f:
                payload = pickle.load(f)

            # Backward compatible: old file stored only a list of papers
            if isinstance(payload, list):
                self.papers = payload
                self.seen_keys = {self._paper_key(p) for p in self.papers}
            else:
                self.papers = payload.get("papers", [])
                self.seen_keys = set(payload.get("seen_keys", []))

            print(f"✅ Loaded {len(self.papers)} papers from vector store")
        else:
            # Create new index
            print("🆕 Creating new FAISS index")
            # Using IndexFlatIP for inner product (cosine similarity with normalized vectors)
            self.index = faiss.IndexFlatIP(self.dimension)
            self.papers = []
            self.seen_keys = set()

    def add_papers(self, papers: List[Paper], embeddings: np.ndarray):
        """
        Add papers and their embeddings to the vector store, skipping duplicates.

        Args:
            papers: List of Paper objects
            embeddings: Numpy array of shape [num_papers, dimension]
        """
        if len(papers) != embeddings.shape[0]:
            raise ValueError("Number of papers must match number of embeddings")

        # Filter duplicates while keeping embeddings aligned
        kept_papers: List[Paper] = []
        kept_rows: List[int] = []

        for i, p in enumerate(papers):
            key = self._paper_key(p)
            if key in self.seen_keys:
                continue
            self.seen_keys.add(key)
            kept_papers.append(p)
            kept_rows.append(i)

        if not kept_papers:
            print("♻️ No new papers to add (all duplicates)")
            return

        kept_embeddings = embeddings[kept_rows]

        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(kept_embeddings)

        # Add to index
        self.index.add(kept_embeddings.astype("float32"))
        self.papers.extend(kept_papers)

        print(
            f"➕ Added {len(kept_papers)} new papers (skipped {len(papers) - len(kept_papers)} dups). "
            f"Total: {len(self.papers)}"
        )

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        sources: Optional[List[str]] = None,
    ) -> List[RankedPaper]:
        """
        Search for similar papers using query embedding.

        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            sources: If provided, only return papers from these sources.
                     Over-fetches from FAISS then filters in Python.

        Returns:
            List of RankedPaper objects with similarity scores
        """
        if self.index.ntotal == 0:
            return []

        # Normalize query
        query_embedding = query_embedding.reshape(1, -1).astype("float32")
        faiss.normalize_L2(query_embedding)

        # When source-filtering, over-fetch so we still get top_k after filtering.
        # Cap at index total to avoid FAISS errors.
        source_set = set(sources) if sources else None
        fetch_k = min(
            top_k * 4 if source_set else top_k,
            self.index.ntotal,
        )

        similarities, indices = self.index.search(query_embedding, fetch_k)

        # Convert to RankedPaper objects, applying source filter
        ranked_papers: List[RankedPaper] = []
        rank = 1
        for idx, score in zip(indices[0], similarities[0]):
            if idx >= len(self.papers):
                continue
            paper = self.papers[idx]
            if source_set and paper.source not in source_set:
                continue  # skip papers from sources not in this request
            ranked_papers.append(
                RankedPaper(
                    **paper.model_dump(),
                    similarity_score=float(score),
                    rank=rank,
                )
            )
            rank += 1
            if len(ranked_papers) >= top_k:
                break

        return ranked_papers

    def save(self):
        """Save index and metadata to disk"""
        index_file = self.index_path / "papers.index"
        metadata_file = self.index_path / "papers.pkl"

        faiss.write_index(self.index, str(index_file))
        with open(metadata_file, "wb") as f:
            pickle.dump({"papers": self.papers, "seen_keys": list(self.seen_keys)}, f)

        print(f"💾 Saved vector store to {self.index_path}")

    def clear(self):
        """Clear the index and papers"""
        self.index.reset()
        self.papers = []
        self.seen_keys = set()
        print("🗑️ Cleared vector store")

    def get_stats(self) -> dict:
        """Get statistics about the vector store"""
        return {
            "total_papers": len(self.papers),
            "index_size": self.index.ntotal,
            "dimension": self.dimension,
            "index_type": type(self.index).__name__,
        }


# Singleton instance
_vector_store_instance = None


def get_vector_store() -> Optional[VectorStore]:
    """Get singleton instance of vector store (if enabled)"""
    if not settings.USE_VECTOR_DB:
        return None

    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStore(dimension=settings.EMBEDDING_DIMENSION)
    return _vector_store_instance