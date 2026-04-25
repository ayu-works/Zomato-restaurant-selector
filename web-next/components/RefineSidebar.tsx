"use client";

export type Refinements = {
  spicy: boolean;
  underBudget: boolean;
  quickTags: string[];     // e.g. ["Authentic", "Fast Delivery"]
};

const QUICK_TAGS = ["Authentic", "Vegetarian Options", "Fast Delivery"];

type Props = {
  value: Refinements;
  onChange: (next: Refinements) => void;
  budgetLabel: string;
};

export function RefineSidebar({ value, onChange, budgetLabel }: Props) {
  const toggleTag = (tag: string) => {
    const has = value.quickTags.includes(tag);
    onChange({
      ...value,
      quickTags: has ? value.quickTags.filter((t) => t !== tag) : [...value.quickTags, tag],
    });
  };

  return (
    <aside className="w-full lg:w-56 shrink-0">
      <div className="rounded-2xl border border-ink-300/50 bg-white p-4 shadow-card">
        <h3 className="text-sm font-semibold text-ink-700 mb-3">Refine</h3>
        <label className="flex items-center gap-2 mb-2 cursor-pointer">
          <input
            type="checkbox"
            checked={value.spicy}
            onChange={(e) => onChange({ ...value, spicy: e.target.checked })}
            className="accent-brand-500 h-4 w-4"
          />
          <span className="text-sm text-ink-700">Spicy</span>
        </label>
        <label className="flex items-center gap-2 mb-4 cursor-pointer">
          <input
            type="checkbox"
            checked={value.underBudget}
            onChange={(e) => onChange({ ...value, underBudget: e.target.checked })}
            className="accent-brand-500 h-4 w-4"
          />
          <span className="text-sm text-ink-700">{budgetLabel}</span>
        </label>

        <div className="text-[11px] uppercase tracking-wider text-ink-500 mt-2 mb-2">Quick Tags</div>
        <div className="flex flex-wrap gap-2">
          {QUICK_TAGS.map((tag) => {
            const active = value.quickTags.includes(tag);
            return (
              <button
                key={tag}
                type="button"
                onClick={() => toggleTag(tag)}
                className={
                  "px-2.5 py-1 text-xs rounded-full border transition " +
                  (active
                    ? "bg-brand-500 text-white border-brand-500"
                    : "bg-white text-ink-700 border-ink-300/70 hover:border-brand-400")
                }
              >
                {tag}
              </button>
            );
          })}
        </div>
      </div>
    </aside>
  );
}
