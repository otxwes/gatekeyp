# Threat Model: Gatekeyp

## 1. Purpose

This document identifies the primary adversaries, trust boundaries, and data flows of Gatekeyp. It guides security decisions across all development phases, prioritizing **data minimization**, **local-first architecture**, and **resistance to surveillance** per the project's core tenets.

## 2. Adversaries

| Adversary | Motivation | Capabilities |
| :--- | :--- | :--- |
| **State actors** | Identify attendees, map social networks, suppress organizing | Network surveillance, subpoenas, infrastructure compromise, legal coercion of hosts |
| **Corporations / data brokers** | Data mining, profiling, monetization of user data | Third-party SDKs, analytics, cross-site tracking, ad networks |
| **Malicious attendees** | Access restricted content, deanonymize others, disrupt events | Brute-force keys, social engineering, scraping public data |
| **Compromised instance host** | Data theft, censorship, surveillance | Full access to server, database, logs, network traffic |
| **Passive network observer** | Traffic analysis, metadata collection | Packet capture, DNS monitoring, TLS metadata |

## 3. Trust Boundaries

```
[User Client] --(TLS)--> [Instance Gateway] --(local)--> [Database]
                              |
                              | (federated, optional)
                              v
                        [Peer Instance]
```

- **Boundary A (Client ↔ Gateway):** User provides keys and requests content. Must be TLS-encrypted. No third-party analytics or tracking SDKs allowed.
- **Boundary B (Gateway ↔ Database):** Internal. Database must encrypt sensitive payloads at rest. Keys stored as keyed hashes, never plaintext.
- **Boundary C (Instance ↔ Peer):** Federated key validation. Must be opt-in, minimal data exchange (only key validity + content metadata), and authenticated.

## 4. Data Inventory & Sensitivity

| Data | Sensitivity | Storage Requirement |
| :--- | :--- | :--- |
| Event location coordinates | **High** | Encrypted at rest; only returned with valid key |
| Contact info (organizer/attendee) | **High** | Encrypted at rest; only returned with valid key |
| Communication board posts | **Medium** | Encrypted at rest; key-gated |
| Event titles/descriptions | **Low-Medium** | Plaintext or encrypted; public/limited |
| Key hashes | **Medium** | Keyed hash (HMAC) or Argon2id; never plaintext |
| IP addresses / access logs | **Medium** | Minimize retention; no PII; aggregate only |
| Organizer identity (DID) | **Medium** | Public by design (federation); no real-world linkage |

## 5. Key Threats & Mitigations

### 5.1 Offline brute-force of keys
- **Threat:** Attacker obtains the database and brute-forces low-entropy keys stored as plain SHA-256.
- **Mitigation:** Store keys as **HMAC-SHA256** keyed by a per-instance secret, or **Argon2id** with per-key salt. Enforce minimum key entropy at generation.

### 5.2 Key enumeration / online brute-force
- **Threat:** Attacker guesses keys via the API.
- **Mitigation:** Rate limiting on the gateway (per-IP and per-key), exponential backoff, and audit logging of failed attempts.

### 5.3 Data exfiltration from compromised host
- **Threat:** Host compromise exposes event locations and contact info.
- **Mitigation:** Encryption at rest (Fernet/AES-GCM) with a master key stored outside the database (e.g., env var / KMS). Key-gated access enforced at the application layer.

### 5.4 Metadata leakage / traffic analysis
- **Threat:** Passive observer correlates requests to identify event attendees.
- **Mitigation:** Local-first resolution (minimize federated traffic), TLS everywhere, no third-party analytics, minimal logging (no PII), consider Tor/onion service support.

### 5.5 Key revocation / rotation
- **Threat:** A leaked key remains valid indefinitely.
- **Mitigation:** Support key expiration (TTL), revocation lists, and rotation workflows. Expired/revoked keys rejected at validation.

### 5.6 Federated validation abuse
- **Threat:** A malicious peer instance harvests key validity data or content metadata.
- **Mitigation:** Federated validation is opt-in, authenticated (mutual TLS or signed requests), and returns only minimal data (valid/invalid + content type, not payloads).

## 6. Data Minimization Principles

1. **Collect only what's necessary:** No analytics SDKs, no device fingerprinting, no persistent cross-instance identifiers.
2. **Minimize log retention:** Logs contain no PII; aggregate counts only; auto-purge after a short window.
3. **Local-first:** Resolve keys locally whenever possible; federated lookups only when explicitly configured.
4. **Anonymity by default:** Users can interact without accounts where the feature allows; no mandatory social graph.

## 7. Security Checklist (per phase)

### Phase 1 Status
- [x] No third-party tracking/analytics dependencies
- [x] All sensitive payloads encrypted at rest (Fernet/AES-GCM)
- [x] Keys stored as keyed hashes (HMAC-SHA256), never plaintext
- [x] Rate limiting on all key-validation endpoints (per-IP and per-key, exponential backoff)
- [x] Audit logging without PII (structured, no raw keys)
- [ ] TLS enforced on all external connections (deferred to Phase 2+ when web framework is added)
- [x] Key expiration + revocation supported
- [ ] Federated validation is opt-in and authenticated (deferred to Cross-Cutting: Federation)
- [x] Threat model reviewed and updated each phase
