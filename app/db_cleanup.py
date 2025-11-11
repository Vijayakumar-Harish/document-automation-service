import asyncio

def safe_close_motor(client):
    """
    Safely closes Motor client without causing 'Event loop is closed' errors,
    especially on Windows' ProactorEventLoop.
    """
    try:
        if client:
            # Attempt graceful close
            client.close()
            # Give Motor executor time to drain
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Schedule a short sleep on the loop (don’t block)
                    loop.create_task(asyncio.sleep(0.05))
            except RuntimeError:
                # No running loop, safe to ignore
                pass
    except Exception as e:
        print("Warning: safe_close_motor:", e)
