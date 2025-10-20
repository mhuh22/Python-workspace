# Hotel_app.py
# Filters (top-left 1/3), Map (top-right 2/3), Table (bottom full width)
# Run: streamlit run Hotel_app.py

from pathlib import Path
import re
import numpy as np
import pandas as pd
import streamlit as st
import pydeck as pdk

st.set_page_config(page_title="Hotel Browser", layout="wide")

# ---------- Safe CSS (prevent clipping, keep labels compact) ----------
st.markdown("""
<style>
/* Prevent any clipping/cropping of headers and widgets */
.stApp, .main, .block-container { overflow: visible !important; }

/* Give the page title a touch more breathing room */
.block-container { padding-top: 1.25rem; }

/* Compact inline labels */
.compact-label { 
  font-size: 0.95rem; 
  font-weight: 600; 
  margin: 0.15rem 0 0.25rem 0; 
  line-height: 1.1; 
}

/* Keep default component paddings (avoid overly-aggressive shrinking) */
</style>
""", unsafe_allow_html=True)

st.title("🏨 Hotel Browser")
# st.caption("Compact filters on the left, map on the right, and table below. Excludes `detail_url` and `page_status`.")

DEFAULT_FILE = Path("snapshot_with_addresses.csv")

# ---------- Helpers ----------
def _to_float_price(x):
    if not x or str(x).strip() == "": return np.nan
    s = str(x).replace(",", "").replace("$", "").replace("€", "").replace("£", "")
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    return float(m.group(1)) if m else np.nan

def _parse_distance_miles(txt):
    if not isinstance(txt, str) or not txt.strip(): return np.nan
    m = re.search(r"([\d\.]+)\s*(mile|miles|km|kilometer|kilometers)\b", txt.lower())
    if not m:
        m2 = re.search(r"([\d\.]+)", txt)
        return float(m2.group(1)) if m2 else np.nan
    val = float(m.group(1))
    if "km" in m.group(2): val *= 0.621371
    return val

def _pick_addr(row):
    for c in ["scraped_address", "address"]:
        if c in row and str(row[c]).strip(): return str(row[c]).strip()
    return ""

def _looks_like_postal(t): return bool(re.fullmatch(r"[0-9\-]{3,7}", t.strip().replace(" ", "")))

@st.cache_data
def load_data(path: Path):
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df = df.drop(columns=[c for c in ["detail_url", "page_status"] if c in df.columns], errors="ignore")
    return df

@st.cache_data
def enrich_data(df):
    if df.empty: return df
    df = df.copy()
    countries, regions = [], []
    for _, r in df.iterrows():
        addr = _pick_addr(r)
        tokens = [t.strip() for t in addr.split(",") if t.strip()]
        country = tokens[-1] if tokens else ""
        region = ""
        for t in reversed(tokens[:-1]):
            if _looks_like_postal(t): continue
            if any(k in t.lower() for k in ["community", "province", "region", "autonomous", "madrid",
                                            "catalonia", "andalusia", "valenc", "galicia", "castile", "basque"]):
                region = t; break
        if not region and len(tokens) >= 2:
            cand = tokens[-2]
            if not _looks_like_postal(cand): region = cand
        countries.append(country); regions.append(region)
    df["__country"], df["__region"] = countries, regions
    df["price_f"] = df.get("display_price", df.get("raw_price_text", "")).apply(_to_float_price)
    df["rating_f"] = pd.to_numeric(df.get("score_numeric", np.nan), errors="coerce")
    df["distance_mi"] = df.get("distance_blurb", "").apply(_parse_distance_miles)
    for c in ["lat", "lon"]:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

# ---------- Load ----------
if not DEFAULT_FILE.exists():
    st.error("File `snapshot_with_addresses.csv` not found.")
    st.stop()
df = enrich_data(load_data(DEFAULT_FILE))

# ---------- Inline widget helpers (wider control area to avoid cutoff) ----------
def inline_select(label, options, index=0, key=None):
    # Wider right column for the actual widget to avoid clipping
    c1, c2 = st.columns([0.35, 0.65], gap="small")
    with c1:
        st.markdown(f"<div class='compact-label'>{label}</div>", unsafe_allow_html=True)
    with c2:
        return st.selectbox("", options=options, index=index, key=key, label_visibility="collapsed")

