#!/usr/bin/env python3
"""
SECRET_KEY生成スクリプト
"""

import secrets
import string

def generate_secret_key(length=64):
    """
    セキュアなランダム文字列を生成
    """
    # 使用可能な文字（英数字）
    alphabet = string.ascii_letters + string.digits
    # ランダムに選択
    secret_key = ''.join(secrets.choice(alphabet) for _ in range(length))
    return secret_key

if __name__ == "__main__":
    # SECRET_KEY生成
    secret_key = generate_secret_key()
    
    print("🔐 SECRET_KEY生成完了！")
    print("=" * 70)
    print(f"{secret_key}")
    print("=" * 70)
    print("")
    print("📝 使い方:")
    print("1. 上記のキーをコピー")
    print("2. .envファイルのSECRET_KEY=の後に貼り付け")
    print("")
    print("⚠️  注意:")
    print("- このキーは一度だけ生成して、安全に保管してください")
    print("- 本番環境では絶対に公開しないでください")
    print("- Gitにコミットしないよう.gitignoreに.envを追加済みです")