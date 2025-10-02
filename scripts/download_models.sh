#!/bin/bash

# LLMモデルのダウンロードスクリプト

echo "🚀 LLMモデルダウンロードを開始します..."

# Ollamaコンテナが起動しているか確認
echo "⏳ Ollamaコンテナの起動を確認中..."
docker-compose ps | grep ollama-light > /dev/null
if [ $? -ne 0 ]; then
    echo "❌ ollama-lightコンテナが起動していません"
    echo "💡 'make dev' でコンテナを起動してください"
    exit 1
fi

docker-compose ps | grep ollama-main > /dev/null
if [ $? -ne 0 ]; then
    echo "❌ ollama-mainコンテナが起動していません"
    echo "💡 'make dev' でコンテナを起動してください"
    exit 1
fi

# qwen2:0.5bのダウンロード
echo ""
echo "📥 軽量モデル qwen2:0.5b をダウンロード中..."
docker-compose exec -T ollama-light sh -c "ollama pull qwen2:0.5b"
if [ $? -eq 0 ]; then
    echo "✅ qwen2:0.5b のダウンロード完了"
else
    echo "❌ qwen2:0.5b のダウンロードに失敗しました"
    exit 1
fi

# gemma3:4b-instructのダウンロード
echo ""
echo "📥 メインモデル gemma3:4b-instruct をダウンロード中..."
echo "⚠️  このモデルは約12GBあります。時間がかかる場合があります..."
docker-compose exec -T ollama-main sh -c "ollama pull gemma3:4b-instruct"
if [ $? -eq 0 ]; then
    echo "✅ gemma3:4b-instruct のダウンロード完了"
else
    echo "❌ gemma3:4b-instruct のダウンロードに失敗しました"
    exit 1
fi

# モデル一覧を確認
echo ""
echo "📋 ダウンロードされたモデル一覧:"
echo ""
echo "ollama-light:"
docker-compose exec -T ollama-light sh -c "ollama list"
echo ""
echo "ollama-main:"
docker-compose exec -T ollama-main sh -c "ollama list"

echo ""
echo "🎉 全てのモデルのダウンロードが完了しました！"
echo ""
echo "💡 次のステップ:"
echo "   1. 'make test-api' でAPIの動作確認"
echo "   2. 'http://localhost:8000/docs' でAPI仕様を確認"