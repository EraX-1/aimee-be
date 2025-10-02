"""
統合LLMサービス
意図解析、データベース照会、レスポンス生成を統合
"""
import json
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.core.logging import app_logger
from app.services.ollama_service import OllamaService
from app.services.database_service import DatabaseService


class IntegratedLLMService:
    """LLM処理を統合したサービス"""
    
    def __init__(self):
        self.ollama_service = OllamaService()
        self.db_service = DatabaseService()
    
    async def process_message(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        db: Optional[AsyncSession] = None,
        detail: bool = False
    ) -> Dict[str, Any]:
        """
        メッセージを処理して適切な応答を生成
        
        Args:
            message: ユーザーからのメッセージ
            context: 追加コンテキスト情報
            db: データベースセッション
            detail: デバッグ情報を含めるかどうか
            
        Returns:
            処理結果（応答、提案、メタデータ、デバッグ情報を含む）
        """
        app_logger.info(f"Processing message: {message}")
        debug_info = {} if detail else None
        
        # ステップ1: 意図解析
        intent = await self.ollama_service.analyze_intent(message)
        app_logger.info(f"Intent analysis result: {intent}")
        
        if detail:
            debug_info["step1_intent_analysis"] = {
                "raw_intent": intent,
                "extracted_location": intent.get("entities", {}).get("location"),
                "extracted_process": intent.get("entities", {}).get("process"),
                "confidence_indicators": {
                    "has_location": bool(intent.get("entities", {}).get("location")),
                    "has_process": bool(intent.get("entities", {}).get("process")),
                    "requires_action": intent.get("requires_action", False)
                }
            }
        
        # ステップ2: データベース照会（dbが提供されている場合）
        db_data = {}
        executed_queries = []
        
        if db and intent.get("intent_type") != "error":
            try:
                if detail:
                    # クエリ実行を監視
                    original_execute = db.execute
                    
                    async def monitored_execute(query, params=None):
                        query_str = str(query)
                        executed_queries.append({
                            "sql": query_str,
                            "params": params,
                            "intent_type": intent.get("intent_type")
                        })
                        return await original_execute(query, params)
                    
                    db.execute = monitored_execute
                
                db_data = await self.db_service.fetch_data_by_intent(
                    intent, 
                    context or {}, 
                    db
                )
                app_logger.info(f"Database query returned {len(db_data)} data categories")
                
                if detail:
                    debug_info["step2_database_queries"] = {
                        "executed_queries": executed_queries,
                        "data_summary": {
                            category: len(data) if isinstance(data, list) else str(type(data).__name__)
                            for category, data in db_data.items()
                        },
                        "total_records": sum(
                            len(data) if isinstance(data, list) else 0
                            for data in db_data.values()
                        )
                    }
                    
            except Exception as e:
                app_logger.error(f"Database query error: {str(e)}")
                db_data = {"error": str(e)}
                if detail:
                    debug_info["step2_database_queries"] = {
                        "error": str(e),
                        "executed_queries": executed_queries
                    }
        
        # ステップ3: 提案生成（必要な場合）
        suggestion = None
        if intent.get("requires_action") and db_data:
            suggestion = await self._generate_suggestion(intent, db_data, context)
            if detail and suggestion:
                debug_info["step3_suggestion_generation"] = {
                    "suggestion_id": suggestion.get("id"),
                    "changes_count": len(suggestion.get("changes", [])),
                    "confidence_score": suggestion.get("confidence_score"),
                    "reasoning": suggestion.get("reason")
                }
        
        # ステップ4: 最終レスポンス生成
        response_context = self._prepare_response_context(intent, db_data, context)
        response_text = await self.ollama_service.generate_response(
            message, 
            intent,
            response_context,
            db_data,
            suggestion
        )
        
        # 回答タイプの分類
        response_type = self._classify_response_type(response_text)
        
        if detail:
            debug_info["step4_response_generation"] = {
                "response_context": response_context,
                "response_length": len(response_text),
                "response_type": response_type,
                "contains_action_request": "選択してください" in response_text,
                "contains_suggestions": any(word in response_text for word in ["提案します", "推奨", "対策"]),
                "is_info_request": "入力してください" in response_text
            }
        
        # 結果をまとめる
        result = {
            "response": response_text,
            "intent": intent,
            "suggestion": suggestion,
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "data_sources": list(db_data.keys()),
                "has_db_data": bool(db_data and not db_data.get("error")),
                "response_type": response_type
            }
        }
        
        if detail:
            result["debug_info"] = debug_info
        
        return result
    
    async def _generate_suggestion(
        self,
        intent: Dict[str, Any],
        db_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        データベースの情報を基に具体的な提案を生成
        """
        intent_type = intent.get("intent_type")
        
        if intent_type == "delay_resolution":
            return await self._generate_delay_resolution_suggestion(intent, db_data, context)
        elif intent_type == "resource_allocation":
            return await self._generate_resource_allocation_suggestion(intent, db_data, context)
        
        return None
    
    async def _generate_delay_resolution_suggestion(
        self,
        intent: Dict[str, Any],
        db_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """遅延解決の提案を生成"""
        
        # 現在の不足状況を確認
        target_process = db_data.get("target_process", [])
        if not target_process:
            target_process = db_data.get("current_assignments", [])
        
        # 余剰リソースを確認
        available_resources = db_data.get("available_resources", [])
        
        # 提案を構築
        changes = []
        total_shortage = 0
        
        for assignment in target_process:
            shortage = assignment.get("shortage", 0)
            if shortage > 0:
                total_shortage += shortage
                location_name = assignment.get("location_name")
                process_name = assignment.get("process_name")
                
                # 余剰リソースから配分
                allocated = 0
                for resource in available_resources:
                    if allocated >= shortage:
                        break
                    
                    surplus = resource.get("surplus", 0)
                    if surplus > 0 and resource.get("process_name") == process_name:
                        transfer_count = min(surplus, shortage - allocated)
                        changes.append({
                            "from": resource.get("location_name"),
                            "to": location_name,
                            "process": process_name,
                            "count": transfer_count
                        })
                        allocated += transfer_count
                        resource["surplus"] -= transfer_count  # 次の割り当てのために更新
        
        # 生産性データから影響を推定
        productivity_trends = db_data.get("productivity_trends", [])
        avg_productivity = 85.0  # デフォルト値
        if productivity_trends:
            recent_productivity = [p.get("avg_productivity", 85) for p in productivity_trends[:3]]
            avg_productivity = sum(recent_productivity) / len(recent_productivity)
        
        # 提案をまとめる
        suggestion = {
            "id": f"SGT{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "changes": changes,
            "impact": {
                "productivity": f"+{min(15, total_shortage * 3)}%",
                "delay": f"-{min(30, total_shortage * 10)}分",
                "quality": "維持" if total_shortage < 5 else "+2%"
            },
            "reason": self._generate_suggestion_reason(changes, avg_productivity),
            "confidence_score": min(0.95, 0.7 + len(changes) * 0.05)
        }
        
        return suggestion
    
    async def _generate_resource_allocation_suggestion(
        self,
        intent: Dict[str, Any],
        db_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """リソース配分の提案を生成"""
        # 実装は遅延解決と同様のロジックを使用
        return await self._generate_delay_resolution_suggestion(intent, db_data, context)
    
    def _prepare_response_context(
        self,
        intent: Dict[str, Any],
        db_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        レスポンス生成用のコンテキストを準備
        """
        response_context = context or {}
        
        # データベース情報のサマリーを追加
        if db_data.get("current_assignments"):
            assignments = db_data["current_assignments"]
            response_context["total_locations"] = len(set(a["location_name"] for a in assignments))
            response_context["shortage_count"] = sum(1 for a in assignments if a.get("shortage", 0) > 0)
            response_context["total_shortage"] = sum(a.get("shortage", 0) for a in assignments)
        
        if db_data.get("productivity_trends"):
            trends = db_data["productivity_trends"]
            recent_avg = sum(t.get("avg_productivity", 0) for t in trends[:5]) / min(5, len(trends))
            response_context["recent_productivity"] = f"{recent_avg:.1f}%"
        
        if db_data.get("available_resources"):
            resources = db_data["available_resources"]
            response_context["available_locations"] = len(resources)
            response_context["total_surplus"] = sum(r.get("surplus", 0) for r in resources)
        
        return response_context
    
    def _generate_suggestion_reason(
        self,
        changes: List[Dict[str, Any]],
        avg_productivity: float
    ) -> str:
        """提案理由を生成"""
        if not changes:
            return "現在のリソースで対応可能です"
        
        total_transfers = sum(c["count"] for c in changes)
        locations_involved = len(set(c["from"] for c in changes))
        
        reasons = []
        if avg_productivity < 80:
            reasons.append("生産性向上が必要")
        if total_transfers > 5:
            reasons.append("大幅な人員不足を解消")
        if locations_involved > 2:
            reasons.append("複数拠点からの協力体制を構築")
        
        if reasons:
            return "、".join(reasons) + f"（{total_transfers}名の配置調整）"
        else:
            return f"{total_transfers}名の配置調整により最適化を実現"
    
    def _classify_response_type(self, response_text: str) -> str:
        """回答タイプを分類"""
        if "入力してください" in response_text or "詳細情報をいただければ" in response_text:
            return "info_request"  # 追加情報要求
        elif "選択してください" in response_text and any(option in response_text for option in ["承認", "否認", "調整"]):
            return "action_choice"  # アクション選択促進
        elif any(word in response_text for word in ["提案します", "推奨", "対策"]):
            return "suggestion"  # 提案・推奨
        elif any(word in response_text for word in ["確認", "状況", "現在"]):
            return "status_report"  # 状況報告
        else:
            return "general"  # 一般回答