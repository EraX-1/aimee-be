#!/usr/bin/env python3
"""
統合LLMサービスのテストスクリプト
"""
import asyncio
import os
import sys
from datetime import datetime

# プロジェクトのパスを追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 環境変数を設定
os.environ["DATABASE_URL"] = "mysql+aiomysql://aimee_user:Aimee2024!@localhost:3306/aimee_db"
os.environ["OLLAMA_LIGHT_HOST"] = "localhost"
os.environ["OLLAMA_LIGHT_PORT"] = "11433"
os.environ["OLLAMA_MAIN_HOST"] = "localhost"  
os.environ["OLLAMA_MAIN_PORT"] = "11434"
os.environ["INTENT_MODEL"] = "qwen2:0.5b"
os.environ["MAIN_MODEL"] = "phi3:3.8b"

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.services.integrated_llm_service import IntegratedLLMService


async def get_test_db_session():
    """テスト用のデータベースセッションを作成"""
    engine = create_async_engine(
        os.environ["DATABASE_URL"],
        echo=False,
        pool_pre_ping=True
    )
    
    async_session = sessionmaker(
        engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
    
    await engine.dispose()


async def test_integrated_llm():
    """統合LLMサービスのテスト"""
    service = IntegratedLLMService()
    
    print("🚀 統合LLMサービステスト開始")
    print("=" * 60)
    
    # テストケース
    test_cases = [
        {
            "message": "札幌のエントリ1工程が遅延しています。対応策を提案してください。",
            "context": {"location": "札幌", "process": "エントリ1", "delay_minutes": 20}
        },
        {
            "message": "東京の出荷工程でリソースが不足しています",
            "context": {"location": "東京", "process": "出荷"}
        },
        {
            "message": "大阪の生産性が低下しています。原因と対策を教えてください",
            "context": {"location": "大阪"}
        }
    ]
    
    # データベースセッションを作成
    async for db in get_test_db_session():
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n📝 テストケース {i}/{len(test_cases)}")
            print(f"メッセージ: {test_case['message']}")
            print(f"コンテキスト: {test_case.get('context', {})}")
            print("-" * 40)
            
            try:
                # 統合処理を実行
                start_time = datetime.now()
                result = await service.process_message(
                    message=test_case["message"],
                    context=test_case.get("context"),
                    db=db
                )
                end_time = datetime.now()
                processing_time = (end_time - start_time).total_seconds()
                
                # 結果を表示
                print(f"\n✅ 処理完了 (処理時間: {processing_time:.2f}秒)")
                
                # 意図解析結果
                intent = result.get("intent", {})
                print(f"\n🎯 意図解析:")
                print(f"  - タイプ: {intent.get('intent_type')}")
                print(f"  - 緊急度: {intent.get('urgency')}")
                print(f"  - アクション必要: {intent.get('requires_action')}")
                print(f"  - エンティティ: {intent.get('entities')}")
                
                # メタデータ
                metadata = result.get("metadata", {})
                print(f"\n📊 メタデータ:")
                print(f"  - データソース: {metadata.get('data_sources')}")
                print(f"  - DBデータあり: {metadata.get('has_db_data')}")
                
                # 提案がある場合
                suggestion = result.get("suggestion")
                if suggestion:
                    print(f"\n💡 提案:")
                    print(f"  - ID: {suggestion.get('id')}")
                    changes = suggestion.get('changes', [])
                    if changes:
                        print(f"  - 変更内容:")
                        for change in changes[:3]:  # 最初の3つまで表示
                            print(f"    • {change['from']} → {change['to']} "
                                  f"({change['process']}) {change['count']}名")
                    impact = suggestion.get('impact', {})
                    if impact:
                        print(f"  - 予想される影響:")
                        print(f"    • 生産性: {impact.get('productivity')}")
                        print(f"    • 遅延: {impact.get('delay')}")
                        print(f"    • 品質: {impact.get('quality')}")
                    print(f"  - 理由: {suggestion.get('reason')}")
                    print(f"  - 信頼度: {suggestion.get('confidence_score', 0):.2f}")
                
                # レスポンス（最初の300文字）
                response_text = result.get("response", "")
                print(f"\n💬 レスポンス:")
                if len(response_text) > 300:
                    print(f"{response_text[:300]}...")
                else:
                    print(response_text)
                
            except Exception as e:
                print(f"\n❌ エラー発生: {str(e)}")
                import traceback
                traceback.print_exc()
            
            print("\n" + "=" * 60)
            
            # 次のテストケースの前に少し待機
            if i < len(test_cases):
                await asyncio.sleep(1)
    
    print("\n✨ テスト完了")


if __name__ == "__main__":
    asyncio.run(test_integrated_llm())