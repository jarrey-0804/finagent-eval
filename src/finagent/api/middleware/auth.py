"""
JWT 认证中间件

提供基于 JWT 的 API 认证功能。
"""

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta


class JWTAuthMiddleware:
    """
    JWT 认证中间件

    支持 JWT Token 的生成、验证和请求认证。
    生产环境建议使用 PyJWT 库，此处为自包含实现。
    """

    def __init__(
        self,
        secret_key: str = "finagent-eval-secret-key",
        algorithm: str = "HS256",
        token_expiry_hours: int = 24,
        exempt_paths: list[str] | None = None,
    ):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.token_expiry_hours = token_expiry_hours
        self.exempt_paths = exempt_paths or [
            "/health",
            "/api/v1/info",
            "/docs",
            "/openapi.json",
        ]

    def generate_token(
        self,
        user_id: str,
        role: str = "user",
        extra_claims: dict | None = None,
    ) -> str:
        """生成 JWT Token"""
        now = datetime.utcnow()

        header = {"alg": self.algorithm, "typ": "JWT"}

        payload = {
            "sub": user_id,
            "role": role,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=self.token_expiry_hours)).timestamp()),
        }

        if extra_claims:
            payload.update(extra_claims)

        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()

        signature_input = f"{header_b64}.{payload_b64}"
        signature = hmac.new(
            self.secret_key.encode(),
            signature_input.encode(),
            hashlib.sha256,
        ).digest()
        signature_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()

        return f"{header_b64}.{payload_b64}.{signature_b64}"

    def verify_token(self, token: str) -> dict | None:
        """验证 JWT Token"""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None

            header_b64, payload_b64, signature_b64 = parts

            # 验证签名
            signature_input = f"{header_b64}.{payload_b64}"
            expected_sig = hmac.new(
                self.secret_key.encode(),
                signature_input.encode(),
                hashlib.sha256,
            ).digest()
            expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).rstrip(b"=").decode()

            if not hmac.compare_digest(signature_b64, expected_sig_b64):
                return None

            # 解析 payload
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding

            payload = json.loads(base64.urlsafe_b64decode(payload_b64))

            # 检查过期
            if payload.get("exp", 0) < time.time():
                return None

            return payload

        except Exception:
            return None

    def is_exempt(self, path: str) -> bool:
        """检查路径是否免认证"""
        return any(path.startswith(exempt) for exempt in self.exempt_paths)

    async def authenticate(self, token: str | None, path: str) -> tuple[bool, dict | None]:
        """
        认证请求

        Returns:
            tuple: (是否通过, 用户信息)
        """
        if self.is_exempt(path):
            return True, {"role": "anonymous"}

        if not token:
            return False, None

        payload = self.verify_token(token)
        if payload is None:
            return False, None

        return True, payload
