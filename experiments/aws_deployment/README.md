# AWS展開ガイド

## 🏗️ システム構成

### 1. UI層（フロントエンド）
- **S3 + CloudFront**
  - 静的ファイルホスティング
  - グローバルCDN配信
  - コスト効率が高い

### 2. API層（FastAPI）
- **ECS Fargate**
  - サーバーレスコンテナ実行
  - 自動スケーリング
  - 運用負荷が低い

### 3. AI層（Llama + RAG）
- **EC2 g5.2xlarge**
  - NVIDIA A10G GPU (24GB)
  - Llama 13Bモデル対応
  - 高速推論

### 4. DB層
- **RDS MySQL**
  - マネージドサービス
  - 自動バックアップ
  - Multi-AZ対応

## 📦 段階的な展開計画

### Phase 1: 開発環境（現在）
```
ローカル Mac
├── UI: Streamlit（仮）
├── API: FastAPI (localhost:8000)
├── AI: Llama 7B Q4
└── DB: ローカルMySQL
```

### Phase 2: AWS検証環境
```
AWS (シングルインスタンス)
├── EC2 g5.2xlarge
│   ├── Docker Compose
│   ├── UI + API + AI
│   └── Llama 13B
└── RDS MySQL (t3.medium)
```

### Phase 3: AWS本番環境
```
AWS (プロダクション構成)
├── S3 + CloudFront (UI)
├── ECS Fargate (API)
├── EC2 g5.4xlarge (AI)
└── RDS MySQL (m5.large, Multi-AZ)
```

### Phase 4: スパコン環境
```
オンプレミス
├── nginx (リバースプロキシ)
├── Kubernetes
│   ├── UI Pod
│   ├── API Pod × N
│   └── AI Pod (GPU)
└── PostgreSQL/MySQL

## 🚀 デプロイ手順

### 1. Dockerコンテナ化
```bash
# Dockerfileの作成
docker build -t aimee-api .
docker build -t aimee-ai .

# ローカルテスト
docker-compose up
```

### 2. AWS初期セットアップ
```bash
# AWS CLIの設定
aws configure

# VPCとセキュリティグループの作成
aws ec2 create-vpc --cidr-block 10.0.0.0/16

# RDSの作成
aws rds create-db-instance \
  --db-instance-identifier aimee-db \
  --db-instance-class db.t3.medium \
  --engine mysql
```

### 3. EC2へのデプロイ（検証用）
```bash
# EC2インスタンスの起動
aws ec2 run-instances \
  --image-id ami-xxxxx \
  --instance-type g5.2xlarge \
  --key-name your-key

# SSHでアクセス
ssh -i your-key.pem ec2-user@instance-ip

# Dockerのインストールと実行
sudo yum install docker
sudo service docker start
docker-compose up -d
```

## 💰 コスト見積もり（月額）

### 検証環境
- EC2 g5.2xlarge: $1,500
- RDS t3.medium: $100
- データ転送: $50
- **合計: 約$1,650/月**

### 本番環境
- EC2 g5.4xlarge: $3,000
- ECS Fargate: $200
- RDS m5.large: $300
- S3 + CloudFront: $100
- **合計: 約$3,600/月**

## 🔧 必要な設定ファイル

### docker-compose.yml
```yaml
version: '3.8'
services:
  api:
    build: ./aimee-be
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: ${DATABASE_URL}
    depends_on:
      - ai

  ai:
    build: ./aimee-ai
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    volumes:
      - ./models:/app/models

  ui:
    build: ./aimee-ui
    ports:
      - "3000:3000"
    depends_on:
      - api
```

### Dockerfile (API)
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Dockerfile (AI)
```dockerfile
FROM nvidia/cuda:12.0-base-ubuntu22.04

# Pythonとllama-cpp-pythonのインストール
RUN apt-get update && apt-get install -y python3 python3-pip
RUN CMAKE_ARGS="-DLLAMA_CUBLAS=on" pip install llama-cpp-python

WORKDIR /app
COPY . .

CMD ["python", "ai_service.py"]
```

## 🎯 次のステップ

1. **Dockerイメージの作成とテスト**
2. **AWSアカウントの準備**
3. **セキュリティグループとIAMロールの設定**
4. **CI/CDパイプラインの構築**