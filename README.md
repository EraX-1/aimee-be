# AIMEE Backend API v2.0

AI配置最適化システム - 統合LLMによる配置最適化システム（実装完了）

## システム概要

AIMEE（AI配置最適化システム）は、自然言語による業務相談に対して、軽量LLMによる意図解析、データベースからの実績データ取得、提案生成を統合した完全動作システムです。

### アーキテクチャ概要

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

### 処理フロー詳細（5段階処理）

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

## システムの特徴

### 1. マルチモデルLLM構成

- **軽量LLM（qwen2:0.5b）**: 高速な意図解析とルーティング
- **メインLLM（gemma3:4b）**: 軽量4Bパラメータモデルによる詳細分析と提案生成

### 2. リアルタイムデータ活用

- **MySQL**: 実績データ（従業員、生産性、勤怠、配置履歴）
- **Redis**: 高速キャッシュによるレスポンス改善
- **ChromaDB**: ベクトルデータベースによる類似検索

### 3. 実装済み統合LLM + RAGフロー（5段階処理）

1. **意図解析** (qwen2:0.5b) → ユーザーメッセージから意図とエンティティを抽出
2. **RAG検索** (ChromaDB) → セマンティック検索で最適なオペレータを検索
3. **データベース照会** → 意図に基づいて適切なデータを取得
4. **提案生成** → RAG結果とDB情報を統合して具体的提案を作成
5. **レスポンス生成** (gemma3:4b) → 日本語で実用的な回答を作成

### 4. ChromaDB RAGシステム（NEW）

- **セマンティックチャンキング**: オペレータ・工程データを意味のある単位で分割
- **ベクトル検索**: 自然言語クエリで最適なオペレータを検索
- **スキルマッチング**: 業務・工程に応じた人員配置最適化

### 5. 対応データベーステーブル

- `locations`: 拠点情報
- `processes`: 工程定義
- `operators`: オペレータマスタ
- `operator_process_capabilities`: オペレータ処理可能工程マトリクス
- `operator_work_records`: 作業実績
- `daily_assignments`: 日次配置計画
- `login_records`: ログイン記録
- `rag_context`: RAGコンテキスト（管理者判断基準）


## API仕様

### 主要エンドポイント

#### 統合LLMサービス（実装完了）
- `POST /api/v1/llm-test/integrated` - 統合LLM処理（意図解析+DB照会+提案生成）
- `POST /api/v1/llm-test/intent` - 意図解析テスト
- `GET /api/v1/llm-test/connection` - LLM接続テスト

#### アラート管理
- `GET /api/v1/alerts` - アラート一覧取得
- `GET /api/v1/alerts/{alert_id}` - アラート詳細取得
- `POST /api/v1/alerts/{alert_id}/acknowledge` - アラート確認

#### 承認管理
- `GET /api/v1/approvals` - 承認一覧取得
- `POST /api/v1/approvals/{approval_id}/action` - 承認アクション
- `POST /api/v1/approvals/bulk/approve` - 一括承認

#### システム状態
- `GET /api/v1/status` - APIステータス
- `GET /api/v1/health` - ヘルスチェック
- `GET /api/v1/status/health` - 詳細ヘルスチェック
- `GET /api/v1/status/metrics` - メトリクス取得

## 使用例

### AI相談機能の利用

#### 統合LLMサービス利用例
```bash
curl -X POST http://localhost:8002/api/v1/llm-test/integrated \
  -H "Content-Type: application/json" \
  -d '{
    "message": "札幌のエントリ1工程が遅延しています。対応策を提案してください。",
    "context": {
      "location": "札幌",
      "process": "エントリ1",
      "delay_minutes": 20
    }
  }'
```

