import React, { useRef, useEffect, useState } from 'react';
import { formatTimestamp, formatScore, getSeverityColor } from '../utils/formatters';

export const RequestTimeline = ({ requests }) => {
  const listRef = useRef(null);
  const [isHovered, setIsHovered] = useState(false);

  useEffect(() => {
    if (listRef.current && !isHovered) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [requests, isHovered]);

  const getMethodBadge = (method) => {
    const m = method?.toUpperCase() || 'GET';
    return <span className={`badge badge-method-${m.toLowerCase()}`}>{m}</span>;
  };

  const getScoreDot = (score) => {
    let color = 'var(--color-success)';
    if (score >= 90) color = 'var(--color-danger)';
    else if (score >= 70) color = 'var(--color-warning)';
    return <span className="status-dot" style={{ backgroundColor: color, flexShrink: 0 }}></span>;
  };

  return (
    <div className="card" style={{ flex: 1, minHeight: 0 }}>
      <div className="card-header">Live Request Stream</div>
      <div 
        className="card-body" 
        style={{ padding: 0, overflowY: 'auto' }}
        ref={listRef}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {requests.map((req, idx) => (
            <div key={req.id || idx} style={{
              display: 'flex', alignItems: 'center', padding: '10px 16px',
              borderBottom: '1px solid rgba(255,255,255,0.02)', gap: '12px',
              animation: 'fade-in 0.3s ease-out'
            }}>
              {getScoreDot(req.score)}
              <span className="text-muted" style={{ fontSize: '11px', flexShrink: 0, width: '60px' }}>
                {formatTimestamp(req.timestamp)}
              </span>
              <div style={{ width: '60px', flexShrink: 0 }}>
                {getMethodBadge(req.method)}
              </div>
              <span style={{ flex: 1, fontFamily: 'monospace', fontSize: '12px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {req.path}
              </span>
              <span style={{ color: req.status >= 400 ? 'var(--color-warning)' : 'var(--color-success)', fontSize: '12px', width: '30px', textAlign: 'right' }}>
                {req.status}
              </span>
              <span style={{ fontWeight: 600, fontSize: '12px', width: '40px', textAlign: 'right', color: getSeverityColor(req.score >= 90 ? 'critical' : req.score >= 70 ? 'warning' : 'normal') }}>
                {formatScore(req.score)}
              </span>
            </div>
          ))}
          {requests.length === 0 && (
            <div style={{ padding: '20px', textAlign: 'center', color: 'var(--color-text-secondary)' }}>
              No requests yet. Waiting for data...
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
