# AIMEE Backend API

AI配置最適化システムのバックエンドAPI（FastAPI）

## アーキテクチャ概要

クリーンアーキテクチャに基づいた3層構造：

```
aimee-be/
├── app/                      # アプリケーション本体
│   ├── api/                  # API層（プレゼンテーション層）
│   │   ├── v1/              # APIバージョン1
│   │   │   ├── endpoints/   # エンドポイント定義
│   │   │   │   ├── alerts.py
│   │   │   │   ├── assignments.py
│   │   │   │   ├── chat.py
│   │   │   │   └── ...
│   │   │   ├── dependencies/  # 依存性注入
│   │   │   └── routers.py    # ルーター集約
│   │   └── middlewares/      # ミドルウェア
│   ├── core/                 # コア設定
│   │   ├── config.py        # 環境設定
│   │   ├── security.py      # セキュリティ設定
│   │   └── logging.py       # ログ設定
│   ├── domain/              # ドメイン層（ビジネスロジック）
│   │   ├── models/          # ドメインモデル
│   │   ├── services/        # ドメインサービス
│   │   └── repositories/    # リポジトリインターフェース
│   ├── infrastructure/      # インフラ層（外部連携）
│   │   ├── database/        # DB接続・モデル
│   │   ├── repositories/   # リポジトリ実装
│   │   └── external/        # 外部API連携
│   ├── schemas/             # Pydanticスキーマ
│   │   ├── requests/        # リクエストスキーマ
│   │   └── responses/       # レスポンススキーマ
│   └── main.py             # アプリケーションエントリーポイント
├── tests/                   # テスト
├── scripts/                 # スクリプト
├── .env.example            # 環境変数サンプル
├── requirements.txt        # 依存パッケージ
└── docker-compose.yml      # Docker設定
```

## 設計原則

1. **レイヤー分離**
   - API層：HTTPリクエスト/レスポンスの処理
   - ドメイン層：ビジネスロジックの実装
   - インフラ層：外部リソースへのアクセス

2. **依存性の方向**
   - API層 → ドメイン層 → インフラ層
   - 依存性注入によるテスタビリティの確保

3. **拡張性**
   - APIバージョニング対応
   - モジュラーな構造で機能追加が容易

4. **型安全性**
   - Pydanticによる厳密な型定義
   - OpenAPI仕様の自動生成

## 次世代アーキテクチャ：ローカルRAG統合システム

### システム全体像

```mermaid
graph TB
    User[👤 ユーザー] --> API[🌐 FastAPI :8000]
    
    subgraph "AIMEE統合RAGシステム"
        API --> RAGEngine[🧠 統合RAGエンジン]
        
        subgraph "ローカルLLM基盤"
            RAGEngine --> Ollama[🤖 Ollama :11434]
            Ollama --> Models[📦 日本語LLM<br/>gemma3:4b-ja<br/>llama3.2:3b-ja]
        end
        
        subgraph "統合ナレッジベース"
            RAGEngine --> ChromaDB[🗄️ ChromaDB :8001]
            ChromaDB --> KB1[📊 数値実績ナレッジ<br/>過去の生産性データ・予測パターン]
            ChromaDB --> KB2[🧩 配置ノウハウナレッジ<br/>成功事例・失敗パターン・ベストプラクティス]
            ChromaDB --> KB3[📋 従業員ナレッジ<br/>個人特性・スキル・勤務パターン]
            ChromaDB --> KB4[🎯 業務ルールナレッジ<br/>制約条件・優先順位・判断基準]
        end
        
        subgraph "データ統合層"
            RAGEngine --> Redis[⚡ Redis :6379]
            RAGEngine --> MySQL[🗃️ MySQL :3306]
            Redis --> Cache[💾 ベクトル検索キャッシュ]
            MySQL --> RealData[📈 リアルタイム業務データ]
        end
    end
    
    style RAGEngine fill:#f9d71c
    style Models fill:#81c784
    style KB1 fill:#ffb74d
    style KB2 fill:#64b5f6
    style KB3 fill:#9575cd
    style KB4 fill:#f48fb1
```


