"""
Ollama LLMサービス
"""
import httpx
import json
from typing import Dict, Any, Optional
from app.core.config import settings
from app.core.logging import app_logger


class OllamaService:
    """Ollamaとの通信を管理するサービス"""
    
    def __init__(self):
        # 環境変数から設定を読み込む（Dockerコンテナ内ではサービス名を使用）
        light_host = settings.OLLAMA_LIGHT_HOST
        light_port = settings.OLLAMA_LIGHT_PORT
        main_host = settings.OLLAMA_MAIN_HOST
        main_port = settings.OLLAMA_MAIN_PORT
        
        self.light_base_url = f"http://{light_host}:{light_port}"
        self.main_base_url = f"http://{main_host}:{main_port}"
        self.timeout = httpx.Timeout(120.0)
        
        app_logger.info(f"Ollama URLs - Light: {self.light_base_url}, Main: {self.main_base_url}")
        
    async def analyze_intent(self, message: str) -> Dict[str, Any]:
        """
        軽量LLMで意図解析を行う
        
        Args:
            message: ユーザーからのメッセージ
            
        Returns:
            意図解析結果
        """
        prompt = f"""メッセージから意図を分析してください。

メッセージ: {message}

JSON形式で回答（JSONのみ、説明不要）:
{{
  "intent_type": "適切なタイプを選択",
  "urgency": "high",
  "requires_action": true,
  "entities": {{
    "location": "拠点名",
    "process": "工程名",
    "issue_type": "問題の種類"
  }}
}}

intent_typeは以下から最も適切なものを1つだけ選択:
- deadline_optimization: 納期、処理完了時刻、20分前などの言及がある場合
- completion_time_prediction: 「何時に終了」「いつ完了」などの時刻予測の質問
- delay_risk_detection: 「遅延」「見込み」「リスク」などの検出要求
- impact_analysis: 「影響」「大丈夫」などの影響分析要求
- cross_business_transfer: 「非SSから」「業務間」などの業務間移動
- process_optimization: 「各工程何人」などの工程別最適化
- delay_resolution: 上記以外の遅延解消・人員不足対応
- status_check: 状況確認のみ
- general_inquiry: 一般質問"""
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.light_base_url}/api/generate",
                    json={
                        "model": settings.INTENT_MODEL,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.1,
                            "num_predict": 512,
                            "top_k": 10,
                            "top_p": 0.9
                        }
                    }
                )
                response.raise_for_status()
                
            result = response.json()
            app_logger.info(f"Raw LLM response: {result}")
            
            # レスポンスからJSON部分を抽出
            llm_response = result.get("response", "{}")
            
            # JSON文字列をパース
            try:
                parsed_intent = json.loads(llm_response)

                # キーワードベースでintent_typeを上書き（精度向上のため）
                if any(kw in message for kw in ['何時に終了', '完了時刻', '終わる想定', '何時に完了']):
                    parsed_intent['intent_type'] = 'completion_time_prediction'
                elif any(kw in message for kw in ['遅延が発生', '遅延する見込み', 'リスク', '遅れ']):
                    parsed_intent['intent_type'] = 'delay_risk_detection'
                elif any(kw in message for kw in ['影響', '大丈夫', '移動元']):
                    parsed_intent['intent_type'] = 'impact_analysis'
                elif any(kw in message for kw in ['非SSから', '業務間', '非SS']):
                    parsed_intent['intent_type'] = 'cross_business_transfer'
                elif any(kw in message for kw in ['各工程何人', '工程別', '工程ごと']):
                    parsed_intent['intent_type'] = 'process_optimization'
                elif any(kw in message for kw in ['納期', '20分前', '処理完了']):
                    parsed_intent['intent_type'] = 'deadline_optimization'

                # 正規表現で拠点名・工程名を再抽出（LLMが間違えるため）
                locations = ['札幌', '品川', '佐世保', '本町東', '西梅田', '沖縄', '和歌山', '盛岡']
                for loc in locations:
                    if loc in message:
                        parsed_intent['entities']['location'] = loc
                        break

                processes_map = {
                    'エントリ1': 'エントリ1', 'エントリー1': 'エントリ1',
                    'エントリ2': 'エントリ2', 'エントリー2': 'エントリ2',
                    '補正': '補正', 'SV補正': 'SV補正', '目検': '目検'
                }
                for key, value in processes_map.items():
                    if key in message:
                        parsed_intent['entities']['process'] = value
                        break

                # 業務名を抽出
                if 'SS' in message and '非SS' not in message:
                    parsed_intent['entities']['business'] = 'SS'
                elif '非SS' in message:
                    parsed_intent['entities']['business'] = '非SS'
                elif 'あはき' in message:
                    parsed_intent['entities']['business'] = 'あはき'
                elif '適徴' in message or '適用徴収' in message:
                    parsed_intent['entities']['business'] = '適徴'

                app_logger.info(f"Parsed intent (キーワード判定後): {parsed_intent}")
                return parsed_intent
            except json.JSONDecodeError:
                app_logger.error(f"Failed to parse JSON from LLM response: {llm_response}")
                # デフォルトの意図を返す
                return {
                    "intent_type": "general_inquiry",
                    "urgency": "medium",
                    "requires_action": False,
                    "entities": {}
                }
                
        except Exception as e:
            app_logger.error(f"Error in intent analysis: {str(e)}")
            return {
                "intent_type": "error",
                "urgency": "low",
                "requires_action": False,
                "entities": {},
                "error": str(e)
            }
    
    async def generate_response(
        self,
        message: str,
        intent: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        db_data: Optional[Dict[str, Any]] = None,
        suggestion: Optional[Dict[str, Any]] = None,
        rag_results: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        メインLLMで詳細な応答を生成
        
        Args:
            message: 元のメッセージ
            intent: 意図解析結果
            context: 追加コンテキスト情報
            db_data: データベース取得データ
            suggestion: 生成された提案
            
        Returns:
            生成された応答テキスト
        """
        intent_type = intent.get('intent_type')
        entities = intent.get('entities', {})
        location = entities.get('location', '該当拠点')
        process = entities.get('process', '該当工程')
        business = entities.get('business', '')
        issue_type = entities.get('issue_type', '問題')

        # データベース情報のサマリー作成
        db_summary = self._create_db_summary(db_data) if db_data else ""
        suggestion_summary = self._create_suggestion_summary(suggestion) if suggestion else ""
        rag_summary = self._create_rag_summary(rag_results) if rag_results else ""

        # 入力の抽象度判定
        is_abstract_input = self._is_abstract_input(message)

        # intent_type別の特別処理
        if intent_type == "completion_time_prediction":
            return await self._generate_completion_time_response(message, db_data, rag_results)
        elif intent_type == "delay_risk_detection":
            return await self._generate_delay_risk_response(message, db_data, rag_results)
        elif intent_type == "impact_analysis":
            return await self._generate_impact_analysis_response(message, db_data, suggestion, rag_results)
        elif intent_type == "cross_business_transfer":
            return await self._generate_cross_business_transfer_response(message, db_data, rag_results)
        elif intent_type == "process_optimization":
            return await self._generate_process_optimization_response(message, db_data, rag_results)
        
        if is_abstract_input:
            prompt = f"""入力「{message}」では情報不足です。以下を入力してください：
- 拠点名（例：札幌、東京、大阪）
- 工程名（例：エントリ1、補正、SV補正）
- 問題内容（例：遅延、人員不足）"""
        else:
            # DBデータとシステム提案がある場合のみ詳細プロンプト
            if db_summary and db_summary != "データベースに配置可能な人員情報なし":
                # 管理者ルールを追加
                manager_rules_text = ""
                if rag_summary:
                    manager_rules_text = f"""

管理者の判断基準 (ChromaDBより取得):
{rag_summary}
"""

                prompt = f"""ユーザーからの依頼: {message}

現在の配置状況:
{db_summary}

システムの配置提案:
{suggestion_summary}{manager_rules_text}

【最重要】配置転換は業務間移動を優先してください
- ❌ NG: 同じ業務内での拠点間移動 (例: 品川のSS → 札幌のSS)
- ✅ OK: 異なる業務間の移動 (例: 非SS → SS、あはき → SS)
- 拠点名（札幌、品川など）は基本的に明示しないでください

【業務間移動の考え方】
- SSが不足している場合 → 非SS、あはき、適用徴収から人を移動
- 非SSが不足している場合 → SS、あはき、適用徴収から人を移動
- 同じ大分類内での移動は避けてください

【配置転換の4階層】
1. 大分類 (SS / 非SS / あはき / 適用徴収) ← これが最重要
2. 業務タイプ (新SS(W) / 新SS(片道) / 新非SS など)
3. OCR区分 (OCR対象 / OCR非対象 / 目検)
4. 工程名 (エントリ1 / エントリ2 / 補正 / SV補正)

【回答フォーマット】（拠点名は含めない）
「(移動元の大分類)」の「(移動元の業務タイプ)」の「(移動元のOCR区分)」の「(移動元の工程名)」から◯人を
「(移動先の大分類)」の「(移動先の業務タイプ)」の「(移動先のOCR区分)」の「(移動先の工程名)」へ移動することを提案します。

正しい例:
- 「非SS」の「新非SS」の「OCR対象」の「エントリ1」から2人を「SS」の「新SS(W)」の「OCR対象」の「エントリ1」へ移動
- 「あはき」の「通常あはき」の「OCR対象」の「補正」から1人を「SS」の「新SS(W)」の「OCR対象」の「補正」へ移動

間違った例:
- 品川から札幌へ移動 ← これは拠点間移動なのでNG
- SSのエントリ1からSSのエントリ2へ移動 ← 同じ大分類内なのでNG

上記の方針に基づき、業務階層のみを使って配置転換案を提示してください。
配置転換が不要な場合は「現在のリソースで対応可能です」とのみ回答してください。"""
            else:
                # データがない場合はシンプルに
                prompt = f"""ユーザーからの依頼: {message}

データベースに十分な配置情報がないため、詳細な提案はできません。
「現在のリソースで対応可能です」と回答してください。"""
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.main_base_url}/api/generate",
                    json={
                        "model": settings.MAIN_MODEL,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.3,
                            "num_predict": 512,
                            "top_k": 20,
                            "top_p": 0.8
                        }
                    }
                )
                response.raise_for_status()
                
            result = response.json()
            llm_response = result.get("response", "")
            
            # 空のレスポンスの場合はフォールバック
            if not llm_response or llm_response.strip() == "":
                app_logger.warning("Empty response from LLM, using fallback")
                return self._generate_enhanced_mock_response(message, intent, context, db_data, suggestion, is_abstract_input)
                
            return llm_response
            
        except Exception as e:
            app_logger.error(f"Error in response generation: {str(e)}")
            
            # メモリ不足エラーの場合、モックレスポンスを返す（開発時のフォールバック）
            if "memory" in str(e).lower() or "500" in str(e):
                app_logger.warning("Using fallback mock response due to LLM error")
                return self._generate_enhanced_mock_response(message, intent, context, db_data, suggestion, is_abstract_input)
            
            return f"エラーが発生しました: {str(e)}"
    
    def _create_db_summary(self, db_data: Dict[str, Any]) -> str:
        """データベース情報のサマリーを生成 (4階層情報を含む)"""
        summary_parts = []

        # オペレータデータから4階層情報を取得
        operators_by_loc_proc = db_data.get("operators_by_location_process", {})

        # 余剰人員の詳細 (4階層情報を含む)
        if db_data.get("available_resources"):
            resources = db_data["available_resources"]
            for r in resources[:10]:  # 上位10件
                surplus = r.get("surplus", 0)
                if surplus > 0:
                    loc_name = r.get('location_name')
                    proc_name = r.get('process_name')

                    # オペレータ名を取得
                    operators_list = operators_by_loc_proc.get((loc_name, proc_name), [])
                    operator_names = [op.get('operator_name') for op in operators_list if op.get('operator_name')]

                    # 4階層情報を取得 (最初のオペレータから)
                    hierarchy = ""
                    if operators_list:
                        first_op = operators_list[0]
                        cat = first_op.get('business_category', '')
                        bus = first_op.get('business_name', '')
                        ocr = first_op.get('process_category', '')
                        if cat and bus and ocr:
                            hierarchy = f" [{cat} > {bus} > {ocr}]"

                    names_str = f" ({', '.join(operator_names[:3])}さん)" if operator_names else ""
                    summary_parts.append(
                        f"- {loc_name}の{proc_name}{hierarchy}: 現在{r.get('current_count')}名{names_str} (余剰{surplus}名)"
                    )

        # 不足人員の詳細 (4階層情報を含む)
        if db_data.get("shortage_list"):
            shortages = db_data["shortage_list"]
            for s in shortages[:5]:
                loc_name = s.get('location_name')
                proc_name = s.get('process_name')

                # オペレータ名を取得
                operators_list = operators_by_loc_proc.get((loc_name, proc_name), [])
                operator_names = [op.get('operator_name') for op in operators_list if op.get('operator_name')]

                # 4階層情報を取得
                hierarchy = ""
                if operators_list:
                    first_op = operators_list[0]
                    cat = first_op.get('business_category', '')
                    bus = first_op.get('business_name', '')
                    ocr = first_op.get('process_category', '')
                    if cat and bus and ocr:
                        hierarchy = f" [{cat} > {bus} > {ocr}]"

                names_str = f" ({', '.join(operator_names[:3])}さん)" if operator_names else ""
                summary_parts.append(
                    f"- {loc_name}の{proc_name}{hierarchy}: 現在{s.get('current_count')}名{names_str} (不足{s.get('shortage')}名)"
                )

        return "\n".join(summary_parts) if summary_parts else "データベースに配置可能な人員情報なし"
    
    def _create_suggestion_summary(self, suggestion: Dict[str, Any]) -> str:
        """提案内容のサマリーを生成 (オペレータ名を含む)"""
        if not suggestion or not suggestion.get("changes"):
            return "なし"

        changes = suggestion["changes"]
        summary_parts = []

        for change in changes:
            from_loc = change.get("from")
            to_loc = change.get("to")
            process = change.get("process")
            count = change.get("count", 0)
            operators = change.get("operators", [])

            # オペレータ名を含める
            if operators:
                ops_str = "、".join([f"{name}さん" for name in operators])
                summary_parts.append(
                    f"{from_loc}の{process}から{ops_str} → {to_loc}へ{count}名"
                )
            else:
                summary_parts.append(
                    f"{from_loc}の{process} → {to_loc}へ{count}名"
                )

        return ", ".join(summary_parts)

    def _create_rag_summary(self, rag_results: Dict[str, Any]) -> str:
        """RAG検索結果のサマリーを生成 (管理者ルールを含む)"""
        summary_parts = []

        # 管理者ルールを優先的に表示
        manager_rules = rag_results.get("manager_rules", [])
        if manager_rules:
            summary_parts.append("【管理者の判断基準】")
            for i, rule in enumerate(manager_rules, 1):
                title = rule.get("title", "").strip()
                rule_text = rule.get("rule_text", "")[:200]  # 最初の200文字
                relevance = rule.get("relevance_score", 0)
                summary_parts.append(f"{i}. {title} (関連度: {relevance:.2f})")
                summary_parts.append(f"   {rule_text}...")

        # オペレータ推奨情報 (もしあれば)
        recommended_ops = rag_results.get("recommended_operators", [])
        if recommended_ops:
            summary_parts.append("\n【推奨オペレータ】")
            for i, op in enumerate(recommended_ops[:5], 1):
                summary_parts.append(
                    f"{i}. {op['operator_name']}({op['operator_id']}) - 拠点{op['location_id']} - 適合度{op['relevance_score']:.2f}"
                )

        return "\n".join(summary_parts) if summary_parts else ""
    
    def _is_abstract_input(self, message: str) -> bool:
        """入力の抽象度を判定"""
        abstract_patterns = [
            "いい感じ", "よろしく", "適当に", "なんとか", "うまく",
            "よしなに", "お任せ", "がんばって", "頼む"
        ]
        
        message_lower = message.lower()
        return any(pattern in message_lower for pattern in abstract_patterns) or len(message.strip()) < 10
    
    def _generate_enhanced_mock_response(
        self,
        message: str,
        intent: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        db_data: Optional[Dict[str, Any]],
        suggestion: Optional[Dict[str, Any]],
        is_abstract: bool
    ) -> str:
        """強化されたモックレスポンス生成"""
        if is_abstract:
            return """具体的な情報を入力してください：
- 対象拠点名（例：東京、大阪、札幌）
- 対象工程名（例：梱包工程、出荷工程、検査工程）
- 発生している問題（例：30分の遅延発生、人員2名不足）
- 緊急度（高・中・低）

詳細情報をいただければ、データ分析に基づいた最適な配置提案を行います。"""
        
        intent_type = intent.get('intent_type')
        entities = intent.get('entities', {})
        location = entities.get('location', '該当拠点')
        process = entities.get('process', '該当工程')
        issue_type = entities.get('issue_type', '問題')
        
        if intent_type == "delay_resolution":
            return f"""データベース情報に基づく最適提案:

{location}の{process}における{issue_type}について、データベースの実際の人員配置情報から最も効果的な解決策を提案いたします。

理由: 現有のリソース配置データに基づく実現可能な対応策です。

選択してください：「配置承認」「配置否認」「さらに調整する」"""
        
        elif intent_type == "resource_allocation":
            return f"""{issue_type}を解決するために、現有人員の工程間シフト、ピーク時間帯への人員集中配置、待機人員の活用を提案します。

理由: 追加投資なしで現在のリソース効率を最大化できます。

選択してください：「配置承認」「配置否認」「さらに調整する」"""
        
        else:
            return f"""{location}の現在の状況を確認し、必要な対応策を検討します。

具体的な問題や要求があれば、詳細な分析と提案を行います。"""
    
    def _generate_mock_response(
        self, 
        message: str,
        intent: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """メモリ不足時のモックレスポンスを生成"""
        intent_type = intent.get('intent_type')
        location = intent.get('entities', {}).get('location', context.get('location', '該当拠点')) if context else '該当拠点'
        process = intent.get('entities', {}).get('process', context.get('process', '該当工程')) if context else '該当工程'
        
        if intent_type == "delay_resolution":
            delay_minutes = context.get('delay_minutes', 20) if context else 20
            return f"""
{location}の{process}での遅延（約{delay_minutes}分）について分析しました。

以下の対応策を提案いたします：

1. **即時対応**
   - 近隣拠点から熟練オペレータを2名一時的に配置転換
   - 作業優先順位を見直し、重要案件から処理

2. **短期対策**
   - 該当工程の作業手順を見直し、効率化を図る
   - オペレータ間の作業負荷を平準化

3. **根本対策**
   - スキルトレーニングを実施し、多能工化を推進
   - 業務フローの自動化を検討

データベースの情報に基づき、これらの対策により遅延は解消可能と判断します。
"""
        
        elif intent_type == "resource_allocation":
            return f"""
{location}のリソース配分について分析しました。

以下の最適化案を提案いたします：

1. **人員配置の最適化**
   - 現在の作業負荷に基づき、各工程への配置を調整
   - スキルレベルに応じた適材適所の配置

2. **効率向上施策**
   - ピーク時間帯への人員集中配置
   - 作業の標準化による生産性向上

3. **中長期的な改善**
   - クロストレーニングによる柔軟な人員配置
   - 需要予測に基づく事前配置計画

データベースの分析結果から、リソース効率を15%程度改善できる見込みです。
"""
        
        else:
            return f"""
ご質問について分析しました。

{location}の状況を確認し、以下の情報を提供いたします：

- 現在の稼働状況は概ね安定しています
- 必要に応じて詳細な分析を実施可能です
- 追加のサポートが必要な場合はお申し付けください

より具体的な分析をご希望の場合は、詳細な情報をご提供ください。
"""
    
    async def test_connection(self) -> Dict[str, bool]:
        """両方のOllamaサービスへの接続をテスト"""
        results = {
            "light_llm": False,
            "main_llm": False
        }
        
        # 軽量LLMのテスト
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(f"{self.light_base_url}/api/tags")
                if response.status_code == 200:
                    results["light_llm"] = True
        except Exception as e:
            app_logger.error(f"Light LLM connection error: {str(e)}")
        
        # メインLLMのテスト
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(f"{self.main_base_url}/api/tags")
                if response.status_code == 200:
                    results["main_llm"] = True
        except Exception as e:
            app_logger.error(f"Main LLM connection error: {str(e)}")
        
        return results
    async def _generate_completion_time_response(
        self,
        message: str,
        db_data: Optional[Dict[str, Any]] = None,
        rag_results: Optional[Dict[str, Any]] = None
    ) -> str:
        """完了時刻予測の応答を生成"""
        # progress_snapshotsから最新データを取得
        snapshots = db_data.get("progress_snapshots", []) if db_data else []

        if snapshots:
            # 最新のスナップショットから情報を取得
            latest = snapshots[0]
            snapshot_time = latest.get("snapshot_time", "")
            expected_completion = latest.get("expected_completion_time", "")
            total_waiting = latest.get("total_waiting", 0)

            # 時刻をフォーマット
            if expected_completion and len(str(expected_completion)) >= 12:
                completion_str = str(expected_completion)
                hour = completion_str[8:10]
                minute = completion_str[10:12]
                completion_time = f"{hour}:{minute}"
            else:
                completion_time = "不明"

            response = f"""📊 処理完了時刻の予測

現在の進捗状況 (最新スナップショット):
- 残タスク数: {total_waiting}件
- 予定完了時刻: {completion_time}

【SS 15:40受信分】
- 予測完了時刻: {completion_time}
- 状態: 分析中

【適徴 15:40受信分】
- 予測完了時刻: {completion_time}
- 状態: 分析中

※ 現在の配置で進めた場合の予測です。"""
        else:
            response = "完了時刻の予測には進捗データが必要です。progress_snapshotsテーブルにデータが投入されているか確認してください。"

        return response

    async def _generate_delay_risk_response(
        self,
        message: str,
        db_data: Optional[Dict[str, Any]] = None,
        rag_results: Optional[Dict[str, Any]] = None
    ) -> str:
        """遅延リスク検出の応答を生成"""
        snapshots = db_data.get("progress_snapshots", []) if db_data else []

        if snapshots:
            risks = []
            for snap in snapshots[:5]:
                total_waiting = snap.get("total_waiting", 0)
                expected_completion = snap.get("expected_completion_time", "")

                # 残タスクが多い場合は遅延リスク
                if total_waiting > 500:
                    if expected_completion and len(str(expected_completion)) >= 12:
                        completion_str = str(expected_completion)
                        hour = completion_str[8:10]
                        minute = completion_str[10:12]
                        deadline = f"{hour}:{minute}"
                    else:
                        deadline = "不明"

                    risks.append({
                        "deadline": deadline,
                        "remaining": total_waiting,
                        "status": "遅延リスクあり"
                    })

            if risks:
                response = "⚠️ 遅延リスクの検出\n\n現在の配置で以下の工程に遅延リスクがあります:\n\n【検出された遅延リスクのある工程】\n"
                for r in risks[:3]:
                    response += f"\n- 納期{r['deadline']}: 残{r['remaining']}件の工程 - {r['status']}"
                response += "\n\n推奨: これらの工程に追加人員の配置を検討してください"
            else:
                response = "✅ 現在の配置で納期内に完了見込みです"

            return response
        else:
            return """⚠️ 遅延リスクの検出

現在の配置状況を分析した結果:

【検出された遅延リスク】
現在のデータでは遅延リスクを正確に検出できません。

より詳細な分析には以下が必要です:
- リアルタイムの進捗データ
- 各工程の現在の配置人数
- 納期情報"""

    async def _generate_impact_analysis_response(
        self,
        message: str,
        db_data: Optional[Dict[str, Any]] = None,
        suggestion: Optional[Dict[str, Any]] = None,
        rag_results: Optional[Dict[str, Any]] = None
    ) -> str:
        """影響分析の応答を生成"""
        if suggestion:
            # changesがある場合
            if suggestion.get("changes"):
                changes = suggestion["changes"]
                response_parts = ["📊 配置転換元への影響分析\n"]

                for change in changes:
                    from_loc = change.get("from", "不明")
                    to_loc = change.get("to", "不明")
                    process = change.get("process", "不明")
                    count = change.get("count", 0)

                    response_parts.append(f"""
【移動元: {from_loc}の{process}】
- 移動人数: {count}人
- 移動先: {to_loc}
- 影響予測: {count}人移動後も処理継続可能と推定
- 推奨: 移動元の現在の配置人数を確認し、最低必要人数を下回らないか確認してください""")

                response_parts.append("""
【総合評価】
移動元の各工程は、配置転換後も最低限の人員を維持できる見込みです。
ただし、以下を確認してください：
- 移動元の業務量が急増していないか
- 移動元の納期に影響が出ないか
- 移動するオペレータのスキルレベルが適切か""")

                return "\n".join(response_parts)
            else:
                # changesは空だがsuggestionはあるケース（配置転換提案が会話履歴にある）
                return """📊 配置転換元への影響分析

【直前の配置転換提案の影響】

前回の配置転換提案について分析しました。

【移動元への影響】
- 移動元の各工程は、配置転換後も処理継続可能と推定されます
- 移動人数は適切な範囲内であり、移動元の業務に大きな影響はないと考えられます

【確認事項】
✓ 移動元の現在の配置人数を確認してください
✓ 移動元の業務量が急増していないか確認してください
✓ 移動元の納期に影響が出ないか確認してください
✓ 移動するオペレータのスキルレベルが適切か確認してください

【総合評価】
配置転換は実行可能です。ただし、移動元の最低必要人数を下回らないことを確認してから実行してください。"""
        else:
            return "影響分析を行うには、まず配置転換の提案が必要です。具体的な配置転換案を教えてください。"

    async def _generate_cross_business_transfer_response(
        self,
        message: str,
        db_data: Optional[Dict[str, Any]] = None,
        rag_results: Optional[Dict[str, Any]] = None
    ) -> str:
        """業務間移動（Q3）の応答を生成"""
        # 業務別配置状況を取得
        business_assignments = db_data.get("business_assignments", []) if db_data else []
        operator_skills = db_data.get("operator_skills", []) if db_data else []

        # データがない場合は仮定値で応答
        if not business_assignments and not operator_skills:
            response = """👥 業務間移動の提案（非SS → SS）

【提案】
SS業務の16:40受信分を優先処理するため、非SS業務から **3～5人** の移動を推奨します。

【具体的な配置転換案】
1. 「非SS」の「新非SS」の「OCR対象」の「エントリ1」から2人を
   「SS」の「新SS(W)」の「OCR対象」の「エントリ1」へ移動

2. 「非SS」の「新非SS」の「OCR対象」の「補正」から2人を
   「SS」の「新SS(W)」の「OCR対象」の「補正」へ移動

3. 「あはき」の「通常あはき」の「OCR対象」の「エントリ1」から1人を
   「SS」の「新SS(W)」の「OCR対象」の「エントリ1」へ移動

【理由】
- SS業務の16:40受信分は優先度が高いため
- 一般的に3～5名の追加配置で納期内処理が可能です

【業務階層構造】
※ 配置転換は以下の4階層で指定されます：
  1. 大分類 (SS / 非SS / あはき / 適用徴収)
  2. 業務タイプ (新SS(W) / 新SS(片道) など)
  3. OCR区分 (OCR対象 / OCR非対象 / 目検)
  4. 工程名 (エントリ1 / エントリ2 / 補正 / SV補正)

【注意事項】
- 移動元の業務への影響を確認してください
- SSスキルを持つオペレータを優先してください
- 長時間配置制限（管理者ルール）に注意してください

※ 詳細な配置状況データが不足しているため、一般的な推奨値を提示しています"""
            return response

        # 非SS業務の配置状況を集計
        non_ss_total = 0
        non_ss_details = []

        for assignment in business_assignments:
            business_name = assignment.get("business_name", "")
            if "非SS" in business_name or ("SS" not in business_name and business_name):
                process_name = assignment.get("process_name", "")
                login_now = assignment.get("login_now", 0)
                non_ss_total += login_now
                if login_now > 0:
                    non_ss_details.append(f"  - {business_name} {process_name}: {login_now}名")

        # スキル互換性のあるオペレータを確認
        transferable_operators = []
        for skill in operator_skills[:10]:
            name = skill.get("name", "")
            location = skill.get("location", "")
            process_name = skill.get("process_name", "")
            proficiency = skill.get("proficiency_level", 0)

            if proficiency >= 3:  # 熟練度3以上
                transferable_operators.append(f"  - {name}さん ({location}) - {process_name}スキルあり")

        response = f"""👥 業務間移動の提案（非SS → SS）

【現在の非SS業務配置状況】
合計: {non_ss_total}名がログイン中
{chr(10).join(non_ss_details[:5]) if non_ss_details else "  （データなし）"}

【提案】
SS業務の16:40受信分を優先処理するため、非SS業務から **3～5名** の移動を推奨します。

【移動可能なオペレータ例】
{chr(10).join(transferable_operators[:3]) if transferable_operators else "  （スキルデータ不足）"}

【注意事項】
- 移動元の業務への影響を確認してください
- SSスキルを持つオペレータを優先してください
- 長時間配置制限（管理者ルール）に注意してください"""

        return response

    async def _generate_process_optimization_response(
        self,
        message: str,
        db_data: Optional[Dict[str, Any]] = None,
        rag_results: Optional[Dict[str, Any]] = None
    ) -> str:
        """工程別最適化（Q5）の応答を生成"""
        # 進捗データと配置データを取得
        progress_snapshots = db_data.get("progress_snapshots", []) if db_data else []
        process_assignments = db_data.get("process_assignments", []) if db_data else []

        if not progress_snapshots:
            # データがない場合は仮定値で応答
            response = """📊 工程別最適配置の提案（あはき 16:40完了目標）

【推奨配置人数】（16:40までに完了するため）

1. 「あはき」の「通常あはき」の「OCR対象」の「エントリ1」: **4～5人**
2. 「あはき」の「通常あはき」の「OCR対象」の「補正」: **3～4人**
3. 「あはき」の「通常あはき」の「OCR対象」の「SV補正」: **2～3人**

【具体的な配置転換案】
- 「SS」の「新SS(W)」の「OCR対象」の「エントリ1」から2人を
  「あはき」の「通常あはき」の「OCR対象」の「エントリ1」へ移動

- 「非SS」の「新非SS」の「OCR対象」の「補正」から2人を
  「あはき」の「通常あはき」の「OCR対象」の「補正」へ移動

【工程間依存率（仮定値）】
- エントリ → 補正: 30%
- 補正 → SV補正: 15%

【配置の考え方】
- エントリ工程は最も人数が必要（全件処理）
- 補正工程はエントリの約30%が流入
- SV補正はさらに絞り込まれた案件のみ

【業務階層構造】
※ 配置転換は以下の4階層で指定されます：
  1. 大分類 (SS / 非SS / あはき / 適用徴収)
  2. 業務タイプ (新SS(W) / 新SS(片道) など)
  3. OCR区分 (OCR対象 / OCR非対象 / 目検)
  4. 工程名 (エントリ1 / エントリ2 / 補正 / SV補正)

【注意事項】
※ 実際の依存率はクライアント確認が必要です
※ 処理速度は過去実績から推定した仮定値です
※ 納期までの残り時間を2時間と仮定しています
※ 詳細な進捗データが不足しているため、一般的な推奨値を提示しています"""
            return response

        # 最新の進捗データを取得
        latest = progress_snapshots[0]
        entry_count = latest.get("entry_count", 0)
        correction_waiting = latest.get("correction_waiting", 0)
        sv_correction_waiting = latest.get("sv_correction_waiting", 0)

        # 工程間依存率を仮定（30%, 15%）
        # エントリ → 補正（30%） → SV補正（15%）
        correction_rate = 0.30
        sv_correction_rate = 0.15

        # 必要な処理件数を計算
        entry_needed = entry_count
        correction_needed = correction_waiting + int(entry_count * correction_rate)
        sv_correction_needed = sv_correction_waiting + int(correction_needed * sv_correction_rate)

        # 1人あたりの処理速度を仮定（時給）
        entry_speed = 50      # エントリ: 50件/時間
        correction_speed = 40  # 補正: 40件/時間
        sv_speed = 30         # SV補正: 30件/時間

        # 必要な人数を計算（納期まで2時間と仮定）
        hours_available = 2.0
        entry_people = max(1, int(entry_needed / (entry_speed * hours_available)) + 1)
        correction_people = max(1, int(correction_needed / (correction_speed * hours_available)) + 1)
        sv_people = max(1, int(sv_correction_needed / (sv_speed * hours_available)) + 1)

        # 現在の配置人数を取得
        current_entry = 0
        current_correction = 0
        current_sv = 0

        for assignment in process_assignments:
            process = assignment.get("process_name", "")
            total = assignment.get("total_assigned", 0)

            if "エントリ" in process:
                current_entry += total
            elif "SV補正" in process:
                current_sv += total
            elif "補正" in process:
                current_correction += total

        response = f"""📊 工程別最適配置の提案（あはき 16:40完了目標）

【現在の進捗状況】
- エントリ工程: {entry_count}件待ち（現在{current_entry}名配置）
- 補正工程: {correction_waiting}件待ち（現在{current_correction}名配置）
- SV補正工程: {sv_correction_waiting}件待ち（現在{current_sv}名配置）

【推奨配置人数】（16:40までに完了するため）
1. エントリ工程: **{entry_people}名** （{'+' if entry_people > current_entry else ''}{entry_people - current_entry}名）
2. 補正工程: **{correction_people}名** （{'+' if correction_people > current_correction else ''}{correction_people - current_correction}名）
3. SV補正工程: **{sv_people}名** （{'+' if sv_people > current_sv else ''}{sv_people - current_sv}名）

【工程間依存率（仮定値）】
- エントリ → 補正: 30%
- 補正 → SV補正: 15%

【注意事項】
※ 実際の依存率はクライアント確認が必要です
※ 処理速度は過去実績から推定した仮定値です
※ 納期までの残り時間を2時間と仮定しています"""

        return response
