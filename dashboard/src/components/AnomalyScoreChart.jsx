import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { formatTimestamp } from '../utils/formatters';

export const AnomalyScoreChart = ({ data }) => {
  return (
    <div className="card" style={{ flex: 1, minHeight: '300px' }}>
      <div className="card-header">Live Anomaly Scores</div>
      <div className="card-body" style={{ padding: '16px 16px 16px 0' }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="colorScore" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-primary)" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="var(--color-primary)" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis 
              dataKey="timestamp" 
              tickFormatter={(ts) => {
                const date = new Date(ts);
                return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
              }} 
              stroke="var(--color-text-secondary)" 
              tick={{ fontSize: 12 }} 
              minTickGap={30}
            />
            <YAxis 
              domain={[0, 100]} 
              stroke="var(--color-text-secondary)" 
              tick={{ fontSize: 12 }} 
              tickCount={5}
            />
            <Tooltip 
              contentStyle={{ backgroundColor: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: '4px' }}
              labelFormatter={(label) => formatTimestamp(label)}
              itemStyle={{ color: 'var(--color-text-primary)' }}
            />
            <ReferenceLine y={70} stroke="var(--color-warning)" strokeDasharray="3 3" />
            <ReferenceLine y={90} stroke="var(--color-danger)" strokeDasharray="3 3" />
            <Area 
              type="monotone" 
              dataKey="score" 
              stroke="var(--color-primary)" 
              strokeWidth={2}
              fillOpacity={1} 
              fill="url(#colorScore)" 
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
