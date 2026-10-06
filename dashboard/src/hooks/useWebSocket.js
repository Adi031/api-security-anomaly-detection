import { useState, useEffect, useRef, useCallback } from 'react';

export const useWebSocket = (url) => {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const connectionAttempts = useRef(0);
  const ws = useRef(null);
  const reconnectTimeout = useRef(null);

  const intentionallyClosed = useRef(false);

  const connect = useCallback(() => {
    try {
      intentionallyClosed.current = false;
      ws.current = new WebSocket(url);
      
      ws.current.onopen = () => {
        setIsConnected(true);
        connectionAttempts.current = 0;
      };
      
      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setLastMessage(data);
        } catch (e) {
          console.error('Failed to parse WS message', e);
        }
      };
      
      ws.current.onclose = () => {
        setIsConnected(false);
        if (!intentionallyClosed.current) {
          const timeout = Math.min(1000 * Math.pow(2, connectionAttempts.current), 30000);
          connectionAttempts.current += 1;
          reconnectTimeout.current = setTimeout(connect, timeout);
        }
      };
      
      ws.current.onerror = (err) => {
        console.error('WebSocket error:', err);
      };
    } catch (err) {
      console.error('WebSocket connection error:', err);
    }
  }, [url]);

  useEffect(() => {
    connect();
    return () => {
      intentionallyClosed.current = true;
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      if (ws.current) ws.current.close();
    };
  }, [connect]);

  const sendMessage = useCallback((msg) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(msg));
    }
  }, []);

  return { isConnected, lastMessage, sendMessage, connectionAttempts };
};
