from datetime import datetime, timezone
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy
from fastapi_users.authentication.strategy.jwt import generate_jwt
from auth.keys import load_keys
from models import User

bearer_transport = BearerTransport(tokenUrl="auth/login")

class CustomJWTStrategy(JWTStrategy):
    async def write_token(self, user: User) -> str:
        data = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "aud": self.token_audience,
            "iat": datetime.now(timezone.utc),
        }
        return generate_jwt(
            data, self.secret, self.lifetime_seconds, algorithm=self.algorithm
        )

def get_jwt_strategy() -> JWTStrategy:
    private_key, public_key = load_keys()
    return CustomJWTStrategy(
        secret=private_key,
        lifetime_seconds=3600,
        algorithm="RS256",
        public_key=public_key,
    )

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)
