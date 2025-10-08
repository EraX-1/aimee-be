# CLAUDE.md

このファイルは、Claude Code (claude.ai/code) がこのリポジトリで作業する際のガイダンスを提供します。

## プロジェクト概要

AIMEE Backend API v2.0 - AI配置最適化システム
自然言語による業務相談に対して、軽量LLMによる意図解析、データベースからの実績データ取得、提案生成を統合した完全動作システムです。

## 最新の実装状況（2025-10-06 19:50 実データ投入完了版）

### ✅ 完了した機能（全て動作確認済み）

1. **LLMモデル変更**: gemma2:9b → gemma3:4b
   - panasonic-llm-integrationと同じモデルを使用
   - ollama-light: qwen2:0.5b (ポート11433) ✅稼働中
   - ollama-main: gemma3:4b (ポート11435) ✅稼働中

2. **ChromaDB RAGシステム完成**
   - セマンティックチャンキング実装完了 (`app/services/chroma_service.py`)
   - **バッチ処理対応**（ChromaDBの制限5,461件に対応）
   - **実データ投入完了**: **25,829ドキュメント**
     - オペレータチャンク: 25,718件（2,591名分）
     - 工程チャンク: 88件（78工程分）
   - ポート8002で稼働中（ポート競合回避）

3. **統合LLMサービスにRAG機能統合完了**
   - `IntegratedLLMService`: ChromaServiceを統合
   - 5段階処理フロー実装:
     1. 意図解析 (qwen2:0.5b)
     2. RAG検索 (ChromaDB セマンティック検索)
     3. DB照会 (MySQL)
     4. 提案生成
     5. 応答生成 (gemma3:4b)

4. **エンドツーエンドテスト成功**
   - テストケース1: 札幌拠点のエントリ1工程で人員不足 ✅
   - テストケース2: 補正工程のオペレータ検索 ✅
   - テストケース3: 本町東拠点での人員配置 ✅

5. **Redis設定**
   - ポート6380で稼働中（ポート競合回避）

6. **実データ投入完了** ✅NEW
   - **MySQL**: 実データ投入済み
     - オペレータ: **2,664名** (mockの380倍!)
     - 処理可能工程: **55,863件**
     - 業務: 12件、工程: 78件、拠点: 7件
   - **ChromaDB**: **25,829ドキュメント** 投入済み
   - パフォーマンスチューニング準備完了

### 🎯 動作確認済みの機能

**RAG検索（単体）:**
- セマンティック検索: 「札幌の拠点でエントリ工程ができるオペレータ」→ a1405015を発見
- 工程別マッチング: 業務523201の工程152に最適なオペレータを5名抽出
- 拠点指定検索: 札幌拠点(91)でのフィルタリングが正常動作

**統合システム（エンドツーエンド）:**
- 意図解析 → RAG検索 → DB照会 → 提案生成 → AI応答が全て連携
- 日本語での自然な応答生成
- メタデータとデバッグ情報の出力

### 📋 次のステップ（オプション）

1. ~~システム構成図の作成（Mermaid図）~~ ✅完了
2. ~~実データ投入~~ ✅完了（MySQL: 2,664名、ChromaDB: 25,829ドキュメント）
3. **API エンドポイントの追加**（RAG検索専用エンドポイント）
4. **パフォーマンスチューニング**（大規模データでの最適化）

## 開発コマンド

### 環境構築・起動
```bash
# 初期セットアップ（環境構築）
make setup

# 開発環境起動
make dev

# LLMモデルのダウンロード（初回のみ必要）
make download-models

# APIサーバー起動（ローカル開発時）
python -c "from app.main import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8002)" &
```

### RAG関連コマンド
```bash
# ChromaDBにデータ投入（初回のみ、または再投入時）
python3 scripts/populate_chromadb.py

# RAG検索テスト（ChromaDB単体）
python3 scripts/test_rag_search.py

# 統合LLM + RAGテスト（エンドツーエンド）
python3 scripts/test_integrated_rag.py
```

