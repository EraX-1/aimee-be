#!/usr/bin/env python3
"""
Llamaモデルのダウンロードスクリプト
M3 Mac用に最適化された量子化モデルをダウンロード
"""

import os
import requests
from tqdm import tqdm

def download_file(url, filename):
    """ファイルをダウンロードする関数"""
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    
    with open(filename, 'wb') as file:
        with tqdm(total=total_size, unit='B', unit_scale=True, desc=filename) as pbar:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
                pbar.update(len(chunk))

def main():
    models_dir = "models"
    
    # モデルの選択肢
    models = {
        "1": {
            "name": "Llama-2-7B-Chat-GGUF (Q4_K_M)",
            "url": "https://huggingface.co/TheBloke/Llama-2-7B-Chat-GGUF/resolve/main/llama-2-7b-chat.Q4_K_M.gguf",
            "size": "4.08GB",
            "description": "標準的な7Bモデル（推奨）"
        },
        "2": {
            "name": "Llama-2-7B-Chat-GGUF (Q3_K_S)",
            "url": "https://huggingface.co/TheBloke/Llama-2-7B-Chat-GGUF/resolve/main/llama-2-7b-chat.Q3_K_S.gguf",
            "size": "2.95GB",
            "description": "より軽量な7Bモデル（メモリ節約）"
        }
    }
    
    print("📥 Llamaモデルをダウンロードします")
    print("\n利用可能なモデル:")
    for key, model in models.items():
        print(f"{key}. {model['name']} ({model['size']}) - {model['description']}")
    
    choice = input("\nダウンロードするモデルを選択してください (1-2): ")
    
    if choice in models:
        model = models[choice]
        filename = os.path.basename(model['url'])
        filepath = os.path.join(models_dir, filename)
        
        print(f"\n📦 {model['name']}をダウンロード中...")
        print(f"保存先: {filepath}")
        
        try:
            download_file(model['url'], filepath)
            print(f"\n✅ ダウンロード完了！")
            print(f"モデルパス: {filepath}")
        except Exception as e:
            print(f"\n❌ エラーが発生しました: {e}")
    else:
        print("❌ 無効な選択です")

if __name__ == "__main__":
    main()