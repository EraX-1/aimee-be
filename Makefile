# AIMEE Backend Makefile for M3 Mac

.PHONY: help setup dev stop clean logs shell test lint format

help:
	@echo "AIMEE Backend Development Commands:"
	@echo "  make setup          - 初期セットアップ（環境構築）"
	@echo "  make dev            - 開発環境起動"
	@echo "  make stop           - サービス停止"
	@echo "  make clean          - クリーンアップ（ボリューム削除）"
	@echo "  make logs           - ログ表示"
	@echo "  make shell-api      - APIコンテナのシェル"
	@echo "  make shell-mysql    - MySQLコンテナのシェル"
	@echo "  make download-models - LLMモデルのダウンロード"
	@echo "  make test           - テスト実行"
	@echo "  make lint           - リンター実行"
	@echo "  make format         - コードフォーマット"

# 初期セットアップ
setup:
	@echo "🚀 AIMEE Backend初期セットアップを開始します..."
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✅ .envファイルを作成しました"; \
	else \
		echo "ℹ️  .envファイルは既に存在します（スキップ）"; \
	fi
	@docker-compose pull
	@echo "✅ Dockerイメージをダウンロードしました"
	@docker-compose up -d mysql redis
	@echo "⏳ データベースの起動を待っています..."
	@sleep 10
	@echo "✅ セットアップ完了！"

# 開発環境起動
dev:
	@echo "🚀 開発環境を起動します..."
	@echo "🧹 既存のポート使用をクリーンアップ中..."
	@lsof -ti:8000 | xargs kill -9 2>/dev/null || true
	@lsof -ti:8001 | xargs kill -9 2>/dev/null || true
	docker-compose up -d --build
	@echo "✅ 全サービスが起動しました"
	@echo "📊 サービス状態:"
	@docker-compose ps
	@echo ""
	@echo "🌐 アクセスURL:"
	@echo "  - API: http://localhost:8000"
	@echo "  - API Docs: http://localhost:8000/docs"
	@echo "  - ChromaDB: http://localhost:8001"
	@echo "  - Ollama Light: http://localhost:11433"
	@echo "  - Ollama Main: http://localhost:11434"

# LLMモデルダウンロード
download-models:
	@echo "📥 LLMモデルをダウンロードします..."
	@docker-compose up -d ollama-light ollama-main
	@echo "⏳ コンテナの起動を待っています..."
	@sleep 10
	@echo "🔍 既存モデルをチェック中..."
	@if docker-compose exec ollama-light ollama list | grep -q "qwen2:0.5b"; then \
		echo "✅ qwen2:0.5b は既にダウンロード済みです"; \
	else \
		echo "📥 qwen2:0.5b をダウンロード中..."; \
		docker-compose exec ollama-light ollama pull qwen2:0.5b; \
		echo "✅ qwen2:0.5b のダウンロード完了"; \
	fi
	@if docker-compose exec ollama-main ollama list | grep -q "gemma3:4b"; then \
		echo "✅ gemma3:4b は既にダウンロード済みです"; \
	else \
		echo "📥 gemma3:4b をダウンロード中..."; \
		docker-compose exec ollama-main ollama pull gemma3:4b; \
		echo "✅ gemma3:4b のダウンロード完了"; \
	fi
	@echo "🎉 モデルの確認が完了しました！"

# サービス停止
stop:
	@echo "🛑 サービスを停止します..."
	docker-compose down
	@echo "✅ 全サービスが停止しました"

# クリーンアップ
clean:
	@echo "🧹 クリーンアップを実行します..."
	@read -p "⚠️  全てのデータが削除されます。続行しますか？ [y/N] " confirm; \
	if [ "$${confirm}" = "y" ] || [ "$${confirm}" = "Y" ]; then \
		docker-compose down -v; \
		echo "✅ クリーンアップ完了"; \
	else \
		echo "❌ クリーンアップをキャンセルしました"; \
	fi

# ログ表示
logs:
	docker-compose logs -f

logs-api:
	docker-compose logs -f api

logs-mysql:
	docker-compose logs -f mysql

logs-ollama:
	docker-compose logs -f ollama-light ollama-main

# シェルアクセス
shell-api:
	docker-compose exec api bash

shell-mysql:
	docker-compose exec mysql mysql -u aimee_user -pAimee2024! aimee_db

shell-redis:
	docker-compose exec redis redis-cli

# ヘルスチェック
health-check:
	@echo "🏥 ヘルスチェックを実行します..."
	@echo "MySQL:"
	@docker-compose exec mysql mysqladmin ping -h localhost -u root -proot_password || echo "❌ MySQL is not healthy"
	@echo ""
	@echo "Redis:"
	@docker-compose exec redis redis-cli ping || echo "❌ Redis is not healthy"
	@echo ""
	@echo "API:"
	@curl -s http://localhost:8000/api/v1/status > /dev/null && echo "✅ API is healthy" || echo "❌ API is not healthy"
	@echo ""
	@echo "Ollama Light:"
	@curl -s http://localhost:11433/api/tags || echo "❌ Ollama Light is not healthy"
	@echo ""
	@echo "Ollama Main:"
	@curl -s http://localhost:11434/api/tags || echo "❌ Ollama Main is not healthy"
	@echo ""
	@echo "ChromaDB:"
	@curl -s http://localhost:8001/api/v2/heartbeat || echo "❌ ChromaDB is not healthy"

# テスト実行
test:
	@echo "🧪 テストを実行します..."
	docker-compose exec api pytest tests/ -v

# リンター
lint:
	@echo "🔍 リンターを実行します..."
	docker-compose exec api ruff check app/

# フォーマット
format:
	@echo "✨ コードをフォーマットします..."
	docker-compose exec api ruff format app/

# データベース状態確認
db-status:
	@echo "📊 データベースの状態を確認します..."
	@docker-compose exec mysql mysql -u aimee_user -pAimee2024! aimee_db -e "SHOW TABLES;"
	@echo ""
	@docker-compose exec mysql mysql -u aimee_user -pAimee2024! aimee_db -e "SELECT table_name, table_rows FROM information_schema.tables WHERE table_schema = 'aimee_db' ORDER BY table_name;"

# API動作確認
test-api:
	@echo "🧪 APIの動作確認を実行します..."
	@echo "Health Check:"
	@curl -s http://localhost:8000/health | jq '.' || echo "Failed"
	@echo ""
	@echo "API Version:"
	@curl -s http://localhost:8000/api/v1/status | jq '.' || echo "Failed"