### Docker管理
```bash
make stop          # サービス停止
make clean         # クリーンアップ（ボリューム削除）
make logs          # ログ表示
make logs-api      # APIログのみ表示
make logs-mysql    # MySQLログのみ表示
make logs-ollama   # LLMログのみ表示
```

### データベース操作
```bash
make shell-mysql   # MySQLシェル (ユーザー: root, パスワード: root_password)
make db-status     # DB状態確認（テーブル一覧と行数）

# rootユーザーでMySQLアクセス
docker-compose exec mysql mysql -u root -proot_password aimee_db
```

### コード品質管理
```bash
make lint          # リンター実行 (ruff check)
make format        # コードフォーマット (ruff format)
make test          # テスト実行 (pytest)
```

### ヘルスチェック
```bash
make health-check  # 全サービスのヘルスチェック
make test-api      # API動作確認

# ChromaDB接続確認
curl http://localhost:8002/api/v2/heartbeat
```

### 統合LLMサービステスト
```bash
# 接続テスト
curl http://localhost:8002/api/v1/llm-test/connection

# 意図解析テスト
curl -X POST http://localhost:8002/api/v1/llm-test/intent \
  -H "Content-Type: application/json" \
  -d '{"message": "東京の出荷工程でリソース不足です"}'

# 統合処理テスト
./test_integrated.sh
```

## アーキテクチャ

### システム全体構成図

```mermaid
graph TB
    subgraph "クライアント層"
        User[ユーザー<br/>自然言語入力]
    end

    subgraph "API層 (FastAPI)"
        API[FastAPI Server<br/>localhost:8002]
        Endpoints[API Endpoints]
        API --> Endpoints
    end

    subgraph "サービス層"
        IntegratedLLM[IntegratedLLMService<br/>5段階処理統合]
        OllamaService[OllamaService<br/>LLM通信]
        ChromaService[ChromaService<br/>RAG検索]
        DBService[DatabaseService<br/>DB照会]
    end

    subgraph "LLM層 (Ollama)"
        LightLLM[ollama-light<br/>qwen2:0.5b<br/>ポート11433<br/>3GB RAM]
        MainLLM[ollama-main<br/>gemma3:4b<br/>ポート11435<br/>12GB RAM]
    end

    subgraph "データ層"
        MySQL[(MySQL 8.0<br/>aimee_db<br/>ポート3306)]
        ChromaDB[(ChromaDB<br/>ベクトルDB<br/>ポート8002<br/>64ドキュメント)]
        Redis[(Redis 7<br/>キャッシュ<br/>ポート6380)]
    end

    User -->|HTTPリクエスト| API
    Endpoints --> IntegratedLLM

    IntegratedLLM --> OllamaService
    IntegratedLLM --> ChromaService
    IntegratedLLM --> DBService

    OllamaService -->|意図解析| LightLLM
    OllamaService -->|応答生成| MainLLM

    ChromaService -->|ベクトル検索| ChromaDB
    DBService -->|SQL照会| MySQL
    IntegratedLLM -.->|キャッシュ| Redis

    style User fill:#e3f2fd
    style API fill:#fff9c4
    style IntegratedLLM fill:#c8e6c9
    style LightLLM fill:#bbdefb
    style MainLLM fill:#ffcc80
    style MySQL fill:#f8bbd0
    style ChromaDB fill:#d1c4e9
    style Redis fill:#ffccbc
```

### 処理フロー詳細図（5段階処理）

