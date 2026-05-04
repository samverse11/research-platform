# app/services/resp_wrapper.py
import pandas as pd
from typing import List, Optional
from crawler.app.models import Paper
from crawler.app.config import get_settings

# Import RESP APIs
try:
    from resp import Arxiv, Semantic_Scholar, ACM, Serp, Resp
    # Connected Papers (optional - requires selenium)
    try:
        from resp. apis. cnnp import connected_papers
        CONNECTED_PAPERS_AVAILABLE = True
    except ImportError:  
        CONNECTED_PAPERS_AVAILABLE = False
        connected_papers = None
except ImportError:
    raise ImportError("Please install respsearch:  pip install respsearch")

settings = get_settings()

class RESPWrapper:
    """
    Complete wrapper around RESP library for ALL supported sources.  
    """
    
    def __init__(self):
        # Direct API sources (no API key needed)
        self.arxiv = Arxiv()
        self.semantic_scholar = Semantic_Scholar()
        self.acm = ACM()
        
        # Resp class for conference proceedings (requires API key)
        # Initialize lazily when first used
        self.resp = None
        self._resp_api_key = settings.SERPAPI_KEY
        
        # Google Scholar API
        self.serp = None
        if settings.SERPAPI_KEY: 
            self.serp = Serp(api_key=settings.SERPAPI_KEY)
            print("✅ Google Scholar API initialized")
        
        # Connected Papers (requires selenium)
        self.connected_papers_client = None
        if CONNECTED_PAPERS_AVAILABLE: 
            try: 
                self.connected_papers_client = connected_papers()
                print("✅ Connected Papers initialized")
            except Exception as e: 
                print(f"⚠️ Connected Papers init failed: {e}")
    
    def _ensure_resp_initialized(self):
        """Lazy initialization of Resp class"""
        if self.resp is None:
            if not self._resp_api_key:
                raise ValueError(
                    "Conference sources (acl, pmlr, neurips, ijcai, openreview, cvf) "
                    "require SERPAPI_KEY in .env for Google Custom Search.  "
                    "Get a free key at https://serpapi.com/ (100 searches/month free)"
                )
            try:
                self.resp = Resp(api_key=self._resp_api_key)
                print("✅ Conference search (Resp) initialized")
            except Exception as e:
                raise ValueError(f"Failed to initialize Resp: {e}")
    
    def fetch_papers(
        self,
        query: str,
        sources: List[str],
        max_results: int = 50,
        min_year: int = 2015,
        max_year: int = 2026
    ) -> List[Paper]:
        """Fetch papers from multiple sources."""
        all_papers = []
        
        for source in sources:
            try:
                print(f"📥 Fetching from {source}.. .", end=" ")
                papers_df = self._fetch_from_source(
                    source, query, max_results, min_year, max_year
                )
                
                if papers_df is None or papers_df.empty:
                    print(f"⚠️ No results")
                    continue
                
                papers = self._normalize_papers(papers_df, source)
                all_papers. extend(papers)
                print(f"✅ {len(papers)} papers")
                
            except Exception as e:
                print(f"❌ Error:  {str(e)[:50]}")
                continue
        
        # Remove duplicates
        unique_papers = self._deduplicate_papers(all_papers)
        print(f"\n📊 Total unique papers: {len(unique_papers)}")
        
        return unique_papers
    
    def _fetch_from_source(
        self,
        source: str,
        query: str,
        max_results: int,
        min_year: int,
        max_year: int
    ) -> Optional[pd.DataFrame]:  
        """Fetch from a specific source"""
        
        pages = max(1, max_results // 50)
        
        # ========== DIRECT API SOURCES (NO API KEY NEEDED) ==========
        if source == "arxiv":
            return self.arxiv.arxiv(
                keyword=query,
                max_pages=pages,
                api_wait=2
            )
        
        elif source == "semantic_scholar":
            return self.semantic_scholar.ss(
                keyword=query,
                max_pages=max(1, max_results // 10),
                min_year=min_year,
                max_year=max_year,
                api_wait=3
            )
        
        elif source == "acm":
            return self.acm.acm(
                keyword=query,
                max_pages=pages,
                min_year=min_year,
                max_year=max_year,
                api_wait=3
            )
        
        elif source == "google_scholar":  
            if not self.serp:
                raise ValueError("Google Scholar requires SERPAPI_KEY in .env")
            return self.serp.google_scholar_search(
                q=query,
                max_pages=max(1, max_results // 10)
            )
        
        # ========== CONFERENCE SOURCES (REQUIRE API KEY) ==========
        elif source in ["acl", "pmlr", "neurips", "ijcai", "openreview", "cvf"]:
            # Lazy initialization
            self._ensure_resp_initialized()
            
            # Route to appropriate method
            if source == "acl":
                return self.resp.acl(keyword=query, max_pages=pages)
            elif source == "pmlr":
                return self.resp.pmlr(keyword=query, max_pages=pages)
            elif source == "neurips": 
                return self.resp.nips(keyword=query, max_pages=pages)
            elif source == "ijcai": 
                return self.resp.ijcai(keyword=query, max_pages=pages)
            elif source == "openreview":
                return self.resp.openreview(keyword=query, max_pages=pages)
            elif source == "cvf":
                return self.resp.cvf(keyword=query, max_pages=pages)
        
        # ========== CONNECTED PAPERS ==========
        elif source == "connected_papers":
            if not self.connected_papers_client:
                raise ValueError("Connected Papers requires:  pip install respsearch[selenium]")
            
            return self.connected_papers_client.download_papers(
                query=query,
                n=min(10, max_results // 10)
            )
        
        else:
            raise ValueError(f"Unsupported source: {source}")
    
    def _normalize_papers(self, df: pd.DataFrame, source: str) -> List[Paper]:
        """Convert DataFrame to Paper objects"""
        papers = []
        
        for _, row in df.iterrows():
            try:
                title = str(row. get('title', '')).strip()
                if not title or title == 'nan':
                    continue
                
                url = str(row.get('link', row.get('url', ''))).strip()
                if url == 'nan':
                    url = None
                
                abstract = str(row.get('snippet', row.get('abstract', ''))).strip()
                if abstract == 'nan' or abstract == '':
                    abstract = None
                
                paper = Paper(
                    title=title,
                    abstract=abstract,
                    url=url,
                    venue=str(row.get('venue', '')).strip() or None,
                    year=self._extract_year(row),
                    authors=self._extract_authors(row),
                    source=source
                )
                papers.append(paper)
            except Exception: 
                continue
        
        return papers
    
    def _extract_year(self, row) -> Optional[int]:
        """Extract publication year"""
        year = row.get('year', row.get('publicationDate', None))
        if year:
            try:
                return int(str(year)[:4])
            except:  
                pass
        return None
    
    def _extract_authors(self, row) -> Optional[List[str]]:
        """Extract authors list"""
        authors = row.get('authors', None)
        if authors:
            if isinstance(authors, list):
                return [str(a) for a in authors]
            elif isinstance(authors, str):
                return [authors]
        return None
    
    def _deduplicate_papers(self, papers:  List[Paper]) -> List[Paper]:
        """Remove duplicate papers based on title"""
        seen_titles = set()
        unique_papers = []
        
        for paper in papers:
            title_normalized = paper.title.lower().strip()
            title_normalized = ' '.join(title_normalized.split())
            
            if title_normalized not in seen_titles and title_normalized:  
                seen_titles.add(title_normalized)
                unique_papers.append(paper)
        
        return unique_papers
    
    def fetch_citations(self, paper_title: str, max_results: int = 50) -> List[Paper]:
        """Fetch citations for a paper (requires SERPAPI_KEY)"""
        if not self.serp:
            raise ValueError("Citations require SERPAPI_KEY in . env")
        
        print(f"📚 Fetching citations for: {paper_title}")
        citations_dict = self.serp.get_citations(paper_title)
        
        all_citations = []
        for key, df in citations_dict.items():
            if isinstance(df, pd.DataFrame):
                papers = self._normalize_papers(df, "google_scholar_citations")
                all_citations.extend(papers)
        
        return all_citations[: max_results]
    
    def fetch_related_papers(self, paper_title: str, max_results: int = 20) -> List[Paper]:
        """Fetch related papers (requires SERPAPI_KEY)"""
        if not self.serp:
            raise ValueError("Related papers require SERPAPI_KEY in .env")
        
        print(f"🔗 Fetching related papers for:  {paper_title}")
        related_dict = self.serp. get_related_pages(paper_title)
        
        all_related = []
        for key, df in related_dict.items():
            if isinstance(df, pd.DataFrame):
                papers = self._normalize_papers(df, "google_scholar_related")
                all_related.extend(papers)
        
        return all_related[:max_results]

# Singleton instance
_wrapper_instance = None

def get_resp_wrapper() -> RESPWrapper:
    """Get singleton instance of RESP wrapper"""
    global _wrapper_instance
    if _wrapper_instance is None:
        _wrapper_instance = RESPWrapper()
    return _wrapper_instance