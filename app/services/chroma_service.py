"""
ChromaDB RAGサービス
オペレータ・工程データのセマンティック検索とチャンキングを提供
"""
import chromadb
from typing import List, Dict, Any, Optional
import os
from datetime import datetime

from app.core.logging import app_logger
from app.core.config import settings


class ChromaService:
    """ChromaDBとのインタラクションを管理するサービス（シングルトンパターン）"""

    _instance = None
    _client = None
    _collection = None

    def __new__(cls):
        """シングルトンパターン実装"""
        if cls._instance is None:
            cls._instance = super(ChromaService, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """ChromaDBクライアントを初期化（初回のみ）"""
        if ChromaService._client is None:
            self._initialize_client()

    def _initialize_client(self):
        """ChromaDBクライアントとコレクションを初期化"""
        try:
            # ChromaDBクライアント設定
            # Docker内ではコンテナ名、ローカル実行時はlocalhost
            chroma_host = settings.CHROMADB_HOST
            chroma_port = settings.CHROMADB_PORT  # コンテナ内ポート8000

            # .envで設定されたポートを優先使用
            app_logger.info(f"ChromaDB接続: {chroma_host}:{chroma_port}")

            ChromaService._client = chromadb.HttpClient(
                host=chroma_host,
                port=chroma_port
            )

            # コレクション取得または作成
            collection_name = os.getenv("CHROMADB_COLLECTION", "aimee_knowledge")
            try:
                ChromaService._collection = ChromaService._client.get_collection(name=collection_name)
                app_logger.info(f"既存のコレクション '{collection_name}' を取得しました")
            except:
                ChromaService._collection = ChromaService._client.create_collection(
                    name=collection_name,
                    metadata={"description": "AIMEE人員配置最適化のナレッジベース"}
                )
                app_logger.info(f"新しいコレクション '{collection_name}' を作成しました")

        except Exception as e:
            app_logger.error(f"ChromaDB初期化エラー: {e}")
            raise

    @property
    def client(self):
        """クライアントのプロパティアクセス"""
        return ChromaService._client

    @property
    def collection(self):
        """コレクションのプロパティアクセス"""
        return ChromaService._collection

    def create_operator_chunks(self, operator: Dict[str, Any], capabilities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        オペレータ情報をセマンティックチャンクに分割

        Args:
            operator: オペレータ基本情報
            capabilities: オペレータの処理可能工程リスト

        Returns:
            チャンクのリスト（各チャンクはdocument, metadata, idを含む）
        """
        chunks = []
        operator_id = operator.get("operator_id")
        operator_name = operator.get("operator_name", "不明")
        location_id = operator.get("location_id", "不明")

        # チャンク1: オペレータ基本情報
        basic_doc = f"""オペレータID: {operator_id}
名前: {operator_name}
所属拠点: {location_id}
有効: {"はい" if operator.get("is_valid") else "いいえ"}
所属コード: {operator.get("belong_code", "なし")}"""

        chunks.append({
            "id": f"operator_basic_{operator_id}",
            "document": basic_doc,
            "metadata": {
                "type": "operator_basic",
                "operator_id": operator_id,
                "operator_name": operator_name,
                "location_id": location_id,
                "timestamp": datetime.now().isoformat()
            }
        })

        # チャンク2〜N: 業務別の処理可能工程
        # 業務ごとにグループ化
        business_groups = {}
        for cap in capabilities:
            business_id = cap.get("business_id")
            if business_id not in business_groups:
                business_groups[business_id] = []
            business_groups[business_id].append(cap)

        for business_id, caps in business_groups.items():
            process_list = []
            for cap in caps:
                process_id = cap.get("process_id")
                work_level = cap.get("work_level", 0)
                process_list.append(f"工程{process_id}(レベル{work_level})")

            capability_doc = f"""オペレータ {operator_name} ({operator_id}) の処理能力:
業務ID: {business_id}
処理可能工程: {", ".join(process_list)}
拠点: {location_id}"""

            chunks.append({
                "id": f"operator_capability_{operator_id}_{business_id}",
                "document": capability_doc,
                "metadata": {
                    "type": "operator_capability",
                    "operator_id": operator_id,
                    "operator_name": operator_name,
                    "business_id": business_id,
                    "location_id": location_id,
                    "process_count": len(caps),
                    "timestamp": datetime.now().isoformat()
                }
            })

        return chunks

    def create_process_chunks(self, processes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        工程情報をセマンティックチャンクに分割

        Args:
            processes: 工程情報のリスト

        Returns:
            チャンクのリスト
        """
        chunks = []

        # 業務ごとにグループ化
        business_groups = {}
        for process in processes:
            business_id = process.get("business_id")
            if business_id not in business_groups:
                business_groups[business_id] = []
            business_groups[business_id].append(process)

        for business_id, procs in business_groups.items():
            # 業務全体のチャンク
            process_list = []
            for proc in procs:
                process_id = proc.get("process_id")
                process_name = proc.get("process_name", "")
                category = proc.get("process_category", "")
                process_list.append(f"{process_name}({process_id}, {category})")

            business_doc = f"""業務ID {business_id} の工程一覧:
工程数: {len(procs)}
工程詳細: {", ".join(process_list[:10])}{"..." if len(process_list) > 10 else ""}"""

            chunks.append({
                "id": f"process_business_{business_id}",
                "document": business_doc,
                "metadata": {
                    "type": "process_business",
                    "business_id": business_id,
                    "process_count": len(procs),
                    "timestamp": datetime.now().isoformat()
                }
            })

            # 個別工程のチャンク（詳細情報が必要な場合）
            for proc in procs:
                process_id = proc.get("process_id")
                level_id = proc.get("level_id")
                process_name = proc.get("process_name", "")
                process_detail = proc.get("process_name_detail", "")
                category = proc.get("process_category", "")

                proc_doc = f"""工程詳細:
業務ID: {business_id}
工程ID: {process_id}
レベル: {level_id}
工程名: {process_name}
詳細: {process_detail}
カテゴリ: {category}"""

                chunks.append({
                    "id": f"process_detail_{business_id}_{process_id}_{level_id}",
                    "document": proc_doc,
                    "metadata": {
                        "type": "process_detail",
                        "business_id": business_id,
                        "process_id": process_id,
                        "level_id": level_id,
                        "process_name": process_name,
                        "process_category": category,
                        "timestamp": datetime.now().isoformat()
                    }
                })

        return chunks

    def add_documents(self, chunks: List[Dict[str, Any]], batch_size: int = 5000):
        """
        チャンクをChromaDBに追加（バッチ処理対応）

        Args:
            chunks: ドキュメントチャンクのリスト
            batch_size: バッチサイズ（デフォルト5000、ChromaDBの制限5461以下）
        """
        if not chunks:
            app_logger.warning("追加するチャンクがありません")
            return

        try:
            total_chunks = len(chunks)
            app_logger.info(f"合計{total_chunks}件のドキュメントをバッチ処理で投入します（バッチサイズ: {batch_size}）")

            # バッチ処理
            for i in range(0, total_chunks, batch_size):
                batch = chunks[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (total_chunks + batch_size - 1) // batch_size

                ids = [chunk["id"] for chunk in batch]
                documents = [chunk["document"] for chunk in batch]
                metadatas = [chunk["metadata"] for chunk in batch]

                self.collection.add(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas
                )

                app_logger.info(f"バッチ {batch_num}/{total_batches} 完了: {len(batch)}件投入 (累計: {min(i + batch_size, total_chunks)}/{total_chunks})")

            app_logger.info(f"✅ 全{total_chunks}件のドキュメントをChromaDBに追加しました")

        except Exception as e:
            app_logger.error(f"ChromaDBへのドキュメント追加エラー: {e}")
            raise

    def query_similar(
        self,
        query_text: str,
        n_results: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        類似ドキュメントを検索

        Args:
            query_text: クエリテキスト
            n_results: 取得する結果数
            filter_metadata: メタデータフィルタ

        Returns:
            検索結果
        """
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where=filter_metadata
            )

            app_logger.info(f"クエリ '{query_text[:50]}...' で {len(results['ids'][0])} 件の結果を取得")

            return {
                "documents": results["documents"][0],
                "metadatas": results["metadatas"][0],
                "distances": results["distances"][0],
                "ids": results["ids"][0]
            }

        except Exception as e:
            app_logger.error(f"ChromaDB検索エラー: {e}")
            raise

    def find_best_operators_for_process(
        self,
        business_id: str,
        process_id: str,
        location_id: Optional[str] = None,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        特定工程に最適なオペレータを検索

        Args:
            business_id: 業務ID
            process_id: 工程ID
            location_id: 拠点ID（オプション）
            n_results: 取得する結果数

        Returns:
            最適なオペレータのリスト
        """
        query_text = f"業務{business_id}の工程{process_id}を処理できるオペレータ"

        # ChromaDB v1.1+ では$and演算子を使用
        if location_id:
            filter_dict = {
                "$and": [
                    {"type": {"$eq": "operator_capability"}},
                    {"business_id": {"$eq": business_id}},
                    {"location_id": {"$eq": location_id}}
                ]
            }
        else:
            filter_dict = {
                "$and": [
                    {"type": {"$eq": "operator_capability"}},
                    {"business_id": {"$eq": business_id}}
                ]
            }

        results = self.query_similar(
            query_text=query_text,
            n_results=n_results,
            filter_metadata=filter_dict
        )

        operators = []
        for i, metadata in enumerate(results["metadatas"]):
            operators.append({
                "operator_id": metadata.get("operator_id"),
                "operator_name": metadata.get("operator_name"),
                "location_id": metadata.get("location_id"),
                "distance": results["distances"][i],
                "relevance_score": 1 - results["distances"][i]  # 距離を関連性スコアに変換
            })

        return operators

    def search_manager_rules(
        self,
        query_text: str,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        管理者ノウハウ・判断基準を検索

        Args:
            query_text: 検索クエリ
            n_results: 取得する結果数

        Returns:
            関連する管理者ルールのリスト
        """
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results
            )

            rules = []
            for i, (doc, metadata) in enumerate(zip(results["documents"][0], results["metadatas"][0])):
                rules.append({
                    "rule_text": doc,
                    "category": metadata.get("category", "general"),
                    "title": metadata.get("title", ""),
                    "relevance_score": 1 - results["distances"][0][i] if "distances" in results else 0.5
                })

            app_logger.info(f"管理者ルール検索: '{query_text[:30]}...' で {len(rules)}件取得")
            return rules

        except Exception as e:
            app_logger.error(f"管理者ルール検索エラー: {e}")
            return []

    def get_collection_stats(self) -> Dict[str, Any]:
        """コレクションの統計情報を取得"""
        try:
            count = self.collection.count()
            return {
                "total_documents": count,
                "collection_name": self.collection.name
            }
        except Exception as e:
            app_logger.error(f"統計情報取得エラー: {e}")
            return {"error": str(e)}
