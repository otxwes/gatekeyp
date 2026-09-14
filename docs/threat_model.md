# Threat Model: gatekeyp

## 1. Purpose

This document identifies the primary adversaries, trust boundaries, and data flows of gatekeyp. It guides security decisions across all development phases, prioritizing **data minimization**, **local-first architecture**, and **resistance to surveillance** per the project's core tenets.

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
- [x] TLS enforced on all external connections (FastAPI server with HTTPS support)
- [x] Key expiration + revocation supported
- [ ] Federated validation is opt-in and authenticated (deferred to Cross-Cutting: Federation)
- [x] Threat model reviewed and updated each phase

### Phase 2 Status
- [x] Media uploads validated (MIME-type allowlist, 10 MB size limit)
- [x] Media assets, bulletins, and comments encrypted at rest (Fernet/AES-GCM)
- [x] All content access key-gated (valid key required for upload/retrieval)
- [x] No third-party tracking/analytics in web UI
- [x] Web UI served from same process (no external CDN dependencies)
- [x] Event lifecycle management enforces key expiration and revocation
- [x] Threat model reviewed and updated each phase

### Phase 3.6 Status (Steganographic Invite Keys)
- [x] Invite-card distribution is **PNG-only and stego-only**: LSB stego is destroyed by lossy re-encode — documented in `docs/steganography_invites.md` §6. The Phase-3.6 printed-QR fallback was **removed in Phase B** (a scannable key is a secrecy downgrade — a photographed card yields its credential to anyone, no steganography suspicion required); the survives-re-encode fallback is the paste-anywhere `gkp:` key line, and the door rejects unreadable files with a specific, honest message.
- [x] The card embeds only the same bearer credential the attendee would type (`event_id` + `access_key`); expiry, revocation, rate limiting and server-side HMAC verification are unchanged — no new server surface, no key storage.
- [x] Keys remain 128-bit random, shown once, never persisted; the per-row card action re-asks for the raw key rather than retrieving it.
- [x] Decode happens entirely client-side; a non-PNG or keyless image is rejected locally with no server round-trip.
- [x] Detectability is documented as casual-opacity, not cryptographic secrecy: LSB replacement is statistically detectable by a motivated analyst who already suspects steganography; the key itself remains the secret.
- [x] No vendored third-party assets remain (Phase B removed `qrcode-generator` and `jsQR` with the QR path); no third-party tracking/analytics in the web UI.
- [x] Threat model reviewed and updated each phase

### Phase B Status (RSVP Pull-Flow Funnel — organizer approval gate)
- [x] Web half committed (`ccc0b8c`): attendee RSVP form with a `website` honeypot (a bot fill gets a canned acknowledgement; nothing is stored or minted), passphrase gate when the organizer sets one, pending/approved result states, single-show access key on approval; organizer RSVP tab with share link, gate settings (passphrase + auto-approve) and the approve/deny queue.
- [x] Invite cards are opaque and stego-only: the printed QR and the door's QR decode fallback (`web/door_qr.js`, `web/vendor/` — jsQR, qrcode-generator) are removed. **QR = secrecy downgrade**: a scannable key can be harvested en masse from photos/screenshots without any suspicion of steganography; the hidden-pixels form at least forces targeted suspicion. The paste-anywhere `gkp:` key line is the fallback for damaged cards.
- [x] Server half landed (`ec1a141`): RSVP request queue (`src/rsvp/`), gateway pending gate, database tables for server-held pre-minted approved-but-unclaimed keys. Threat-model review of that storage, 2026-09-13 — all four flagged questions cleared:
- [x] **At-rest exposure: none beyond the existing boundary.** A pre-minted key is stored **only as a keyed HMAC** (`keys.hash_key` via `KeyManager.hash_key`, mirrored in `rsvps.key_hash`) — the same digest-only representation as every other GateKeyP key. The raw key is returned exactly once in the 201 response and never persisted. A stolen DB copy yields digests, not credentials; recovering raw keys would require the server HMAC secret, which is already total compromise (the same secret decrypts the Fernet-encrypted contacts, which are stored encrypted and tested as such).
- [x] **TTL: inherited and door-enforced.** Every pre-minted key carries `expires_at = now + 30 days` (`DEFAULT_ACCESS_KEY_DAYS`, same as organizer-issued access keys), and `validate_key` rejects expired keys at the door independent of RSVP status — a never-decided key self-deadlines in 30 days even if the organizer never looks. The leftover `rsvps` row is inert, bounded bookkeeping, destroyed with the event; no security-critical cleanup job exists.
- [x] **Request queue: bounded three ways.** (1) Per-IP sliding-window limiter on the unauthenticated submission endpoint — 5 per 600 s, then 429 + `Retry-After: 600`; `X-Forwarded-For` is not trusted, so header spoofing cannot rotate buckets. (2) `MAX_PENDING_RSVP_PER_EVENT = 500` — the bound that survives IP rotation, capping attacker-minted key rows per event (denial frees slots; tested). (3) The `website` honeypot — bot fills get a canned acknowledgement and mint nothing. Documented accepted limits: limiter state is in-process (per-worker, resets on restart — same trade-off as the lite funnel limiter), and a shared NAT IP gives many humans one bucket — a funnel-availability annoyance, not a key-growth path.
- [x] **Auto-approve surface: explicit organizer opt-in per event, bounded by `MAX_AUTO_APPROVE = 100000`.** Semantics as implemented and now tested: the dial keeps *up to N currently-approved* (denying one frees the slot for the next submission) — not literally "first N ever"; a denied key is revoked, and any re-approval mints a fresh granted key. Dial-on ≈ open-door mode by definition.
- [x] **Wipe cascade holds.** `wipe_event` deletes RSVP rows **and their pre-minted keys** (captured before rows vanish — pending keys carry no content links) in the same transaction, tombstone intact. Organizer endpoints are master-key-gated like the rest of the API; GETs accept `?key=` matching the established API pattern (`list_bulletins`, `get_media`, …).
- [x] Threat model reviewed and updated each phase


### Phase 3.9 Status (Mesh key delivery prototype — considered and parked)
- [x] **Decision: the LXMF/Reticulum mesh option for master-key delivery was evaluated and documented but is not enabled by default.** A working prototype exists (`src/ephemeral/lxmf_delivery.py`, opt-in via `GATEKEYP_LXMF_ENABLED=1` + the `mesh` extra) that relays an event master key to an attendee's LXMF address through the organizer's own instance; `scripts/lxmf_loopback.py` proves the send/decrypt path end to end.
- [x] **Why it was parked rather than shipped:** it re-centralises distribution on the instance's always-on network presence, the operator's node holds ciphertext (and its metadata) indefinitely instead of "browser only, wiped at expiry", and LXMF's retry/job-thread delivery model conflicts with the "key exists for the TTL, then nothing" expiry model.
- [x] **What the prototype guarantees when enabled:** the endpoint only relays keys that were actually displayed for that event (same HMAC check as the attendee unlock, via `get_keyed_view`), the destination must be a 32-hex-character LXMF destination hash, payloads are end-to-end encrypted by Reticulum (relays see ciphertext only), and gatekeyp never logs or persists the key.
- [x] **The browser "show once" flow remains the default** delivery path; mesh delivery is an explicit operator opt-in aimed at closed meshes.
- [x] Threat model reviewed and updated each phase
