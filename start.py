#!/usr/bin/env python3
"""バックエンド起動スクリプト（Python版）"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    print("🚀 AIMEE バックエンドを起動します...")
    
    # 環境変数ファイルのチェック
    if not Path(".env").exists():
        print("⚠️  .envファイルが見つかりません。.env.exampleからコピーします...")
        if Path(".env.example").exists():
            import shutil
            shutil.copy(".env.example", ".env")
            print("✅ .envファイルを作成しました。必要に応じて編集してください。")
    
    # 依存関係のインストール
    print("📚 依存関係をインストールします...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
    
    # サーバー起動
    print("🌐 FastAPIサーバーを起動します...")
    print("📍 API: http://localhost:8002")
    print("📖 ドキュメント: http://localhost:8002/docs")
    print("")

    # Uvicornを起動
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--reload",
        "--host", "0.0.0.0",
        "--port", "8002"
    ])

if __name__ == "__main__":
    main()