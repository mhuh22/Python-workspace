# Hotel_app.py (with collapsible AI chat at top)
# Filters (top-left 1/3), Map (top-right 2/3), Table (bottom full width)
# Run: streamlit run Hotel_app.py

from pathlib import Path
import re
import json
import numpy as np
import pandas as pd
import streamlit as st
import pydeck as pdk

# Optional deps for AI modes
try:
    from openai import OpenAI  # pip install openai
except Exception:
    OpenAI = None

import requests
import textwrap

st.set_page_config(page_title="Hotel Browser", layout="wide")

# ---------- Safe CSS (prevent clipping, keep labels compact) ----------
st.markdown("""
<style>
.stApp, .main, .block-container { overflow: visible !important; }
.block-container { padding-top: 1.25rem; }
.compact-label { font-size: 0.95rem; font-weight: 600; margin: 0.15rem 0 0.25rem 0; line-height: 1.1; }
</style>
""", unsafe_allow_html=True)

# ---------- Load Data First ----------
DEFAULT_FILE = Path("snapshot_with_addresses.csv")

@st.cache_data
def _to_float_price(x):
    if x is None or str(x).strip() == "":
        return np.nan
    s = str(x).replace(",", "").replace("$", "").replace("€", "").replace("£", "")
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    return float(m.group(1)) if m else np.nan

@st.cache_data
def _parse_distance_miles(txt):
    if not isinstance(txt, str) or not txt.strip():
        return np.nan
    m = re.search(r"([\d\.]+)\s*(mile|miles|km|kilometer|kilometers)\b", txt.lower())
    if not m:
        m2 = re.search(r"([\d\.]+)", txt)
        return float(m2.group(1)) if m2 else np.nan
    val = float(m.group(1))
    if "km" in m.group(2):
        val *= 0.621371
    return val

def _pick_addr(row):
    for c in ["scraped_address", "address"]:
        if c in row and str(row[c]).strip():
            return str(row[c]).strip()
    return ""

def _looks_like_postal(t):
    return bool(re.fullmatch(r"[0-9\-]{3,7}", t.strip().replace(" ", "")))

@st.cache_data
def load_data(path: Path):
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df = df.drop(columns=[c for c in ["detail_url", "page_status"] if c in df.columns], errors="ignore")
    return df

@st.cache_data
def enrich_data(df):
    if df.empty:
        return df
    df = df.copy()
    countries, regions = [], []
    for _, r in df.iterrows():
        addr = _pick_addr(r)
        tokens = [t.strip() for t in addr.split(",") if t.strip()]
        country = tokens[-1] if tokens else ""
        region = ""
        for t in reversed(tokens[:-1]):
            if _looks_like_postal(t):
                continue
            if any(k in t.lower() for k in ["community", "province", "region", "autonomous", "madrid",
                                            "catalonia", "andalusia", "valenc", "galicia", "castile", "basque"]):
                region = t; break
        if not region and len(tokens) >= 2:
            cand = tokens[-2]
            if not _looks_like_postal(cand):
                region = cand
        countries.append(country); regions.append(region)
    df["__country"], df["__region"] = countries, regions
    df["price_f"] = df.get("display_price", df.get("raw_price_text", "")).apply(_to_float_price)
    df["rating_f"] = pd.to_numeric(df.get("score_numeric", np.nan), errors="coerce")
    df["distance_mi"] = df.get("distance_blurb", "").apply(_parse_distance_miles)
    for c in ["lat", "lon"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

if not DEFAULT_FILE.exists():
    st.error("File `snapshot_with_addresses.csv` not found.")
    st.stop()

df = enrich_data(load_data(DEFAULT_FILE))

st.title("🏨 Hotel Browser")

# ---------- Ask AI (collapsible at top) ----------
with st.expander("🧠 Ask AI about this dataset", expanded=False):
    backend = st.radio("Model backend", ["OpenAI API", "Local (Ollama)"], horizontal=True, key="ai_backend_top")

    @st.cache_data(show_spinner=False)
    def build_ai_context_top(data: pd.DataFrame, sample_rows=200):
        cols = [{"name": c, "dtype": str(data[c].dtype)} for c in data.columns]
        sample = data.sample(min(len(data), sample_rows), random_state=42)
        desc = data.describe(include="all").to_dict()
        return {"columns": cols, "n_rows": int(len(data)), "sample": sample.to_dict(orient="records"), "describe": desc}

    ctx_top = build_ai_context_top(df)

    if "ai_history_top" not in st.session_state:
        st.session_state.ai_history_top = []

    if st.session_state.ai_history_top:
        for role, content in st.session_state.ai_history_top[-8:]:
            with st.chat_message(role):
                st.markdown(content)

    prompt_top = st.chat_input("Ask a question about the dataset (uses full data, not just filters)…")

    if prompt_top:
        st.session_state.ai_history_top.append(("user", prompt_top))
        with st.chat_message("user"):
            st.markdown(prompt_top)

        answer_top = ""
        if backend == "OpenAI API":
            if OpenAI is None:
                answer_top = "`openai` package not installed. Run: `pip install openai`"
            else:
                try:
                    client = OpenAI()
                    system = ("You are a careful data analyst. Use ONLY the provided context. Prefer concise bullet points.")
                    payload = {"question": prompt_top, "data_context": ctx_top}
                    resp = client.chat.completions.create(model="gpt-4o-mini", temperature=0.2, messages=[{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload)}])
                    answer_top = resp.choices[0].message.content
                except Exception as e:
                    answer_top = f"OpenAI error: {e}"
        else:
            try:
                prompt_payload = textwrap.dedent(f"""
                You are a careful data analyst. Use ONLY the provided context.
                Return concise bullet points and simple summaries.

                Question: {prompt_top}
                Context (JSON): {json.dumps(ctx_top)}
                """)
                r = requests.post("http://localhost:11434/api/generate", json={"model": "llama3", "prompt": prompt_payload, "stream": False, "temperature": 0.2}, timeout=120)
                r.raise_for_status()
                answer_top = r.json().get("response", "").strip()
            except Exception as e:
                answer_top = f"Local (Ollama) error: {e}"

        st.session_state.ai_history_top.append(("assistant", answer_top))
        with st.chat_message("assistant"):
            st.markdown(answer_top)

