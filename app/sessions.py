"""Session management with Redis."""
import json
import structlog
from typing import Optional, Dict, Any
from redis.asyncio import Redis
from app.config import settings

logger = structlog.get_logger()


class SessionStore:
    """Redis-based session storage."""

    def __init__(self):
        self.redis: Optional[Redis] = None
        self.ttl = settings.redis_session_ttl

    async def connect(self):
        """Initialize Redis connection."""
        self.redis = Redis.from_url(
            settings.redis_url,
            encoding='utf-8',
            decode_responses=True
        )

        # Test connection
        await self.redis.ping()
        logger.info("Redis connected", url=settings.redis_url)

    async def disconnect(self):
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
            logger.info("Redis disconnected")

    async def get_session(self, session_id: str) -> Dict[str, Any]:
        """
        Get session state.

        Returns empty dict for new sessions.
        """
        try:
            data = await self.redis.get(f"session:{session_id}")

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
        """
        Update session state with TTL.
        """
        try:
            await self.redis.setex(
                f"session:{session_id}",
                self.ttl,
                json.dumps(state)
            )
            logger.debug("Session updated", session_id=session_id)

        except Exception as e:
            logger.error("Session update failed", session_id=session_id, exc_info=e)

    async def delete_session(self, session_id: str):
        """Delete session."""
        try:
            await self.redis.delete(f"session:{session_id}")
            logger.debug("Session deleted", session_id=session_id)
        except Exception as e:
            logger.error("Session delete failed", session_id=session_id, exc_info=e)
