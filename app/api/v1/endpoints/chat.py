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
    統合LLMサービスを使用して実際のAI処理を行います。
    """
    app_logger.info(f"Received chat message: {request.message} (session: {request.session_id})")

    from app.services.integrated_llm_service import IntegratedLLMService
    from app.services.conversation_store import conversation_store
    from app.db.session import get_db

    try:
        # 会話履歴から直前の提案を取得
        last_suggestion = conversation_store.get_last_suggestion(request.session_id)

        # 統合LLMサービスでAI処理
        llm_service = IntegratedLLMService()

        # 非同期DB接続を取得
        async for db in get_db():
            result = await llm_service.process_message(
                message=request.message,
                context={**request.context, "last_suggestion": last_suggestion} if last_suggestion else request.context,
                db=db,
                detail=False
            )

            # 応答を整形
            response_text = result.get("response", "応答を生成できませんでした")
            suggestion_data = result.get("suggestion")

            # 提案があれば変換
            suggestion = None
            if suggestion_data:
                suggestion = Suggestion(
                    id=suggestion_data.get("id", f"SGT{datetime.now().year}-{str(uuid.uuid4())[:8].upper()}"),
                    changes=[AllocationChange(**c) for c in suggestion_data.get("changes", [])],
                    impact=Impact(**suggestion_data.get("impact", {})),
                    reason=suggestion_data.get("reason", ""),
                    confidence_score=suggestion_data.get("confidence_score", 0.85)
                )

                # 承認待ちリストに追加 (approvalsエンドポイントで使用)
                from app.api.v1.endpoints.approvals import pending_approvals_db
                from app.schemas.responses.approvals import PendingApproval, ApprovalImpact, UrgencyLevel, ApprovalStatus
                from datetime import timedelta

                # PendingApprovalオブジェクトとして作成
                pending_approval = PendingApproval(
                    id=suggestion.id,
                    changes=[AllocationChange(**c) for c in suggestion_data.get("changes", [])],
                    impact=ApprovalImpact(
                        capacity=100,  # デフォルト値
                        delay_risk="低",
                        delay_change=suggestion_data.get("impact", {}).get("delay", "-15分"),
                        quality=suggestion_data.get("impact", {}).get("quality", "維持")
                    ),
                    reason=suggestion_data.get("reason", ""),
                    confidence_score=suggestion_data.get("confidence_score", 0.85),
                    urgency=UrgencyLevel.HIGH,
                    status=ApprovalStatus.PENDING,
                    timestamp=datetime.now(),
                    expires_at=datetime.now() + timedelta(hours=24),
                    requested_by="AI Assistant"
                )

                pending_approvals_db[suggestion.id] = pending_approval
                app_logger.info(f"Added to pending approvals: {suggestion.id}")

            # 会話履歴に保存
            conversation_store.add_message(
                session_id=request.session_id,
                message=request.message,
                response=response_text,
                suggestion=suggestion_data,
                intent=result.get("intent")
            )
            app_logger.info(f"Added to conversation history (session: {request.session_id})")

            # 完全なレスポンスを返す (detail情報含む)
            return {
                "response": response_text,
                "suggestion": suggestion.dict() if suggestion else None,
                "intent": result.get("intent"),
                "rag_results": result.get("rag_results"),
                "metadata": result.get("metadata"),
                "timestamp": datetime.now().isoformat()
            }

    except Exception as e:
        app_logger.error(f"Chat message processing error: {e}")

        # エラー時はシンプルな応答を返す
        response_text = f"""
了解しました。「{request.message}」について分析します。

⚠️ 現在、AI処理システムが初期化中です。
簡易モードで応答しています。

📊 **メッセージ受信**: 確認しました
🔄 **システム状態**: 起動処理中

しばらくお待ちください。
"""

        return ChatResponse(
            response=response_text,
            suggestion=None,
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