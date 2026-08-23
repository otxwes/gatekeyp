# Research Note: Local Situation Awareness (Public Safety Radio + AI)

- **Date:** 2026-08-23 · **Status:** scoping research feeding **Phase 6** of `../roadmap.md`
- **Goal:** a privacy-preserving "situation layer" for an event — real-time, event-adjacent awareness for organizers & attendees, derived from public-safety radio and interpreted locally by an open ML pipeline.

## Bottom line
Broadcastify exposes **no public live-audio API**; the sanctioned bulk-audio path is paid (RadioReference premium, CC BY 3.0) and post-event only. The viable **real-time** path is **self-production**: SDR + `trunk-recorder` (the same open-source engine that actually supplies Broadcastify and OpenMHz feeds). Everywhere, the dominant uncontrollable blocker is **P25-AES encryption** — if an agency encrypts, the audio simply does not exist for anyone.

## What is actually available

### Broadcastify — NO public live-audio API
- **Feed Catalog API v1.3** (`broadcastify.com/api/audio/`): feed *directory* metadata — feeds by state/county, top feeds, search, genre, feed details, archive date listings. **Metadata only, no audio, licensee-gated** (official help: *"only available to approved licensees… currently not issuing additional licenses… contact support with details of your plans"*).
- **Feed Owner API v0.9** (`broadcastify.com/api/owner/`): feed health + archive URLs, via RadioReference login — feed **providers only**, for their own feeds; archives are personal-use, no redistribution.
- **Calls Upload API**: **push-only** — you upload `.m4a`/`.mp3` clips + talkgroup metadata **to** Broadcastify. Public consumption of Calls is their premium web player (`broadcastify.com/calls`).
- **Live listener streams**: Shoutcast-style; **no API exists** and third-party programmatic consumption is not supported.

### Sanctioned bulk audio (post-event / training only)
- Broadcastify/RR audio archives (up to 365 days), **"Audio Provided by Broadcastify" CC BY 3.0**, via **RadioReference premium** (paid). Usable for analysis, evaluation, and fine-tuning datasets — never real-time.

### The open real-time path (recommended for Phase 6)
- **`trunk-recorder`** (GPLv3; `github.com/trunk-recorder/trunk-recorder`, formerly `robotastic/trunk-recorder`): the open-source software that ingests the feeds behind Broadcastify/OpenMHz. With an **RTL-SDR (~$30–40)** or **AirSpy**: decodes P25 / Phase I & II trunking and produces per-talkgroup audio clips + **JSON call records** (talkgroup, system, site, frequency, source, timeslot, encryption flag).
- **Surfacing:** **Rdio Scanner** (`github.com/chuot/rdio-scanner-2`) or **Trunk Player**; alternatively this project's own minimal local `src/intel/` service.
- **OpenMHz** (`openmhz.com`, by the same author as trunk-recorder): free JSON-call API (`/calls`, `/call/{id}`, `/system/{id}`…) where a system is already monitored — zero hardware, but coverage is community/metro-dependent; **verify live availability at build time**.

## Dominant risk: encryption (pre-flight is mandatory)
- Growing **P25-AES** adoption means police audio is frequently **encrypted end-to-end**; broadcasters and listeners alike hear nothing.
- Documented example: OpenMHz's origin system is **DC** — its own about page notes DC Police run a **separate encrypted** system while Fire/EMS/City ride the open system, so OpenMHz carries Fire/EMS/City only.
- ⇒ Define the **target metro(s) first**, then run a per-metro pre-flight against the RadioReference database (**"Encryption"** flag on the system/talkgroup pages + community forums) *before* any engineering or hardware spend.

## Legal / ethics baseline (codify in `../threat_model.md`)
- Federal: receiving *unencrypted* public-safety radio is lawful (transmissions "readily accessible to the general public"). Some states restrict scanner use (in-vehicle, "in furtherance of a crime"). **Never decrypt or circumvent encryption.**
- Broadcastify's own lawful-feed rules restrict LE feeds to **routine dispatch** channels (no tactical/NCIC/records).
- Product position: we monitor **agencies, not attendees**; redact civilian PII/medical info; **no raw audio retained by default**; opt-in and transparently labeled.

## Interpretation pipeline (Phase 6 work)
1. Per-clip STT — local `faster-whisper` / `vosk` (cloud optional: Deepgram / OpenAI).
2. Talkgroup-aware structuring — *dispatch* = the permissible channel; filter routine traffic.
3. Incident-type + location extraction.
4. Geofence/alerting tied to Phase-4 map coordinates.
5. LLM "situation brief" for organizers/attendees.

## Open questions → verify at build time
- Which metro(s)?
- Real-time only, post-event only, or both?
- Local vs cloud ML; SDR hardware vs OpenMHz ingestion; budget?

## Sources
- Broadcastify help — Feed Catalog API: `broadcastify.com/api/audio/`
- Broadcastify help — Feed Owner API: `broadcastify.com/api/owner/`
- Broadcastify help — Calls Upload API: `calls.broadcastify.com/api/` · web player `broadcastify.com/calls`
- RadioReference premium (archives): `radioreference.com/premium/`
- trunk-recorder: `github.com/trunk-recorder/trunk-recorder`
- OpenMHz: `openmhz.com` (+ `/about`)
- Rdio Scanner: `github.com/chuot/rdio-scanner-2`

> Live support pages often 403 automated fetches (Cloudflare); the official help content above was read via archived copies and cross-checked against the feeds' own about/help pages. RadioReference current API-key policy and OpenMHz current SLA require re-verification at build time.