```mermaid
sequenceDiagram
    participant User as ユーザー
    participant API as FastAPI
    participant Integrated as IntegratedLLMService
    participant Light as ollama-light<br/>(qwen2:0.5b)
    participant Chroma as ChromaDB
    participant DB as MySQL
    participant Main as ollama-main<br/>(gemma3:4b)

    User->>API: POST /api/v1/llm-test/integrated<br/>「札幌のエントリ工程で人員不足」

    rect rgb(220, 240, 255)
        Note over Integrated,Light: ステップ1: 意図解析
        API->>Integrated: process_message()
        Integrated->>Light: analyze_intent()
        Light-->>Integrated: intent_type: resource_allocation<br/>location: 札幌<br/>process: エントリ工程
    end

    rect rgb(255, 240, 220)
        Note over Integrated,Chroma: ステップ2: RAG検索
        Integrated->>Chroma: find_best_operators_for_process()
        Chroma-->>Integrated: 推奨オペレータ5名<br/>スキルマッチスコア付き
        Integrated->>Chroma: query_similar()
        Chroma-->>Integrated: 関連コンテキスト3件
    end

    rect rgb(220, 255, 220)
        Note over Integrated,DB: ステップ3: DB照会
        Integrated->>DB: fetch_data_by_intent()
        DB-->>Integrated: 配置情報、生産性データ<br/>余剰リソース、アラート
    end

    rect rgb(255, 220, 255)
        Note over Integrated: ステップ4: 提案生成
        Integrated->>Integrated: generate_suggestion()<br/>RAG結果 + DB情報を統合
        Note right of Integrated: 配置変更案<br/>影響予測<br/>信頼度スコア
    end

    rect rgb(220, 255, 255)
        Note over Integrated,Main: ステップ5: 応答生成
        Integrated->>Main: generate_response()<br/>意図+DB+RAG+提案
        Main-->>Integrated: 日本語応答<br/>「以下の対応策を提案します...」
    end

    Integrated-->>API: response + suggestion + metadata
    API-->>User: JSON応答<br/>(推奨オペレータ含む)
```

### データベーススキーマ構成

```mermaid
erDiagram
    locations ||--o{ operators : "所属"
    locations ||--o{ daily_assignments : "配置先"
    operators ||--o{ operator_process_capabilities : "スキル"
    operators ||--o{ operator_work_records : "実績"
    operators ||--o{ daily_assignments : "配置"
    operators ||--o{ login_records : "ログイン"
    processes ||--o{ operator_process_capabilities : "工程定義"
    processes ||--o{ operator_work_records : "作業工程"
    processes ||--o{ daily_assignments : "配置工程"
    businesses ||--o{ processes : "業務"

    locations {
        int location_id PK
        string location_name
        string address
        string phone
        datetime created_at
    }

    operators {
        string operator_id PK
        string operator_name
        int location_id FK
        string email
        string phone
        date hire_date
    }

    processes {
        string business_id PK
        string process_id PK
        int level_id PK
        string process_name
        int standard_minutes
        text process_description
    }

    operator_process_capabilities {
        string operator_id FK
        string business_id FK
        string process_id FK
        int level_id FK
        int skill_level
    }

    operator_work_records {
        int record_id PK
        string operator_id FK
        string business_id FK
        string process_id FK
        date work_date
        int actual_minutes
        decimal productivity
    }

    daily_assignments {
        int assignment_id PK
        date assignment_date
        string operator_id FK
        int location_id FK
        string business_id FK
        string process_id FK
        int assigned_count
    }
```

### ChromaDB RAGアーキテクチャ

