"use client";
import { useState } from "react";

type Props = {
  cuisine: string;
  setCuisine: (s: string) => void;
  location: string;
  setLocation: (s: string) => void;
  budget: number | null;
  setBudget: (n: number | null) => void;
  localities: string[];
};

export function QueryBar({ cuisine, setCuisine, location, setLocation, budget, setBudget, localities }: Props) {
  const [editing, setEditing] = useState(false);
  const summary = formatSummary(cuisine, location, budget);

  return (
    <div className="rounded-full border border-brand-100 bg-white shadow-card px-5 py-3 flex items-center gap-3">
      <span className="text-brand-500">📍</span>
      {!editing ? (
        <>
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="flex-1 text-left text-ink-900 truncate hover:text-brand-600"
            title="Edit query"
          >
            {summary}
          </button>
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="text-ink-500 hover:text-brand-500"
            aria-label="Edit"
          >
            <PencilIcon />
          </button>
        </>
      ) : (
        <div className="flex flex-1 flex-wrap items-center gap-2">
          <input
            value={cuisine}
            onChange={(e) => setCuisine(e.target.value)}
            placeholder="Cuisine (e.g. Thai)"
            className="w-40 text-sm bg-transparent outline-none border-b border-ink-300/60 focus:border-brand-500 py-1"
          />
          <span className="text-ink-500 text-sm">in</span>
          <select
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            className="text-sm bg-transparent outline-none border-b border-ink-300/60 focus:border-brand-500 py-1"
          >
            <option value="">Select locality…</option>
            {localities.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
          <span className="text-ink-500 text-sm">under</span>
          <span className="text-sm">₹</span>
          <input
            type="number"
            min={0}
            step={50}
            value={budget ?? ""}
            onChange={(e) => setBudget(e.target.value === "" ? null : Number(e.target.value))}
            placeholder="1000"
            className="w-20 text-sm bg-transparent outline-none border-b border-ink-300/60 focus:border-brand-500 py-1"
          />
          <button
            type="button"
            onClick={() => setEditing(false)}
            className="ml-auto text-xs px-3 py-1 rounded-full bg-brand-500 text-white hover:bg-brand-600"
          >
            Done
          </button>
        </div>
      )}
    </div>
  );
}

function formatSummary(cuisine: string, location: string, budget: number | null) {
  const parts: string[] = [];
  if (cuisine) parts.push(cuisine);
  parts.push(location ? `in ${location}` : "in (pick a locality)");
  if (budget) parts.push(`under ₹${budget}`);
  return parts.join(" ");
}

function PencilIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.121 2.121 0 113 3L7 19l-4 1 1-4 12.5-12.5z" />
    </svg>
  );
}
