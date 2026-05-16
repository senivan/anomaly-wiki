import { request } from "./client";
import type {
  CreateDraftRequest,
  CreatePageRequest,
  PageState,
  PublishRequest,
  Revision,
  RevisionLineage,
  RevertRequest,
  StatusTransitionRequest,
  UpdateMetadataRequest,
} from "./types";

export const pagesApi = {
  listMine: (params: { status?: string }, token: string) => {
    const qs = new URLSearchParams();
    if (params.status) qs.set("status", params.status);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request<{ pages: PageState[] }>(`/pages/mine${suffix}`, { token });
  },

  getBySlug: (slug: string, token?: string) =>
    request<PageState>(`/pages/slug/${slug}`, { token }),

  getById: (pageId: string, token?: string) =>
    request<PageState>(`/pages/${pageId}`, { token }),

  create: (body: CreatePageRequest, token: string) =>
    request<PageState>("/pages", {
      method: "POST",
      body: JSON.stringify(body),
      token,
    }),

  createDraft: (pageId: string, body: CreateDraftRequest, token: string) =>
    request<PageState>(`/pages/${pageId}/drafts`, {
      method: "POST",
      body: JSON.stringify(body),
      token,
    }),

  updateMetadata: (pageId: string, body: UpdateMetadataRequest, token: string) =>
    request<PageState>(`/pages/${pageId}/metadata`, {
      method: "PUT",
      body: JSON.stringify(body),
      token,
    }),

  publish: (pageId: string, body: PublishRequest, token: string) =>
    request<PageState>(`/pages/${pageId}/publish`, {
      method: "POST",
      body: JSON.stringify(body),
      token,
    }),

  revert: (pageId: string, body: RevertRequest, token: string) =>
    request<PageState>(`/pages/${pageId}/revert`, {
      method: "POST",
      body: JSON.stringify(body),
      token,
    }),

  transitionStatus: (pageId: string, body: StatusTransitionRequest, token: string) =>
    request<PageState>(`/pages/${pageId}/status`, {
      method: "POST",
      body: JSON.stringify(body),
      token,
    }),

  listRevisions: (pageId: string, token?: string) =>
    request<{ page: PageState["page"]; revisions: Revision[] }>(
      `/pages/${pageId}/revisions`,
      { token },
    ),

  getRevision: (pageId: string, revisionId: string, token?: string) =>
    request<RevisionLineage>(`/pages/${pageId}/revisions/${revisionId}`, { token }),
};
