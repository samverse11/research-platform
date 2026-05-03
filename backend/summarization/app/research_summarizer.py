import os
import requests


SUMMARIZATION_API_URL = os.getenv("SUMMARIZATION_API_URL", "http://127.0.0.1:11434")
SUMMARIZATION_MODEL = os.getenv("SUMMARIZATION_MODEL", "summarization_model_T5")
SUMMARIZATION_REQUEST_TIMEOUT = int(os.getenv("SUMMARIZATION_REQUEST_TIMEOUT", "180"))

SYSTEM_PROMPT = """You are a research summarization model. Your task is to read the given research paper or article and write a short single-paragraph summary.

Rules:
- Write exactly one paragraph, around 4-6 sentences
- Extract and naturally include key terms and concepts from the paper
- Keep sentences simple and direct, not overly polished
- Do not cover every detail — focus on the general idea and main findings
- You may miss or lightly gloss over secondary contributions or nuanced findings
- Do not use phrases like "this paper proposes", "the authors demonstrate", "in conclusion" etc.
- Write like a graduate student jotting notes, not like a formal abstract
- Avoid bullet points, headers, or any formatting — plain paragraph only
- Do not start with the title of the paper

Now summarize the following:
"""


def summarize_text(text: str) -> str:
    prompt = f"{SYSTEM_PROMPT}\n\n{text.strip()}"
    payload = {
        "model": SUMMARIZATION_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 512,
        },
    }
    endpoint = f"{SUMMARIZATION_API_URL.rstrip('/')}/api/generate"

    try:
        response = requests.post(endpoint, json=payload, timeout=SUMMARIZATION_REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        summary = (data.get("response") or "").strip()
        if not summary:
            raise RuntimeError("Summarization backend returned an empty response.")
        return summary
    except requests.RequestException as exc:
        raise RuntimeError(
            "Unable to reach the summarization inference server. "
            "Ensure it is running and the model is available."
        ) from exc
