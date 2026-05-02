// frontend/src/pages/DashboardPage.js
import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import api from '../services/api';
import './DashboardPage.css';

const TABS = [
  { id: 'overview',  label: '📊 Overview' },
  { id: 'summaries', label: '📝 Summaries' },
  { id: 'searches',  label: '🔍 Searches' },
  { id: 'uploads',   label: '📄 Uploads' },
];

function DashboardPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState('overview');
  const [stats, setStats] = useState(null);
  const [summaries, setSummaries] = useState([]);
  const [searches, setSearches] = useState([]);
  const [uploads, setUploads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [statsRes, sumRes, searchRes, uploadRes] = await Promise.all([
        api.history.dashboardStats(),
        api.history.getSummaries(),
        api.history.getSearches(),
        api.history.getUploads(),
      ]);
      setStats(statsRes.data);
      setSummaries(sumRes.data.items || []);
      setSearches(searchRes.data.items || []);
      setUploads(uploadRes.data.items || []);
    } catch (err) {
      console.error('Dashboard fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const formatDate = (d) => {
    if (!d) return '—';
    return new Date(d).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  };

  const handleDeleteSummary = async (id) => {
    if (!window.confirm('Delete this summary?')) return;
    try {
      await api.history.deleteSummary(id);
      setSummaries(prev => prev.filter(s => s.id !== id));
      setStats(prev => prev ? { ...prev, total_summaries: prev.total_summaries - 1 } : prev);
    } catch (err) {
      alert('Failed to delete');
    }
  };

  const handleDeleteSearch = async (id) => {
    if (!window.confirm('Delete this search record?')) return;
    try {
      await api.history.deleteSearch(id);
      setSearches(prev => prev.filter(s => s.id !== id));
      setStats(prev => prev ? { ...prev, total_searches: prev.total_searches - 1 } : prev);
    } catch (err) {
      alert('Failed to delete');
    }
  };

  const handleDeleteUpload = async (id) => {
    if (!window.confirm('Delete this upload record?')) return;
    try {
      await api.history.deleteUpload(id);
      setUploads(prev => prev.filter(u => u.id !== id));
      setStats(prev => prev ? { ...prev, total_uploads: prev.total_uploads - 1 } : prev);
    } catch (err) {
      alert('Failed to delete');
    }
  };

  const handleDownload = async (id, filename) => {
    try {
      const res = await api.history.downloadSummary(id);
      const blob = new Blob([res.data], { type: 'text/plain' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = (filename || 'summary').replace('.pdf', '') + '_summary.txt';
      a.click();
    } catch (err) {
      alert('Download failed');
    }
  };

  if (loading) {
    return (
      <div className="dashboard-page">
        <div className="dash-loading">
          <div className="loading-spinner" />
          <p>Loading your dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-page">
      {/* Header */}
      <div className="dash-header">
        <div>
          <h1 className="dash-title">Dashboard</h1>
          <p className="dash-welcome">
            Welcome back, <strong>{user?.username || 'Researcher'}</strong>
          </p>
        </div>
      </div>

      {/* Stats */}
      <div className="stats-row">
        <div className="stat-card">
          <div className="stat-number">{stats?.total_summaries || 0}</div>
          <div className="stat-label">Summaries</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">{stats?.total_searches || 0}</div>
          <div className="stat-label">Searches</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">{stats?.total_uploads || 0}</div>
          <div className="stat-label">Uploads</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="dash-tabs">
        {TABS.map(t => (
          <button
            key={t.id}
            className={`dash-tab ${tab === t.id ? 'active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="dash-content">

        {/* ── Overview ── */}
        {tab === 'overview' && (
          <div className="history-list">
            <h3 style={{ color: '#888', fontWeight: 400, marginBottom: 8 }}>Recent Summaries</h3>
            {(stats?.recent_summaries || []).length === 0 ? (
              <div className="dash-empty">
                <div className="dash-empty-icon">📝</div>
                <h3>No summaries yet</h3>
                <p>Upload a paper to get started</p>
              </div>
            ) : (
              stats.recent_summaries.map(s => (
                <div key={s.id} className="history-card">
                  <div className="hc-header">
                    <div className="hc-title">{s.paper_title || s.original_filename || 'Untitled'}</div>
                    <div className="hc-date">{formatDate(s.created_at)}</div>
                  </div>
                  {s.summary_text && (
                    <div className="hc-preview">{s.summary_text}</div>
                  )}
                </div>
              ))
            )}

            <h3 style={{ color: '#888', fontWeight: 400, marginTop: 24, marginBottom: 8 }}>Recent Searches</h3>
            {(stats?.recent_searches || []).length === 0 ? (
              <div className="dash-empty">
                <div className="dash-empty-icon">🔍</div>
                <h3>No searches yet</h3>
                <p>Try searching for research papers</p>
              </div>
            ) : (
              stats.recent_searches.map(s => (
                <div key={s.id} className="history-card">
                  <div className="search-query-text">"{s.search_query}"</div>
                  <div className="search-meta-row">
                    <span>{s.results_count} results</span>
                    <span>{formatDate(s.searched_at)}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* ── Summaries ── */}
        {tab === 'summaries' && (
          <div className="history-list">
            {summaries.length === 0 ? (
              <div className="dash-empty">
                <div className="dash-empty-icon">📝</div>
                <h3>No summaries yet</h3>
                <p>Upload and summarize a paper to see it here</p>
              </div>
            ) : (
              summaries.map(s => (
                <div key={s.id} className="history-card">
                  <div className="hc-header">
                    <div className="hc-title">{s.paper_title || s.original_filename || 'Untitled'}</div>
                    <div className="hc-date">{formatDate(s.created_at)}</div>
                  </div>
                  <div className="hc-meta">
                    {s.model_used && (
                      <div className="hc-meta-item">
                        <span className="hc-meta-label">Model:</span>
                        <span>{s.model_used}</span>
                      </div>
                    )}
                    {s.processing_time && (
                      <div className="hc-meta-item">
                        <span className="hc-meta-label">Time:</span>
                        <span>{s.processing_time.toFixed(1)}s</span>
                      </div>
                    )}
                    {s.detected_language && (
                      <div className="hc-meta-item">
                        <span className="hc-meta-label">Language:</span>
                        <span>{s.detected_language} → {s.target_language || 'en'}</span>
                      </div>
                    )}
                  </div>

                  {s.summary_text && (
                    <div className="hc-preview">{s.summary_text}</div>
                  )}

                  {expandedId === s.id && s.summary_text && (
                    <div className="summary-expanded">
                      <h4>Full Summary</h4>
                      <p>{s.summary_text}</p>
                    </div>
                  )}

                  <div className="hc-actions">
                    <button
                      className="btn-action btn-view"
                      onClick={() => setExpandedId(expandedId === s.id ? null : s.id)}
                    >
                      {expandedId === s.id ? '▲ Collapse' : '▼ Expand'}
                    </button>
                    <button
                      className="btn-action btn-download"
                      onClick={() => handleDownload(s.id, s.original_filename)}
                    >
                      ⬇ Download
                    </button>
                    <button
                      className="btn-action btn-delete"
                      onClick={() => handleDeleteSummary(s.id)}
                    >
                      🗑 Delete
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* ── Searches ── */}
        {tab === 'searches' && (
          <div className="history-list">
            {searches.length === 0 ? (
              <div className="dash-empty">
                <div className="dash-empty-icon">🔍</div>
                <h3>No search history</h3>
                <p>Your search queries will appear here</p>
              </div>
            ) : (
              searches.map(s => (
                <div key={s.id} className="history-card">
                  <div className="hc-header">
                    <div className="search-query-text">"{s.search_query}"</div>
                    <div className="hc-date">{formatDate(s.searched_at)}</div>
                  </div>
                  <div className="search-meta-row">
                    {s.results_count != null && <span>{s.results_count} results</span>}
                    {s.sources_used && <span>Sources: {s.sources_used}</span>}
                  </div>
                  <div className="hc-actions" style={{ marginTop: 12 }}>
                    <button
                      className="btn-action btn-delete"
                      onClick={() => handleDeleteSearch(s.id)}
                    >
                      🗑 Delete
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* ── Uploads ── */}
        {tab === 'uploads' && (
          <div className="history-list">
            {uploads.length === 0 ? (
              <div className="dash-empty">
                <div className="dash-empty-icon">📄</div>
                <h3>No uploaded papers</h3>
                <p>Papers you upload will be tracked here</p>
              </div>
            ) : (
              uploads.map(u => (
                <div key={u.id} className="history-card">
                  <div className="hc-header">
                    <div className="hc-title">{u.filename}</div>
                    <div className="hc-date">{formatDate(u.upload_date)}</div>
                  </div>
                  <div className="hc-meta">
                    {u.file_size && (
                      <div className="hc-meta-item">
                        <span className="hc-meta-label">Size:</span>
                        <span>{(u.file_size / 1024).toFixed(0)} KB</span>
                      </div>
                    )}
                    {u.total_pages && (
                      <div className="hc-meta-item">
                        <span className="hc-meta-label">Pages:</span>
                        <span>{u.total_pages}</span>
                      </div>
                    )}
                    {u.extracted_text_length && (
                      <div className="hc-meta-item">
                        <span className="hc-meta-label">Text:</span>
                        <span>{u.extracted_text_length.toLocaleString()} chars</span>
                      </div>
                    )}
                  </div>
                  <div className="hc-actions">
                    <button
                      className="btn-action btn-delete"
                      onClick={() => handleDeleteUpload(u.id)}
                    >
                      🗑 Delete
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default DashboardPage;
