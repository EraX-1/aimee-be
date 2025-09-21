#!/usr/bin/env python3
"""
RAG（Retrieval-Augmented Generation）のテスト
DBのサンプルデータを使用してRAGの動作を確認
"""

from llama_cpp import Llama
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
import time

class SimpleRAG:
    def __init__(self, model_path):
        print("🚀 RAGシステムを初期化中...")
        
        # Llamaモデルの初期化
        self.llm = Llama(
            model_path=model_path,
            n_ctx=2048,
            n_threads=8,
            n_gpu_layers=1,
        )
        
        # 埋め込みモデル（日本語対応）
        self.embeddings = HuggingFaceEmbeddings(
            model_name="intfloat/multilingual-e5-small",
            model_kwargs={'device': 'cpu'}
        )
        
        print("✅ 初期化完了！\n")
    
    def create_knowledge_base(self, documents):
        """ナレッジベースを作成"""
        print("📚 ナレッジベースを構築中...")
        
        # テキストを小さなチャンクに分割
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50
        )
        
        texts = []
        for doc in documents:
            chunks = text_splitter.split_text(doc)
            texts.extend(chunks)
        
        # ベクトルストアを作成
        self.vectorstore = FAISS.from_texts(texts, self.embeddings)
        print(f"✅ {len(texts)}個のチャンクからナレッジベース構築完了！\n")
    
    def query(self, question, k=3):
        """質問に対してRAGで回答"""
        print(f"🔍 質問: {question}")
        
        # 関連する文書を検索
        start_time = time.time()
        relevant_docs = self.vectorstore.similarity_search(question, k=k)
        search_time = time.time() - start_time
        
        print(f"📄 {len(relevant_docs)}件の関連文書を検索 ({search_time:.2f}秒)")
        
        # コンテキストを作成
        context = "\n\n".join([doc.page_content for doc in relevant_docs])
        
        # プロンプトを構築（日本語回答を強制）
        prompt = f"""<s>[INST] <<SYS>>
あなたは労働力管理システムのアシスタントです。
以下のコンテキストを使用して質問に答えてください。
重要：必ず日本語で回答してください。英語は使用しないでください。
<</SYS>>

コンテキスト:
{context}

質問: {question}

日本語での回答: [/INST]"""
        
        # Llamaで回答生成
        start_time = time.time()
        response = self.llm(prompt, max_tokens=300, stop=["</s>"])
        generation_time = time.time() - start_time
        
        answer = response['choices'][0]['text'].strip()
        
        print(f"\n💡 回答: {answer}")
        print(f"⏱️ 生成時間: {generation_time:.2f}秒\n")
        
        return answer

def main():
    # サンプルデータ（実際のDBデータを想定）
    sample_documents = [
        # 拠点情報
        "札幌拠点には現在50名の従業員が在籍しており、データ入力工程と品質チェック工程を担当しています。",
        "盛岡拠点は30名体制で、主に補正処理工程を担当しています。熟練者が多く生産性が高い拠点です。",
        "横浜拠点は最大規模で80名が在籍。全工程に対応可能ですが、最近は欠勤率が上昇傾向にあります。",
        "京都拠点は40名体制で、品質チェックと最終確認工程を専門的に行っています。",
        
        # 生産性データ
        "2024年1月の横浜拠点の生産性は目標値の85%でした。主な原因は熟練者の退職による影響です。",
        "盛岡拠点の生産性は安定して目標値の110%を維持しています。チームワークが良好です。",
        
        # 管理ノウハウ（RAGコンテキスト）
        "月曜日の朝は全体的に生産性が低下する傾向があります。重要な作業は火曜日以降に配置することを推奨します。",
        "田中さん（従業員ID: E001）は月曜朝の調子が特に悪いため、午後からの配置が望ましいです。",
        "繁忙期には拠点間での応援体制を組むことが効果的です。特に盛岡-横浜間の連携実績が良好です。",
        "新人教育は熟練者とのペア作業から開始し、段階的に独立作業に移行することで定着率が向上します。",
    ]
    
    # RAGシステムの初期化
    rag = SimpleRAG("./models/llama-2-7b-chat.Q4_K_M.gguf")
    
    # ナレッジベースの作成
    rag.create_knowledge_base(sample_documents)
    
    # テスト質問
    test_questions = [
        "横浜拠点の現在の状況を教えてください",
        "生産性を向上させるための対策を提案してください",
        "月曜日の人員配置で注意すべき点は何ですか？",
        "拠点間の連携について教えてください",
    ]
    
    print("=" * 50)
    print("📋 RAGテストを開始します")
    print("=" * 50)
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n【テスト {i}】")
        rag.query(question)
        print("-" * 50)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        print("必要なモデルファイルが存在することを確認してください。")