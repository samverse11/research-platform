# Summarization Module

## Purpose
Generate summaries of research papers using LLMs. 

## TODO
- [ ] Implement paper text extraction
- [ ] Integrate LLM (GPT-4, Claude, or open-source)
- [ ] Create summary generation pipeline
- [ ] Add caching for summaries
- [ ] Implement different summary types (short, detailed)

## API Endpoints
- `POST /summarize` - Generate summary for a paper
- `GET /summary/{id}` - Retrieve existing summary

## Team Member Assigned
[Name here]

## Dependencies
```txt
fastapi==0.109.0
openai==1.3.0  # or transformers for open-source