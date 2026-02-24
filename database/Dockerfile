# Database Docker Image
# Build: docker build -t my-community-db:latest ./2-cho-community-be/database

FROM mysql:8.0

ARG APP_VERSION=1.0.0
LABEL maintainer="corpseonthemission@icloud.com"
LABEL version="${APP_VERSION}"
LABEL description="my-community MySQL database"

# Default environment variables (override at runtime)
ENV MYSQL_DATABASE=community_service

# Copy schema to initialization directory
# Scripts here run automatically on first container start
COPY schema.sql /docker-entrypoint-initdb.d/01_schema.sql

# Expose MySQL port
EXPOSE 3306

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=60s --retries=3 \
    CMD mysqladmin ping -h localhost || exit 1
