# COMMONDEPTH Identity Data Model

## Status

Design specification — not yet implemented.

## Purpose

Define the identity and session data model required for the first COMMONDEPTH vertical slice:

Registration → Profile → Follow → Feed

The identity layer establishes durable user identity, authentication credentials, sessions, and device/session management without coupling social identity to cryptocurrency or blockchain identity.

## Core Principles

1. A COMMONDEPTH user does not need a wallet.
2. Social identity and wallet identity are separate domains.
3. Authentication credentials must never be stored in plaintext.
4. Sessions must be revocable.
5. Devices must be independently identifiable.
6. User identifiers are opaque internal identifiers.
7. Usernames are human-facing identifiers and belong to the profile domain.
8. Email addresses, when used, are authentication/contact identifiers and are not the public social identity by default.
9. Server-side authorization is authoritative.
10. Account lifecycle state must be explicit.
11. Financial or blockchain state must not be stored in identity tables.
12. Future authentication methods must be extensible without redesigning the user entity.

# 1. Domain Boundary

The identity domain owns:

- user account identity
- authentication credentials
- authentication identities
- sessions
- devices
- account lifecycle state

The identity domain does not own:

- posts
- follows
- profiles/social presentation
- messages
- notifications
- wallets
- blockchain addresses
- token balances
- financial transactions
- moderation cases

Those domains may reference the user’s immutable internal identifier.

# 2. users

`users` represents the canonical COMMONDEPTH account.

## Proposed fields

| Field | Type | Rules |
|---|---|---|
| id | UUID | Primary key; immutable |
| status | enum/string | Account lifecycle state |
| created_at | timestamp | Required |
| updated_at | timestamp | Required |
| last_seen_at | timestamp | Nullable |
| deleted_at | timestamp | Nullable; account deletion lifecycle |

## Status values

Initial states:

- `active`
- `suspended`
- `deactivated`
- `pending_deletion`
- `deleted`

The exact database representation will be finalized during implementation.

## Rules

- `id` is never reused.
- Public APIs should not expose sequential database identifiers.
- Deleted accounts must retain enough internal identity information to preserve referential integrity and auditability.
- Account deletion behavior must be defined before implementation.
- Suspension/deactivation must not silently destroy historical records.

# 3. user_identities

`user_identities` stores authentication identities associated with a canonical user account. It allows COMMONDEPTH to support multiple authentication mechanisms without changing the `users` entity.

## Proposed fields

| Field | Type | Rules |
|---|---|---|
| id | UUID | Primary key; immutable |
| user_id | UUID | Required; foreign key to `users.id` |
| provider | string/enum | Authentication provider type |
| provider_subject | string | Provider-specific stable identity; required |
| created_at | timestamp | Required |
| last_used_at | timestamp | Nullable |
| disabled_at | timestamp | Nullable |

## Initial provider model

The model should be extensible for:

- email/password
- magic link
- OAuth/OIDC
- passkeys/WebAuthn

The exact provider enum will be finalized during implementation.

## Uniqueness

- `(provider, provider_subject)` must be unique.
- A provider identity must belong to exactly one canonical user.
- Provider subjects must not be exposed as public social identifiers.

## Rules

- Authentication identity records must not contain plaintext passwords.
- Authentication provider secrets must never be stored in source code.
- Disabled identities must not authenticate successfully.
- Removing or disabling an authentication identity must not accidentally delete the canonical user.
- Future authentication methods should be addable without redesigning `users`.
| provider | string/enum | Authentication provider type |
| provider_subject | string | Provider-specific stable identity; required |
| created_at | timestamp | Required |
| last_used_at | timestamp | Nullable |

## Initial provider model

The model should be extensible for:

- email/password
- magic link
- OAuth/OIDC
- passkeys/WebAuthn

The exact provider enum will be finalized during implementation.

## Uniqueness

- `(provider, provider_subject)` must be unique.
- A provider identity must belong to exactly one canonical user.
- Provider subjects must not be exposed as public social identifiers.

## Rules

- Authentication identity records must not contain plaintext passwords.
- Authentication provider secrets must never be stored in source code.
- Disabled identities must not authenticate successfully.
- Removing or disabling an authentication identity must not accidentally delete the canonical user.
- Future authentication methods should be addable without redesigning `users`.

