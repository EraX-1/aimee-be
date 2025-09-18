from fastapi import APIRouter, HTTPException
from datetime import datetime
import random
import uuid

from app.schemas.requests.chat import ChatMessageRequest
from app.schemas.responses.chat import ChatResponse, Suggestion, AllocationChange, Impact
from app.core.logging import app_logger

router = APIRouter()


def generate_suggestion(message: str, context: dict) -> Suggestion:
    """メッセージに基づいて配置提案を生成（モック）"""
    
    # デモ用の提案パターン
    suggestions = [
        {
            "changes": [
                {"from": "盛岡", "to": "札幌", "process": "エントリ1", "count": 3},
                {"from": "品川", "to": "札幌", "process": "エントリ1", "count": 2},
                {"from": "西梅田", "to": "札幌", "process": "エントリ1", "count": 1}
            ],
            "impact": {
                "productivity": "+25%",
                "delay": "-30分",
                "quality": "維持"
            },
            "reason": "過去の類似ケースでは、この配置により95%の確率で遅延解消"
        },
        {
            "changes": [
                {"from": "沖縄", "to": "盛岡", "process": "補正", "count": 2},
                {"from": "佐世保", "to": "盛岡", "process": "補正", "count": 1}
            ],
            "impact": {
                "productivity": "+15%",
                "delay": "-20分",
                "quality": "+2%"
            },
            "reason": "補正工程の経験者を集中配置することで品質向上が期待できます"
        },
        {
            "changes": [
                {"from": "本町東", "to": "品川", "process": "エントリ2", "count": 4},
                {"from": "和歌山", "to": "品川", "process": "エントリ2", "count": 2}
            ],
            "impact": {
                "productivity": "+30%",
                "delay": "-40分",
                "quality": "維持"
            },
            "reason": "品川拠点の処理能力を最大化し、全体の効率を向上させます"
        }
    ]
    
    # ランダムに提案を選択（実際はAI/MLモデルで生成）
    selected = random.choice(suggestions)
    
    return Suggestion(
        id=f"SGT{datetime.now().year}-{str(uuid.uuid4())[:8].upper()}",
        changes=[AllocationChange(**change) for change in selected["changes"]],
        impact=Impact(**selected["impact"]),
        reason=selected["reason"],
        confidence_score=random.uniform(0.85, 0.98)
    )


@router.post("/message", response_model=ChatResponse, summary="チャットメッセージ送信")
async def send_chat_message(request: ChatMessageRequest):
    """
    ユーザーからのメッセージを受け取り、AI配置調整の提案を返します。
    """
    app_logger.info(f"Received chat message: {request.message}")
    
    # メッセージ分析（実際はNLP処理）
    keywords = ["遅延", "不足", "配置", "調整", "対応", "提案"]
    needs_suggestion = any(keyword in request.message for keyword in keywords)
    
    # 応答生成
    response_text = f"""
了解しました。「{request.message}」について分析します。

📊 **現在の状況分析：**
"""
    
    # コンテキストから状況を抽出
    if request.context.get("location"):
        response_text += f"- 拠点: {request.context['location']}\n"
    if request.context.get("process"):
        response_text += f"- 工程: {request.context['process']}\n"
    if request.context.get("delay_minutes"):
        response_text += f"- 遅延: {request.context['delay_minutes']}分\n"
    
    # ダミーデータで状況を補完
    response_text += f"""- 現在配置: 12名
- 処理残: 450件
- 必要処理能力: 550件/時

🎯 **最適化提案：**
以下の配置調整を提案します：
"""
    
    # 提案生成
    suggestion = None
    if needs_suggestion:
        suggestion = generate_suggestion(request.message, request.context)
    
    return ChatResponse(
        response=response_text,
        suggestion=suggestion,
        timestamp=datetime.now()
    )


@router.get("/history", summary="チャット履歴取得")
async def get_chat_history(
    limit: int = 10,
    offset: int = 0
):
    """
    チャット履歴を取得します。
    """
    # 実際の実装ではデータベースから取得
    app_logger.info(f"Getting chat history: limit={limit}, offset={offset}")
    
    history = [
        {
            "role": "user",
            "content": "札幌のエントリ1工程が遅延しています",
            "timestamp": "2024-01-15T10:25:00"
        },
        {
            "role": "assistant",
            "content": "承知しました。札幌のエントリ1工程の遅延について分析し、最適な配置を提案します。",
            "timestamp": "2024-01-15T10:25:30"
        }
    ]
    
    return {
        "history": history,
        "total": len(history),
        "limit": limit,
        "offset": offset
    }