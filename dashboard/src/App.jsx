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
import { fetchStats, fetchSessions, fetchAlerts } from './utils/api';

function App() {
  const { isConnected, lastMessage } = useWebSocket('ws://127.0.0.1:8001/ws/live');
  const { alerts, setAlerts, addAlert } = useAlerts();

  const [stats, setStats] = useState({ totalRequests: 0, activeSessions: 0, warnings: 0, criticalAlerts: 0 });
  const [chartData, setChartData] = useState([]);
  const [requests, setRequests] = useState([]);
  const [sessions, setSessions] = useState([]);
  
  const [selectedSession, setSelectedSession] = useState(null);

  // Periodic polling for freshness
  useEffect(() => {
    const loadData = async () => {
      try {
        const [statsData, sessionsData, alertsData] = await Promise.all([
          fetchStats(),
          fetchSessions(),
          fetchAlerts()
        ]);

        if (statsData) {
          setStats(prev => ({
            ...prev,
            totalRequests: Number.isFinite(statsData.total_scored) ? statsData.total_scored : (Number.isFinite(prev.totalRequests) ? prev.totalRequests : 0),
            warnings: statsData.alerts_by_severity?.warning ?? prev.warnings ?? 0,
            criticalAlerts: statsData.alerts_by_severity?.critical ?? prev.criticalAlerts ?? 0,
            model_info: statsData.model_info || prev.model_info
          }));
        }

        if (sessionsData && Array.isArray(sessionsData)) {
          setSessions(sessionsData);
          setStats(prev => ({
            ...prev,
            activeSessions: sessionsData.length
          }));
        }

        if (alertsData && Array.isArray(alertsData) && alertsData.length > 0) {
          setAlerts(prev => {
            // Merge existing with fetched alerts without losing real-time ones
            const existingIds = new Set(prev.map(a => a.id || `${a.session_id}-${a.timestamp}`));
            const fresh = alertsData.filter(a => !existingIds.has(a.id || `${a.session_id}-${a.timestamp}`));
            return [...fresh, ...prev].slice(0, 200);
          });
        }
      } catch (err) {
        console.error('Error polling dashboard data:', err);
      }
    };

    loadData();
    const interval = setInterval(loadData, 8000);
    return () => clearInterval(interval);
  }, [setAlerts]);

  // Handle WebSocket messages
  useEffect(() => {
    if (!lastMessage) return;

    const { type, data } = lastMessage;

    if (type === 'stats_update') {
      setStats(prev => ({
        ...prev,
        totalRequests: Number.isFinite(data.total_scored) ? data.total_scored : (Number.isFinite(prev.totalRequests) ? prev.totalRequests : 0),
        activeSessions: sessions.length || prev.activeSessions || 0,
        warnings: data.alerts_by_severity?.warning ?? 0,
        criticalAlerts: data.alerts_by_severity?.critical ?? 0,
        model_info: data.model_info || prev.model_info
      }));
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
      
      // Update stats based on incoming request safely
      setStats(prev => ({
        ...prev,
        totalRequests: (Number.isFinite(prev.totalRequests) ? prev.totalRequests : 0) + 1,
      }));

      // Update sessions list in real time
      if (data.session_id) {
        setSessions(prev => {
          const sid = data.session_id;
          const idx = prev.findIndex(s => s.session_id === sid);
          if (idx >= 0) {
            const updated = [...prev];
            updated[idx] = {
              ...updated[idx],
              requests: (updated[idx].requests || 0) + 1,
              score: data.anomaly_score,
              ip: data.ip_address || updated[idx].ip
            };
            return updated;
          } else {
            return [{
              session_id: sid,
              requests: 1,
              score: data.anomaly_score,
              ip: data.ip_address || '192.168.1.1',
              status: 'CLEAN'
            }, ...prev].slice(0, 50);
          }
        });
      }
    } else if (type === 'entity_blocked') {
      if (data.session_id) {
        setSessions(prev => prev.map(s => s.session_id === data.session_id ? { ...s, status: 'BLOCKED' } : s));
      }
    } else if (type === 'alert') {
      addAlert(data);
      if (data.severity === 'critical') {
        setStats(prev => ({ ...prev, criticalAlerts: (prev.criticalAlerts || 0) + 1 }));
      } else {
        setStats(prev => ({ ...prev, warnings: (prev.warnings || 0) + 1 }));
      }
    }
  }, [lastMessage, addAlert, sessions.length]);

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
          <SystemStats stats={{ ...stats, activeSessions: sessions.length }} />
          
          <div className="flex gap-4" style={{ height: '300px' }}>
            <AnomalyScoreChart data={chartData} threshold={stats.model_info?.threshold || 0.65} />
            <RequestTimeline requests={requests} />
          </div>

          <UserSessionTable 
            sessions={sessions} 
            onSessionClick={setSelectedSession} 
            threshold={stats.model_info?.threshold || 0.65}
          />
        </section>

        {/* Right Panel - Slide In */}
        <SessionDrilldown 
          isOpen={!!selectedSession} 
          sessionId={selectedSession} 
          threshold={stats.model_info?.threshold || 0.65}
          onClose={() => setSelectedSession(null)} 
        />
      </main>
    </div>
  );
}

export default App;
