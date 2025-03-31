import os
import json
import time
from loguru import logger
import requests
import jwt
from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from jwt.algorithms import RSAAlgorithm
from typing import Dict, Any, Optional, List
from app.config import Settings, get_settings

# --- Configuration ---
settings: Settings = get_settings()
# Clerk configuration from environment variables
CLERK_JWKS_URL: str = settings.CLERK_JWKS_URL
CLERK_ISSUER: str = settings.CLERK_ISSUER
CLERK_AUDIENCE: str = settings.CLERK_AUDIENCE

# Validate essential configuration
if not CLERK_JWKS_URL:
    logger.error("Missing environment variable: CLERK_JWKS_URL")
    raise ValueError("Missing environment variable: CLERK_JWKS_URL")
if not CLERK_ISSUER:
    logger.error("Missing environment variable: CLERK_ISSUER")
    raise ValueError("Missing environment variable: CLERK_ISSUER")
# Add audience validation if it's strictly required for your setup
if not CLERK_AUDIENCE:
    logger.warning(
        "Missing environment variable: CLERK_AUDIENCE. Audience validation will be skipped."
    )


# JWT Algorithm
ALGORITHMS: List[str] = ["RS256"]

# --- JWK Caching ---

JWK_CACHE: Dict[str, Any] = {"keys": None, "timestamp": 0}
JWK_CACHE_TTL_SECONDS: int = 600  # Cache JWKs for 10 minutes


def get_jwks() -> Dict[str, Any]:
    """
    Fetches Clerk JSON Web Keys (JWKs) and caches them.

    Retrieves JWKs from the CLERK_JWKS_URL. Caches the keys for
    JWK_CACHE_TTL_SECONDS to avoid excessive requests.

    Returns:
        Dict[str, Any]: The JWKS dictionary containing the keys.

    Raises:
        HTTPException: If fetching the JWKs fails (status code 500).
    """
    now = time.time()

    # Check cache validity
    if JWK_CACHE["keys"] and (now - JWK_CACHE["timestamp"] < JWK_CACHE_TTL_SECONDS):
        logger.debug("Returning cached JWKs.")
        return JWK_CACHE["keys"]

    logger.info(f"Fetching new JWKs from {CLERK_JWKS_URL}")
    try:
        response = requests.get(CLERK_JWKS_URL, timeout=10)  # Added timeout
        response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)

        new_jwks = response.json()
        JWK_CACHE["keys"] = new_jwks
        JWK_CACHE["timestamp"] = now
        logger.info("Successfully fetched and cached new JWKs.")
        return new_jwks

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to retrieve JWKs: {e}", exc_info=True)
        # Don't update cache on failure, keep stale data if available? Or clear it?
        # For now, just raise error. If stale data is preferred, add logic here.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve JWKs from authentication provider.",
        ) from e


# --- Token Verification Dependency ---

# Initialize HTTPBearer security scheme
security = HTTPBearer()


