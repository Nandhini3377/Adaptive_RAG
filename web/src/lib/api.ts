// A small typed client for the FastAPI backend. The login token lives in localStorage.

import type { AnalysisOut, DocumentOut, Intent, LabOut, LabQueryOut, Mode, QueryOut } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "adaptive-rag-token";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // storage blocked (private mode): the user will need to log in again
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, `Cannot reach the API at ${API_URL}. Is the backend running?`);
  }
  if (response.status === 401 && path !== "/auth/login") {
    setToken(null);
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      // Outside React (no router here): a full reload also clears any stale page state
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.href = "/login";
    }
  }
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response));
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) return body.detail.map((d: { msg: string }) => d.msg).join("; ");
  } catch {
    // not JSON
  }
  return `Request failed (${response.status})`;
}

export const api = {
  register: (email: string, password: string) =>
    request<{ id: string; email: string }>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => request<{ id: string; email: string }>("/auth/me"),

  listDocuments: () => request<DocumentOut[]>("/documents"),
  getDocument: (id: string) => request<DocumentOut>(`/documents/${id}`),
  upload: (file: File, intents: Intent[] = []) => {
    const form = new FormData();
    form.append("file", file);
    intents.forEach((intent) => form.append("intents", intent));
    return request<{ document_id: string; duplicate: boolean }>("/documents", {
      method: "POST",
      body: form,
    });
  },
  getAnalysis: (id: string) => request<AnalysisOut>(`/documents/${id}/analysis`),
  setIntent: (id: string, intents: Intent[], skip = false) =>
    request<DocumentOut>(`/documents/${id}/intent`, {
      method: "POST",
      body: JSON.stringify({ intents, skip }),
    }),
  buildIndex: (id: string, index: "bm25" | "graph" | "bm25+graph") =>
    request<DocumentOut>(`/documents/${id}/build-index`, {
      method: "POST",
      body: JSON.stringify({ index }),
    }),
  deleteDocument: (id: string) => request<void>(`/documents/${id}`, { method: "DELETE" }),

  query: (question: string, documentIds?: string[], mode?: Mode) =>
    request<QueryOut>("/query", {
      method: "POST",
      body: JSON.stringify({ question, document_ids: documentIds, mode }),
    }),

  getLab: () => request<LabOut | null>("/lab"),
  setLabSnippet: (text: string) =>
    request<LabOut>("/lab/snippet", { method: "POST", body: JSON.stringify({ text }) }),
  deleteLab: () => request<void>("/lab", { method: "DELETE" }),
  labQuery: (question: string) =>
    request<LabQueryOut>("/lab/query", { method: "POST", body: JSON.stringify({ question }) }),

  health: () => request<{ status: string; llm: string; neo4j: string }>("/health"),
};
