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

def signature_for_request(sources: List[str], min_year: int, max_year: int) -> Dict[str, Any]:
    return {
        "sources": sorted(list(sources)),
        "min_year": int(min_year),
        "max_year": int(max_year),
    }

def signature_matches(sig: Dict[str, Any], req_sig: Dict[str, Any]) -> bool:
    return sig == req_sig