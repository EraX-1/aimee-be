#!/bin/bash

# 仮想環境のアクティベーションスクリプト

if [ ! -d "venv" ]; then
    echo "❌ 仮想環境が見つかりません。"
    echo "💡 先に './setup.sh' を実行してください。"
    exit 1
fi

echo "🔄 仮想環境を有効化します..."
source venv/bin/activate

echo "✅ 仮想環境が有効化されました！"
echo ""
echo "📍 現在の環境: $(which python)"
echo "🐍 Pythonバージョン: $(python --version)"
echo ""
echo "🎯 次のコマンドが使用可能です:"
echo "  python download_model_auto.py 1  # モデルダウンロード（標準版）"
echo "  python download_model_auto.py 2  # モデルダウンロード（軽量版）"
echo "  python test_llama.py             # Llama動作テスト"
echo "  python test_rag.py               # RAGテスト"
echo "  python test_batch_integration.py # 統合テスト"