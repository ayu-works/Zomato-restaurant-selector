import type { Refinements } from "../components/RefineSidebar";

export type PersistedPrefs = {
  location: string;
  cuisine: string;
  budget: number | null;
  minRating: number;
  extras: string;
  refine: Refinements;
  v: 1;            // schema version — bump when shape changes
};

const KEY = "zomato-ai:prefs";

export function loadPrefs(): PersistedPrefs | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as PersistedPrefs;
    if (data?.v !== 1) return null;          // unknown schema → ignore
    return data;
  } catch {
    return null;
  }
}

export function savePrefs(p: Omit<PersistedPrefs, "v">): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(KEY, JSON.stringify({ ...p, v: 1 } satisfies PersistedPrefs));
  } catch {
    /* quota / privacy mode — best effort */
  }
}

export function clearPrefs(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}
