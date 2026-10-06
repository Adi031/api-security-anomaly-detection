import { useState, useCallback } from 'react';

export const useAlerts = (initialAlerts = []) => {
  const [alerts, setAlerts] = useState(initialAlerts);

  const addAlert = useCallback((newAlert) => {
    setAlerts((prev) => {
      const updated = [newAlert, ...prev];
      return updated.slice(0, 200); // keep max 200
    });
  }, []);

  const clearAlerts = useCallback(() => {
    setAlerts([]);
  }, []);

  const getAlertsBySeverity = useCallback((severity) => {
    return alerts.filter(a => a.severity?.toLowerCase() === severity.toLowerCase());
  }, [alerts]);

  return { alerts, setAlerts, addAlert, clearAlerts, getAlertsBySeverity };
};
