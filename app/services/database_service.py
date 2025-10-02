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
        """遅延解決のためのデータ取得"""
        data = {}
        
        # 1. 現在の配置状況
        if location:
            current_assignment_query = text("""
                SELECT 
                    da.assignment_id,
                    l.location_name,
                    p.process_name,
                    COUNT(da.operator_id) as allocated_count,
                    5 as required_count,
                    (5 - COUNT(da.operator_id)) as shortage,
                    da.assignment_date
                FROM daily_assignments da
                JOIN locations l ON da.location_id = l.location_id
                LEFT JOIN processes p ON da.business_id = p.business_id AND da.process_id = p.process_id
                WHERE l.location_name LIKE :location
                AND da.assignment_date = CURDATE()
                GROUP BY da.assignment_id, l.location_name, p.process_name, da.assignment_date
                ORDER BY shortage DESC
            """)
            
            result = await db.execute(
                current_assignment_query,
                {"location": f"%{location}%"}
            )
            data["current_assignments"] = [dict(row._mapping) for row in result]
            
            # 特定の工程がある場合は絞り込み
            if process and data["current_assignments"]:
                data["target_process"] = [
                    a for a in data["current_assignments"] 
                    if process in a.get("process_name", "")
                ]
        
        # 2. 過去7日間の作業実績トレンド
        productivity_query = text("""
            SELECT 
                DATE(owr.record_date) as date,
                l.location_name,
                p.process_name,
                AVG(owr.work_count) as avg_productivity,
                COUNT(DISTINCT owr.operator_id) as employee_count
            FROM operator_work_records owr
            JOIN locations l ON owr.location_id = l.location_id
            LEFT JOIN processes p ON owr.business_id = p.business_id AND owr.process_id = p.process_id
            WHERE owr.record_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            AND (:location IS NULL OR l.location_name LIKE :location)
            AND (:process IS NULL OR p.process_name LIKE :process)
            GROUP BY DATE(owr.record_date), l.location_name, p.process_name
            ORDER BY date DESC
        """)
        
        result = await db.execute(
            productivity_query,
            {
                "location": f"%{location}%" if location else None,
                "process": f"%{process}%" if process else None
            }
        )
        data["productivity_trends"] = [dict(row._mapping) for row in result]
        
        # 3. 他拠点のオペレータ状況
        surplus_query = text("""
            SELECT 
                l.location_name,
                p.process_name,
                COUNT(DISTINCT da.operator_id) as allocated_count,
                5 as required_count,
                (COUNT(DISTINCT da.operator_id) - 5) as surplus,
                GROUP_CONCAT(
                    DISTINCT o.operator_name 
                    SEPARATOR ', '
                ) as available_employees
            FROM daily_assignments da
            JOIN locations l ON da.location_id = l.location_id
            LEFT JOIN processes p ON da.business_id = p.business_id AND da.process_id = p.process_id
            LEFT JOIN operators o ON da.operator_id = o.operator_id
            WHERE da.assignment_date = CURDATE()
            AND (:process IS NULL OR p.process_name LIKE :process)
            GROUP BY l.location_id, p.process_id, l.location_name, p.process_name
            HAVING surplus > 0
            ORDER BY surplus DESC
            LIMIT 10
        """)
        
        result = await db.execute(
            surplus_query,
            {"process": f"%{process}%" if process else None}
        )
        data["available_resources"] = [dict(row._mapping) for row in result]
        
        # 4. ログイン記録（活動状況の確認）
        if location:
            login_query = text("""
                SELECT 
                    lr.business_name,
                    lr.process_name,
                    lr.login_count,
                    lr.record_time
                FROM login_records lr
                WHERE lr.record_time >= DATE_FORMAT(DATE_SUB(NOW(), INTERVAL 24 HOUR), '%Y%m%d%H%i')
                ORDER BY lr.record_time DESC
                LIMIT 10
            """)
            
            result = await db.execute(login_query)
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
        
        # 1. 全体のリソース状況
        resource_overview_query = text("""
            SELECT 
                l.location_name,
                p.process_name,
                COUNT(DISTINCT o.operator_id) as total_employees,
                COUNT(DISTINCT da.operator_id) as present_count,
                5 as required_count,
                COUNT(DISTINCT da.operator_id) as allocated_count
            FROM locations l
            CROSS JOIN (SELECT DISTINCT business_id, process_id, process_name FROM processes) p
            LEFT JOIN operators o ON o.location_id = l.location_id
            LEFT JOIN operator_process_capabilities opc ON opc.operator_id = o.operator_id 
                AND opc.business_id = p.business_id AND opc.process_id = p.process_id
            LEFT JOIN daily_assignments da ON da.location_id = l.location_id
                AND da.business_id = p.business_id AND da.process_id = p.process_id
                AND da.assignment_date = CURDATE()
            WHERE (:location IS NULL OR l.location_name LIKE :location)
            AND (:process IS NULL OR p.process_name LIKE :process)
            GROUP BY l.location_id, p.business_id, p.process_id, l.location_name, p.process_name
            ORDER BY l.location_name, p.process_name
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
        
        # 現在の運用状況サマリー
        status_query = text("""
            SELECT 
                l.location_name,
                COUNT(DISTINCT p.process_id) as process_count,
                COUNT(DISTINCT o.operator_id) as total_employees,
                COUNT(DISTINCT da.operator_id) as total_allocated,
                COUNT(DISTINCT da.operator_id) * 5 as total_required,
                AVG(owr.work_count) as avg_productivity,
                COUNT(DISTINCT lr.login_id) as active_alerts
            FROM locations l
            LEFT JOIN operators o ON o.location_id = l.location_id AND o.is_valid = 1
            LEFT JOIN daily_assignments da ON da.location_id = l.location_id
                AND da.assignment_date = CURDATE()
            LEFT JOIN operator_work_records owr ON owr.operator_id = o.operator_id
                AND owr.record_date = CURDATE()
            LEFT JOIN login_records lr ON lr.record_time = DATE_FORMAT(NOW(), '%Y%m%d%H%i')
            LEFT JOIN processes p ON da.business_id = p.business_id AND da.process_id = p.process_id
            WHERE (:location IS NULL OR l.location_name LIKE :location)
            GROUP BY l.location_id, l.location_name
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