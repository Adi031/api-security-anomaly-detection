import React, { useEffect, useState } from 'react';
import { fetchSessionDetail } from '../utils/api';
import { truncateId, formatDuration, formatScore, getSeverityColor } from '../utils/formatters';

export const SessionDrilldown = ({ sessionId, isOpen, onClose }) => {
  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen && sessionId) {
      setLoading(true);
      fetchSessionDetail(sessionId).then(data => {
        setDetails(data);
        setLoading(false);
      });
    } else {
      setDetails(null);
    }
  }, [isOpen, sessionId]);

  if (!isOpen) return null;

  return (
    <div className={`right-panel ${isOpen ? 'open' : ''}`}>
      <div className="flex justify-between items-center" style={{ padding: '20px', borderBottom: '1px solid var(--color-border)' }}>
        <h2 style={{ fontSize: '16px', fontWeight: 600 }}>Session Drilldown</h2>
        <button 
          onClick={onClose}
          style={{ 
            background: 'transparent', border: 'none', color: 'var(--color-text-secondary)', 
            cursor: 'pointer', fontSize: '18px', padding: '4px' 
          }}
        >
          ✕
        </button>
      </div>

      <div style={{ padding: '20px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', color: 'var(--color-text-secondary)', marginTop: '40px' }}>Loading...</div>
        ) : details ? (
          <>
            <div className="card" style={{ padding: '16px', borderLeft: `3px solid ${getSeverityColor(details.score >= 90 ? 'critical' : details.score >= 70 ? 'warning' : 'normal')}` }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <div className="text-muted" style={{ fontSize: '11px', textTransform: 'uppercase' }}>Session ID</div>
                  <div style={{ fontFamily: 'monospace', fontSize: '13px' }}>{truncateId(details.session_id)}</div>
                </div>
                <div>
                  <div className="text-muted" style={{ fontSize: '11px', textTransform: 'uppercase' }}>Risk Score</div>
                  <div style={{ fontWeight: 700, fontSize: '16px', color: getSeverityColor(details.score >= 90 ? 'critical' : details.score >= 70 ? 'warning' : 'normal') }}>
                    {formatScore(details.score)}
                  </div>
                </div>
                <div>
                  <div className="text-muted" style={{ fontSize: '11px', textTransform: 'uppercase' }}>IP / User</div>
                  <div>{details.ip || 'Unknown'}</div>
                </div>
                <div>
                  <div className="text-muted" style={{ fontSize: '11px', textTransform: 'uppercase' }}>Duration</div>
                  <div>{formatDuration(details.duration || 0)}</div>
                </div>
              </div>
            </div>

            <div>
              <h3 style={{ fontSize: '13px', textTransform: 'uppercase', color: 'var(--color-text-secondary)', marginBottom: '12px' }}>Flagged Features</h3>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {(details.features || []).map((feat, i) => (
                  <span key={i} className="badge" style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)' }}>
                    {feat}
                  </span>
                ))}
                {(!details.features || details.features.length === 0) && (
                  <span className="text-muted">None detected</span>
                )}
              </div>
            </div>

            <div>
              <h3 style={{ fontSize: '13px', textTransform: 'uppercase', color: 'var(--color-text-secondary)', marginBottom: '12px' }}>Request History</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {(details.requests || []).map((req, i) => (
                  <div key={i} style={{ padding: '10px', background: 'rgba(255,255,255,0.02)', borderRadius: '4px', fontSize: '12px' }}>
                    <div className="flex justify-between" style={{ marginBottom: '4px' }}>
                      <span style={{ color: 'var(--color-text-secondary)' }}>{new Date(req.timestamp).toLocaleTimeString()}</span>
                      <span style={{ color: getSeverityColor(req.score >= 90 ? 'critical' : req.score >= 70 ? 'warning' : 'normal') }}>
                        Score: {req.score?.toFixed(1)}
                      </span>
                    </div>
                    <div style={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>
                      <span className={`badge badge-method-${req.method?.toLowerCase()}`} style={{ marginRight: '8px' }}>{req.method}</span>
                      {req.path}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        ) : (
          <div style={{ textAlign: 'center', color: 'var(--color-text-secondary)', marginTop: '40px' }}>
            Session details not found
          </div>
        )}
      </div>
    </div>
  );
};
