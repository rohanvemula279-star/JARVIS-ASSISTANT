import asyncio
import logging
from functools import wraps

logger = logging.getLogger(__name__)

RETRY_DELAYS = [5, 15, 30]  # seconds — respects per-minute quota windows

async def with_retry(coro_fn, *args, fallback=None, **kwargs):
    last_error = None
    for attempt, delay in enumerate(RETRY_DELAYS + [None]):
        try:
            return await coro_fn(*args, **kwargs)
        except Exception as e:
            last_error = e
            error_str = str(e)
            
            # Log the ACTUAL error — not just "retrying"
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Attempt {attempt+1} failed: {type(e).__name__}: {error_str[:200]}")
            
            is_quota = "429" in error_str or "RESOURCE_EXHAUSTED" in error_str
            is_retryable = is_quota or "503" in error_str or "timeout" in error_str.lower()
            
            # ClientError is NOT retryable — it's a config/auth/network problem
            if "ClientError" in type(e).__name__ and not is_quota:
                logger.error("ClientError is not retryable — check API key and transport config")
                if fallback is not None:
                    return fallback
                raise
            
            if not is_retryable:
                raise
            
            if delay is None:
                if fallback is not None:
                    return fallback
                raise
            
            logger.warning(f"Retrying in {delay}s...")
            await asyncio.sleep(delay)
