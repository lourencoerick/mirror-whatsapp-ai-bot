# backend/app/api/routers/google_auth.py

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from google_auth_oauthlib.flow import Flow
from google.auth.exceptions import GoogleAuthError
from uuid import UUID

from app.database import get_db
from app.config import get_settings
from app.core.security import (
    encrypt_logical_token,
)  # Nosso utilitário de criptografia
from app.services.repository import (
    google_token as token_repo,
)  # Repositório para salvar o token

from app.core.dependencies.auth import (
    AuthContext,
    get_auth_context,
)

from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/google/auth", tags=["v1 - Google Auth"])

# URL para onde o usuário será enviado no frontend após o sucesso/falha
SETTINGS_PAGE_URL = f"{settings.FRONTEND_URL}/dashboard/settings"


@router.get("/authorize-url")
async def get_google_authorize_url(
    request: Request,
    auth_context: AuthContext = Depends(
        get_auth_context
    ),  # Precisamos saber quem é o usuário
):
    """
    Generates the Google OAuth2 authorization URL for the frontend to use.
    It also generates and stores a 'state' token in the user's session
    for CSRF protection during the callback.
    """
    # O redirect_uri deve ser a URL completa do nosso endpoint de callback
    redirect_uri = request.url_for("google_oauth_callback")

    logger.debug(f"Generated Redirect URI for Google: '{redirect_uri}'")
    flow = Flow.from_client_config(
        client_config={
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=settings.GOOGLE_AUTH_SCOPES,
        redirect_uri=redirect_uri,
    )

    authorization_url, state = flow.authorization_url(
        access_type="offline", prompt="consent"
    )

    # --- A PARTE CRUCIAL ---
    # Salvamos o state e o user_id na sessão ANTES de enviar a URL para o frontend.
    request.session["oauth_state"] = state
    request.session["user_id_for_oauth"] = str(auth_context.user.id)

    logger.info(
        f"Generated auth URL for user {auth_context.user.id} with state {state}"
    )

    return {"authorization_url": authorization_url}


@router.get("/callback", name="google_oauth_callback")
async def google_oauth_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
    state: str = None,  # O 'state' é passado como query param pelo Google
    code: str = None,  # O 'code' de autorização
    error: str = None,  # O Google envia 'error' se o usuário negar
):
    """
    Handles the OAuth2 callback from Google. This endpoint is intended to be
    used as the redirect_uri for a flow initiated by Clerk on the frontend.
    It exchanges the authorization code for a refresh token, encrypts it,

    and stores it in the database.
    """
    # Pega o state e o user_id que o frontend salvou na sessão ANTES de redirecionar
    session_state = request.session.pop("oauth_state", None)
    user_id_str = request.session.pop("user_id_for_oauth", None)

    redirect_uri = str(request.url_for("google_oauth_callback"))
    logger.debug(f"Using Redirect URI for fetch_token: '{redirect_uri}'")

    if error:
        logger.warning(f"Google OAuth flow denied by user: {error}")
        return RedirectResponse(url=f"{SETTINGS_PAGE_URL}?error=google_auth_denied")

    if not code or not state or state != session_state or not user_id_str:
        logger.error(
            f"code {code}  state: {state}  session_state: {session_state}  user id: {user_id_str} "
        )
        logger.error("OAuth callback error: Invalid state or missing code/user_id.")
        return RedirectResponse(url=f"{SETTINGS_PAGE_URL}?error=invalid_state")

    try:
        # Configura o 'flow' do google-auth-oauthlib para trocar o código.
        # É crucial que o redirect_uri aqui seja EXATAMENTE o mesmo que está
        # configurado no Google Cloud Console e que foi usado para iniciar o fluxo.
        flow = Flow.from_client_config(
            client_config={
                "web": {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=settings.GOOGLE_AUTH_SCOPES,  # Usa os mesmos escopos
            state=state,
            redirect_uri=redirect_uri,
        )

        # Troca o código recebido por credenciais (incluindo o refresh_token)
        flow.fetch_token(code=code)
        credentials = flow.credentials

        refresh_token = credentials.refresh_token
        if not refresh_token:
            logger.error(
                f"Refresh token not received from Google for user {user_id_str}."
            )
            return RedirectResponse(url=f"{SETTINGS_PAGE_URL}?error=no_refresh_token")

        # Criptografa e salva o token no nosso banco de dados
        encrypted_token = encrypt_logical_token(refresh_token)

        await token_repo.upsert_google_token(
            db=db,
            user_id=UUID(user_id_str),
            encrypted_refresh_token=encrypted_token,
            scopes=credentials.scopes,
        )
        await db.commit()
        logger.success(
            f"Successfully stored Google refresh token for user {user_id_str}."
        )
        return RedirectResponse(url=f"{SETTINGS_PAGE_URL}?success=google_connected")

    except Exception as e:
        logger.exception(
            f"Error during Google OAuth callback for user {user_id_str}: {e}"
        )
        await db.rollback()
        return RedirectResponse(url=f"{SETTINGS_PAGE_URL}?error=callback_failed")
