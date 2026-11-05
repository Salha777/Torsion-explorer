# Torsion Explorer: a single static page, built from source and served by nginx.
#   docker build -t torsion-explorer .
#   docker run --rm -p 8080:80 torsion-explorer      ->  http://localhost:8080

FROM python:3.12-alpine AS build
WORKDIR /app
COPY build.py ./
COPY src ./src
COPY data ./data
COPY fonts ./fonts
RUN python build.py

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/site/ /usr/share/nginx/html/
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
