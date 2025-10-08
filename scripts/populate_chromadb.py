"""
ChromaDBにMySQLデータを投入するスクリプト
"""
import sys
import os
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from dotenv import load_dotenv

from app.services.chroma_service import ChromaService
from app.core.logging import app_logger

# 環境変数をロード
load_dotenv()


async def fetch_operators(session: AsyncSession):
    """オペレータ情報を取得"""
    query = text("""
        SELECT operator_id, operator_name, location_id, is_valid, belong_code
        FROM operators
        WHERE is_valid = 1
    """)
    result = await session.execute(query)
    return [dict(row._mapping) for row in result]


async def fetch_operator_capabilities(session: AsyncSession, operator_id: str):
    """特定オペレータの処理可能工程を取得"""
    query = text("""
        SELECT business_id, process_id, work_level, location_id
        FROM operator_process_capabilities
        WHERE operator_id = :operator_id
    """)
    result = await session.execute(query, {"operator_id": operator_id})
    return [dict(row._mapping) for row in result]


async def fetch_processes(session: AsyncSession):
    """工程情報を取得"""
    query = text("""
        SELECT business_id, process_id, level_id, process_name,
               process_name_detail, process_category
        FROM processes
    """)
    result = await session.execute(query)
    return [dict(row._mapping) for row in result]


async def main():
    """メイン処理"""
    app_logger.info("=" * 60)
    app_logger.info("ChromaDBデータ投入スクリプト開始")
    app_logger.info("=" * 60)

    # データベース接続設定
    database_url = os.getenv("DATABASE_URL", "mysql+aiomysql://root:root_password@localhost:3306/aimee_db")

    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # ChromaDBサービス初期化
    try:
        chroma_service = ChromaService()
        app_logger.info("ChromaDBサービスを初期化しました")
    except Exception as e:
        app_logger.error(f"ChromaDB初期化失敗: {e}")
        return

    async with async_session() as session:
        try:
            # オペレータデータを取得してチャンク化
            app_logger.info("\n[1/3] オペレータデータを取得中...")
            operators = await fetch_operators(session)
            app_logger.info(f"  → {len(operators)}名のオペレータを取得")

            all_operator_chunks = []
            for operator in operators:
                operator_id = operator["operator_id"]
                capabilities = await fetch_operator_capabilities(session, operator_id)

                chunks = chroma_service.create_operator_chunks(operator, capabilities)
                all_operator_chunks.extend(chunks)
                app_logger.info(f"  オペレータ {operator_id}: {len(chunks)}チャンク作成")

            # オペレータチャンクをChromaDBに追加
            if all_operator_chunks:
                app_logger.info(f"\n  {len(all_operator_chunks)}個のオペレータチャンクをChromaDBに投入中...")
                chroma_service.add_documents(all_operator_chunks)
                app_logger.info("  ✓ オペレータチャンク投入完了")

            # 工程データを取得してチャンク化
            app_logger.info("\n[2/3] 工程データを取得中...")
            processes = await fetch_processes(session)
            app_logger.info(f"  → {len(processes)}件の工程を取得")

            process_chunks = chroma_service.create_process_chunks(processes)
            app_logger.info(f"  {len(process_chunks)}個の工程チャンクを作成")

            # 工程チャンクをChromaDBに追加
            if process_chunks:
                app_logger.info(f"\n  {len(process_chunks)}個の工程チャンクをChromaDBに投入中...")
                chroma_service.add_documents(process_chunks)
                app_logger.info("  ✓ 工程チャンク投入完了")

            # 統計情報を表示
            app_logger.info("\n[3/3] ChromaDB統計情報:")
            stats = chroma_service.get_collection_stats()
            app_logger.info(f"  コレクション名: {stats.get('collection_name')}")
            app_logger.info(f"  総ドキュメント数: {stats.get('total_documents')}")

        except Exception as e:
            app_logger.error(f"データ投入エラー: {e}", exc_info=True)
            raise
        finally:
            await engine.dispose()

    app_logger.info("\n" + "=" * 60)
    app_logger.info("ChromaDBデータ投入完了！")
    app_logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
