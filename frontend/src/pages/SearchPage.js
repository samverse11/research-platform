// frontend/src/pages/SearchPage. js
import React, { useState, useEffect } from 'react';
import api from '../services/api';
import './SearchPage.css';

function SearchPage() {
  const [query, setQuery] = useState('');
  const [sources, setSources] = useState(['openalex', 'semantic_scholar', 'arxiv']);
  const [topK, setTopK] = useState(10);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [availableSources, setAvailableSources] = useState([]);

  useEffect(() => {
    fetchSources();
  }, []);

  const fetchSources = async () => {
    try {
      const response = await api.crawler.getSources();
      console.log('Fetched sources:', response.data); // Debug log
      // Show ALL sources (available and unavailable)
      setAvailableSources(response.data);
    } catch (err) {
      console.error('Error fetching sources:', err);
    }
  };

  const handleSearch = async () => {
    if (!query.trim()) {
      setError('Please enter a search query');
      return;
    }

    if (sources.length === 0) {
      setError('Please select at least one source');
      return;
    }

    setLoading(true);
    setError(null);
    setResults(null);

    try {
      const response = await api.crawler.search({
        query: query,
        top_k: topK,
        sources: sources,
        min_year: 2015,
        max_year: 2024
      });
      setResults(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Search failed');
      console.error('Search error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSourceToggle = (sourceId) => {
    setSources(prev => {
      if (prev.includes(sourceId)) {
        return prev.filter(s => s !== sourceId);
      } else {
        return [...prev, sourceId];
      }
    });
  };

  return (
    <div className="search-page">
      {/* Header */}
      <div className="page-header">
        <h1 className="page-title">Research Paper Discovery</h1>
        <p className="page-subtitle">AI-powered semantic search across academic sources</p>
      </div>

      {/* Search Container */}
      <div className="search-container">
        {/* Search Input */}
        <div className="input-group">
          <label className="input-label">Search Query</label>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="e.g., transformer neural networks, deep learning algorithms"
            className="search-input"
          />
        </div>

        {/* Sources Selection */}
        <div className="input-group">
          <label className="input-label">
            Data Sources <span className="source-count">({sources.length} selected)</span>
          </label>
          
          {availableSources.length === 0 ? (
            <div className="loading-sources">Loading sources...</div>
          ) : (
            <div className="sources-grid">
              {availableSources.map(source => (
                <label 
                  key={source.id} 
                  className={`source-checkbox ${source.status === 'unavailable' ? 'source-unavailable' : ''}`}
                  title={source.status === 'unavailable' ? (source.message || 'API key required') : source.description}
                >
                  <input
                    type="checkbox"
                    checked={sources.includes(source.id)}
                    onChange={() => handleSourceToggle(source.id)}
                    disabled={source.status === 'unavailable'}
                  />
                  <span className="source-info">
                    <span className="source-name">
                      {source.name}
                      {source.status === 'unavailable' && (
                        <span className="unavailable-badge">🔒 Locked</span>
                      )}
                    </span>
                    <span className="source-coverage">{source.coverage}</span>
                  </span>
                </label>
              ))}
            </div>
          )}
        </div>

        {/* Results Limit */}
        <div className="input-group">
          <label className="input-label">Number of Results</label>
          <input
            type="number"
            min="1"
            max="100"
            value={topK}
            onChange={(e) => setTopK(Math.max(1, Math.min(100, parseInt(e.target.value) || 10)))}
            className="number-input"
            placeholder="Enter number between 1-100"
          />
          <span className="input-hint">Between 1 and 100 papers</span>
        </div>

        {/* Search Button */}
        <button 
          onClick={handleSearch} 
          disabled={loading}
          className="search-button"
        >
          {loading ? 'Searching.. .' : 'Search Papers'}
        </button>
      </div>

      {/* Error Message */}
      {error && (
        <div className="error-box">
          <div className="error-icon">⚠</div>
          <div className="error-message">{error}</div>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="loading-container">
          <div className="loading-spinner"></div>
          <p className="loading-text">Fetching and ranking papers...</p>
          <p className="loading-subtext">This may take 10-15 seconds</p>
        </div>
      )}

      {/* Results */}
      {results && ! loading && (
        <div className="results-container">
          {/* Stats Bar */}
          <div className="stats-bar">
            <div className="stat-item">
              <div className="stat-value">{results.total_returned}</div>
              <div className="stat-label">Papers Returned</div>
            </div>
            <div className="stat-item">
              <div className="stat-value">{results.total_fetched}</div>
              <div className="stat-label">Papers Fetched</div>
            </div>
            <div className="stat-item">
              <div className="stat-value">{results.processing_time_seconds.toFixed(2)}s</div>
              <div className="stat-label">Processing Time</div>
            </div>
            <div className="stat-item">
              <div className="stat-value">{results.sources_used.length}</div>
              <div className="stat-label">Sources Used</div>
            </div>
          </div>

          {/* Papers List */}
          <div className="papers-list">
            {results.papers.map((paper, idx) => (
              <div key={idx} className="paper-card">
                {/* Paper Header */}
                <div className="paper-header">
                  <div className="paper-rank">#{paper.rank}</div>
                  <div className="paper-match">{(paper.similarity_score * 100).toFixed(1)}%</div>
                </div>

                {/* Paper Title */}
                <h3 className="paper-title">{paper.title}</h3>

                {/* Paper Metadata */}
                <div className="paper-metadata">
                  {paper.authors && paper.authors.length > 0 && (
                    <div className="metadata-row">
                      <span className="metadata-label">Authors:</span>
                      <span className="metadata-value">
                        {paper.authors.slice(0, 5).join(', ')}
                        {paper.authors.length > 5 && ` et al.  (${paper.authors.length} total)`}
                      </span>
                    </div>
                  )}
                  
                  <div className="metadata-row">
                    {paper.year && (
                      <div className="metadata-item">
                        <span className="metadata-label">Year:</span>
                        <span className="metadata-value">{paper.year}</span>
                      </div>
                    )}
                    {paper.venue && (
                      <div className="metadata-item">
                        <span className="metadata-label">Venue:</span>
                        <span className="metadata-value">{paper.venue}</span>
                      </div>
                    )}
                  </div>

                  <div className="metadata-row">
                    <div className="metadata-item">
                      <span className="metadata-label">Source:</span>
                      <span className="metadata-value source-badge">{paper.source}</span>
                    </div>
                    {paper.citation_count !== null && paper.citation_count !== undefined && (
                      <div className="metadata-item">
                        <span className="metadata-label">Citations:</span>
                        <span className="metadata-value">{paper.citation_count.toLocaleString()}</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Abstract - FULL TEXT, NO TRUNCATION */}
                {paper.abstract && (
                  <div className="paper-abstract">
                    <div className="abstract-label">Abstract</div>
                    <p className="abstract-text">
                      {paper.abstract}  {/* ← Shows FULL abstract now */}
                    </p>
                  </div>
                )}

                {/* Paper Links - ONLY View Paper and DOI */}
                <div className="paper-links">
                  {paper.url && (
                    <a
                      href={paper.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="paper-link primary"
                    >
                      View Paper →
                    </a>
                  )}
                  
                  {paper.doi && (
                    <a
                      href={`https://doi.org/${paper.doi}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="paper-link doi"
                    >
                      DOI:  {paper.doi}
                    </a>
                  )}
                  
                  {/* ❌ REMOVED Download PDF button */}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* No Results */}
      {results && results.papers.length === 0 && (
        <div className="no-results">
          <div className="no-results-icon">📭</div>
          <h3>No papers found</h3>
          <p>Try adjusting your search terms or selecting different sources</p>
        </div>
      )}
    </div>
  );
}

export default SearchPage;