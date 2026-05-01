import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';

function TranslatePage() {
  const navigate = useNavigate();

  // State: array of objects { file, status, summary, sections, translation, error }
  const [tasks, setTasks] = useState([]);

  const handleProcess = async (index) => {
    setTasks(prev => {
      const newTasks = [...prev];
      newTasks[index] = { ...newTasks[index], status: 'loading', error: null };
      return newTasks;
    });

    try {
      const formData = new FormData();
      formData.append('file', tasks[index].file);
      formData.append('max_length', '512');
      formData.append('source_lang', 'de');
      formData.append('target_lang', 'en');

      const res = await api.summarization.translateAndSummarizeFile(formData);

      const summaryText = res.data?.final_summary || '';
      const translationText = res.data?.translation || '';

      setTasks(prev => {
        const newTasks = [...prev];
        newTasks[index] = {
          ...newTasks[index],
          status: 'success',
          summary: summaryText,
          sections: res.data?.sections || null,
          translation: translationText
        };
        return newTasks;
      });
    } catch (err) {
      setTasks(prev => {
        const newTasks = [...prev];
        newTasks[index] = { ...newTasks[index], status: 'error', error: err.response?.data?.detail || err.message || 'Request failed' };
        return newTasks;
      });
    }
  };


  const handleUpload = (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    const newTasks = files.map(f => ({
      file: f,
      status: 'idle',
      summary: null,
      sections: null,
      translation: null,
      error: null,
    }));

    setTasks(prev => [...newTasks, ...prev]);
    e.target.value = '';
  };

  return (
    <div style={{ padding: '40px', maxWidth: '1000px', margin: '0 auto', color: 'white' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px' }}>
        <div>
          <h1 style={{ margin: 0 }}>🌍 Translate & Summarize</h1>
          <p style={{ color: '#a0a0a0', marginTop: '5px' }}>
            Upload German PDF(s) to translate to English and automatically summarize ({tasks.length} item(s))
          </p>
        </div>
        <div style={{ display: 'flex', gap: '15px' }}>
          <button
            className="animated-btn"
            onClick={() => navigate('/')}
            style={{ padding: '10px 20px', backgroundColor: 'rgba(0, 212, 255, 0.1)', border: '1px solid #00d4ff', color: '#00d4ff', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold' }}
          >
            ← Home
          </button>

        </div>
      </div>

      <div style={{ marginBottom: '20px', backgroundColor: '#2b2d42', padding: '16px', borderRadius: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>Upload papers (German PDF)</div>
            <div style={{ color: '#a0a0a0', fontSize: '0.95rem' }}>Each PDF will be translated to English and then summarized. Both text and summary will appear below.</div>
          </div>
          <label className="upload-label" style={{ padding: '10px 16px', background: 'linear-gradient(135deg, #00d4ff 0%, #00a8cc 100%)', color: '#0a0a0a', borderRadius: '8px', cursor: 'pointer', fontWeight: 600 }}>
            Upload PDF(s)
            <input type="file" accept="application/pdf,.pdf" multiple onChange={handleUpload} style={{ display: 'none' }} />
          </label>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {tasks.length === 0 && (
          <div style={{ backgroundColor: '#2b2d42', padding: '24px', borderRadius: '12px', textAlign: 'center', color: '#a0a0a0' }}>
            No items yet. Upload a German PDF above.
          </div>
        )}
        {tasks.map((task, idx) => (
          <div key={idx} className="task-card" style={{ backgroundColor: '#2b2d42', padding: '25px', borderRadius: '16px', border: '1px solid rgba(255,255,255,0.05)', boxShadow: '0 8px 16px rgba(0,0,0,0.2)' }}>
            <h3 style={{ marginTop: 0, color: '#fff', fontSize: '1.4rem' }}>{task.file?.name}</h3>
            <p style={{ fontSize: '0.95rem', color: '#a0a0a0' }}>
              Source: Uploaded PDF File
            </p>

            <div style={{ marginTop: '20px', display: 'flex', gap: '15px' }}>
              <button
                className="animated-btn"
                onClick={() => handleProcess(idx)}
                disabled={task.status === 'loading'}
                style={{ padding: '10px 20px', background: 'linear-gradient(135deg, #00d4ff 0%, #00a8cc 100%)', color: '#0a0a0a', border: 'none', borderRadius: '8px', cursor: task.status === 'loading' ? 'not-allowed' : 'pointer', fontWeight: '600' }}
              >
                {task.status === 'loading' ? 'Processing...' : 'Translate & Summarize'}
              </button>
            </div>

            {task.status === 'loading' && (
              <div style={{ marginTop: '20px', color: '#fca311', display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ display: 'inline-block', width: '20px', height: '20px', border: '3px solid #fca311', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                <span>Extracting, translating to English, and analyzing document... This could take up to a few minutes depending on PDF length.</span>
              </div>
            )}

            {task.error && (
              <div style={{ marginTop: '20px', color: '#fff', backgroundColor: '#d90429', padding: '15px', borderRadius: '8px' }}>
                <strong>❌ Process Failed:</strong> {task.error}
              </div>
            )}

            {task.summary && (
              <div style={{ marginTop: '25px', padding: '20px', backgroundColor: '#1d1e2c', borderRadius: '8px', borderLeft: '5px solid #4cc9f0' }}>
                <h4 style={{ marginTop: 0, color: '#4cc9f0', fontSize: '1.2rem', marginBottom: '10px' }}>Generated English Summary (LongT5)</h4>
                <p style={{ whiteSpace: 'pre-wrap', lineHeight: '1.7', margin: 0, fontSize: '1.05rem' }}>{task.summary}</p>
              </div>
            )}

            {task.sections && Object.keys(task.sections).length > 0 && (
              <div style={{ marginTop: '18px' }}>
                <h4 style={{ margin: '0 0 10px 0', color: '#9bf6ff', fontSize: '1.05rem' }}>Section English summaries</h4>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '10px' }}>
                  {Object.entries(task.sections)
                    .filter(([, v]) => typeof v === 'string' && v.trim().length > 0)
                    .map(([sectionName, sectionText]) => (
                      <details
                        key={sectionName}
                        className="details-panel"
                        style={{
                          backgroundColor: '#1d1e2c',
                          borderRadius: '10px',
                          border: '1px solid rgba(255,255,255,0.08)',
                          overflow: 'hidden',
                        }}
                      >
                        <summary
                          style={{
                            cursor: 'pointer',
                            padding: '12px 14px',
                            listStyle: 'none',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: '12px',
                            userSelect: 'none',
                          }}
                        >
                          <span style={{ fontWeight: 700, color: '#fff', textTransform: 'capitalize' }}>{sectionName}</span>
                          <span style={{ color: '#a0a0a0', fontSize: '0.9rem' }}>Click to expand</span>
                        </summary>
                        <div style={{ padding: '0 14px 14px 14px' }}>
                          <div style={{ height: '1px', backgroundColor: 'rgba(255,255,255,0.06)', marginBottom: '12px' }} />
                          <p style={{ margin: 0, whiteSpace: 'pre-wrap', lineHeight: '1.7', color: '#e6e6e6' }}>
                            {sectionText}
                          </p>
                        </div>
                      </details>
                    ))}
                </div>
              </div>
            )}

            {/*task.translation && (
              <div style={{ marginTop: '25px', padding: '20px', backgroundColor: '#1d1e2c', borderRadius: '8px', borderLeft: '5px solid #f72585' }}>
                <h4 style={{ marginTop: 0, color: '#f72585', fontSize: '1.2rem', marginBottom: '10px' }}>Full English Translation (OPUS-MT)</h4>
                <p style={{ whiteSpace: 'pre-wrap', lineHeight: '1.7', margin: 0, fontSize: '1.05rem' }}>{task.translation}</p>
              </div>
            )*/}
          </div>
        ))}
      </div>
      <style>{`
        @keyframes spin { 100% { transform: rotate(360deg); } }
        
        .animated-btn {
          transition: all 0.3s ease;
        }
        .animated-btn:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(0,0,0,0.3);
          filter: brightness(1.1);
        }
        .animated-btn:active:not(:disabled) {
          transform: translateY(0);
        }

        .task-card {
          transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        .task-card:hover {
          transform: translateY(-4px);
          box-shadow: 0 12px 24px rgba(0,0,0,0.4) !important;
        }

        .details-panel summary {
          transition: background-color 0.2s ease;
        }
        .details-panel summary:hover {
          background-color: rgba(255,255,255,0.05);
        }
        
        .upload-label {
          transition: all 0.3s ease;
        }
        .upload-label:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(67, 97, 238, 0.4);
          filter: brightness(1.1);
        }
      `}</style>
    </div>
  );
}

export default TranslatePage;
