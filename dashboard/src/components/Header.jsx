import React, { useState, useEffect } from 'react';
import { StatusIndicator } from './StatusIndicator';

export const Header = ({ isConnected }) => {
  const [time, setTime] = useState(new Date().toLocaleTimeString());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date().toLocaleTimeString()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="header">
      <div className="flex items-center gap-4">
        <h1 style={{ fontSize: '18px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span>🛡️</span> API Shield
        </h1>
        <div className="badge" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
          Model: Sentinel-v2
        </div>
      </div>
      <div className="flex items-center gap-4">
        <StatusIndicator isConnected={isConnected} />
        <div style={{ color: 'var(--color-text-secondary)', fontWeight: 500 }}>
          {time}
        </div>
      </div>
    </header>
  );
};