```mermaid
graph LR
    subgraph "データソース"
        MySQL_Operators[MySQL<br/>operators table]
        MySQL_Processes[MySQL<br/>processes table]
        MySQL_Skills[MySQL<br/>operator_process_capabilities]
    end

    subgraph "データ投入 (populate_chromadb.py)"
        Extract[データ抽出]
        Chunk[セマンティックチャンキング]
        Embed[エンベディング生成]
    end

    subgraph "ChromaDB (64ドキュメント)"
        OpChunks[オペレータチャンク<br/>12件]
        ProcChunks[工程チャンク<br/>52件]
        Metadata[メタデータ<br/>operator_id, location_id<br/>business_id, process_id]
    end

    subgraph "RAG検索機能"
        Semantic[セマンティック検索<br/>query_similar()]
        Match[スキルマッチング<br/>find_best_operators_for_process()]
    end

    MySQL_Operators --> Extract
    MySQL_Processes --> Extract
    MySQL_Skills --> Extract

    Extract --> Chunk
    Chunk --> Embed

    Embed --> OpChunks
    Embed --> ProcChunks
    OpChunks -.-> Metadata
    ProcChunks -.-> Metadata

    OpChunks --> Semantic
    ProcChunks --> Semantic
    OpChunks --> Match

    Semantic -->|関連コンテキスト| Output[検索結果]
    Match -->|推奨オペレータ| Output

    style MySQL_Operators fill:#f8bbd0
    style MySQL_Processes fill:#f8bbd0
    style MySQL_Skills fill:#f8bbd0
    style OpChunks fill:#d1c4e9
    style ProcChunks fill:#d1c4e9
    style Output fill:#c8e6c9
```

### Docker コンテナ構成とポート割り当て

```mermaid
graph TB
    subgraph "ホストマシン (M3 Mac)"
        Host[macOS<br/>Apple Silicon]
    end

    subgraph "Docker Network (172.20.0.0/16)"
        subgraph "LLMコンテナ"
            Light[ollama-light<br/>qwen2:0.5b<br/>内部: 11434<br/>外部: 11433<br/>3GB RAM]
            Main[ollama-main<br/>gemma3:4b<br/>内部: 11434<br/>外部: 11435<br/>12GB RAM]
        end

        subgraph "データベースコンテナ"
            MySQL[MySQL 8.0<br/>内部: 3306<br/>外部: 3306<br/>1GB RAM]
            Chroma[ChromaDB<br/>内部: 8000<br/>外部: 8002<br/>1GB RAM]
            Redis[Redis 7<br/>内部: 6379<br/>外部: 6380<br/>512MB RAM]
        end

        subgraph "永続化ボリューム"
            MySQLVol[(mysql-data)]
            ChromaVol[(chroma-data)]
            RedisVol[(redis-data)]
            LightVol[(ollama-light-models)]
            MainVol[(ollama-main-models)]
        end

        MySQL -.-> MySQLVol
        Chroma -.-> ChromaVol
        Redis -.-> RedisVol
        Light -.-> LightVol
        Main -.-> MainVol
    end

    subgraph "ローカル開発環境"
        API[FastAPI<br/>localhost:8002<br/>2GB RAM]
    end

    Host -->|Docker Compose| Light
    Host -->|Docker Compose| Main
    Host -->|Docker Compose| MySQL
    Host -->|Docker Compose| Chroma
    Host -->|Docker Compose| Redis

    API -->|localhost:11433| Light
    API -->|localhost:11435| Main
    API -->|localhost:3306| MySQL
    API -->|localhost:8002| Chroma
    API -->|localhost:6380| Redis

    style Light fill:#bbdefb
    style Main fill:#ffcc80
    style MySQL fill:#f8bbd0
    style Chroma fill:#d1c4e9
    style Redis fill:#ffccbc
    style API fill:#fff9c4
```

### マルチモデルLLM構成

プロジェクトは2つの独立したOllamaコンテナを使用：

1. **ollama-light** (ポート11433)
   - モデル: qwen2:0.5b
   - 用途: 高速な意図解析とルーティング
   - メモリ: 3GB

2. **ollama-main** (ポート11435)
   - モデル: gemma3:4b (4Bパラメータモデル)
   - 用途: 詳細分析と提案生成
   - メモリ: 12GB
   - **注意**: ポート11434はpanasonic-llm-integrationが使用中のため11435を使用

### RAGシステム構成

1. **ChromaDBサービス** (`app/services/chroma_service.py`)
   - セマンティックチャンキング機能
   - オペレータスキル検索
   - 工程情報検索
   - 人員配置最適化マッチング

