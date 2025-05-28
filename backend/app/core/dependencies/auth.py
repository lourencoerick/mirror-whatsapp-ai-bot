from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload
from loguru import logger

from app.models.user import User
from app.models.account import Account
from app.models.account_user import AccountUser
from app.database import get_db

from app.api.routes.auth import verify_clerk_token

try:
    from clerk_backend_api import Clerk

    CLERK_SDK_AVAILABLE = True
except ImportError:
    CLERK_SDK_AVAILABLE = False
    logger.warning(
        "Clerk Python SDK (clerk_backend_api) not found. Admin role checks via Clerk API disabled."
    )

from app.config import get_settings

settings = get_settings()


class AuthContext:
    """Holds the authenticated internal user and their active account."""

    def __init__(self, internal_user: User, active_account: Account):
        """init

        Args:
            internal_user (User): internal_user
            active_account (Account): active_account
        """
        self.user: User = internal_user
        self.account: Account = active_account


# --- Função de Dependência ---
async def get_auth_context(
    payload: dict = Depends(verify_clerk_token),
    db: AsyncSession = Depends(get_db),  # Inject the database session
) -> AuthContext:
    """
    FastAPI dependency to retrieve the internal User and active Account
    based on the validated Clerk JWT payload.  Also sets the RLS context.

    Raises:
        HTTPException(401): If the 'sub' claim is missing in the token.
        HTTPException(403): If the user is not found in the internal DB
                            or is not associated with any account.
        HTTPException(500): If there's a database error or RLS context setting fails.

    Returns:
        AuthContext: An object containing the internal User and active Account.
    """
    clerk_sub = payload.get("sub")
    if not clerk_sub:
        logger.error("Missing 'sub' claim in verified Clerk token payload.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token state: Missing subject.",
        )

    logger.debug(f"Attempting to find internal user for clerk_sub: {clerk_sub}")

    try:
        stmt = (
            select(User)
            .options(selectinload(User.account_users).selectinload(AccountUser.account))
            .where(User.provider == "clerk", User.uid == clerk_sub)
        )

        result = await db.execute(stmt)
        user = result.scalars().first()

        if not user:
            logger.error(
                f"Authenticated user (provider=clerk, uid={clerk_sub}) not found in internal DB."
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account not provisioned. Please contact support.",
            )

        logger.debug(f"Found internal user ID: {user.id} for clerk_sub: {clerk_sub}")

        if not user.account_users:
            logger.error(
                f"Internal User {user.id} (clerk uid {clerk_sub}) has no associated accounts via AccountUser."
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has no associated account. Please contact support.",
            )

        # Lógica Simplificada: Assumir a primeira conta associada
        # TODO: Implementar lógica mais robusta se múltiplos accounts/user for possível
        # (ex: ler X-Account-Id header, buscar preferência do usuário, etc.)
        active_account_user_link = user.account_users[0]
        active_account = active_account_user_link.account

        if not active_account:
            logger.error(
                f"Data integrity issue: AccountUser {active_account_user_link.id} for User {user.id} links to a non-existent Account."
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error retrieving account information.",
            )

        logger.info(
            f"Auth context established: Internal User ID {user.id}, Active Account ID {active_account.id}"
        )

        if active_account and active_account.id:
            try:
                stmt = text(f"SET LOCAL my.app.account_id = '{str(active_account.id)}'")
                await db.execute(stmt)
                logger.debug(
                    f"[RLS] SET LOCAL my.app.account_id = {active_account.id} (via get_auth_context)"
                )

            except Exception as rls_error:
                logger.exception(
                    f"[RLS] Failed to set account_id {active_account.id} in get_auth_context"
                )
                await db.rollback()  # Rollback the transaction
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to set security context",
                ) from rls_error
        else:
            pass

        return AuthContext(internal_user=user, active_account=active_account)

    except Exception as e:
        logger.exception(f"Failed to establish auth context for clerk_sub {clerk_sub}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while processing authentication context.",
        ) from e


async def require_admin_user(
    auth_context: AuthContext = Depends(get_auth_context),
) -> AuthContext:
    """
    Dependency that ensures the current user has an admin role.
    Raises 401 if not authenticated,
    403 if not an admin,
    or 503 if the admin check cannot be performed.
    """
    if not auth_context.user or not auth_context.user.uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    user_is_admin = False

    # Approach 1: If 'role' is already on your internal User model
    if hasattr(auth_context.user, "role") and auth_context.user.role == "admin":
        user_is_admin = True

    # Approach 2 (more robust if internal User lacks 'role'): call Clerk API
    # Requires CLERK_SECRET_KEY set and clerk_backend_api installed.
    elif CLERK_SDK_AVAILABLE and settings.CLERK_SECRET_KEY:
        try:
            async with Clerk(bearer_auth=settings.CLERK_SECRET_KEY) as clerk:
                clerk_user = await clerk.users.get_async(user_id=auth_context.user.uid)
                # Check public or private metadata for admin role
                if clerk_user and clerk_user.public_metadata.get("role") == "admin":
                    user_is_admin = True
                elif clerk_user and clerk_user.private_metadata.get("role") == "admin":
                    user_is_admin = True
                else:
                    logger.warning(
                        f"User {auth_context.user.uid} does not have 'role: admin' in Clerk metadata."
                    )
        except Exception as e:
            logger.error(
                f"Error fetching metadata for user {auth_context.user.uid} from Clerk: {e}"
            )
            # Fail closed: deny admin access if check fails
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to verify admin permissions.",
            )
    else:
        logger.error(
            "Cannot determine admin role: Clerk SDK unavailable or secret key missing, and no 'role' on internal User."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin verification not properly configured.",
        )

    if not user_is_admin:
        logger.warning(f"Admin access DENIED for user {auth_context.user.uid}.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have administrator privileges.",
        )

    logger.info(f"Admin access GRANTED for user {auth_context.user.uid}.")
    return auth_context