# 4. Password Authentication

Password authentication is an authentication mechanism, not the user identity itself.

## Proposed credential fields

| Field | Type | Rules |
|---|---|---|
| user_identity_id | UUID | Required; references the password authentication identity |
| password_hash | string | Required; password-derived hash only |
| password_changed_at | timestamp | Required |
| created_at | timestamp | Required |
| updated_at | timestamp | Required |

## Password rules

- Passwords must never be stored in plaintext.
- Passwords must never be logged.
- Password hashes must never be returned through public APIs.
- Use a modern password-hashing algorithm appropriate for production deployment.
- Password verification must be performed server-side.
- Password changes must update `password_changed_at`.
- Password changes must invalidate sessions according to the session-security policy.
- Password-reset tokens are temporary authentication credentials and must not be stored in plaintext.
- Password-reset flows must be rate-limited and auditable.

## Authentication boundary

The password credential belongs to the authentication identity. The canonical `users` record must not contain a password field.

The exact password-hashing algorithm, parameters, reset-token storage strategy, and session invalidation behavior will be finalized during implementation and security review.

# 5. sessions

`sessions` represents authenticated application sessions. A session is revocable, independently identifiable, and bound to a user and device where applicable.

## Proposed fields

| Field | Type | Rules |
|---|---|---|
| id | UUID | Primary key; immutable |
| user_id | UUID | Required; foreign key to `users.id` |
| device_id | UUID | Nullable initially; foreign key to `devices.id` |
| token_hash | string | Required; hash of the session token, never the raw token |
| created_at | timestamp | Required |
| last_used_at | timestamp | Nullable |
| expires_at | timestamp | Required |
| revoked_at | timestamp | Nullable |
| revoke_reason | string | Nullable |
| ip_address | string | Nullable; security/audit metadata |
| user_agent | string | Nullable; security/audit metadata |
| created_from | string | Nullable; authentication/session creation context |

## Session rules

- Raw session tokens must never be persisted.
- Only a secure hash of the session token may be stored.
- Sessions must have explicit expiration.
- Sessions must be individually revocable.
- Revoked sessions must never authenticate successfully.
- Expired sessions must never authenticate successfully.
- Session validation must be performed server-side.
- Session identifiers must be opaque and non-sequential.
- Session records must not expose authentication secrets through public APIs.
- Session creation, revocation, and security-sensitive changes should be auditable.

## Session invalidation

The implementation must define which events revoke which sessions. At minimum, password changes and explicit user logout must be able to revoke sessions.

Security-sensitive events such as account suspension, credential compromise, or administrative security action may require revocation of all active sessions.

The exact session lifetime, idle timeout, token format, cookie/header transport, rotation strategy, and revocation policy will be finalized during implementation and security review.

# 6. devices

`devices` represents a recognizable application/device context associated with a user. Device records support session management, security visibility, and selective session revocation without requiring unnecessary collection of raw hardware identifiers.

## Proposed fields

| Field | Type | Rules |
|---|---|---|
| id | UUID | Primary key; immutable |
| user_id | UUID | Required; foreign key to `users.id` |
| device_identifier_hash | string | Nullable; derived identifier only when justified |
| platform | string | Required; application platform category |
| name | string | Nullable; user-defined or application-generated label |
| created_at | timestamp | Required |
| last_seen_at | timestamp | Nullable |
| revoked_at | timestamp | Nullable |

## Device rules

- Device records must not require collection of unnecessary hardware identifiers.
- Raw hardware identifiers should not be stored unless there is a documented security or product requirement.
- Where a device identifier is necessary, prefer a derived or protected representation.
- A device may have multiple sessions over time.
- Revoking a device must be distinguishable from revoking one session.
- Device revocation may require associated active sessions to be revoked.
- Device records must not be treated as public social identity.
- Device metadata must not be exposed to other users.

## Privacy and security

Device information is security-sensitive metadata. Access must be limited to the authenticated user and appropriately authorized security or administrative workflows.

The exact device-identification strategy, platform values, retention behavior, and device/session revocation relationship will be finalized during implementation and security review.

# 7. Public Social Identity

Public social identity belongs to the profile domain, not the identity domain.

The identity domain provides the immutable internal `users.id` reference. The profile domain will own the human-facing representation of that account.

