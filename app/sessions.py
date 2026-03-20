"""Session management with Redis."""
import json
import structlog
from typing import Optional, Dict, Any
from redis.asyncio import Redis
from app.config import settings

logger = structlog.get_logger()


class SessionStore:
    """Redis-based session storage with in-memory fallback."""

    def __init__(self):
        self.redis: Optional[Redis] = None
        self.ttl = settings.redis_session_ttl
        self._memory_store: Dict[str, str] = {}

    async def connect(self):
        """Initialize Redis connection, fall back to in-memory if unavailable."""
        try:
            self.redis = Redis.from_url(
                settings.redis_url,
                encoding='utf-8',
                decode_responses=True
            )
            await self.redis.ping()
            logger.info("Redis connected", url=settings.redis_url)
        except Exception as e:
            logger.warning("Redis unavailable, using in-memory sessions", error=str(e))
            self.redis = None

    async def disconnect(self):
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
            logger.info("Redis disconnected")

    async def get_session(self, session_id: str) -> Dict[str, Any]:
        """Get session state. Returns empty dict for new sessions."""
        key = f"session:{session_id}"
        try:
            if self.redis:
                data = await self.redis.get(key)
            else:
                data = self._memory_store.get(key)

            if data:
                state = json.loads(data)
                logger.debug("Session loaded", session_id=session_id)
                return state
            else:
                logger.debug("New session", session_id=session_id)
                return {}

        except Exception as e:
            logger.error("Session load failed", session_id=session_id, exc_info=e)
            return {}

    async def update_session(self, session_id: str, state: Dict[str, Any]):
        """Update session state with TTL."""
        key = f"session:{session_id}"
        try:
            if self.redis:
                await self.redis.setex(key, self.ttl, json.dumps(state))
            else:
                self._memory_store[key] = json.dumps(state)
            logger.debug("Session updated", session_id=session_id)

        except Exception as e:
            logger.error("Session update failed", session_id=session_id, exc_info=e)

    async def delete_session(self, session_id: str):
        """Delete session."""
        key = f"session:{session_id}"
        try:
            if self.redis:
                await self.redis.delete(key)
            else:
                self._memory_store.pop(key, None)
            logger.debug("Session deleted", session_id=session_id)
        except Exception as e:
            logger.error("Session delete failed", session_id=session_id, exc_info=e)
