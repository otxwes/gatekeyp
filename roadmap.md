# Project Roadmap: Decentralized Key System

## Project Overview
A decentralized "key system" designed to facilitate safe, private event organization for underground scenes, moving away from big-tech infrastructure and surveillance.

## Core Objectives
- **Privacy:** Avoid Google/Apple Maps, Meta, and other tracking-heavy platforms.
- **Autonomy:** Provide tools that can be hosted on alternative clouds (e.g., Co-op Cloud) or self-hosted.
- **Security:** Implement a "key" based access model to ensure only intended participants see event details.

---

## Development Phases

### Phase 1: Core Architecture & Key Management
*Goal: Establish the foundation of the key-based access system.*
- [ ] Define "Key" logic (cryptographic hashes/unique identifiers).
- [ ] Design Federation Logic for multi-instance compatibility.
- [ ] Develop Database Schema (linking Keys to Events and Content Blocks).
- [ ] **Current Status:** Planning / Initializing

### Phase 2: Map & Navigation Module
*Goal: Provide an alternative to mainstream mapping services.*
- [ ] Select open-source map tiles (e.g., OpenStreetMap).
- [ ] Implement basic routing/geofencing without third-party tracking.
- [ ] Link specific Keys to geographic coordinates or routes.

### Phase 3: Content & Communication Layer
*Goal: Build the interface for organizers and participants.*
- [ ] Develop content hosting (flyers, descriptions, media).
- [ ] Create "Secure Communication Boards" (bulletins/comments) restricted by Key.

### Phase 4: Payment & Ticketing System
*Goal: Implement privacy-preserving financial transactions.*
- [ ] Research and integrate privacy-focused payment rails (e.g., Monero).
- [ ] Develop ticketing logic that generates a "ticket" upon successful payment.

### Phase 5: Frontend & UX/UI Design
*Goal: Ensure the platform is intuitive and aesthetically compelling.*
- [ ] Develop a mobile-first responsive web application.
- [ ] Refine Security UI to ensure seamless user experience during key entry.

---

## Technical Stack Notes
- **Infrastructure:** Target Co-op Cloud / Self-hosted instances.
- **Maps:** OpenStreetMap (OSM) or similar.
- **Security Focus:** Minimal data retention, no third-party analytics.

## Context for Future Sessions
*This section is updated as we progress to maintain continuity.*
- Current focus: Phase 1 - Core Architecture.
