import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from starlette.middleware.sessions import SessionMiddleware
from loguru import logger
import stripe
from typing import Optional
import redis.asyncio as aioredis

# Import Routers
from app.api.routes import auth as auth_routes
from app.api.routes import message as message_routes
from app.api.routes import conversation as conversation_routes
from app.api.routes import inbox as inbox_routes
from app.api.routes import contact as contact_routes
from app.api.routes import me as me_routes
from app.api.routes import websocket as ws_routes
from app.api.routes import evolution_instance as evolution_instance_routes
from app.api.routes.integrations import google_calendar as google_calendar_routes
from app.api.routes.webhooks import clerk as clerk_routes
from app.api.routes.webhooks.evolution import webhook as evolution_wb_routes
from app.api.routes.webhooks.whatsapp_cloud import webhook as whatsapp_cloud_wb_routes
from app.api.routes.webhooks.stripe import webhook as stripe_wb_routes
from app.api.routes import batch_contacts as batch_contacts_routes
from app.api.routes import research as research_routes
from app.api.routes import bot_agent as bot_agent_routes
from app.api.routes import company_profile as profile_routes
from app.api.routes import knowledge as knowledge_routes
from app.api.routes import simulation as simulation_routes
from app.api.routes import dashboard as dashboard_routes
from app.api.routes import billing as billing_routes
from app.api.routes import beta_tester as beta_routes
from app.api.routes import admin_beta as admin_beta_routes
from app.api.routes import google_auth as google_auth_routes

# Import Dependencies and Context
from app.core.dependencies.auth import get_auth_context, AuthContext
from app.core.dependencies.billing import require_active_subscription

# Import Services/Config
from app.services.realtime.redis_pubsub import RedisPubSubBridge
from app.config import get_settings


# Import functions from arq_manager
from app.core.arq_manager import init_arq_pool, close_arq_pool
from arq.connections import ArqRedis

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# --- Initialization ---
pubsub_bridge = RedisPubSubBridge()
settings = get_settings()
stripe.api_key = settings.STRIPE_SECRET_KEY

logger.info("Verifying environment variables...")
# Verify required environment variables
logger.info(f"GCS BUCKET: {settings.CONTACT_IMPORT_GCS_BUCKET_NAME}")
logger.info(f"Evolution URL: {settings.EVOLUTION_API_SHARED_URL}")

# Create FastAPI app instance
app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)


@asynccontextmanager
async def lifespan_manager(app: FastAPI):
    """
    Handles application startup and shutdown events.
    Initializes ARQ pool and starts background tasks like Redis bridge.
    """
    logger.info("Application startup sequence initiated...")

    # Initialize ARQ Redis pool
    logger.info("Initializing ARQ Redis pool...")
    await init_arq_pool()
    logger.info("ARQ Redis pool initialized.")

    # Start other background tasks like Redis bridge
    logger.info("Starting Redis PubSub Bridge...")
    pubsub_task = asyncio.create_task(pubsub_bridge.start())
    # You might want to add error handling or checks for pubsub_task startup

    try:
        yield
    finally:
        # Clean up resources on shutdown
        logger.info("Application shutdown sequence initiated...")

        # Stop Redis PubSub Bridge (ensure stop logic is safe)
        logger.info("Stopping Redis PubSub Bridge...")
        # Consider adding timeout or cancellation logic for the task if needed
        # await pubsub_bridge.stop() # Call your actual stop logic
        if "pubsub_task" in locals() and not pubsub_task.done():
            # Optional: Add cancellation logic if start() runs indefinitely
            # pubsub_task.cancel()
            # try:
            #     await pubsub_task
            # except asyncio.CancelledError:
            #     logger.info("PubSub bridge task cancelled.")
            pass

        # Close ARQ Redis pool
        logger.info("Closing ARQ Redis pool...")
        await close_arq_pool()
        logger.info("ARQ Redis pool closed.")

        logger.info("Application shutdown complete.")


app.router.lifespan_context = lifespan_manager


# --- Middleware ---
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

# CORS Middleware (Essential for frontend interaction)
allowed_origins_str = (
    settings.FRONTEND_ALLOWED_ORIGINS
    if settings.FRONTEND_ALLOWED_ORIGINS is not None
    else "http://localhost:3000"
)
allowed_origins_list = [origin.strip() for origin in allowed_origins_str.split(",")]

logger.info(f"Allowed origins for CORS: {allowed_origins_list}")
# CORS Middleware (Essential for frontend interaction)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET_KEY,
    same_site="lax",  # 'lax' é um bom padrão. 'none' exige https.
    https_only=True,  # Para desenvolvimento local com HTTP. Mude para True em produção.
)


common_protected_dependencies = [Depends(require_active_subscription)]

# --- API Routers (v1) ---
api_v1_prefix = "/api/v1"

logger.info(f"Including API routers under prefix: {api_v1_prefix}")

# Core API routes that the frontend will consume
app.include_router(
    auth_routes.router, prefix=f"{api_v1_prefix}/auth", tags=["v1 - Auth"]
)

