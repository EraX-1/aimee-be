#!/usr/bin/env python3
"""
クイックフローテスト: RAG検索のみテスト
"""
import sys
import os
import time

# パスを追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.chroma_service import ChromaService


def test_rag_search():
    """RAG検索のクイックテスト"""

    print("=" * 80)
    print("RAG検索クイックテスト（実データ版）")
    print("=" * 80)

    chroma = ChromaService()

    # 統計情報
    print("\n[1/3] ChromaDB統計情報")
    stats = chroma.get_collection_stats()
    print(f"  総ドキュメント数: {stats.get('total_documents', 0):,}件")

    # テストケース1: セマンティック検索
    print("\n[2/3] セマンティック検索テスト")
    print("  クエリ: 「札幌の拠点でエントリ工程ができるオペレータ」")

    start_time = time.time()
    results = chroma.query_similar(
        query_text="札幌の拠点でエントリ工程ができるオペレータ",
        n_results=5
    )
    elapsed = time.time() - start_time

    print(f"  検索時間: {elapsed:.2f}秒")
    print(f"  結果数: {len(results.get('documents', []))}件")

    if results.get('documents'):
        print("  トップ3結果:")
        for i in range(min(3, len(results['documents']))):
            doc = results['documents'][i][:100]
            meta = results.get('metadatas', [])[i] if i < len(results.get('metadatas', [])) else {}
            distance = results.get('distances', [])[i] if i < len(results.get('distances', [])) else 0
            print(f"    {i+1}. スコア: {1-distance:.3f} | {doc}...")

    # テストケース2: 工程特定検索
    print("\n[3/3] 工程特定オペレータ検索")
    print("  業務ID: 523201, 工程ID: 152")

    start_time = time.time()
    operators = chroma.find_best_operators_for_process(
        business_id="523201",
        process_id="152",
        n_results=5
    )
    elapsed = time.time() - start_time

    print(f"  検索時間: {elapsed:.2f}秒")
    print(f"  推奨オペレータ数: {len(operators)}名")

    if operators:
        print("  トップ3オペレータ:")
        for i, op in enumerate(operators[:3], 1):
            print(f"    {i}. {op.get('operator_name', 'N/A')} " +
                  f"(ID: {op.get('operator_id', 'N/A')}, " +
                  f"拠点: {op.get('location_id', 'N/A')}, " +
                  f"スコア: {op.get('relevance_score', 0):.3f})")

    print("\n" + "=" * 80)
    print("✅ テスト完了")
    print("=" * 80)


if __name__ == "__main__":
    test_rag_search()
