"""Streamlit Community Cloud entry point.

Self-contained UI that imports `recommend()` directly — there is no FastAPI
process here; Streamlit Cloud renders this script and the Phase 1 catalog
parquet shipped under `data/processed/restaurants.parquet`.

Local dev:
    streamlit run streamlit_app.py

Cloud:
    Set repo + main branch + this file as the app entry point.
    Add GROQ_API_KEY under Streamlit Cloud Secrets (see .streamlit/secrets.toml.example).
"""
from __future__ import annotations

import os
import time

import streamlit as st

from restaurant_rec.config import AppConfig
from restaurant_rec.phase2 import UserPreferences, load_catalog
from restaurant_rec.phase3 import recommend

# ----------------------------------------------------------------------
# Secrets bridge: Streamlit Cloud puts secrets in st.secrets; the rest of
# the codebase (groq_client.py) reads os.environ. Wire them together.
# ----------------------------------------------------------------------
if not os.environ.get("GROQ_API_KEY"):
    try:
        if "GROQ_API_KEY" in st.secrets:
            os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        pass


# ----------------------------------------------------------------------
# Cached singletons.
# ----------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_config() -> AppConfig:
    return AppConfig.load()


@st.cache_resource(show_spinner="Loading catalog…")
def get_catalog(parquet_path: str):
    return load_catalog(parquet_path)


@st.cache_data(show_spinner=False)
def get_localities(parquet_path: str) -> list[str]:
    df = get_catalog(parquet_path)
    return sorted({str(c) for c in df["locality"].dropna().unique() if str(c).strip()})


# ----------------------------------------------------------------------
# Page setup.
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="Zomato AI · Concierge",
    page_icon="🍽️",
    layout="wide",
)

cfg = get_config()
catalog = get_catalog(str(cfg.paths.processed_catalog))
localities = get_localities(str(cfg.paths.processed_catalog))

st.markdown(
    """
    <style>
      .brand { color:#e23744; font-weight:700; font-size:1.4rem; }
      .why { background:#fdecec; border:1px solid #ffd5d5; border-radius:10px; padding:10px 12px; margin-top:8px; }
      .why-title { color:#cb202d; font-weight:600; font-size:0.85rem; margin-bottom:4px; }
      .meta { color:#6b7280; font-size:0.8rem; }
      .chip { display:inline-block; background:#fff5f5; border:1px solid #ffd5d5; color:#374151;
              padding:2px 8px; margin:2px 4px 2px 0; border-radius:9999px; font-size:0.72rem; }
      .rank { background:#e23744; color:white; padding:2px 8px; border-radius:9999px;
              font-size:0.72rem; font-weight:700; }
      .rating { color:#047857; font-weight:600; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="brand">Zomato AI · Concierge</div>', unsafe_allow_html=True)
st.caption("Bangalore · Zomato data · Groq-powered ranking")

# ----------------------------------------------------------------------
# Form.
# ----------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Refine")
    spicy = st.checkbox("Spicy", value=False)
    quick_tags = st.multiselect(
        "Quick tags",
        options=["Authentic", "Vegetarian Options", "Fast Delivery"],
        default=[],
    )
    st.markdown("---")
    st.caption(f"catalog: {len(catalog):,} rows")
    st.caption(f"model: `{cfg.llm.model}`")

col_left, col_right = st.columns([2, 1])
with col_left:
    location = st.selectbox(
        "Locality *",
        options=localities,
        index=(localities.index("Indiranagar") if "Indiranagar" in localities else 0),
    )
    cuisine = st.text_input("Cuisine", value="Italian", placeholder="e.g. North Indian, Italian")

with col_right:
    min_rating = st.number_input("Min rating", min_value=0.0, max_value=5.0, value=4.0, step=0.1)
    budget = st.number_input(
        "Max budget (₹ for two)", min_value=0, max_value=10000, value=1500, step=50
    )

extras_text = st.text_input(
    "Extras (optional)", value="", placeholder="family-friendly, quick service…"
)
go = st.button("Get recommendations", type="primary", use_container_width=False)

# ----------------------------------------------------------------------
# Results.
# ----------------------------------------------------------------------
if go:
    if not os.environ.get("GROQ_API_KEY"):
        st.error(
            "GROQ_API_KEY is not configured. Add it to Streamlit Cloud → Settings → Secrets."
        )
        st.stop()

    extra_bits: list[str] = []
    if spicy:
        extra_bits.append("spicy")
    if quick_tags:
        extra_bits.extend(t.lower() for t in quick_tags)
    if extras_text.strip():
        extra_bits.append(extras_text.strip())
    extras = ", ".join(extra_bits) or None

    prefs = UserPreferences(
        location=location,
        cuisine=cuisine.strip() or None,
        min_rating=float(min_rating),
        budget_max_inr=float(budget) if budget else None,
        extras=extras,
    )

    t0 = time.perf_counter()
    with st.spinner("Asking the model…"):
        result = recommend(prefs, cfg, catalog=catalog)
    elapsed = time.perf_counter() - t0

    st.markdown(f"#### {result.summary}")
    meta = result.meta
    st.markdown(
        f"<span class='meta'>shortlist: {meta.get('shortlist_size','?')} · "
        f"model: <code>{meta.get('model','?')}</code> · "
        f"parse: {meta.get('parse_method','?')} · "
        f"LLM: {'yes' if meta.get('llm_called') else 'no'} · "
        f"{elapsed:.2f}s"
        + (f" · filter: {meta.get('filter_reason')}" if meta.get("filter_reason") not in (None, "OK") else "")
        + "</span>",
        unsafe_allow_html=True,
    )

    if not result.items:
        st.info(
            "No restaurants matched. Try widening the area, lowering the rating, or raising the budget."
        )
    else:
        # Two columns of cards.
        cols = st.columns(2)
        for i, item in enumerate(result.items):
            with cols[i % 2]:
                with st.container(border=True):
                    head_l, head_r = st.columns([4, 1])
                    head_l.markdown(
                        f"<span class='rank'>#{item.rank}</span> "
                        f"&nbsp;<strong>{item.name}</strong>",
                        unsafe_allow_html=True,
                    )
                    if item.rating is not None:
                        head_r.markdown(
                            f"<span class='rating'>★ {item.rating}</span>",
                            unsafe_allow_html=True,
                        )
                    line = []
                    if item.locality:
                        line.append(item.locality)
                    if item.cost_for_two is not None:
                        line.append(f"₹{int(item.cost_for_two)} for two")
                    if item.budget_tier:
                        line.append(item.budget_tier)
                    st.markdown(
                        f"<span class='meta'>{' · '.join(line)}</span>",
                        unsafe_allow_html=True,
                    )
                    if item.cuisines:
                        st.markdown(
                            "".join(f"<span class='chip'>{c}</span>" for c in item.cuisines[:5]),
                            unsafe_allow_html=True,
                        )
                    st.markdown(
                        f"<div class='why'>"
                        f"<div class='why-title'>💬 Why this for you?</div>"
                        f"{item.explanation}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
else:
    st.info(
        "Pick a locality on the left, tweak cuisine / rating / budget, then click "
        "**Get recommendations**."
    )
