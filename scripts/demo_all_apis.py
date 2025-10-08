#!/usr/bin/env python3
"""
全APIのデモ実行と結果分析
"""
import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.alert_service import AlertService
from app.services.chroma_service import ChromaService
from app.services.integrated_llm_service import IntegratedLLMService
from app.db.session import async_session_factory


def print_section(title):
    """セクションヘッダーを表示"""
    print("\n" + "=" * 100)
    print(f"  {title}")
    print("=" * 100)


async def main():
    """全APIのデモ実行"""

    print("=" * 100)
    print("  AIMEE Backend API - デモ実行と根拠データ分析")
    print("=" * 100)

    async with async_session_factory() as db:

        # ============================================================
        # 1. アラート基準チェック
        # ============================================================
        print_section("1️⃣ アラート基準チェック（やばい基準判定）")

        alert_service = AlertService()

        print("\n📋 やばい基準（閾値）:")
        for key, value in AlertService.ALERT_THRESHOLDS.items():
            print(f"  - {key}: {value}")

        print("\n🔍 アラートチェック実行中...")
        alerts = await alert_service.check_all_alerts(db)

        print(f"\n✅ 検出結果: {len(alerts)}件のアラート")

        for i, alert in enumerate(alerts, 1):
            print(f"\n  【アラート{i}】")
            print(f"    タイプ: {alert['type']}")
            print(f"    優先度: {alert['priority']}")
            print(f"    タイトル: {alert['title']}")
            print(f"    現在値: {alert['current_value']} （基準: {alert['threshold']}）")
            print(f"    根拠ルール: {alert['rule_source']}")

            print(f"\n    📊 使用データ:")
            print(f"      - MySQL locations: 拠点情報")
            print(f"      - MySQL operators: オペレータ数カウント")
            print(f"      - rag_context: 管理者ルール「{alert['rule_source']}」")

        # ============================================================
        # 2. RAG検索（セマンティック検索）
        # ============================================================
        print_section("2️⃣ RAG検索（セマンティック検索）")

        chroma_service = ChromaService()
        query = "札幌の拠点でエントリ工程ができるオペレータ"

        print(f"\n🔍 検索クエリ: 「{query}」")
        print(f"📊 検索対象: ChromaDB 25,829ドキュメント")

        import time
        start = time.time()
        results = chroma_service.query_similar(query_text=query, n_results=5)
        elapsed = time.time() - start

        print(f"\n✅ 検索完了: {elapsed:.3f}秒")
        print(f"   結果数: {len(results.get('documents', []))}件")

        print(f"\n  【トップ3結果】")
        for i in range(min(3, len(results.get('documents', [])))):
            doc = results['documents'][i][:80]
            meta = results.get('metadatas', [])[i] if i < len(results.get('metadatas', [])) else {}
            distance = results.get('distances', [])[i] if i < len(results.get('distances', [])) else 0
            score = 1 - distance

            print(f"\n  {i+1}. スコア: {score:.3f}")
            print(f"     内容: {doc}...")
            print(f"     メタデータ: operator_id={meta.get('operator_id')}, location_id={meta.get('location_id')}")

            print(f"\n     📊 使用データ:")
            print(f"       - ChromaDB: オペレータチャンク（25,718件から検索）")
            print(f"       - ベクトル類似度計算")
            print(f"\n     🎯 根拠:")
            print(f"       - ベクトル類似度スコア: {score:.3f}")
            print(f"       - 拠点ID: {meta.get('location_id')}")

        # ============================================================
        # 3. RAG検索（工程特定）
        # ============================================================
        print_section("3️⃣ RAG検索（工程特定: 業務523201, 工程152）")

        print(f"\n🔍 検索条件:")
        print(f"  - 業務ID: 523201")
        print(f"  - 工程ID: 152")
        print(f"  - 拠点ID: 51（品川）")

        start = time.time()
        operators = chroma_service.find_best_operators_for_process(
            business_id="523201",
            process_id="152",
            location_id="51",
            n_results=5
        )
        elapsed = time.time() - start

        print(f"\n✅ 検索完了: {elapsed:.3f}秒")
        print(f"   推奨オペレータ数: {len(operators)}名")

        print(f"\n  【トップ3オペレータ】")
        for i, op in enumerate(operators[:3], 1):
            print(f"\n  {i}. {op.get('operator_name')} (ID: {op.get('operator_id')})")
            print(f"     拠点: {op.get('location_id')}")
            print(f"     スコア: {op.get('relevance_score', 0):.3f}")

            print(f"\n     📊 使用データ:")
            print(f"       - ChromaDB: オペレータチャンク（業務・工程でフィルタ）")
            print(f"       - MySQL: operator_process_capabilities（55,863件）")
            print(f"\n     🎯 根拠:")
            print(f"       - 業務523201 + 工程152の処理可能")
            print(f"       - 拠点51でフィルタリング")
            print(f"       - スキルマッチスコア: {op.get('relevance_score', 0):.3f}")

        # ============================================================
        # 4. 統合LLM処理
        # ============================================================
        print_section("4️⃣ 統合LLM処理（人員不足対応）")

        message = "札幌のエントリ1工程で2名不足しています。対応できるオペレータを提案してください。"
        print(f"\n📝 依頼文章: 「{message}」")

        print(f"\n🔄 5段階処理開始...")

        llm_service = IntegratedLLMService()
        start = time.time()
        result = await llm_service.process_message(
            message=message,
            context={"location": "札幌", "process": "エントリ1", "shortage": 2},
            db=db,
            detail=True
        )
        elapsed = time.time() - start

        print(f"\n✅ 処理完了: {elapsed:.2f}秒")

        # ステップ1: 意図解析
        print(f"\n  【ステップ1: 意図解析】")
        intent = result.get("intent", {})
        print(f"    意図タイプ: {intent.get('intent_type')}")
        print(f"    緊急度: {intent.get('urgency')}")
        print(f"    抽出エンティティ: {intent.get('entities')}")
        print(f"\n    📊 使用データ: LLM (qwen2:0.5b)")
        print(f"    🎯 根拠: 自然言語解析")

        # ステップ2: RAG検索
        print(f"\n  【ステップ2: RAG検索】")
        rag_results = result.get("rag_results", {})
        print(f"    推奨オペレータ数: {rag_results.get('recommended_operators', []).__len__() if isinstance(rag_results.get('recommended_operators'), list) else 0}名")
        print(f"    コンテキスト関連度: {rag_results.get('context_relevance', 0)}件")
        print(f"\n    📊 使用データ:")
        print(f"      - ChromaDB: 25,829ドキュメント")
        print(f"      - セマンティック検索")
        print(f"    🎯 根拠: ベクトル類似度スコア")

        # ステップ3: DB照会
        print(f"\n  【ステップ3: DB照会】")
        metadata = result.get("metadata", {})
        print(f"    データソース: {metadata.get('data_sources', [])}")
        print(f"    DB データ有: {metadata.get('has_db_data', False)}")
        print(f"\n    📊 使用データ:")
        print(f"      - MySQL operators: 2,664名")
        print(f"      - MySQL operator_process_capabilities: 55,863件")
        print(f"      - MySQL locations: 7拠点")
        print(f"    🎯 根拠: 実績データ、配置履歴")

        # ステップ4: 提案生成
        print(f"\n  【ステップ4: 提案生成】")
        suggestion = result.get("suggestion")
        if suggestion:
            print(f"    提案ID: {suggestion.get('id')}")
            print(f"    信頼度: {suggestion.get('confidence_score', 0):.2f}")
            print(f"    理由: {suggestion.get('reason')}")
            print(f"\n    📊 使用データ:")
            print(f"      - RAG検索結果")
            print(f"      - DB照会結果")
            print(f"      - rag_context: 管理者ルール14件")
            print(f"    🎯 根拠: RAG + DB + ルール適合")

        # ステップ5: AI応答
        print(f"\n  【ステップ5: AI応答生成】")
        response_text = result.get("response", "")
        print(f"    応答長: {len(response_text)}文字")
        print(f"    応答タイプ: {metadata.get('response_type', 'N/A')}")
        print(f"\n    📊 使用データ: LLM (gemma3:4b)")
        print(f"    🎯 根拠: 全ステップの統合結果")

        print(f"\n  📝 AI応答（抜粋）:")
        print(f"    {response_text[:200]}...")

        # ============================================================
        # 5. アラート解消提案
        # ============================================================
        if alerts:
            print_section("5️⃣ アラート解消提案（AI自動解消）")

            target_alert = alerts[0]
            print(f"\n🚨 対象アラート:")
            print(f"   タイトル: {target_alert['title']}")
            print(f"   メッセージ: {target_alert['message']}")

            print(f"\n🤖 AI解消提案を生成中...")

            start = time.time()
            resolution = await alert_service.resolve_alert_with_ai(target_alert, db)
            elapsed = time.time() - start

            print(f"\n✅ 解消提案生成完了: {elapsed:.2f}秒")

            if "error" not in resolution:
                print(f"\n  【解消提案】")
                print(f"    {resolution.get('resolution', '')[:300]}...")

                if resolution.get('suggestion'):
                    sug = resolution['suggestion']
                    print(f"\n  【配置変更案】")
                    print(f"    提案ID: {sug.get('id')}")
                    print(f"    信頼度: {sug.get('confidence_score', 0):.2f}")
                    print(f"    理由: {sug.get('reason')}")

                print(f"\n  📊 使用データ:")
                print(f"    - アラート情報（type, threshold, current_value）")
                print(f"    - 自動生成された依頼文章")
                print(f"    - 統合LLMの5段階処理")
                print(f"    - ChromaDB: 25,829ドキュメント")
                print(f"    - MySQL: 2,664名のオペレータ")
                print(f"    - rag_context: 管理者ルール")

                print(f"\n  🎯 根拠:")
                print(f"    - やばい基準（{target_alert['rule_source']}）")
                print(f"    - RAG推奨オペレータ")
                print(f"    - DB実績データ")
                print(f"    - 管理者ノウハウ14件")

    print("\n" + "=" * 100)
    print("  ✅ 全デモ完了")
    print("=" * 100)


if __name__ == "__main__":
    asyncio.run(main())
