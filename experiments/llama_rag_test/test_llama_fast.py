#!/usr/bin/env python3
"""
Llama高速動作テスト版
回答時間を最適化した設定
"""

import time
from llama_cpp import Llama
import hashlib
from functools import lru_cache

# グローバルでモデルを初期化（起動時間短縮）
print("🚀 高速版Llamaモデルをロード中...")
llm = Llama(
    model_path="./models/llama-2-7b-chat.Q4_K_M.gguf",  # Q3_K_Sがあればそちらを使用
    n_ctx=1024,         # コンテキスト長を短縮
    n_batch=256,        # バッチサイズ調整
    n_threads=8,        # M3のコア数に最適化
    n_gpu_layers=32,    # Metal GPU最大活用
    use_mlock=False,
    use_mmap=True,      # メモリマップで高速化
    verbose=False,      # ログ出力を抑制
)

@lru_cache(maxsize=100)
def cached_response(prompt_hash, max_tokens=100):
    """キャッシュ付き応答生成"""
    return llm(prompt_hash, max_tokens=max_tokens)

def test_speed_optimization():
    """速度最適化のテスト"""
    print("\n⚡ 速度最適化テスト")
    
    # テスト1: 短い応答
    print("\n📝 テスト1: 短い応答（max_tokens=50）")
    prompt = "What is 2+2? Answer in one sentence."
    
    start_time = time.time()
    response = llm(prompt, max_tokens=50, temperature=0.1)
    end_time = time.time()
    
    print(f"質問: {prompt}")
    print(f"回答: {response['choices'][0]['text'].strip()}")
    print(f"⏱️ 生成時間: {end_time - start_time:.2f}秒")
    
    # テスト2: ストリーミング応答
    print("\n📝 テスト2: ストリーミング応答")
    prompt = "List 3 benefits of exercise:"
    
    print(f"質問: {prompt}")
    print("回答: ", end='')
    
    start_time = time.time()
    for token in llm(prompt, max_tokens=100, stream=True, temperature=0.5):
        print(token['choices'][0]['text'], end='', flush=True)
    end_time = time.time()
    
    print(f"\n⏱️ 生成時間: {end_time - start_time:.2f}秒")

def test_batch_processing():
    """バッチ処理のテスト"""
    print("\n📦 バッチ処理テスト")
    
    questions = [
        "横浜拠点の状況は？",
        "生産性を上げる方法は？",
        "月曜の注意点は？"
    ]
    
    # Llama-2のバッチプロンプト形式
    batch_prompt = f"""<s>[INST] <<SYS>>
簡潔に回答してください。各質問に1-2文で答えてください。
<</SYS>>

質問1: {questions[0]}
質問2: {questions[1]}
質問3: {questions[2]}

回答: [/INST]"""
    
    start_time = time.time()
    response = llm(batch_prompt, max_tokens=200, temperature=0.3)
    end_time = time.time()
    
    print("バッチ回答:")
    print(response['choices'][0]['text'])
    print(f"\n⏱️ 3つの質問の総生成時間: {end_time - start_time:.2f}秒")
    print(f"📊 1質問あたり: {(end_time - start_time) / 3:.2f}秒")

def test_cache_performance():
    """キャッシュ性能のテスト"""
    print("\n💾 キャッシュ性能テスト")
    
    prompt = "What are the benefits of using AI in workforce management?"
    
    # 初回実行
    start_time = time.time()
    response1 = llm(prompt, max_tokens=100)
    first_time = time.time() - start_time
    
    # 2回目実行（キャッシュなし）
    start_time = time.time()
    response2 = llm(prompt, max_tokens=100)
    second_time = time.time() - start_time
    
    print(f"⏱️ 初回実行: {first_time:.2f}秒")
    print(f"⏱️ 2回目実行: {second_time:.2f}秒")
    print(f"📈 速度向上: {((first_time - second_time) / first_time * 100):.1f}%")

def print_optimization_tips():
    """最適化のヒント"""
    print("\n💡 更なる高速化のヒント:")
    print("1. より小さいモデル（Q3_K_S）を使用")
    print("2. n_ctx（コンテキスト長）を必要最小限に")
    print("3. max_tokensを適切に制限")
    print("4. temperatureを低く設定（0.1-0.3）")
    print("5. Metal GPUレイヤーを最大化")
    print("6. プロンプトを簡潔に")
    print("7. 頻繁な質問はキャッシュ")

if __name__ == "__main__":
    print("🚀 Llama高速動作テストを開始します...\n")
    
    try:
        test_speed_optimization()
        test_batch_processing()
        test_cache_performance()
        print_optimization_tips()
        
        print("\n✅ すべてのテストが完了しました！")
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")