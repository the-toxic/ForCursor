const STORAGE_KEY = "uniq_news_session";
export const ACCESS_KEY = "toxic";

export function readStoredSession(): string {
  return window.localStorage.getItem(STORAGE_KEY) || "";
}

export function hasAccess(): boolean {
  return readStoredSession() === ACCESS_KEY;
}

export function saveSession(key: string): void {
  window.localStorage.setItem(STORAGE_KEY, key);
}

export function clearSession(): void {
  window.localStorage.removeItem(STORAGE_KEY);
}