def verify_clerk_token(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> Dict[str, Any]:
    """
    FastAPI dependency to verify a Clerk JWT bearer token.

    Args:
        credentials (HTTPAuthorizationCredentials): The credentials extracted
            by FastAPI's HTTPBearer scheme, containing the token.

    Returns:
        Dict[str, Any]: The validated token payload (claims).

    Raises:
        HTTPException:
            - 401 Unauthorized: If the token is missing, invalid, expired,
              has an invalid signature, or the required JWK is not found.
            - 403 Forbidden: If the token's claims (like audience or issuer)
              are invalid for this application.
            - 500 Internal Server Error: If JWKs cannot be fetched or processed.
    """
    token = credentials.credentials
    logger.debug("Attempting to verify token.")

    try:
        # 1. Get the Key ID (kid) from the token header
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        if not kid:
            logger.warning("Token header missing 'kid'.")
            # No original exception 'e' here, so no 'from e'
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token header: Missing 'kid'",
                headers={"WWW-Authenticate": "Bearer"},
            )
        logger.debug(f"Token 'kid': {kid}")

        # 2. Fetch JWKs (uses cache)
        jwks = get_jwks()  # This can raise HTTPException 500 if fetching fails

        # 3. Find the matching public key in JWKs
        rsa_key = next((key for key in jwks["keys"] if key["kid"] == kid), None)
        if not rsa_key:
            logger.warning(
                f"No matching JWK found for 'kid': {kid}. Forcing JWK refresh."
            )
            # Key might be new, try fetching JWKs again, bypassing cache once
            JWK_CACHE["keys"] = None  # Invalidate cache
            jwks = get_jwks()  # This can raise HTTPException 500
            rsa_key = next((key for key in jwks["keys"] if key["kid"] == kid), None)
            if not rsa_key:  # If still not found after refresh
                logger.error(
                    f"No matching JWK found for 'kid' {kid} even after refresh."
                )
                # No original exception 'e' here, so no 'from e'
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid token: Public key not found for kid '{kid}'",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        logger.debug(f"Found matching JWK for kid '{kid}'.")

        # 4. Convert the JWK to a public key object `pyjwt` understands
        try:
            public_key = RSAAlgorithm.from_jwk(json.dumps(rsa_key))
        except Exception as e:
            logger.error(f"Failed to convert JWK to public key: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process authentication key.",
            ) from e

        # 5. Decode and validate the token
        logger.debug(
            f"Decoding token with issuer='{CLERK_ISSUER}', audience='{CLERK_AUDIENCE}'"
        )
        payload = jwt.decode(
            token,
            public_key,
            algorithms=ALGORITHMS,
            # Only include audience if CLERK_AUDIENCE is set and expected
            audience=CLERK_AUDIENCE if CLERK_AUDIENCE else None,
            issuer=CLERK_ISSUER,
            leeway=30,  # Allow 30 seconds clock skew
            options={
                "verify_aud": CLERK_AUDIENCE
                is not None  # Only verify audience if configured
            },
        )

        logger.info(f"Token successfully verified for sub: {payload.get('sub')}")
        # You can access claims like payload['sub'] (user ID), payload['email'], etc.
        return payload

    # Specific JWT exceptions
    except jwt.ExpiredSignatureError as e:
        logger.warning("Token verification failed: Expired signature.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={
                "WWW-Authenticate": 'Bearer error="invalid_token", error_description="Token has expired"'
            },
        ) from e

    except jwt.InvalidAudienceError as e:
        logger.warning(
            f"Token verification failed: Invalid audience. Expected '{CLERK_AUDIENCE}'."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,  # Use 403 for invalid claims like audience/issuer
            detail="Invalid token audience",
            headers={
                "WWW-Authenticate": 'Bearer error="invalid_token", error_description="Invalid token audience"'
            },
        ) from e

    except jwt.InvalidIssuerError as e:
        logger.warning(
            f"Token verification failed: Invalid issuer. Expected '{CLERK_ISSUER}'."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid token issuer",
            headers={
                "WWW-Authenticate": 'Bearer error="invalid_token", error_description="Invalid token issuer"'
            },
        ) from e

    except jwt.InvalidSignatureError as e:
        logger.warning("Token verification failed: Invalid signature.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token signature",
            headers={
                "WWW-Authenticate": 'Bearer error="invalid_token", error_description="Invalid signature"'
            },
        ) from e

    except jwt.DecodeError as e:
        logger.warning(f"Token verification failed: Decode error - {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={
                "WWW-Authenticate": 'Bearer error="invalid_token", error_description="Token decode error"'
            },
        ) from e

    except jwt.InvalidTokenError as e:  # Catch-all for other JWT errors
        logger.warning(f"Token verification failed: Invalid token - {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,  # Or 403 if it's claim-related? 401 is safer default.
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        ) from e

    # Handle potential HTTPExceptions raised from get_jwks() or key conversion
    except HTTPException as e:
        # Re-raise the HTTPException to maintain original status code/detail
        # No 'from e' needed here as we are propagating the *same* exception
        raise e

    # Catch unexpected errors during verification
    except Exception as e:
        logger.error(
            f"An unexpected error occurred during token verification: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred during authentication.",
        ) from e


# --- Example Usage ---

router = APIRouter()


@router.get("/protected", summary="Example protected route")
async def protected_route(payload: Dict[str, Any] = Depends(verify_clerk_token)):
    """
    An example route protected by Clerk authentication.

    Requires a valid Bearer token in the Authorization header.
    The verified token payload is injected into the 'payload' argument.
    """
    user_id = payload.get("sub")  # Standard JWT claim for subject (user ID)
    # You can now use the user_id or other claims from the payload
    return {"message": f"Hello, authenticated user {user_id}!", "payload": payload}


@router.get("/public", summary="Example public route")
async def public_route():
    """
    An example route that does not require authentication.
    """
    return {"message": "This is a public endpoint."}
