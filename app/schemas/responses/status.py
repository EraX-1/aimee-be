from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime


class SystemAlert(BaseModel):
    icon: str = Field(..., description="アラートアイコン")
    message: str = Field(..., description="アラートメッセージ")
    severity: str = Field(..., description="重要度（info/warning/error/critical）")
    location: Optional[str] = Field(None, description="関連拠点")
    timestamp: datetime = Field(default_factory=datetime.now, description="発生時刻")


class SystemMetrics(BaseModel):
    availability: float = Field(..., description="稼働率（%）")
    processed_cases: int = Field(..., description="処理済み案件数")
    processed_delta: int = Field(..., description="前日比増減")
    avg_processing_time: float = Field(..., description="平均処理時間（分）")
    active_operators: int = Field(..., description="稼働中オペレータ数")


class LocationStatus(BaseModel):
    location: str = Field(..., description="拠点名")
    total_operators: int = Field(..., description="総オペレータ数")
    active_operators: int = Field(..., description="稼働中オペレータ数")
    productivity_rate: float = Field(..., description="生産性（%）")
    delay_minutes: int = Field(..., description="遅延時間（分）")
    status: str = Field(..., description="状態（normal/warning/critical）")


class SystemStatusResponse(BaseModel):
    alerts: List[SystemAlert] = Field(..., description="アラート一覧")
    metrics: SystemMetrics = Field(..., description="システムメトリクス")
    locations: List[LocationStatus] = Field(..., description="拠点別ステータス")
    last_updated: datetime = Field(default_factory=datetime.now, description="最終更新時刻")
    
    class Config:
        json_schema_extra = {
            "example": {
                "alerts": [
                    {
                        "icon": "🔴",
                        "message": "札幌エントリ1工程で遅延発生中",
                        "severity": "warning",
                        "location": "札幌",
                        "timestamp": "2024-01-15T10:30:00"
                    }
                ],
                "metrics": {
                    "availability": 98.5,
                    "processed_cases": 1234,
                    "processed_delta": 156,
                    "avg_processing_time": 4.5,
                    "active_operators": 145
                },
                "locations": [
                    {
                        "location": "札幌",
                        "total_operators": 35,
                        "active_operators": 32,
                        "productivity_rate": 85.5,
                        "delay_minutes": 20,
                        "status": "warning"
                    }
                ],
                "last_updated": "2024-01-15T10:30:00"
            }
        }