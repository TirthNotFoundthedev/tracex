# Builds one browser app (APP=admin or officer) and serves it with nginx. nginx also proxies /api to
# the API service, so the browser sees one origin and the API needs no CORS header.
FROM node:22.12-alpine@sha256:51eff88af6dff26f59316b6e356188ffa2c422bd3c3b76f2556a2e7e89d080bd AS build
ARG APP
WORKDIR /repo
COPY package.json package-lock.json tsconfig.base.json ./
COPY apps ./apps
COPY packages ./packages
RUN npm ci
# Same-origin API base: the app calls /api/..., nginx strips the prefix.
ENV VITE_API_URL=/api
RUN npm run build --workspace "apps/${APP}"

FROM nginx:1.27.5-alpine@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10
ARG APP
COPY docker/app-nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/apps/${APP}/dist /usr/share/nginx/html
EXPOSE 80
