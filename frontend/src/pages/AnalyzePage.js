// frontend/src/pages/AnalyzePage.js  —  v6.1
import React, { useState, useRef, useEffect, useCallback } from 'react';
import api from '../services/api';
import './AnalyzePage.css';

// ── MathJax ───────────────────────────────────────────────────────────────────
function useMathJax(trigger) {
  useEffect(() => {
    const run = () => setTimeout(() => window.MathJax?.typesetPromise?.(), 200);
    if (window.MathJax) { run(); return; }
    window.MathJax = {
      tex: { inlineMath: [['$', '$'], ['\\(', '\\)']], displayMath: [['$$', '$$'], ['\\[', '\\]']] },
      svg: { fontCache: 'global' },
    };
    const s = document.createElement('script');
    s.src = 'https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js';
    s.async = true; s.onload = run;
    document.head.appendChild(s);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trigger]);
}

function MathBlock({ latex }) {
  const ref = useRef();
  useEffect(() => {
    if (ref.current && window.MathJax?.typesetPromise)
      window.MathJax.typesetPromise([ref.current]);
  });
  if (!latex) return null;
  return <div ref={ref} className="math-render">{`$$${latex}$$`}</div>;
}

// ── Tabs ──────────────────────────────────────────────────────────────────────
const TABS = [
  { id: 'comparison', label: '📊 Comparison' },
  { id: 'formulas', label: '📐 Formulas' },
  { id: 'methodology', label: '⚙️ Methodology' },
  { id: 'issues', label: '⚠️ Potential Issues' },
  { id: 'claims', label: '🔍 Claim Verification' },
];

// ── SmartValue — renders comma/semicolon lists as bullets ─────────────────────
function SmartValue({ val }) {
  if (!val || val === '—') return <span style={{ color: '#333' }}>—</span>;

  // Split on semicolons first
  let parts = val.split(/;\s+/).map(s => s.trim()).filter(Boolean);

  // If still one long item with commas, split on commas
  if (parts.length === 1 && val.length > 60 && val.includes(',')) {
    parts = val.split(',').map(s => s.trim()).filter(Boolean);
  }

  if (parts.length > 1) {
    return (
      <ul style={{ margin: 0, paddingLeft: 16, color: '#aaa', listStyle: 'disc' }}>
        {parts.map((p, i) => (
          <li key={i} style={{ marginBottom: 4, lineHeight: 1.55, fontSize: '.83em' }}>{p}</li>
        ))}
      </ul>
    );
  }

  return <span>{val}</span>;
}

