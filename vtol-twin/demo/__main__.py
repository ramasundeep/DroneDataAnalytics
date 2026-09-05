"""python -m demo  ->  serve the demo UI on DEMO_PORT (default 8090)."""
import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run("demo.app:app", host=os.getenv("DEMO_HOST", "0.0.0.0"), port=int(os.getenv("DEMO_PORT", "8090")),
                log_level=os.getenv("LOG_LEVEL", "info").lower())