2. **データ投入スクリプト** (`scripts/populate_chromadb.py`)
   - MySQLからオペレータ・工程データを取得
   - セマンティックチャンクに分割
   - ChromaDBに投入

3. **検索機能**
   - `query_similar()`: 汎用セマンティック検索
   - `find_best_operators_for_process()`: 工程に最適なオペレータを検索
   - メタデータフィルタ: 業務ID、拠点IDでの絞り込み対応

### 統合LLMフロー（完成版）

`IntegratedLLMService` が以下の5段階処理を実行：

1. **意図解析** (軽量LLM qwen2:0.5b)
   - ユーザーメッセージから意図とエンティティを抽出
   - intent_type: delay_resolution, resource_allocation, status_check, general_inquiry

2. **RAG検索** (`ChromaService`) ✅NEW
   - セマンティック検索で最適なオペレータを検索
   - 工程情報の関連コンテキストを取得
   - 業務ID・拠点IDでフィルタリング

3. **データベース照会** (`DatabaseService`)
   - 意図に基づいて実績データを取得
   - 配置情報、生産性データ、余剰リソースを取得

4. **提案生成**
   - RAG検索結果とDB情報を統合
   - リソース配分や遅延解決の具体的提案を作成

5. **レスポンス生成** (メインLLM gemma3:4b)
   - RAG推奨オペレータを含む日本語応答
   - 配置承認/否認/調整の選択肢を提示

### ディレクトリ構造

```
app/
├── api/v1/
│   ├── endpoints/      # APIエンドポイント実装
│   │   ├── llm_test.py     # LLMテストエンドポイント
│   │   ├── chat.py         # チャット機能
│   │   ├── alerts.py       # アラート管理
│   │   ├── approvals.py    # 承認管理
│   │   └── status.py       # システム状態
│   └── routers.py      # ルーター統合
├── services/           # ビジネスロジック層
│   ├── integrated_llm_service.py  # 統合LLMサービス（中核）
│   ├── ollama_service.py          # Ollama API通信
│   ├── database_service.py        # DB照会ロジック
│   ├── chroma_service.py          # ChromaDB RAGサービス（NEW）
│   └── llm_service.py
├── core/              # コア設定
│   ├── config.py      # 環境変数・設定管理
│   └── logging.py     # ロギング設定
├── db/                # データベース層
│   └── session.py     # SQLAlchemy非同期セッション
├── schemas/           # Pydanticスキーマ
│   ├── requests/      # リクエストモデル
│   └── responses/     # レスポンスモデル
├── domain/            # ドメインモデル
└── infrastructure/    # インフラストラクチャ層

scripts/
├── populate_chromadb.py   # ChromaDBデータ投入スクリプト（NEW）
└── test_rag_search.py     # RAG検索テストスクリプト（NEW）
```

### Dockerサービス（ポート割り当て）

- **mysql** (3306): MySQL 8.0データベース (aimee-db統合)
- **ollama-light** (11433): 軽量LLM qwen2:0.5b
- **ollama-main** (11435): メインLLM gemma3:4b ※11434はpanasonic使用中
- **chromadb** (8002): ベクトルデータベース ※8001はpanasonic使用中
- **redis** (6380): キャッシュサーバー ※6379はpanasonic使用中
- **api** (8000): FastAPIアプリケーション（Dockerモード）
  - ローカル開発時はポート8002で実行

### データベース

**接続情報:**
- ユーザー名: `root` (推奨) / `aimee_user` (権限問題あり)
- パスワード: `root_password` / `Aimee2024!`
- データベース名: `aimee_db`
- ホスト: `localhost` (ローカル) / `mysql` (Docker)
- ポート: 3306
- ドライバー: `aiomysql` (非同期対応)