### RAG処理フロー

```mermaid
sequenceDiagram
    participant User as 👤 ユーザー
    participant API as 🌐 FastAPI
    participant RAG as 🧠 RAGエンジン
    participant Cache as ⚡ Redis
    participant Vector as 🗄️ ChromaDB
    participant LLM as 🤖 Ollama
    participant DB as 🗃️ MySQL
    
    User->>API: 「横浜拠点の明日の最適配置を提案して」
    API->>RAG: 配置最適化リクエスト
    
    Note over RAG: 1. 必要な情報を判断
    RAG->>Cache: キャッシュ確認
    Cache-->>RAG: キャッシュなし
    
    Note over RAG: 2. 関連情報を検索
    RAG->>Vector: セマンティック検索<br/>「横浜 配置 最適化 明日」
    Vector-->>RAG: 関連チャンク取得<br/>・横浜拠点の生産性データ<br/>・従業員の特性情報<br/>・配置ベストプラクティス
    
    Note over RAG: 3. リアルタイムデータ取得
    RAG->>DB: 最新の業務データ取得
    DB-->>RAG: 明日の予定業務量<br/>従業員の出勤状況
    
    Note over RAG: 4. コンテキスト統合
    RAG->>RAG: ナレッジ + リアルタイムデータ統合
    
    Note over RAG: 5. AI回答生成
    RAG->>LLM: 統合プロンプト送信
    LLM-->>RAG: ストリーミング回答
    
    Note over RAG: 6. 結果キャッシュ
    RAG->>Cache: 検索結果をキャッシュ
    
    RAG-->>API: 最適配置提案<br/>+ 根拠となるデータソース
    API-->>User: 詳細な配置提案と理由
```

### Docker統合構成

```mermaid
graph TB
    subgraph "Docker Compose Network"
        
        subgraph "Web層"
            Nginx[🌐 Nginx<br/>:80]
            Frontend[⚛️ Next.js<br/>:3000]
        end
        
        subgraph "API層"
            Backend[🐍 FastAPI<br/>:8000]
        end
        
        subgraph "AI基盤層"
            Ollama[🤖 Ollama<br/>:11434]
            ChromaDB[🗄️ ChromaDB<br/>:8001]
        end
        
        subgraph "データ層"
            MySQL[🗃️ MySQL<br/>:3306]
            Redis[⚡ Redis<br/>:6379]
        end
        
        subgraph "ボリューム永続化"
            OllamaVol[📦 ollama-models]
            ChromaVol[📊 chroma-data]
            MySQLVol[🗃️ mysql-data]
            RedisVol[💾 redis-data]
        end
    end
    
    Nginx --> Frontend
    Nginx --> Backend
    Backend --> Ollama
    Backend --> ChromaDB
    Backend --> MySQL
    Backend --> Redis
    
    Ollama --- OllamaVol
    ChromaDB --- ChromaVol
    MySQL --- MySQLVol
    Redis --- RedisVol
    
    style Backend fill:#f9d71c
    style Ollama fill:#81c784
    style ChromaDB fill:#64b5f6
```

## API仕様

### 新統合エンドポイント

#### 統合AI相談
- `POST /api/v1/ai/consult` - 自然言語での業務相談
- `WebSocket /ws/ai/stream` - リアルタイムAI対話

#### RAG管理
- `POST /api/v1/rag/documents` - ナレッジドキュメント登録
- `GET /api/v1/rag/search` - ナレッジ検索
- `DELETE /api/v1/rag/documents/{doc_id}` - ドキュメント削除

#### 従来エンドポイント（統合後）

#### アラート管理
- `GET /api/v1/alerts` - アラート一覧取得
- `GET /api/v1/alerts/{alert_id}` - アラート詳細取得
- `POST /api/v1/alerts/{alert_id}/acknowledge` - アラート確認

