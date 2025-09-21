#!/usr/bin/env python3
"""
Llamaモデルの自動ダウンロードスクリプト
M3 Mac用に最適化された量子化モデルを自動でダウンロード
"""

import os
import sys
import requests
from pathlib import Path

def download_file(url, filename):
    """ファイルをダウンロードする関数（プログレスバー付き）"""
    print(f"📥 ダウンロード開始: {filename}")
    
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    
    downloaded = 0
    chunk_size = 8192
    
    with open(filename, 'wb') as file:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                file.write(chunk)
                downloaded += len(chunk)
                
                # 簡易プログレス表示
                if total_size > 0:
                    progress = (downloaded / total_size) * 100
                    print(f"\r進行状況: {progress:.1f}% ({downloaded / 1024 / 1024:.1f}MB / {total_size / 1024 / 1024:.1f}MB)", end='', flush=True)
    
    print()  # 改行

def main():
    # コマンドライン引数でモデル選択（デフォルトは1）
    model_choice = sys.argv[1] if len(sys.argv) > 1 else "1"
    
    models_dir = Path("models")
    models_dir.mkdir(exist_ok=True)
    
    # モデルの定義
    models = {
        "1": {
            "name": "Llama-2-7B-Chat-GGUF (Q4_K_M)",
            "url": "https://huggingface.co/TheBloke/Llama-2-7B-Chat-GGUF/resolve/main/llama-2-7b-chat.Q4_K_M.gguf",
            "filename": "llama-2-7b-chat.Q4_K_M.gguf",
            "size": "4.08GB",
            "description": "標準的な7Bモデル（推奨）"
        },
        "2": {
            "name": "Llama-2-7B-Chat-GGUF (Q3_K_S)",
            "url": "https://huggingface.co/TheBloke/Llama-2-7B-Chat-GGUF/resolve/main/llama-2-7b-chat.Q3_K_S.gguf",
            "filename": "llama-2-7b-chat.Q3_K_S.gguf",
            "size": "2.95GB",
            "description": "より軽量な7Bモデル（メモリ節約）"
        }
    }
    
    if model_choice not in models:
        print(f"❌ 無効な選択: {model_choice}")
        print("使用方法: python download_model_auto.py [1|2]")
        return
    
    model = models[model_choice]
    filepath = models_dir / model['filename']
    
    # 既にダウンロード済みかチェック
    if filepath.exists():
        print(f"✅ {model['name']} は既にダウンロード済みです")
        print(f"📍 パス: {filepath}")
        return
    
    print(f"\n📦 {model['name']} ({model['size']}) をダウンロードします")
    print(f"📝 説明: {model['description']}")
    print(f"📍 保存先: {filepath}\n")
    
    try:
        download_file(model['url'], str(filepath))
        print(f"\n✅ ダウンロード完了！")
        print(f"📍 モデルパス: {filepath}")
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        # ダウンロード失敗時は部分ファイルを削除
        if filepath.exists():
            filepath.unlink()

if __name__ == "__main__":
    main()