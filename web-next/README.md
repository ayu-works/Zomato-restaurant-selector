# Zomato AI · Next.js frontend (`web-next/`)

Enhanced UI in the spirit of `design/` mockups — Next.js 14 App Router + Tailwind. Calls the same FastAPI backend (Phase 4) as the legacy `web/` static UI.

## Run

```bash
# 1) start the backend (in repo root)
uvicorn restaurant_rec.phase4.app:app --reload   # listens on :8000

# 2) install + start the Next.js app (in web-next/)
cd web-next
npm install
npm run dev                                      # listens on :3000
# open http://127.0.0.1:3000/
```

`next.config.mjs` rewrites `/api/*` → `http://127.0.0.1:8000/api/*`, so the browser
sees one origin and there are no CORS preflights. Override the upstream with
`BACKEND_URL=http://host:port npm run dev`.

## Deploy to Vercel

1. Vercel → New Project → import this repo.
2. **Root Directory**: `web-next` (so Vercel runs `npm run build` in this folder).
3. Framework preset: Next.js (auto-detected).
4. **Environment Variables**: add `BACKEND_URL` = your deployed FastAPI URL
   (e.g. `https://zomato-recommender-api.onrender.com`, no trailing slash).
   See `.env.example`.
5. Deploy. The browser calls same-origin `/api/*`; Next.js rewrites those
   to `BACKEND_URL` server-side, so no CORS config is needed.

## Structure

```
app/
  layout.tsx          # root layout, font, globals
  page.tsx            # main concierge page (form + results)
  globals.css         # Tailwind imports + creamy backdrop
components/
  Header.tsx          # brand + nav, AI Concierge highlighted
  RefineSidebar.tsx   # left "Refine" panel (Spicy, Under ₹___, Quick Tags)
  QueryBar.tsx        # natural-language query bar with edit affordance
  RestaurantCard.tsx  # rank badge, rating, cuisine chips, "Why this for you?"
  RefineInput.tsx     # bottom chat-style refine-further input
lib/
  api.ts              # fetchLocalities, recommend
  types.ts            # response/preference types
  persistence.ts      # localStorage hydrate/save (versioned schema, key `zomato-ai:prefs`)
```
