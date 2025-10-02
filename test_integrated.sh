#\!/bin/bash

echo "🧪 統合LLMテストを実行します..."

curl -X POST http://localhost:8000/api/v1/llm-test/integrated \
  -H "Content-Type: application/json" \
  -d '{
    "message": "札幌拠点でSS業務の補正工程に人員を配置したいです",
    "context": {"location_id": "91"},
    "detail": true
  }' \
  --max-time 120

echo ""
echo "✅ テスト完了"
