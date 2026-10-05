# COMMONDEPTH

> Go beyond the surface.

COMMONDEPTH is a global social network built by Goldx Technologies.

## Product Principle

**People first. Crypto is infrastructure.**

COMMONDEPTH is designed as a social, communication, publishing, discovery, and community platform. Cryptocurrency and blockchain capabilities are optional infrastructure for appropriate value, payment, ownership, and settlement use cases.

Users will be able to use the core social network without optionally owning a wallet or purchasing a token.

## Engineering Principles

COMMONDEPTH follows these foundational rules:

- People before infrastructure.
- Security before scale.
- Privacy by design.
- Global by default.
- Africa-first in execution.
- Modular monolith before unnecessary service distribution.
- Strong domain boundaries.
- Server-side authorization.
- Database migrations for every schema change.
- Testing from the first feature.
- Observability from the foundation.
- No secrets or private keys in source control.
- Social identity and wallet identity remain separate.
- Financial and blockchain systems remain isolated from the social core.
- No blockchain for blockchain's sake.
- No dark-pattern engagement optimization.
- No hidden financial fees.

## Deployment Architecture

### Frontend

- React
- TypeScript
- Vite
- Cloudflare

### Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- Render

### Database

- PostgreSQL

The browser communicates with the COMMONDEPTH API. It does not connect directly to PostgreSQL.

## Repository Structure

```text
COMMONDEPTH/
├── backend/
├── frontend/
├── docs/
├── infrastructure/
├── scripts/
├── tests/
├── .github/
├── .gitignore
└── README.md
## Development Sequence

Engineering Foundation
↓
Identity
↓
Social Graph
↓
Following Feed
↓
Content
↓
Engagement
↓
Messaging
↓
Discovery
↓
Safety
↓
Hardening
↓
Economy
↓
Crypto Infrastructure

## Engineering Workflow

Every implementation follows:

1. Inspect.
2. Design.
3. Implement the smallest correct change.
4. Run focused tests.
5. Review the diff.
6. Review security and authorization.
7. Run broader validation.
8. Commit only when explicitly authorized.

## Product Boundary

COMMONDEPTH is a separate product and codebase.

It must not inherit Goldx OS AI Vault, Safe, relayer, treasury, or corporate-wallet capabilities merely because both products belong to Goldx Technologies.

Any future integration must be explicit, authenticated, authorized, audited, and architecturally reviewed.

## Current Milestone

Milestone 0 — Engineering Foundation

Current objective:

- repository foundation
- backend foundation
- frontend foundation
- configuration
- database connectivity
- migration system
- logging
- errors
- health/readiness
- testing infrastructure
- CI foundation

First product vertical slice:

Registration → Profile → Follow → Feed

## Status

COMMONDEPTH is currently in engineering foundation initialization.

No production feature should be considered complete without its required database behavior, authorization, API contract, tests, security review, observability, and frontend behavior.