## Profile-owned identity

The future profile domain may own:

- username
- display name
- biography
- avatar/profile image
- profile links
- other intentionally public profile attributes

## Boundary rules

- Username must not be used as the primary internal foreign key.
- Other domains should reference the immutable `users.id`.
- Authentication email addresses must not automatically become public profile information.
- Authentication provider subjects must never become public social identifiers.
- Changing a username must not change the canonical user identity.
- Deactivating or deleting an account must not cause another account to inherit its internal identity.
- Public profile visibility must be governed separately from authentication state.

## Separation principle

A user should be able to authenticate without exposing authentication credentials or provider identity as their public COMMONDEPTH identity.

Wallet addresses, blockchain identities, token balances, and financial information are also not part of the public social identity model by default.

# 8. Wallet and Blockchain Identity Separation

COMMONDEPTH social identity and blockchain identity are separate domains.

A user may participate fully in COMMONDEPTH without connecting a wallet, owning cryptocurrency, holding tokens, or exposing a blockchain address.

## Identity boundary

- `users.id` is the canonical COMMONDEPTH identity.
- A wallet address is not a COMMONDEPTH user identifier.
- A blockchain address must not be used as the primary foreign key for social data.
- Wallet connection must be optional.
- Wallet ownership must never be inferred solely from a social username, email address, or other public profile attribute.
- Blockchain addresses must not be stored in identity tables merely because a user has an account.

## Financial separation

Wallets, blockchain addresses, balances, transactions, custody state, signing state, token ownership, and payment activity belong to a separate financial/blockchain domain.

The financial domain may reference `users.id` where an authenticated relationship is required, but the identity domain must not own financial state.

## Security boundary

- Private keys and seed phrases must never be stored in identity records.
- Authentication credentials must never grant blockchain signing authority.
- Connecting a wallet must not automatically grant financial permissions beyond the explicitly authorized operation.
- Blockchain transactions must use a dedicated financial authorization and audit model.
- Social APIs must not expose private financial information by default.

## Goldx integration boundary

COMMONDEPTH must not directly inherit Goldx Vault, Safe, relayer, treasury, corporate-wallet, custody, or signing capabilities because both products belong to Goldx Technologies.

Any future integration must be explicitly designed, authenticated, authorized, audited, and reviewed as a separate integration boundary.

# 9. Authorization Boundary

Authentication establishes the identity of an actor. Authorization determines whether that authenticated actor may perform a specific action on a specific resource.

## Authentication

The identity domain is responsible for establishing and maintaining authenticated identity through supported authentication mechanisms and sessions.

Authentication must not by itself grant unrestricted access to application resources.

## Authorization

Authorization is enforced server-side for every protected resource and operation.

Authorization decisions must consider, where applicable:

- authenticated user identity
- account lifecycle state
- resource ownership
- resource visibility
- relationship to the resource
- required role or permission
- moderation or safety restrictions
- administrative authority

## Object-level authorization

Protected APIs must verify access to the specific resource being requested.

Possessing a valid session must not be sufficient to access another user’s private resource merely because the resource identifier is known.

## Domain responsibility

The identity domain establishes authentication state and account lifecycle constraints. Individual application domains remain responsible for their own resource-level authorization rules.

For example:

- Profile domain controls profile visibility and profile modifications.
- Social graph domain controls follow, block, and mute permissions.
- Messaging domain controls conversation membership and message access.
- Moderation domain controls reports, moderation actions, and administrative safety permissions.
- Financial domain controls wallet and transaction authorization independently of social authentication.

## Administrative authorization

Administrative capabilities must use explicit roles or permissions and must not rely solely on possession of an authenticated session.

Administrative actions affecting accounts, moderation, security, or financial state must be auditable.

## Security principle

Authorization must fail closed. If the server cannot establish that an action is permitted, the action must be denied.

# 10. Account Lifecycle

Account lifecycle state is authoritative for whether an account may authenticate or participate in protected application operations.

## Lifecycle states

The initial lifecycle states are:

- `active` — normal account operation is permitted.
- `suspended` — account access is restricted by a safety or administrative action.
- `deactivated` — account is voluntarily or administratively inactive while retained by the system.
- `pending_deletion` — account has entered the deletion process but has not yet reached terminal deletion state.
- `deleted` — account is in a terminal deleted state while sufficient internal identity may be retained for referential integrity and auditability.

