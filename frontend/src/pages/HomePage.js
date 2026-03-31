// frontend/src/pages/HomePage.js
import React from 'react';
import { Link } from 'react-router-dom';
import './HomePage.css';

function HomePage() {
  return (
    <div className="home-page">
      {/* Hero Section */}
      <section className="hero-section">
        <div className="hero-content">
          <h1 className="hero-title">
            AI-Powered Cross-Lingual
            <span className="hero-title-highlight"> Research Discovery System</span>
          </h1>
          <p className="hero-subtitle">
            Discover and analyze research papers across languages using AI-powered semantic search and summarization.
          </p>
          <p className="hero-description">
            Retrieve relevant research papers using semantic search, summarize both English and German research papers, and generate grouped summaries to compare key insights across selected documents.
          </p>
          <Link to="/search" className="hero-cta">
            Start Searching →
          </Link>
        </div>
      </section>

      {/* Features Section */}
      <section className="features-section">
        <h2 className="section-title">Key Features</h2>
        
        <div className="features-grid">
          <div className="feature-card">
            <div className="feature-icon">🔍</div>
            <h3 className="feature-title">Semantic Search</h3>
            <p className="feature-description">
              Advanced AI-powered search that understands meaning, not just keywords.  Uses E5 transformer embeddings for accurate results.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon">📚</div>
            <h3 className="feature-title">Multiple Sources</h3>
            <p className="feature-description">
              Search across 10+ academic databases including OpenAlex, Semantic Scholar, ArXiv, IEEE, Springer, and more.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon">⚡</div>
            <h3 className="feature-title">Fast & Accurate</h3>
            <p className="feature-description">
              Get ranked results in seconds with similarity scores showing relevance to your query.  Smart deduplication across sources.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon">📊</div>
            <h3 className="feature-title">Rich Metadata</h3>
            <p className="feature-description">
              Complete paper information including authors, citations, venue, abstract, DOI, and direct PDF links when available.
            </p>
          </div>
        </div>
      </section>

      {/* Sources Section */}
      <section className="sources-section">
        <h2 className="section-title">Available Sources</h2>
        <p className="section-subtitle">
          Access papers from leading academic databases and repositories
        </p>

        <div className="sources-grid">
          <div className="source-item">
            <div className="source-name">OpenAlex</div>
            <div className="source-count">250M+ papers</div>
          </div>
          <div className="source-item">
            <div className="source-name">Semantic Scholar</div>
            <div className="source-count">200M+ papers</div>
          </div>
          <div className="source-item">
            <div className="source-name">CrossRef</div>
            <div className="source-count">140M+ records</div>
          </div>
          <div className="source-item">
            <div className="source-name">Springer Nature</div>
            <div className="source-count">13M+ documents</div>
          </div>
          <div className="source-item">
            <div className="source-name">DBLP</div>
            <div className="source-count">6M+ publications</div>
          </div>
          <div className="source-item">
            <div className="source-name">IEEE Xplore</div>
            <div className="source-count">5M+ documents</div>
          </div>
          <div className="source-item">
            <div className="source-name">ACM Library</div>
            <div className="source-count">2M+ publications</div>
          </div>
          <div className="source-item">
            <div className="source-name">ArXiv</div>
            <div className="source-count">2M+ preprints</div>
          </div>
          <div className="source-item">
            <div className="source-name">OpenReview</div>
            <div className="source-count">100K+ papers</div>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="how-it-works-section">
        <h2 className="section-title">How It Works</h2>
        
        <div className="steps-container">
          <div className="step">
            <div className="step-number">01</div>
            <div className="step-content">
              <h3 className="step-title">Enter Your Query</h3>
              <p className="step-description">
                Type your research topic or question in natural language
              </p>
            </div>
          </div>

          <div className="step-arrow">→</div>

          <div className="step">
            <div className="step-number">02</div>
            <div className="step-content">
              <h3 className="step-title">AI Processing</h3>
              <p className="step-description">
                Papers are fetched and ranked using semantic similarity
              </p>
            </div>
          </div>

          <div className="step-arrow">→</div>

          <div className="step">
            <div className="step-number">03</div>
            <div className="step-content">
              <h3 className="step-title">Get Results</h3>
              <p className="step-description">
                Receive ranked papers with relevance scores and metadata
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="cta-section">
        <h2 className="cta-title">Ready to discover research? </h2>
        <p className="cta-description">
          Start searching through millions of academic papers now
        </p>
        <Link to="/search" className="cta-button">
          Begin Search
        </Link>
      </section>
    </div>
  );
}

export default HomePage;