# backend/app/api/routers/beta.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, exists  # Importar exists

from app.database import get_db
from app.core.dependencies.auth import AuthContext, get_auth_context
from app.models.beta_tester import BetaTester, BetaStatusEnum
from app.api.schemas.beta_tester import (
    BetaTesterCreate,
    BetaTesterRead,
    BetaTesterStatusResponse,
    BetaRequestResponse,
)
from loguru import logger

# (Opcional) Importar serviço de email se for enviar notificações
# from app.services.email_service import send_beta_request_admin_notification, send_beta_request_confirmation

router = APIRouter(
    prefix="/beta",  # Será /api/v1/beta
    tags=["Beta Program"],
    dependencies=[
        Depends(get_auth_context)
    ],  # Todas as rotas aqui requerem autenticação
)


@router.post(
    "/request-access",
    response_model=BetaRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new beta program application",
)
async def request_beta_access(
    payload: BetaTesterCreate,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Allows an authenticated user to submit an application for the beta program.
    The user's email, user_id, and account_id are taken from their auth context.
    """
    user = auth_context.user
    account = auth_context.account

    if not user or not user.email or not account:  # Validação extra
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User authentication context is incomplete.",
        )

    # Verificar se já existe uma solicitação para este email
    stmt_exists = select(exists().where(BetaTester.email == user.email))
    email_exists = await db.scalar(stmt_exists)

    if email_exists:
        # Opcional: buscar a solicitação existente para retornar o status atual
        existing_request_stmt = select(BetaTester).where(BetaTester.email == user.email)
        existing_request = await db.scalar(existing_request_stmt)
        if existing_request:
            logger.warning(
                f"Beta access already requested for email {user.email}. Current status: {existing_request.status.value}"
            )
            # Não levantar erro, mas informar que já existe e qual o status
            return BetaRequestResponse(
                message="Você já solicitou acesso ao programa beta.",
                email=user.email,
                status=existing_request.status,
            )
        # Se por algum motivo exists é true mas não encontramos, é um estado estranho, mas prosseguir como se fosse novo
        # ou logar um erro mais sério. Por simplicidade, vamos tratar como se pudesse criar.

    logger.info(
        f"User {user.email} (Account: {account.id}) requesting beta access with payload: {payload.model_dump()}"
    )

    beta_tester_entry = BetaTester(
        email=user.email,
        user_id=user.id,  # Assumindo que user.id é o UUID interno do seu modelo User
        account_id=account.id,
        contact_name=payload.contact_name
        or user.name,  # Fallback para o nome do usuário do Clerk
        company_name=payload.company_name,
        company_website=(
            str(payload.company_website) if payload.company_website else None
        ),
        business_description=payload.business_description,
        beta_goal=payload.beta_goal,
        has_sales_team=payload.has_sales_team,
        sales_team_size=payload.sales_team_size,
        avg_leads_per_period=payload.avg_leads_per_period,
        current_whatsapp_usage=payload.current_whatsapp_usage,
        willing_to_give_feedback=payload.willing_to_give_feedback,
        status=BetaStatusEnum.PENDING_APPROVAL.value,  # Default, mas explícito aqui
    )

    try:
        db.add(beta_tester_entry)
        await db.commit()
        await db.refresh(beta_tester_entry)
        logger.success(
            f"Beta access request for {user.email} saved with status PENDING_APPROVAL."
        )

        # TODO: Enviar email para admin (opcional, mas recomendado)
        # await send_beta_request_admin_notification(admin_email="your_admin_email@example.com", applicant_email=user.email, details=payload)

        # TODO: Enviar email de confirmação para o usuário (opcional)
        # await send_beta_request_confirmation(user_email=user.email, user_name=beta_tester_entry.contact_name)

    except Exception as e:  # Captura erros de DB, etc.
        await db.rollback()
        logger.exception(f"Failed to save beta access request for {user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not process your beta access request at this time.",
        )

    return BetaRequestResponse(
        message="Sua solicitação de acesso ao programa beta foi recebida! Entraremos em contato em breve.",
        email=beta_tester_entry.email,
        status=beta_tester_entry.status,
    )


@router.get(
    "/my-status",
    response_model=BetaTesterStatusResponse,  # Pode ser BetaTesterRead se quiser retornar todos os dados
    summary="Get the current user's beta program application status",
)
async def get_my_beta_status(
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves the beta application status for the currently authenticated user.
    """
    user = auth_context.user
    if not user or not user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User email not available."
        )

    logger.debug(f"Fetching beta status for user {user.email}")

    stmt = select(BetaTester).where(BetaTester.email == user.email)
    beta_tester_entry = await db.scalar(stmt)

    if not beta_tester_entry:
        logger.info(f"No beta application found for user {user.email}.")
        # Retorna um objeto com campos nulos ou um status específico de "não encontrado"
        return BetaTesterStatusResponse(
            email=user.email, status=None, requested_at=None
        )
        # Alternativamente:
        # raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No beta application found for this user.")
        # A escolha depende de como o frontend prefere tratar "não encontrado".

    logger.info(
        f"Beta application found for user {user.email} with status: {beta_tester_entry.status.value}"
    )
    return BetaTesterStatusResponse(
        email=beta_tester_entry.email,
        status=beta_tester_entry.status,
        requested_at=beta_tester_entry.requested_at,
        # Adicione outros campos do BetaTesterRead se quiser retorná-los aqui
        # company_name=beta_tester_entry.company_name
    )
