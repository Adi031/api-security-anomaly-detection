from datetime import datetime
from db import db
from scorer import scorer

class AlertManager:
    async def create_alert_if_needed(self, session_id: str, logs: list, score: float, severity: str, feature_contributions: dict = None):
        if severity == "normal":
            return None
            
        last_log = logs[-1]
        
        if feature_contributions is None:
            feature_contributions = {"reconstruction_error": score}
        
        alert = {
            "timestamp": datetime.utcnow(),
            "session_id": session_id,
            "user_id": last_log.get('user_id'),
            "ip_address": last_log.get('ip_address', '0.0.0.0'),
            "anomaly_score": score,
            "severity": severity,
            "model_type": scorer.model_type,
            "description": f"High anomaly score ({score:.4f}) detected for session {session_id}",
            "feature_contributions": feature_contributions,
            "window_start": logs[0]['timestamp'],
            "window_end": logs[-1]['timestamp'],
            "resolved": False
        }
        
        alert_id = await db.insert_alert(alert)
        alert["id"] = alert_id
        return alert

alert_manager = AlertManager()