app.include_router(
    google_auth_routes.router, prefix=f"{api_v1_prefix}", tags=["v1 - Google Auth"]
)


app.include_router(
    billing_routes.router, prefix=f"{api_v1_prefix}", tags=["v1 - Billing"]
)

app.include_router(
    me_routes.router,
    prefix=f"{api_v1_prefix}",
    tags=["v1 - Me"],
)

app.include_router(
    beta_routes.router,
    prefix=f"{api_v1_prefix}",
    tags=["v1 - Beta Program"],
)

app.include_router(
    admin_beta_routes.router,
    prefix=f"{api_v1_prefix}",
    tags=["v1 - Admin - Beta Program"],
)

app.include_router(
    conversation_routes.router,
    prefix=f"{api_v1_prefix}",
    tags=["v1 - Conversations"],
    dependencies=common_protected_dependencies,
)
app.include_router(
    message_routes.router,
    prefix=f"{api_v1_prefix}",
    tags=["v1 - Messages"],
    dependencies=common_protected_dependencies,
)
app.include_router(
    inbox_routes.router,
    prefix=f"{api_v1_prefix}",
    tags=["v1 - Inboxes"],
    dependencies=common_protected_dependencies,
)
app.include_router(
    contact_routes.router,
    prefix=f"{api_v1_prefix}",
    tags=["v1 - Contacts"],
    dependencies=common_protected_dependencies,
)

app.include_router(
    simulation_routes.router,
    prefix=f"{api_v1_prefix}",
    tags=["v1 - Simulation"],
    dependencies=common_protected_dependencies,
)

app.include_router(
    profile_routes.router,
    prefix=f"{api_v1_prefix}",
    tags=["v1 - Company Profile"],
    dependencies=common_protected_dependencies,  # Tag já está no router
)

app.include_router(
    bot_agent_routes.router,
    prefix=f"{api_v1_prefix}",
    tags=["v1 - Bot Agent"],
    dependencies=common_protected_dependencies,
)


app.include_router(
    batch_contacts_routes.router,
    prefix=f"{api_v1_prefix}",
    tags=["v1 - Contacts Batch Operations"],
    dependencies=common_protected_dependencies,
)


app.include_router(
    dashboard_routes.router,
    prefix=f"{api_v1_prefix}",
    tags=["v1 - Dashboard Metrics"],
    dependencies=common_protected_dependencies,
)


# --- Researcher Router ---
logger.info("Including Researcher router")
app.include_router(
    research_routes.router,
    prefix=f"{api_v1_prefix}",
    tags=["v1 - Researcher"],
    dependencies=common_protected_dependencies,
)

logger.info("Including Knowledge router")
app.include_router(
    knowledge_routes.router,
    prefix=f"{api_v1_prefix}",
    tags=["v1 - Knowledge"],
    dependencies=common_protected_dependencies,
)


# --- Evolution Instance Router ---
logger.info("Including Evolution Instance router")
app.include_router(
    evolution_instance_routes.router,
    prefix=f"{api_v1_prefix}",
    tags=["v1 - Evolution Instances"],
    dependencies=common_protected_dependencies,
)

# --- Integrations Routers ---
logger.info("Including Integrations routers")
app.include_router(
    google_calendar_routes.router,
    prefix=f"{api_v1_prefix}",
    tags=["Google Calendar Integration"],
)


# --- Webhook Routers ---
logger.info("Including Webhook routers")
app.include_router(clerk_routes.router, prefix="", tags=["Clerk Webhooks"])

app.include_router(
    evolution_wb_routes.router, prefix="", tags=["Evolution Instance Webhooks"]
)

app.include_router(
    whatsapp_cloud_wb_routes.router, prefix="", tags=["Whatsapp Cloud Webhooks"]
)

app.include_router(stripe_wb_routes.router, prefix="", tags=["Stripe Webhooks"])


# --- WebSocket Router ---
logger.info("Including WebSocket router")
app.include_router(ws_routes.router, prefix="", tags=["WebSockets"])


# --- Root and Health Check ---
@app.get("/", tags=["Root"])
def home():
    return {"message": f"{settings.APP_NAME} API"}


@app.get("/health", tags=["Health Check"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get(f"{api_v1_prefix}/me", tags=["v1 - Users"])
def get_authenticated_user_context(
    auth_context: AuthContext = Depends(get_auth_context),
):
    """
    Returns information about the authenticated user and their active context
    (internal user ID, active account ID, etc.).
    """
    internal_user = auth_context.user
    active_account = auth_context.account
    logger.info(
        f"Serving /api/v1/me request for User ID: {internal_user.id}, Account ID: {active_account.id}"
    )
    return {
        "message": "Authenticated and context established",
        "internal_user_id": internal_user.id,
        "user_name": internal_user.name,
        "user_email": internal_user.email,
        "clerk_user_id": internal_user.uid,
        "active_account_id": active_account.id,
        "active_account_name": active_account.name,
    }
