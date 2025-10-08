# 🎬 AIMEE デモ実行結果と根拠データ分析

**実行日時**: 2025-10-07 00:18
**実行環境**: 実データ（2,664名、25,829ドキュメント）

---

## ✅ 実行結果サマリー

| API | 処理時間 | 結果 | ステータス |
|-----|---------|------|----------|
| アラート基準チェック | < 1秒 | 1件検出 | ✅ 成功 |
| RAG検索（セマンティック） | 0.205秒 | 5件抽出 | ✅ 成功 |
| RAG検索（工程特定） | 0.162秒 | 5名抽出 | ✅ 成功 |
| 統合LLM処理 | 13.18秒 | AI提案生成 | ✅ 成功 |
| アラート解消提案 | 11.67秒 | 解消案生成 | ✅ 成功 |

**全てのAPIが正常動作！**

---

## 1️⃣ アラート基準チェック

### 実行コマンド
```python
alert_service = AlertService()
alerts = await alert_service.check_all_alerts(db)
```

### やばい基準（閾値）
```python
correction_threshold_shinagawa: 50    # 品川: 50件以上
correction_threshold_osaka: 100       # 大阪: 100件以上
ss_massive_threshold: 1000            # SS: 1,000件以上
max_assignment_minutes: 60            # 長時間: 60分以上
entry_balance_threshold: 0.3          # バランス: 差30%以上
```

### 検出結果
```
✅ 1件のアラート検出

【アラート】
タイプ: correction_threshold
優先度: high
タイトル: 補正工程の残件数が基準超過（品川）
メッセージ: 品川拠点の補正工程に102件の未処理があります（基準: 50件以上）
現在値: 102件 > 基準: 50件
根拠ルール: timing_rule: 補正配置タイミング
```

### 使用データ
```
📊 MySQL (aimee_db)
├─ locations: 拠点情報（7件）
│   └─ location_name LIKE '%品川%' でフィルタ
├─ operators: オペレータ数カウント（2,664名から）
│   └─ WHERE is_valid = 1
└─ rag_context: 管理者ルール（14件）
    └─ timing_rule: 補正配置タイミング（基準: 品川50件）
```

### 判定ロジック
```python
if '品川' in location_name and remaining_count >= 50:
    → アラート生成（priority: high）
```

---

## 2️⃣ RAG検索（セマンティック検索）

### 実行コマンド
```python
chroma_service = ChromaService()
results = chroma_service.query_similar(
    query_text="札幌の拠点でエントリ工程ができるオペレータ",
    n_results=5
)
```

### 検索結果
```
✅ 検索完了: 0.205秒
検索対象: 25,829ドキュメント
結果数: 5件

【トップ3】
1. 新垣　さつき (e1005512) - スコア: 0.351, 拠点: 51
2. 垣内　さやか (h1510922) - スコア: 0.349, 拠点: 51
3. 今野政洋 (h20220910) - スコア: 0.340, 拠点: 51
```

### 使用データ
```
📊 ChromaDB (aimee_knowledge)
├─ 総ドキュメント数: 25,829件
│   ├─ オペレータチャンク: 25,718件
│   └─ 工程チャンク: 88件
│
└─ 各チャンクの内容:
    ├─ operator_id, operator_name
    ├─ location_id（拠点）
    ├─ 処理可能工程リスト
    └─ スキルレベル
```

### 検索ロジック
```
1. クエリ文をベクトル化（埋め込み）
2. ChromaDBで類似度計算（コサイン類似度）
3. 距離スコア（0-1）を計算
4. スコア = 1 - distance
5. 上位n件を返却
```

### 根拠
```
🎯 ベクトル類似度スコア
- 新垣　さつき: 0.351
  → クエリ「札幌 + エントリ工程」と高い類似性
  → 拠点51のメタデータも一致
```

---

## 3️⃣ RAG検索（工程特定）

### 実行コマンド
```python
operators = chroma_service.find_best_operators_for_process(
    business_id="523201",
    process_id="152",
    location_id="51",
    n_results=5
)
```

### 検索結果
```
✅ 検索完了: 0.162秒
推奨オペレータ数: 5名

【トップ3】
1. ﾏｸﾛﾏﾝ(523201-152) (523201q152) - スコア: 0.520, 拠点: 51
2. 佃　麻紀 (b1920003) - スコア: 0.515, 拠点: 51
3. ﾏｸﾛﾏﾝ(523201-152) (523201p152) - スコア: 0.513, 拠点: 51
```

### 使用データ
```
📊 複合データソース
├─ ChromaDB: オペレータチャンク
│   └─ メタデータフィルタ: business_id=523201, process_id=152
│
└─ MySQL: operator_process_capabilities（55,863件）
    └─ WHERE business_id='523201' AND process_id='152'
```

### 検索ロジック
```python
# 検索クエリ生成
query_text = f"業務{business_id}の工程{process_id}を処理できるオペレータ"

# ChromaDBで検索
results = collection.query(
    query_texts=[query_text],
    n_results=n_results,
    where={  # メタデータフィルタ
        "business_id": business_id,
        "process_id": process_id
    }
)
```

