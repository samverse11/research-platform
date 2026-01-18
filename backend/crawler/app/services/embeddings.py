import torch
import numpy as np
from transformers import AutoTokenizer, AutoModel
from typing import List
from functools import lru_cache
from crawler.app.config import get_settings

settings = get_settings()

class EmbeddingService:
    """
    Semantic embedding service using E5 models.
    E5 models require specific prefixes: 
    - "query:  " for queries
    - "passage: " for documents
    """
    
    def __init__(self):
        self.device = torch.device(settings.DEVICE)
        print(f"🔧 Loading embedding model: {settings. EMBEDDING_MODEL}")
        
        self.tokenizer = AutoTokenizer. from_pretrained(settings.EMBEDDING_MODEL)
        self.model = AutoModel.from_pretrained(settings.EMBEDDING_MODEL)
        self.model.to(self.device)
        self.model.eval()
        
        print(f"✅ Model loaded on {self.device}")
    
    def encode_query(self, query: str) -> np.ndarray:
        """
        Encode search query with E5 query prefix.
        
        Args:
            query: User search query
            
        Returns: 
            Embedding vector (numpy array)
        """
        # E5 models require "query: " prefix for queries
        prefixed_query = f"query:  {query}"
        return self._encode_text(prefixed_query)
    
    def encode_documents(self, texts: List[str]) -> np.ndarray:
        """
        Encode multiple documents with E5 passage prefix.
        
        Args:
            texts: List of document texts
            
        Returns:
            Matrix of embeddings (shape: [num_docs, embedding_dim])
        """
        if not texts:
            return np. array([])
        
        # E5 models require "passage:  " prefix for documents
        prefixed_texts = [f"passage:  {text}" for text in texts]
        
        embeddings = []
        batch_size = settings.EMBEDDING_BATCH_SIZE
        
        for i in range(0, len(prefixed_texts), batch_size):
            batch = prefixed_texts[i:i + batch_size]
            batch_embeddings = self._encode_batch(batch)
            embeddings. append(batch_embeddings)
        
        return np.vstack(embeddings)
    
    def _encode_text(self, text: str) -> np.ndarray:
        """Encode single text"""
        return self._encode_batch([text])[0]
    
    def _encode_batch(self, texts: List[str]) -> np.ndarray:
        """Encode batch of texts"""
        # Tokenize
        encoded = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors='pt'
        )
        
        # Move to device
        encoded = {k: v.to(self.device) for k, v in encoded. items()}
        
        # Generate embeddings
        with torch.no_grad():
            outputs = self.model(**encoded)
            # Mean pooling over token embeddings
            embeddings = self._mean_pooling(
                outputs.last_hidden_state,
                encoded['attention_mask']
            )
        
        # Normalize embeddings for cosine similarity
        embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
        
        return embeddings. cpu().numpy()
    
    def _mean_pooling(self, token_embeddings:  torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        """Mean pooling with attention mask"""
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings. size()).float()
        sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, dim=1)
        sum_mask = torch.clamp(input_mask_expanded. sum(dim=1), min=1e-9)
        return sum_embeddings / sum_mask

# Singleton instance
@lru_cache()
def get_embedding_service() -> EmbeddingService: 
    """Get singleton instance of embedding service"""
    return EmbeddingService()