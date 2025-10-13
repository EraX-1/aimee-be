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
from app.services.chroma_service import ChromaService


class IntegratedLLMService:
    """LLM処理を統合したサービス"""

    def __init__(self):
        self.ollama_service = OllamaService()
        self.db_service = DatabaseService()
        # ChromaServiceは遅延初期化（最初の使用時に初期化）
        self._chroma_service = None
        self._chroma_initialized = False
    
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
        
        # ステップ2: RAG検索（関連情報の取得）
        rag_results = {}
        try:
            # ChromaServiceを遅延初期化
            if not self._chroma_initialized:
                try:
                    self._chroma_service = ChromaService()
                    self._chroma_initialized = True
                    app_logger.info("ChromaDB初期化成功")
                except Exception as e:
                    app_logger.warning(f"ChromaDB初期化失敗: {e}")
                    self._chroma_service = None
                    self._chroma_initialized = True  # 再試行しない

            if self._chroma_service:
                entities = intent.get("entities", {})
                business_id = entities.get("business_id", "523201")
                process_id = entities.get("process_id")
                location_id = entities.get("location")

                # セマンティック検索でコンテキスト情報を取得
                query_text = message
                similar_docs = self._chroma_service.query_similar(
                    query_text=query_text,
                    n_results=3
                )
                rag_results["similar_context"] = similar_docs
                app_logger.info(f"RAG検索完了: {len(similar_docs.get('documents', []))}件")

                if detail:
                    debug_info["step2_rag_search"] = {
                        "query_text": query_text,
                        "similar_docs_count": len(similar_docs.get("documents", []))
                    }
            else:
                app_logger.info("ChromaDB未初期化のためRAG検索スキップ")

        except Exception as e:
            app_logger.error(f"RAG search error: {str(e)}")
            if detail:
                debug_info["step2_rag_search"] = {"error": str(e)}

        # ステップ3: データベース照会（dbが提供されている場合）
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
                    debug_info["step3_database_queries"] = {
                        "error": str(e),
                        "executed_queries": executed_queries
                    }

        # ステップ4: 提案生成（必要な場合）
        suggestion = None
        if intent.get("requires_action") and (db_data or rag_results):
            suggestion = await self._generate_suggestion(intent, db_data, context, rag_results)
            if detail and suggestion:
                debug_info["step4_suggestion_generation"] = {
                    "suggestion_id": suggestion.get("id"),
                    "changes_count": len(suggestion.get("changes", [])),
                    "confidence_score": suggestion.get("confidence_score"),
                    "reasoning": suggestion.get("reason")
                }

        # ステップ5: 最終レスポンス生成（RAG結果も含める）
        response_context = self._prepare_response_context(intent, db_data, context, rag_results)
        response_text = await self.ollama_service.generate_response(
            message,
            intent,
            response_context,
            db_data,
            suggestion,
            rag_results  # RAG検索結果を追加
        )
        
        # 回答タイプの分類
        response_type = self._classify_response_type(response_text)
        
        if detail:
            debug_info["step5_response_generation"] = {
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
            "rag_results": {
                "recommended_operators": rag_results.get("recommended_operators", []),
                "context_relevance": len(rag_results.get("similar_context", {}).get("documents", []))
            },
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "data_sources": list(db_data.keys()) + ["rag_search"],
                "has_db_data": bool(db_data and not db_data.get("error")),
                "has_rag_data": bool(rag_results),
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
        context: Optional[Dict[str, Any]] = None,
        rag_results: Optional[Dict[str, Any]] = None
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
        """遅延解決の提案を生成 (実データベース)"""

        # 余剰リソースと不足リソースを取得
        available_resources = db_data.get("available_resources", [])
        shortage_list = db_data.get("shortage_list", [])
        operators_by_location_process = db_data.get("operators_by_location_process", {})

        app_logger.info(f"提案生成開始: 余剰{len(available_resources)}件, 不足{len(shortage_list)}件, オペレータ{len(operators_by_location_process)}グループ")

        # デバッグ: 実際のデータを確認
        app_logger.info(f"余剰詳細: {[(r.get('location_name'), r.get('process_name'), r.get('surplus')) for r in available_resources[:5]]}")
        app_logger.info(f"不足詳細: {[(s.get('location_name'), s.get('process_name'), s.get('shortage')) for s in shortage_list[:5]]}")

        # ユーザーが指定した拠点のみに絞り込む
        user_specified_location = intent.get("entities", {}).get("location")
        app_logger.info(f"【デバッグ】user_specified_location = '{user_specified_location}' (type: {type(user_specified_location)})")
        app_logger.info(f"【デバッグ】フィルタリング前の不足リスト件数: {len(shortage_list)}")

        if user_specified_location and user_specified_location != "不明":
            original_count = len(shortage_list)
            shortage_list = [s for s in shortage_list if s.get("location_name") == user_specified_location]
            app_logger.info(f"ユーザー指定拠点でフィルタリング: {user_specified_location} → {original_count}件から{len(shortage_list)}件に絞り込み")
        else:
            app_logger.info(f"【デバッグ】フィルタリングスキップ (location={user_specified_location})")

        # 配置提案を構築
        changes = []

        # 不足している拠点・工程に対して、余剰がある拠点から配置
        for i, shortage in enumerate(shortage_list[:5]):  # 最大5件の不足に対応
            shortage_loc = shortage.get("location_name")
            shortage_process = shortage.get("process_name")
            needed = shortage.get("shortage", 0)

            app_logger.info(f"不足{i+1}: {shortage_loc}の{shortage_process} (不足{needed}名)")

            # 同じ工程で余剰がある拠点を探す
            matched_count = 0
            for j, resource in enumerate(available_resources):
                if len(changes) >= 3:  # 最大3件の変更
                    break

                resource_process = resource.get("process_name", "")
                if resource_process == shortage_process:
                    matched_count += 1
                    surplus = resource.get("surplus", 0)
                    app_logger.info(f"  余剰候補{j+1}: {resource.get('location_name')}の{resource_process} (余剰{surplus}名)")

                    if surplus > 0:
                        from_loc = resource.get("location_name")
                        # 同じ拠点への配置は除外
                        if from_loc != shortage_loc:
                            transfer_count = min(surplus, needed, 2)  # 最大2名まで

                            # この拠点・工程のオペレータを取得 (4階層対応)
                            # まず4階層キーで取得を試みる
                            operators_by_hierarchy = db_data.get("operators_by_hierarchy", {})

                            # shortage側の4階層情報を取得
                            shortage_category = shortage.get("business_category", "SS")
                            shortage_business = shortage.get("business_name", "新SS(W)")
                            shortage_ocr = shortage.get("process_category", "OCR対象")

                            # resource側の4階層情報を取得
                            resource_category = resource.get("business_category", "SS")
                            resource_business = resource.get("business_name", "新SS(W)")
                            resource_ocr = resource.get("process_category", "OCR対象")

                            # 4階層キーで検索
                            key_4layer = (from_loc, resource_category, resource_business, resource_ocr, shortage_process)
                            available_operators = operators_by_hierarchy.get(key_4layer, [])

                            # フォールバック: シンプルキーで検索
                            if not available_operators:
                                key_simple = (from_loc, shortage_process)
                                available_operators = operators_by_location_process.get(key_simple, [])
                                # さらにフィルタリング: 同じ業務・OCR区分のみ
                                available_operators = [
                                    op for op in available_operators
                                    if op.get("business_category") == shortage_category
                                    and op.get("business_name") == shortage_business
                                    and op.get("process_category") == shortage_ocr
                                ]

                            app_logger.info(f"    利用可能オペレータ: {len(available_operators)}名 (拠点={from_loc}, 工程={shortage_process})")

                            # ランダムまたは最初のN名を選択
                            import random
                            selected_operators = []
                            if available_operators:
                                # シャッフルしてランダム選択
                                shuffled = available_operators.copy()
                                random.shuffle(shuffled)
                                selected_operators = shuffled[:transfer_count]

                            operator_names = [op.get("operator_name") for op in selected_operators] if selected_operators else []

                            change = {
                                "from": from_loc,
                                "to": shortage_loc,
                                "process": shortage_process,
                                "count": transfer_count,
                                "operators": operator_names  # オペレータ名リスト追加
                            }
                            changes.append(change)
                            app_logger.info(f"  → 配置転換追加: {change}")

                            needed -= transfer_count
                            resource["surplus"] -= transfer_count

                        if needed <= 0:
                            break

            if matched_count == 0:
                app_logger.info(f"  → マッチする余剰なし")

        app_logger.info(f"提案生成完了: {len(changes)}件の配置転換")

        # 提案をまとめる
        suggestion = {
            "id": f"SGT{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "changes": changes,
            "impact": {
                "productivity": f"+{len(changes) * 10}%" if changes else "+0%",
                "delay": f"-{len(changes) * 15}分" if changes else "-0分",
                "quality": "維持"
            },
            "reason": self._generate_suggestion_reason(changes, 85.0),
            "confidence_score": 0.85 if changes else 0.5
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
        context: Optional[Dict[str, Any]] = None,
        rag_results: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        レスポンス生成用のコンテキストを準備
        """
        response_context = context or {}
        
        # データベース情報のサマリーを追加
        if db_data.get("current_assignments"):
            assignments = db_data["current_assignments"]
            # 拠点名がない場合はスキップ
            response_context["total_assignments"] = len(assignments)

        if db_data.get("shortage_list"):
            shortages = db_data["shortage_list"]
            response_context["shortage_count"] = len(shortages)
            response_context["total_shortage"] = sum(s.get("shortage", 0) for s in shortages)
        
        if db_data.get("productivity_trends"):
            trends = db_data["productivity_trends"]
            recent_avg = sum(t.get("avg_productivity", 0) for t in trends[:5]) / min(5, len(trends))
            response_context["recent_productivity"] = f"{recent_avg:.1f}%"
        
        if db_data.get("available_resources"):
            resources = db_data["available_resources"]
            response_context["available_locations"] = len(resources)
            response_context["total_surplus"] = sum(r.get("surplus", 0) for r in resources)

        # RAG検索結果をコンテキストに追加
        if rag_results:
            recommended_ops = rag_results.get("recommended_operators", [])
            if recommended_ops:
                response_context["rag_recommended_operators"] = [
                    {
                        "name": op["operator_name"],
                        "id": op["operator_id"],
                        "location": op["location_id"],
                        "score": f"{op['relevance_score']:.2f}"
                    }
                    for op in recommended_ops[:3]  # 上位3名
                ]
                response_context["rag_match_count"] = len(recommended_ops)

        return response_context
    
    def _generate_suggestion_reason(
        self,
        changes: List[Dict[str, Any]],
        avg_productivity: float
    ) -> str:
        """提案理由を生成"""
        if not changes or len(changes) == 0:
            return "現在のリソースで対応可能です"

        total_transfers = sum(c.get("count", 0) for c in changes)
        locations_involved = len(set(c.get("from", "") for c in changes if c.get("from")))

        if total_transfers == 0:
            return "現在のリソースで対応可能です"

        reasons = []
        if total_transfers > 5:
            reasons.append("大幅な人員不足を解消")
        if locations_involved > 2:
            reasons.append("複数拠点からの協力体制")

        if reasons:
            return "、".join(reasons) + f"（{total_transfers}名の配置調整）"
        else:
            return f"実データに基づく{total_transfers}名の配置調整"
    
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