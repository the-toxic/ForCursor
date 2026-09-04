export interface Source {
  id: number;
  username: string;
  title: string | null;
  enabled: boolean;
  last_post_id: number | null;
  last_fetched_at: string | null;
  error: string | null;
  created_at: string;
}

export interface NewsItem {
  id: number;
  source_username: string;
  external_id: string;
  raw_text: string;
  photo_url: string | null;
  source_url: string | null;
  status: "published" | "duplicate" | "skipped" | string;
  similarity: number | null;
  matched_item_id: number | null;
  posted_at: string | null;
  created_at: string;
}

export interface Stats {
  sources: number;
  published: number;
  duplicates: number;
  skipped: number;
  items_total: number;
  mode: string;
  last_fetch_at: string | null;
}

export interface RuntimeSettings {
  app_mode: string;
  target_channel: string;
  similarity_threshold: number;
  poll_interval_seconds: number;
  min_text_length: number;
  bot_configured: boolean;
}

export interface FetchResult {
  fetched: number;
  published: number;
  duplicates: number;
  skipped: number;
  errors: string[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(payload.detail || `Ошибка запроса: ${response.status}`);
  }
  return (await response.json()) as T;
}

export const api = {
  stats: () => request<Stats>("/api/stats"),
  sources: () => request<Source[]>("/api/sources"),
  items: (status?: string) =>
    request<NewsItem[]>(status ? `/api/items?status=${status}` : "/api/items"),
  settings: () => request<RuntimeSettings>("/api/settings"),
  addSource: (username: string) =>
    request<Source>("/api/sources", {
      method: "POST",
      body: JSON.stringify({ username }),
    }),
  toggleSource: (id: number, enabled: boolean) =>
    request<Source>(`/api/sources/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ enabled }),
    }),
  deleteSource: (id: number) =>
    request<{ ok: boolean }>(`/api/sources/${id}`, { method: "DELETE" }),
  saveSettings: (payload: Partial<RuntimeSettings>) =>
    request<RuntimeSettings>("/api/settings", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  fetchNow: () => request<FetchResult>("/api/fetch", { method: "POST" }),
  resetDemo: () => request<FetchResult>("/api/demo/reset", { method: "POST" }),
};
