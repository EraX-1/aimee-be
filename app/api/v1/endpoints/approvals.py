from fastapi import APIRouter, HTTPException, Path, Depends
from datetime import datetime, timedelta
import uuid
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.schemas.responses.approvals import (
    PendingApproval,
    ApprovalListResponse,
    ApprovalActionRequest,
    ApprovalActionResponse,
    ApprovalImpact,
    UrgencyLevel,
    ApprovalStatus
)
from app.schemas.responses.chat import AllocationChange
from app.core.logging import app_logger
from app.db.session import get_db

router = APIRouter()

# メモリ内での承認管理（実際はデータベースを使用）
pending_approvals_db = {}


async def save_approval_history(
    db: AsyncSession,
    suggestion_id: str,
    changes: list,
    impact: dict,
    action_type: str,
    action_user: str,
    action_user_id: str,
    feedback_reason: str = "",
    feedback_notes: str = "",
    reason: str = "",
    confidence_score: float = 0.0
):
    """承認履歴をDBに保存"""
    try:
        query = text("""
        INSERT INTO approval_history (
            suggestion_id,
            suggestion_type,
            changes,
            impact,
            reason,
            confidence_score,
            action_type,
            action_user,
            action_user_id,
            action_timestamp,
            feedback_reason,
            feedback_notes,
            execution_status
        ) VALUES (:suggestion_id, :suggestion_type, :changes, :impact, :reason,
                  :confidence_score, :action_type, :action_user, :action_user_id,
                  NOW(), :feedback_reason, :feedback_notes, :execution_status)
        """)

        await db.execute(query, {
            "suggestion_id": suggestion_id,
            "suggestion_type": "allocation_change",
            "changes": json.dumps(changes, ensure_ascii=False),
            "impact": json.dumps(impact, ensure_ascii=False),
            "reason": reason,
            "confidence_score": confidence_score,
            "action_type": action_type,
            "action_user": action_user,
            "action_user_id": action_user_id,
            "feedback_reason": feedback_reason,
            "feedback_notes": feedback_notes,
            "execution_status": "pending"
        })
        await db.commit()
        app_logger.info(f"Approval history saved: {suggestion_id}")

    except Exception as e:
        app_logger.error(f"Failed to save approval history: {e}")
        await db.rollback()
        raise


def generate_pending_approvals():
    """ダミーの承認待ちデータを生成"""
    
    approvals = [
        {
            "id": f"APV{datetime.now().year}-001",
            "changes": [
                {"from": "札幌", "to": "盛岡", "process": "エントリ2", "count": 3},
                {"from": "品川", "to": "札幌", "process": "エントリ1", "count": 2}
            ],
            "impact": {
                "capacity": 230,
                "delay_risk": "低",
                "delay_change": "-15%",
                "quality": "98.5%"
            },
            "urgency": UrgencyLevel.HIGH
        },
        {
            "id": f"APV{datetime.now().year}-002",
            "changes": [
                {"from": "西梅田", "to": "本町東", "process": "補正", "count": 4},
                {"from": "沖縄", "to": "西梅田", "process": "SV補正", "count": 1}
            ],
            "impact": {
                "capacity": 180,
                "delay_risk": "中",
                "delay_change": "-10%",
                "quality": "97.8%"
            },
            "urgency": UrgencyLevel.MEDIUM
        },
        {
            "id": f"APV{datetime.now().year}-003",
            "changes": [
                {"from": "佐世保", "to": "和歌山", "process": "目検", "count": 2}
            ],
            "impact": {
                "capacity": 150,
                "delay_risk": "低",
                "delay_change": "-5%",
                "quality": "99.1%"
            },
            "urgency": UrgencyLevel.LOW
        }
    ]
    
    # グローバル変数に保存
    for approval_data in approvals:
        approval = PendingApproval(
            id=approval_data["id"],
            timestamp=datetime.now() - timedelta(minutes=30),
            changes=[AllocationChange(**change) for change in approval_data["changes"]],
            impact=ApprovalImpact(**approval_data["impact"]),
            urgency=approval_data["urgency"],
            status=ApprovalStatus.PENDING,
            expires_at=datetime.now() + timedelta(hours=1),
            requested_by="AI"
        )
        pending_approvals_db[approval.id] = approval
    
    return list(pending_approvals_db.values())


@router.get("", response_model=ApprovalListResponse, summary="承認待ち一覧取得")
async def get_pending_approvals(
    status: str = "pending",
    urgency: str = None
):
    """
    承認待ちの配置変更提案一覧を取得します。
    """
    app_logger.info(f"Getting pending approvals: status={status}, urgency={urgency}")
    
    # 初回アクセス時にダミーデータを生成
    if not pending_approvals_db:
        generate_pending_approvals()
    
    # フィルタリング
    approvals = list(pending_approvals_db.values())

    # dictとPendingApprovalオブジェクトの両方に対応
    filtered_approvals = []
    for a in approvals:
        # dictの場合
        if isinstance(a, dict):
            if status and a.get("status") != status:
                continue
            if urgency and a.get("urgency") != urgency:
                continue
            filtered_approvals.append(a)
        # PendingApprovalオブジェクトの場合
        else:
            if status and a.status != status:
                continue
            if urgency and a.urgency != urgency:
                continue
            filtered_approvals.append(a)

    return ApprovalListResponse(
        approvals=filtered_approvals,
        total=len(filtered_approvals)
    )


