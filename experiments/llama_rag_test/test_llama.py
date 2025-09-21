#!/usr/bin/env python3
"""
Llamaの基本動作テスト
M3 Macでの動作確認用
"""

import time
from llama_cpp import Llama

def test_basic_generation():
    """基本的なテキスト生成テスト"""
    print("🤖 Llamaモデルをロード中...")
    
    # M3 Mac用の設定
    llm = Llama(
        model_path="./models/llama-2-7b-chat.Q4_K_M.gguf",
        n_ctx=2048,        # コンテキスト長
        n_threads=8,       # M3のコア数に合わせて
        n_gpu_layers=1,    # Metal GPU使用
        use_mlock=False,   # メモリスワップ許可
    )
    
    print("✅ モデルのロード完了！\n")
    
    # テスト1: シンプルな質問
    print("📝 テスト1: シンプルな質問")
    start_time = time.time()
    
    prompt = "What is the capital of Japan?"
    response = llm(prompt, max_tokens=50)
    
    print(f"質問: {prompt}")
    print(f"回答: {response['choices'][0]['text']}")
    print(f"生成時間: {time.time() - start_time:.2f}秒\n")
    
    # テスト2: 日本語対応確認
    print("📝 テスト2: 日本語での質問")
    start_time = time.time()
    
    prompt = "人工知能の利点を3つ教えてください。"
    response = llm(prompt, max_tokens=200)
    
    print(f"質問: {prompt}")
    print(f"回答: {response['choices'][0]['text']}")
    print(f"生成時間: {time.time() - start_time:.2f}秒\n")

def test_chat_format():
    """チャット形式のテスト"""
    print("💬 チャット形式のテスト")
    
    llm = Llama(
        model_path="./models/llama-2-7b-chat.Q4_K_M.gguf",
        n_ctx=2048,
        n_threads=8,
        n_gpu_layers=1,
    )
    
    # Llama-2のチャットテンプレート
    system_prompt = "You are a helpful assistant for workforce management."
    user_message = "横浜拠点の生産性が低下しています。どう対応すべきですか？"
    
    prompt = f"""<s>[INST] <<SYS>>
{system_prompt}
<</SYS>>

{user_message} [/INST]"""
    
    start_time = time.time()
    response = llm(prompt, max_tokens=300)
    
    print(f"システムプロンプト: {system_prompt}")
    print(f"ユーザー: {user_message}")
    print(f"アシスタント: {response['choices'][0]['text']}")
    print(f"生成時間: {time.time() - start_time:.2f}秒\n")

def check_memory_usage():
    """メモリ使用量の確認"""
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    
    print(f"📊 メモリ使用状況:")
    print(f"  - RSS: {memory_info.rss / 1024 / 1024 / 1024:.2f} GB")
    print(f"  - VMS: {memory_info.vms / 1024 / 1024 / 1024:.2f} GB")

if __name__ == "__main__":
    print("🚀 Llama動作テストを開始します...\n")
    
    try:
        test_basic_generation()
        test_chat_format()
        check_memory_usage()
        
        print("\n✅ すべてのテストが完了しました！")
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        print("モデルファイルが存在することを確認してください。")