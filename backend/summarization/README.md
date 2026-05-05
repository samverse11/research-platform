# Summarization Module

## Purpose
Generate summaries of research literature. 

## Features
- [ ] Paper text extraction 
- [ ] Summary generation pipeline
- [ ] Caching for summaries
- [ ] Different summary types (short, detailed)

## API Endpoints
- `POST /summarize` - Generate summary for a paper
- `GET /summary/{id}` - Retrieve existing summary

## Dependencies
```txt
fastapi==0.109.0
openai==1.3.0  # or transformers for open-source
