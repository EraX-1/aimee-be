from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum

from .chat import AllocationChange


class UrgencyLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ApprovalImpact(BaseModel):
    capacity: int = Field(..., description="処理能力への影響（件/時）")
    delay_risk: str = Field(..., description="遅延リスク")
    delay_change: str = Field(..., description="遅延リスクの変化")
    quality: str = Field(..., description="品質スコア")


class PendingApproval(BaseModel):
    id: str = Field(..., description="承認ID")
    timestamp: datetime = Field(..., description="作成日時")
    changes: List[AllocationChange] = Field(..., description="配置変更内容")
    impact: ApprovalImpact = Field(..., description="予測される影響")
    urgency: UrgencyLevel = Field(..., description="緊急度")
    status: ApprovalStatus = Field(default=ApprovalStatus.PENDING, description="承認ステータス")
    expires_at: datetime = Field(..., description="有効期限")
    requested_by: str = Field(default="AI", description="提案者")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "APV2024-001",
                "timestamp": "2024-01-15T10:30:00",
                "changes": [
                    {
                        "from": "札幌",
                        "to": "盛岡",
                        "process": "エントリ2",
                        "count": 3
                    }
                ],
                "impact": {
                    "capacity": 230,
                    "delay_risk": "低",
                    "delay_change": "-15%",
                    "quality": "98.5%"
                },
                "urgency": "high",
                "status": "pending",
                "expires_at": "2024-01-15T11:00:00",
                "requested_by": "AI"
            }
        }


class ApprovalListResponse(BaseModel):
    approvals: List[PendingApproval] = Field(..., description="承認待ち一覧")
    total: int = Field(..., description="総件数")
    
    
class ApprovalActionRequest(BaseModel):
    action: str = Field(..., description="承認アクション（approve/reject）")
    user: Optional[str] = Field(None, description="ユーザー名")
    user_id: Optional[str] = Field(None, description="ユーザーID")
    reason: Optional[str] = Field(None, description="理由")
    notes: Optional[str] = Field(None, description="補足コメント")
    
    
class ApprovalActionResponse(BaseModel):
    success: bool = Field(..., description="処理成功フラグ")
    message: str = Field(..., description="処理結果メッセージ")
    approval_id: str = Field(..., description="承認ID")
    action: str = Field(..., description="実行したアクション")
    timestamp: datetime = Field(default_factory=datetime.now, description="処理日時")