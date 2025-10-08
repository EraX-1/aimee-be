"""
統合LLM + RAGシステムのエンドツーエンドテスト
"""
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

from app.services.integrated_llm_service import IntegratedLLMService
from app.core.logging import app_logger

load_dotenv()


def print_separator(title=""):
    """セパレータを表示"""
    print("\n" + "=" * 80)
    if title:
        print(f"  {title}")
        print("=" * 80)


async def test_case_1():
    """テストケース1: 札幌拠点のエントリ1工程で人員不足"""
    print_separator("テストケース1: 札幌拠点のエントリ1工程で人員不足")

    database_url = os.getenv("DATABASE_URL", "mysql+aiomysql://root:root_password@localhost:3306/aimee_db")
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    service = IntegratedLLMService()

    message = "札幌拠点のエントリ1工程で2名不足しています。対応できるオペレータを提案してください。"
    context = {
        "location": "札幌",
        "process": "エントリ1",
        "shortage": 2
    }

    print(f"\n📝 入力メッセージ: {message}")
    print(f"📋 コンテキスト: {context}")

    async with async_session() as session:
        result = await service.process_message(
            message=message,
            context=context,
            db=session,
            detail=True
        )

    print(f"\n🤖 AI応答:")
    print(result["response"])

    print(f"\n📊 意図解析:")
    print(f"  - タイプ: {result['intent'].get('intent_type')}")
    print(f"  - 緊急度: {result['intent'].get('urgency')}")
    print(f"  - アクション必要: {result['intent'].get('requires_action')}")

    print(f"\n🔍 RAG検索結果:")
    rag_ops = result.get('rag_results', {}).get('recommended_operators', [])
    if rag_ops:
        print(f"  推奨オペレータ: {len(rag_ops)}名")
        for op in rag_ops[:3]:
            print(f"    - {op['operator_name']}({op['operator_id']}) 拠点{op['location_id']} スコア{op['relevance_score']:.2f}")
    else:
        print("  推奨オペレータなし")

    print(f"\n💡 提案:")
    if result.get('suggestion'):
        print(f"  ID: {result['suggestion'].get('id')}")
        print(f"  信頼度: {result['suggestion'].get('confidence_score', 0):.2f}")
        print(f"  理由: {result['suggestion'].get('reason')}")
    else:
        print("  提案なし")

    await engine.dispose()


async def test_case_2():
    """テストケース2: 補正工程に対応できるオペレータを検索"""
    print_separator("テストケース2: 補正工程に対応できるオペレータを検索")

    database_url = os.getenv("DATABASE_URL", "mysql+aiomysql://root:root_password@localhost:3306/aimee_db")
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    service = IntegratedLLMService()

    message = "業務523201の補正工程ができるオペレータを教えてください"

    print(f"\n📝 入力メッセージ: {message}")

    async with async_session() as session:
        result = await service.process_message(
            message=message,
            context={},
            db=session,
            detail=False
        )

    print(f"\n🤖 AI応答:")
    print(result["response"])

    print(f"\n🔍 RAG検索結果:")
    rag_ops = result.get('rag_results', {}).get('recommended_operators', [])
    print(f"  推奨オペレータ: {len(rag_ops)}名")
    for op in rag_ops[:5]:
        print(f"    - {op['operator_name']}({op['operator_id']}) 拠点{op['location_id']} スコア{op['relevance_score']:.2f}")

    await engine.dispose()


async def test_case_3():
    """テストケース3: 拠点指定での人員配置"""
    print_separator("テストケース3: 本町東拠点で業務523201の人員を増やしたい")

    database_url = os.getenv("DATABASE_URL", "mysql+aiomysql://root:root_password@localhost:3306/aimee_db")
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    service = IntegratedLLMService()

    message = "本町東拠点で業務523201の人員を1名増やしたいです。誰を配置すべきですか？"
    context = {
        "location": "本町東",
        "business_id": "523201"
    }

    print(f"\n📝 入力メッセージ: {message}")

    async with async_session() as session:
        result = await service.process_message(
            message=message,
            context=context,
            db=session,
            detail=False
        )

    print(f"\n🤖 AI応答:")
    print(result["response"])

    print(f"\n🔍 RAG検索結果:")
    rag_ops = result.get('rag_results', {}).get('recommended_operators', [])
    if rag_ops:
        print(f"  推奨オペレータ: {len(rag_ops)}名")
        for op in rag_ops[:3]:
            print(f"    - {op['operator_name']}({op['operator_id']}) 拠点{op['location_id']} スコア{op['relevance_score']:.2f}")

    await engine.dispose()


async def main():
    """メインテスト実行"""
    print("\n" + "=" * 80)
    print("  統合LLM + RAGシステム - エンドツーエンドテスト")
    print("=" * 80)

    try:
        await test_case_1()
        await test_case_2()
        await test_case_3()

        print("\n" + "=" * 80)
        print("  ✅ 全てのテストが完了しました！")
        print("=" * 80 + "\n")

    except Exception as e:
        app_logger.error(f"テスト実行エラー: {e}", exc_info=True)
        print(f"\n❌ エラーが発生しました: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
