import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import path from "node:path";
import { expect, type APIRequestContext, type Page } from "@playwright/test";

export const gatewayURL = process.env.NEXT_PUBLIC_GATEWAY_URL ?? "http://127.0.0.1:8000";
export const password = "testpassword123";

export function uniqueId(prefix: string): string {
  return `${prefix}-${Date.now()}-${randomUUID().slice(0, 8)}`.toLowerCase();
}

export async function registerUser(request: APIRequestContext, role = "Researcher") {
  const email = `${uniqueId("ui")}@example.com`;
  const response = await request.post(`${gatewayURL}/auth/register`, {
    data: { email, password, role },
  });
  expect(response.status(), await response.text()).toBe(201);
  return { email, password, user: await response.json() };
}

export async function loginApi(request: APIRequestContext, email: string) {
  const response = await request.post(`${gatewayURL}/auth/login`, {
    form: { username: email, password },
  });
  expect(response.status(), await response.text()).toBe(200);
  const body = await response.json();
  return body.access_token as string;
}

export async function authenticate(page: Page, token: string) {
  await page.addInitScript((value) => {
    window.localStorage.setItem("anomaly_wiki_token", value);
  }, token);
}

export function promoteUser(email: string, role: "Editor" | "Admin") {
  const dbRole = role.toUpperCase();
  execFileSync(
    "docker",
    [
      "compose",
      "exec",
      "-T",
      "db",
      "psql",
      "-U",
      "admin",
      "-d",
      "auth_db",
      "-c",
      `UPDATE "user" SET role = '${dbRole}' WHERE email = '${email}';`,
    ],
    {
      stdio: "pipe",
      cwd: path.resolve(process.cwd(), ".."),
    },
  );
}

export async function createPage(
  request: APIRequestContext,
  token: string,
  overrides: Partial<{
    slug: string;
    title: string;
    summary: string;
    content: string;
    type: string;
    visibility: string;
  }> = {},
) {
  const slug = overrides.slug ?? uniqueId("e2e-page");
  const response = await request.post(`${gatewayURL}/pages`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      slug,
      type: overrides.type ?? "Anomaly",
      visibility: overrides.visibility ?? "Public",
      title: overrides.title ?? `E2E ${slug}`,
      summary: overrides.summary ?? "E2E summary from Playwright.",
      content: overrides.content ?? "## Field Notes\n\nE2E body from Playwright.",
    },
  });
  expect(response.status(), await response.text()).toBe(201);
  return { slug, state: await response.json() };
}

export async function transitionStatus(
  request: APIRequestContext,
  token: string,
  pageId: string,
  version: number,
  status: "Review" | "Archived" | "Redacted",
) {
  const response = await request.post(`${gatewayURL}/pages/${pageId}/status`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { expected_page_version: version, status },
  });
  expect(response.status(), await response.text()).toBe(200);
  return response.json();
}

interface PageState {
  page: {
    id: string;
    version: number;
    current_draft_revision_id: string | null;
  };
}

export async function publishPage(request: APIRequestContext, token: string, state: PageState) {
  const response = await request.post(`${gatewayURL}/pages/${state.page.id}/publish`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      expected_page_version: state.page.version,
      revision_id: state.page.current_draft_revision_id,
    },
  });
  expect(response.status(), await response.text()).toBe(200);
  return response.json();
}

export async function waitForSearchHit(request: APIRequestContext, token: string, q: string, slug: string) {
  await expect.poll(async () => {
    const response = await request.get(`${gatewayURL}/search`, {
      headers: { Authorization: `Bearer ${token}` },
      params: { q },
    });
    if (!response.ok()) return false;
    const body = await response.json();
    return body.hits?.some((hit: { slug: string }) => hit.slug === slug) ?? false;
  }, { timeout: 60_000 }).toBe(true);
}