@router.get("/{approval_id}", response_model=PendingApproval, summary="承認詳細取得")
async def get_approval_detail(
    approval_id: str = Path(..., description="承認ID")
):
    """
    指定された承認IDの詳細情報を取得します。
    """
    app_logger.info(f"Getting approval detail: {approval_id}")
    
    if approval_id not in pending_approvals_db:
        # ダミーデータを生成してみる
        if not pending_approvals_db:
            generate_pending_approvals()
    
    if approval_id in pending_approvals_db:
        return pending_approvals_db[approval_id]
    
    raise HTTPException(status_code=404, detail="承認情報が見つかりません")


@router.post("/{approval_id}/action", response_model=ApprovalActionResponse, summary="承認アクション実行")
async def execute_approval_action(
    approval_id: str = Path(..., description="承認ID"),
    request: ApprovalActionRequest = ...,
    db: AsyncSession = Depends(get_db)
):
    """
    配置変更提案に対して承認または却下を実行します。
    """
    app_logger.info(f"Executing approval action: {approval_id}, action={request.action}")
    
    if approval_id not in pending_approvals_db:
        raise HTTPException(status_code=404, detail="承認情報が見つかりません")
    
    approval = pending_approvals_db[approval_id]
    
    # ステータス確認
    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(
            status_code=400, 
            detail=f"この承認は既に処理済みです（ステータス: {approval.status}）"
        )
    
    # 有効期限確認
    if approval.expires_at < datetime.now():
        approval.status = ApprovalStatus.EXPIRED
        raise HTTPException(status_code=400, detail="この承認は有効期限切れです")
    
    # アクション実行
    if request.action == "approve":
        approval.status = ApprovalStatus.APPROVED
        message = "配置変更を承認しました"
        action_type = "approved"
        # 実際の実装では配置変更の実行処理を行う
    elif request.action == "reject":
        approval.status = ApprovalStatus.REJECTED
        message = "配置変更を却下しました"
        action_type = "rejected"
    else:
        raise HTTPException(status_code=400, detail="無効なアクションです")

    # 承認履歴をDBに保存
    try:
        # Pydantic v2対応: model_dump()を使用
        changes_list = []
        for c in approval.changes:
            if hasattr(c, 'model_dump'):
                changes_list.append(c.model_dump())
            elif hasattr(c, 'dict'):
                changes_list.append(c.dict())
            else:
                changes_list.append(dict(c))

        impact_dict = {}
        if approval.impact:
            if hasattr(approval.impact, 'model_dump'):
                impact_dict = approval.impact.model_dump()
            elif hasattr(approval.impact, 'dict'):
                impact_dict = approval.impact.dict()
            else:
                impact_dict = dict(approval.impact)

        # reasonとconfidence_scoreはPendingApprovalにないため、デフォルト値を使用
        reason = getattr(approval, 'reason', "AI提案による配置変更")
        confidence_score = getattr(approval, 'confidence_score', 0.85)

        await save_approval_history(
            db=db,
            suggestion_id=approval_id,
            changes=changes_list,
            impact=impact_dict,
            action_type=action_type,
            action_user=request.user or "system",
            action_user_id=request.user_id or "system",
            feedback_reason=request.reason or "",
            feedback_notes=request.notes or "",
            reason=reason,
            confidence_score=confidence_score
        )
        app_logger.info(f"承認履歴をDBに保存しました: {approval_id}")
    except Exception as e:
        app_logger.error(f"承認履歴の保存に失敗しました: {e}")
        # エラーでもAPIレスポンスは返す（ユーザー体験を損なわない）

    return ApprovalActionResponse(
        success=True,
        message=message,
        approval_id=approval_id,
        action=request.action,
        timestamp=datetime.now()
    )


@router.post("/bulk/approve", summary="一括承認")
async def bulk_approve(
    approval_ids: list[str]
):
    """
    複数の配置変更提案を一括で承認します。
    """
    app_logger.info(f"Bulk approving: {approval_ids}")
    
    results = []
    for approval_id in approval_ids:
        try:
            result = await execute_approval_action(
                approval_id,
                ApprovalActionRequest(action="approve")
            )
            results.append({"id": approval_id, "success": True})
        except Exception as e:
            results.append({"id": approval_id, "success": False, "error": str(e)})
    
    return {
        "results": results,
        "total": len(approval_ids),
        "succeeded": sum(1 for r in results if r.get("success"))
    }