#!/usr/bin/env python3
"""
アラート基準システムのテスト
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.alert_service import AlertService
from app.db.session import async_session_factory


async def test_alert_system():
    """アラート基準システムのテスト"""

    print("=" * 80)
    print("アラート基準システムテスト")
    print("=" * 80)
    print()

    async with async_session_factory() as db:
        alert_service = AlertService()

        # やばい基準の表示
        print("[1/3] やばい基準（アラート閾値）")
        print("-" * 80)
        for key, value in AlertService.ALERT_THRESHOLDS.items():
            print(f"  {key}: {value}")
        print()

        # アラートチェック実行
        print("[2/3] アラート基準チェック実行")
        print("-" * 80)
        alerts = await alert_service.check_all_alerts(db)

        print(f"  生成されたアラート数: {len(alerts)}件")
        print()

        if alerts:
            print("  検出されたアラート:")
            for i, alert in enumerate(alerts, 1):
                print(f"\n  【アラート{i}】")
                print(f"    タイプ: {alert.get('type')}")
                print(f"    優先度: {alert.get('priority')}")
                print(f"    タイトル: {alert.get('title')}")
                print(f"    メッセージ: {alert.get('message')}")
                print(f"    基準値: {alert.get('threshold')}")
                print(f"    現在値: {alert.get('current_value')}")
                print(f"    ルール元: {alert.get('rule_source')}")
        print()

        # アラート解消提案テスト
        if alerts:
            print("[3/3] アラート解消提案テスト")
            print("-" * 80)
            test_alert = alerts[0]
            print(f"  対象アラート: {test_alert.get('title')}")
            print()

            print("  AI解消提案を生成中...")
            resolution = await alert_service.resolve_alert_with_ai(test_alert, db)

            print()
            print("  【解消提案】")
            if "error" in resolution:
                print(f"    エラー: {resolution['error']}")
            else:
                print(f"    提案: {resolution.get('resolution', 'N/A')[:200]}...")
                if resolution.get('suggestion'):
                    sug = resolution['suggestion']
                    print(f"    提案ID: {sug.get('id', 'N/A')}")
                    print(f"    信頼度: {sug.get('confidence_score', 0):.2f}")
                    print(f"    理由: {sug.get('reason', 'N/A')}")
        else:
            print("[3/3] アラート解消提案テスト")
            print("-" * 80)
            print("  アラートがないためスキップ")

    print()
    print("=" * 80)
    print("テスト完了")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_alert_system())
