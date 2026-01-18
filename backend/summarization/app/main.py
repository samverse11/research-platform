# backend/summarization/app/main.py
"""
Summarization Module
TODO: Implement paper summarization using LLMs
"""

from fastapi import FastAPI

app = FastAPI(
    title="Summarization Module",
    version="1.0.0",
    root_path="/api/summarization"
)

@app.get("/health")
async def health():
    return {"module": "summarization", "status":  "coming_soon"}

@app.post("/summarize")
async def summarize_paper(paper_id: str):
    """
    TODO: Implement summarization
    Input: paper_id
    Output: summary
    """
    return {
        "message": "Summarization module not yet implemented",
        "paper_id": paper_id
    }