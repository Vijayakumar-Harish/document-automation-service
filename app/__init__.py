import sys
import asyncio

# Fix for Motor + Windows (ProactorEventLoop race issue)
if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass
