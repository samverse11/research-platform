# app/services/multi_source_fetcher.py
import requests
import urllib.request
import feedparser
import time
from typing import List, Optional, Dict, Any
from datetime import datetime
from crawler.app.models import Paper
from crawler.app.config import get_settings
import xml.etree.ElementTree as ET
import asyncio
from typing import Tuple

settings = get_settings()

class MultiSourceFetcher:
    """
    Enhanced academic paper fetcher supporting 10+ sources with full metadata. 
    All sources are free or have free API tiers.
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': f'ResearchPaperDiscovery/2.0 ({settings. OPENALEX_EMAIL})' if settings.OPENALEX_EMAIL 
                         else 'ResearchPaperDiscovery/2.0'
        })
    
    def fetch_papers(
        self,
        query: str,
        sources: List[str],
        max_results: int = 50,
        min_year: int = 2015,
        max_year: int = 2024
    ) -> List[Paper]:
        """Fetch papers from multiple sources"""
        all_papers = []
        
        for source in sources:
            try:
                print(f"📥 Fetching from {source}.. .", end=" ", flush=True)
                papers = self._fetch_from_source(source, query, max_results, min_year, max_year)
                
                if papers:
                    all_papers.extend(papers)
                    print(f"✅ {len(papers)} papers")
                else:
                    print(f"⚠️ No results")
                    
            except Exception as e:
                print(f"❌ Error:  {str(e)[:50]}")
                continue
        
        # Deduplicate
        unique_papers = self._deduplicate_papers(all_papers)
        print(f"\n📊 Total unique papers: {len(unique_papers)}")
        
        return unique_papers
    
    async def fetch_papers_async(
        self,
        query: str,
        sources: List[str],
        max_results: int = 50,
        min_year: int = 2015,
        max_year: int = 2024,
        per_source_timeout_s: float = 12.0
    ) -> List[Paper]:
        """
        Fetch papers from multiple sources in parallel.

        Uses threads for the existing blocking fetchers (requests/urllib).
        Keeps the same dedup behavior as fetch_papers().
        """

        async def fetch_one(source: str) -> Tuple[str, List[Paper]]:
            try:
                papers = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._fetch_from_source,
                        source, query, max_results, min_year, max_year
                    ),
                    timeout=per_source_timeout_s
                )
                return source, papers or []
            except Exception:
                return source, []

        results = await asyncio.gather(*(fetch_one(s) for s in sources))

        all_papers: List[Paper] = []
        for source, papers in results:
            if papers:
                all_papers.extend(papers)

        unique = self._deduplicate_papers(all_papers)
        return unique
    
    def _fetch_from_source(
        self,
        source: str,
        query: str,
        max_results: int,
        min_year: int,
        max_year: int
    ) -> List[Paper]:
        """Route to appropriate fetcher"""
        
        fetchers = {
            'openalex': self._fetch_openalex,
            'semantic_scholar':  self._fetch_semantic_scholar,
            'arxiv': self._fetch_arxiv,
            'ieee': self._fetch_ieee,
            'springer': self._fetch_springer,
            'openreview': self._fetch_openreview,
            'crossref':  self._fetch_crossref,
            'dblp': self._fetch_dblp,
            'pubmed': self._fetch_pubmed,
        }
        
        fetcher = fetchers.get(source)
        if not fetcher: 
            raise ValueError(f"Unknown source: {source}")
        
        return fetcher(query, max_results, min_year, max_year)
    
    # ==================== OPENALEX API ====================
    def _fetch_openalex(self, query:  str, max_results: int, min_year: int, max_year: int) -> List[Paper]:
        """
        OpenAlex:  250M+ papers, all fields, completely free
        Best overall coverage - replacement for Google Scholar
        """
        url = "https://api.openalex.org/works"
        papers = []
        page = 1
        per_page = 100
        
        while len(papers) < max_results:
            params = {
                'search':  query,
                'filter': f'publication_year:{min_year}-{max_year}',
                'per_page': min(per_page, max_results - len(papers)),
                'page': page,
                'sort': 'cited_by_count: desc'
            }
            
            try:
                response = self.session.get(url, params=params, timeout=settings.REQUEST_TIMEOUT)
                response.raise_for_status()
                data = response.json()
                
                if not data. get('results'):
                    break
                
                for item in data['results']:
                    try:
                        # Extract authors
                        authors = None
                        if item.get('authorships'):
                            authors = [a['author']['display_name'] for a in item['authorships'] if a.get('author')]
                        
                        # Extract venue
                        venue = None
                        if item.get('primary_location') and item['primary_location'].get('source'):
                            venue = item['primary_location']['source']. get('display_name')
                        
                        # Extract URLs
                        url_main = item.get('doi')
                        if url_main and not url_main.startswith('http'):
                            url_main = f"https://doi.org/{url_main}"
                        
                        pdf_url = None
                        if item.get('open_access') and item['open_access'].get('oa_url'):
                            pdf_url = item['open_access']['oa_url']
                        
                        paper = Paper(
                            title=item.get('title', '').strip(),
                            abstract=self._extract_abstract_inverted(item. get('abstract_inverted_index')),
                            url=url_main or item.get('id'),
                            doi=item.get('doi'),
                            venue=venue,
                            year=item.get('publication_year'),
                            authors=authors,
                            source="openalex",
                            citation_count=item.get('cited_by_count', 0),
                            pdf_url=pdf_url
                        )
                        
                        if paper.title: 
                            papers.append(paper)
                            
                    except Exception: 
                        continue
                
                # Check if more pages
                if len(data['results']) < per_page:
                    break
                    
                page += 1
                time.sleep(0.1)  # Be polite
                
            except Exception as e:
                print(f"\nOpenAlex error: {e}")
                break
        
        return papers
    
    def _extract_abstract_inverted(self, inverted_index: Optional[Dict]) -> Optional[str]:
        """Convert OpenAlex inverted index to text"""
        if not inverted_index:
            return None
        
        try:
            words = []
            for word, positions in inverted_index.items():
                for pos in positions:
                    words.append((pos, word))
            words.sort()
            return ' '. join([w[1] for w in words])
        except: 
            return None
    
    # ==================== SEMANTIC SCHOLAR API ====================
    def _fetch_semantic_scholar(self, query: str, max_results: int, min_year: int, max_year: int) -> List[Paper]:
        """Semantic Scholar: 200M+ papers, AI-powered search"""
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        papers = []
        offset = 0
        limit = 100
        
        while len(papers) < max_results:
            params = {
                'query': query,
                'limit': min(limit, max_results - len(papers)),
                'offset':  offset,
                'year':  f'{min_year}-{max_year}',
                'fields': 'title,abstract,year,authors,venue,url,externalIds,citationCount,openAccessPdf'
            }
            
            try:
                response = self.session.get(url, params=params, timeout=settings.REQUEST_TIMEOUT)
                response.raise_for_status()
                data = response.json()
                
                if not data. get('data'):
                    break
                
                for item in data['data']: 
                    try:
                        authors = None
                        if item. get('authors'):
                            authors = [a. get('name', 'Unknown') for a in item['authors']]
                        
                        paper_url = item.get('url')
                        if not paper_url and item.get('externalIds', {}).get('ArXiv'):
                            paper_url = f"https://arxiv.org/abs/{item['externalIds']['ArXiv']}"
                        
                        doi = item.get('externalIds', {}).get('DOI')
                        pdf_url = None
                        if item.get('openAccessPdf'):
                            pdf_url = item['openAccessPdf']. get('url')
                        
                        paper = Paper(
                            title=item.get('title', '').strip(),
                            abstract=item.get('abstract'),
                            url=paper_url,
                            doi=doi,
                            venue=item.get('venue'),
                            year=item.get('year'),
                            authors=authors,
                            source="semantic_scholar",
                            citation_count=item.get('citationCount', 0),
                            pdf_url=pdf_url
                        )
                        
                        if paper.title:
                            papers.append(paper)
                            
                    except Exception:
                        continue
                
                if len(data['data']) < limit:
                    break
                    
                offset += limit
                time.sleep(1)  # Rate limiting
                
            except Exception as e:
                print(f"\nSemantic Scholar error: {e}")
                break
        
        return papers
    
    # ==================== ARXIV API ====================
    def _fetch_arxiv(self, query: str, max_results: int, min_year: int, max_year:  int) -> List[Paper]:
        """ArXiv: 2M+ preprints, perfect metadata"""
        import urllib.parse
        params = urllib.parse.urlencode({
            'search_query': f'all:{query}',
            'max_results': max_results,
            'sortBy': 'relevance',
        })
        url = f'http://export.arxiv.org/api/query?{params}'
        
        papers = []
        
        try:
            response = urllib.request.urlopen(url, timeout=settings.REQUEST_TIMEOUT)
            feed = feedparser.parse(response.read())
            
            for entry in feed.entries:
                try:
                    year = int(entry.published[: 4])
                    
                    if year < min_year or year > max_year:
                        continue
                    
                    arxiv_id = entry.id. split('/abs/')[-1]
                    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}. pdf"
                    
                    paper = Paper(
                        title=entry.title. replace('\n', ' ').strip(),
                        abstract=entry. summary. replace('\n', ' ').strip(),
                        url=entry.id,
                        doi=f"10.48550/arXiv.{arxiv_id}",
                        venue="ArXiv",
                        year=year,
                        authors=[author.name for author in entry.authors],
                        source="arxiv",
                        pdf_url=pdf_url
                    )
                    
                    papers.append(paper)
                    
                except Exception:
                    continue
                    
        except Exception as e:
            print(f"\nArXiv error: {e}")
        
        return papers
    
    # ==================== IEEE API ====================
    def _fetch_ieee(self, query: str, max_results: int, min_year: int, max_year: int) -> List[Paper]:
        """IEEE Xplore: 5M+ engineering/CS papers"""
        if not settings.IEEE_API_KEY:
            raise ValueError("IEEE requires IEEE_API_KEY in . env.  Get free key at https://developer.ieee.org/")
        
        url = "https://ieeexploreapi.ieee.org/api/v1/search/articles"
        papers = []
        start_record = 1
        max_records = 200  # API limit
        
        while len(papers) < max_results:
            params = {
                'apikey': settings.IEEE_API_KEY,
                'querytext': query,
                'max_records': min(max_records, max_results - len(papers)),
                'start_record': start_record,
                'start_year': min_year,
                'end_year': max_year,
                'sort_order': 'desc',
                'sort_field': 'article_number'
            }
            
            try:
                response = self.session.get(url, params=params, timeout=settings. REQUEST_TIMEOUT)
                response.raise_for_status()
                data = response.json()
                
                if not data.get('articles'):
                    break
                
                for item in data['articles']:
                    try:
                        authors = None
                        if item.get('authors') and item['authors']. get('authors'):
                            authors = [a.get('full_name') or a.get('author_name') 
                                     for a in item['authors']['authors']]
                        
                        doi = item.get('doi')
                        url_main = f"https://doi.org/{doi}" if doi else item.get('html_url')
                        
                        pdf_url = item.get('pdf_url')
                        
                        paper = Paper(
                            title=item.get('title', '').strip(),
                            abstract=item.get('abstract'),
                            url=url_main,
                            doi=doi,
                            venue=item.get('publication_title'),
                            year=item. get('publication_year'),
                            authors=authors,
                            source="ieee",
                            citation_count=item.get('citing_paper_count', 0),
                            pdf_url=pdf_url
                        )
                        
                        if paper.title:
                            papers.append(paper)
                            
                    except Exception:
                        continue
                
                if len(data['articles']) < max_records:
                    break
                    
                start_record += max_records
                time.sleep(0.5)
                
            except Exception as e: 
                print(f"\nIEEE error: {e}")
                break
        
        return papers
    
    # ==================== SPRINGER API ====================
    def _fetch_springer(self, query: str, max_results: int, min_year: int, max_year: int) -> List[Paper]:
        """Springer Nature: 13M+ papers"""
        import requests as _req

        if not settings.SPRINGER_API_KEY:
            print("⚠️  Springer: no API key set — skipping.")
            return []

        # Try the newer endpoint first, fall back to the older one
        endpoints = [
            "https://api.springernature.com/metadata/json",
            "https://api.springer.com/metadata/json",
        ]

        url = None
        for ep in endpoints:
            try:
                probe = self.session.get(
                    ep,
                    params={'api_key': settings.SPRINGER_API_KEY, 'q': query, 's': 1, 'p': 1},
                    timeout=8,
                )
                if probe.status_code == 200:
                    url = ep
                    break
                elif probe.status_code in (401, 403):
                    print(
                        f"⚠️  Springer: API key rejected (HTTP {probe.status_code}) at {ep}. "
                        "Check that your key is subscribed to the Metadata API at "
                        "https://dev.springernature.com — skipping Springer."
                    )
                    return []
            except Exception:
                continue  # try next endpoint

        if url is None:
            print("⚠️  Springer: could not reach any endpoint — skipping.")
            return []

        papers = []
        start = 1
        page_size = 100

        while len(papers) < max_results:
            params = {
                'api_key': settings.SPRINGER_API_KEY,
                'q': query,
                's': start,
                'p': min(page_size, max_results - len(papers)),
            }

            try:
                response = self.session.get(url, params=params, timeout=settings.REQUEST_TIMEOUT)
                response.raise_for_status()
                data = response.json()

                if not data.get('records'):
                    break

                for item in data['records']:
                    try:
                        year = None
                        if item.get('publicationDate'):
                            year = int(item['publicationDate'][:4])

                        if year and (year < min_year or year > max_year):
                            continue

                        authors = None
                        if item.get('creators'):
                            authors = [a.get('creator') for a in item['creators'] if a.get('creator')]

                        doi = item.get('doi')
                        url_main = f"https://doi.org/{doi}" if doi else item.get('url', [{}])[0].get('value')

                        paper = Paper(
                            title=item.get('title', '').strip(),
                            abstract=item.get('abstract'),
                            url=url_main,
                            doi=doi,
                            venue=item.get('publicationName'),
                            year=year,
                            authors=authors,
                            source="springer",
                        )

                        if paper.title:
                            papers.append(paper)

                    except Exception:
                        continue

                if len(data['records']) < page_size:
                    break

                start += page_size
                time.sleep(0.5)

            except _req.exceptions.HTTPError as e:
                print(f"⚠️  Springer HTTP error: {e} — stopping pagination.")
                break
            except Exception as e:
                print(f"⚠️  Springer error: {e} — skipping.")
                break
        
        return papers
    
    # ==================== OPENREVIEW API ====================
    def _fetch_openreview(self, query:  str, max_results: int, min_year: int, max_year: int) -> List[Paper]:
        """OpenReview:  ML conference papers with reviews"""
        url = "https://api.openreview.net/notes/search"
        papers = []
        offset = 0
        limit = 100
        
        while len(papers) < max_results:
            params = {
                'term': query,
                'content':  'all',
                'source': 'forum',
                'limit': min(limit, max_results - len(papers)),
                'offset': offset
            }
            
            try:
                response = self.session.get(url, params=params, timeout=settings. REQUEST_TIMEOUT)
                response.raise_for_status()
                data = response.json()
                
                if not data.get('notes'):
                    break
                
                for item in data['notes']:
                    try: 
                        content = item.get('content', {})
                        
                        # Extract year from date
                        year = None
                        if item.get('cdate'):
                            year = int(datetime.fromtimestamp(item['cdate'] / 1000).year)
                        
                        if year and (year < min_year or year > max_year):
                            continue
                        
                        authors = content.get('authors')
                        if isinstance(authors, str):
                            authors = [authors]
                        
                        paper_url = f"https://openreview.net/forum? id={item['forum']}"
                        pdf_url = f"https://openreview.net/pdf?id={item['forum']}"
                        
                        paper = Paper(
                            title=content.get('title', '').strip(),
                            abstract=content. get('abstract'),
                            url=paper_url,
                            venue=content.get('venue', 'OpenReview'),
                            year=year,
                            authors=authors,
                            source="openreview",
                            pdf_url=pdf_url
                        )
                        
                        if paper.title:
                            papers.append(paper)
                            
                    except Exception: 
                        continue
                
                if len(data['notes']) < limit:
                    break
                    
                offset += limit
                time.sleep(0.5)
                
            except Exception as e:
                print(f"\nOpenReview error:  {e}")
                break
        
        return papers
    
    # ==================== CROSSREF API ====================
    def _fetch_crossref(self, query: str, max_results: int, min_year: int, max_year: int) -> List[Paper]:
        """CrossRef: 140M+ DOI records"""
        url = "https://api.crossref.org/works"
        papers = []
        offset = 0
        rows = 100
        
        while len(papers) < max_results:
            params = {
                'query': query,
                'rows':  min(rows, max_results - len(papers)),
                'offset': offset,
                'filter': f'from-pub-date:{min_year},until-pub-date:{max_year}',
                'sort': 'relevance',
                'select': 'title,author,published,container-title,DOI,abstract,URL'
            }
            
            try:
                response = self.session.get(url, params=params, timeout=settings.REQUEST_TIMEOUT)
                response.raise_for_status()
                data = response.json()
                
                if not data.get('message', {}).get('items'):
                    break
                
                for item in data['message']['items']:
                    try:
                        # Extract year
                        year = None
                        if item.get('published'):
                            date_parts = item['published'].get('date-parts', [[]])[0]
                            if date_parts:
                                year = date_parts[0]
                        
                        # Extract authors
                        authors = None
                        if item.get('author'):
                            authors = [f"{a.get('given', '')} {a.get('family', '')}".strip() 
                                     for a in item['author']]
                        
                        # Extract title
                        title = None
                        if item.get('title'):
                            title = item['title'][0] if isinstance(item['title'], list) else item['title']
                        
                        # Extract venue
                        venue = None
                        if item.get('container-title'):
                            venue = item['container-title'][0] if isinstance(item['container-title'], list) else item['container-title']
                        
                        doi = item.get('DOI')
                        url_main = f"https://doi.org/{doi}" if doi else item.get('URL')
                        
                        paper = Paper(
                            title=title. strip() if title else '',
                            abstract=item.get('abstract'),
                            url=url_main,
                            doi=doi,
                            venue=venue,
                            year=year,
                            authors=authors,
                            source="crossref"
                        )
                        
                        if paper.title:
                            papers.append(paper)
                            
                    except Exception:
                        continue
                
                if len(data['message']['items']) < rows:
                    break
                    
                offset += rows
                time.sleep(0.5)
                
            except Exception as e:
                print(f"\nCrossRef error:  {e}")
                break
        
        return papers
    
    # ==================== DBLP API ====================
    def _fetch_dblp(self, query: str, max_results: int, min_year: int, max_year: int) -> List[Paper]:
        """DBLP: Computer Science bibliography"""
        url = "https://dblp.org/search/publ/api"
        papers = []
        first = 0
        hits = 100
        
        while len(papers) < max_results:
            params = {
                'q':  query,
                'format': 'json',
                'h': min(hits, max_results - len(papers)),
                'f': first
            }
            
            try: 
                response = self.session. get(url, params=params, timeout=settings.REQUEST_TIMEOUT)
                response.raise_for_status()
                data = response.json()
                
                if not data.get('result', {}).get('hits', {}).get('hit'):
                    break
                
                for hit in data['result']['hits']['hit']:
                    try:
                        item = hit['info']
                        
                        year = int(item. get('year', 0))
                        if year < min_year or year > max_year:
                            continue
                        
                        authors = None
                        if item.get('authors'):
                            author_data = item['authors']. get('author', [])
                            if isinstance(author_data, list):
                                authors = [a.get('text') for a in author_data if a.get('text')]
                            else:
                                authors = [author_data.get('text')]
                        
                        title = item.get('title', '')
                        venue = item.get('venue', '')
                        doi = item.get('doi')
                        ee = item.get('ee')  # Electronic edition
                        
                        url_main = f"https://doi.org/{doi}" if doi else ee
                        
                        paper = Paper(
                            title=title. strip(),
                            abstract=None,  # DBLP doesn't provide abstracts
                            url=url_main,
                            doi=doi,
                            venue=venue,
                            year=year,
                            authors=authors,
                            source="dblp"
                        )
                        
                        if paper.title:
                            papers.append(paper)
                            
                    except Exception: 
                        continue
                
                if len(data['result']['hits']['hit']) < hits:
                    break
                    
                first += hits
                time.sleep(0.3)
                
            except Exception as e:
                print(f"\nDBLP error: {e}")
                break
        
        return papers
    
    # ==================== PUBMED API ====================
    def _fetch_pubmed(self, query: str, max_results: int, min_year: int, max_year: int) -> List[Paper]:
        """PubMed:  Biomedical literature"""
        # Search for paper IDs
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        search_params = {
            'db': 'pubmed',
            'term': f'{query} AND {min_year}:{max_year}[pdat]',
            'retmax': max_results,
            'retmode': 'json',
            'sort': 'relevance'
        }
        
        papers = []
        
        try:
            response = self.session.get(search_url, params=search_params, timeout=settings.REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response. json()
            
            id_list = data.get('esearchresult', {}).get('idlist', [])
            
            if not id_list: 
                return papers
            
            # Fetch details for IDs (in batches of 200)
            fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            
            for i in range(0, len(id_list), 200):
                batch_ids = id_list[i:i+200]
                fetch_params = {
                    'db': 'pubmed',
                    'id': ','.join(batch_ids),
                    'retmode': 'xml'
                }
                
                time.sleep(0.4)  # Rate limiting (3 req/sec)
                
                response = self.session.get(fetch_url, params=fetch_params, timeout=settings.REQUEST_TIMEOUT)
                response.raise_for_status()
                
                root = ET.fromstring(response. content)
                
                for article in root.findall('.//PubmedArticle'):
                    try:
                        medline = article.find('. //MedlineCitation')
                        
                        # Title
                        title_elem = medline.find('. //ArticleTitle')
                        title = title_elem.text if title_elem is not None else ''
                        
                        # Abstract
                        abstract = ''
                        abstract_elem = medline.find('.//Abstract/AbstractText')
                        if abstract_elem is not None:
                            abstract = abstract_elem.text
                        
                        # Authors
                        authors = []
                        for author in medline.findall('. //Author'):
                            last = author.find('LastName')
                            first = author.find('ForeName')
                            if last is not None: 
                                name = f"{first.text if first is not None else ''} {last. text}".strip()
                                authors. append(name)
                        
                        # Year
                        year_elem = medline.find('.//PubDate/Year')
                        year = int(year_elem.text) if year_elem is not None else None
                        
                        # Journal
                        journal_elem = medline.find('.//Journal/Title')
                        venue = journal_elem.text if journal_elem is not None else None
                        
                        # PMID
                        pmid_elem = medline.find('PMID')
                        pmid = pmid_elem.text if pmid_elem is not None else ''
                        
                        url_main = f"https://pubmed.ncbi.nlm. nih.gov/{pmid}/"
                        
                        paper = Paper(
                            title=title.strip(),
                            abstract=abstract,
                            url=url_main,
                            venue=venue,
                            year=year,
                            authors=authors if authors else None,
                            source="pubmed"
                        )
                        
                        if paper.title:
                            papers.append(paper)
                            
                    except Exception:
                        continue
                        
        except Exception as e:
            print(f"\nPubMed error: {e}")
        
        return papers
    
    # ==================== DEDUPLICATION ====================
    def _deduplicate_papers(self, papers:  List[Paper]) -> List[Paper]:
        """Remove duplicates based on title and DOI"""
        seen_titles = set()
        seen_dois = set()
        unique_papers = []
        
        for paper in papers:
            # Normalize title
            title_normalized = paper.title.lower().strip()
            title_normalized = ' '.join(title_normalized.split())
            
            # Check DOI first (most reliable)
            if paper.doi:
                doi_normalized = paper.doi.lower().strip()
                if doi_normalized in seen_dois:
                    continue
                seen_dois. add(doi_normalized)
            
            # Check title
            if title_normalized in seen_titles: 
                continue
            
            if title_normalized: 
                seen_titles.add(title_normalized)
                unique_papers.append(paper)
        
        return unique_papers

# Singleton instance
_fetcher_instance = None

def get_multi_source_fetcher() -> MultiSourceFetcher:
    """Get singleton instance"""
    global _fetcher_instance
    if _fetcher_instance is None:
        _fetcher_instance = MultiSourceFetcher()
    return _fetcher_instance