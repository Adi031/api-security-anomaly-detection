from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

class ScoredRequest(BaseModel):
    id: int
    timestamp: datetime
    user_id: Optional[str]
    session_id: str
    ip_address: str
    endpoint: str
    anomaly_score: float
    is_anomaly: bool

class Alert(BaseModel):
    id: Optional[int]
    timestamp: datetime
    session_id: str
    user_id: Optional[str]
    ip_address: str
    anomaly_score: float
    severity: str
    model_type: str
    description: str
    feature_contributions: Dict[str, float]
    window_start: datetime
    window_end: datetime
    resolved: bool = False

class SessionSummary(BaseModel):
    session_id: str
    request_count: int
    max_anomaly_score: float
    status: str

class SystemStats(BaseModel):
    total_scored: int
    alerts_by_severity: Dict[str, int]
    model_info: Dict[str, Any]
    uptime: float

class WebSocketMessage(BaseModel):
    type: str
    data: Any
