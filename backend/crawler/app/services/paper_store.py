import sqlite3
import hashlib
import json
from pathlib import Path
from typing import List, Optional, Tuple
import numpy as np

from crawler.app.models import Paper
from crawler.app.config import get_settings

settings = get_settings()

def _paper_key(p: Paper) -> str:
    # Prefer DOI, then URL, else title hash
    base = (p.doi or p.url or p.title or "").strip().lower()
    return hashlib.sha256(base.encode("utf-8")).hexdigest()

class PaperStore:
    def __init__(self, db_path: str = "./data/papers.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS papers (
                    paper_key TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    abstract TEXT,
                    url TEXT,
                    doi TEXT,
                    venue TEXT,
                    year INTEGER,
                    authors_json TEXT,
                    source TEXT,
                    citation_count INTEGER,
                    pdf_url TEXT,
                    embedding BLOB,
                    embedding_dim INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_year ON papers(year)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_source ON papers(source)")

    def upsert_paper(self, paper: Paper, embedding: Optional[np.ndarray] = None) -> bool:
        """
        Returns True if inserted or updated (new or changed), False if no-op.
        """
        key = _paper_key(paper)

        emb_blob = None
        emb_dim = None
        if embedding is not None:
            emb = embedding.astype("float32").tobytes()
            emb_blob = emb
            emb_dim = int(embedding.shape[0])

        authors_json = json.dumps(paper.authors) if paper.authors else None

        with self._connect() as conn:
            # Upsert
            conn.execute(
                """
                INSERT INTO papers (
                    paper_key, title, abstract, url, doi, venue, year, authors_json, source,
                    citation_count, pdf_url, embedding, embedding_dim
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(paper_key) DO UPDATE SET
                    title=excluded.title,
                    abstract=COALESCE(excluded.abstract, papers.abstract),
                    url=COALESCE(excluded.url, papers.url),
                    doi=COALESCE(excluded.doi, papers.doi),
                    venue=COALESCE(excluded.venue, papers.venue),
                    year=COALESCE(excluded.year, papers.year),
                    authors_json=COALESCE(excluded.authors_json, papers.authors_json),
                    source=COALESCE(excluded.source, papers.source),
                    citation_count=COALESCE(excluded.citation_count, papers.citation_count),
                    pdf_url=COALESCE(excluded.pdf_url, papers.pdf_url),
                    embedding=COALESCE(excluded.embedding, papers.embedding),
                    embedding_dim=COALESCE(excluded.embedding_dim, papers.embedding_dim),
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    key,
                    paper.title,
                    paper.abstract,
                    paper.url,
                    paper.doi,
                    paper.venue,
                    paper.year,
                    authors_json,
                    paper.source,
                    paper.citation_count,
                    paper.pdf_url,
                    emb_blob,
                    emb_dim,
                ),
            )
        return True

    def get_papers_missing_embedding(self, limit: int = 500) -> List[Paper]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT title, abstract, url, doi, venue, year, authors_json, source, citation_count, pdf_url
                FROM papers
                WHERE embedding IS NULL
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        papers: List[Paper] = []
        for (title, abstract, url, doi, venue, year, authors_json, source, citation_count, pdf_url) in rows:
            authors = json.loads(authors_json) if authors_json else None
            papers.append(
                Paper(
                    title=title,
                    abstract=abstract,
                    url=url,
                    doi=doi,
                    venue=venue,
                    year=year,
                    authors=authors,
                    source=source,
                    citation_count=citation_count,
                    pdf_url=pdf_url,
                )
            )
        return papers