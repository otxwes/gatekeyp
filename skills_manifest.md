# Project Skills Manifest

This document tracks the technical capabilities and "skills" (derived from the `anthropics/skills` framework) that will be utilized during the development of Gatekeyp.

## 1. Development & Technical Skills
*Primary use: Phase 1 (Core Architecture) and Phase 4 (Map & Navigation)*

- **Backend Development:** Implementation of "Key" logic, cryptographic hashing, and database schema design.
- **Map Integration:** Logic for interfacing with OpenStreetMap and other non-tracking map providers.
- **Security Hardening:** Ensuring the system is robust against surveillance and unauthorized access.

## 2. Document Skills (docx, pdf, pptx, xlsx)
*Primary use: Phase 2 (Content & Communication Layer)*

- **Asset Processing:** Handling and processing of event flyers, descriptions, and other media assets uploaded by organizers.
- **Reporting:** Generating automated summaries or reports for community administrators.

## 3. API Integration Skills
*Potential use: Phase 2 and Future Iterations*

- **Advanced Features:** Potential integration of AI-driven features in communication boards (e.g., moderation, summarization).
- **Search Capabilities:** Enhancing internal search functionality within the platform.

## 4. Template & Custom Instruction Skills
*Internal Tooling: Used across all phases*

- **Specialized Modes:** Creating specific "modes" for development tasks, such as a "Security Audit" mode or a "UI/UX Design" iteration mode to ensure the interface remains aesthetically compelling and intuitive.

---

## Installed Skills

| Skill | Source | Purpose |
| :--- | :--- | :--- |
| `coding_principals.md` | [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) | Behavioral guidelines to reduce LLM coding mistakes (Karpathy Guidelines). |
| `security_audit.md` | Custom | Auditing code/architecture for surveillance resistance, data privacy, and security hardening. |
| `ui_ux_design.md` | Custom | Creating an aesthetically compelling, intuitive, mobile-first user experience. |
| `property_based_testing.md` | Adapted from [trailofbits/skills](https://github.com/trailofbits/skills) | Property-based testing guidance (Hypothesis) for stronger test coverage. |
| `supply_chain_audit.md` | Adapted from [trailofbits/skills](https://github.com/trailofbits/skills) | Identifies dependencies at heightened risk of exploitation or takeover. |
| `insecure_defaults.md` | Adapted from [trailofbits/skills](https://github.com/trailofbits/skills) | Detects fail-open insecure defaults (hardcoded secrets, weak auth, permissive security). |
| `modern_python.md` | Adapted from [trailofbits/skills](https://github.com/trailofbits/skills) | Modern Python tooling (uv, ruff, ty) and best practices. |

## Mapping to Project Roadmap
| Project Phase | Relevant Skills | Purpose |
| :--- | :--- | :--- |
| **Phase 1: Core Architecture** | Development & Technical | Building key logic, database, and secure backend. |
| **Phase 2: Content & Communication** | Document Skills | Handling flyers, descriptions, and media files. |
| **Phase 3: Frontend & UX/UI Design** | Template / Custom | Ensuring the interface is intuitive and visually appealing. |
| **Phase 4: Map & Navigation** | Development & Technical | Integrating open-source maps and geofencing. |
| **Phase 5: Payment & Ticketing** | Development & Technical | Implementing secure payment rails (e.g., Monero). |

## Skill-to-Phase Alignment
| Skill | Primary Phase | Notes |
| :--- | :--- | :--- |
| `coding_principals.md` | All | Baseline behavioral guidelines for all coding tasks. |
| `security_audit.md` | All | Security review across all phases; aligns with `docs/threat_model.md`. |
| `ui_ux_design.md` | Phase 3 | Frontend & UX/UI Design. |
| `property_based_testing.md` | Phase 1 | Strengthens test coverage for key logic, serialization, and crypto. |
| `supply_chain_audit.md` | Phase 1 | Audits dependencies (cryptography, argon2-cffi, pytest). |
| `insecure_defaults.md` | Phase 1 | Reviews config/env handling for fail-open vulnerabilities. |
| `modern_python.md` | All | Modern Python tooling for project setup and migration. |
