from fastapi import APIRouter, Query, Path, HTTPException, Depends
from typing import Optional, List
from datetime import datetime, timedelta
import random
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.responses.alerts import (
    Alert,
    AlertListResponse,
    AlertDetailResponse,
    AlertType,
    AlertPriority,
    AlertStatus,
)
from app.services.alert_service import AlertService
from app.db.session import get_db
from app.core.logging import app_logger

router = APIRouter()


def generate_dummy_alerts() -> List[Alert]:
    """ダミーアラートデータを生成"""
    alerts = []
    
    alert_templates = [
        {
            "type": AlertType.ATTENDANCE,
            "priority": AlertPriority.HIGH,
            "title": "欠勤による人員不足",
            "message": "横浜拠点でデータ入力工程の人員が3名不足しています。",
            "location_id": 3,
            "location_name": "横浜",
        },
        {
            "type": AlertType.PRODUCTIVITY,
            "priority": AlertPriority.MEDIUM,
            "title": "生産性低下警告",
            "message": "補正処理工程の生産性が目標値を20%下回っています。",
            "location_id": 2,
            "location_name": "盛岡",
        },
        {
            "type": AlertType.SKILL_GAP,
            "priority": AlertPriority.LOW,
            "title": "スキル不足の検出",
            "message": "品質チェック工程で必要スキルレベル4の人員が不足しています。",
            "location_id": 1,
            "location_name": "札幌",
        },
        {
            "type": AlertType.WORKLOAD,
            "priority": AlertPriority.CRITICAL,
            "title": "業務量急増アラート",
            "message": "明日の業務量が通常の150%を超える予測です。緊急対応が必要です。",
            "location_id": 4,
            "location_name": "京都",
        },
        {
            "type": AlertType.SYSTEM,
            "priority": AlertPriority.LOW,
            "title": "データ同期遅延",
            "message": "RealWorksからのデータ同期に5分の遅延が発生しています。",
            "location_id": None,
            "location_name": None,
        },
    ]
    
    base_time = datetime.now()
    
    for i, template in enumerate(alert_templates * 3):  # 15件のアラートを生成
        alert = Alert(
            id=i + 1,
            type=template["type"],
            priority=template["priority"],
            status=random.choice([AlertStatus.NEW, AlertStatus.ACKNOWLEDGED, AlertStatus.IN_PROGRESS]),
            title=template["title"],
            message=template["message"],
            location_id=template.get("location_id"),
            location_name=template.get("location_name"),
            employee_id=None,
            employee_name=None,
            created_at=base_time - timedelta(hours=random.randint(0, 48)),
            updated_at=base_time - timedelta(hours=random.randint(0, 24)),
            acknowledged_at=None,
            resolved_at=None,
        )
        alerts.append(alert)
    
    return alerts


@router.get("/check", summary="アラート基準チェック")
async def check_alerts(
    db: AsyncSession = Depends(get_db)
):
    """
    現在の状況をチェックして、基準を超えているアラートを生成します。

    やばい基準:
    - 補正工程残件数: 品川50件以上、大阪100件以上
    - SS受領件数: 1,000件以上
    - 長時間配置: 60分以上
    - エントリバランス: 差30%以上
    """
    app_logger.info("アラート基準チェック開始")

    alert_service = AlertService()
    alerts = await alert_service.check_all_alerts(db)

    return {
        "message": "アラートチェック完了",
        "alert_count": len(alerts),
        "alerts": alerts,
        "checked_at": datetime.now().isoformat()
    }


