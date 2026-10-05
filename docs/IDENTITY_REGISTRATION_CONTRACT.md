# COMMONDEPTH Identity Registration Contract

## Status

Design contract for the first Identity registration implementation.

This document defines the security and application boundary for MVP account
registration. It does not implement registration and does not define the
public Profile or Social Graph domains.

---

## 1. Purpose

Registration creates the canonical COMMONDEPTH user identity and establishes
the initial authentication state.

The registration operation may create:

1. a `User`
2. a `UserIdentity`
3. a `PasswordCredential`
4. an optional `Device`
5. an initial authenticated `Session`

These records belong to the Identity domain.

---

## 2. MVP Authentication Method

The first registration flow uses:

- email identity
- password authentication

The email is represented through:

`UserIdentity(provider="email", provider_subject=<normalized email>)`

The email is not stored directly on `users`.

Passwords are stored only as an Argon2id password hash through the existing
password security service.

Plaintext passwords must never be persisted, logged, returned by an API, or
placed in exceptions.

---

## 3. Canonical User Identity

Every successful registration creates a server-generated UUID `User.id`.

`User.id` is the immutable internal identity used by other COMMONDEPTH domains.

Registration must not use:

- username
- display name
- wallet address
- blockchain address
- provider subject
- email address

as the canonical cross-domain user identifier.

---

## 4. Registration Input

The initial registration request contains:

- `email`
- `password`
- optional initial device metadata

The registration API must not require:

- wallet connection
- token ownership
- blockchain address
- crypto payment
- public username
- profile information

Social profile creation is a separate domain operation.

---

## 5. Email Handling

The email provider subject must have one deterministic normalization policy.

The same normalized registration identity must map to the same
`(provider, provider_subject)` pair.

The existing database unique constraint remains authoritative:

`uq_user_identities_provider_subject`

Application-level checks may provide a friendly duplicate response, but they
must not replace the database constraint.

Registration must handle a concurrent duplicate safely without creating a
second identity.

Email normalization is deterministic:

- trim surrounding whitespace
- normalize to lowercase
- do not apply provider-specific transformations such as Gmail dot removal
  or plus-tag removal

Provider-specific transformations must not silently change identity semantics.

---

## 6. Password Requirements

Registration passes the supplied password to the existing password security
service.

The service is responsible for Argon2id hashing.

The registration service must not implement password hashing independently.

Password policy is explicit and deterministic:

- minimum length: 12 characters
- enforce a reasonable maximum input length
- reject empty passwords
- reject passwords exceeding the maximum
- do not silently truncate passwords
- do not store plaintext passwords
- do not log passwords
- do not return password hashes through API responses

Password policy may be strengthened later without changing the Identity data
model.

---

## 7. Device Handling

Device registration is optional at the API boundary.

If device metadata is supplied, only security-relevant metadata defined by the
Identity model may be accepted.

The system must not require unnecessary hardware identifiers.

Any device identifier that is persisted must use the approved protected or
derived representation rather than storing an unnecessary raw hardware
identifier.

Device creation must remain associated with the newly created `User.id`.

---

## 8. Initial Session

A successful registration creates an authenticated session immediately.

Email verification is outside the MVP registration flow.

The session record stores only the protected session representation:

`token_hash`

The raw session token must never be persisted.

The raw token may be returned only through the intended authenticated-session
response mechanism.

Sessions must have:

- server-generated UUID
- explicit expiration
- protected token representation
- creation timestamp
- optional device association
- revocation support

Initial session policy:

- token is a cryptographically secure opaque random value
- only the protected token hash is persisted
- absolute session lifetime: 30 days
- session revocation is supported

Session rotation, idle timeout, and additional session-hardening policy may be
defined in the broader authentication/session contract.

---

## 9. Transaction Boundary

Registration is one logical Identity transaction.

The Identity Service owns the transaction boundary.

The repository layer must not commit or rollback the transaction.

Conceptually:

    begin transaction
        create User
        create UserIdentity
        create PasswordCredential
        optionally create Device
        create Session
    commit transaction

If any required operation fails:

    rollback transaction

A partial registration must not remain in the database.

---

## 10. Repository Boundary

`IdentityRepository` remains persistence-focused.

It may:

- retrieve identities
- retrieve users
- add users
- add identities
- add password credentials
- add devices

It must not:

