# app/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path
import torch

class Settings(BaseSettings):
    # API Settings
    APP_NAME: str = "Research Paper Discovery API"
    VERSION: str = "2.0.0"
    API_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    
    # API Keys (all optional)
    SERPAPI_KEY: str = ""  # For Google Scholar (100 free/month)
    IEEE_API_KEY: str = ""  # Free from https://developer.ieee.org/
    SPRINGER_API_KEY:  str = ""  # Free from https://dev.springernature.com/
    
    # OpenAlex (no key needed, just email for polite pool)
    OPENALEX_EMAIL: str = ""  # Your email for rate limit boost
    
    # Fetching Settings
    MAX_PAPERS_PER_SOURCE: int = 50
    REQUEST_TIMEOUT: int = 30
    
    # Embedding Settings
    EMBEDDING_MODEL: str = "intfloat/e5-base-v2"
    EMBEDDING_DIMENSION: int = 768
    DEVICE: str = "cuda" if torch.cuda.is_available() else "cpu"
    EMBEDDING_BATCH_SIZE: int = 32
    
    # Search Settings
    DEFAULT_TOP_K: int = 10
    MIN_SIMILARITY_SCORE: float = 0.0
    MAX_PAPERS_LIMIT: int = 1000
    
    # Vector DB Settings
    USE_VECTOR_DB: bool = False
    VECTOR_DB_TYPE: str = "faiss"
    VECTOR_DB_PATH: str = "./data/vector_store"
    # Paper cache (SQLite) + refresh policy
    PAPER_DB_PATH: str = "./data/papers.sqlite"
    CACHE_STALE_HOURS: int = 6
    FETCH_SOURCE_TIMEOUT_S: float = 12.0
    
    # Cache Settings
    ENABLE_CACHE: bool = True
    CACHE_DIR: str = "./data/cache"
    CACHE_TTL_HOURS: int = 24
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create directories
        Path(self.VECTOR_DB_PATH).mkdir(parents=True, exist_ok=True)
        Path(self.CACHE_DIR).mkdir(parents=True, exist_ok=True)

@lru_cache()
def get_settings() -> Settings:
    return Settings()