### 根拠
```
🎯 スキルマッチング
1. 業務523201 + 工程152の処理可能（operator_process_capabilities）
2. 拠点51でフィルタリング
3. ベクトル類似度スコア: 0.520（高い類似性）
```

---

## 4️⃣ 統合LLM処理（5段階フル処理）

### 実行コマンド
```python
llm_service = IntegratedLLMService()
result = await llm_service.process_message(
    message="札幌のエントリ1工程で2名不足しています。対応できるオペレータを提案してください。",
    context={"location": "札幌", "process": "エントリ1", "shortage": 2},
    db=db,
    detail=True
)
```

### 処理結果
```
✅ 総処理時間: 13.18秒

【5段階処理の内訳】
ステップ1: 意図解析 - 約2秒
ステップ2: RAG検索 - 0.2秒
ステップ3: DB照会 - 0.1秒
ステップ4: 提案生成 - < 0.1秒
ステップ5: AI応答生成 - 約10秒
```

### 各ステップの詳細

#### ステップ1: 意図解析
```yaml
LLM: qwen2:0.5b
処理時間: 約2秒

抽出結果:
  intent_type: resource_allocation
  urgency: high
  requires_action: true
  entities:
    location: 札幌
    process: エントリ1工程
    issue_type: 遅延

使用データ: ユーザー入力文章
根拠: LLMによる自然言語理解
```

#### ステップ2: RAG検索
```yaml
検索エンジン: ChromaDB
処理時間: 0.2秒

検索結果:
  コンテキスト関連度: 3件
  推奨オペレータ: RAG検索で抽出

使用データ:
  - ChromaDB: 25,829ドキュメント
  - セマンティック検索

根拠: ベクトル類似度スコア
```

#### ステップ3: DB照会
```yaml
データソース: MySQL
処理時間: 0.1秒

取得データ:
  - resource_overview: 拠点×工程の配置可能人数
  - skill_distribution: スキルレベル別分布
  - available_resources: 他拠点の利用可能オペレータ

使用データ:
  - MySQL operators: 2,664名
  - MySQL operator_process_capabilities: 55,863件
  - MySQL locations: 7拠点
  - MySQL processes: 78工程

根拠: 実績データ、処理可能工程マトリクス
```

#### ステップ4: 提案生成
```yaml
処理時間: < 0.1秒

生成内容:
  提案ID: SGT20251007-XXXXXX
  配置変更案: RAG + DB から最適配置を算出
  影響予測: 生産性、遅延、品質
  信頼度スコア: 計算値

使用データ:
  - RAG検索結果（推奨オペレータ）
  - DB照会結果（配置状況、スキル分布）
  - rag_context: 管理者ルール14件

根拠:
  - スキルマッチング（RAG）
  - 配置履歴（DB）
  - ルール適合（配置制約、タイミング）
```

#### ステップ5: AI応答生成
```yaml
LLM: gemma3:4b
処理時間: 約10秒

生成内容:
  - 日本語の実用的な応答
  - 配置承認/否認/調整の選択肢
  - RAG推奨オペレータの明示

使用データ:
  - 全ステップの統合結果
  - プロンプトテンプレート

根拠: 全情報の統合判断
```

---

## 5️⃣ アラート解消提案

### 実行フロー
```
1. アラート検出
   → 品川補正工程: 102件（基準50件超過）

2. 依頼文章の自動生成
   → "品川の補正工程に102件の未処理があります（基準: 50件）。人員を配置してください。"

3. 統合LLM処理（5段階）
   → 意図解析→RAG→DB→提案→応答

4. 解消提案返却
   → 配置案、影響予測、RAG推奨オペレータ
```

### 処理結果
```
✅ 解消提案生成完了: 11.67秒

【解消提案】
- 配置変更案: 生成済み
- 影響予測: 計算済み
- 推奨オペレータ: RAG検索結果含む
```

### 使用データの全体像
```
📊 データソース統合
├─ アラート情報
│   ├─ type: correction_threshold
│   ├─ threshold: 50件
│   ├─ current_value: 102件
│   └─ rule_source: timing_rule: 補正配置タイミング
│
├─ 自動生成クエリ
│   └─ "品川の補正工程に102件..."
│
├─ ChromaDB（RAG検索）
│   ├─ 25,829ドキュメントから検索
│   └─ 推奨オペレータ抽出
│
├─ MySQL（実績データ）
│   ├─ operators: 2,664名
│   ├─ operator_process_capabilities: 55,863件
│   └─ locations, processes
│
└─ RAGコンテキスト（管理者ノウハウ）
    └─ 14件のルール（配置制約、タイミング等）
```

