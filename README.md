# 🔬 Research Platform

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![React](https://img.shields.io/badge/react-19.2.3-blue)
![FastAPI](https://img.shields.io/badge/fastapi-0.109.0-green)
![Status](https://img.shields.io/badge/status-active-success)

A highly advanced, AI-powered platform for academic researchers, data scientists, and students. This platform automates the discovery, extraction, analysis, translation, and summarization of dense academic papers using state-of-the-art Large Language Models (LLMs) and Vector Databases.

---

## ✨ Main Features

- **🔍 Semantic Paper Retrieval**: Instantly search and aggregate academic papers from IEEE Xplore, Springer Nature, and Google Scholar using unified APIs.
- **🌐 Cross-lingual Translation**: Automatically detect and translate foreign-language papers (e.g., German to English) using local offline NLP models before summarization.
- **📑 Long-document Summarization**: Break down large, 50+ page PDFs using intelligent chunking and summarize them natively using Groq's high-speed inference (Llama-3.3-70B).
- **🧠 RAG-based Multi-Paper Analysis**: Compare multiple papers side-by-side using Retrieval-Augmented Generation to extract methodologies, metric alignments, and research gaps.
- **📐 Formula Extraction**: Automatically parse and render complex mathematical formulas from PDFs using OCR and MathJax.
- **⚡ Intelligent Caching**: Prevent redundant API calls and save compute by dynamically hashing files and checking SQLite vector cache.
- **🔐 Secure Authentication**: Full JWT-based user authentication system with secure bcrypt password hashing and persistent sessions.
- **📊 User Dashboard & History**: Dedicated dashboard to track your past searches, manage uploaded papers, and review historical summaries.

---

## 🏛️ Architecture Overview

The project follows a decoupled **Client-Server** micro-monolith architecture:
1. **Frontend**: React-based SPA focusing on a premium, responsive dark-mode UI with smooth micro-animations.
2. **API Gateway (Backend)**: FastAPI application acting as the orchestrator for multiple sub-modules (Crawler, Analyzer, Summarization, Auth, History).
3. **Database**: Persistent SQLite database managed via SQLAlchemy ORM.

### Tech Stack
- **Frontend**: React, React Router, Axios, Vanilla CSS
- **Backend**: Python, FastAPI, Uvicorn, SQLAlchemy, Pydantic, JWT/Passlib
- **AI/ML**: PyTorch, HuggingFace (`sentence-transformers`), FAISS (Vector DB), Groq API, EasyOCR

---

## 📂 Folder Structure

```text
research-platform/
├── .env.example             # Environment placeholders
├── backend/
│   ├── api_gateway/         # Central FastAPI entrypoint
│   ├── analyzer/            # RAG-based paper comparison
│   ├── auth/                # JWT Authentication & User management
│   ├── crawler/             # Paper fetching (IEEE, Springer, Scholar)
│   ├── history/             # Dashboard and user history endpoints
│   ├── shared/              # SQLAlchemy models, database setup
│   └── summarization/       # PDF chunking, Translation, LLM abstraction
├── frontend/
│   ├── public/
│   └── src/
│       ├── components/      # Reusable UI (Navbar, ProtectedRoute)
│       ├── context/         # React Context (AuthContext)
│       ├── pages/           # Pages (Dashboard, Search, Analyze, etc.)
│       └── services/        # Axios API configurations
```

---

## 🚀 Installation & Setup

### Prerequisites
- Node.js (v18+)
- Python (3.10+)
- Git

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/research-platform.git
cd research-platform
```

### 2. Environment Variables
Create a `.env` file in the root directory based on `.env.example`:
```bash
cp .env.example .env
```
Fill out `.env` with your API keys:
- `GROQ_API_KEY`: Get from [Groq Console](https://console.groq.com/)
- `IEEE_API_KEY`: Get from [IEEE Developer](https://developer.ieee.org/)
- `SPRINGER_API_KEY`: Get from [Springer Nature](https://dev.springernature.com/)
- `JWT_SECRET_KEY`: Set a secure random string for user authentication.

### 3. Backend Setup
Create a virtual environment and install dependencies:
```bash
# Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate
# Mac/Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**Start the Backend Server:**
```bash
python -m uvicorn backend.api_gateway.app.main:app --host 0.0.0.0 --port 8000 --reload
```
*The API will be available at `http://localhost:8000`. The SQLite database will initialize automatically.*

### 4. Frontend Setup
Open a new terminal and navigate to the frontend directory:
```bash
cd frontend

# Install Node dependencies
npm install

# Start the React development server
npm start
```
*The frontend will be available at `http://localhost:3000`.*

---

## 🚢 Deployment Notes

### Backend Deployment (Render / Railway)
1. Set the Build Command to `pip install -r requirements.txt`
2. Set the Start Command to `uvicorn backend.api_gateway.app.main:app --host 0.0.0.0 --port $PORT`
3. Add all `.env` variables to the platform's Environment Variables settings.

### Frontend Deployment (Vercel / Netlify)
1. Ensure the Build Command is `npm run build`
2. Set `REACT_APP_API_URL` to your deployed backend URL.

---

## 🔮 Future Enhancements
- Real-time collaborative document annotation.
- PDF generation for exported summaries.
- Advanced citation graph visualization using D3.js.
- Native integration with Zotero/Mendeley.

---

## 🤝 Contributors
Contributions, issues, and feature requests are welcome!
Feel free to check the [issues page](https://github.com/yourusername/research-platform/issues).

---

## 📄 License
This project is [MIT](LICENSE) licensed.
