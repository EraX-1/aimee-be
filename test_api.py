#!/usr/bin/env python3
"""
APIテストスクリプト
バックエンドAPIの動作確認用
"""

import requests
import json
from datetime import datetime


def test_health_check():
    """ヘルスチェック"""
    print("🔍 ヘルスチェック...")
    try:
        response = requests.get("http://localhost:8000/api/v1/health")
        if response.status_code == 200:
            print("✅ APIは正常に動作しています")
            print(f"   レスポンス: {response.json()}")
        else:
            print(f"❌ エラー: {response.status_code}")
    except requests.ConnectionError:
        print("❌ APIサーバーに接続できません。サーバーが起動していることを確認してください。")
        return False
    return True


def test_alerts_list():
    """アラート一覧取得テスト"""
    print("\n🔍 アラート一覧取得...")
    try:
        response = requests.get("http://localhost:8000/api/v1/alerts")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ {data['total']}件のアラートを取得しました")
            print(f"   最初のアラート: {data['alerts'][0]['title'] if data['alerts'] else 'なし'}")
        else:
            print(f"❌ エラー: {response.status_code}")
    except Exception as e:
        print(f"❌ エラー: {e}")


def test_alert_detail():
    """アラート詳細取得テスト"""
    print("\n🔍 アラート詳細取得...")
    try:
        response = requests.get("http://localhost:8000/api/v1/alerts/1")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ アラート詳細を取得しました")
            print(f"   タイトル: {data['alert']['title']}")
            print(f"   推奨アクション数: {len(data['recommended_actions'])}")
        else:
            print(f"❌ エラー: {response.status_code}")
    except Exception as e:
        print(f"❌ エラー: {e}")


def test_acknowledge_alert():
    """アラート確認テスト"""
    print("\n🔍 アラート確認...")
    try:
        response = requests.post("http://localhost:8000/api/v1/alerts/1/acknowledge")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ アラートを確認しました")
            print(f"   確認時刻: {data['acknowledged_at']}")
        else:
            print(f"❌ エラー: {response.status_code}")
    except Exception as e:
        print(f"❌ エラー: {e}")


def main():
    print("=" * 60)
    print("🚀 AIMEE Backend API テスト")
    print("=" * 60)
    
    # ヘルスチェック
    if not test_health_check():
        print("\n⚠️  APIサーバーが起動していません。")
        print("以下のコマンドでサーバーを起動してください:")
        print("cd /Users/umemiya/Desktop/erax/aimee-be && ./run_backend.sh")
        return
    
    # 各種APIテスト
    test_alerts_list()
    test_alert_detail()
    test_acknowledge_alert()
    
    print("\n✅ すべてのテストが完了しました")
    print("\n📝 Swagger UI でAPIドキュメントを確認:")
    print("   http://localhost:8000/docs")


if __name__ == "__main__":
    main()