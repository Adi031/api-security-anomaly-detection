export const formatTimestamp = (ts) => {
  if (!ts) return '';
  const date = new Date(ts);
  return date.toLocaleTimeString('en-US', { hour12: false });
};

export const formatScore = (score) => {
  return Number(score).toFixed(2);
};

export const formatDuration = (seconds) => {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}m ${s}s`;
};

export const getSeverityColor = (severity) => {
  switch (severity?.toLowerCase()) {
    case 'critical': return 'var(--color-danger)';
    case 'warning': return 'var(--color-warning)';
    default: return 'var(--color-success)';
  }
};

export const truncateId = (id) => {
  if (!id) return '';
  return id.substring(0, 8);
};
