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

## API仕様

### エンドポイント一覧

#### アラート管理
- `GET /api/v1/alerts` - アラート一覧取得
- `GET /api/v1/alerts/{alert_id}` - アラート詳細取得
- `POST /api/v1/alerts/{alert_id}/acknowledge` - アラート確認

#### 配置管理
- `GET /api/v1/assignments/current` - 現在の配置取得
- `POST /api/v1/assignments/recommend` - AI推奨配置取得
- `PUT /api/v1/assignments/{assignment_id}` - 配置更新

#### チャット
- `POST /api/v1/chat/messages` - メッセージ送信
- `GET /api/v1/chat/history` - チャット履歴取得

## 開発環境

### 必要要件
- Python 3.11+
- MySQL 8.0+
- Redis（キャッシュ用）

### セットアップ
```bash
# 仮想環境作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存パッケージインストール
pip install -r requirements.txt

# 環境変数設定
cp .env.example .env
# .envファイルを編集

# 開発サーバー起動
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### API ドキュメント
開発サーバー起動後、以下でアクセス可能：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc