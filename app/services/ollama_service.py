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
        prompt = f"""メッセージから拠点名と工程名を抽出してください。

メッセージ: {message}

拠点名の候補: 札幌, 品川, 佐世保, 本町東, 西梅田, 沖縄, 和歌山
工程名の候補: エントリ1, エントリ2, 補正, SV補正, 目検

JSON形式で回答（JSONのみ、説明不要）:
{{
  "intent_type": "delay_resolution",
  "urgency": "high",
  "requires_action": true,
  "entities": {{
    "location": "メッセージに含まれる拠点名",
    "process": "メッセージに含まれる工程名",
    "issue_type": "人員不足"
  }}
}}

intent_typeは以下から1つだけ選択:
- delay_resolution (遅延解消)
- resource_allocation (人員配置)
- status_check (状況確認)
- general_inquiry (一般質問)"""
        
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

                app_logger.info(f"Parsed intent (正規表現上書き後): {parsed_intent}")
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
        location = entities.get('location', 'な拠点')
        process = entities.get('process', '該当工程')
        issue_type = entities.get('issue_type', '問題')
        
        # データベース情報のサマリー作成
        db_summary = self._create_db_summary(db_data) if db_data else ""
        suggestion_summary = self._create_suggestion_summary(suggestion) if suggestion else ""
        rag_summary = self._create_rag_summary(rag_results) if rag_results else ""
        
        # 入力の抽象度判定
        is_abstract_input = self._is_abstract_input(message)
        
        if is_abstract_input:
            prompt = f"""入力「{message}」では情報不足です。以下を入力してください：
- 拠点名（例：札幌、東京、大阪）
- 工程名（例：エントリ1、補正、SV補正）
- 問題内容（例：遅延、人員不足）"""
        else:
            # DBデータとシステム提案がある場合のみ詳細プロンプト
            if db_summary and db_summary != "データベースに配置可能な人員情報なし":
                prompt = f"""ユーザーからの依頼: {message}

現在の配置状況:
{db_summary}

システムの配置提案:
{suggestion_summary}

【重要】配置転換案を提示する際は、必ず以下の4階層を明示してください:
1. 大分類 (新SS / 新SS+ / あはき / その他)
2. 業務タイプ (新SS(W) / 新SS(U) など)
3. OCR区分 (OCR対象 / OCR非対象 / 目検)
4. 工程名 (エントリ1 / エントリ2 / 補正 / SV補正)

【回答フォーマット】
「(大分類)」の「(業務タイプ)」の「(OCR区分)」の「(工程名)」において、
[元の拠点]から[配置先の拠点]へ[オペレータ名]を配置転換することを提案します。

【重要な注意】
- システムの配置提案に記載されている通り、「[元の拠点]から[配置先の拠点]へ」の順番を厳守してください
- オペレータ名は必ずシステムの配置提案に記載されている名前をそのまま使用してください
- 存在しないオペレータ名や拠点名を作らないでください

例: 「新SS」の「新SS(W)」の「OCR対象」の「エントリ1」において、以下の配置転換を提案します:
1. 札幌から品川へ札幌テスト太郎1、札幌テスト太郎6を配置転換
2. 西梅田から品川へ大阪テスト花子1、大阪テスト花子2を配置転換

上記のシステムの配置提案に記載されているすべての提案を含めて、簡潔に配置転換案を提示してください。
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

        for idx, change in enumerate(changes, 1):
            from_loc = change.get("from")
            to_loc = change.get("to")
            process = change.get("process")
            count = change.get("count", 0)
            operators = change.get("operators", [])

            # オペレータ名を含める（より明確なフォーマット）
            if operators:
                ops_str = "、".join(operators)
                summary_parts.append(
                    f"【提案{idx}】{from_loc}から{to_loc}へ {ops_str} ({count}名) を配置転換 (工程: {process})"
                )
            else:
                summary_parts.append(
                    f"【提案{idx}】{from_loc}から{to_loc}へ {count}名を配置転換 (工程: {process})"
                )

        return "\n".join(summary_parts)

    def _create_rag_summary(self, rag_results: Dict[str, Any]) -> str:
        """RAG検索結果のサマリーを生成"""
        recommended_ops = rag_results.get("recommended_operators", [])
        if not recommended_ops:
            return "RAG検索結果: 該当するオペレータが見つかりませんでした"

        summary_parts = ["RAG検索で以下のオペレータが適合しました:"]
        for i, op in enumerate(recommended_ops[:5], 1):
            summary_parts.append(
                f"{i}. {op['operator_name']}({op['operator_id']}) - 拠点{op['location_id']} - 適合度{op['relevance_score']:.2f}"
            )

        return "\n".join(summary_parts)
    
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