## Lifecycle principles

- Lifecycle transitions must be explicit.
- Lifecycle transitions must be authorized.
- Security-sensitive lifecycle changes must be auditable.
- Suspended accounts must not authenticate normally.
- Deactivated accounts must not authenticate normally unless an explicit reactivation flow permits it.
- Pending-deletion accounts must follow the defined deletion policy and must not silently return to normal operation.
- Deleted account identifiers must never be reassigned.
- Lifecycle state must not silently destroy historical records belonging to other domains.

## Deletion boundary

Account deletion behavior must distinguish between deleting personal information and preserving information required for legal, security, financial, moderation, or referential-integrity purposes.

Before implementation, COMMONDEPTH must define:

- what personal data is deleted
- what data is anonymized
- what data is retained
- retention periods
- treatment of posts and social relationships
- treatment of messages and attachments
- treatment of moderation and audit records
- treatment of financial records if the user later participates in the financial domain
- whether deletion is immediate or delayed
- who may cancel or authorize deletion

The deletion process must not be implemented as a generic cascading delete across the entire platform.

# 11. Referential Integrity

The immutable `users.id` is the canonical internal reference for a COMMONDEPTH account.

## Cross-domain references

- Other domains may reference `users.id` through foreign keys where appropriate.
- Cross-domain records must not use usernames, email addresses, wallet addresses, or provider subjects as their canonical user reference.
- Foreign-key relationships must preserve the integrity of historical records.

## Deletion behavior

Foreign-key relationships must be designed deliberately rather than relying on unrestricted database cascading.

In general:

- Identity deletion must not automatically delete social history.
- Identity deletion must not automatically delete messages required for conversation integrity.
- Identity deletion must not automatically delete moderation or audit records that must be retained.
- Financial records must follow the separate financial domain retention and ledger rules.

Where a related record must survive account deletion, the relationship should preserve the immutable user identifier or use an appropriate anonymization/retention strategy.

## Constraint principle

Database constraints should enforce relationships that are fundamental to data integrity. Application-level authorization must remain responsible for determining whether an authenticated actor is allowed to access or modify those records.

Referential integrity must not be used as a substitute for authorization.

# 12. Privacy and Data Minimization

The identity domain should collect only information necessary for authentication, account security, lifecycle management, and explicitly supported product functionality.

## Data minimization

- Do not collect identity or device information without a defined product, security, legal, or operational purpose.
- Authentication metadata must not automatically become public profile data.
- Device metadata must be limited to what is necessary for security and session management.
- IP addresses and user-agent information must have a documented security or operational purpose and retention policy.
- Financial and blockchain information must remain outside the identity domain.

## Sensitive authentication data

- Passwords must never be stored or logged in plaintext.
- Raw session tokens must never be persisted.
- Password-reset tokens must never be persisted in plaintext.
- Private keys, seed phrases, signing material, and wallet credentials must never be stored in identity records.

## API exposure

- Identity database records must not be returned directly through public APIs.
- Authentication credentials and security secrets must never be exposed through API responses.
- Security-sensitive metadata must only be exposed to the authenticated user or explicitly authorized administrative/security workflows.
- Public profile APIs must expose only intentionally public profile data.

## Logging and observability

- Logs must not contain passwords, raw session tokens, reset tokens, private keys, or other authentication secrets.
- Authentication and security events should be observable without logging secret material.
- Security-sensitive administrative actions must be auditable.

## Retention

Retention periods for authentication metadata, sessions, device information, audit events, and deleted-account data must be explicitly defined before production implementation.

Privacy requirements must be reviewed alongside security, compliance, and operational requirements rather than added after the identity system is implemented.

# 13. Indexing Requirements

Indexes must support documented identity-domain access patterns and security operations. Indexes should not be created speculatively.

## users

Likely access patterns include:

- retrieving a user by immutable `id`
- filtering or checking account lifecycle state

The primary key on `users.id` is mandatory. Additional indexes on lifecycle state will be evaluated against actual query patterns during implementation.

## user_identities

Required access patterns include:

- resolving an authentication identity by `(provider, provider_subject)`
- retrieving authentication identities for a user

The uniqueness constraint on `(provider, provider_subject)` should provide the required lookup support.

