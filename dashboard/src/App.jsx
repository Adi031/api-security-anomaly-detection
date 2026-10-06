import React, { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { SystemStats } from './components/SystemStats';
import { AnomalyScoreChart } from './components/AnomalyScoreChart';
import { RequestTimeline } from './components/RequestTimeline';
import { AlertFeed } from './components/AlertFeed';
import { UserSessionTable } from './components/UserSessionTable';
import { SessionDrilldown } from './components/SessionDrilldown';
import { useWebSocket } from './hooks/useWebSocket';
import { useAlerts } from './hooks/useAlerts';
import { fetchStats, fetchSessions } from './utils/api';

function App() {
  const { isConnected, lastMessage } = useWebSocket('ws://127.0.0.1:8001/ws/live');
  const { alerts, addAlert } = useAlerts();

  const [stats, setStats] = useState({ totalRequests: 0, activeSessions: 0, warnings: 0, criticalAlerts: 0 });
  const [chartData, setChartData] = useState([]);
  const [requests, setRequests] = useState([]);
  const [sessions, setSessions] = useState([]);
  
  const [selectedSession, setSelectedSession] = useState(null);

  // Initial load
  useEffect(() => {
    fetchStats().then(data => {
      if (data) setStats(data);
    });
    fetchSessions().then(data => {
      if (data) setSessions(data);
    });
  }, []);

  // Handle WebSocket messages
  useEffect(() => {
    if (!lastMessage) return;

    const { type, data } = lastMessage;

    if (type === 'stats_update') {
      setStats({
        totalRequests: data.total_scored || 0,
        activeSessions: sessions.length,
        warnings: data.alerts_by_severity?.warning || 0,
        criticalAlerts: data.alerts_by_severity?.critical || 0
      });
    } else if (type === 'scored_request') {
      // Update chart
      setChartData(prev => {
        const newData = [...prev, { timestamp: data.timestamp, score: data.anomaly_score }];
        return newData.slice(-60); // keep last 60 points
      });
      // Update timeline
      setRequests(prev => {
        const newData = [...prev, { ...data, score: data.anomaly_score }];
        return newData.slice(-100); // keep last 100
      });
      
      // Update stats based on incoming request if not using stats_update
      setStats(prev => ({
        ...prev,
        totalRequests: prev.totalRequests + 1,
        activeSessions: prev.activeSessions // we'd need more logic for this, assuming backend sends stats_update
      }));
    } else if (type === 'alert') {
      addAlert(data);
      if (data.severity === 'critical') {
        setStats(prev => ({ ...prev, criticalAlerts: prev.criticalAlerts + 1 }));
      } else {
        setStats(prev => ({ ...prev, warnings: prev.warnings + 1 }));
      }
    }
  }, [lastMessage, addAlert]);

  const handleAlertClick = useCallback((alert) => {
    if (alert.session_id) {
      setSelectedSession(alert.session_id);
    }
  }, []);

  return (
    <div className="app-container">
      <Header isConnected={isConnected} />
      
      <main className="main-content">
        {/* Left Sidebar */}
        <aside className="sidebar-left">
          <AlertFeed alerts={alerts} onAlertClick={handleAlertClick} />
        </aside>

        {/* Center Panel */}
        <section className="center-panel">
          <SystemStats stats={stats} />
          
          <div className="flex gap-4" style={{ height: '300px' }}>
            <AnomalyScoreChart data={chartData} />
            <RequestTimeline requests={requests} />
          </div>

          <UserSessionTable 
            sessions={sessions} 
            onSessionClick={setSelectedSession} 
          />
        </section>

        {/* Right Panel - Slide In */}
        <SessionDrilldown 
          isOpen={!!selectedSession} 
          sessionId={selectedSession} 
          onClose={() => setSelectedSession(null)} 
        />
      </main>
    </div>
  );
}

export default App;
