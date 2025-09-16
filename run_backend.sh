#!/bin/bash

# バックエンド起動スクリプト

echo "🚀 AIMEE バックエンドを起動します..."

# 環境変数ファイルのチェック
if [ ! -f .env ]; then
    echo "⚠️  .envファイルが見つかりません。.env.exampleからコピーします..."
    cp .env.example .env
    echo "✅ .envファイルを作成しました。必要に応じて編集してください。"
fi

# 仮想環境のチェック
if [ ! -d "venv" ]; then
    echo "📦 仮想環境を作成します..."
    python3 -m venv venv
fi

# 仮想環境の有効化
echo "🔌 仮想環境を有効化します..."
source venv/bin/activate

# 依存関係のインストール
echo "📚 依存関係をインストールします..."
pip install -r requirements.txt

# サーバー起動
echo "🌐 FastAPIサーバーを起動します..."
echo "📍 API: http://localhost:8000"
echo "📖 ドキュメント: http://localhost:8000/docs"
echo ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000