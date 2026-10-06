import React from 'react';

export const StatusIndicator = ({ isConnected }) => {
  return (
    <div className="flex items-center gap-2" style={{ fontSize: '12px', fontWeight: 600 }}>
      <span className={`status-dot ${isConnected ? 'status-connected' : 'status-disconnected'}`}></span>
      <span style={{ color: isConnected ? 'var(--color-success)' : 'var(--color-danger)' }}>
        {isConnected ? 'LIVE' : 'RECONNECTING...'}
      </span>
    </div>
  );
};
