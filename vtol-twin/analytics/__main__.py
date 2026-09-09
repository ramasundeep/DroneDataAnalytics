import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run("analytics.service:app", host="0.0.0.0", port=int(os.getenv("ANALYTICS_PORT", "8092")),
                log_level=os.getenv("LOG_LEVEL", "info").lower())
