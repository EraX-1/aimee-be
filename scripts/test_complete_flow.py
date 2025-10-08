#!/usr/bin/env python3
"""
完全フローテスト: 依頼文章から最終結果まで
実データ2,664名のオペレータと55,863件の処理可能工程を使用
"""
import asyncio
import sys
import os
import time
from datetime import datetime

# パスを追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.integrated_llm_service import IntegratedLLMService
from app.services.chroma_service import ChromaService
from app.db.session import async_session_factory
from app.core.logging import app_logger


async def test_complete_flow():
    """完全フローのテスト"""

    print("=" * 80)
    print("AIMEE Backend - 完全フローテスト（実データ版）")
    print("=" * 80)
    print(f"開始時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # ChromaDB統計情報
    print("[1/4] ChromaDB統計情報")
    print("-" * 80)
    chroma = ChromaService()
    stats = chroma.get_collection_stats()
    print(f"  総ドキュメント数: {stats.get('total_documents', 0):,}件")
    print()

    # テストケース
    test_cases = [
        {
            "name": "札幌拠点のエントリ工程で人員不足",
            "message": "札幌のエントリ1工程が遅延しています。人員を追加配置してください。",
            "context": {"location": "札幌", "process": "エントリ1"}
        },
        {
            "name": "品川拠点での補正工程オペレータ検索",
            "message": "品川で補正工程ができるオペレータを探しています",
            "context": {"location": "品川", "process": "補正"}
        },
        {
            "name": "業務523201の工程152に最適な配置",
            "message": "業務523201の工程152に最適なオペレータを配置したい",
            "context": {"business_id": "523201", "process_id": "152"}
        }
    ]

    # データベース接続
    async with async_session_factory() as db:
        service = IntegratedLLMService()

        for i, test in enumerate(test_cases, 1):
            print(f"[{i+1}/4] テストケース{i}: {test['name']}")
            print("-" * 80)
            print(f"  依頼文章: 「{test['message']}」")
            print()

            start_time = time.time()

            try:
                # 統合処理実行
                result = await service.process_message(
                    message=test['message'],
                    context=test['context'],
                    db=db,
                    detail=True
                )

                elapsed_time = time.time() - start_time

                # 結果表示
                print(f"  ✅ 処理完了（{elapsed_time:.2f}秒）")
                print()
                print("  【意図解析結果】")
                intent = result.get("intent", {})
                print(f"    意図タイプ: {intent.get('intent_type', 'N/A')}")
                print(f"    緊急度: {intent.get('urgency', 'N/A')}")
                print(f"    アクション必要: {intent.get('requires_action', False)}")
                print()

                print("  【RAG検索結果】")
                rag_results = result.get("rag_results", {})
                operators = rag_results.get("recommended_operators", [])
                print(f"    推奨オペレータ数: {len(operators)}名")
                if operators:
                    print("    上位3名:")
                    for j, op in enumerate(operators[:3], 1):
                        print(f"      {j}. {op.get('operator_name', 'N/A')} " +
                              f"(ID: {op.get('operator_id', 'N/A')}, " +
                              f"拠点: {op.get('location_id', 'N/A')}, " +
                              f"スコア: {op.get('relevance_score', 0):.3f})")
                print()

                print("  【AI応答】")
                response_text = result.get("response", "応答なし")
                # 長い場合は最初の200文字のみ表示
                if len(response_text) > 200:
                    print(f"    {response_text[:200]}...")
                else:
                    print(f"    {response_text}")
                print()

                print("  【パフォーマンス指標】")
                debug = result.get("debug_info", {})
                if debug:
                    step2 = debug.get("step2_rag_search", {})
                    print(f"    RAG検索時間: 含まれる")
                    print(f"    類似度トップスコア: {step2.get('top_relevance_score', 0):.3f}")
                print(f"    総処理時間: {elapsed_time:.2f}秒")
                print()

            except Exception as e:
                print(f"  ❌ エラー: {str(e)}")
                import traceback
                traceback.print_exc()

            print()

    print("=" * 80)
    print("全テスト完了")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_complete_flow())
