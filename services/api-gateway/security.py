import asyncio
import base64
import json
import time
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from fastapi import Depends, Request
from jwt import InvalidTokenError
from jwt.algorithms import RSAAlgorithm

from config import Settings, get_settings
from errors import GatewayAuthError


def _b64url_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, byteorder="big")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


@dataclass(frozen=True)
class AuthContext:
    subject: str
    email: str | None
    role: str | None
    claims: dict[str, Any]


class JwksCache:
    def __init__(self) -> None:
        self._keys: list[dict[str, Any]] = []
        self._expires_at: float = 0
        self._lock = asyncio.Lock()

    def _resolve_key(self, kid: str | None) -> dict[str, Any] | None:
        if kid is None and len(self._keys) == 1:
            return self._keys[0]
        for key in self._keys:
            if key.get("kid") == kid:
                return key
        return None

    async def get_key(
        self,
        *,
        kid: str | None,
        request: Request,
        settings: Settings,
    ) -> dict[str, Any]:
        now = time.time()
        if not self._keys or now >= self._expires_at:
            await self.refresh(request=request, settings=settings)

        key = self._resolve_key(kid)
        if key is not None:
            return key

        await self.refresh(request=request, settings=settings, force=True)
        key = self._resolve_key(kid)
        if key is None:
            raise GatewayAuthError(
                status_code=401,
                code="invalid_token",
                message="Token signing key is not recognized.",
                details={"kid": kid},
                headers={"WWW-Authenticate": "Bearer"},
            )
        return key

    async def refresh(
        self,
        *,
        request: Request,
        settings: Settings,
        force: bool = False,
    ) -> None:
        async with self._lock:
            now = time.time()
            if not force and self._keys and now < self._expires_at:
                return

            transport = getattr(request.app.state, "upstream_transport", None)
            async with httpx.AsyncClient(
                base_url=str(settings.researcher_auth_base_url),
                timeout=settings.upstream_timeout_seconds,
                transport=transport,
            ) as client:
                response = await client.get(settings.auth_jwks_path)
            response.raise_for_status()

            payload = response.json()
            keys = payload.get("keys")
            if not isinstance(keys, list) or not keys:
                raise GatewayAuthError(
                    status_code=503,
                    code="jwks_unavailable",
                    message="Gateway could not load signing keys.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            self._keys = keys
            self._expires_at = now + settings.auth_jwks_cache_ttl_seconds


async def get_auth_context(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> AuthContext:
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise GatewayAuthError(
            status_code=401,
            code="missing_bearer_token",
            message="Bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise GatewayAuthError(
            status_code=401,
            code="invalid_authorization_header",
            message="Authorization header must use Bearer token format.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        unverified_header = jwt.get_unverified_header(token)
    except InvalidTokenError as exc:
        raise GatewayAuthError(
            status_code=401,
            code="invalid_token",
            message="Bearer token is malformed.",
            details={"reason": exc.__class__.__name__},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    cache: JwksCache = request.app.state.jwks_cache
    jwk = await cache.get_key(
        kid=unverified_header.get("kid"),
        request=request,
        settings=settings,
    )

    try:
        key = RSAAlgorithm.from_jwk(json.dumps(jwk))
        claims = jwt.decode(
            token,
            key=key,
            algorithms=[settings.auth_jwt_algorithm],
            audience=settings.auth_expected_audience,
        )
    except InvalidTokenError as exc:
        raise GatewayAuthError(
            status_code=401,
            code="invalid_token",
            message="Bearer token could not be verified.",
            details={"reason": exc.__class__.__name__},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    context = AuthContext(
        subject=str(claims["sub"]),
        email=claims.get("email"),
        role=claims.get("role"),
        claims=dict(claims),
    )
    request.state.auth = context
    return context


def require_role(*allowed_roles: str):
    normalized_roles = {role.casefold() for role in allowed_roles}

    async def _require_role(
        auth: AuthContext = Depends(get_auth_context),
    ) -> AuthContext:
        if (auth.role or "").casefold() not in normalized_roles:
            raise GatewayAuthError(
                status_code=403,
                code="forbidden",
                message="Authenticated user does not have the required role.",
            )
        return auth

    return _require_role


def jwk_from_public_numbers(n: int, e: int, kid: str = "default") -> dict[str, str]:
    return {
        "kty": "RSA",
        "alg": "RS256",
        "use": "sig",
        "kid": kid,
        "n": _b64url_uint(n),
        "e": _b64url_uint(e),
    }
