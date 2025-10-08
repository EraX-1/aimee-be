from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime


class AllocationChange(BaseModel):
    from_location: str = Field(..., alias="from", description="移動元拠点")
    to_location: str = Field(..., alias="to", description="移動先拠点")
    process: str = Field(..., description="工程")
    count: int = Field(..., description="人数")
    operators: Optional[List[str]] = Field(default=None, description="対象オペレータ名リスト")

    class Config:
        populate_by_name = True


class Impact(BaseModel):
    productivity: str = Field(..., description="生産性への影響")
    delay: str = Field(..., description="遅延への影響")
    quality: str = Field(..., description="品質への影響")


class Suggestion(BaseModel):
    id: str = Field(..., description="提案ID")
    changes: List[AllocationChange] = Field(..., description="配置変更内容")
    impact: Impact = Field(..., description="予測される影響")
    reason: str = Field(..., description="提案理由")
    confidence_score: float = Field(default=0.95, description="提案の確信度")


class ChatResponse(BaseModel):
    response: str = Field(..., description="AIからの応答テキスト")
    suggestion: Optional[Suggestion] = Field(None, description="配置調整提案")
    timestamp: datetime = Field(default_factory=datetime.now, description="応答日時")
    
    class Config:
        json_schema_extra = {
            "example": {
                "response": "札幌のエントリ1工程の遅延について分析しました。最適な配置調整を提案します。",
                "suggestion": {
                    "id": "SGT2024-001",
                    "changes": [
                        {
                            "from": "盛岡",
                            "to": "札幌",
                            "process": "エントリ1",
                            "count": 3
                        }
                    ],
                    "impact": {
                        "productivity": "+25%",
                        "delay": "-30分",
                        "quality": "維持"
                    },
                    "reason": "過去の類似ケースでは、この配置により95%の確率で遅延解消",
                    "confidence_score": 0.95
                },
                "timestamp": "2024-01-15T10:30:00"
            }
        }