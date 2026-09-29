# syntax=docker/dockerfile:1.7
# CD Sim Instructor Console — build context is apps/instructor-console.
# Internet is needed only at build time (npm ci); the runtime image is static
# files + nginx and works fully offline.

# ---- build stage ----
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json .npmrc ./
# Optional build-proxy CA (docs/09_DEPLOYMENT_OFFLINE.md §"Building behind a proxy").
RUN --mount=type=secret,id=build_ca,required=false \
    if [ -s /run/secrets/build_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/build_ca; fi; \
    npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# ---- runtime stage ----
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1/healthz || exit 1
