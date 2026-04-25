import type { RecommendItem } from "../lib/types";

const CUISINE_EMOJI: Record<string, string> = {
  italian: "🍝",
  pizza: "🍕",
  chinese: "🥡",
  thai: "🌶️",
  japanese: "🍣",
  burger: "🍔",
  "fast food": "🍟",
  "north indian": "🍛",
  "south indian": "🥥",
  biryani: "🍚",
  cafe: "☕",
  desserts: "🍰",
  "ice cream": "🍦",
  bakery: "🥐",
  bbq: "🔥",
  beverages: "🥤",
  continental: "🍽️",
  mexican: "🌮",
  finger: "🍢",
  mughlai: "🍢",
};

function pickEmoji(cuisines: string[]): string {
  for (const c of cuisines) {
    const e = CUISINE_EMOJI[c.toLowerCase()];
    if (e) return e;
  }
  return "🍽️";
}

function gradientFor(name: string): string {
  // Deterministic warm gradient seeded by name length parity.
  const seed = (name.charCodeAt(0) + name.length) % 4;
  const list = [
    "from-orange-200 via-rose-200 to-pink-200",
    "from-amber-200 via-rose-200 to-fuchsia-200",
    "from-rose-200 via-red-200 to-orange-200",
    "from-pink-200 via-rose-200 to-amber-200",
  ];
  return list[seed];
}

export function RestaurantCard({ item }: { item: RecommendItem }) {
  const cuisines = item.cuisines ?? [];
  const emoji = pickEmoji(cuisines);
  const grad = gradientFor(item.name || "x");
  const ratingTxt = item.rating != null ? item.rating.toFixed(1) : "—";

  return (
    <article className="rounded-2xl border border-ink-300/40 bg-white shadow-card overflow-hidden flex flex-col">
      {/* Image / placeholder */}
      <div className={`relative h-40 bg-gradient-to-br ${grad} flex items-center justify-center`}>
        <span className="text-5xl drop-shadow-sm" aria-hidden="true">
          {emoji}
        </span>
        {item.rating != null && (
          <div className="absolute top-3 right-3 bg-white/95 rounded-full px-2 py-0.5 text-xs font-semibold text-emerald-700 shadow">
            ★ {ratingTxt}
          </div>
        )}
        <div className="absolute top-3 left-3 bg-brand-500/95 text-white text-[10px] uppercase tracking-wider rounded-full px-2 py-0.5 shadow">
          #{item.rank}
        </div>
      </div>

      <div className="p-4 flex flex-col gap-2">
        <div className="flex items-start justify-between gap-3">
          <h3 className="font-semibold text-ink-900 leading-tight">{item.name}</h3>
          {item.cost_display && (
            <span className="text-xs text-ink-500 whitespace-nowrap">{item.cost_display}</span>
          )}
        </div>
        <div className="text-xs text-ink-500">
          {item.locality ?? ""} {item.estimated_cost ? ` · ${item.estimated_cost}` : ""}
        </div>
        <div className="flex flex-wrap gap-1.5 mt-1">
          {cuisines.slice(0, 4).map((c) => (
            <span key={c} className="bg-cream text-ink-700 border border-brand-100 px-2 py-0.5 rounded-full text-[11px]">
              {c}
            </span>
          ))}
        </div>

        <div className="mt-3 rounded-xl bg-whyBg/80 border border-brand-100 p-3">
          <div className="text-[11px] font-semibold text-brand-600 mb-1 flex items-center gap-1">
            <span aria-hidden="true">💬</span> Why this for you?
          </div>
          <p className="text-[13px] text-ink-700 leading-snug">{item.explanation}</p>
        </div>
      </div>
    </article>
  );
}
