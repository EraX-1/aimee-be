#!/usr/bin/env python3
"""
Llama日本語専用テスト
必ず日本語で回答するための設定
"""

import time
from llama_cpp import Llama

def create_japanese_llm():
    """日本語特化のLlamaモデルを作成"""
    print("🇯🇵 日本語対応Llamaモデルをロード中...")
    
    llm = Llama(
        model_path="./models/llama-2-7b-chat.Q4_K_M.gguf",
        n_ctx=2048,
        n_threads=8,
        n_gpu_layers=1,
    )
    
    print("✅ モデルのロード完了！\n")
    return llm

def japanese_prompt(user_message, system_message=None):
    """日本語回答を強制するプロンプトテンプレート"""
    
    if system_message is None:
        system_message = """あなたは日本語で回答するAIアシスタントです。
以下の重要なルールを必ず守ってください：
1. 必ず日本語で回答してください
2. 英語や他の言語は使わないでください
3. 専門用語も可能な限り日本語にしてください
4. ユーザーが英語で質問しても、日本語で答えてください"""
    
    prompt = f"""<s>[INST] <<SYS>>
{system_message}
<</SYS>>

{user_message} [/INST]

回答（日本語で）："""
    
    return prompt

def test_japanese_responses():
    """日本語回答のテスト"""
    llm = create_japanese_llm()
    
    test_cases = [
        # 英語の質問に日本語で答える
        {
            "question": "What is AI?",
            "expected": "日本語での回答"
        },
        # 日本語の質問
        {
            "question": "人工知能の利点を3つ教えてください。",
            "expected": "日本語での回答"
        },
        # 業務関連の質問
        {
            "question": "How can we improve productivity in Yokohama office?",
            "expected": "日本語での回答"
        },
        # 混在した質問
        {
            "question": "Llama modelの使い方を説明して",
            "expected": "日本語での回答"
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"📝 テスト{i}: {test['question']}")
        
        # 日本語プロンプトでラップ
        prompt = japanese_prompt(test['question'])
        
        start_time = time.time()
        response = llm(prompt, max_tokens=200, temperature=0.7)
        answer = response['choices'][0]['text'].strip()
        
        print(f"💬 回答: {answer}")
        print(f"⏱️ 生成時間: {time.time() - start_time:.2f}秒")
        print("-" * 50)

def test_business_japanese():
    """ビジネス用途の日本語テスト"""
    llm = create_japanese_llm()
    
    print("\n🏢 ビジネスシナリオテスト")
    
    # ビジネス特化のシステムプロンプト
    business_system = """あなたは日本企業の労働力管理を支援するAIアシスタントです。
必ず以下のルールに従ってください：
1. 回答は必ず日本語で行う
2. 敬語を適切に使用する
3. ビジネス用語は日本語で表現する
4. 数値は全角ではなく半角を使用する
5. 簡潔で分かりやすい日本語を心がける"""
    
    questions = [
        "What is the current productivity rate?",
        "横浜拠点の人員配置を最適化する方法を提案してください",
        "Monday morningの生産性が低い理由と対策を教えて",
    ]
    
    for question in questions:
        print(f"\n❓ 質問: {question}")
        
        prompt = japanese_prompt(question, business_system)
        response = llm(prompt, max_tokens=300, temperature=0.5)
        answer = response['choices'][0]['text'].strip()
        
        print(f"📊 回答: {answer}")

def test_rag_japanese():
    """RAG使用時の日本語回答テスト"""
    llm = create_japanese_llm()
    
    print("\n📚 RAG + 日本語回答テスト")
    
    # RAG用のコンテキスト（英語混在）
    context = """
    横浜拠点: 80名在籍, productivity 85%
    盛岡拠点: 30名在籍, productivity 110%
    Main issues: High absence rate on Monday morning
    Recommendation: Skill matching and workload balancing needed
    """
    
    question = "各拠点の状況と改善策を教えてください"
    
    # RAG対応プロンプト
    rag_prompt = f"""<s>[INST] <<SYS>>
あなたは日本語で回答するAIアシスタントです。
提供されたコンテキストを参考に、必ず日本語で回答してください。
英語の情報も日本語に翻訳して説明してください。
<</SYS>>

コンテキスト:
{context}

質問: {question}

日本語で回答: [/INST]"""
    
    print(f"📄 コンテキスト（英語混在）:\n{context}")
    print(f"\n❓ 質問: {question}")
    
    response = llm(rag_prompt, max_tokens=400, temperature=0.3)
    answer = response['choices'][0]['text'].strip()
    
    print(f"\n💡 回答: {answer}")

def create_japanese_enforcer_wrapper(llm):
    """日本語を強制するラッパー関数"""
    def japanese_only_llm(user_input, **kwargs):
        # 自動的に日本語プロンプトでラップ
        prompt = japanese_prompt(user_input)
        return llm(prompt, **kwargs)
    
    return japanese_only_llm

if __name__ == "__main__":
    print("🇯🇵 日本語専用Llamaテストを開始します...\n")
    
    try:
        test_japanese_responses()
        test_business_japanese()
        test_rag_japanese()
        
        print("\n✅ すべてのテストが完了しました！")
        print("\n💡 ヒント:")
        print("- システムプロンプトで「必ず日本語で」と明記")
        print("- 英語の質問にも日本語で回答するよう指示")
        print("- プロンプトの最後に「日本語で回答：」を追加")
        
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")