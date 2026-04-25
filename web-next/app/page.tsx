"use client";
import { useEffect, useState } from "react";
import { Header } from "../components/Header";
import { QueryBar } from "../components/QueryBar";
import { RefineSidebar, type Refinements } from "../components/RefineSidebar";
import { RestaurantCard } from "../components/RestaurantCard";
import { RefineInput } from "../components/RefineInput";
import { fetchLocalities, recommend } from "../lib/api";
import type { RecommendResponse } from "../lib/types";

export default function Page() {
  const [localities, setLocalities] = useState<string[]>([]);
  const [location, setLocation] = useState<string>("Indiranagar");
  const [cuisine, setCuisine] = useState<string>("Thai");
  const [budget, setBudget] = useState<number | null>(1000);
  const [minRating, setMinRating] = useState<number>(4.0);
  const [extras, setExtras] = useState<string>("");
  const [refine, setRefine] = useState<Refinements>({
    spicy: true,
    underBudget: true,
    quickTags: ["Authentic"],
  });

  const [resp, setResp] = useState<RecommendResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState<number | null>(null);

  useEffect(() => {
    fetchLocalities()
      .then((list) => {
        setLocalities(list);
        if (!list.includes(location) && list.length > 0) {
          // Indiranagar exists in the dataset, but be defensive.
          if (!list.includes("Indiranagar")) setLocation(list[0]);
        }
      })
      .catch((e) => setError(`Could not load localities: ${e.message}`));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function buildExtras(extra?: string): string | undefined {
    const bits: string[] = [];
    if (refine.spicy) bits.push("spicy");
    if (refine.quickTags.length) bits.push(...refine.quickTags.map((t) => t.toLowerCase()));
    if (extras.trim()) bits.push(extras.trim());
    if (extra) bits.push(extra);
    const joined = bits.join(", ").trim();
    return joined || undefined;
  }

  async function runRecommend(extraText?: string) {
    if (!location) {
      setError("Pick a locality first.");
      return;
    }
    setError(null);
    setLoading(true);
    const t0 = performance.now();
    try {
      const data = await recommend({
        location,
        cuisine: cuisine.trim() || undefined,
        min_rating: minRating,
        budget_max_inr: refine.underBudget ? budget ?? undefined : undefined,
        extras: buildExtras(extraText),
      });
      setResp(data);
      setElapsed((performance.now() - t0) / 1000);
    } catch (e: any) {
      setError(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  const budgetLabel = budget ? `Under ₹${budget}` : "Set budget";

  return (
    <>
      <Header />
      <main className="mx-auto max-w-6xl px-6 py-6 flex flex-col lg:flex-row gap-6">
        <RefineSidebar value={refine} onChange={setRefine} budgetLabel={budgetLabel} />

        <section className="flex-1 flex flex-col gap-5">
          <QueryBar
            cuisine={cuisine}
            setCuisine={setCuisine}
            location={location}
            setLocation={setLocation}
            budget={budget}
            setBudget={setBudget}
            localities={localities}
          />

          <div className="flex items-center gap-3 text-xs text-ink-500">
            <label className="flex items-center gap-1.5">
              Min rating
              <input
                type="number"
                min={0}
                max={5}
                step={0.1}
                value={minRating}
                onChange={(e) => setMinRating(parseFloat(e.target.value) || 0)}
                className="w-14 border border-ink-300/60 rounded px-1.5 py-0.5 text-xs"
              />
            </label>
            <button
              type="button"
              onClick={() => runRecommend()}
              disabled={loading}
              className="ml-auto px-4 py-1.5 rounded-full bg-brand-500 text-white text-xs font-semibold hover:bg-brand-600 disabled:opacity-50"
            >
              {loading ? "Asking the model…" : "Get recommendations"}
            </button>
          </div>

          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 text-red-700 px-4 py-3 text-sm">
              {error}
            </div>
          )}

          {resp && (
            <>
              <div className="text-sm text-ink-700">
                <div className="font-semibold text-ink-900 mb-1">{resp.summary}</div>
                <div className="text-xs text-ink-500">
                  shortlist: {resp.meta.shortlist_size ?? "?"} · model:{" "}
                  {resp.meta.model ?? "?"} · parse: {resp.meta.parse_method ?? "?"} · LLM:{" "}
                  {resp.meta.llm_called ? "yes" : "no"}
                  {elapsed != null && ` · ${elapsed.toFixed(2)}s`}
                  {resp.meta.filter_reason && resp.meta.filter_reason !== "OK" && (
                    <> · filter: {resp.meta.filter_reason}</>
                  )}
                </div>
              </div>

              {resp.items.length > 0 ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {resp.items.map((item) => (
                    <RestaurantCard key={item.id} item={item} />
                  ))}
                </div>
              ) : (
                <div className="rounded-xl border border-ink-300/50 bg-white p-6 text-sm text-ink-500">
                  No restaurants matched. Try widening the area, lowering the rating, or raising the budget.
                </div>
              )}
            </>
          )}

          {!resp && !error && !loading && (
            <div className="rounded-xl border border-dashed border-ink-300/60 bg-white/60 p-8 text-center text-sm text-ink-500">
              Set your preferences above and hit <span className="font-semibold text-brand-600">Get recommendations</span>.
            </div>
          )}

          <div className="mt-2">
            <RefineInput
              onSubmit={(t) => runRecommend(t)}
              disabled={loading}
            />
          </div>
        </section>
      </main>
    </>
  );
}
