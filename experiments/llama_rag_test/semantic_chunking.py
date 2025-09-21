#!/usr/bin/env python3
"""
セマンティックチャンキング実装
意味的に関連するテキストをまとめて分割することで、RAGの精度を向上
"""

import numpy as np
from typing import List, Tuple
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
from nltk.tokenize import sent_tokenize
import re

class SemanticChunker:
    def __init__(self, model_name="intfloat/multilingual-e5-base", threshold=0.75):
        """
        セマンティックチャンカーの初期化
        
        Args:
            model_name: 文埋め込みモデル名
            threshold: 類似度の閾値（0.0-1.0）
        """
        self.model = SentenceTransformer(model_name)
        self.threshold = threshold
        
        # 日本語の文分割用
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt')
    
    def _split_sentences(self, text: str) -> List[str]:
        """テキストを文に分割（日本語対応）"""
        # 日本語の文末記号で分割
        japanese_pattern = r'[。！？\n]+'
        english_pattern = r'[.!?\n]+'
        
        # 日本語と英語の両方に対応
        sentences = re.split(f'{japanese_pattern}|{english_pattern}', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences
    
    def _calculate_similarity_matrix(self, sentences: List[str]) -> np.ndarray:
        """文間の類似度行列を計算"""
        embeddings = self.model.encode(sentences)
        similarity_matrix = cosine_similarity(embeddings)
        return similarity_matrix
    
    def _group_similar_sentences(self, sentences: List[str], similarity_matrix: np.ndarray) -> List[List[str]]:
        """類似度に基づいて文をグループ化"""
        n = len(sentences)
        groups = []
        used = set()
        
        for i in range(n):
            if i in used:
                continue
            
            # 新しいグループを開始
            group = [sentences[i]]
            used.add(i)
            
            # 後続の文で類似度が閾値を超えるものを追加
            for j in range(i + 1, min(i + 10, n)):  # 最大10文先まで見る
                if j not in used and similarity_matrix[i][j] >= self.threshold:
                    group.append(sentences[j])
                    used.add(j)
                elif similarity_matrix[i][j] < self.threshold * 0.7:  # 大きく異なる場合は打ち切り
                    break
            
            groups.append(group)
        
        return groups
    
    def chunk_text(self, text: str, max_chunk_size: int = 500, min_chunk_size: int = 100) -> List[str]:
        """
        セマンティックチャンキングを実行
        
        Args:
            text: 分割するテキスト
            max_chunk_size: チャンクの最大文字数
            min_chunk_size: チャンクの最小文字数
        
        Returns:
            チャンクのリスト
        """
        # 文に分割
        sentences = self._split_sentences(text)
        if not sentences:
            return []
        
        # 類似度行列を計算
        similarity_matrix = self._calculate_similarity_matrix(sentences)
        
        # 文をグループ化
        groups = self._group_similar_sentences(sentences, similarity_matrix)
        
        # チャンクを作成
        chunks = []
        current_chunk = []
        current_size = 0
        
        for group in groups:
            group_text = ' '.join(group)
            group_size = len(group_text)
            
            if current_size + group_size > max_chunk_size and current_chunk:
                # 現在のチャンクを保存
                chunk_text = ' '.join(current_chunk)
                if len(chunk_text) >= min_chunk_size:
                    chunks.append(chunk_text)
                current_chunk = [group_text]
                current_size = group_size
            else:
                current_chunk.append(group_text)
                current_size += group_size
        
        # 最後のチャンク
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            if len(chunk_text) >= min_chunk_size:
                chunks.append(chunk_text)
        
        return chunks

class HybridChunker:
    """セマンティックと構造的チャンキングのハイブリッド"""
    
    def __init__(self, semantic_chunker: SemanticChunker):
        self.semantic_chunker = semantic_chunker
    
    def chunk_with_overlap(self, text: str, overlap_size: int = 50) -> List[str]:
        """オーバーラップ付きチャンキング（コンテキスト保持）"""
        base_chunks = self.semantic_chunker.chunk_text(text)
        
        if len(base_chunks) <= 1:
            return base_chunks
        
        # 隣接チャンク間にオーバーラップを追加
        enhanced_chunks = []
        for i, chunk in enumerate(base_chunks):
            if i > 0:
                # 前のチャンクの末尾を追加
                prev_words = base_chunks[i-1].split()[-overlap_size//10:]
                chunk = ' '.join(prev_words) + ' ' + chunk
            
            if i < len(base_chunks) - 1:
                # 次のチャンクの先頭を追加
                next_words = base_chunks[i+1].split()[:overlap_size//10]
                chunk = chunk + ' ' + ' '.join(next_words)
            
            enhanced_chunks.append(chunk.strip())
        
        return enhanced_chunks
    
    def chunk_with_metadata(self, text: str, metadata: dict = None) -> List[Tuple[str, dict]]:
        """メタデータ付きチャンキング"""
        chunks = self.semantic_chunker.chunk_text(text)
        
        result = []
        for i, chunk in enumerate(chunks):
            chunk_metadata = metadata.copy() if metadata else {}
            chunk_metadata.update({
                'chunk_index': i,
                'total_chunks': len(chunks),
                'chunk_method': 'semantic'
            })
            result.append((chunk, chunk_metadata))
        
        return result

# 使用例
if __name__ == "__main__":
    # テストテキスト
    sample_text = """
    横浜拠点には現在80名の従業員が在籍しています。主にデータ入力業務を担当しており、24時間体制で稼働しています。
    最近の生産性は目標値の85%程度で推移しています。月曜日の朝は特に生産性が低下する傾向があります。
    
    盛岡拠点は30名体制で運営されています。補正処理業務に特化しており、熟練者が多く在籍しています。
    生産性は安定して目標値の110%を達成しており、他拠点のモデルケースとなっています。
    
    人員配置の最適化には、各従業員のスキルレベルと作業効率を考慮する必要があります。
    新人教育では、熟練者とのペア作業から始めることが効果的です。
    """
    
    # セマンティックチャンカーの初期化
    chunker = SemanticChunker(threshold=0.7)
    
    print("🔍 セマンティックチャンキング結果:")
    chunks = chunker.chunk_text(sample_text)
    for i, chunk in enumerate(chunks, 1):
        print(f"\nチャンク {i}:")
        print(chunk)
        print("-" * 50)
    
    # ハイブリッドチャンカーの使用
    hybrid = HybridChunker(chunker)
    
    print("\n\n🔄 オーバーラップ付きチャンキング:")
    overlap_chunks = hybrid.chunk_with_overlap(sample_text, overlap_size=30)
    for i, chunk in enumerate(overlap_chunks, 1):
        print(f"\nチャンク {i}:")
        print(chunk)
        print("-" * 50)