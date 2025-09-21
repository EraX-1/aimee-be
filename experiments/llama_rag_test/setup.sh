#!/bin/bash

echo "🚀 Llama RAG実験環境のセットアップを開始します..."

# 仮想環境の作成
echo "📦 仮想環境を作成中..."
python3 -m venv venv

# 仮想環境の有効化
echo "🔄 仮想環境を有効化中..."
source venv/bin/activate

# pip、setuptools、wheelのアップグレード
echo "⬆️ pip、setuptools、wheelをアップグレード中..."
pip install --upgrade pip setuptools wheel

# 依存関係のインストール（M3 Mac用のMetal対応）
echo "📥 依存関係をインストール中..."

# llama-cpp-pythonを個別にインストール（Metal対応）
echo "🦙 llama-cpp-pythonをインストール中（Metal GPU対応）..."
CMAKE_ARGS="-DLLAMA_METAL=on" pip install llama-cpp-python

# その他の依存関係をインストール
echo "📚 その他のパッケージをインストール中..."
pip install langchain langchain-community chromadb sentence-transformers
pip install python-dotenv pandas numpy tqdm psutil

# モデル保存用ディレクトリの作成
echo "📁 モデル用ディレクトリを作成中..."
mkdir -p models

echo ""
echo "✅ セットアップ完了！"
echo ""
echo "🎯 次のステップ:"
echo "1. source venv/bin/activate  # 仮想環境を有効化"
echo "2. python download_model.py  # モデルをダウンロード"
echo "3. python test_llama.py      # Llamaの動作テスト"
echo "4. python test_rag.py        # RAGの動作テスト"
echo "5. python test_batch_integration.py  # バッチ統合テスト"