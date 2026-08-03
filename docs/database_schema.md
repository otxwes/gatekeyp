# Database Schema: Phase 1 & 2 - Core Architecture + Content & Communication

This document defines the database schema for Gatekeyp, covering the core infrastructure for keys and content blocks, plus the content hosting and communication board tables added in Phase 2. All sensitive payloads are encrypted at rest with security hardening for encryption-at-rest and federation support.

## 1. Entities Overview

### 1.1 Keys
The `keys` table stores the unique identifiers used to unlock specific content.
- **Hash_Key**: The HMAC-SHA256 keyed hash of the user-provided key (never stored in plaintext).
- **Type**: The category of key (e.g., "access", "master").
- **Created_At / Expires_At**: Timestamps for management and rotation.
- **Revoked / Revoked_At**: Revocation status and timestamp.
- **Owner_ID**: Federation identifier (e.g., `@org:instance`).

### 1.2 Events
The `events` table represents organized gatherings or occurrences.
- **EventID**: Unique identifier for the event.
- **Title/Description**: Basic information (encrypted or plain depending on access level).
- **Organizer_ID**: Reference to the entity creating the event.
- **Location_Data**: Raw coordinate data, **encrypted at rest** (Fernet/AES-GCM), only accessible if linked key is valid.
- **Created_At**: Timestamp for management.

### 1.3 Content Blocks
The `content_blocks` table holds specific segments of information that are "gated" by a Key.
- **BlockID**: Unique identifier for the content chunk.
- **KeyID**: Reference to the required key to unlock this block.
- **Content_Type**: Type (e.g., "location", "media_url", "contact_info").
- **Payload**: The actual data, **encrypted at rest** (Fernet/AES-GCM).
- **Created_At**: Timestamp for management.

### 1.4 Key-Content Links (Many-to-Many)
The `key_content_links` join table maps keys to content items.
- **Key_Hash**: Reference to a key hash.
- **Content_ID**: Reference to a content block or event.
- **Content_Type**: Type of content ("block" or "event").

### 1.5 Media Assets (Phase 2)
The `media_assets` table stores uploaded files (flyers, images, documents) gated by Keys.
- **Asset_ID**: Unique identifier for the media asset.
- **Event_ID**: Reference to the owning event.
- **Key_ID**: Reference to the required key to access this asset.
- **Filename**: Original filename (stored encrypted).
- **Content_Type**: MIME type (validated against allowlist).
- **Size_Bytes**: File size in bytes (max 10 MB).
- **Data**: The file contents, **encrypted at rest** (Fernet/AES-GCM).
- **Created_At**: Timestamp for management.

### 1.6 Bulletins (Phase 2)
The `bulletins` table stores communication board posts gated by Keys.
- **Bulletin_ID**: Unique identifier for the bulletin.
- **Event_ID**: Reference to the owning event.
- **Key_ID**: Reference to the required key to access this bulletin.
- **Author**: Author identifier (stored encrypted).
- **Body**: The bulletin content, **encrypted at rest** (Fernet/AES-GCM).
- **Created_At**: Timestamp for management.
- **Updated_At**: Timestamp for last update.

### 1.7 Comments (Phase 2)
The `comments` table stores threaded comments on bulletins.
- **Comment_ID**: Unique identifier for the comment.
- **Bulletin_ID**: Reference to the parent bulletin.
- **Parent_Comment_ID**: Optional reference to a parent comment (for threading).
- **Author**: Author identifier (stored encrypted).
- **Body**: The comment content, **encrypted at rest** (Fernet/AES-GCM).
- **Created_At**: Timestamp for management.

## 2. Relationships

- **Event -> Content Blocks**: One event contains many content blocks.
- **Key -> Content Blocks**: A key can unlock one or more content blocks (many-to-many via `key_content_links`).
- **Key -> Events**: A key can unlock one or more events (many-to-many via `key_content_links`).
- **Event -> Media Assets**: One event has many media assets.
- **Event -> Bulletins**: One event has many bulletins.
- **Bulletin -> Comments**: One bulletin has many comments (threaded via `parent_comment_id`).

## 3. Schema Definition (SQL)

### `keys` Table
| Column | Type | Description |
| :--- | :--- | :--- |
| hash_key | TEXT PRIMARY KEY | HMAC-SHA256 keyed hash of the input key. |
| type | VARCHAR(32) | e.g., "access", "master". |
| expires_at | TEXT | Optional expiration timestamp (ISO format). |
| created_at | TEXT | Creation timestamp (ISO format, UTC). |
| revoked | INTEGER | 0 = active, 1 = revoked. |
| revoked_at | TEXT | Revocation timestamp (ISO format, UTC). |
| owner_id | TEXT | Federation identifier (e.g., `@org:instance`). |

