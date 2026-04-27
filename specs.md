# ANOMALY-WIKI Product Specifications

## 1. Project Overview
ANOMALY-WIKI is an interactive, microservice-based encyclopedia dedicated to the research records of the S.T.A.L.K.E.R. universe. It serves as a structured knowledge base for anomalies, artifacts, locations, and incidents, supporting a professional workflow for researchers and editors.

## 2. User Roles & Permissions
| Role | Permissions |
| :--- | :--- |
| **Public Reader** | View approved (published) encyclopedia content and media. Perform searches. |
| **Researcher** | Create drafts, suggest edits, and view internal/unapproved records. |
| **Editor** | Review, approve, publish, and redact content. Manage revisions. |
| **Admin** | Manage users, roles, permissions, and system-wide configurations. |

## 3. Core Functional Requirements

### 3.1 Researcher Authentication Service
- **User Management**: Registration, profile management for researchers.
- **Authentication**: Secure login/logout using token-based auth (e.g., JWT).
- **Authorization**: Role-based access control (RBAC) to distinguish between researchers, editors, and admins.

### 3.2 Encyclopedia Service
- **Page Management**: CRUD operations for various page types (Anomaly, Artifact, Location, Incident, Expedition, Researcher Note).
- **Content Format**: Canonical content stored in Markdown.
- **Revision Control**: 
  - Git-like immutable revision history.
  - Every edit creates a new revision with a parent reference.
  - Support for optimistic locking to handle edit conflicts.
- **Workflow State Machine**: Pages transition through states: `Draft` -> `Review` -> `Published` -> `Archived/Redacted`.
- **Relationships**: Linking pages to each other and to media assets.

### 3.3 Media Service 
- **Asset Storage**: Upload and storage of binary files (images, audio, PDF).
- **Metadata**: Management of asset IDs, MIME types, and sizes.
- **Retrieval**: Generation of stable URLs or signed URLs for secure access.

### 3.4 Search & Indexing
- **Search Capabilities**: Full-text search across titles, summaries, and Markdown bodies.
- **Filtering**: By page type, tags, and visibility status.
- **Indexing**: Asynchronous updates to the search index triggered by content changes in the Encyclopedia or Media services.

## 4. Technical Architecture

### 4.1 Microservices Definition
- **API Gateway**: Entry point for all clients. Handles routing, rate limiting, and CORS.
- **Researcher Auth Service**: Manages identity and access.
- **Encyclopedia Service**: Source of truth for structured content and history.
- **Media Service**: Manages binary assets.
- **Search Indexer Service**: Event-driven worker that transforms content into searchable documents.
- **Search Service**: High-performance retrieval service for search queries.

### 4.2 Data Storage
- **Relational Database**: For metadata, user records, and revision history (PostgreSQL recommended).
- **Object Storage**: For binary media files (S3-compatible).
- **Search Engine**: For indexed search documents (Elasticsearch or OpenSearch).

### 4.3 Communication
- **Synchronous**: REST or gRPC via API Gateway for user-facing operations.
- **Asynchronous**: Event bus (e.g., RabbitMQ, Kafka) for propagation of content updates to the indexer.

## 5. Entity Models

### 5.1 Page
- `id`: UUID
- `slug`: String (unique)
- `type`: Enum (Article, Anomaly, etc.)
- `status`: Enum (Draft, Published, etc.)
- `visibility`: Enum (Public, Internal)
- `current_published_revision_id`: UUID
- `current_draft_revision_id`: UUID

### 5.2 Revision
- `id`: UUID
- `page_id`: UUID
- `parent_revision_id`: UUID (nullable)
- `author_id`: UUID
- `title`: String
- `summary`: Text
- `content`: Markdown Text
- `created_at`: Timestamp

### 5.3 Media Asset
- `id`: UUID
- `filename`: String
- `mime_type`: String
- `storage_path`: String
- `uploaded_by`: UUID