**現在のデータ状態（実データ投入済み）:** ✅
- `locations`: 7件（拠点マスタ）
- `businesses`: 12件（業務マスタ）
- `processes`: 78件（工程定義）
- `operators`: **2,664名**（オペレータマスタ）
- `operator_process_capabilities`: **55,863件**（処理可能工程マトリクス）
- ChromaDB: **25,829ドキュメント**（オペレータ25,718 + 工程88チャンク）

**実データ再投入方法:**
```bash
# ChromaDBに再投入する場合
python3 scripts/populate_chromadb.py

# 処理時間: 約7分（バッチ処理で自動分割）
```

**主要テーブル:**
- `locations`: 拠点情報
- `businesses`: 業務マスタ
- `processes`: 工程定義（複合主キー: business_id + process_id + level_id）
- `operators`: オペレータマスタ
- `operator_process_capabilities`: オペレータ処理可能工程マトリクス
- `operator_work_records`: 作業実績
- `daily_assignments`: 日次配置計画
- `login_records`: ログイン記録
- `rag_context`: RAGコンテキスト（管理者判断基準）

スキーマは `../aimee-db/` ディレクトリで管理され、`docker-compose.yml` の初期化スクリプトで自動投入されます。

## 環境変数

主要な環境変数（`.env`を参照）:

```bash
# LLMモデル設定
INTENT_MODEL=qwen2:0.5b          # 意図解析用軽量モデル
MAIN_MODEL=gemma3:4b             # メイン回答生成モデル
OLLAMA_LIGHT_HOST=localhost      # ローカル開発時
OLLAMA_LIGHT_PORT=11433
OLLAMA_MAIN_HOST=localhost
OLLAMA_MAIN_PORT=11435           # ★11435を使用（11434はpanasonic使用中）

# データベース設定
DATABASE_URL=mysql+aiomysql://root:root_password@localhost:3306/aimee_db

# Redis設定
REDIS_URL=redis://redis:6379/0
REDIS_EXTERNAL_PORT=6380         # ★6380を使用（6379はpanasonic使用中）

# ChromaDB設定
CHROMADB_HOST=chromadb
CHROMADB_PORT=8000               # コンテナ内部ポート
CHROMADB_EXTERNAL_PORT=8002      # ★8002を使用（8001はpanasonic使用中）
CHROMADB_AUTH_TOKEN=aimee-chroma-token
CHROMADB_COLLECTION=aimee_knowledge

# パフォーマンス最適化
ENABLE_PARALLEL_PROCESSING=true
STREAMING_RESPONSE=true
```

## ChromaDB RAGシステムの使用方法

### 初回セットアップ（完了済み）

```bash
# 1. ChromaDBコンテナ起動
docker-compose up -d chromadb

# 2. MySQLからChromaDBにデータを投入
python3 scripts/populate_chromadb.py
# 結果: 64ドキュメント投入完了（オペレータ12 + 工程52チャンク）
```

### RAG検索テスト（動作確認済み）

```bash
# RAG単体テスト: 5つのテストケースを実行
python3 scripts/test_rag_search.py
```

テスト内容：
1. ChromaDB統計情報表示
2. セマンティック検索（「札幌の拠点でエントリ工程ができるオペレータ」）
3. 工程情報検索（「補正工程について教えて」）
4. 工程別オペレータマッチング（業務523201の工程152）
5. 拠点指定検索（札幌拠点91）

### 統合システムテスト（動作確認済み）

```bash
# 統合LLM + RAGのエンドツーエンドテスト
python3 scripts/test_integrated_rag.py
```

テスト内容：
1. 札幌拠点のエントリ1工程で人員不足 → 意図解析 + RAG + DB + 提案生成
2. 補正工程のオペレータ検索 → RAG検索で適切なオペレータを提案
3. 本町東拠点での人員配置 → 拠点指定での最適化提案

### ChromaService API

