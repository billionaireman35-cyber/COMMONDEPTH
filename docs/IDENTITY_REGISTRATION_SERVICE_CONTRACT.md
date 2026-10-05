# COMMONDEPTH Identity Registration Service Contract

## Status

Approved service-level contract derived from the Identity Registration
Contract.

This document defines the application-service boundary for registration.
It does not implement the API endpoint.

---

## 1. Service Responsibility

The Identity Registration Service owns the complete registration use case.

It coordinates:

- input validation
- email normalization
- duplicate identity detection
- password hashing
- User creation
- UserIdentity creation
- PasswordCredential creation
- optional Device creation
- session creation
- transaction commit/rollback
- safe error translation

The service does not own HTTP transport concerns.

---

## 2. Transaction Ownership

The service owns the registration transaction.

The repository performs persistence operations but never commits or rolls
back the registration transaction.

A successful operation commits exactly one logical registration transaction.

Any failure rolls the transaction back so that partial identity records cannot
remain.

---

## 3. Registration Inputs

The service accepts:

- email
- password
- optional device metadata

The service does not accept:

- user ID
- username
- display name
- wallet address
- blockchain address
- account status
- session ID
- password hash

Server-owned fields are never client-controlled.

---

## 4. Email Normalization

The service applies the approved deterministic normalization policy:

1. trim surrounding whitespace
2. convert to lowercase
3. do not remove dots
4. do not remove plus-tags
5. do not apply provider-specific Gmail transformations

The normalized value becomes the email provider subject.

Provider:

`email`

---

## 5. Duplicate Identity Handling

The service may perform a pre-check using the repository for efficient
validation.

The database unique constraint remains authoritative.

Concurrent registration attempts must safely handle the uniqueness conflict.

A duplicate registration must not create a second `User`.

The API layer must translate the service result according to the approved
account-enumeration policy.

Raw database integrity exceptions must never cross the API boundary.

---

## 6. Password Handling

The service validates the password policy before persistence.

Current MVP policy:

- minimum length: 12 characters
- maximum length: 128 characters
- empty passwords rejected
- passwords exceeding 128 characters rejected
- no silent truncation

The service calls:

`hash_password(password)`

It never implements Argon2id directly.

The plaintext password must not be persisted or logged.

The resulting password hash is stored only in `PasswordCredential`.

---

## 7. User Creation

The service creates a new `User` with:

`status="active"`

The UUID is generated server-side.

The service does not accept a client-supplied user ID.

---

## 8. Identity Creation

The service creates:

`UserIdentity(provider="email", provider_subject=<normalized email>)`

The identity references the newly created `User.id`.

The provider subject is an authentication identifier, not a public social
identifier.

---

## 9. Password Credential Creation

The service creates exactly one password credential for the email/password
identity.

The credential contains only:

- user_identity_id
- password_hash
- password_changed_at
- created_at
- updated_at

No plaintext password is stored.

---

## 10. Device Creation

Device creation is optional.

If supplied, device data is validated against the approved Identity device
contract.

The resulting device references the newly created `User.id`.

Unnecessary hardware identifiers are rejected.

---

## 11. Session Creation

Successful registration immediately creates an authenticated session.

The service generates a cryptographically secure opaque random token.

Only a protected hash of the token is persisted in `sessions.token_hash`.

The raw token exists only long enough to construct the authenticated response.

Initial session lifetime:

`30 days absolute`

The session references:

- the new User
- the optional Device
- creation timestamp
- expiration timestamp

Session revocation remains supported.

---

## 12. Session Token Security

The session token must be generated using a cryptographically secure random
source.

The service must not use:

- UUIDs as bearer session tokens
- timestamps
- predictable counters
- usernames
- email addresses
- passwords
- provider subjects
- database IDs

The persisted token representation uses SHA-256 over the cryptographically
random bearer token.

Because the bearer token is generated with high entropy from a cryptographically
secure random source, a deliberately slow password hashing algorithm is not
required for session-token lookup.

The raw session token must never be logged.

---

## 13. Registration Result

The service returns an internal result object containing only data required by
the API layer.

Conceptually:

- canonical user ID
- session identifier where required
- raw session token for immediate authentication
- session expiration
- safe account metadata explicitly approved by the API contract

The result must never contain:

- password hash
- database credentials
- provider secrets
- private device identifiers
- wallet credentials
- private keys
- seed phrases
- financial credentials

---

## 14. Error Contract

The service exposes typed application-level outcomes rather than raw database
exceptions.

Expected registration failures include:

- invalid registration input
- invalid password policy
- duplicate identity
- persistence conflict
- unexpected internal failure

The service must not expose SQL statements, database credentials, hashes, or
internal security state.

Unexpected failures must trigger transaction rollback and safe error handling.

---

## 15. Authorization Boundary

Registration does not perform authorization for unrelated resources.

The newly authenticated user receives authentication state only.

It does not grant access to:

- another user's resources
- wallets
- financial transactions
- organizations
- administrative functions
- moderation administration

---

## 16. Financial Boundary

The service must not import or invoke Financial-domain services.

It must not:

- create wallets
- create blockchain addresses
- access balances
- create transactions
- sign transactions
- invoke relayers
- access Goldx corporate wallets
- access Goldx Vault or Safe

---

## 17. AI Boundary

The service does not delegate identity or authentication decisions to AI.

AI cannot:

- create canonical identities
- validate passwords
- authorize registration
- create sessions
- determine wallet ownership

Registration remains deterministic and server-authoritative.

---

## 18. Testing Requirements

Before the service is exposed through an API route, tests must cover at least:

1. successful registration
2. normalized email identity
3. 12-character password acceptance
4. empty password rejection
5. password below minimum rejection
6. password above maximum rejection
7. password hash is not plaintext
8. User starts active
9. UserIdentity references User
10. PasswordCredential references UserIdentity
11. optional Device references User
12. authenticated Session creation
13. 30-day session expiration
14. raw session token is not persisted
15. duplicate identity rejection
16. transaction rollback on failure
17. no partial registration after failure
18. concurrent duplicate protection
19. safe handling of database integrity errors
20. no sensitive information in returned result

---

## 19. API Separation

The service must remain independent of FastAPI request/response objects.

The API layer is responsible for:

- HTTP request parsing
- schema validation
- authentication response formatting
- HTTP status mapping
- transport-specific error responses

The service is responsible for Identity business rules.

---

## 20. Implementation Rule

Before implementation:

1. inspect existing session/security dependencies
2. identify exact files to modify
3. create timestamped backups for every existing target file
4. create new files without requiring backups
5. implement the smallest service/security primitives
6. test each primitive
7. inspect the complete diff
8. run regression tests
9. perform security review
10. only then create the API route

No unrelated refactoring is permitted.
