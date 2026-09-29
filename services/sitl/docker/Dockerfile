# ArduPilot SITL for CD Sim — UNVERIFIED BUILD (not yet built in CI; see
# services/sitl/README.md). Builds UNMODIFIED ArduPilot from a pinned release
# tag at image-build time (internet needed only here). The resulting image
# runs fully offline.
#
# Build:  docker compose --profile sitl build sitl
# ADR:    docs/ADR/0003-ardupilot-sitl-json-physics.md

ARG UBUNTU_VERSION=22.04
FROM ubuntu:${UBUNTU_VERSION} AS build

ARG ARDUPILOT_REPO=https://github.com/ArduPilot/ardupilot.git
ARG ARDUPILOT_REF=Copter-4.5.7
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        git ca-certificates build-essential g++ python3 python3-pip python3-dev \
        python3-setuptools pkg-config libtool \
    && rm -rf /var/lib/apt/lists/*
RUN pip3 install --no-cache-dir future empy==3.3.4 pexpect pymavlink

WORKDIR /src
RUN git clone --depth 1 --branch "${ARDUPILOT_REF}" --recurse-submodules --shallow-submodules \
        "${ARDUPILOT_REPO}" ardupilot
WORKDIR /src/ardupilot
RUN ./waf configure --board sitl && ./waf copter

FROM ubuntu:${UBUNTU_VERSION}
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /src/ardupilot/build/sitl/bin/arducopter /usr/local/bin/arducopter
COPY services/sitl/docker/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY services/sitl/docker/healthcheck.py /usr/local/bin/healthcheck.py
RUN chmod +x /usr/local/bin/entrypoint.sh && useradd -m sitl
USER sitl
WORKDIR /home/sitl

# 5760: MAVLink TCP (SERIAL0) — instructor console / scripted tests
# 14550/udp: MAVLink out to a ground-control station (SERIAL1)
# 9002/udp:  JSON physics exchange is initiated by SITL towards SIM_HOST:9002
EXPOSE 5760 14550/udp

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s \
    CMD python3 /usr/local/bin/healthcheck.py
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
