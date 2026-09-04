import { clearSession, readStoredSession } from "../auth";

export interface Source {
  id: number;
  username: string;
  title: string | null;
  enabled: boolean;
  source_kind: "public" | "private" | string;
  invite_link: string | null;
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

export interface TelegramUserStatus {
  configured: boolean;
  authorized: boolean;
  code_sent: boolean;
  user_id: number | null;
  first_name: string | null;
  username: string | null;
  phone: string | null;
  error: string | null;
}

function errorMessage(payload: { detail?: unknown }, status: number): string {
  const detail = payload.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail) && detail[0] && typeof detail[0] === "object" && "msg" in detail[0]) {
    return String((detail[0] as { msg: string }).msg);
  }
  return `Ошибка запроса: ${status}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      "X-Auth-Key": readStoredSession(),
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (response.status === 401) {
    clearSession();
    window.dispatchEvent(new Event("uniq-news-unauthorized"));
    throw new Error("Нужен ключ доступа");
  }
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as { detail?: unknown };
    throw new Error(errorMessage(payload, response.status));
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
  telegramUser: () => request<TelegramUserStatus>("/api/telegram-user"),
  saveTelegramCredentials: (apiId: number, apiHash: string) =>
    request<TelegramUserStatus>("/api/telegram-user/credentials", {
      method: "POST",
      body: JSON.stringify({ api_id: apiId, api_hash: apiHash }),
    }),
  sendTelegramCode: (phone: string, apiId?: number, apiHash?: string) =>
    request<{ ok: boolean; phone: string }>("/api/telegram-user/send-code", {
      method: "POST",
      body: JSON.stringify({
        phone,
        ...(apiId && apiHash ? { api_id: apiId, api_hash: apiHash } : {}),
      }),
    }),
  signInTelegram: (phone: string, code: string, password?: string) =>
    request<TelegramUserStatus>("/api/telegram-user/sign-in", {
      method: "POST",
      body: JSON.stringify({
        phone,
        code,
        ...(password ? { password } : {}),
      }),
    }),
  logoutTelegram: () => request<TelegramUserStatus>("/api/telegram-user/logout", { method: "POST" }),
};
