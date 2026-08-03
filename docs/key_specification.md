# Gatekeyp Key Specification

## 1. Overview
The "Key" is the primary mechanism for gatekeeping content in Gatekeyp. It allows users to access restricted information (e.g., event locations, contact details) only if they possess a valid key provided by an organizer.

## 2. Key Types
- **Public Keys:** Used for identification but not for direct decryption/access of secret data (if applicable).
- **Access Keys:** Unique identifiers used to unlock specific content blocks or sections of the application.
- **Master Keys:** Administrative keys with elevated privileges.
- **Event Master Keys:** Created when an event is created (365-day default lifetime). Grants full access to all event content.
- **Attendee Access Keys:** Generated for attendees (30-day default lifetime). Grant access to event content blocks, media, bulletins, and comments.

## 3. Generation Logic
A Key should be:
- **Unique:** No two distinct keys should represent the same piece of content unless intentional.
- **Opaque:** The key itself should not reveal information about the underlying data (e.g., "Event_ID_123").
- **Robust:** Generated using a cryptographically secure random number generator (`secrets.token_hex`).
- **High-Entropy:** Minimum 128 bits (16 bytes) of randomness enforced at generation.

## 4. Validation Process
Users provide a Key to the system. The system performs:
1. **Federation Prefix Resolution:** Parse the key to determine if it's local (`local:key`) or federated (`@org:host/key`).
2. **Existence Check:** Does this key exist in the database? (Stored as HMAC-SHA256 keyed hash.)
3. **Revocation Check:** Has this key been revoked?
4. **TTL (Time to Live):** Is the key still valid for the current timeframe?

## 5. Technical Implementation Details

### Hashing (Phase 1 - Security Hardened)
- **Algorithm:** HMAC-SHA256 keyed by a per-instance secret (`GATEKEYP_HMAC_SECRET`).
- **Purpose:** Prevents offline brute-force attacks — an attacker who obtains the database cannot compute the HMAC without the secret key.
- **Constant-Time Comparison:** Uses `hmac.compare_digest` to prevent timing attacks.
- **Optional Argon2id:** Higher-cost, memory-hard verification for password-style keys.

### Format
- **Key Format:** A hex string (e.g., `k3j8f...`) to be easily copy-pasted and shared.
- **Federation Format:** `@org_name:host_identifier/key_content` or `local:key_content`.

### Fail-Secure Configuration
- `KeyManager` refuses to start without `GATEKEYP_HMAC_SECRET` environment variable.

## 6. Key Lifecycle

### Rotation
- Old key is revoked.
- New key is created.
- Content links are re-mapped from the old key to the new key.

### Revocation
- Keys can be revoked at any time.
- Revoked keys are rejected during validation.

### Expiration
- Keys can have an optional expiration timestamp.
- Expired keys are rejected during validation.

## 7. Federation Logic
To support multi-instance compatibility, the Key logic must not rely on a central global registry if possible. Instead:
- Keys are local to the instance or can be validated against a federated peer using standard protocols (e.g., Matrix-like logic for cross-server validation).
- The `owner_id` field on keys stores the federation identifier (e.g., `@org:instance`).
