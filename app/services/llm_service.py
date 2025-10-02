"""
統合LLMサービス
意図解析、データベース照会、レスポンス生成を統合
"""
import json
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import app_logger
from app.services.ollama_service import OllamaService
from app.services.database_service import DatabaseService

class LLMService:
    def __init__(self):
        self.light_llm_url = f"http://{settings.OLLAMA_LIGHT_HOST}:{settings.OLLAMA_LIGHT_PORT}"
        self.main_llm_url = f"http://{settings.OLLAMA_MAIN_HOST}:{settings.OLLAMA_MAIN_PORT}"
        
    async def process_chat_message(
        self, 
        message: str, 
        context: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        実際のLLM処理フロー
        """
        
        # ステップ1: 軽量LLMで意図解析（0.2秒）
        intent = await self._analyze_intent(message)
        app_logger.info(f"Intent analysis: {intent}")
        
        # ステップ2: データベースから関連データ取得（0.5秒）
        db_data = await self._fetch_relevant_data(intent, context, db)
        app_logger.info(f"Fetched DB data: {len(db_data)} records")
        
        # ステップ3: メインLLMで詳細分析と提案生成（1-2秒）
        response = await self._generate_response(message, context, intent, db_data)
        
        return response
    
    async def _analyze_intent(self, message: str) -> Dict[str, Any]:
        """
        軽量LLM（qwen2:0.5b）で意図解析
        """
        prompt = f"""
        以下のメッセージから意図を分析してJSON形式で返してください。
        
        メッセージ: {message}
        
        返すJSON形式:
        {{
            "intent_type": "delay_resolution|resource_allocation|status_check|other",
            "urgency": "high|medium|low",
            "requires_suggestion": true|false,
            "entities": {{
                "location": "抽出した拠点名",
                "process": "抽出した工程名",
                "issue": "問題の種類"
            }}
        }}
        """
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.light_llm_url}/api/generate",
                json={
                    "model": settings.INTENT_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 200
                    }
                }
            )
            
        result = response.json()
        return json.loads(result.get("response", "{}"))
    
    async def _fetch_relevant_data(
        self, 
        intent: Dict[str, Any],
        context: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        データベースから関連データを取得
        """
        location = context.get("location") or intent.get("entities", {}).get("location")
        
        if not location:
            return {}
        
        # 現在の配置状況を取得
        current_allocation = await db.execute(
            text("""
                SELECT 
                    da.location_id,
                    l.location_name,
                    da.process_id,
                    pd.process_name,
                    da.allocated_count,
                    da.required_count
                FROM daily_assignments da
                JOIN locations l ON da.location_id = l.location_id
                JOIN process_definitions pd ON da.process_id = pd.process_id
                WHERE l.location_name = :location
                AND da.assignment_date = CURDATE()
            """),
            {"location": location}
        )
        
        # 生産性データを取得
        productivity_data = await db.execute(
            text("""
                SELECT 
                    AVG(pr.productivity_score) as avg_productivity,
                    COUNT(DISTINCT pr.employee_id) as employee_count
                FROM productivity_records pr
                JOIN employees e ON pr.employee_id = e.employee_id
                JOIN locations l ON e.location_id = l.location_id
                WHERE l.location_name = :location
                AND pr.record_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            """),
            {"location": location}
        )
        
        # 他拠点の余剰人員を取得
        available_resources = await db.execute(
            text("""
                SELECT 
                    l.location_name,
                    pd.process_name,
                    (da.allocated_count - da.required_count) as surplus_count
                FROM daily_assignments da
                JOIN locations l ON da.location_id = l.location_id
                JOIN process_definitions pd ON da.process_id = pd.process_id
                WHERE da.assignment_date = CURDATE()
                AND da.allocated_count > da.required_count
                ORDER BY surplus_count DESC
                LIMIT 5
            """)
        )
        
        return {
            "current_allocation": current_allocation.fetchall(),
            "productivity": productivity_data.fetchone(),
            "available_resources": available_resources.fetchall()
        }
    
    async def _generate_response(
        self,
        message: str,
        context: Dict[str, Any],
        intent: Dict[str, Any],
        db_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        メインLLM（gemma:7b）で詳細分析と提案生成
        """
        # データベースの情報を整形
        data_summary = self._format_db_data(db_data)
        
        prompt = f"""
        あなたは労働力配置の最適化を行うAIアシスタントです。
        以下の情報を元に、具体的で実行可能な配置調整案を提案してください。
        
        ユーザーのメッセージ: {message}
        
        現在の状況:
        {data_summary}
        
        以下の形式でJSON形式の提案を生成してください：
        {{
            "response_text": "状況分析と提案の説明文",
            "suggestion": {{
                "changes": [
                    {{"from": "移動元拠点", "to": "移動先拠点", "process": "工程名", "count": 人数}}
                ],
                "impact": {{
                    "productivity": "生産性の変化予測（例: +15%）",
                    "delay": "遅延解消時間（例: -30分）",
                    "quality": "品質への影響（例: 維持）"
                }},
                "reason": "この提案の根拠",
                "confidence_score": 0.0-1.0の信頼度スコア
            }}
        }}
        """
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.main_llm_url}/api/generate",
                json={
                    "model": settings.MAIN_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 1000
                    }
                },
                timeout=30.0
            )
            
        result = response.json()
        llm_response = json.loads(result.get("response", "{}"))
        
        return {
            "response": llm_response.get("response_text", "分析を実行しました。"),
            "suggestion": llm_response.get("suggestion"),
            "metadata": {
                "intent": intent,
                "data_points_used": len(db_data.get("current_allocation", [])),
                "models_used": [settings.INTENT_MODEL, settings.MAIN_MODEL]
            }
        }
    
    def _format_db_data(self, db_data: Dict[str, Any]) -> str:
        """
        データベースデータを読みやすい形式に整形
        """
        summary = []
        
        # 現在の配置状況
        if db_data.get("current_allocation"):
            summary.append("【現在の配置】")
            for row in db_data["current_allocation"]:
                summary.append(f"- {row.location_name} {row.process_name}: {row.allocated_count}名（必要: {row.required_count}名）")
        
        # 生産性
        if db_data.get("productivity"):
            prod = db_data["productivity"]
            summary.append(f"\n【生産性】平均: {prod.avg_productivity:.1f}% ({prod.employee_count}名)")
        
        # 利用可能なリソース
        if db_data.get("available_resources"):
            summary.append("\n【他拠点の余剰人員】")
            for row in db_data["available_resources"]:
                if row.surplus_count > 0:
                    summary.append(f"- {row.location_name} {row.process_name}: +{row.surplus_count}名")
        
        return "\n".join(summary)