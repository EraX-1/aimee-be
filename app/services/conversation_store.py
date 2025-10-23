"""
会話履歴管理サービス
簡易的なメモリベースの会話履歴ストア
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta


class ConversationStore:
    """会話履歴を管理するシングルトンクラス"""

    _instance = None
    _conversations: Dict[str, List[Dict[str, Any]]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def add_message(
        self,
        session_id: str,
        message: str,
        response: str,
        suggestion: Optional[Dict[str, Any]] = None,
        intent: Optional[Dict[str, Any]] = None
    ):
        """会話履歴にメッセージを追加"""
        if session_id not in self._conversations:
            self._conversations[session_id] = []

        self._conversations[session_id].append({
            "timestamp": datetime.now(),
            "message": message,
            "response": response,
            "suggestion": suggestion,
            "intent": intent
        })

        # 古い履歴を削除（100件まで）
        if len(self._conversations[session_id]) > 100:
            self._conversations[session_id] = self._conversations[session_id][-100:]

    def get_last_suggestion(self, session_id: str) -> Optional[Dict[str, Any]]:
        """直前の配置提案を取得"""
        if session_id not in self._conversations:
            return None

        # 最新から順に遡って提案を探す
        for conv in reversed(self._conversations[session_id]):
            if conv.get("suggestion"):
                return conv["suggestion"]

        return None

    def get_recent_messages(self, session_id: str, count: int = 5) -> List[Dict[str, Any]]:
        """直近のメッセージ履歴を取得"""
        if session_id not in self._conversations:
            return []

        return self._conversations[session_id][-count:]

    def clear_session(self, session_id: str):
        """セッションの会話履歴をクリア"""
        if session_id in self._conversations:
            del self._conversations[session_id]

    def clear_old_sessions(self, hours: int = 24):
        """古いセッションをクリア"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        sessions_to_delete = []

        for session_id, messages in self._conversations.items():
            if messages and messages[-1]["timestamp"] < cutoff_time:
                sessions_to_delete.append(session_id)

        for session_id in sessions_to_delete:
            del self._conversations[session_id]


# シングルトンインスタンスを取得
conversation_store = ConversationStore()
