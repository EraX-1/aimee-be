"""
データベース照会サービス
意図解析結果に基づいて適切なデータを取得
"""
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime, timedelta

from app.core.logging import app_logger


class DatabaseService:
    """データベースから業務データを取得するサービス"""
    
    async def fetch_data_by_intent(
        self, 
        intent: Dict[str, Any], 
        context: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        意図解析結果に基づいてデータを取得
        
        Args:
            intent: 意図解析結果
            context: 追加コンテキスト
            db: データベースセッション
            
        Returns:
            取得したデータ
        """
        intent_type = intent.get("intent_type")
        entities = intent.get("entities", {})
        location = entities.get("location") or context.get("location")
        process = entities.get("process") or context.get("process")
        
        app_logger.info(f"Fetching data for intent_type: {intent_type}, location: {location}, process: {process}")
        
        result = {}
        
        # 意図タイプに応じたデータ取得
        if intent_type == "delay_resolution":
            result = await self._fetch_delay_resolution_data(location, process, db)
        elif intent_type == "resource_allocation":
            result = await self._fetch_resource_allocation_data(location, process, db)
        elif intent_type == "status_check":
            result = await self._fetch_status_data(location, process, db)
        else:
            result = await self._fetch_general_data(location, db)
        
        return result
    
    async def _fetch_delay_resolution_data(
        self,
        location: Optional[str],
        process: Optional[str],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """遅延解決のためのデータ取得 (login_records_by_locationから実データ取得)"""
        data = {}

        # 1. 最新のログイン状況から配置状況を取得
        # 最新の1レコードのみを使用 (工程別にGROUP BY)
        assignment_query = text("""
            SELECT
                business_name,
                process_name,
                sapporo as 札幌,
                tokyo as 東京,
                osaka as 大阪,
                okinawa as 沖縄,
                sasebo as 佐世保,
                login_now,
                login_today,
                record_time
            FROM login_records_by_location
            WHERE business_name LIKE '%SS%'
              AND record_time = (
                  SELECT MAX(record_time) FROM login_records_by_location
              )
            ORDER BY process_name
        """)

        result = await db.execute(assignment_query)
        rows = result.fetchall()

        # データ整形
        current_assignments = []
        for row in rows:
            row_dict = dict(row._mapping)
            current_assignments.append({
                "business_name": row_dict["business_name"],
                "process_name": row_dict["process_name"],
                "札幌": row_dict["札幌"],
                "東京": row_dict["東京"],
                "大阪": row_dict["大阪"],
                "沖縄": row_dict["沖縄"],
                "佐世保": row_dict["佐世保"],
                "total_now": row_dict["login_now"],
                "total_today": row_dict["login_today"]
            })

        data["current_assignments"] = current_assignments
        app_logger.info(f"配置状況取得: {len(current_assignments)}件 (最新スナップショット)")

        # 2. 実オペレータデータから余剰・不足を分析
        # operator_process_capabilitiesから拠点×業務×工程別の人数を集計
        actual_allocation_query = text("""
            SELECT
                l.location_name,
                b.business_category,
                b.business_name,
                p.process_category,
                p.process_name,
                COUNT(DISTINCT o.operator_id) as operator_count
            FROM
                operators o
                INNER JOIN operator_process_capabilities opc ON o.operator_id = opc.operator_id
                INNER JOIN locations l ON o.location_id = l.location_id
                INNER JOIN businesses b ON opc.business_id = b.business_id
                INNER JOIN processes p ON opc.business_id = p.business_id AND opc.process_id = p.process_id
            WHERE
                o.is_valid = 1
                AND b.business_category IN ('新SS', '新SS+')
                AND b.business_name LIKE '%SS%'
            GROUP BY
                l.location_name, b.business_category, b.business_name, p.process_category, p.process_name
            ORDER BY
                p.process_name, l.location_name
        """)

        result = await db.execute(actual_allocation_query)
        actual_data = [dict(row._mapping) for row in result]

        surplus_locations = []
        shortage_locations = []

        for row in actual_data:
            loc_name = row["location_name"]
            process_name = row["process_name"]
            business_name = row["business_name"]
            count = row["operator_count"]
            category = row["business_category"]
            ocr_type = row["process_category"]

            # 3名以上なら余剰候補
            if count >= 3:
                surplus_locations.append({
                    "location_name": loc_name,
                    "process_name": process_name,
                    "business_name": business_name,
                    "business_category": category,
                    "process_category": ocr_type,
                    "current_count": count,
                    "surplus": count - 2
                })
            # 1名なら不足候補
            elif count == 1:
                shortage_locations.append({
                    "location_name": loc_name,
                    "process_name": process_name,
                    "business_name": business_name,
                    "business_category": category,
                    "process_category": ocr_type,
                    "current_count": count,
                    "shortage": 1
                })

        # ユーザーが特定の拠点+工程で「遅延」を報告した場合、強制的に不足候補に追加
        if location and process:
            user_specified_data = next(
                (row for row in actual_data
                 if row["location_name"] == location and row["process_name"] == process),
                None
            )

            if user_specified_data:
                already_in_shortage = any(
                    s["location_name"] == location and s["process_name"] == process
                    for s in shortage_locations
                )

                if not already_in_shortage:
                    app_logger.info(f"ユーザー指定の遅延拠点を不足候補に追加: {location} - {process}")
                    shortage_locations.append({
                        "location_name": user_specified_data["location_name"],
                        "process_name": user_specified_data["process_name"],
                        "business_name": user_specified_data["business_name"],
                        "business_category": user_specified_data["business_category"],
                        "process_category": user_specified_data["process_category"],
                        "current_count": user_specified_data["operator_count"],
                        "shortage": 10  # 遅延対応として10名程度の増員を想定
                    })

        data["available_resources"] = surplus_locations
        data["shortage_list"] = shortage_locations

        app_logger.info(f"余剰候補: {len(surplus_locations)}件, 不足候補: {len(shortage_locations)}件")

        # 余剰・不足の詳細ログ
        app_logger.info(f"余剰TOP5: {[(s.get('location_name'), s.get('process_name'), s.get('surplus')) for s in surplus_locations[:5]]}")
        app_logger.info(f"不足TOP5: {[(s.get('location_name'), s.get('process_name'), s.get('shortage')) for s in shortage_locations[:5]]}")

        # 3. 各拠点・工程で利用可能なオペレータを取得 (4階層情報を含む)
        operators_query = text("""
            SELECT
                o.operator_id,
                o.operator_name,
                l.location_name,
                b.business_category,
                b.business_name,
                p.process_category,
                p.process_name,
                opc.work_level
            FROM operators o
            JOIN locations l ON o.location_id = l.location_id
            LEFT JOIN operator_process_capabilities opc ON opc.operator_id = o.operator_id
            LEFT JOIN businesses b ON b.business_id = opc.business_id
            LEFT JOIN processes p ON p.business_id = opc.business_id AND p.process_id = opc.process_id
            WHERE o.is_valid = 1
              AND p.process_name IN ('エントリ1', 'エントリ2', '補正', 'SV補正', '目検')
            ORDER BY l.location_name, b.business_category, b.business_name, p.process_category, p.process_name, o.operator_name
        """)

        result = await db.execute(operators_query)
        operators_data = [dict(row._mapping) for row in result]

        # 拠点×業務×OCR区分×工程別にオペレータをグルーピング (4階層対応)
        operators_by_location_process = {}
        for op in operators_data:
            # 4階層をキーに含める
            key = (
                op.get("location_name"),
                op.get("business_category"),
                op.get("business_name"),
                op.get("process_category"),
                op.get("process_name")
            )
            if key not in operators_by_location_process:
                operators_by_location_process[key] = []
            operators_by_location_process[key].append(op)

        # 後方互換性のため、(location, process)のキーも作成
        operators_by_simple_key = {}
        for op in operators_data:
            simple_key = (op.get("location_name"), op.get("process_name"))
            if simple_key not in operators_by_simple_key:
                operators_by_simple_key[simple_key] = []
            operators_by_simple_key[simple_key].append(op)

        data["operators_by_location_process"] = operators_by_simple_key  # シンプルキー版
        data["operators_by_hierarchy"] = operators_by_location_process  # 4階層キー版

        app_logger.info(f"オペレータデータ取得: {len(operators_data)}件")
        
        # 4. 進捗スナップショット（活動状況の確認）
        if location:
            snapshot_query = text("""
                SELECT
                    snapshot_time,
                    total_waiting,
                    processing,
                    entry_count,
                    correction_waiting
                FROM progress_snapshots
                ORDER BY snapshot_id DESC
                LIMIT 10
            """)

            result = await db.execute(snapshot_query)
            data["recent_alerts"] = [dict(row._mapping) for row in result]
        
        return data
    
    async def _fetch_resource_allocation_data(
        self,
        location: Optional[str],
        process: Optional[str],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """リソース配分のためのデータ取得"""
        data = {}
        
        # 1. 全体のリソース状況（daily_assignmentsテーブルなしバージョン）
        resource_overview_query = text("""
            SELECT
                l.location_name,
                p.process_name,
                COUNT(DISTINCT o.operator_id) as total_employees,
                COUNT(DISTINCT opc.operator_id) as capable_count,
                5 as required_count
            FROM locations l
            CROSS JOIN (SELECT DISTINCT business_id, process_id, process_name FROM processes LIMIT 10) p
            LEFT JOIN operators o ON o.location_id = l.location_id AND o.is_valid = 1
            LEFT JOIN operator_process_capabilities opc ON opc.operator_id = o.operator_id
                AND opc.business_id = p.business_id AND opc.process_id = p.process_id
            WHERE (:location IS NULL OR l.location_name LIKE :location)
            AND (:process IS NULL OR p.process_name LIKE :process)
            GROUP BY l.location_id, p.business_id, p.process_id, l.location_name, p.process_name
            HAVING capable_count > 0
            ORDER BY l.location_name, p.process_name
            LIMIT 20
        """)
        
        result = await db.execute(
            resource_overview_query,
            {
                "location": f"%{location}%" if location else None,
                "process": f"%{process}%" if process else None
            }
        )
        data["resource_overview"] = [dict(row._mapping) for row in result]
        
        # 2. オペレータのスキル分布
        skill_distribution_query = text("""
            SELECT 
                l.location_name,
                p.process_name,
                opc.work_level as skill_level,
                COUNT(DISTINCT o.operator_id) as employee_count,
                AVG(owr.work_count) as avg_productivity
            FROM operators o
            JOIN locations l ON o.location_id = l.location_id
            JOIN operator_process_capabilities opc ON opc.operator_id = o.operator_id
            JOIN processes p ON p.business_id = opc.business_id AND p.process_id = opc.process_id
            LEFT JOIN operator_work_records owr ON owr.operator_id = o.operator_id
                AND owr.record_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            WHERE o.is_valid = 1
            AND (:location IS NULL OR l.location_name LIKE :location)
            AND (:process IS NULL OR p.process_name LIKE :process)
            GROUP BY l.location_id, p.business_id, p.process_id, opc.work_level, l.location_name, p.process_name
            ORDER BY l.location_name, p.process_name, opc.work_level DESC
        """)
        
        result = await db.execute(
            skill_distribution_query,
            {
                "location": f"%{location}%" if location else None,
                "process": f"%{process}%" if process else None
            }
        )
        data["skill_distribution"] = [dict(row._mapping) for row in result]
        
        return data
    
    async def _fetch_status_data(
        self,
        location: Optional[str],
        process: Optional[str],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """ステータス確認のためのデータ取得"""
        data = {}
        
        # 現在の運用状況サマリー（daily_assignmentsテーブルなしバージョン）
        status_query = text("""
            SELECT
                l.location_name,
                l.region,
                COUNT(DISTINCT o.operator_id) as total_employees,
                COUNT(DISTINCT opc.operator_id) as capable_operators,
                AVG(owr.work_count) as avg_productivity
            FROM locations l
            LEFT JOIN operators o ON o.location_id = l.location_id AND o.is_valid = 1
            LEFT JOIN operator_process_capabilities opc ON opc.operator_id = o.operator_id
            LEFT JOIN operator_work_records owr ON owr.operator_id = o.operator_id
                AND owr.record_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            WHERE (:location IS NULL OR l.location_name LIKE :location)
            GROUP BY l.location_id, l.location_name, l.region
            ORDER BY l.location_name
        """)
        
        result = await db.execute(
            status_query,
            {"location": f"%{location}%" if location else None}
        )
        data["status_summary"] = [dict(row._mapping) for row in result]
        
        return data
    
    async def _fetch_general_data(
        self,
        location: Optional[str],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """一般的なデータ取得"""
        data = {}
        
        # 拠点一覧
        locations_query = text("""
            SELECT 
                location_id,
                location_name,
                region
            FROM locations
            ORDER BY location_name
        """)
        
        result = await db.execute(locations_query)
        data["locations"] = [dict(row._mapping) for row in result]
        
        # プロセス一覧
        processes_query = text("""
            SELECT DISTINCT
                p.business_id,
                p.process_id,
                p.process_name,
                p.process_category,
                p.priority
            FROM processes p
            ORDER BY p.priority DESC, p.process_name
        """)
        
        result = await db.execute(processes_query)
        data["processes"] = [dict(row._mapping) for row in result]
        
        return data