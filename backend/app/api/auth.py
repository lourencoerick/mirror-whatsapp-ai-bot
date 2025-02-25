import os
import json
import time
import requests
import jwt
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from jwt.algorithms import RSAAlgorithm

# Load environment variables
load_dotenv()

# Auth0 Configuration
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
API_AUDIENCE = os.getenv("API_AUDIENCE")
ALGORITHMS = ["RS256"]

router = APIRouter()
security = HTTPBearer()

# Cache for Auth0 public keys (avoids repetitive API calls)
JWK_CACHE = {"keys": None, "timestamp": 0}
JWK_CACHE_TTL = 600  # Cache TTL (10 minutes)


def get_jwk():
    """Fetches the public keys (JWK) from Auth0 to validate JWT tokens.

    Caches the keys for performance optimization.
    """
    global JWK_CACHE

    if JWK_CACHE["keys"] and (time.time() - JWK_CACHE["timestamp"] < JWK_CACHE_TTL):
        return JWK_CACHE["keys"]

    jwks_url = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
    response = requests.get(jwks_url)

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Could not retrieve JWKs")

    JWK_CACHE["keys"] = response.json()
    JWK_CACHE["timestamp"] = time.time()
    return JWK_CACHE["keys"]


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Validates the JWT token from Auth0.

    - Extracts the token from the `Authorization: Bearer <token>` header.
    - Retrieves the JWKs and verifies the token signature.
    - Ensures the token is valid and has the correct audience.
    - Returns the decoded payload if valid.
    """
    token = credentials.credentials
    jwks = get_jwk()

    try:
        # Extract header and key ID (kid)
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if not kid:
            raise HTTPException(status_code=401, detail="Token header missing 'kid'")

        # Retrieve the matching RSA public key
        rsa_key = next((key for key in jwks["keys"] if key["kid"] == kid), None)
        if not rsa_key:
            raise HTTPException(
                status_code=401, detail="Invalid token header: no matching key"
            )

        public_key = RSAAlgorithm.from_jwk(json.dumps(rsa_key))

        # Decode and verify JWT
        payload = jwt.decode(
            token, public_key, algorithms=ALGORITHMS, audience=API_AUDIENCE
        )

        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")

    except jwt.InvalidAudienceError:
        raise HTTPException(status_code=403, detail="Token audience is invalid")

    except jwt.JWTClaimsError:
        raise HTTPException(status_code=403, detail="Invalid token claims")

    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


@router.get("/protected")
async def protected_route(payload: dict = Depends(verify_token)):
    """Example of a protected route that requires a valid JWT token.

    - The `verify_token` function is used to validate the token.
    - If valid, the decoded user payload is returned.
    """
    return {"message": "Welcome!", "payload": payload}
