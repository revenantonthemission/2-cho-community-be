# Gemini Context: 2-cho-community-be

## Project Overview
This project is a FastAPI-based backend for a community application, developed as part of the AWS AI School (2nd Gen, Week 3). It provides a robust API for user management, authentication, and social features like posts, comments, and likes.

**Key Technologies:**
*   **Framework:** FastAPI (Python 3.11+)
*   **Database:** MySQL with `aiomysql` (Async driver)
*   **Validation:** Pydantic (v2)
*   **Authentication:** Session-based (Cookies + DB-backed session table)
*   **Server:** Uvicorn

## Architecture
The codebase follows a clear **3-Layer Architecture**:

1.  **Routers (`routers/`)**: Define API endpoints and handle request parsing/validation using Pydantic schemas.
2.  **Controllers (`controllers/`)**: Implement business logic, coordinate between models, and format standardized responses.
3.  **Models (`models/`)**: Perform direct database operations using raw SQL. Domain objects are represented as Python `dataclasses`.

**Support Modules:**
*   `schemas/`: Pydantic models for request/response bodies.
*   `dependencies/`: FastAPI dependencies (e.g., `get_current_user` for auth).
*   `middleware/`: Logging, timing, and exception handling.
*   `core/`: Configuration and settings management.
*   `database/`: Connection pooling and transaction management.

## Database Patterns
*   **Connection Pool:** Managed via `aiomysql.create_pool` in `database/connection.py`.
*   **Context Managers:**
    *   `async with get_connection() as conn`: For simple read operations.
    *   `async with transactional() as cur`: For write operations. Automatically handles `COMMIT` on success and `ROLLBACK` on error. Returns an async cursor.
*   **Optimizations:** Complex queries like `get_posts_with_details` use JOINs and subqueries to solve N+1 problems.
*   **Soft Delete:** Uses `deleted_at` timestamps instead of physical row deletion for most entities.

## Authentication & Sessions
*   **Session Management:** Uses `starlette.middleware.sessions.SessionMiddleware` for cookie handling.
*   **Persistence:** Sessions are also stored in the `user_session` table in MySQL to allow server-side invalidation and session tracking.
*   **Auth Dependency:** Routes requiring authentication use the `get_current_user` dependency, which validates the session and checks if the user is still active (not soft-deleted).

## User Withdrawal & Re-registration
*   When a user withdraws, their data is soft-deleted, and their unique identifiers (email, nickname) are **anonymized** (e.g., `deleted_uuid@deleted.user`).
*   This process frees up the original email and nickname for new registrations while maintaining database integrity for historical data (e.g., posts and comments which are linked to the user ID).

## Standardized Response Format
All API responses follow a consistent structure defined in `schemas/common.py`:
```json
{
    "code": "SUCCESS_CODE",
    "message": "Action completed successfully",
    "data": { ... },
    "errors": [],
    "timestamp": "2026-02-02T12:00:00Z"
}
```

## Development Commands
```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

# Database Initialization
mysql -u [user] -p community_service < database/schema.sql

# Running the Server
uvicorn main:app --reload

# Testing
pytest tests/ -v
```

## Problem Solving Methodology
For complex feature additions or bug fixes, use the **Tree of Thought (ToT)** approach:
1.  **Summarize** the core problem.
2.  **Analyze** from multiple perspectives (Technical, Strategic, User UX).
3.  **Branch** out independent thinking paths with 3-4 steps each.
4.  **Evaluate** and select the most robust path with clear reasoning.
