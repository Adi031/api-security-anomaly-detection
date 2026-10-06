import React from 'react';
import { formatTimestamp, truncateId } from '../utils/formatters';

export const AlertFeed = ({ alerts, onAlertClick }) => {
  return (
    <div className="card" style={{ flex: 1, minHeight: 0 }}>
      <div className="card-header flex justify-between items-center">
        <span>Recent Alerts</span>
        <span className="badge" style={{ background: 'rgba(255,255,255,0.1)' }}>{alerts.length}</span>
      </div>
      <div className="card-body" style={{ padding: 0, overflowY: 'auto' }}>
        {alerts.map((alert, idx) => (
          <div 
            key={alert.id || idx} 
            onClick={() => onAlertClick && onAlertClick(alert)}
            style={{
              padding: '12px 16px',
              borderBottom: '1px solid rgba(255,255,255,0.05)',
              cursor: 'pointer',
              borderLeft: alert.severity === 'critical' ? '2px solid var(--color-danger)' : '2px solid transparent',
              background: alert.severity === 'critical' ? 'rgba(239, 68, 68, 0.05)' : 'transparent',
              transition: 'background 0.2s',
              animation: alert.severity === 'critical' ? 'pulse-red 2s infinite' : 'fade-in 0.3s'
            }}
            onMouseOver={(e) => {
              if (alert.severity !== 'critical') e.currentTarget.style.background = 'rgba(255,255,255,0.02)';
            }}
            onMouseOut={(e) => {
              if (alert.severity !== 'critical') e.currentTarget.style.background = 'transparent';
            }}
          >
            <div className="flex justify-between items-center" style={{ marginBottom: '6px' }}>
              <span className={`badge badge-${alert.severity === 'critical' ? 'critical' : 'warning'}`}>
                {alert.severity}
              </span>
              <span className="text-muted" style={{ fontSize: '11px' }}>
                {formatTimestamp(alert.timestamp)}
              </span>
            </div>
            <div style={{ fontSize: '13px', fontWeight: 500, marginBottom: '4px' }}>
              {alert.description}
            </div>
            <div className="flex justify-between items-center" style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>
              <span>Session: <span style={{ fontFamily: 'monospace' }}>{truncateId(alert.session_id)}</span></span>
              <span>Score: <span style={{ color: alert.severity === 'critical' ? 'var(--color-danger)' : 'var(--color-warning)', fontWeight: 600 }}>{alert.score?.toFixed(1)}</span></span>
            </div>
          </div>
        ))}
        {alerts.length === 0 && (
          <div style={{ padding: '20px', textAlign: 'center', color: 'var(--color-text-secondary)' }}>
            No alerts generated. System is clean.
          </div>
        )}
      </div>
    </div>
  );
};
