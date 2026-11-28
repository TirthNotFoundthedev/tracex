# Builds one browser app (APP=admin or officer) and serves it with nginx. nginx also proxies /api to
# the API service, so the browser sees one origin and the API needs no CORS header.
FROM node:22.12-alpine AS build
ARG APP
WORKDIR /repo
COPY package.json package-lock.json ./
COPY apps ./apps
COPY packages ./packages
RUN npm ci
# Same-origin API base: the app calls /api/..., nginx strips the prefix.
ENV VITE_API_URL=/api
RUN npm run build --workspace "apps/${APP}"

FROM nginx:1.27.5-alpine
ARG APP
COPY docker/app-nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/apps/${APP}/dist /usr/share/nginx/html
EXPOSE 80
