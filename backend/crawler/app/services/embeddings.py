import torch
import numpy as np
from transformers import AutoTokenizer, AutoModel
from typing import List
from functools import lru_cache
import re
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
    
    def _normalize_text_for_embedding(self, text: str) -> str:
        """
        Convert LaTeX math signals into natural language tokens
        so E5 embeddings can actually match them semantically.
        """
        s = text
        replacements = [
            (r'\\frac\{([^}]+)\}\{([^}]+)\}', r'\1 divided by \2'),
            (r'\\sum_\{([^}]+)\}',  r'summation over \1'),
            (r'\\sum',              'summation'),
            (r'\\prod',             'product'),
            (r'\\int',              'integral'),
            (r'\\partial',          'partial derivative'),
            (r'\\nabla',            'gradient'),
            (r'\\infty',            'infinity'),
            (r'\\alpha',   'alpha'),  (r'\\beta',  'beta'),
            (r'\\gamma',   'gamma'),  (r'\\delta', 'delta'),
            (r'\\theta',   'theta'),  (r'\\lambda','lambda'),
            (r'\\sigma',   'sigma'),  (r'\\mu',    'mu'),
            (r'\\mathcal\{L\}',     'loss function'),
            (r'\\mathcal\{([^}]+)\}', r'math \1'),
            (r'\\operatorname\{([^}]+)\}', r'\1'),
            (r'\\text\{([^}]+)\}',  r'\1'),
            (r'\\begin\{[^}]+\}|\\end\{[^}]+\}', ''),
            (r'\\[a-zA-Z]+',        ''),   # strip remaining commands
            (r'[_^{}]',             ' '),  # strip math punctuation
            (r'[∑∏∫∂∇]',           'math operator'),
            (r'[αβγδεθλμσφψω]',    'greek variable'),
            (r'\s{2,}',             ' '),
        ]
        for pattern, replacement in replacements:
            s = re.sub(pattern, replacement, s)
        return s.strip()
    
    def encode_query(self, query: str) -> np.ndarray:
        """
        Encode search query with E5 query prefix.
        
        Args:
            query: User search query
            
        Returns: 
            Embedding vector (numpy array)
        """
        # Normalize LaTeX away
        norm_query = self._normalize_text_for_embedding(query)
        # E5 models require "query: " prefix for queries
        prefixed_query = f"query: {norm_query}"
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
        
        # Normalize texts to strip LaTeX
        norm_texts = [self._normalize_text_for_embedding(t) for t in texts]
        
        # E5 models require "passage: " prefix for documents
        prefixed_texts = [f"passage: {text}" for text in norm_texts]
        
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