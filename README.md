# AIMEE Backend API v2.0

AI配置最適化システム - 統合LLMによる配置最適化システム（実装完了）

## システム概要

AIMEE（AI配置最適化システム）は、自然言語による業務相談に対して、軽量LLMによる意図解析、データベースからの実績データ取得、提案生成を統合した完全動作システムです。

### アーキテクチャ概要

```mermaid
graph TB
    User[ユーザー] --> API[FastAPI<br/>8000番ポート]
    
    API --> ChatService[チャットサービス]
    
    ChatService --> IntegratedLLM[統合LLMサービス]
    IntegratedLLM --> LightLLM[軽量LLM<br/>qwen2:0.5b<br/>意図解析]
    IntegratedLLM --> MainLLM[メインLLM<br/>mock対応<br/>回答生成]
    
    ChatService --> DB[(MySQL<br/>aimee_db)]
    ChatService --> Redis[(Redis<br/>キャッシュ)]
    ChatService --> ChromaDB[(ChromaDB<br/>ベクトルDB)]
    
    style API fill:#f9d71c
    style LightLLM fill:#e1f5fe
    style MainLLM fill:#ff9800
```

## システムの特徴

### 1. マルチモデルLLM構成

- **軽量LLM（qwen2:0.5b）**: 高速な意図解析とルーティング
- **メインLLM（gemma:7b）**: 高性能7Bパラメータモデルによる詳細分析と提案生成

### 2. リアルタイムデータ活用

- **MySQL**: 実績データ（従業員、生産性、勤怠、配置履歴）
- **Redis**: 高速キャッシュによるレスポンス改善
- **ChromaDB**: ベクトルデータベースによる類似検索

### 3. 実装済み統合LLMフロー

1. **意図解析** (qwen2:0.5b) → ユーザーメッセージから意図とエンティティを抽出
2. **データベース照会** → 意図に基づいて適切なデータを取得
3. **提案生成** → リソース配分や遅延解決の具体的提案を作成
4. **レスポンス生成** → 日本語で実用的な回答を作成

### 4. 対応データベーステーブル

- `locations`: 拠点情報
- `processes`: 工程定義
- `operators`: オペレータマスタ
- `operator_work_records`: 作業実績
- `daily_assignments`: 日次配置計画
- `login_records`: ログイン記録


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
- **ollama-main**: メインLLM gemma:7b (ポート11434、12GB割当)
- **chromadb**: ベクトルデータベース (ポート8001)
- **redis**: キャッシュサーバー (ポート6379)
- **FastAPI**: ローカルポート8002で実行中

## 環境変数

主要な環境変数は`.env`ファイルで設定します：

```bash
# LLMモデル設定
INTENT_MODEL=qwen2:0.5b          # 意図解析用軽量モデル
MAIN_MODEL=gemma:7b               # メイン回答生成モデル（7Bパラメータ高性能モデル）

# データベース設定
DATABASE_URL=mysql+aiomysql://aimee_user:Aimee2024!@localhost:3306/aimee_db

# サービスホスト設定（ローカル開発）
OLLAMA_LIGHT_HOST=localhost
OLLAMA_LIGHT_PORT=11433
OLLAMA_MAIN_HOST=localhost
OLLAMA_MAIN_PORT=11434
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