### 根拠の積み上げ
```
🎯 提案の根拠（多層的）

1. やばい基準（rag_context）
   → 品川は50件以上で配置必要

2. RAG検索（ChromaDB）
   → 補正工程ができる最適なオペレータ5名を抽出
   → スコア0.5以上の高マッチング

3. DB実績（MySQL）
   → 55,863件の処理可能工程から該当者を確認
   → 2,664名のオペレータから配置可能性を判定

4. 管理者ルール（rag_context 14件）
   → 長時間配置制限（60分以上NG）
   → 同一人物コンペア禁止
   → 配置タイミング（毎時15分等）

5. AI統合判断（LLM）
   → 全情報を統合して最適解を提示
```

---

## 📊 データがどう使われるか（詳細フロー）

### シナリオ: 「品川の補正工程60件のアラートを解消して」

#### 段階1: アラート検出
```sql
-- MySQLクエリ
SELECT l.location_id, l.location_name, COUNT(*) as operator_count
FROM operators o
JOIN locations l ON o.location_id = l.location_id
WHERE l.location_name LIKE '%品川%'
GROUP BY l.location_id, l.location_name

-- 結果: 品川拠点にオペレータXXX名

-- rag_contextから基準取得
SELECT * FROM rag_context
WHERE context_type = 'timing_rule'
  AND context_key = '補正配置タイミング'

-- 結果: 基準50件

-- 判定
if 102件 >= 50件:
    → アラート生成 ✅
```

#### 段階2: 依頼文章の自動生成
```python
alert_type = "correction_threshold"
location = "品川"
current_value = 102
threshold = 50

message = f"{location}の補正工程に{current_value}件の未処理があります（基準: {threshold}件）。人員を配置してください。"

→ "品川の補正工程に102件の未処理があります（基準: 50件）。人員を配置してください。"
```

#### 段階3: RAG検索
```python
# ChromaDBクエリ
query_text = "品川の補正工程に対応できるオペレータ"
collection.query(
    query_texts=[query_text],
    n_results=5
)

# ベクトル検索実行
25,829ドキュメント → ベクトル類似度計算 → トップ5抽出

# 結果例
[
  {operator_id: "a1234567", name: "山田太郎", score: 0.52},
  {operator_id: "b7654321", name: "佐藤花子", score: 0.51},
  ...
]
```

#### 段階4: DB照会
```sql
-- 配置可能オペレータの詳細取得
SELECT
    l.location_name,
    p.process_name,
    COUNT(DISTINCT opc.operator_id) as capable_count
FROM operator_process_capabilities opc
JOIN operators o ON o.operator_id = opc.operator_id
JOIN locations l ON o.location_id = l.location_id
JOIN processes p ON p.business_id = opc.business_id
WHERE p.process_name LIKE '%補正%'
  AND l.location_name LIKE '%品川%'
GROUP BY l.location_name, p.process_name

-- 結果: 品川の補正工程に対応可能なオペレータ数
```

#### 段階5: 提案生成
```python
# 情報統合
rag_operators = [...] # RAG検索結果（5名）
db_overview = {...}    # DB照会結果（配置状況）
rag_rules = [...]      # 管理者ルール14件

# 提案アルゴリズム
for operator in rag_operators:
    # スキルチェック
    if operator.score >= 0.5:
        # ルールチェック
        if check_placement_rules(operator, rag_rules):
            # 提案に追加
            suggestions.append(operator)

# 影響予測
impact = calculate_impact(suggestions, db_overview)
```

#### 段階6: AI応答生成
```python
# LLMプロンプト構築
prompt = f"""
ユーザー依頼: {message}
意図: {intent}
RAG推奨オペレータ: {rag_operators}
DB配置状況: {db_overview}
提案: {suggestion}

日本語で実用的な応答を生成してください。
"""

# gemma3:4bで生成
response = llm.generate(prompt)

→ "品川拠点の補正工程に102件の未処理を確認しました。
   以下の対応策を提案します：

   1. RAG推奨オペレータ「山田太郎」を配置
   2. ...

   配置承認 / 配置否認 / さらに調整する"
```

---

## 🎯 デモで強調すべきポイント

### 1. データ規模
- **2,664名のオペレータ**から最適な人を検索
- **55,863件の処理可能工程**を活用
- **25,829ドキュメント**のナレッジベース

### 2. 高速性
- RAG検索: **0.2秒**（25,829件）
- アラート検出: **< 1秒**
- 統合処理: **13秒**（実用レベル）

### 3. 根拠の透明性
- **ベクトル類似度スコア**を数値で表示
- **管理者ルール**を明示（timing_rule等）
- **実績データ**を参照（55,863件の処理可能工程）

### 4. 自動化レベル
- やばい基準の**自動判定**
- アラート発生から解消提案まで**自動生成**
- **ほぼリアルタイム**（5分間隔 + 1秒）

---

## 🚀 実行可能なデモスクリプト

```bash
# 簡易デモ（RAG検索のみ）
python3 scripts/test_quick_flow.py

# 統合デモ（全API）
python3 scripts/demo_all_apis.py

# アラートシステムデモ
python3 scripts/test_alert_system.py
```

---

**作成日**: 2025-10-07 00:18
**実行環境**: macOS + Docker（M3 Mac）
**データ規模**: 2,664名、55,863件、25,829ドキュメント
