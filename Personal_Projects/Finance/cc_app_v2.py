# optimizer_dual.py
import os
import io
import json
import requests
import pandas as pd
import streamlit as st
import altair as alt


st.set_page_config(page_title="Credit Card Rewards Optimizer (Dual Modes)", page_icon="🧾", layout="wide")

# -----------------------------
# Shared: data loading helpers
# -----------------------------
@st.cache_data
def load_credit_cards():
    """Load credit card data: try local file first, then GitHub fallback."""
    local_path = "cc_options.json"
    if os.path.exists(local_path):
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            st.warning(f"Local file found but could not be read: {e}")

    try:
        url = "https://raw.githubusercontent.com/mhuh22/Python-workspace/master/Personal_Projects/Finance/cc_options.json"
        response = requests.get(url, headers={"User-Agent": "streamlit-app/1.0"}, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching credit card data from GitHub: {e}")
        return None

@st.cache_data(show_spinner=False)
def load_default_transactions():
    url = "https://raw.githubusercontent.com/mhuh22/Python-workspace/master/Personal_Projects/Finance/sample_transactions.csv"
    r = requests.get(url, headers={"User-Agent": "streamlit-app/1.0"}, timeout=10)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text))

# -----------------------------
# Shared: optimization helpers
# -----------------------------
def get_all_card_options(transaction_category, amount, cc_data):
    """Get all credit card options for a single transaction amount in a category."""
    if not cc_data or "credit_cards" not in cc_data:
        return []

    # Map app categories -> card categories
    category_mapping = {
        "groceries": ["U.S._supermarkets", "grocery_stores", "grocery_stores_and_wholesale_clubs"],
        "dining": ["restaurants_worldwide", "dining"],
        "gas": ["gas_stations"],
        "online_shopping": ["online_shopping"],
        "utilities": ["utilities"],
        "airfare": ["flights_booked_direct"],
        "hotels": ["hotels"],
        "subscriptions": ["streaming_services"],
        "entertainment": ["entertainment"],
        "drugstores": ["drugstores"],
        "travel_portal": ["travel_portal"],
        "home_improvement": ["home_improvement"],
        "rideshare": ["rideshare"]
    }

    card_options = []
    for card in cc_data["credit_cards"]:
        base_rate = card.get("base_rate_x", 0.0)
        multipliers = card.get("category_multipliers_x", {}) or {}
        max_multiplier = base_rate
        matched_category = "Base Rate"

        mapped_categories = category_mapping.get(str(transaction_category).lower(), [])
        for cc_category in mapped_categories:
            if cc_category in multipliers and multipliers[cc_category] > max_multiplier:
                max_multiplier = multipliers[cc_category]
                matched_category = cc_category.replace("_", " ").title()

        transaction_rewards = amount * max_multiplier / 100.0

        # Parse annual fee
        fee_str = str(card.get("annual_cost", "")).replace("$", "").replace(",", "").strip()
        annual_cost = float(fee_str) if fee_str else 0.0

        monthly_annual_cost = annual_cost / 12.0
        net_rewards = transaction_rewards - monthly_annual_cost

        card_options.append({
            "card_name": card.get("card_name", "Unknown"),
            "annual_cost": card.get("annual_cost", "$0"),
            "annual_cost_numeric": annual_cost,
            "reward_rate": max_multiplier,
            "matched_category": matched_category,
            "rewards": transaction_rewards,
            "monthly_annual_cost": monthly_annual_cost,
            "net_rewards": net_rewards,
        })

    card_options.sort(key=lambda x: x["net_rewards"], reverse=True)
    return card_options

# -----------------------------
# UI: Header + Mode Toggle
# -----------------------------
col1, col2 = st.columns([4, 1])
with col1:
    st.title("🧾 Credit Card Rewards Optimizer (Dual Modes)")
