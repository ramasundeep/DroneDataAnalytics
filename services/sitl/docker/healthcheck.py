"""Container health: SITL is healthy when its MAVLink TCP port accepts connections."""

import os
import socket
import sys

port = 5760 + 10 * int(os.environ.get("INSTANCE", "0"))
try:
    with socket.create_connection(("127.0.0.1", port), timeout=2):
        pass
except OSError:
    sys.exit(1)
