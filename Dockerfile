# Backend Docker Image for AWS Lambda
FROM public.ecr.aws/lambda/python:3.13

ARG APP_VERSION=1.0.0
LABEL maintainer="corpseonthemission@icloud.com"
LABEL version="${APP_VERSION}"
LABEL description="my-community-be: A community platform backend API built with FastAPI and adapted for AWS Lambda"

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies using dnf (Amazon Linux 2023)
RUN dnf update -y && dnf install -y \
    gcc \
    gcc-c++ \
    make \
    && dnf clean all

# Copy dependency files first
COPY pyproject.toml uv.lock ${LAMBDA_TASK_ROOT}/

# Export dependencies and install them directly into the Lambda task root
RUN uv export --format requirements-txt > requirements.txt && \
    uv pip install --system --no-cache -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

# Copy application code
COPY . ${LAMBDA_TASK_ROOT}/

# Start application using a Lambda handler
CMD ["main.handler"]