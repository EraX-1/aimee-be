# Llama RAG 実験環境

このディレクトリは、LlamaとRAGの動作検証用の実験環境です。

## 目的
- ローカルLLM（Llama）の動作確認
- RAG（Retrieval-Augmented Generation）の実装テスト
- バッチ2,3との連携方法の検証

## セットアップ手順

### 1. 環境構築
```bash
# 実験ディレクトリに移動
cd experiments/llama_rag_test

# セットアップスクリプトを実行
./setup.sh

# 仮想環境を有効化
source venv/bin/activate
```

### 2. モデルのダウンロード

**重要**: 必ず仮想環境を有効化してから実行してください！

```bash
# 仮想環境が有効化されていることを確認
# (venv) が表示されていればOK

# 対話式でダウンロード
python download_model.py

# または自動でダウンロード（推奨）
python download_model_auto.py 1  # 標準版（4GB）
python download_model_auto.py 2  # 軽量版（3GB）
```

## 実験ファイルの使い方

### 1. test_llama.py - Llama基本動作テスト
```bash
python test_llama.py           # 通常版
python test_llama_fast.py      # 高速版（推奨）
```
**テスト内容**:
- シンプルな質問応答
- 日本語対応の確認
- チャット形式での対話
- メモリ使用量の確認
- **高速版**: ストリーミング、バッチ処理、キャッシュ性能テスト

### 2. test_rag.py - RAG機能テスト
```bash
python test_rag.py
```
**テスト内容**:
- サンプルデータからナレッジベース構築
- 質問に対する関連文書の検索
- コンテキストを使った回答生成
- 拠点情報・生産性データを使った実践的なテスト

### 3. test_batch_integration.py - バッチ統合テスト
```bash
python test_batch_integration.py
```
**テスト内容**:
- バッチ2（数値分析AI）のシミュレーション
- バッチ3（ノウハウ最適化AI）のシミュレーション
- Llamaによる統合的な判断と回答生成
- 実際の業務シナリオでのテスト

## ファイル構成

```
llama_rag_test/
├── README.md                    # このファイル
├── requirements.txt             # Python依存パッケージ
├── setup.sh                     # セットアップスクリプト
├── download_model.py            # モデルダウンロード用
├── test_llama.py               # Llama動作テスト
├── test_rag.py                 # RAGテスト
├── test_batch_integration.py   # バッチ統合テスト
├── .gitignore                  # Git除外設定
├── models/                     # ダウンロードしたモデル（作成される）
└── venv/                       # Python仮想環境（作成される）
```

## トラブルシューティング

### メモリ不足エラーの場合
- `download_model.py`で軽量版（Q3_K_S）を選択
- test_llama.pyの`n_ctx`パラメータを1024に減らす

### M3 Mac特有の設定
- Metal GPUが自動的に使用されます
- `CMAKE_ARGS="-DLLAMA_METAL=on"`でビルドされます

### モデルが見つからないエラー
- `models/`ディレクトリにモデルファイルが存在するか確認
- `download_model.py`を再実行

## 次のステップ

実験が成功したら：
1. 本番用のコードを`app/`ディレクトリに実装
2. FastAPIエンドポイントとして統合
3. aimee-dbとの連携実装

## 注意
- このディレクトリ内のコードは実験用です
- 本番コードはapp/ディレクトリに実装します