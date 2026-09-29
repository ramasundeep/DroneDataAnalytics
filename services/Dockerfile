# syntax=docker/dockerfile:1.7
#
# Shared image recipe for every CD Sim Python service (services/api,
# services/recorder, services/assessment, services/rl, terrain/services).
# docker-compose.yml passes PACKAGE (the package directory) as a build arg.
# The build context is the repository root (see .dockerignore).
#
# Internet is needed only while building (pip). The resulting image runs
# fully offline. Optional: if your build network uses a TLS-inspecting proxy,
# provide its CA as the `build_ca` secret (CDSIM_BUILD_CA in .env) — see
# docs/09_DEPLOYMENT_OFFLINE.md §"Building behind a proxy".

ARG PYTHON_IMAGE=python:3.11-slim
FROM ${PYTHON_IMAGE}

ARG PACKAGE
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /opt/cdsim
COPY services/common src/services/common
COPY ${PACKAGE} src/${PACKAGE}
RUN --mount=type=secret,id=build_ca,required=false \
    if [ -s /run/secrets/build_ca ]; then \
        export PIP_CERT=/run/secrets/build_ca SSL_CERT_FILE=/run/secrets/build_ca; \
    fi; \
    pip install "src/services/common[infra]" "src/${PACKAGE}" \
    && rm -rf src

# Contracts are baked in; manifests are mounted read-only at runtime.
COPY schemas/json /opt/cdsim/schemas/json
ENV CDSIM_SCHEMAS_DIR=/opt/cdsim/schemas/json \
    CDSIM_PLATFORMS_DIR=/opt/cdsim/data/platforms \
    CDSIM_AREAS_DIR=/opt/cdsim/data/areas \
    CDSIM_SCENARIOS_DIR=/opt/cdsim/data/scenarios \
    CDSIM_RUBRICS_DIR=/opt/cdsim/data/rubrics

RUN useradd --system --uid 10001 --no-create-home cdsim
USER cdsim
