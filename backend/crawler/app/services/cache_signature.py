import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from crawler.app.config import get_settings

settings = get_settings()

def _sig_path() -> Path:
    base = Path(settings.VECTOR_DB_PATH)
    base.mkdir(parents=True, exist_ok=True)
    return base / "cache_signature.json"

def load_signature() -> Optional[Dict[str, Any]]:
    p = _sig_path()
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))

def save_signature(sig: Dict[str, Any]) -> None:
    p = _sig_path()
    p.write_text(json.dumps(sig, indent=2, sort_keys=True), encoding="utf-8")

def _normalize_query(q: str) -> str:
    return " ".join(q.lower().strip().split())

def signature_for_request(query: str, sources: List[str], min_year: int, max_year: int) -> Dict[str, Any]:
    return {
        "query": _normalize_query(query),
        "sources": sorted(list(sources)),
        "min_year": int(min_year),
        "max_year": int(max_year),
    }

def signature_matches(sig: Dict[str, Any], req_sig: Dict[str, Any]) -> bool:
    """
    Cache is valid when:
    - Same query, min_year, max_year
    - All requested sources are a subset of previously-fetched sources
      (the vector_store.search() source filter handles returning only the right papers)
    A strict new source (e.g. adding ieee when it wasn't fetched before) still triggers a fresh fetch.
    """
    if sig.get("query") != req_sig.get("query"):
        return False
    if sig.get("min_year") != req_sig.get("min_year"):
        return False
    if sig.get("max_year") != req_sig.get("max_year"):
        return False
    # All requested sources must have been fetched previously
    cached_sources = set(sig.get("sources", []))
    requested_sources = set(req_sig.get("sources", []))
    return requested_sources.issubset(cached_sources)