from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    message: str = Field(..., description="ユーザーからのメッセージ")
    context: dict = Field(default={}, description="追加のコンテキスト情報")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "札幌のエントリ1工程が遅延しています。対応策を提案してください。",
                "context": {
                    "location": "札幌",
                    "process": "エントリ1",
                    "delay_minutes": 20
                }
            }
        }