```python
from app.services.chroma_service import ChromaService

chroma = ChromaService()

# セマンティック検索
results = chroma.query_similar(
    query_text="札幌でエントリ工程ができるオペレータ",
    n_results=5
)

# 工程に最適なオペレータを検索
operators = chroma.find_best_operators_for_process(
    business_id="523201",
    process_id="152",
    location_id="91",  # オプション
    n_results=5
)

# 統計情報
stats = chroma.get_collection_stats()
```

## 開発時の注意事項

### ポート番号（重要）

**panasonic-llm-integration** と共存するため、以下のポートを使用：
- **Ollama Main**: 11435 (11434はpanasonic使用中)
- **ChromaDB**: 8002 (8001はpanasonic使用中)
- **Redis**: 6380 (6379はpanasonic使用中)

### LLMモデル

現在使用中のモデル：
- **qwen2:0.5b**: 意図解析（ollama-light, ポート11433）
- **gemma3:4b**: メイン回答生成（ollama-main, ポート11435）

モデルの確認：
```bash
docker-compose exec ollama-light ollama list
docker-compose exec ollama-main ollama list
```

### M3 Mac対応
Docker Composeの全サービスは `platform: linux/arm64/v8` で設定され、Apple Siliconに最適化されています。

### ChromaDBの文字エンコーディング

ChromaDB内部では日本語が正しく保存されています。表示時の文字化けはターミナルの問題であり、システム動作には影響しません。検索機能は正常に動作しています。

### データベーススキーマの更新

`../aimee-db/` ディレクトリのSQLファイルを更新後、以下を実行:
```bash
make clean   # データをリセット（注意: 全データ削除）
make setup   # 再セットアップ
make dev     # 起動
```

### 実データへの切り替え

mockデータから実データ（約7万件）に切り替える場合：
```bash
cd ../aimee-db
python3 import_all_real_data.py  # 実データ投入（資料フォルダが必要）

cd ../aimee-be
python3 scripts/populate_chromadb.py  # ChromaDBに再投入
```

### 統合LLMサービスのデバッグ
`detail=true`パラメータを使用すると、各ステップの詳細情報が返されます:
```bash
curl -X POST http://localhost:8002/api/v1/llm-test/integrated \
  -H "Content-Type: application/json" \
  -d '{"message": "札幌の遅延について教えてください", "detail": true}'
```

## トラブルシューティング

### Dockerコンテナが起動しない
```bash
# ポート使用状況を確認
lsof -i:8000
lsof -i:11433
lsof -i:11435

# 使用中のプロセスを終了
make dev  # 自動クリーンアップが実行されます
```

### LLMモデルが見つからない
```bash
# モデルの確認
docker-compose exec ollama-light ollama list
docker-compose exec ollama-main ollama list

# モデルのダウンロード
make download-models
```

### MySQLアクセスエラー
```bash
# rootユーザーでアクセス（推奨）
docker-compose exec mysql mysql -u root -proot_password aimee_db

# aimee_userに権限問題がある場合はrootを使用
```

### ChromaDB接続エラー
```bash
# ChromaDBの状態確認
curl http://localhost:8002/api/v2/heartbeat

# コンテナ再起動
docker-compose restart chromadb
```

### RAG検索で結果が返らない
```bash
# データが投入されているか確認
python3 -c "
from app.services.chroma_service import ChromaService
chroma = ChromaService()
print(chroma.get_collection_stats())
"

# データ再投入
python3 scripts/populate_chromadb.py
```

## API主要エンドポイント

- `POST /api/v1/llm-test/integrated` - 統合LLM処理
- `POST /api/v1/llm-test/intent` - 意図解析テスト
- `GET /api/v1/llm-test/connection` - LLM接続テスト
- `GET /api/v1/health` - ヘルスチェック
- `GET /api/v1/status` - APIステータス
- `GET /docs` - Swagger UIドキュメント

## 依存パッケージ

主要な追加パッケージ：
- `chromadb==1.1.1`: RAGベクトルデータベース（最新版）
- `aiomysql==0.2.0`: 非同期MySQL接続
- `redis==5.0.7`: キャッシュ
