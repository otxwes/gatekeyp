# Federation Specification

## 1. Overview
To support a decentralized architecture, the system must allow "Key" validation across different instances without requiring every instance to host every key. This is crucial for community-driven growth where separate groups might host their own local content while still allowing shared access.

## 2. Federation Mechanisms
- **Local Validation:** A key belongs specifically to one instance/organizer.
- **Cross-Instance Handshake (Optional):** If an organizer wants a "shared" key that works across multiple instances, the system can use a federated lookup.
- **Identity Resolution:** Use something similar to Matrix's `@user:server` or ENS names to identify which instance owns the root of a specific content block.

## 3. Compatibility Standards
- **Decentralized Identifiers (DIDs):** Explore using DIDs for organizer identities to ensure unique, platform-agnostic identification.
- **Gateway Protocol:** A standardized API method that allows `Instance A` to query `Instance B` to verify if a Key is valid and which content it unlocks.

## 4. Implementation Strategy
1. **Primary Selection:** Initially support "Local" federation where the user's client knows which host to check based on a prefix in the key or an invitation link.
2. **Fallback Mechanism:** If local lookup fails, provide a way for admins to cross-reference keys between trusted partner instances via a shared public key infrastructure (PKI).

## 5. Scalability
- The system should prioritize "local-first" resolution to minimize inter-network traffic and potential tracking points during the federation handshake.