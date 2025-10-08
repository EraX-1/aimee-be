"""
RAG検索と人員配置最適化のテストスクリプト
"""
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from app.services.chroma_service import ChromaService
from app.core.logging import app_logger

load_dotenv()


def print_separator(title=""):
    """セパレータを表示"""
    print("\n" + "=" * 70)
    if title:
        print(f"  {title}")
        print("=" * 70)


def test_basic_search():
    """基本的なRAG検索テスト"""
    print_separator("テスト1: 基本的なセマンティック検索")

    chroma = ChromaService()

    # テスト1: オペレータ検索
    print("\n🔍 クエリ: '札幌の拠点でエントリ工程ができるオペレータ'")
    results = chroma.query_similar(
        query_text="札幌の拠点でエントリ工程ができるオペレータ",
        n_results=3
    )

    print(f"\n📊 検索結果: {len(results['documents'])}件")
    for i, (doc, metadata, distance) in enumerate(zip(
        results['documents'],
        results['metadatas'],
        results['distances']
    ), 1):
        print(f"\n結果 {i}:")
        print(f"  関連性スコア: {1 - distance:.3f}")
        print(f"  タイプ: {metadata.get('type')}")
        if 'operator_name' in metadata:
            print(f"  オペレータ: {metadata.get('operator_name')} ({metadata.get('operator_id')})")
            print(f"  拠点: {metadata.get('location_id')}")
        print(f"  内容: {doc[:150]}...")


def test_process_search():
    """工程情報の検索テスト"""
    print_separator("テスト2: 工程情報検索")

    chroma = ChromaService()

    # テスト2: 工程検索
    print("\n🔍 クエリ: '補正工程について教えて'")
    results = chroma.query_similar(
        query_text="補正工程について教えて",
        n_results=3
    )

    print(f"\n📊 検索結果: {len(results['documents'])}件")
    for i, (doc, metadata, distance) in enumerate(zip(
        results['documents'],
        results['metadatas'],
        results['distances']
    ), 1):
        print(f"\n結果 {i}:")
        print(f"  関連性スコア: {1 - distance:.3f}")
        print(f"  タイプ: {metadata.get('type')}")
        if 'process_name' in metadata:
            print(f"  工程名: {metadata.get('process_name')}")
            print(f"  工程ID: {metadata.get('process_id')}")
            print(f"  カテゴリ: {metadata.get('process_category')}")
        print(f"  内容: {doc[:150]}...")


def test_operator_matching():
    """特定工程に最適なオペレータを検索"""
    print_separator("テスト3: 工程別オペレータマッチング")

    chroma = ChromaService()

    # テスト3: 業務523201のエントリ1工程に最適なオペレータ
    print("\n🔍 業務523201の工程152(エントリ1)に最適なオペレータを検索")
    operators = chroma.find_best_operators_for_process(
        business_id="523201",
        process_id="152",
        n_results=5
    )

    print(f"\n📊 マッチング結果: {len(operators)}名")
    for i, op in enumerate(operators, 1):
        print(f"\n候補 {i}:")
        print(f"  オペレータ: {op['operator_name']} ({op['operator_id']})")
        print(f"  拠点: {op['location_id']}")
        print(f"  関連性スコア: {op['relevance_score']:.3f}")


def test_location_based_search():
    """拠点指定での検索テスト"""
    print_separator("テスト4: 拠点指定オペレータ検索")

    chroma = ChromaService()

    # テスト4: 札幌拠点でのオペレータ検索
    print("\n🔍 札幌拠点(91)で業務523201ができるオペレータ")
    operators = chroma.find_best_operators_for_process(
        business_id="523201",
        process_id="152",
        location_id="91",
        n_results=5
    )

    print(f"\n📊 マッチング結果: {len(operators)}名")
    for i, op in enumerate(operators, 1):
        print(f"\n候補 {i}:")
        print(f"  オペレータ: {op['operator_name']} ({op['operator_id']})")
        print(f"  拠点: {op['location_id']}")
        print(f"  関連性スコア: {op['relevance_score']:.3f}")


def test_collection_stats():
    """コレクション統計情報"""
    print_separator("テスト5: ChromaDB統計情報")

    chroma = ChromaService()
    stats = chroma.get_collection_stats()

    print(f"\n📊 コレクション統計:")
    print(f"  コレクション名: {stats.get('collection_name')}")
    print(f"  総ドキュメント数: {stats.get('total_documents')}")


def main():
    """メインテスト実行"""
    print("\n" + "=" * 70)
    print("  AIMEE RAGシステム - 人員配置最適化テスト")
    print("=" * 70)

    try:
        # 統計情報
        test_collection_stats()

        # 基本検索
        test_basic_search()

        # 工程検索
        test_process_search()

        # オペレータマッチング
        test_operator_matching()

        # 拠点指定検索
        test_location_based_search()

        print("\n" + "=" * 70)
        print("  ✅ 全てのテストが完了しました！")
        print("=" * 70 + "\n")

    except Exception as e:
        app_logger.error(f"テスト実行エラー: {e}", exc_info=True)
        print(f"\n❌ エラーが発生しました: {e}\n")


if __name__ == "__main__":
    main()
