import os
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from app.middleware.account_context import AccountContextMiddleware
from fastapi.middleware.cors import CORSMiddleware
from app.api.auth import router as auth_router
from app.api.routes import webhook as webhook_routes
from app.api.routes import conversation as conversation_routes
from app.api.routes import dev as dev_routes


from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv()

# Create an instance of the FastAPI class
app = FastAPI()

# Get the frontend domain from environment variables
frontend_domain = os.getenv("FRONTEND_DOMAIN", "http://localhost:3001")
secret_key = os.getenv("SECRET_KEY", "my_secret_key")


app.add_middleware(AccountContextMiddleware)

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
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])

app.include_router(webhook_routes.router)

app.include_router(conversation_routes.router)


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
