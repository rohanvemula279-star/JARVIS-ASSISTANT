import asyncio
from playwright.async_api import async_playwright # type: ignore

async def run_playwright_test():
    try:
        print("Starting async_playwright...")
        mgr = async_playwright()
        p = await mgr.start()
        print("Started playwight:", p)
        # Try to launch chromium
        print("Trying to launch chromium...")
        browser = await p.chromium.launch()
        print("Launched chromium:", browser)
        await browser.close() # type: ignore
        await p.stop()
    except Exception as e:
        print("Playwright test failed with Exception:", type(e), repr(e))

if __name__ == "__main__":
    if hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
        asyncio.set_event_loop_policy(getattr(asyncio, "WindowsProactorEventLoopPolicy")()) # type: ignore
    asyncio.run(run_playwright_test())