@router.get("", response_model=AlertListResponse, summary="アラート一覧取得")
async def get_alerts(
    page: int = Query(1, ge=1, description="ページ番号"),
    page_size: int = Query(20, ge=1, le=100, description="1ページあたりの件数"),
    type: Optional[AlertType] = Query(None, description="アラート種別でフィルタ"),
    priority: Optional[AlertPriority] = Query(None, description="優先度でフィルタ"),
    status: Optional[AlertStatus] = Query(None, description="ステータスでフィルタ"),
    location_id: Optional[int] = Query(None, description="拠点IDでフィルタ"),
):
    """
    アラート一覧を取得します。
    各種フィルタリングオプションを使用して、必要なアラートのみを絞り込むことができます。
    """
    app_logger.info(f"Getting alerts - page: {page}, page_size: {page_size}, filters: type={type}, priority={priority}, status={status}, location_id={location_id}")

    all_alerts = generate_dummy_alerts()

    # フィルタリング
    filtered_alerts = all_alerts
    if type:
        filtered_alerts = [a for a in filtered_alerts if a.type == type]
    if priority:
        filtered_alerts = [a for a in filtered_alerts if a.priority == priority]
    if status:
        filtered_alerts = [a for a in filtered_alerts if a.status == status]
    if location_id:
        filtered_alerts = [a for a in filtered_alerts if a.location_id == location_id]

    # ページネーション
    total = len(filtered_alerts)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paged_alerts = filtered_alerts[start_idx:end_idx]

    return AlertListResponse(
        alerts=paged_alerts,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{alert_id}", response_model=AlertDetailResponse, summary="アラート詳細取得")
async def get_alert_detail(
    alert_id: int = Path(..., ge=1, description="アラートID"),
):
    """
    指定されたIDのアラート詳細情報を取得します。
    推奨アクションと関連アラートの情報も含まれます。
    """
    app_logger.info(f"Getting alert detail for ID: {alert_id}")
    
    all_alerts = generate_dummy_alerts()
    
    # 該当アラートを検索
    alert = None
    for a in all_alerts:
        if a.id == alert_id:
            alert = a
            break
    
    if not alert:
        raise HTTPException(status_code=404, detail="アラートが見つかりません")
    
    # 推奨アクションを生成
    recommended_actions = []
    if alert.type == AlertType.ATTENDANCE:
        recommended_actions = [
            "他拠点から応援人員を配置",
            "在宅勤務可能な従業員を緊急配置",
            "優先度の低い工程から人員を一時的に移動",
        ]
    elif alert.type == AlertType.PRODUCTIVITY:
        recommended_actions = [
            "熟練者を配置して生産性を向上",
            "作業手順の見直しと改善",
            "休憩時間の調整による効率化",
        ]
    elif alert.type == AlertType.SKILL_GAP:
        recommended_actions = [
            "スキルトレーニングの実施",
            "熟練者とのペア作業を設定",
            "一時的に他拠点から熟練者を配置",
        ]
    elif alert.type == AlertType.WORKLOAD:
        recommended_actions = [
            "全拠点での人員配置見直し",
            "残業対応の事前調整",
            "外部リソースの活用検討",
        ]
    else:
        recommended_actions = [
            "システム管理者に連絡",
            "手動でのデータ確認実施",
        ]
    
    # 関連アラートID（ダミー）
    related_alerts = [i for i in range(1, 16) if i != alert_id][:3]
    
    return AlertDetailResponse(
        alert=alert,
        recommended_actions=recommended_actions,
        related_alerts=related_alerts,
    )


@router.post("/{alert_id}/acknowledge", summary="アラート確認")
async def acknowledge_alert(
    alert_id: int = Path(..., ge=1, description="アラートID"),
):
    """
    指定されたアラートを確認済みとしてマークします。
    """
    app_logger.info(f"Acknowledging alert ID: {alert_id}")

    all_alerts = generate_dummy_alerts()

    # 該当アラートを検索
    alert_exists = any(a.id == alert_id for a in all_alerts)

    if not alert_exists:
        raise HTTPException(status_code=404, detail="アラートが見つかりません")

    return {
        "message": "アラートを確認しました",
        "alert_id": alert_id,
        "acknowledged_at": datetime.now().isoformat(),
    }


@router.post("/{alert_id}/resolve", summary="アラート解消提案")
async def resolve_alert(
    alert_id: int = Path(..., ge=1, description="アラートID"),
    db: AsyncSession = Depends(get_db)
):
    """
    指定されたアラートをAIで解消する提案を生成します。

    例: 「補正工程60件のアラートを解消して」→ 最適なオペレータ配置案を提案
    """
    app_logger.info(f"アラート解消提案生成: ID {alert_id}")

    # まずアラートを生成してIDで検索
    alert_service = AlertService()
    all_alerts = await alert_service.check_all_alerts(db)

    # 該当アラートを検索（IDではなくtypeで検索）
    # 実際の実装ではDBに保存されたアラートを取得
    if alert_id > len(all_alerts):
        raise HTTPException(status_code=404, detail="アラートが見つかりません")

    target_alert = all_alerts[min(alert_id - 1, len(all_alerts) - 1)] if all_alerts else None

    if not target_alert:
        raise HTTPException(status_code=404, detail="アラートが見つかりません")

    # AIで解消提案を生成
    resolution = await alert_service.resolve_alert_with_ai(target_alert, db)

    return resolution