# backend/app/api/routers/admin_beta.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func as sql_func
from typing import List, Optional
from datetime import datetime, timezone

from app.database import get_db
from app.core.dependencies.auth import (
    AuthContext,
    get_auth_context,
    require_admin_user,
)  # Importar require_admin_user
from app.models.beta_tester import BetaTester, BetaStatusEnum
from app.api.schemas.admin_beta_tester import (
    AdminBetaTesterRead,
    AdminBetaTesterListResponse,
    AdminBetaActionResponse,
)
from loguru import logger

# (Opcional) Importar serviço de email
# from app.services.email_service import send_beta_approval_email, send_beta_denial_email

router = APIRouter(
    prefix="/admin/beta",  # Será /api/v1/admin/beta
    tags=["Admin - Beta Program"],
    dependencies=[Depends(require_admin_user)],  # Proteger todas as rotas de admin aqui
)


@router.get(
    "/requests",
    response_model=AdminBetaTesterListResponse,
    summary="List beta tester applications (Admin)",
)
async def list_beta_requests_admin(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: Optional[BetaStatusEnum] = Query(
        None, description="Filter by status"
    ),
    sort_by: str = Query(
        "requested_at", description="Field to sort by (e.g., requested_at, email)"
    ),
    sort_order: str = Query("desc", description="Sort order (asc or desc)"),
):
    offset = (page - 1) * size

    query = select(BetaTester)
    count_query = select(sql_func.count()).select_from(BetaTester)

    if status_filter:
        query = query.where(BetaTester.status == status_filter)
        count_query = count_query.where(BetaTester.status == status_filter)

    total_items = await db.scalar(count_query)
    if total_items is None:
        total_items = 0

    # Sorting
    sort_column = getattr(BetaTester, sort_by, BetaTester.requested_at)
    if sort_order.lower() == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    query = query.offset(offset).limit(size)

    result = await db.execute(query)
    items = result.scalars().all()

    return AdminBetaTesterListResponse(
        items=[AdminBetaTesterRead.model_validate(item) for item in items],
        total=total_items,
        page=page,
        size=size,
        # pages= (total_items + size - 1) // size # Cálculo de páginas totais
    )


@router.post(
    "/requests/{applicant_email}/approve",
    response_model=AdminBetaActionResponse,
    summary="Approve a beta tester application (Admin)",
)
async def approve_beta_request_admin(
    applicant_email: str,
    auth_context: AuthContext = Depends(
        require_admin_user
    ),  # Para pegar o ID do admin que aprovou
    db: AsyncSession = Depends(get_db),
):
    logger.info(
        f"Admin {auth_context.user.email if auth_context.user else 'N/A'} attempting to approve beta request for {applicant_email}"
    )

    stmt = select(BetaTester).where(BetaTester.email == applicant_email)
    beta_tester_entry = await db.scalar(stmt)

    if not beta_tester_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Beta applicant not found."
        )

    if beta_tester_entry.status == BetaStatusEnum.APPROVED:
        return AdminBetaActionResponse(
            message="Applicant already approved.",
            email=applicant_email,
            new_status=BetaStatusEnum.APPROVED,
        )

    beta_tester_entry.status = BetaStatusEnum.APPROVED
    beta_tester_entry.approved_at = datetime.now(timezone.utc)
    beta_tester_entry.approved_by_admin_id = (
        auth_context.user.uid if auth_context.user else None
    )  # Clerk User ID do admin

    db.add(beta_tester_entry)
    try:
        await db.commit()
        await db.refresh(beta_tester_entry)
        logger.success(
            f"Beta request for {applicant_email} approved by admin {auth_context.user.email if auth_context.user else 'N/A'}."
        )

        # TODO: Enviar email de aprovação para o usuário
        # await send_beta_approval_email(applicant_email, beta_tester_entry.contact_name)

        return AdminBetaActionResponse(
            message="Beta applicant approved successfully.",
            email=applicant_email,
            new_status=BetaStatusEnum.APPROVED,
        )
    except Exception as e:
        await db.rollback()
        logger.exception(f"Failed to approve beta request for {applicant_email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not approve beta request.",
        )


@router.post(
    "/requests/{applicant_email}/deny",
    response_model=AdminBetaActionResponse,
    summary="Deny a beta tester application (Admin)",
)
async def deny_beta_request_admin(
    applicant_email: str,
    auth_context: AuthContext = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    logger.info(
        f"Admin {auth_context.user.email if auth_context.user else 'N/A'} attempting to deny beta request for {applicant_email}"
    )

    stmt = select(BetaTester).where(BetaTester.email == applicant_email)
    beta_tester_entry = await db.scalar(stmt)

    if not beta_tester_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Beta applicant not found."
        )

    if beta_tester_entry.status == BetaStatusEnum.DENIED:
        return AdminBetaActionResponse(
            message="Applicant already denied.",
            email=applicant_email,
            new_status=BetaStatusEnum.DENIED,
        )

    beta_tester_entry.status = BetaStatusEnum.DENIED
    # Você pode querer limpar approved_at e approved_by_admin_id se estiver revertendo uma aprovação
    beta_tester_entry.approved_at = None
    beta_tester_entry.approved_by_admin_id = None  # Ou o ID do admin que negou

    db.add(beta_tester_entry)
    try:
        await db.commit()
        await db.refresh(beta_tester_entry)
        logger.success(
            f"Beta request for {applicant_email} denied by admin {auth_context.user.email if auth_context.user else 'N/A'}."
        )

        # TODO: (Opcional) Enviar email de negação para o usuário
        # await send_beta_denial_email(applicant_email, beta_tester_entry.contact_name)

        return AdminBetaActionResponse(
            message="Beta applicant denied successfully.",
            email=applicant_email,
            new_status=BetaStatusEnum.DENIED,
        )
    except Exception as e:
        await db.rollback()
        logger.exception(f"Failed to deny beta request for {applicant_email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not deny beta request.",
        )