#### レスポンス例
```json
{
  "response": "札幌市のエントリ1工程での遅延について分析しました。\n\n以下の対応策を提案いたします：\n\n1. **即時対応**\n   - 近隣拠点から熟練オペレータを2名一時的に配置転換\n   - 作業優先順位を見直し、重要案件から処理...",
  "intent": {
    "intent_type": "delay_resolution",
    "urgency": "high",
    "requires_action": true,
    "entities": {
      "location": "札幌市",
      "process": "エントリ1工程",
      "issue_type": "遅延"
    }
  },
  "suggestion": {
    "id": "SGT20250925-200414",
    "changes": [],
    "impact": {
      "productivity": "+0%",
      "delay": "-0分",
      "quality": "維持"
    },
    "reason": "現在のリソースで対応可能です",
    "confidence_score": 0.7
  },
  "metadata": {
    "timestamp": "2025-09-25T20:04:14.336467",
    "data_sources": [
      "current_assignments",
      "productivity_trends",
      "available_resources",
      "recent_alerts"
    ],
    "has_db_data": true
  }
}
```

## データベース接続設定

aimee-dbプロジェクトで使用している以下の設定に統合されました：
- **ユーザー名**: aimee_user
- **パスワード**: Aimee2024!
- **データベース名**: aimee_db
- **ホスト**: localhost（ローカル開発時）
- **ポート**: 3306
- **ドライバー**: aiomysql（非同期対応）

## Docker最適化環境

### クイックスタート（M3 Mac対応）
```bash
# 環境構築（5分）
git clone <repository-url>
cd aimee-be

# 設定
cp .env.example .env
# .envファイルを編集してSECRET_KEYを設定
# データベースのパスワードは自動的にAimee2024!に設定済み

# 初期セットアップ
make setup

# Dockerサービス起動（バックエンド）
make dev

# LLMモデルダウンロード（初回のみ必要）
make download-models

# APIサーバー起動（ローカル開発）
python -c "from app.main import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8002)" &

# 統合LLMテスト
curl -X POST http://localhost:8002/api/v1/llm-test/integrated \
  -H "Content-Type: application/json" \
  -d '{"message": "札幌の遅延について教えてください"}'
```

### 主要コマンド
```bash
make help           # ヘルプ表示
make dev            # 開発環境起動
make stop           # サービス停止
make logs           # ログ表示
make shell-mysql    # MySQLシェル
make db-status      # DB状態確認
make test-api       # API動作確認
```

### Docker構成

本プロジェクトは以下のDockerサービスを使用します：

- **mysql**: MySQL 8.0データベース (ポート3306) 
- **ollama-light**: 軽量LLM qwen2:0.5b (ポート11433)
- **ollama-main**: メインLLM gemma3:4b (ポート11435、12GB割当)
- **chromadb**: ベクトルデータベース (ポート8001)
- **redis**: キャッシュサーバー (ポート6379)
- **FastAPI**: ローカルポート8002で実行中

## 環境変数

主要な環境変数は`.env`ファイルで設定します：

```bash
# LLMモデル設定
INTENT_MODEL=qwen2:0.5b          # 意図解析用軽量モデル
MAIN_MODEL=gemma3:4b             # メイン回答生成モデル（4Bパラメータ軽量モデル）

# データベース設定
DATABASE_URL=mysql+aiomysql://aimee_user:Aimee2024!@localhost:3306/aimee_db

# サービスホスト設定（ローカル開発）
OLLAMA_LIGHT_HOST=localhost
OLLAMA_LIGHT_PORT=11433
OLLAMA_MAIN_HOST=localhost
OLLAMA_MAIN_PORT=11435
REDIS_URL=redis://redis:6379/0
```

## トラブルシューティング

### 統合LLMサービスのテスト
```bash
# 接続テスト
curl http://localhost:8002/api/v1/llm-test/connection

# 意図解析テスト
curl -X POST http://localhost:8002/api/v1/llm-test/intent \
  -H "Content-Type: application/json" \
  -d '{"message": "東京の出荷工程でリソース不足です"}'

# 統合処理テスト
curl -X POST http://localhost:8002/api/v1/llm-test/integrated \
  -H "Content-Type: application/json" \
  -d '{"message": "札幌のエントリ1工程が遅延しています"}'  
```

### MySQL接続エラー
```bash  
# パスワードがAimee2024!に設定されているか確認
cat .env | grep DATABASE_URL

# MySQLコンテナへの接続テスト
make shell-mysql
```

### Docker容量不足
```bash
# 不要なコンテナやイメージを削除
docker system prune -a --volumes -f
```

## ライセンス

MIT License

## コントリビューション

IssueやPull Requestを歓迎します。

---

**AIMEE Backend** - AIを活用した労働力配置最適化システム