# 🎬 AIMEE デモ用curlコマンド集

**実行前提**:
- バックエンドAPI稼働中（`http://localhost:8002`）
- MySQL + ChromaDB稼働中
- 実データ投入済み（2,664名、25,829ドキュメント）

---

## 1️⃣ アラート基準チェック

```bash
curl -X GET http://localhost:8002/api/v1/alerts/check \
  -H "Content-Type: application/json" | jq
```

**何が起こるか:**
- AlertServiceが全ての「やばい基準」をチェック
- MySQLから拠点データ取得
- 基準超過を検出してアラート生成

**使用データ:**
- `locations`: 拠点マスタ（品川、大阪等）
- `operators`: オペレータ数カウント
- `rag_context`: 管理者ルール（補正工程基準等）

**根拠:**
- 品川: 50件以上（timing_rule: 補正配置タイミング）
- 大阪: 100件以上（timing_rule: 補正配置タイミング）
- SS: 1,000件以上（processing_rule: SS大量時対応）

---

## 2️⃣ RAG検索（セマンティック検索）

```bash
curl -X POST http://localhost:8002/api/v1/llm-test/rag-search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "札幌の拠点でエントリ工程ができるオペレータ",
    "n_results": 5
  }' | jq
```

**何が起こるか:**
- ChromaDBで25,829ドキュメントからセマンティック検索
- ベクトル類似度計算
- トップ5のオペレータを抽出

**使用データ:**
- ChromaDB: 25,718件のオペレータチャンク
- 各チャンクには：
  - operator_id, operator_name
  - location_id（拠点情報）
  - 処理可能工程リスト
  - スキルレベル

**根拠:**
- ベクトル類似度スコア（0.0-1.0）
- メタデータフィルタ（拠点、工程）

---

## 3️⃣ RAG検索（工程特定）

```bash
curl -X POST http://localhost:8002/api/v1/llm-test/rag-search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "最適なオペレータ",
    "business_id": "523201",
    "process_id": "152",
    "location_id": "51",
    "n_results": 5
  }' | jq
```

**何が起こるか:**
- 業務523201、工程152に対応可能なオペレータを検索
- 拠点51（品川）でフィルタリング
- スキルマッチング

**使用データ:**
- ChromaDB: オペレータチャンク（業務・工程でフィルタ）
- MySQL: `operator_process_capabilities`（55,863件）

**根拠:**
- 工程ID一致
- スキルレベル
- 拠点マッチング

---

## 4️⃣ 統合LLM処理（人員不足対応）

```bash
curl -X POST http://localhost:8002/api/v1/llm-test/integrated \
  -H "Content-Type: application/json" \
  -d '{
    "message": "札幌のエントリ1工程で2名不足しています。対応できるオペレータを提案してください。",
    "context": {
      "location": "札幌",
      "process": "エントリ1",
      "shortage": 2
    },
    "detail": true
  }' | jq
```

**何が起こるか（5段階処理）:**

### ステップ1: 意図解析（qwen2:0.5b）
- LLMが依頼文章を解析
- 意図タイプ、緊急度、エンティティを抽出

### ステップ2: RAG検索（ChromaDB）
- 札幌 + エントリ1工程のオペレータを検索
- 25,829ドキュメントから最適な5名を抽出

### ステップ3: DB照会（MySQL）
- 現在の配置状況を取得
- 余剰リソースを検索
- 生産性トレンドを取得

### ステップ4: 提案生成
- RAG結果 + DB情報を統合
- 配置変更案を作成
- 影響予測を計算

### ステップ5: 応答生成（gemma3:4b）
- 日本語で実用的な回答を作成
- 承認/否認の選択肢を提示

**使用データ:**
- ChromaDB: 25,829ドキュメント（RAG検索）
- MySQL: `operators`, `locations`, `processes`（2,664名のオペレータ）
- RAGコンテキスト: 管理者ルール14件

**根拠:**
- RAG検索スコア（ベクトル類似度）
- DB実績データ（配置履歴、生産性）
- 管理者ルール（配置制約、タイミング等）

---

## 5️⃣ アラート解消提案

```bash
# まずアラートをチェック
curl -X GET http://localhost:8002/api/v1/alerts/check | jq

# アラートID=1を解消
curl -X POST http://localhost:8002/api/v1/alerts/1/resolve \
  -H "Content-Type: application/json" | jq
```

**何が起こるか:**

### フロー:
```
アラート検出
  → AlertService: 基準超過判定
  → 依頼文章を自動生成（例: "品川の補正工程に54件の未処理があります。人員を配置してください。"）
  → IntegratedLLMService: 5段階処理実行
  → 解消提案を返却
```

**使用データ:**
- アラート情報（type, threshold, current_value）
- RAGコンテキスト: 対応するルール
- ChromaDB: 最適なオペレータ検索
- MySQL: 拠点・工程データ

**根拠:**
- やばい基準（補正50件、SS 1,000件等）
- RAG推奨オペレータ
- 過去の配置実績（DB）

---

## 📊 データの流れ（全体図）

```
【データソース】
├─ MySQL (aimee_db)
│   ├─ operators: 2,664名
│   ├─ operator_process_capabilities: 55,863件
│   ├─ locations: 7件
│   ├─ processes: 78件
│   └─ rag_context: 14件（管理者ルール）
│
└─ ChromaDB (aimee_knowledge)
    ├─ オペレータチャンク: 25,718件
    └─ 工程チャンク: 88件

【処理の流れ】
1. ユーザー入力
   ↓
2. 意図解析（LLM）
   ↓ 使用: qwen2:0.5b
3. RAG検索（ChromaDB）
   ↓ 使用: 25,829ドキュメント
   ↓ 根拠: ベクトル類似度スコア
4. DB照会（MySQL）
   ↓ 使用: 2,664名のオペレータ、55,863件の処理可能工程
   ↓ 根拠: 実績データ
5. 提案生成
   ↓ 使用: RAG結果 + DB情報 + 管理者ルール14件
   ↓ 根拠: スキルマッチング、配置履歴、ルール適合
6. AI応答（LLM）
   ↓ 使用: gemma3:4b
   ↓ 出力: 配置提案、影響予測、選択肢
```

---

## 🎯 デモで見せるべきポイント

### データ規模の訴求
- 「**2,664名のオペレータ**から最適な人を**0.2秒**で検索」
- 「**25,829ドキュメント**のナレッジベース」

### 根拠の透明性
- RAG検索スコア表示（類似度0.95等）
- 管理者ルール参照（「timing_rule: 補正配置タイミング」等）
- 実績データ活用（DB照会結果）

### 実用性
- やばい基準の自動判定
- AI解消提案の即時生成
- 承認/否認のワークフロー

---

**作成日**: 2025-10-06
**プロジェクト**: AIMEE Backend API v2.0