def inline_slider(label, min_val, max_val, value, step=None, key=None):
    # Use Python floats (not numpy types) to satisfy Streamlit and avoid slider glitches
    min_v = float(min_val); max_v = float(max_val)
    if isinstance(value, tuple) or isinstance(value, list):
        value = (float(value[0]), float(value[1]))
    c1, c2 = st.columns([0.35, 0.65], gap="small")
    with c1:
        st.markdown(f"<div class='compact-label'>{label}</div>", unsafe_allow_html=True)
    with c2:
        return st.slider("", min_value=min_v, max_value=max_v, value=value, step=step, key=key, label_visibility="collapsed")

# ---------- Top row: Filters (1/3) | Map (2/3) ----------
filters_col, map_col = st.columns([1, 2], gap="large")

with filters_col:
    st.subheader("Filters")

    country_opts = ["All"] + sorted([c for c in df["__country"].dropna().unique() if c])
    idx = country_opts.index("Spain") if "Spain" in country_opts else 0
    country = inline_select("Country", country_opts, idx, "country")

    if country != "All": df_reg = df[df["__country"] == country]
    else: df_reg = df
    region_opts = ["All"] + sorted([r for r in df_reg["__region"].dropna().unique() if r])
    region = inline_select("Region", region_opts, 0, "region")

    # Price
    if df["price_f"].notna().any():
        pmin, pmax = float(np.nanmin(df["price_f"])), float(np.nanmax(df["price_f"]))
        price = inline_slider("Price", np.floor(pmin), np.ceil(pmax),
                              (np.floor(pmin), np.ceil(pmax)), key="price")
    else:
        price = None

    # Rating 0–10
    if df["rating_f"].notna().any():
        rmin, rmax = float(np.nanmin(df["rating_f"])), float(np.nanmax(df["rating_f"]))
        r_min_c = max(0.0, np.floor(rmin)); r_max_c = min(10.0, np.ceil(rmax))
        rating = inline_slider("Rating", r_min_c, r_max_c, (r_min_c, r_max_c), key="rating")
    else:
        rating = None

    # Distance (mi)
    if df["distance_mi"].notna().any():
        dmin, dmax = float(np.nanmin(df["distance_mi"])), float(np.nanmax(df["distance_mi"]))
        if np.isfinite(dmin) and np.isfinite(dmax) and dmin != dmax:
            distance = inline_slider("Distance (mi)", max(0.0, np.floor(dmin)), np.ceil(dmax),
                                     (max(0.0, np.floor(dmin)), np.ceil(dmax)), key="distance")
        else:
            distance = None
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

    if "lat" in filt.columns and "lon" in filt.columns:
        map_df = filt.dropna(subset=["lat", "lon"])
    else:
        map_df = pd.DataFrame(columns=["lat", "lon", "name"])

    default_lat, default_lon = 40.4168, -3.7038
    if not map_df.empty:
        center_lat, center_lon = float(map_df["lat"].mean()), float(map_df["lon"].mean())
    else:
        center_lat, center_lon = default_lat, default_lon
        map_df = pd.DataFrame({"lat": [default_lat], "lon": [default_lon], "name": ["Madrid, Spain"]})

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_df,
        get_position=["lon", "lat"],
        get_color=[255, 0, 0],
        get_radius=100,
        pickable=True,
    )
    view = pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=11)
    st.pydeck_chart(
        pdk.Deck(layers=[layer], initial_view_state=view,
                 map_style="mapbox://styles/mapbox/light-v11",
                 tooltip={"text": "{name}"}),
        use_container_width=True,
    )

# ---------- Table (bottom full width) ----------
st.markdown("---")
st.subheader("📋 Filtered Hotels")
st.caption(f"{len(filt):,} rows")
hide_cols = ["__country", "__region", "price_f", "rating_f", "distance_mi"]
st.dataframe(filt.drop(columns=hide_cols, errors="ignore"), use_container_width=True, height=520)

# ---------- Notes ----------
with st.expander("Notes"):
    st.markdown("""
    - Safer CSS prevents cutoffs; inline filters get more horizontal space.
    - Filters left (1/3), map right (2/3), table full width below.
    - Country/Region parsed from address; price/rating/distance parsed from columns.
    - Map defaults to Madrid if no coordinates.
    """)