with col2:
    if st.button("🔄 Reset", type="secondary"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

# Load both resources
cc_data = load_credit_cards()
sample_df = load_default_transactions()

if not cc_data or not cc_data.get("credit_cards"):
    st.stop()

# Compute average monthly category spend from sample data
sample_df["date"] = pd.to_datetime(sample_df["date"], errors="coerce")
monthly_avg = (
    sample_df.groupby("category")["price"].mean().to_dict()
)

mode = st.radio(
    "Choose optimizer mode:",
    ["Monthly Spend Mode", "Spreadsheet Mode"],   # <-- swapped order
    horizontal=True,
    index=0                                       # <-- monthly spend default
)


cc_data = load_credit_cards()
if not cc_data or not cc_data.get("credit_cards"):
    st.stop()

# ----------------------------------------------------
# MODE A: Spreadsheet Mode (CSV of individual txns)
# ----------------------------------------------------
if mode == "Spreadsheet Mode":
    st.subheader("📊 Spreadsheet Mode")
    st.caption("Upload a CSV of transactions (or use the sample). Required columns: date, vendor, category, price.")

    uploaded = st.file_uploader("Upload CSV", type=["csv"])
    if uploaded is not None:
        try:
            df = pd.read_csv(uploaded)
        except Exception as e:
            st.error(f"Could not read file: {e}")
            st.stop()
    else:
        df = load_default_transactions()

    # Validate + normalize
    required = {"date", "vendor", "category", "price"}
    missing = required - set(map(str.lower, df.columns))
    if missing:
        st.error(f"Missing columns: {sorted(list(missing))}. Expected: {sorted(list(required))}")
        st.stop()

    df.columns = [c.lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df = df.sort_values("date", ascending=False)

    st.dataframe(df, use_container_width=True, hide_index=True)

    # Optimize across transactions
    optimization_rows = []
    total_spend = 0.0
    total_gross = 0.0
    total_fees = 0.0
    unique_cards = set()

    for _, row in df.iterrows():
        amount = float(row["price"])
        opts = get_all_card_options(row["category"], amount, cc_data)
        if not opts:
            continue
        best = opts[0]
        optimization_rows.append({
            "Date": row["date"].strftime("%Y-%m-%d"),
            "Vendor": row["vendor"],
            "Category": row["category"],
            "Amount": f"${amount:,.2f}",
            "Best Card": best["card_name"],
            "Reward Rate": f"{best['reward_rate']:.1f}%",
            "Gross Rewards": f"${best['rewards']:,.2f}",
            "Net (1/12 fee deducted)": f"${best['net_rewards']:,.2f}",
        })

        total_spend += amount
        total_gross += best["rewards"]
        if best["card_name"] not in unique_cards:
            total_fees += best["annual_cost_numeric"]
            unique_cards.add(best["card_name"])

    st.write("### Recommendations")
    if optimization_rows:
        st.dataframe(pd.DataFrame(optimization_rows), use_container_width=True, hide_index=True)

        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("Total Gross Rewards", f"${total_gross:,.2f}")
        with c2: st.metric("Total Spend", f"${total_spend:,.2f}")
        with c3: st.metric("Total Annual Costs", f"${total_fees:,.2f}")
        with c4: st.metric("Net Rewards (After Fees)", f"${(total_gross-total_fees):,.2f}")

        st.caption(f"Cards used: {len(unique_cards)} (annual fees counted once per card).")
    else:
        st.info("No recommendations to show. Check categories/amounts.")

# ----------------------------------------------------
# MODE B: Monthly Spend Mode (default)
# ----------------------------------------------------
if mode == "Monthly Spend Mode":
    st.subheader("🗂️ Monthly Spend Mode")
    st.caption("Enter your average monthly spend by category (defaults are based on sample data).")

    input_categories = [
        "groceries", "dining", "gas", "online_shopping", "utilities",
        "airfare", "hotels", "subscriptions", "entertainment",
        "drugstores", "travel_portal", "home_improvement", "rideshare"
    ]

    # Initialize defaults from sample averages
    if "monthly_spend" not in st.session_state:
        st.session_state.monthly_spend = {}
        for c in input_categories:
            default_val = float(monthly_avg.get(c, 0.0))
            st.session_state.monthly_spend[c] = round(default_val, 2)

    # Side-by-side layout: inputs (left) | donut chart (right)
    col_inputs, col_chart = st.columns([2, 1], gap="large")

    # -----------------------------
    # LEFT: Inputs grid
    # -----------------------------
    with col_inputs:
        cols = st.columns(3)
        for i, c in enumerate(input_categories):
            with cols[i % 3]:
                st.session_state.monthly_spend[c] = st.number_input(
                    c.replace("_", " ").title(),
                    min_value=0.0,
                    step=10.0,
                    value=float(st.session_state.monthly_spend[c]),
                    key=f"spend_{c}",
                )
        st.caption("Adjust your spending to update the chart and optimization results.")

# -----------------------------
# RIGHT: Donut Chart
# -----------------------------
with col_chart:
    st.subheader("💸 Budget Breakdown")

    donut_df = pd.DataFrame([
        {"Category": c.replace("_", " ").title(), "Spend": amt}
        for c, amt in st.session_state.monthly_spend.items() if amt > 0
    ])

    if donut_df.empty:
        st.info("Enter some spending amounts to see your breakdown.")
    else:
        import altair as alt

        total_spend = donut_df["Spend"].sum()
        donut_df["Percent"] = donut_df["Spend"] / total_spend * 100
        donut_df["Label"] = donut_df.apply(
            lambda r: f"{r['Category']} ({r['Percent']:.1f}%)", axis=1
        )

        base = alt.Chart(donut_df).encode(
            theta=alt.Theta("Spend:Q", stack=True),
            color=alt.Color("Category:N", legend=None),
            tooltip=[
                alt.Tooltip("Category:N", title="Category"),
                alt.Tooltip("Spend:Q", format="$,.2f"),
                alt.Tooltip("Percent:Q", format=".1f", title="% of Total")
            ]
        )

        # Donut arcs with white borders for spacing
        arcs = base.mark_arc(
            innerRadius=80,
            outerRadius=140,
            stroke="white",
            strokeWidth=2
        )

        # White category + percent labels placed further out
        labels = base.mark_text(
            radius=190,  # increased radius for more space
            size=13,
            fontWeight="bold",
            color="white"   # white text labels
        ).encode(
            text=alt.Text("Label:N")
        )

        # White center text (total spend)
        center_text = (
            alt.Chart(pd.DataFrame([{"text": f"Total\n${total_spend:,.0f}"}]))
            .mark_text(
                align="center",
                baseline="middle",
                fontSize=22,
                fontWeight="bold",
                color="white"
            )
            .encode(text="text:N")
        )

        donut_chart = (arcs + labels + center_text).properties(
            width=480,
            height=480,
            padding={"left": 20, "right": 20, "top": 20, "bottom": 20}  # more outer space
        )

        st.altair_chart(donut_chart, use_container_width=True)


    st.divider()



# Optimize per-category totals
recs = []
total_spend = 0.0
total_gross = 0.0
total_fees = 0.0
unique_cards = set()

for cat, amt in st.session_state.monthly_spend.items():
    if amt <= 0:
        continue
    opts = get_all_card_options(cat, amt, cc_data)
    if not opts:
        continue
    best = opts[0]
    recs.append({
        "Category": cat,
        "Monthly Spend": f"${amt:,.2f}",
        "Best Card": best["card_name"],
        "Reward Rate": f"{best['reward_rate']:.1f}%",
        "Gross Rewards": f"${best['rewards']:,.2f}",
        "Net (1/12 fee deducted)": f"${best['net_rewards']:,.2f}",
    })
    total_spend += amt
    total_gross += best["rewards"]
    if best["card_name"] not in unique_cards:
        total_fees += best["annual_cost_numeric"]
        unique_cards.add(best["card_name"])

st.write("### Recommended Cards by Category")
if recs:
    st.dataframe(pd.DataFrame(recs), use_container_width=True, hide_index=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Total Gross Rewards", f"${total_gross:,.2f}")
    with c2: st.metric("Total Spend", f"${total_spend:,.2f}")
    with c3: st.metric("Total Annual Costs", f"${total_fees:,.2f}")
    with c4: st.metric("Net Rewards (After Fees)", f"${(total_gross-total_fees):,.2f}")

    st.caption(f"Cards used: {len(unique_cards)} (annual fees counted once per card).")
else:
    st.info("Enter some monthly spend to see recommendations.")

# -----------------------------
# All Cards (for reference)
# -----------------------------
with st.expander("All Available Cards", expanded=False):
    rows = []
    for card in cc_data.get("credit_cards", []):
        multipliers = card.get("category_multipliers_x", {}) or {}
        readable = ", ".join([f"{k.replace('_',' ').title()}: {v:.1f}%"
                              for k, v in multipliers.items()]) if multipliers else "—"
        rows.append({
            "Card Name": card.get("card_name", ""),
            "Annual Cost": card.get("annual_cost", ""),
            "Base Rate": f"{card.get('base_rate_x', 0):.1f}%",
            "Category Multipliers": readable,
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
