export type PageType =
  | "Article" | "Anomaly" | "Artifact" | "Location"
  | "Incident" | "Expedition" | "Researcher Note";

export type PageStatus = "Draft" | "Review" | "Published" | "Archived" | "Redacted";

export type Visibility = "Public" | "Internal";

export type UserRole = "Public" | "Researcher" | "Editor" | "Admin";

export interface Page {
  id: string;
  slug: string;
  type: PageType;
  status: PageStatus;
  visibility: Visibility;
  current_published_revision_id: string | null;
  current_draft_revision_id: string | null;
  version: number;
  tags: string[];
  classifications: Record<string, string>;
  related_page_ids: string[];
  media_asset_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface Revision {
  id: string;
  page_id: string;
  parent_revision_id: string | null;
  author_id: string | null;
  title: string;
  summary: string;
  content: string;
  created_at: string;
}

export interface RevisionLineage {
  revision: Revision;
  lineage: Revision[];
}

export interface PageState {
  page: Page;
  current_draft_revision: Revision | null;
  current_published_revision: Revision | null;
}

export interface MediaAsset {
  id: string;
  filename: string;
  mime_type: string;
  content_type?: string;
  uploaded_by: string;
  size_bytes: number;
  created_at: string;
  page_id?: string;
}

export interface SearchResult {
  page_id: string;
  slug: string;
  title: string;
  type: PageType;
  status: PageStatus;
  visibility: Visibility;
  summary: string;
  snippet: string;
  tags?: string[];
}

export interface SearchResponse {
  total: number;
  hits: SearchResult[];
}

export interface AuthToken {
  access_token: string;
  token_type: "bearer";
}

export interface CurrentUser {
  id: string;
  email: string;
  role: UserRole;
}

export interface CreatePageRequest {
  slug: string;
  type: PageType;
  visibility: Visibility;
  title: string;
  summary: string;
  content: string;
  author_id?: string;
}

export interface CreateDraftRequest {
  parent_revision_id: string | null;
  title: string;
  summary: string;
  content: string;
  expected_page_version: number;
  author_id?: string;
}

export interface PublishRequest {
  revision_id: string;
  expected_page_version: number;
}

export interface RevertRequest {
  target_revision_id: string;
  expected_page_version: number;
}

export interface StatusTransitionRequest {
  status: PageStatus;
  expected_page_version: number;
}

export interface UpdateMetadataRequest {
  expected_page_version: number;
  tags?: string[];
  classifications?: Record<string, string>;
  related_page_ids?: string[];
  media_asset_ids?: string[];
}
