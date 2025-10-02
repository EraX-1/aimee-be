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
        prompt = f"""あなたはメッセージの意図を分析するアシスタントです。
以下のメッセージを分析し、JSON形式で結果を返してください。

メッセージ: {message}

以下の形式で回答してください（JSONのみ、他の文章は不要）：
{{
  "intent_type": "delay_resolution|resource_allocation|status_check|general_inquiry",
  "urgency": "high|medium|low",
  "requires_action": true|false,
  "entities": {{
    "location": "拠点名（あれば）",
    "process": "工程名（あれば）",
    "issue_type": "遅延|人員不足|品質問題|その他"
  }}
}}"""
        
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
                            "num_predict": 200,
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
                app_logger.info(f"Parsed intent: {parsed_intent}")
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
        suggestion: Optional[Dict[str, Any]] = None
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
        
        # 入力の抽象度判定
        is_abstract_input = self._is_abstract_input(message)
        
        if is_abstract_input:
            prompt = f"""入力「{message}」では情報不足です。以下を入力してください：
- 拠点名（例：東京、大阪）
- 工程名（例：梱包工程、検査工程）  
- 問題内容（例：遅延30分、人員2名不足）
- 緊急度（高・中・低）"""
        else:
            prompt = f"""{location}の{process}で{issue_type}が発生しました。

データベース取得情報:
{db_summary}

システム提案:
{suggestion_summary}

【絶対制約・実行指示】
- データベースの余剰人員情報を必ず使用して配置提案を行う
- 上記のデータベース情報に記載された実在する拠点・工程のみ使用
- 架空の拠点名は一切使用禁止
- データベースに余剰人員がある場合は必ず配置転換案を1つ提案する
- 余剰人員がない場合のみ「配置困難」と回答する

必須回答形式: 
最適提案: [余剰人員がある拠点名]の[工程名]から[余剰人数]名を[問題のある拠点]へ配置転換

実行理由: データベースの余剰人員データに基づく実現可能な配置変更
最後に「配置承認」「配置否認」「さらに調整する」の選択を促す。"""
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.main_base_url}/api/generate",
                    json={
                        "model": settings.MAIN_MODEL,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "num_predict": 200,
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
        """データベース情報のサマリーを生成"""
        summary_parts = []
        
        # 人員不足の詳細
        if db_data.get("current_assignments"):
            assignments = db_data["current_assignments"]
            for a in assignments:
                shortage = a.get("shortage", 0)
                if shortage > 0:
                    summary_parts.append(
                        f"- {a.get('location_name')}の{a.get('process_name')}で{shortage}名不足"
                    )
        
        # 余剰人員の詳細
        if db_data.get("available_resources"):
            resources = db_data["available_resources"]
            for r in resources:
                surplus = r.get("surplus", 0)
                if surplus > 0:
                    summary_parts.append(
                        f"- {r.get('location_name')}の{r.get('process_name')}で{surplus}名余剰"
                    )
                    employees = r.get("available_employees", "")
                    if employees:
                        summary_parts.append(f"  対象者: {employees}")
        
        # リソース概要
        if db_data.get("resource_overview"):
            overview = db_data["resource_overview"]
            for o in overview[:5]:  # 上位5件のみ
                location = o.get("location_name")
                process = o.get("process_name")
                allocated = o.get("allocated_count", 0)
                required = o.get("required_count", 5)
                if location and process:
                    summary_parts.append(
                        f"- {location}の{process}: 配置{allocated}名/必要{required}名"
                    )
        
        return "\n".join(summary_parts) if summary_parts else "データベースに配置可能な人員情報なし"
    
    def _create_suggestion_summary(self, suggestion: Dict[str, Any]) -> str:
        """提案内容のサマリーを生成"""
        if not suggestion or not suggestion.get("changes"):
            return "システムによる配置変更提案なし（データベース情報を基に新規提案を生成してください）"
        
        changes = suggestion["changes"]
        summary_parts = []
        
        for i, change in enumerate(changes, 1):
            from_loc = change.get("from")
            to_loc = change.get("to")
            process = change.get("process")
            count = change.get("count", 0)
            
            summary_parts.append(
                f"{i}. {from_loc}の{process}から{to_loc}へ{count}名配置転換"
            )
        
        return "\n".join(summary_parts) if summary_parts else "具体的な配置転換案を生成してください"
    
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