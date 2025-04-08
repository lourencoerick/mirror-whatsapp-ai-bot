import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

# Import Routers
from app.api.routes import auth as auth_routes
from app.api.routes import message as message_routes
from app.api.routes import conversation as conversation_routes
from app.api.routes import inbox as inbox_routes
from app.api.routes import contact as contact_routes
from app.api.routes import me as me_routes
from app.api.routes import websocket as ws_routes
from app.api.routes.webhooks import clerk as clerk_routes
from app.api.routes import evolution_instance as evolution_instance_routes
from app.api.routes.webhooks.evolution import webhook as evolution_wb_routes

# Import Dependencies and Context
from app.core.dependencies.auth import get_auth_context, AuthContext

# Import Services/Config
from app.services.realtime.redis_pubsub import RedisPubSubBridge
from app.config import get_settings

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Initialization ---
pubsub_bridge = RedisPubSubBridge()
settings = get_settings()  # Load settings if needed for config below


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background tasks like Redis bridge
    logger.info("Starting Redis PubSub Bridge...")
    asyncio.create_task(pubsub_bridge.start())
    yield
    # Clean up resources if needed on shutdown
    logger.info("Stopping Redis PubSub Bridge (if applicable)...")
    # await pubsub_bridge.stop() # Add stop logic if needed


# Create FastAPI app instance
app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG, lifespan=lifespan)

# --- Middleware ---
# CORS Middleware (Essential for frontend interaction)
frontend_domain = os.getenv("FRONTEND_DOMAIN", "http://localhost:3000")
frontend_domain = "http://localhost:3000"
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_domain],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- API Routers (v1) ---
api_v1_prefix = "/api/v1"

logger.info(f"Including API routers under prefix: {api_v1_prefix}")

# Core API routes that the frontend will consume
app.include_router(
    auth_routes.router, prefix=f"{api_v1_prefix}/auth", tags=["v1 - Auth"]
)
app.include_router(
    conversation_routes.router, prefix=f"{api_v1_prefix}", tags=["v1 - Conversations"]
)
app.include_router(
    message_routes.router, prefix=f"{api_v1_prefix}", tags=["v1 - Messages"]
)
app.include_router(
    inbox_routes.router, prefix=f"{api_v1_prefix}", tags=["v1 - Inboxes"]
)
app.include_router(
    contact_routes.router, prefix=f"{api_v1_prefix}", tags=["v1 - Contacts"]
)

app.include_router(me_routes.router, prefix=f"{api_v1_prefix}", tags=["v1 - Me"])


# --- Evolution Instance Router ---
logger.info("Including Evolution Instance router")
app.include_router(
    evolution_instance_routes.router,
    prefix=f"{api_v1_prefix}",
    tags=["v1 - Evolution Instances"],
)


# --- Webhook Routers ---
logger.info("Including Webhook routers")
app.include_router(clerk_routes.router, prefix="", tags=["Clerk Webhooks"])
app.include_router(
    evolution_wb_routes.router, prefix="", tags=["Evolution Instance Webhooks"]
)

# --- WebSocket Router ---
logger.info("Including WebSocket router")
app.include_router(ws_routes.router, prefix="", tags=["WebSockets"])


# --- Root and Health Check ---
@app.get("/", tags=["Root"])
def home():
    # Consider removing the Auth0 message if not using Auth0
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