### `events` Table
| Column | Type | Description |
| :--- | :--- | :--- |
| event_id | TEXT PRIMARY KEY | Unique identifier. |
| title | TEXT | Name of the event. |
| description | TEXT | General info (public/limited). |
| organizer_id | VARCHAR | ID of the creator. |
| location_data | TEXT | **Encrypted** coordinate data (Fernet/AES-GCM). |
| created_at | TEXT | Creation timestamp (ISO format, UTC). |

### `content_blocks` Table
| Column | Type | Description |
| :--- | :--- | :--- |
| block_id | TEXT PRIMARY KEY | Unique identifier. |
| event_id | VARCHAR | Foreign Key to `events`. |
| key_id | VARCHAR | Foreign Key to `keys`. |
| content_type | VARCHAR(32) | e.g., "location", "media". |
| payload | TEXT | **Encrypted** data (Fernet/AES-GCM). |
| created_at | TEXT | Creation timestamp (ISO format, UTC). |

### `key_content_links` Table
| Column | Type | Description |
| :--- | :--- | :--- |
| key_hash | TEXT | Foreign Key to `keys.hash_key`. |
| content_id | TEXT | Foreign Key to `content_blocks.block_id` or `events.event_id`. |
| content_type | TEXT | Type of content ("block" or "event"). |
| PRIMARY KEY | (key_hash, content_id, content_type) | Composite primary key. |

### `media_assets` Table (Phase 2)
| Column | Type | Description |
| :--- | :--- | :--- |
| asset_id | TEXT PRIMARY KEY | Unique identifier. |
| event_id | VARCHAR | Foreign Key to `events`. |
| key_id | VARCHAR | Foreign Key to `keys`. |
| filename | TEXT | **Encrypted** original filename. |
| content_type | VARCHAR(128) | MIME type (validated against allowlist). |
| size_bytes | INTEGER | File size in bytes (max 10 MB). |
| data | BLOB | **Encrypted** file contents (Fernet/AES-GCM). |
| created_at | TEXT | Creation timestamp (ISO format, UTC). |

### `bulletins` Table (Phase 2)
| Column | Type | Description |
| :--- | :--- | :--- |
| bulletin_id | TEXT PRIMARY KEY | Unique identifier. |
| event_id | VARCHAR | Foreign Key to `events`. |
| key_id | VARCHAR | Foreign Key to `keys`. |
| author | TEXT | **Encrypted** author identifier. |
| body | TEXT | **Encrypted** bulletin content (Fernet/AES-GCM). |
| created_at | TEXT | Creation timestamp (ISO format, UTC). |
| updated_at | TEXT | Last update timestamp (ISO format, UTC). |

### `comments` Table (Phase 2)
| Column | Type | Description |
| :--- | :--- | :--- |
| comment_id | TEXT PRIMARY KEY | Unique identifier. |
| bulletin_id | VARCHAR | Foreign Key to `bulletins`. |
| parent_comment_id | VARCHAR | Optional Foreign Key to `comments` (threading). |
| author | TEXT | **Encrypted** author identifier. |
| body | TEXT | **Encrypted** comment content (Fernet/AES-GCM). |
| created_at | TEXT | Creation timestamp (ISO format, UTC). |

## 4. Security Features

### Encryption at Rest
- **Master Key**: Required via `GATEKEYP_MASTER_KEY` environment variable (fail-secure).
- **Algorithm**: Fernet (AES-128-CBC + HMAC-SHA256) from the `cryptography` library.
- **Encrypted Fields**: `content_blocks.payload`, `events.location_data`, `media_assets.filename`, `media_assets.data`, `bulletins.author`, `bulletins.body`, `comments.author`, `comments.body`.
- **Key Hashes**: Stored as HMAC-SHA256 keyed by `GATEKEYP_HMAC_SECRET` (never plaintext).

### Fail-Secure Configuration
- `DatabaseHandler` refuses to start without `GATEKEYP_MASTER_KEY`.
- `KeyManager` refuses to start without `GATEKEYP_HMAC_SECRET`.

## 5. Federation Support
To support multi-instance capabilities, the `key_id` and `event_id` should be globally unique (e.g., prepended with an owner identifier like `@org:instance`) to ensure that a key found on one server does not conflict with another unless intentionally shared. The `owner_id` field on keys stores this federation identifier.
