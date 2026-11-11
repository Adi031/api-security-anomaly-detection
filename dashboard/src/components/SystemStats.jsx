import React, { useEffect, useState, useRef } from 'react';

const AnimatedCounter = ({ value }) => {
  const num = typeof value === 'number' && !isNaN(value) ? value : 0;
  const [displayValue, setDisplayValue] = useState(num);
  const prevValue = useRef(num);

  useEffect(() => {
    if (num !== prevValue.current) {
      setDisplayValue(num);
      prevValue.current = num;
    }
  }, [num]);

  return <span style={{ animation: 'count-up 0.3s ease-out' }} key={displayValue}>{displayValue.toLocaleString()}</span>;
};

export const SystemStats = ({ stats }) => {
  const totalRequests = Number.isFinite(stats?.totalRequests) ? stats.totalRequests : (Number.isFinite(stats?.total_scored) ? stats.total_scored : 0);
  const activeSessions = Number.isFinite(stats?.activeSessions) ? stats.activeSessions : 0;
  const warnings = Number.isFinite(stats?.warnings) ? stats.warnings : (stats?.alerts_by_severity?.warning || 0);
  const criticalAlerts = Number.isFinite(stats?.criticalAlerts) ? stats.criticalAlerts : (stats?.alerts_by_severity?.critical || 0);
  
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
      <div className="card">
        <div className="card-body">
          <div className="text-muted" style={{ fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', marginBottom: '8px' }}>Total Requests</div>
          <div style={{ fontSize: '28px', fontWeight: 700, color: 'var(--color-text-primary)' }}>
            <AnimatedCounter value={totalRequests} />
          </div>
        </div>
      </div>
      
      <div className="card">
        <div className="card-body">
          <div className="text-muted" style={{ fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', marginBottom: '8px' }}>Active Sessions</div>
          <div style={{ fontSize: '28px', fontWeight: 700, color: 'var(--color-primary)' }}>
            <AnimatedCounter value={activeSessions} />
          </div>
        </div>
      </div>
      
      <div className="card">
        <div className="card-body">
          <div className="text-muted" style={{ fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', marginBottom: '8px' }}>Warnings</div>
          <div style={{ fontSize: '28px', fontWeight: 700, color: 'var(--color-warning)' }}>
            <AnimatedCounter value={warnings} />
          </div>
        </div>
      </div>
      
      <div className="card" style={criticalAlerts > 0 ? { animation: 'pulse-red 2s infinite' } : {}}>
        <div className="card-body">
          <div className="text-muted" style={{ fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', marginBottom: '8px' }}>Critical Alerts</div>
          <div style={{ fontSize: '28px', fontWeight: 700, color: 'var(--color-danger)' }}>
            <AnimatedCounter value={criticalAlerts} />
          </div>
        </div>
      </div>
    </div>
  );
};
