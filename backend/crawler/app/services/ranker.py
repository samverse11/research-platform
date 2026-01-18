import numpy as np
from typing import List
from sklearn.metrics.pairwise import cosine_similarity
from crawler.app.models import Paper, RankedPaper
from crawler.app.services.embeddings import get_embedding_service
from crawler.app.config import get_settings

settings = get_settings()

class SemanticRanker:
    """
    Semantic ranking using cosine similarity.
    Does NOT reuse RESP's ranking logic - pure semantic search.
    """
    
    def __init__(self):
        self.embedding_service = get_embedding_service()
    
    def rank_papers(
        self,
        query: str,
        papers: List[Paper],
        top_k: int = 10
    ) -> List[RankedPaper]:
        """
        Rank papers by semantic similarity to query.
        
        Process: 
        1. Encode query into embedding
        2. Encode paper texts (title + abstract) into embeddings
        3. Compute cosine similarity between query and papers
        4. Sort by similarity and return top-k
        
        Args: 
            query: User search query
            papers: List of papers to rank
            top_k:  Number of top results to return
            
        Returns: 
            List of RankedPaper objects sorted by similarity
        """
        if not papers:
            return []
        
        # Step 1: Encode query
        print(f"🔍 Encoding query: '{query[: 50]}...'")
        query_embedding = self.embedding_service. encode_query(query)
        
        # Step 2: Prepare paper texts
        paper_texts = [self._create_paper_text(paper) for paper in papers]
        
        # Step 3: Encode papers
        print(f"📄 Encoding {len(papers)} papers...")
        paper_embeddings = self.embedding_service.encode_documents(paper_texts)
        
        # Step 4: Compute similarities
        similarities = self._compute_similarities(query_embedding, paper_embeddings)
        
        # Step 5: Rank and filter
        ranked_papers = self._rank_and_filter(papers, similarities, top_k)
        
        print(f"✅ Ranked {len(ranked_papers)} papers (Top-{top_k})")
        return ranked_papers
    
    def _create_paper_text(self, paper: Paper) -> str:
        """Create searchable text from paper (title + abstract)"""
        text_parts = [paper.title]
        
        if paper.abstract:
            text_parts.append(paper. abstract)
        
        return " ".join(text_parts)
    
    def _compute_similarities(
        self,
        query_embedding: np.ndarray,
        paper_embeddings: np.ndarray
    ) -> np.ndarray:
        """
        Compute cosine similarities between query and papers.
        
        Returns:
            Array of similarity scores (shape: [num_papers])
        """
        query_embedding = query_embedding.reshape(1, -1)
        similarities = cosine_similarity(query_embedding, paper_embeddings)[0]
        return similarities
    
    def _rank_and_filter(
        self,
        papers: List[Paper],
        similarities: np.ndarray,
        top_k: int
    ) -> List[RankedPaper]:
        """Rank papers and return top-k"""
        
        # Create ranked papers with scores
        ranked_papers = [
            RankedPaper(
                **paper.model_dump(),
                similarity_score=float(score),
                rank=None  # Will be assigned after sorting
            )
            for paper, score in zip(papers, similarities)
            if score >= settings.MIN_SIMILARITY_SCORE
        ]
        
        # Sort by similarity (descending)
        ranked_papers.sort(key=lambda x: x.similarity_score, reverse=True)
        
        # Assign ranks and return top-k
        top_papers = ranked_papers[:top_k]
        for i, paper in enumerate(top_papers, start=1):
            paper.rank = i
        
        return top_papers

# Singleton instance
_ranker_instance = None

def get_ranker() -> SemanticRanker:
    """Get singleton instance of ranker"""
    global _ranker_instance
    if _ranker_instance is None:
        _ranker_instance = SemanticRanker()
    return _ranker_instance