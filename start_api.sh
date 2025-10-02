#!/bin/bash

echo "🧹 ポート8000をクリーンアップ中..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

echo "🚀 APIサーバーを起動します..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload