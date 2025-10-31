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

                # 管理者ノウハウ・判断基準を検索
                manager_rules = self._chroma_service.search_manager_rules(
                    query_text=message,
                    n_results=5
                )
                rag_results["manager_rules"] = manager_rules
                app_logger.info(f"管理者ルール検索完了: {len(manager_rules)}件")

                if detail:
                    debug_info["step2_rag_search"] = {
                        "query_text": message,
                        "manager_rules_count": len(manager_rules),
                        "manager_rules": [r.get("title") for r in manager_rules]
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

        # ステップ4: 提案生成（intent_typeに応じて処理）
        suggestion = None
        intent_type = intent.get("intent_type")

        # completion_time_prediction と delay_risk_detection は提案不要
        # impact_analysisは直前の提案を参照
        if intent_type == "impact_analysis":
            app_logger.info(f"Intent type 'impact_analysis' - 直前の提案を参照")
            # contextから直前の提案を取得
            last_suggestion = context.get("last_suggestion") if context else None
            if last_suggestion:
                suggestion = last_suggestion
                app_logger.info(f"直前の提案を使用: {suggestion}")
            else:
                app_logger.warning("直前の提案が見つかりません")
        elif intent_type in ["completion_time_prediction", "delay_risk_detection"]:
            app_logger.info(f"Intent type '{intent_type}' は提案生成をスキップ（予測・検出のみ）")
        elif intent.get("requires_action") and (db_data or rag_results):
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

        # intent_typeに応じて応答を生成
        intent_type = intent.get("intent_type")

        # impact_analysis（影響分析）の場合は専用の応答
        if intent_type == "impact_analysis":
            response_text = self._generate_impact_analysis_response(suggestion)
            app_logger.info(f"影響分析応答生成（LLMスキップ）")
        # 提案がある場合はシンプル応答（LLMスキップで高速化）
        elif suggestion and len(suggestion.get("changes", [])) > 0:
            response_text = self._generate_simple_response(suggestion)
            app_logger.info(f"シンプル応答生成（LLMスキップ）: {len(suggestion.get('changes', []))}件")
        else:
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
                "manager_rules": rag_results.get("manager_rules", []),
                "context_relevance": len(rag_results.get("manager_rules", []))
            },
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "data_sources": list(db_data.keys()) + ["rag_search", "manager_rules"],
                "has_db_data": bool(db_data and not db_data.get("error")),
                "has_rag_data": bool(rag_results),
                "has_manager_rules": bool(rag_results.get("manager_rules")),
                "response_type": response_type
            }
        }
        
        if detail:
            # DebugInfoモデルのフィールド名に合わせてキーを変換
            result["debug_info"] = {
                "intent_analysis": debug_info.get("step1_intent_analysis"),
                "database_queries": debug_info.get("step2_database_queries"),
                "rag_results": debug_info.get("step2_rag_search"),
                "processing_time": debug_info.get("processing_time", {}),
                "skill_matching": debug_info.get("step4_suggestion_generation")
            }

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
        elif intent_type == "deadline_optimization":
            return await self._generate_delay_resolution_suggestion(intent, db_data, context)
        elif intent_type == "cross_business_transfer":
            return await self._generate_delay_resolution_suggestion(intent, db_data, context)
        elif intent_type == "process_optimization":
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

        # 不足がない場合でも、deadline_optimization等では提案を生成
        intent_type = intent.get("intent_type")
        if len(shortage_list) == 0 and intent_type in ["deadline_optimization", "cross_business_transfer"]:
            app_logger.info(f"不足なしだが、{intent_type}のため効率化提案を生成")

            # 非SSのリソースを優先的に選ぶ（業務間移動）
            non_ss_resources = [
                r for r in available_resources
                if r.get("business_category") not in ["SS", None]
            ]

            app_logger.info(f"非SSリソース: {len(non_ss_resources)}件")

            # 工程別にグループ化
            by_process = {}
            for r in non_ss_resources:
                proc = r.get("process_name", "不明")
                if proc not in by_process:
                    by_process[proc] = []
                by_process[proc].append(r)

            # 優先順位: エントリ1 > エントリ2 > 補正
            priority_processes = ["エントリ1", "エントリ2", "補正", "SV補正"]
            selected_operators_set = set()

            for priority_proc in priority_processes:
                if len(changes) >= 3:  # 最大3件
                    break

                if priority_proc not in by_process or len(by_process[priority_proc]) == 0:
                    continue

                resource = by_process[priority_proc][0]
                process_name = resource.get("process_name")

                # 該当工程のスキル保有者を取得
                operators_by_target_skill = db_data.get("operators_by_target_skill", {})
                skill_holders = operators_by_target_skill.get(process_name, [])

                # オペレータを選定（ランダムに2人）
                import random
                operator_names = []
                if len(skill_holders) > 0:
                    # 移動元の業務カテゴリのオペレータを優先
                    from_category = resource.get("business_category")
                    from_ops = [
                        op for op in skill_holders
                        if op.get("current_business_category") == from_category
                        and op.get("operator_name") not in selected_operators_set
                    ]

                    if len(from_ops) >= 2:
                        random.shuffle(from_ops)
                        selected = from_ops[:2]
                        operator_names = [op.get("operator_name") for op in selected]
                        for name in operator_names:
                            selected_operators_set.add(name)

                app_logger.info(f"オペレータ選定: {len(operator_names)}人（{process_name}）")

                if len(operator_names) > 0:
                    # 4階層形式で生成（非SS → SS）
                    change = {
                        "from_business_category": resource.get("business_category"),
                        "from_business_name": resource.get("business_name"),
                        "from_process_category": resource.get("process_category", "OCR対象"),
                        "from_process_name": process_name,
                        "to_business_category": "SS",
                        "to_business_name": "新SS(W)",
                        "to_process_category": resource.get("process_category", "OCR対象"),
                        "to_process_name": process_name,
                        "count": len(operator_names),
                        "operators": operator_names,
                        "is_cross_business": True
                    }
                    changes.append(change)
                    app_logger.info(f"業務間移動提案: {resource.get('business_category')} → SS ({process_name}, {len(operator_names)}人: {operator_names})")

        # 不足している拠点・工程に対して、余剰がある拠点から配置
        for i, shortage in enumerate(shortage_list[:5]):  # 最大5件の不足に対応
            shortage_loc = shortage.get("location_name")
            shortage_process = shortage.get("process_name")
            needed = shortage.get("shortage", 0)

            app_logger.info(f"不足{i+1}: {shortage_loc}の{shortage_process} (不足{needed}名)")

            # 同じ工程で余剰がある拠点を探す（業務間移動を優先、なければ同一業務も許可）
            matched_count = 0

            # shortage側の4階層情報を取得
            shortage_category = shortage.get("business_category", "SS")
            shortage_business = shortage.get("business_name", "新SS(W)")
            shortage_ocr = shortage.get("process_category", "OCR対象")

            # フェーズ1: 業務間移動を探す（優先）
            cross_business_resources = []
            same_business_resources = []

            for j, resource in enumerate(available_resources):
                resource_process = resource.get("process_name", "")
                if resource_process == shortage_process:
                    surplus = resource.get("surplus", 0)
                    if surplus > 0:
                        resource_category = resource.get("business_category", "SS")
                        is_cross_business = (resource_category != shortage_category)

                        if is_cross_business:
                            cross_business_resources.append(resource)
                            app_logger.info(f"  業務間余剰{len(cross_business_resources)}: {resource.get('location_name')}の{resource_process} ({resource_category} → {shortage_category}) 余剰{surplus}名")
                        else:
                            same_business_resources.append(resource)
                            app_logger.info(f"  同一業務余剰{len(same_business_resources)}: {resource.get('location_name')}の{resource_process} ({resource_category}) 余剰{surplus}名")

            # 優先順位: 業務間移動 → 同一業務内移動
            priority_resources = cross_business_resources + same_business_resources
            app_logger.info(f"  マッチング候補: 業務間{len(cross_business_resources)}件, 同一業務{len(same_business_resources)}件")

            for j, resource in enumerate(priority_resources):
                if len(changes) >= 3:  # 最大3件の変更
                    break

                matched_count += 1
                surplus = resource.get("surplus", 0)
                resource_process = resource.get("process_name", "")
                resource_category = resource.get("business_category", "SS")
                resource_business = resource.get("business_name", "新SS(W)")
                resource_ocr = resource.get("process_category", "OCR対象")
                is_cross_business = (resource_category != shortage_category)

                if surplus > 0:  # 業務間・同一業務両方を許可（優先順位付き）
                        from_loc = resource.get("location_name")
                        # 同じ拠点への配置は除外
                        if from_loc != shortage_loc:
                            transfer_count = min(surplus, needed, 2)  # 最大2名まで

                            # この拠点・工程のオペレータを取得 (4階層対応)
                            # まず4階層キーで取得を試みる
                            operators_by_hierarchy = db_data.get("operators_by_hierarchy", {})

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

    def _generate_impact_analysis_response(self, suggestion: Dict[str, Any]) -> str:
        """
        影響分析の応答を生成（Q2対応）
        """
        # 直前の提案を確認
        if suggestion and len(suggestion.get("changes", [])) > 0:
            changes = suggestion.get("changes", [])
            total_moved = sum(c.get("count", 0) for c in changes)

            response_parts = [
                "**移動元への影響分析**",
                "",
                f"直前の提案で合計{total_moved}人の移動を提案しています。",
                "",
                "【移動元の確認事項】"
            ]

            # ユニークな移動元を抽出
            from_locations = set()
            for c in changes:
                from_cat = c.get("from_business_category", "")
                from_name = c.get("from_business_name", "")
                from_proc = c.get("from_process_name", "")
                count = c.get("count", 0)
                from_locations.add((from_cat, from_name, from_proc, count))

            for i, (cat, name, proc, count) in enumerate(sorted(from_locations), 1):
                response_parts.append(f"{i}. **{cat}**の「{name}」の「{proc}」")
                response_parts.append(f"   移動人数: {count}人")
                response_parts.append(f"   → 残りの人員で処理可能か確認が必要")
                response_parts.append("")

            response_parts.append("【推奨確認】")
            response_parts.append("- 移動元の工程に十分な人員が残っているか")
            response_parts.append("- 移動後も処理速度が維持できるか")
            response_parts.append("- 特定のスキル保有者が偏っていないか")

            return "\n".join(response_parts)
        else:
            # 直前の提案がない場合
            return """**配置変更における移動元への影響確認ポイント**

配置変更を実施する際は、以下の点を確認してください：

【移動元工程の確認事項】
1. 残存人員数
   - 移動後も最低限の人員が確保できているか

2. スキルバランス
   - 熟練者と新人のバランスは適切か

3. 処理速度への影響
   - 移動後も納期に間に合う処理速度が維持できるか

【推奨】
具体的な配置変更を提案した後、この影響確認を行うことをお勧めします。"""

    def _generate_simple_response(self, suggestion: Dict[str, Any]) -> str:
        """
        提案がある場合のシンプルな応答を生成（LLMスキップで高速化）
        4階層形式に対応
        """
        changes = suggestion.get("changes", [])
        total = sum(c.get("count", 0) for c in changes)

        lines = [f"**配置変更を提案します**（合計{total}人）\n"]

        for i, c in enumerate(changes[:5], 1):
            # 4階層形式を優先、なければ旧形式
            from_cat = c.get("from_business_category", "")
            from_name = c.get("from_business_name", "")
            from_proc = c.get("from_process_name", c.get("process", "不明"))
            to_cat = c.get("to_business_category", "")
            to_name = c.get("to_business_name", "")
            to_proc = c.get("to_process_name", c.get("process", "不明"))
            count = c.get("count", 0)
            operators = c.get("operators", [])

            # 4階層表示
            if from_cat:
                lines.append(f"{i}. **{from_cat}**の「{from_name}」の「{from_proc}」")
                lines.append(f"   → **{to_cat}**の「{to_name}」の「{to_proc}」")
                lines.append(f"   移動人数: {count}人")
            else:
                # 旧形式フォールバック
                from_loc = c.get("from", "不明")
                to_loc = c.get("to", "不明")
                lines.append(f"{i}. {from_loc} → {to_loc} ({from_proc}, {count}人)")

            if operators and len(operators) > 0:
                lines.append(f"   オペレータ: {', '.join(operators[:3])}")

            lines.append("")

        if len(changes) > 5:
            lines.append(f"（他{len(changes)-5}件の提案あり）")

        return "\n".join(lines)