- hash passwords
- generate authentication tokens
- decide authorization
- decide account lifecycle policy
- commit registration transactions
- expose private credentials
- perform financial operations

The Identity Service coordinates the business operation.

---

## 11. Account Lifecycle

Registration may create only an eligible new account.

A newly registered user starts with:

`status="active"`

unless a separately approved registration/verification policy requires a
different initial state.

Existing suspended, deactivated, pending-deletion, or deleted identities
must not be silently converted into new active accounts.

Deleted canonical user IDs are never reused.

---

## 12. Authentication and Authorization Boundary

Registration establishes authentication state.

It does not grant authority over:

- wallets
- blockchain assets
- financial transactions
- organizational resources
- administrative functions
- moderation administration
- another user's resources

A valid registration session is not equivalent to unrestricted authorization.

Every protected resource remains subject to server-side object-level
authorization.

---

## 13. Privacy

Registration must minimize collection.

The system must not collect or persist information merely because it could be
useful later.

Authentication email and security metadata are not automatically public
profile information.

Registration must not expose:

- password hashes
- session hashes
- provider secrets
- device security identifiers
- internal authentication metadata

through public profile or social APIs.

---

## 14. Error Behavior

Registration errors must not leak sensitive authentication information.

Duplicate identity handling must be designed consistently with the account
enumeration policy.

Database integrity errors must not be returned as raw database exceptions.

Unexpected internal failures must fail safely and must not expose secrets,
SQL statements, credentials, hashes, or internal security state.

---

## 15. Observability and Audit

Registration failures and security-relevant events must be observable without
logging secrets.

Logs must not contain:

- plaintext passwords
- raw session tokens
- password hashes
- reset tokens
- private keys
- seed phrases
- wallet signing material

Security/audit events may record safe identifiers and operational metadata
according to the approved retention policy.

---

## 16. Financial and Blockchain Boundary

Registration has no dependency on the Financial domain.

Registration must not:

- create a wallet
- create a blockchain address
- connect a wallet
- require token ownership
- require cryptocurrency payment
- create a blockchain transaction
- invoke Goldx Vault
- invoke Goldx Safe
- invoke a relayer
- access corporate wallets
- create financial ledger entries

Crypto remains infrastructure and an optional future capability.

---

## 17. AI Boundary

AI is not authoritative for registration security.

AI must not determine:

- canonical user identity
- password validity
- session validity
- authorization
- wallet ownership
- financial signing authority

Registration security decisions remain deterministic and server-side.

Future AI-assisted fraud or abuse signals may be introduced as a separate
security/moderation capability without changing the Identity authority model.

---

## 18. API Response Boundary

A successful registration response may contain only information explicitly
approved by the API contract.

It must never return:

- password hash
- raw database credentials
- provider secrets
- internal security metadata
- private device identifiers
- financial credentials

The canonical internal user UUID may be returned only where the API contract
requires it.

The public username/profile is not implicitly created by registration.

---

## 19. Idempotency and Concurrency

Registration is not assumed to be safely repeatable merely because the client
retries.

Concurrent requests for the same authentication identity must be protected
by the database uniqueness constraint and transaction handling.

If an explicit idempotency mechanism is introduced, it must be separately
designed and must not weaken identity uniqueness.

---

## 20. Implementation Order

Before implementing the registration endpoint:

1. finalize email normalization
2. finalize password policy
3. finalize session token format and lifetime
4. finalize device input policy
5. define request/response schemas
6. define service contract
7. define expected error behavior
8. add service tests
9. implement the service
10. add API route
11. add API integration tests
12. inspect migration/schema impact
13. run security and regression validation
14. review the complete diff

No schema change should be introduced unless the Identity model or approved
requirements actually require it.

---

## 21. Explicit Non-Goals

This contract does not implement:

- email verification
- password reset
- OAuth/OIDC
- magic links
- passkeys/WebAuthn
- multi-factor authentication
- username creation
- public profile creation
- follow relationships
- feed generation
- messaging
- wallet connection
- crypto payments
- blockchain identity

Those capabilities require their own reviewed contracts.

---

## 22. Engineering Rule

The registration implementation must remain narrowly scoped to Identity.

The implementation must follow:

Inspect → design → backup existing targets → implement narrowly → test →
review diff/security → broader validation.

No unrelated refactoring is permitted during registration implementation.
