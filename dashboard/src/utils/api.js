const BASE_URL = 'http://127.0.0.1:8001/api';

export const fetchStats = async () => {
  try {
    const res = await fetch(`${BASE_URL}/stats`);
    if (!res.ok) throw new Error('Network response was not ok');
    return await res.json();
  } catch (err) {
    console.error('Failed to fetch stats:', err);
    return null;
  }
};

export const fetchAlerts = async (page = 1, severity = '') => {
  try {
    const res = await fetch(`${BASE_URL}/alerts?page=${page}&per_page=20${severity ? `&severity=${severity}` : ''}`);
    if (!res.ok) throw new Error('Network response was not ok');
    return await res.json();
  } catch (err) {
    console.error('Failed to fetch alerts:', err);
    return [];
  }
};

export const fetchSessions = async () => {
  try {
    const res = await fetch(`${BASE_URL}/sessions`);
    if (!res.ok) throw new Error('Network response was not ok');
    return await res.json();
  } catch (err) {
    console.error('Failed to fetch sessions:', err);
    return [];
  }
};

export const fetchSessionDetail = async (id) => {
  try {
    const res = await fetch(`${BASE_URL}/sessions/${id}`);
    if (!res.ok) throw new Error('Network response was not ok');
    return await res.json();
  } catch (err) {
    console.error(`Failed to fetch session ${id}:`, err);
    return null;
  }
};
