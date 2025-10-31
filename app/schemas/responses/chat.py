from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime


class AllocationChange(BaseModel):
    # 新構造: 4階層情報（拠点情報を含めない）
    from_business_category: str = Field(..., description="移動元 業務大分類 (SS/非SS/あはき/適用徴収)")
    from_business_name: str = Field(..., description="移動元 業務タイプ (新SS(W)等)")
    from_process_category: str = Field(..., description="移動元 OCR区分 (OCR対象等)")
    from_process_name: str = Field(..., description="移動元 工程名")
    to_business_category: str = Field(..., description="移動先 業務大分類")
    to_business_name: str = Field(..., description="移動先 業務タイプ")
    to_process_category: str = Field(..., description="移動先 OCR区分")
    to_process_name: str = Field(..., description="移動先 工程名")
    count: int = Field(..., description="人数")
    operators: Optional[List[str]] = Field(default=None, description="対象オペレータ名リスト")
    is_cross_business: Optional[bool] = Field(default=False, description="業務間移動かどうか")

    # 後方互換性のための旧フィールド（Optionalにして削除予定）
    from_location: Optional[str] = Field(None, alias="from", description="[廃止予定] 移動元拠点")
    to_location: Optional[str] = Field(None, alias="to", description="[廃止予定] 移動先拠点")
    process: Optional[str] = Field(None, description="[廃止予定] 工程")

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


class DebugInfo(BaseModel):
    """デバッグ情報"""
    intent_analysis: Optional[Dict] = Field(None, description="意図解析結果")
    database_queries: Optional[Dict] = Field(None, description="実行されたSQLクエリ情報")
    rag_results: Optional[Dict] = Field(None, description="RAG検索結果と類似度")
    processing_time: Optional[Dict] = Field(None, description="処理時間内訳")
    skill_matching: Optional[Dict] = Field(None, description="スキルマッチング詳細")


class ChatResponse(BaseModel):
    response: str = Field(..., description="AIからの応答テキスト")
    suggestion: Optional[Suggestion] = Field(None, description="配置調整提案")
    intent: Optional[Dict] = Field(None, description="意図解析結果")
    rag_results: Optional[Dict] = Field(None, description="RAG検索結果")
    metadata: Optional[Dict] = Field(None, description="メタデータ")
    timestamp: datetime = Field(default_factory=datetime.now, description="応答日時")
    debug_info: Optional[DebugInfo] = Field(None, description="デバッグ情報（debug=trueの場合のみ）")

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