# Database Schema: Phase 1 - Core Architecture

This document defines the initial database schema for Gatekeyp, focusing on the core infrastructure needed to manage keys and associated content blocks.

## 1. Entities Overview

### 1.1 Keys
The `keys` table stores the unique identifiers used to unlock specific content.
- **KeyID**: A unique identifier (e.g., UUID or a hash).
- **Hashed_Value**: The actual value the user provides (stored as a hash for security if necessary, though the spec suggests opaque keys).
- **Type**: The category of key (e.g., "access", "administrative").
- **Created_At / Expires_At**: Timestamps for management and rotation.

### 1.2 Events
The `events` table represents organized gatherings or occurrences.
- **EventID**: Unique identifier for the event.
- **Title/Description**: Basic information (encrypted or plain depending on access level).
- **Organizer_ID**: Reference to the entity creating the event.
- **Location_Data**: Raw coordinate data, only accessible if linked key is valid.

### 1.3 Content Blocks
The `content_blocks` table holds specific segments of information that are "gated" by a Key.
- **BlockID**: Unique identifier for the content chunk.
- **KeyID**: Reference to the required key to unlock this block.
- **Content_Type**: Type (e.g., "location", "media_url", "contact_info").
- **Payload**: The actual data (potentially encrypted).

## 2. Relationships

- **Event -> Content Blocks**: One event contains many content blocks.
- **Key -> Content Blocks**: A key can unlock one or more content blocks. In a decentralized setup, a single Key could potentially be used across different events if shared by the same organizer.

## 3. Schema Definition (Proposed SQL structure)

### `keys` Table
| Column | Type | Description |
| :--- | :--- | :--- |
| id | UUID / VARCHAR | Primary Key. The internal identifier. |
| hash_key | VARCHAR(64) | The hashed representation of the input key. |
| type | VARCHAR(32) | e.g., "access", "master". |
| expires_at | TIMESTAMP | Optional expiration date. |

### `events` Table
| Column | Type | Description |
| :--- | :--- | :--- |
| id | UUID / VARCHAR | Primary Key. |
| title | TEXT | Name of the event. |
| description | TEXT | General info (public/limited). |
| organizer_id | VARCHAR | ID of the creator. |

### `content_blocks` Table
| Column | Type | Description |
| :--- | :--- | :--- |
| id | UUID / VARCHAR | Primary Key. |
| event_id | VARCHAR | Foreign Key to `events`. |
| key_id | VARCHAR | Foreign Key to `keys`. |
| content_type | VARCHAR(32) | e.g., "location", "media". |
| payload | TEXT | The actual data or reference link. |

## 4. Federation Support
To support multi-instance capabilities, the `key_id` and `event_id` should be globally unique (e.g., prepended with an owner identifier like `@org:instance`) to ensure that a key found on one server does not conflict with another unless intentionally shared.