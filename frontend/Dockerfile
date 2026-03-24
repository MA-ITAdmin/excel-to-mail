FROM node:22-alpine AS build

ARG PUBLIC_MAILPIT_URL=http://localhost:8025
ENV PUBLIC_MAILPIT_URL=${PUBLIC_MAILPIT_URL}

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