#### 配置管理（AI強化）
- `GET /api/v1/assignments/current` - 現在の配置取得
- `POST /api/v1/assignments/recommend` - AI推奨配置取得（RAG強化）
- `PUT /api/v1/assignments/{assignment_id}` - 配置更新

#### チャット（RAG統合）
- `POST /api/v1/chat/messages` - メッセージ送信（RAG対応）
- `GET /api/v1/chat/history` - チャット履歴取得

## 開発環境

### 従来セットアップ（実験用）
```bash
# 仮想環境作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存パッケージインストール
pip install -r requirements.txt

# 環境変数設定
cp .env.example .env

# 開発サーバー起動
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 新RAG統合環境（推奨）

#### 必要要件
- Docker & Docker Compose
- 最低16GB RAM（推奨: 32GB）
- 20GB以上の空き容量

#### クイックスタート
```bash
# リポジトリクローン
git clone <repository-url>
cd aimee-be

# 環境設定
cp .env.example .env
# LLMモデルとベクトルDB設定を編集

# Docker環境構築
make setup

# AIモデルダウンロード
make download-models

# 全サービス起動
make dev
```

#### 利用可能なサービス
- **メインAPI**: http://localhost:8000
- **管理UI**: http://localhost:3000
- **Swagger文書**: http://localhost:8000/docs
- **Ollama**: http://localhost:11434
- **ChromaDB**: http://localhost:8001

#### 開発コマンド
```bash
make dev           # 全サービス起動
make logs          # 全ログ表示
make health        # サービス状態確認
make test          # テスト実行
make clean         # 環境リセット
```

### 環境変数設定

#### AI関連設定
```bash
# LLMモデル設定
OLLAMA_MODEL=gemma3:4b         # メインAIモデル
EMBEDDING_MODEL=nomic-embed-text   # 埋め込みモデル

# RAG設定
CHUNK_SIZE=512                 # ドキュメントチャンクサイズ
TOP_K_RESULTS=5               # 検索結果数
SIMILARITY_THRESHOLD=0.7      # 類似度閾値

# ベクトルDB設定
CHROMADB_HOST=chromadb
CHROMADB_PORT=8000

# キャッシュ設定
REDIS_HOST=redis
REDIS_PORT=6379
```

#### 従来設定
```bash
# データベース設定
DATABASE_URL=mysql://user:password@localhost:3306/aimee
REDIS_URL=redis://localhost:6379
```

## 実装ロードマップ

### フェーズ1: RAG基盤構築（2週間）
- [ ] Ollama統合とモデル最適化
- [ ] ChromaDB導入とベクトル化パイプライン
- [ ] 基本的なRAG検索機能

### フェーズ2: ナレッジベース構築（3週間）
- [ ] 数値分析ナレッジの移行（元バッチ2）
- [ ] ノウハウナレッジの移行（元バッチ3）
- [ ] 業務マニュアルの統合

### フェーズ3: UI/UX統合（2週間）
- [ ] Next.js管理UIの構築
- [ ] WebSocketストリーミング対応
- [ ] リアルタイム配置シミュレーション

### フェーズ4: プロダクション対応（1週間）
- [ ] パフォーマンス最適化
- [ ] セキュリティ強化
- [ ] モニタリング・ログ整備

## 移行のメリット

### 技術的メリット
1. **システム統合**: 3つのAIシステム → 1つの統合RAG
2. **レスポンス向上**: ベクトル検索による高速化
3. **拡張性**: 新しいナレッジの簡単追加
4. **保守性**: 統一アーキテクチャによる管理简化

### ビジネスメリット
1. **コスト削減**: 外部API不要、完全ローカル運用
2. **セキュリティ**: 企業データの外部流出リスクゼロ
3. **カスタマイズ**: 企業固有のナレッジに特化
4. **可用性**: インターネット接続不要の安定運用

### API ドキュメント
開発サーバー起動後、以下でアクセス可能：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- 管理画面: http://localhost:3000