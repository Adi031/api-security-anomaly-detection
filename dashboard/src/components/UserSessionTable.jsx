import React, { useState } from 'react';
import { truncateId, formatScore, getSeverityColor } from '../utils/formatters';

export const UserSessionTable = ({ sessions, onSessionClick, threshold = 0.526 }) => {
  const warningLine = threshold;
  const criticalLine = threshold * 2;
  const [sortConfig, setSortConfig] = useState({ key: 'score', direction: 'desc' });

  const sortedSessions = [...sessions].sort((a, b) => {
    if (a[sortConfig.key] < b[sortConfig.key]) {
      return sortConfig.direction === 'asc' ? -1 : 1;
    }
    if (a[sortConfig.key] > b[sortConfig.key]) {
      return sortConfig.direction === 'asc' ? 1 : -1;
    }
    return 0;
  });

  const requestSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  const getSortIndicator = (key) => {
    if (sortConfig.key !== key) return null;
    return sortConfig.direction === 'asc' ? ' ↑' : ' ↓';
  };

  return (
    <div className="card" style={{ flex: 1, minHeight: '300px' }}>
      <div className="card-header">Active Sessions</div>
      <div className="card-body" style={{ padding: 0, overflowY: 'auto' }}>
        <table>
          <thead style={{ position: 'sticky', top: 0, background: 'var(--color-surface)', zIndex: 1 }}>
            <tr>
              <th onClick={() => requestSort('session_id')}>Session ID{getSortIndicator('session_id')}</th>
              <th onClick={() => requestSort('ip')}>IP Address{getSortIndicator('ip')}</th>
              <th onClick={() => requestSort('score')}>Risk Score{getSortIndicator('score')}</th>
              <th onClick={() => requestSort('requests')}>Requests{getSortIndicator('requests')}</th>
              <th onClick={() => requestSort('status')}>Status{getSortIndicator('status')}</th>
            </tr>
          </thead>
          <tbody>
            {sortedSessions.map((session) => {
              const isFlagged = session.score >= warningLine;
              return (
                <tr 
                  key={session.session_id} 
                  className={isFlagged ? 'flagged' : ''}
                  onClick={() => onSessionClick && onSessionClick(session.session_id)}
                  style={{ cursor: 'pointer' }}
                >
                  <td style={{ fontFamily: 'monospace' }}>{truncateId(session.session_id)}</td>
                  <td>{session.ip || 'Unknown'}</td>
                  <td style={{ 
                    fontWeight: 600, 
                    color: getSeverityColor(session.score >= criticalLine ? 'critical' : session.score >= warningLine ? 'warning' : 'normal')
                  }}>
                    {formatScore(session.score)}
                  </td>
                  <td>{session.requests || 0}</td>
                  <td>
                    <span className={`badge badge-${isFlagged ? (session.score >= criticalLine ? 'critical' : 'warning') : 'normal'}`}>
                      {isFlagged ? (session.score >= criticalLine ? 'BLOCKED' : 'FLAGGED') : 'CLEAN'}
                    </span>
                  </td>
                </tr>
              );
            })}
            {sessions.length === 0 && (
              <tr>
                <td colSpan="5" style={{ textAlign: 'center', color: 'var(--color-text-secondary)', padding: '20px' }}>
                  No active sessions
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
