from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional
from enum import Enum


class AlertType(str, Enum):
    ATTENDANCE = "attendance"
    PRODUCTIVITY = "productivity"
    SKILL_GAP = "skill_gap"
    WORKLOAD = "workload"
    SYSTEM = "system"


class AlertPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class Alert(BaseModel):
    id: int = Field(..., description="アラートID")
    type: AlertType = Field(..., description="アラート種別")
    priority: AlertPriority = Field(..., description="優先度")
    status: AlertStatus = Field(..., description="ステータス")
    title: str = Field(..., description="アラートタイトル")
    message: str = Field(..., description="アラート詳細メッセージ")
    location_id: Optional[int] = Field(None, description="拠点ID")
    location_name: Optional[str] = Field(None, description="拠点名")
    employee_id: Optional[int] = Field(None, description="従業員ID")
    employee_name: Optional[str] = Field(None, description="従業員名")
    created_at: datetime = Field(..., description="作成日時")
    updated_at: datetime = Field(..., description="更新日時")
    acknowledged_at: Optional[datetime] = Field(None, description="確認日時")
    resolved_at: Optional[datetime] = Field(None, description="解決日時")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "type": "attendance",
                "priority": "high",
                "status": "new",
                "title": "欠勤による人員不足",
                "message": "横浜拠点でデータ入力工程の人員が3名不足しています。",
                "location_id": 3,
                "location_name": "横浜",
                "employee_id": None,
                "employee_name": None,
                "created_at": "2025-09-16T08:30:00",
                "updated_at": "2025-09-16T08:30:00",
                "acknowledged_at": None,
                "resolved_at": None,
            }
        }


class AlertListResponse(BaseModel):
    alerts: List[Alert] = Field(..., description="アラート一覧")
    total: int = Field(..., description="総件数")
    page: int = Field(1, description="現在のページ番号")
    page_size: int = Field(20, description="1ページあたりの件数")
    
    class Config:
        json_schema_extra = {
            "example": {
                "alerts": [
                    {
                        "id": 1,
                        "type": "attendance",
                        "priority": "high",
                        "status": "new",
                        "title": "欠勤による人員不足",
                        "message": "横浜拠点でデータ入力工程の人員が3名不足しています。",
                        "location_id": 3,
                        "location_name": "横浜",
                        "employee_id": None,
                        "employee_name": None,
                        "created_at": "2025-09-16T08:30:00",
                        "updated_at": "2025-09-16T08:30:00",
                        "acknowledged_at": None,
                        "resolved_at": None,
                    }
                ],
                "total": 15,
                "page": 1,
                "page_size": 20,
            }
        }


class AlertDetailResponse(BaseModel):
    alert: Alert = Field(..., description="アラート詳細")
    recommended_actions: List[str] = Field(..., description="推奨アクション")
    related_alerts: List[int] = Field(..., description="関連アラートID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "alert": {
                    "id": 1,
                    "type": "attendance",
                    "priority": "high",
                    "status": "new",
                    "title": "欠勤による人員不足",
                    "message": "横浜拠点でデータ入力工程の人員が3名不足しています。",
                    "location_id": 3,
                    "location_name": "横浜",
                    "employee_id": None,
                    "employee_name": None,
                    "created_at": "2025-09-16T08:30:00",
                    "updated_at": "2025-09-16T08:30:00",
                    "acknowledged_at": None,
                    "resolved_at": None,
                },
                "recommended_actions": [
                    "他拠点から応援人員を配置",
                    "在宅勤務可能な従業員を緊急配置",
                    "優先度の低い工程から人員を一時的に移動",
                ],
                "related_alerts": [2, 5, 8],
            }
        }