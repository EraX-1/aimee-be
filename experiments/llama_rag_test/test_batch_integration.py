#!/usr/bin/env python3
"""
バッチ2（数値分析）とバッチ3（ノウハウ分析）の統合テスト
Llamaがこれらのバッチを呼び出すシミュレーション
"""

from llama_cpp import Llama
import json
import random
from datetime import datetime, timedelta

class Batch2NumericalAnalyzer:
    """バッチ2: 数値データ分析AI"""
    
    def analyze_productivity(self, location_id: int, date_range: dict):
        """生産性分析（ダミー実装）"""
        # 実際はDBから取得
        dummy_data = {
            1: {"name": "札幌", "productivity": 95, "trend": "stable"},
            2: {"name": "盛岡", "productivity": 110, "trend": "increasing"},
            3: {"name": "横浜", "productivity": 85, "trend": "decreasing"},
            4: {"name": "京都", "productivity": 100, "trend": "stable"}
        }
        
        location_data = dummy_data.get(location_id, {})
        
        return {
            "location_id": location_id,
            "location_name": location_data.get("name", "不明"),
            "productivity_rate": location_data.get("productivity", 0),
            "trend": location_data.get("trend", "unknown"),
            "analysis": f"{location_data.get('name', '不明')}拠点の生産性は{location_data.get('productivity', 0)}%です。",
            "recommendation": "熟練者の追加配置を検討してください。" if location_data.get("productivity", 100) < 90 else "現状維持で問題ありません。"
        }
    
    def forecast_workload(self, date: str):
        """業務量予測（ダミー実装）"""
        # 実際は過去データから予測
        base_workload = 100
        random_factor = random.uniform(0.8, 1.5)
        
        return {
            "date": date,
            "predicted_workload": int(base_workload * random_factor),
            "confidence": random.uniform(0.7, 0.95),
            "factors": ["過去の傾向", "曜日パターン", "季節要因"]
        }

class Batch3KnowledgeOptimizer:
    """バッチ3: ノウハウベース最適化AI"""
    
    def get_employee_preferences(self, employee_id: str):
        """従業員の特性・好み（ダミー実装）"""
        # 実際はRAGコンテキストから取得
        preferences = {
            "E001": {
                "name": "田中",
                "morning_performance": "low",
                "preferred_tasks": ["品質チェック", "データ確認"],
                "notes": "月曜朝は調子が悪い"
            },
            "E002": {
                "name": "佐藤",
                "morning_performance": "high",
                "preferred_tasks": ["データ入力", "補正処理"],
                "notes": "朝一番が最も生産的"
            }
        }
        
        return preferences.get(employee_id, {
            "name": "不明",
            "morning_performance": "normal",
            "preferred_tasks": [],
            "notes": "特記事項なし"
        })
    
    def optimize_assignment(self, employees: list, tasks: list, constraints: dict):
        """最適配置の提案（ダミー実装）"""
        # 実際は複雑な最適化ロジック
        assignments = []
        
        for i, emp in enumerate(employees):
            task = tasks[i % len(tasks)]
            pref = self.get_employee_preferences(emp)
            
            assignments.append({
                "employee_id": emp,
                "employee_name": pref["name"],
                "assigned_task": task,
                "shift_time": "午後" if pref["morning_performance"] == "low" else "午前",
                "confidence": random.uniform(0.8, 0.95)
            })
        
        return {
            "assignments": assignments,
            "optimization_score": random.uniform(0.85, 0.95),
            "applied_rules": ["従業員の好み考慮", "スキルマッチング", "負荷分散"]
        }

class AIOrchestrator:
    """メインAI（Llama）がバッチを統合的に制御"""
    
    def __init__(self, model_path):
        print("🤖 AIオーケストレーターを初期化中...")
        
        self.llm = Llama(
            model_path=model_path,
            n_ctx=2048,
            n_threads=8,
            n_gpu_layers=1,
        )
        
        self.batch2 = Batch2NumericalAnalyzer()
        self.batch3 = Batch3KnowledgeOptimizer()
        
        print("✅ 初期化完了！\n")
    
    def process_request(self, user_query: str):
        """ユーザーのリクエストを処理"""
        print(f"👤 ユーザー: {user_query}\n")
        
        # Step 1: Llamaが必要なバッチを判断
        analysis_prompt = f"""<s>[INST] <<SYS>>
あなたは労働力管理AIです。以下のツールを使用できます：
- batch2_analyze_productivity: 生産性を数値分析
- batch2_forecast_workload: 業務量を予測
- batch3_get_preferences: 従業員の特性を取得
- batch3_optimize_assignment: 最適配置を計算

ユーザーの質問に答えるために必要なツールを選んでください。
<</SYS>>

ユーザーの質問: {user_query}

必要なツール（カンマ区切り）: [/INST]"""
        
        # 今回はデモなので固定で両方のバッチを使用
        print("🔧 必要なツールを判断中...")
        
        # Step 2: バッチ2を実行（数値分析）
        print("\n📊 バッチ2（数値分析）を実行中...")
        productivity_data = self.batch2.analyze_productivity(3, {})  # 横浜拠点
        workload_data = self.batch2.forecast_workload("2024-11-20")
        
        print(f"  生産性: {productivity_data['productivity_rate']}%")
        print(f"  予測業務量: {workload_data['predicted_workload']}%")
        
        # Step 3: バッチ3を実行（ノウハウ分析）
        print("\n🧠 バッチ3（ノウハウ分析）を実行中...")
        optimization_data = self.batch3.optimize_assignment(
            ["E001", "E002", "E003"],
            ["データ入力", "品質チェック", "補正処理"],
            {}
        )
        
        print(f"  最適化スコア: {optimization_data['optimization_score']:.2%}")
        
        # Step 4: Llamaが統合的な回答を生成
        print("\n💭 統合的な回答を生成中...")
        
        final_prompt = f"""<s>[INST] <<SYS>>
あなたは労働力管理AIです。以下の分析結果を基に、ユーザーの質問に答えてください。
<</SYS>>

ユーザーの質問: {user_query}

分析結果:
1. 生産性分析: {json.dumps(productivity_data, ensure_ascii=False, indent=2)}
2. 業務量予測: {json.dumps(workload_data, ensure_ascii=False, indent=2)}
3. 最適配置: {json.dumps(optimization_data, ensure_ascii=False, indent=2)}

これらの結果を統合して、具体的な提案を含む回答を生成してください: [/INST]"""
        
        response = self.llm(final_prompt, max_tokens=500)
        answer = response['choices'][0]['text'].strip()
        
        print(f"\n🤖 AI: {answer}\n")
        
        return {
            "user_query": user_query,
            "batch2_results": {
                "productivity": productivity_data,
                "workload": workload_data
            },
            "batch3_results": {
                "optimization": optimization_data
            },
            "final_answer": answer
        }

def main():
    orchestrator = AIOrchestrator("./models/llama-2-7b-chat.Q4_K_M.gguf")
    
    print("=" * 60)
    print("🚀 バッチ統合テストを開始します")
    print("=" * 60)
    
    # テストケース
    test_queries = [
        "横浜拠点の明日の人員配置を最適化してください",
        "生産性が低下している拠点への対策を提案してください",
        "月曜日の朝の配置で注意すべき点を教えてください"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n【テストケース {i}】")
        print("-" * 60)
        
        result = orchestrator.process_request(query)
        
        print("\n📋 実行サマリー:")
        print(f"  - バッチ2実行: ✅")
        print(f"  - バッチ3実行: ✅")
        print(f"  - 統合回答生成: ✅")
        print("=" * 60)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")