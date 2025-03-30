import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from app.api.routes import auth as auth_routes
from app.api.routes import message as message_routes
from app.api.routes import conversation as conversation_routes
from app.api.routes import inbox as inbox_routes
from app.api.routes import dev as dev_routes
from app.api.routes import websocket as ws_routes
from app.api.routes.webhooks import webhook as webhook_routes
from app.api.routes.webhooks import clerk as clerk_routes

from app.core.dependencies.auth import get_auth_context, AuthContext

from app.services.realtime.redis_pubsub import RedisPubSubBridge

from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv()

pubsub_bridge = RedisPubSubBridge()


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(pubsub_bridge.start())
    yield


# Create an instance of the FastAPI class
app = FastAPI(lifespan=lifespan)

# Get the frontend domain from environment variables
frontend_domain = os.getenv("FRONTEND_DOMAIN", "http://localhost:3000")
secret_key = os.getenv("SECRET_KEY", "my_secret_key")


# Add session middleware
app.add_middleware(
    SessionMiddleware, secret_key=secret_key, same_site="lax", https_only=False
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_domain],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dev_routes.router)

# Include the authentication router
app.include_router(auth_routes.router, prefix="/auth", tags=["Authentication"])

app.include_router(webhook_routes.router)
app.include_router(clerk_routes.router)


app.include_router(conversation_routes.router)
app.include_router(message_routes.router)
app.include_router(inbox_routes.router)


app.include_router(ws_routes.router)


@app.get("/")
def home():
    return {"message": "API FastAPI com Auth0"}


@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify if the application is running.

    Returns:
        dict: A dictionary containing the status of the application.
    """
    return {"status": "healthy"}


@app.get("/me")
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
        f"Serving /me request for User ID: {internal_user.id}, Account ID: {active_account.id}"
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
