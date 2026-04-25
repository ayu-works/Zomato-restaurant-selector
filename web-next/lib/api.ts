import type { Preferences, RecommendResponse } from "./types";

export async function fetchLocalities(): Promise<string[]> {
  const r = await fetch("/api/v1/localities", { cache: "no-store" });
  if (!r.ok) throw new Error(`localities ${r.status}`);
  const data = (await r.json()) as { localities: string[] };
  return data.localities ?? [];
}

export async function recommend(prefs: Preferences): Promise<RecommendResponse> {
  const r = await fetch("/api/v1/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(prefs),
  });
  if (r.status === 422) {
    const body = await r.json();
    const msg = (body.detail ?? [])
      .map((e: any) => `${(e.loc ?? []).slice(1).join(".")}: ${e.msg}`)
      .join("; ");
    throw new Error(`Validation: ${msg || "invalid input"}`);
  }
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
  return (await r.json()) as RecommendResponse;
}
