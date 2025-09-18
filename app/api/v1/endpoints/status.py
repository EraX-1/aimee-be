from fastapi import APIRouter
from datetime import datetime
import random

from app.schemas.responses.status import (
    SystemStatusResponse,
    SystemAlert,
    SystemMetrics,
    LocationStatus
)
from app.core.logging import app_logger

router = APIRouter()


def generate_system_alerts():
    """システムアラートを生成（モック）"""
    alert_templates = [
        {
            "icon": "🔴",
            "message": "札幌エントリ1工程で遅延発生中",
            "severity": "warning",
            "location": "札幌"
        },
        {
            "icon": "🟡",
            "message": "品川で15分後に人員不足予測",
            "severity": "warning",
            "location": "品川"
        },
        {
            "icon": "🟢",
            "message": "盛岡の生産性が目標を10%上回っています",
            "severity": "info",
            "location": "盛岡"
        },
        {
            "icon": "🔵",
            "message": "システムメンテナンス: 明日2:00-3:00",
            "severity": "info",
            "location": None
        }
    ]
    
    # ランダムに2-3個のアラートを選択
    num_alerts = random.randint(2, 3)
    selected_alerts = random.sample(alert_templates, num_alerts)
    
    return [
        SystemAlert(**alert, timestamp=datetime.now())
        for alert in selected_alerts
    ]


def generate_location_status():
    """拠点別ステータスを生成（モック）"""
    locations = [
        {"name": "札幌", "total": 35, "productivity_base": 85},
        {"name": "盛岡", "total": 28, "productivity_base": 92},
        {"name": "品川", "total": 48, "productivity_base": 88},
        {"name": "西梅田", "total": 32, "productivity_base": 90},
        {"name": "本町東", "total": 26, "productivity_base": 87},
        {"name": "沖縄", "total": 20, "productivity_base": 85},
        {"name": "佐世保", "total": 15, "productivity_base": 83},
        {"name": "和歌山", "total": 22, "productivity_base": 86}
    ]
    
    status_list = []
    for loc in locations:
        # ランダムな変動を追加
        active_rate = random.uniform(0.85, 0.95)
        productivity_variation = random.uniform(-5, 5)
        delay = random.choice([0, 0, 0, 5, 10, 15, 20])  # 多くは遅延なし
        
        productivity = loc["productivity_base"] + productivity_variation
        
        # ステータス判定
        if delay >= 20 or productivity < 80:
            status = "critical"
        elif delay >= 10 or productivity < 85:
            status = "warning"
        else:
            status = "normal"
        
        status_list.append(LocationStatus(
            location=loc["name"],
            total_operators=loc["total"],
            active_operators=int(loc["total"] * active_rate),
            productivity_rate=round(productivity, 1),
            delay_minutes=delay,
            status=status
        ))
    
    return status_list


@router.get("", response_model=SystemStatusResponse, summary="システムステータス取得")
async def get_system_status():
    """
    システム全体のリアルタイムステータスを取得します。
    アラート、メトリクス、拠点別状況を含みます。
    """
    app_logger.info("Getting system status")
    
    # アラート生成
    alerts = generate_system_alerts()
    
    # メトリクス生成
    metrics = SystemMetrics(
        availability=random.uniform(97.0, 99.9),
        processed_cases=random.randint(1100, 1400),
        processed_delta=random.randint(-50, 200),
        avg_processing_time=round(random.uniform(3.5, 5.5), 1),
        active_operators=random.randint(140, 155)
    )
    
    # 拠点ステータス生成
    locations = generate_location_status()
    
    return SystemStatusResponse(
        alerts=alerts,
        metrics=metrics,
        locations=locations,
        last_updated=datetime.now()
    )


@router.get("/metrics", summary="詳細メトリクス取得")
async def get_detailed_metrics(
    period: str = "today"
):
    """
    詳細なシステムメトリクスを取得します。
    """
    app_logger.info(f"Getting detailed metrics for period: {period}")
    
    # 時間帯別のメトリクス（モック）
    hourly_data = []
    for hour in range(8, 18):  # 8:00-18:00
        hourly_data.append({
            "hour": f"{hour:02d}:00",
            "processed": random.randint(80, 150),
            "productivity": round(random.uniform(82, 95), 1),
            "active_operators": random.randint(130, 155)
        })
    
    return {
        "period": period,
        "hourly_metrics": hourly_data,
        "peak_hour": "14:00",
        "peak_productivity": 94.5,
        "total_processed": sum(h["processed"] for h in hourly_data)
    }


@router.get("/health", summary="ヘルスチェック")
async def health_check():
    """
    APIサーバーのヘルスチェック
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "AIMEE-Backend",
        "version": "1.0.0"
    }