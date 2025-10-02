#!/bin/bash
# 開発環境でAPIをローカル実行するスクリプト

echo "🚀 AIMEE Backend APIを開発モードで起動します..."

# 環境変数の設定（ローカル実行用）
export DATABASE_URL="mysql+pymysql://aimee_user:Aimee2024!@localhost:3306/aimee_db"
export REDIS_URL="redis://localhost:6379/0"
export OLLAMA_LIGHT_HOST="localhost"
export OLLAMA_LIGHT_PORT="11433"
export OLLAMA_MAIN_HOST="localhost"
export OLLAMA_MAIN_PORT="11434"
export CHROMADB_HOST="localhost"
export CHROMADB_PORT="8001"

# .envファイルから他の設定を読み込む
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | grep -v '^$' | xargs)
fi

echo "📋 環境設定:"
echo "  - Database: $DATABASE_URL"
echo "  - Redis: $REDIS_URL"
echo "  - Ollama Light: http://$OLLAMA_LIGHT_HOST:$OLLAMA_LIGHT_PORT"
echo "  - Ollama Main: http://$OLLAMA_MAIN_HOST:$OLLAMA_MAIN_PORT"
echo "  - ChromaDB: http://$CHROMADB_HOST:$CHROMADB_PORT"

# Pythonパスの設定
export PYTHONPATH=/Users/umemiya/Desktop/erax/aimee-be:$PYTHONPATH

# APIサーバーの起動
echo ""
echo "🌐 APIサーバーを起動します..."
echo "   URL: http://localhost:8000"
echo "   Docs: http://localhost:8000/docs"
echo ""

# uvicornでAPIを起動
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000