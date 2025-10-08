"""
アラート基準判定サービス
管理者ノウハウ（RAGコンテキスト）に基づいてアラートを自動生成
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.logging import app_logger


class AlertService:
    """アラート基準判定とアラート生成を管理するサービス"""

    # やばい基準（rag_contextから取得したルール）
    ALERT_THRESHOLDS = {
        # 補正工程の残件数基準
        "correction_threshold_shinagawa": 50,   # 品川: 50件以上
        "correction_threshold_osaka": 100,      # 大阪: 100件以上

        # SS大量受領基準
        "ss_massive_threshold": 1000,           # SS受領1000件以上

        # 長時間配置基準
        "max_assignment_minutes": 60,           # 1時間以上は危険

        # 処理バランス基準
        "entry_balance_threshold": 0.3,         # エントリ1・2の差が30%以上
    }

    def __init__(self):
        """初期化"""
        pass

    async def check_all_alerts(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """
        全てのアラート基準をチェックして、該当するアラートを生成

        Args:
            db: データベースセッション

        Returns:
            アラートリスト
        """
        alerts = []

        try:
            # 1. 補正工程の残件数チェック
            correction_alerts = await self._check_correction_threshold(db)
            alerts.extend(correction_alerts)

            # 2. SS大量受領チェック
            ss_alerts = await self._check_ss_massive_threshold(db)
            alerts.extend(ss_alerts)

            # 3. 長時間配置チェック
            long_assignment_alerts = await self._check_long_assignment(db)
            alerts.extend(long_assignment_alerts)

            # 4. 処理バランスチェック
            balance_alerts = await self._check_entry_balance(db)
            alerts.extend(balance_alerts)

            app_logger.info(f"アラートチェック完了: {len(alerts)}件のアラートを生成")
            return alerts

        except Exception as e:
            app_logger.error(f"アラートチェックエラー: {e}")
            return []

    async def _check_correction_threshold(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """補正工程の残件数が基準を超えているかチェック"""
        alerts = []

        try:
            # TODO: progress_snapshotsテーブルから実際の残件数を取得
            # 現在は固定値で表示せず (アラート条件に該当するデータがないため非表示)
            pass

        except Exception as e:
            app_logger.error(f"補正工程チェックエラー: {e}")

        return alerts

    async def _check_ss_massive_threshold(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """SS大量受領をチェック"""
        alerts = []

        try:
            # TODO: 実際のDBから受領件数を取得
            # 現在は固定値で表示 (常にアラート表示)
            ss_received = 1269  # 固定値

            if ss_received >= self.ALERT_THRESHOLDS["ss_massive_threshold"]:
                alerts.append({
                    "type": "ss_massive",
                    "priority": "critical",
                    "title": "SS案件大量受領アラート",
                    "message": f"SS案件を{ss_received}件受領しました（基準: 1,000件以上）。納品1時間前に人員集中が必要です。",
                    "location_id": None,
                    "location_name": "全拠点",
                    "threshold": 1000,
                    "current_value": ss_received,
                    "rule_source": "processing_rule: SS大量時対応"
                })

        except Exception as e:
            app_logger.error(f"SS大量受領チェックエラー: {e}")

        return alerts

    async def _check_long_assignment(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """長時間配置をチェック"""
        alerts = []

        try:
            # TODO: 実際のdaily_assignmentsから長時間配置を検出
            # 現在は固定値で表示 (常にアラート表示)
            alerts.append({
                "type": "long_assignment",
                "priority": "medium",
                "title": "長時間配置の検出",
                "message": "オペレータID: a1234567 がエントリ1工程に90分配置されています（基準: 60分以上で集中力低下）。配置転換を検討してください。",
                "location_id": None,
                "location_name": None,
                "threshold": 60,
                "current_value": 90,
                "rule_source": "placement_rule: 長時間配置制限"
            })

        except Exception as e:
            app_logger.error(f"長時間配置チェックエラー: {e}")

        return alerts

    async def _check_entry_balance(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """エントリ1・2の処理バランスをチェック"""
        alerts = []

        try:
            # TODO: progress_snapshotsテーブルから実際のエントリ件数を取得
            # 現在は固定値で表示せず (アラート条件に該当するデータがないため非表示)
            pass

        except Exception as e:
            app_logger.error(f"エントリバランスチェックエラー: {e}")

        return alerts

    async def resolve_alert_with_ai(
        self,
        alert: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        アラートをAIで解消する提案を生成

        Args:
            alert: アラート情報
            db: データベースセッション

        Returns:
            解消提案
        """
        from app.services.integrated_llm_service import IntegratedLLMService

        try:
            # アラートから依頼文章を生成
            message = self._generate_message_from_alert(alert)

            # 統合LLMサービスで処理
            llm_service = IntegratedLLMService()
            result = await llm_service.process_message(
                message=message,
                context={
                    "alert_type": alert.get("type"),
                    "location": alert.get("location_name"),
                    "threshold": alert.get("threshold"),
                    "current_value": alert.get("current_value")
                },
                db=db,
                detail=True
            )

            return {
                "alert_id": alert.get("id"),
                "resolution": result.get("response"),
                "suggestion": result.get("suggestion"),
                "rag_results": result.get("rag_results"),
                "metadata": result.get("metadata")
            }

        except Exception as e:
            app_logger.error(f"アラート解消提案エラー: {e}")
            return {
                "alert_id": alert.get("id"),
                "error": str(e)
            }

    def _generate_message_from_alert(self, alert: Dict[str, Any]) -> str:
        """アラートから依頼文章を生成"""
        alert_type = alert.get("type")
        location = alert.get("location_name", "")
        threshold = alert.get("threshold")
        current_value = alert.get("current_value")

        if alert_type == "correction_threshold":
            return f"{location}の補正工程に{current_value}件の未処理があります（基準: {threshold}件）。人員を配置してください。"

        elif alert_type == "ss_massive":
            return f"SS案件を{current_value}件受領しました（基準: {threshold}件）。納品1時間前までに人員集中が必要です。対応策を提案してください。"

        elif alert_type == "long_assignment":
            return f"オペレータが1つの工程に{current_value}分配置されています（基準: {threshold}分以上で集中力低下）。配置転換を提案してください。"

        elif alert_type == "entry_balance":
            return f"エントリ1・2の処理バランスが悪化しています（差: {current_value}、基準: {threshold}以上）。バランス調整を提案してください。"

        else:
            return alert.get("message", "アラートが発生しています。対応策を提案してください。")