# ---------- Filters, Map, and Table ----------
def inline_select(label, options, index=0, key=None):
    c1, c2 = st.columns([0.35, 0.65], gap="small")
    with c1:
        st.markdown(f"<div class='compact-label'>{label}</div>", unsafe_allow_html=True)
    with c2:
        return st.selectbox("", options=options, index=index, key=key, label_visibility="collapsed")

def inline_slider(label, min_val, max_val, value, step=None, key=None):
    min_v, max_v = float(min_val), float(max_val)
    if isinstance(value, (tuple, list)):
        value = (float(value[0]), float(value[1]))
    c1, c2 = st.columns([0.35, 0.65], gap="small")
    with c1:
        st.markdown(f"<div class='compact-label'>{label}</div>", unsafe_allow_html=True)
    with c2:
        return st.slider("", min_value=min_v, max_value=max_v, value=value, step=step, key=key, label_visibility="collapsed")

filters_col, map_col = st.columns([1, 2], gap="large")
with filters_col:
    st.subheader("Filters")
    country_opts = ["All"] + sorted([c for c in df["__country"].dropna().unique() if c])
    idx = country_opts.index("Spain") if "Spain" in country_opts else 0
    country = inline_select("Country", country_opts, idx, "country")
    df_reg = df if country == "All" else df[df["__country"] == country]
    region_opts = ["All"] + sorted([r for r in df_reg["__region"].dropna().unique() if r])
    region = inline_select("Region", region_opts, 0, "region")
    price = inline_slider("Price", np.floor(df["price_f"].min()), np.ceil(df["price_f"].max()), (np.floor(df["price_f"].min()), np.ceil(df["price_f"].max())), key="price") if df["price_f"].notna().any() else None
    rating = inline_slider("Rating", 0, 10, (0, 10), key="rating") if df["rating_f"].notna().any() else None
    if df["distance_mi"].notna().any():
        dmin, dmax = float(np.nanmin(df["distance_mi"])), float(np.nanmax(df["distance_mi"]))
        distance = inline_slider("Distance (mi)", max(0.0, np.floor(dmin)), np.ceil(dmax), (max(0.0, np.floor(dmin)), np.ceil(dmax)), key="distance")
    else:
        distance = None

with map_col:
    st.subheader("🗺️ Map")
    mask = pd.Series(True, index=df.index)
    if country != "All": mask &= df["__country"] == country
    if region != "All": mask &= df["__region"] == region
    if price is not None: mask &= df["price_f"].between(price[0], price[1])
    if rating is not None: mask &= df["rating_f"].between(rating[0], rating[1])
    if distance is not None: mask &= df["distance_mi"].between(distance[0], distance[1])
    filt = df[mask]
    map_df = filt.dropna(subset=["lat", "lon"]) if {"lat", "lon"}.issubset(filt.columns) else pd.DataFrame(columns=["lat", "lon", "name"])
    center_lat, center_lon = (map_df["lat"].mean(), map_df["lon"].mean()) if not map_df.empty else (40.4168, -3.7038)
    if map_df.empty:
        map_df = pd.DataFrame({"lat": [center_lat], "lon": [center_lon], "name": ["Madrid, Spain"]})
    layer = pdk.Layer("ScatterplotLayer", data=map_df, get_position=["lon", "lat"], get_color=[255, 0, 0], get_radius=100, pickable=True)
    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=11), map_style="mapbox://styles/mapbox/light-v11", tooltip={"text": "{name}"}), use_container_width=True)

st.markdown("---")
st.subheader("📋 Filtered Hotels")
st.caption(f"{len(filt):,} rows")
cols_hide = ["__country", "__region", "price_f", "rating_f", "distance_mi"]
st.dataframe(filt.drop(columns=cols_hide, errors="ignore"), use_container_width=True, height=520)

with st.expander("Notes"):
    st.markdown("""- Filters left (1/3), map right (2/3), table full width below.
- Country/Region parsed from address; price/rating/distance parsed from columns.
- Map defaults to Madrid if no coordinates.
- Collapsible AI chat added at top for quick insights.""")