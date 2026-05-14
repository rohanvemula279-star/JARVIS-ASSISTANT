"""Step 4: Test retry utility (no API needed)"""
import asyncio
import backend.utils.retry as r

r.RETRY_DELAYS = [0.1, 0.1, 0.1]

call_count = 0

async def flaky_fn():
    global call_count
    call_count += 1
    if call_count < 3:
        raise Exception("429 RESOURCE_EXHAUSTED")
    return "success"

async def main():
    global call_count
    result = await r.with_retry(flaky_fn, fallback="fallback")
    assert result == "success", f"Got: {result}"
    assert call_count == 3
    print("with_retry exponential backoff: PASS")

    # Test 2: non-retryable error should raise immediately
    call_count = 0
    async def auth_error():
        global call_count
        call_count += 1
        raise ValueError("Invalid API key")

    try:
        await r.with_retry(auth_error, fallback="fallback")
        print("ERROR: Should have raised ValueError")
    except ValueError:
        assert call_count == 1, f"Should only call once, called {call_count}"
        print("with_retry non-retryable raises immediately: PASS")

    # Test 3: fallback on exhaustion
    call_count = 0
    async def always_429():
        global call_count
        call_count += 1
        raise Exception("429 rate limit")

    result = await r.with_retry(always_429, fallback="used_fallback")
    assert result == "used_fallback", f"Got: {result}"
    print("with_retry fallback on exhaustion: PASS")

if __name__ == "__main__":
    asyncio.run(main())