// ── Comparison Tab ────────────────────────────────────────────────────────────
function ComparisonTab({ table, metricAlignment, papers }) {
  if (!table?.length) return <div className="empty-state">No data available.</div>;
  const hasMultiple = papers.length > 1;

  return (
    <div className="tab-body">
      <div className="section-heading">Overview Comparison</div>
      <div className="table-scroll-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th className="col-factor">Factor</th>
              {papers.map((p, i) => (
                <th key={i} className="col-paper">
                  <div className="th-title">{p.paper_title}</div>
                  <div className="th-sub">{p.pages} pages</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.map((row, i) => (
              <tr key={i} className={i % 2 === 0 ? 'row-a' : 'row-b'}>
                <td className="td-factor">{row.factor}</td>
                {papers.map((p, j) => (
                  <td key={j} className="td-value">
                    <SmartValue val={row.values[p.paper_title] || '—'} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {hasMultiple && metricAlignment?.length > 0 && (
        <>
          <div className="section-heading" style={{ marginTop: 36 }}>
            Metric Alignment
            <span className="section-heading-sub">
              Exact values across papers · <span className="gap-legend">— = not reported</span>
            </span>
          </div>
          <div className="table-scroll-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th className="col-factor">Metric</th>
                  {papers.map((p, i) => (
                    <th key={i} className="col-paper">
                      <div className="th-title">{p.paper_title}</div>
                    </th>
                  ))}
                  <th className="col-gap">Gap?</th>
                </tr>
              </thead>
              <tbody>
                {metricAlignment.map((row, i) => (
                  <tr key={i} className={row.has_gap ? 'row-gap' : (i % 2 === 0 ? 'row-a' : 'row-b')}>
                    <td className="td-factor td-metric-name">{row.metric_name}</td>
                    {papers.map((p, j) => (
                      <td key={j} className={`td-value ${row.values[p.paper_title] === '—' ? 'td-missing' : ''}`}>
                        {row.values[p.paper_title] || '—'}
                      </td>
                    ))}
                    <td className="td-gap">
                      {row.has_gap
                        ? <span className="gap-badge">Gap</span>
                        : <span className="ok-badge">✓</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="metric-note">
            Red rows = metrics reported by some papers but missing in others.
          </div>
        </>
      )}
    </div>
  );
}

// ── Formulas Tab ──────────────────────────────────────────────────────────────
function FormulasTab({ papers, formulaRegistry }) {
  useMathJax(papers);
  const hasRegistry = formulaRegistry?.length > 0 && papers.length > 1;

  return (
    <div className="tab-body">

      {hasRegistry && (
        <>
          <div className="section-heading">
            Formula Registry
            <span className="section-heading-sub">Shared across multiple papers</span>
          </div>
          <div className="registry-list">
            {formulaRegistry.map((entry, i) => (
              <div key={i} className="registry-card">
                <div className="registry-header">
                  <span className="registry-name">{entry.canonical_name}</span>
                  <span className="registry-count">{entry.occurrences.length} papers</span>
                </div>
                {entry.shared_symbols.length > 0 && (
                  <div className="registry-symbols">
                    Shared symbols: {entry.shared_symbols.join(', ')}
                  </div>
                )}
                <div className="registry-occurrences">
                  {entry.occurrences.map((occ, j) => (
                    <div key={j} className="registry-occ">
                      <div className="occ-meta">
                        <span className="occ-paper">{occ.paper}</span>
                        {occ.page && <span className="occ-page">pg {occ.page}</span>}
                        {occ.section && <span className="occ-section">{occ.section}</span>}
                        {occ.variant_note && <span className="occ-variant">variant</span>}
                      </div>
                      <MathBlock latex={occ.latex} />
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {papers.map((paper, pi) => (
        <div key={pi}>
          <div className="section-heading" style={pi === 0 && !hasRegistry ? {} : { marginTop: 36 }}>
            {paper.paper_title}
            <span className="section-heading-sub">
              {paper.formulas.length} formula{paper.formulas.length !== 1 ? 's' : ''} extracted
              {paper.image_formulas_found > 0 &&
                <span style={{ color: '#fbbf24', marginLeft: 8 }}>
                  · {paper.image_formulas_found} from images
                </span>}
            </span>
          </div>

          {paper.formulas.length === 0 ? (
            <div className="empty-state">No formulas extracted from this paper.</div>
          ) : (
            <div className="formulas-grid">
              {paper.formulas.map((f, fi) => {
                const sectionLabel = f.section || '';
                const tagCls = ['methodology', 'results', 'experiments', 'abstract']
                  .find(k => sectionLabel.toLowerCase().includes(k)) || 'cat';

                return (
                  <div key={fi} className="formula-card">

                    {/* Name + tags */}
                    <div className="fc-header">
                      <span className="fc-name">{f.name || 'Formula'}</span>
                      <div className="fc-tags">
                        {f.page && <span className="tag tag-page">pg {f.page}</span>}
                        {sectionLabel && (
                          <span className={`tag tag-${tagCls}`}>
                            {sectionLabel.length > 22 ? sectionLabel.slice(0, 22) + '…' : sectionLabel}
                          </span>
                        )}
                        {f.source === 'image' && (
                          <span className="tag" style={{ background: 'rgba(251,191,36,.12)', color: '#fbbf24' }}>
                            📷 image
                          </span>
                        )}
                      </div>
                    </div>

                    {/* LaTeX render */}
                    <div className="fc-math">
                      {f.latex
                        ? <MathBlock latex={f.latex} />
                        : <span style={{ color: '#333', fontSize: '.8em' }}>No LaTeX available</span>
                      }
                    </div>

                    {/* Structured rows */}
                    <div className="fc-details">
                      <div className="fc-row">
                        <span className="fc-label">Meaning</span>
                        <span className="fc-val">{f.meaning || '—'}</span>
                      </div>
                      <div className="fc-row">
                        <span className="fc-label">Symbols</span>
                        <span className="fc-val" style={{ fontFamily: 'monospace', fontSize: '.79em', lineHeight: 1.7 }}>
                          {f.explanation || '—'}
                        </span>
                      </div>
                      <div className="fc-row">
                        <span className="fc-label">Purpose</span>
                        <span className="fc-val">{f.purpose || '—'}</span>
                      </div>
                      <div className="fc-row fc-row-result">
                        <span className="fc-label">Result</span>
                        <span className="fc-val fc-result-val">
                          {f.results_obtained && f.results_obtained !== 'N/A'
                            ? f.results_obtained
                            : <span style={{ color: '#333' }}>N/A</span>}
                        </span>
                      </div>
                    </div>

                  </div>
                );
              })}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Methodology Tab ───────────────────────────────────────────────────────────
const STEP_COLORS = ['#00d4ff', '#a78bfa', '#34d399', '#fbbf24', '#f87171', '#60a5fa', '#f59e0b', '#ec4899'];

function MethodologyTab({ papers }) {
  const [active, setActive] = useState(0);
  const paper = papers[active];

  return (
    <div className="tab-body">
      {papers.length > 1 && (
        <div className="paper-pills">
          {papers.map((p, i) => (
            <button key={i}
              className={`pill-btn ${active === i ? 'pill-active' : ''}`}
              onClick={() => setActive(i)}>
              {p.paper_title.length > 35 ? p.paper_title.slice(0, 35) + '…' : p.paper_title}
            </button>
          ))}
        </div>
      )}
      {!paper?.methodology_steps?.length ? (
        <div className="empty-state">No methodology steps extracted.</div>
      ) : (
        <div className="steps-list">
          {paper.methodology_steps.map((step, i) => (
            <div key={i} className="step-row">
              <div className="step-num" style={{ background: STEP_COLORS[i % STEP_COLORS.length] }}>
                {step.step_number}
              </div>
              <div className="step-body">
                <div className="step-title">{step.title}</div>
                <div className="step-desc">{step.description}</div>
                {step.key_detail && (
                  <div className="step-key">
                    <span className="step-key-label">Key detail</span>
                    <span className="step-key-val">{step.key_detail}</span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Claim Verification Tab ───────────────────────────────────────────────────
const STATUS_META = {
  supported: { color: '#34d399', icon: '✅', label: 'Supported' },
  unsupported: { color: '#f87171', icon: '❌', label: 'Unsupported' },
  original_contribution: { color: '#a78bfa', icon: '⭐', label: 'Original Contribution' },
};

function ClaimsTab({ papers }) {
  const [active, setActive] = React.useState(0);
  const paper = papers[active];
  const claims = paper?.claim_verification || [];

  return (
    <div className="tab-body">
      {papers.length > 1 && (
        <div className="paper-pills">
          {papers.map((p, i) => (
            <button key={i} className={`pill-btn ${active === i ? 'pill-active' : ''}`}
              onClick={() => setActive(i)}>
              {p.paper_title.length > 35 ? p.paper_title.slice(0, 35) + '…' : p.paper_title}
            </button>
          ))}
        </div>
      )}

      <div className="section-heading">
        Claim Verification
        <span className="section-heading-sub">
          Citation-graph grounded — claims checked against citations in their section
        </span>
      </div>

      {claims.length === 0 ? (
        <div className="empty-state">No claims extracted for this paper.</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {claims.filter(c => c.status !== 'unsupported').map((c, i) => {
            const meta = STATUS_META[c.status] || STATUS_META.unsupported;
            return (
              <div key={i} style={{
                background: '#0f0f0f', border: `1px solid #1a1a1a`,
                borderLeft: `3px solid ${meta.color}`,
                borderRadius: 10, padding: '16px 18px'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, marginBottom: 10 }}>
                  <span style={{ fontSize: '.92em', fontWeight: 700, color: '#e0e0e0', lineHeight: 1.5, flex: 1 }}>
                    {meta.icon} {c.claim}
                  </span>
                  <span style={{
                    fontSize: '.68em', fontWeight: 800, padding: '3px 10px',
                    borderRadius: 5, background: `${meta.color}18`, color: meta.color,
                    whiteSpace: 'nowrap', flexShrink: 0
                  }}>
                    {meta.label}
                  </span>
                </div>

                <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: '.78em', color: '#555', marginBottom: c.citations_found?.length || c.risk_note ? 10 : 0 }}>
                  {c.section && <span>📍 {c.section}</span>}
                  {c.page && <span>pg {c.page}</span>}
                </div>

                {c.citations_found?.length > 0 && (
                  <div style={{ fontSize: '.78em', color: '#555', marginBottom: 6 }}>
                    <span style={{ color: '#3a3a3a', fontWeight: 700, marginRight: 6 }}>CITATIONS:</span>
                    {c.citations_found.join(', ')}
                  </div>
                )}


              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Research Gaps Tab ─────────────────────────────────────────────────────────
const GAP_COLORS = {
  language: '#00d4ff', dataset: '#a78bfa', model: '#34d399',
  domain: '#fbbf24', metric: '#f87171', other: '#888'
};

function GapsTab({ papers, crossPaperGaps }) {
  return (
    <div className="tab-body">

      {/* Cross-paper gaps — only when multiple papers */}
      {crossPaperGaps?.length > 0 && (
        <>
          <div className="section-heading">
            Shared Research Gaps
            <span className="section-heading-sub">
              These gaps appear across multiple papers — highest significance
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 36 }}>
            {crossPaperGaps.map((g, i) => (
              <div key={i} style={{
                background: '#0f0f0f', border: '1px solid #1a1a1a',
                borderLeft: '3px solid #fbbf24', borderRadius: 10, padding: '16px 18px'
              }}>
                <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 8 }}>
                  <span style={{
                    fontSize: '.68em', fontWeight: 800, padding: '2px 8px',
                    background: 'rgba(251,191,36,.12)', color: '#fbbf24', borderRadius: 5
                  }}>
                    {g.gap_type?.toUpperCase()}
                  </span>
                  <span style={{ fontSize: '.68em', color: '#555' }}>
                    Found in {g.found_in_papers?.length} papers
                  </span>
                </div>
                <div style={{ fontSize: '.88em', fontWeight: 600, color: '#e0e0e0', marginBottom: 6 }}>
                  {g.description}
                </div>
                <div style={{ fontSize: '.8em', color: '#666', lineHeight: 1.55 }}>
                  {g.significance}
                </div>
                <div style={{ fontSize: '.74em', color: '#3a3a3a', marginTop: 8 }}>
                  {g.found_in_papers?.join(' · ')}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Per-paper gaps */}
      {papers.map((paper, pi) => {
        const gaps = paper.research_gaps || [];
        return (
          <div key={pi}>
            <div className="section-heading" style={pi > 0 ? { marginTop: 32 } : {}}>
              {paper.paper_title}
              <span className="section-heading-sub">{gaps.length} gaps identified</span>
            </div>
            {gaps.length === 0 ? (
              <div className="empty-state">No research gaps identified.</div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12, marginBottom: 8 }}>
                {gaps.map((g, gi) => {
                  const col = GAP_COLORS[g.gap_type] || GAP_COLORS.other;
                  return (
                    <div key={gi} style={{
                      background: '#0f0f0f', border: '1px solid #1a1a1a',
                      borderTop: `2px solid ${col}`, borderRadius: 10, padding: '14px 16px'
                    }}>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
                        <span style={{
                          fontSize: '.66em', fontWeight: 800, padding: '2px 8px',
                          background: `${col}18`, color: col, borderRadius: 4
                        }}>
                          {g.gap_type?.toUpperCase()}
                        </span>
                      </div>
                      <div style={{ fontSize: '.86em', fontWeight: 600, color: '#ddd', marginBottom: 6, lineHeight: 1.45 }}>
                        {g.description}
                      </div>
                      <div style={{ fontSize: '.79em', color: '#666', lineHeight: 1.55 }}>
                        {g.significance}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Issues Tab ────────────────────────────────────────────────────────────────
const SEV = {
  strong: { icon: '🟢', label: 'STRONG', cls: 'sev-strong' },
  issue: { icon: '🟡', label: 'ISSUE', cls: 'sev-issue' },
  critical: { icon: '🔴', label: 'CRITICAL', cls: 'sev-critical' },
};

function IssuesTab({ papers }) {
  const total = papers.reduce((s, p) => s + (p.potential_issues?.length || 0), 0);
  if (total === 0)
    return <div className="tab-body"><div className="empty-state">✅ No potential issues detected.</div></div>;

  return (
    <div className="tab-body">
      {papers.map((paper, pi) => (
        <div key={pi}>
          <div className="section-heading" style={pi > 0 ? { marginTop: 32 } : {}}>
            {paper.paper_title}
            <span className="section-heading-sub">
              {paper.potential_issues.length} issue{paper.potential_issues.length !== 1 ? 's' : ''}
            </span>
          </div>
          {paper.potential_issues.length === 0 ? (
            <div className="empty-state">✅ No issues.</div>
          ) : (
            <div className="issues-list">
              {paper.potential_issues.map((issue, ii) => {
                const meta = SEV[issue.severity] || SEV.issue;
                return (
                  <div key={ii} className={`issue-card ${meta.cls}`}>
                    <span className="issue-icon">{meta.icon}</span>
                    <div className="issue-body">
                      <div className="issue-top">
                        <span className={`issue-badge ${meta.cls}-badge`}>{meta.label}</span>
                      </div>
                      <div className="issue-title">{issue.title}</div>
                      <div className="issue-detail">{issue.detail}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Live Progress ─────────────────────────────────────────────────────────────
function LiveProgress({ jobId, progress, message, papers }) {
  const icon = s => ({
    complete: '✅', failed: '❌', analyzing: '🤖',
    building_graph: '🕸️', extracting: '📄', chunking: '✂️', merging: '🔀', queued: '⏳'
  }[s] || '⏳');

  return (
    <div className="live-box">
      <div className="live-top">
        <span className="live-id">Job #{jobId}</span>
        <span className="live-pct">{progress}%</span>
      </div>
      <div className="live-msg">{message}</div>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${progress}%` }} />
      </div>
      <div className="live-papers">
        {Object.entries(papers || {}).map(([fn, s]) => (
          <div key={fn} className={`live-row live-${s.status}`}>
            <span className="live-icon">{icon(s.status)}</span>
            <div className="live-info">
              <div className="live-fn">{fn.replace('.pdf', '').slice(0, 40)}</div>
              <div className="live-state">{s.message || s.status}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Export ────────────────────────────────────────────────────────────────────
function exportJSON(data) {
  const b = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const a = document.createElement('a'); a.href = URL.createObjectURL(b);
  a.download = 'analysis.json'; a.click();
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function AnalyzePage() {
  useMathJax(null);

  const MAX_PAPERS = 3;

  const [files, setFiles] = useState([]);
  const [dragging, setDragging] = useState(false);
  const [phase, setPhase] = useState('upload');
  const [jobId, setJobId] = useState(null);
  const [jobState, setJobState] = useState(null);
  const [error, setError] = useState(null);
  const [results, setResults] = useState(null);
  const [tab, setTab] = useState('comparison');
  const inputRef = useRef();
  const pollRef = useRef();

  const fmt = n => n >= 1e6 ? (n / 1e6).toFixed(1) + ' MB' : (n / 1024).toFixed(0) + ' KB';

  const addFiles = useCallback(inc => {
    const pdfs = Array.from(inc).filter(f => f.name.toLowerCase().endsWith('.pdf'));
    setFiles(prev => {
      const merged = [...prev, ...pdfs];
      const unique = merged.filter((f, i, arr) => arr.findIndex(x => x.name === f.name) === i);
      return unique.slice(0, MAX_PAPERS);
    });
  }, []);

  const startPolling = useCallback(id => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const res = await api.analyzer.status(id);
        const s = res.data;
        setJobState(s);
        if (s.status === 'complete') {
          clearInterval(pollRef.current);
          setResults(s.result); setPhase('results'); setTab('comparison');
          setTimeout(() => window.MathJax?.typesetPromise?.(), 600);
          api.analyzer.deleteJob(id).catch(() => { });
        }
        if (s.status === 'failed') {
          clearInterval(pollRef.current);
          setError(s.error || 'Analysis failed.'); setPhase('upload');
        }
      } catch {
        clearInterval(pollRef.current);
        setError('Connection lost.'); setPhase('upload');
      }
    }, 3000);
  }, []);

  useEffect(() => () => clearInterval(pollRef.current), []);

  const handleAnalyze = async () => {
    if (!files.length) return;
    setError(null);
    try {
      const fd = new FormData();
      files.forEach(f => fd.append('files', f));
      const res = await api.analyzer.submit(fd);
      setJobId(res.data.job_id); setPhase('polling'); startPolling(res.data.job_id);
    } catch (err) {
      setError(err.response?.data?.detail || 'Submit failed.');
    }
  };

  const reset = () => {
    clearInterval(pollRef.current);
    setFiles([]); setResults(null); setError(null);
    setJobId(null); setJobState(null); setPhase('upload');
  };

  return (
    <div className="analyze-page">

      <div className="ap-header">
        <h1 className="ap-title">Research Paper Analyzer</h1>
        <p className="ap-subtitle">
          Full-text PDF Extraction · AI-Powered Semantic Breakdown · Cross-Paper Comparison
        </p>
        <p style={{ color: '#555', fontSize: '.85em', marginTop: 8 }}>
          Upload up to {MAX_PAPERS} papers to extract formulas, methodology, metrics and compare side-by-side.
        </p>
      </div>

      {phase === 'upload' && (
        <div className="upload-box">
          <div className="upload-label">Upload Research Papers — up to {MAX_PAPERS} PDFs</div>

          <div className={`dropzone ${dragging ? 'dz-over' : ''}`}
            onDrop={e => { e.preventDefault(); setDragging(false); addFiles(e.dataTransfer.files); }}
            onDragOver={e => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onClick={() => inputRef.current?.click()}>
            <input ref={inputRef} type="file" accept=".pdf" multiple
              style={{ display: 'none' }} onChange={e => addFiles(e.target.files)} />
            <div className="dz-icon">📄</div>
            <div className="dz-text">Drag &amp; drop PDFs or <span className="dz-link">browse</span></div>
            <div className="dz-hint">PDF only · max 50MB each · up to {MAX_PAPERS} papers</div>
          </div>

          {files.length > 0 && (
            <div className="file-list">
              {files.map((f, i) => (
                <div key={i} className="file-item">
                  <span className="fi-icon">📄</span>
                  <span className="fi-name">{f.name}</span>
                  <span className="fi-size">{fmt(f.size)}</span>
                  <button className="fi-rm"
                    onClick={e => { e.stopPropagation(); setFiles(p => p.filter((_, j) => j !== i)); }}>
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}

          <button className="go-btn" onClick={handleAnalyze} disabled={!files.length}>
            {files.length
              ? `Analyze ${files.length} Paper${files.length > 1 ? 's' : ''}`
              : 'Select Papers to Begin'}
          </button>
        </div>
      )}

      {error && <div className="error-banner"><span>⚠</span> {error}</div>}

      {phase === 'polling' && jobState && (
        <LiveProgress jobId={jobId} progress={jobState.progress}
          message={jobState.message} papers={jobState.papers} />
      )}

      {phase === 'results' && results && (
        <div className="results-area">

          <div className="paper-header-row">
            {results.papers.map((p, i) => (
              <div key={i} className="paper-hcard">
                <div className="phc-title">{p.paper_title}</div>
                <div className="phc-meta">
                  <span>{p.pages} pages</span>
                  <span className="phc-dot">·</span>
                  <span>{p.formulas?.length || 0} formulas</span>
                  <span className="phc-dot">·</span>
                  <span>{p.metrics?.length || 0} metrics</span>
                  <span className="phc-dot">·</span>
                  <span>{p.methodology_steps?.length || 0} steps</span>
                </div>
              </div>
            ))}
          </div>

          <div className="tab-bar">
            {TABS.map(t => (
              <button key={t.id} className={`tab-btn ${tab === t.id ? 'tab-on' : ''}`}
                onClick={() => { setTab(t.id); setTimeout(() => window.MathJax?.typesetPromise?.(), 200); }}>
                {t.label}
              </button>
            ))}
          </div>

          {tab === 'comparison' && <ComparisonTab table={results.comparison_table} metricAlignment={results.metric_alignment} papers={results.papers} />}
          {tab === 'formulas' && <FormulasTab papers={results.papers} formulaRegistry={results.formula_registry} />}
          {tab === 'methodology' && <MethodologyTab papers={results.papers} />}
          {tab === 'issues' && <IssuesTab papers={results.papers} />}
          {tab === 'claims' && <ClaimsTab papers={results.papers} />}

          <div className="action-row">
            <button className="btn-export" onClick={() => exportJSON(results)}>💾 Export JSON</button>
            <button className="btn-reset" onClick={reset}>← New Analysis</button>
          </div>
        </div>
      )}
    </div>
  );
}