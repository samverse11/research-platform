"""
Optional:  Vector database integration using FAISS for scalable semantic search.
Only needed if you want to persist embeddings and search millions of papers. 

Install:  pip install faiss-cpu (or faiss-gpu)
"""

import faiss
import numpy as np
import pickle
from pathlib import Path
from typing import List, Tuple, Optional
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
        self.papers:  List[Paper] = []
        self.index_path = Path(settings.VECTOR_DB_PATH)
        self.index_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize or load index
        self._initialize_index()
    
    def _initialize_index(self):
        """Initialize or load existing FAISS index"""
        index_file = self.index_path / "papers.index"
        metadata_file = self.index_path / "papers.pkl"
        
        if index_file.exists() and metadata_file.exists():
            # Load existing index
            print(f"📂 Loading existing vector store from {self.index_path}")
            self.index = faiss.read_index(str(index_file))
            with open(metadata_file, 'rb') as f:
                self.papers = pickle.load(f)
            print(f"✅ Loaded {len(self.papers)} papers from vector store")
        else:
            # Create new index
            print("🆕 Creating new FAISS index")
            # Using IndexFlatIP for inner product (cosine similarity with normalized vectors)
            self.index = faiss.IndexFlatIP(self.dimension)
            self.papers = []
    
    def add_papers(self, papers: List[Paper], embeddings: np.ndarray):
        """
        Add papers and their embeddings to the vector store. 
        
        Args:
            papers: List of Paper objects
            embeddings: Numpy array of shape [num_papers, dimension]
        """
        if len(papers) != embeddings.shape[0]:
            raise ValueError("Number of papers must match number of embeddings")
        
        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(embeddings)
        
        # Add to index
        self.index.add(embeddings.astype('float32'))
        self.papers.extend(papers)
        
        print(f"➕ Added {len(papers)} papers to vector store (total: {len(self.papers)})")
    
    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10
    ) -> List[RankedPaper]:
        """
        Search for similar papers using query embedding.
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            
        Returns: 
            List of RankedPaper objects with similarity scores
        """
        if self.index. ntotal == 0:
            return []
        
        # Normalize query
        query_embedding = query_embedding.reshape(1, -1).astype('float32')
        faiss.normalize_L2(query_embedding)
        
        # Search
        similarities, indices = self.index.search(query_embedding, min(top_k, self.index.ntotal))
        
        # Convert to RankedPaper objects
        ranked_papers = []
        for rank, (idx, score) in enumerate(zip(indices[0], similarities[0]), start=1):
            if idx < len(self.papers):
                paper = self.papers[idx]
                ranked_paper = RankedPaper(
                    **paper.model_dump(),
                    similarity_score=float(score),
                    rank=rank
                )
                ranked_papers.append(ranked_paper)
        
        return ranked_papers
    
    def save(self):
        """Save index and metadata to disk"""
        index_file = self.index_path / "papers.index"
        metadata_file = self.index_path / "papers.pkl"
        
        faiss.write_index(self. index, str(index_file))
        with open(metadata_file, 'wb') as f:
            pickle.dump(self.papers, f)
        
        print(f"💾 Saved vector store to {self.index_path}")
    
    def clear(self):
        """Clear the index and papers"""
        self.index. reset()
        self.papers = []
        print("🗑️ Cleared vector store")
    
    def get_stats(self) -> dict:
        """Get statistics about the vector store"""
        return {
            "total_papers": len(self. papers),
            "index_size": self.index.ntotal,
            "dimension": self.dimension,
            "index_type": type(self.index).__name__
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