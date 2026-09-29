"""CD Sim shared library.

Everything more than one Python service needs lives here, so there is exactly
one implementation of the unified sim clock, the event models, service
configuration, health endpoints and manifest (platform/area/rubric/scenario)
loading. See services/common/README.md.
"""

__version__ = "0.1.0"