## sessions

Required access patterns include:

- resolving a session by its token hash
- retrieving active sessions for a user
- identifying expired sessions
- identifying sessions associated with a device

Indexes should support these access patterns while avoiding redundant indexes.

## devices

Required access patterns include:

- retrieving devices for a user
- identifying active/revoked devices
- locating a device when a protected device identifier is used

Indexes should be finalized from the actual authentication and session-management queries.

## Indexing principle

Every non-trivial index should have a documented access pattern or integrity requirement. Index design must be reviewed alongside query plans and migration performance before production deployment.

# 14. First Vertical Slice Dependencies

The first COMMONDEPTH vertical slice is:

Registration → Profile → Follow → Feed

The identity domain provides the foundation for this slice.

## Identity components required

The initial implementation requires:

- `users`
- `user_identities`
- password authentication credentials where password authentication is enabled
- `sessions`
- `devices`

## Downstream dependencies

The profile domain will reference `users.id` for the canonical account relationship.

The social graph domain will reference `users.id` for follows, blocks, and mutes.

The feed domain will consume authorized social-graph relationships and content owned by users, without making identity responsible for feed ranking or content state.

## Explicit boundary

Identity implementation must not introduce posts, follows, profile presentation, feed ranking, messaging, moderation, wallet connection, blockchain state, or token economics into the identity schema.

# 15. Migration Policy

All identity schema changes must be introduced through reviewed database migrations.

## Required workflow

1. Finalize the data-model design.
2. Implement the corresponding SQLAlchemy models.
3. Define constraints, foreign keys, uniqueness rules, and indexes.
4. Generate an Alembic migration.
5. Review the generated migration manually.
6. Add isolated database/integration tests for the schema behavior.
7. Validate downgrade behavior where supported and appropriate.
8. Perform security and authorization review.
9. Apply the migration only to an explicitly authorized development database.

## Prohibited practices

- No manual production table creation.
- No ad-hoc production schema changes.
- No bypassing Alembic for normal schema evolution.
- No migration that silently drops or alters identity data without an explicit reviewed data-migration strategy.
- No credentials or production connection strings committed to migration files or source control.

## Migration safety

Identity migrations must be reviewed for foreign-key ordering, uniqueness constraints, index creation cost, nullability, default values, rollback behavior, and potential impact on existing data.

# 16. Explicit Non-Goals

The identity data model does not implement or define the following systems:

- Public profile presentation and profile editing
- Follow, block, and mute relationships
- Posts, replies, reactions, reposts, or bookmarks
- Feed generation or ranking
- Direct messaging or group messaging
- Notifications
- Search and discovery
- Moderation workflows beyond identity-related account lifecycle state
- Wallet connection or wallet management
- Blockchain addresses or blockchain identity
- Token balances or token economics
- Cryptocurrency payments or financial transactions
- Custodial wallet infrastructure
- Private-key storage or signing infrastructure
- Creator payments, subscriptions, or tipping
- Recommendation algorithms
- Verification systems
- Business or organization accounts

These capabilities may reference the canonical `users.id` where appropriate, but they must be designed as separate domains with their own data models, authorization rules, and security boundaries.

# 17. Approval Gate

The identity schema must not be implemented until the following design decisions have been reviewed and explicitly approved.

## Required review decisions

- User lifecycle states and transition semantics
- Authentication provider strategy
- Password authentication and credential-storage strategy
- Password hashing and password-reset strategy
- Session token storage, expiration, rotation, and revocation strategy
- Device identification and device/session relationship
- Public social identity separation
- Wallet and blockchain identity separation
- Authentication versus authorization boundaries
- Account deletion, anonymization, and retention behavior
- Cross-domain foreign-key and referential-integrity strategy
- Privacy and identity-data retention requirements
- Required uniqueness constraints and indexes
- Migration ordering and migration safety

## Implementation gate

Only after these decisions are approved should COMMONDEPTH proceed to:

1. SQLAlchemy identity models.
2. Model-level constraints and relationships.
3. Alembic migration generation.
4. Migration review.
5. Identity schema tests.
6. Authentication/session implementation.

No development, staging, or production database schema should be mutated before the appropriate authorization and migration-review gates are satisfied.

## Status

**Design specification — awaiting explicit approval before implementation.**
