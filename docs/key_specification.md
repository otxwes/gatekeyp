# Gatekeyp Key Specification

## 1. Overview
The "Key" is the primary mechanism for gatekeeping content in Gatekeyp. It allows users to access restricted information (e.g., event locations, contact details) only if they possess a valid key provided by an organizer.

## 2. Key Types
- **Public Keys:** Used for identification but not for direct decryption/access of secret data (if applicable).
- **Access Keys:** Unique identifiers used to unlock specific content blocks or sections of the application.

## 3. Generation Logic
A Key should be:
- **Unique:** No two distinct keys should represent the same piece of content unless intentional.
- **Opaque:** The key itself should not reveal information about the underlying data (e.g., "Event_ID_123").
- **Robust:** Generated using a cryptographically secure random number generator or a high-entropy hashing algorithm.

## 4. Validation Process
Users provide a Key to the system. The system performs:
1. **Existence Check:** Does this key exist in the database?
2. **Permission Mapping:** Which content blocks are associated with this key?
3. **TTL (Time to Live):** Is the key still valid for the current timeframe?

## 5. Technical Implementation Details
- **Algorithm:** SHA-256 or Ed25519 (if asymmetric keys are used for specific features).
- **Format:** A base62 or hex string (e.g., `k3j8f...`) to be easily copy-pasted and shared.

## 6. Federation Logic
To support multi-instance compatibility, the Key logic must not rely on a central global registry if possible. Instead:
- Keys are local to the instance or can be validated against a federated peer using standard protocols (e.g., Matrix-like logic for cross-server validation).
