import pandas as pd
import streamlit as st
import altair as alt
import json
import os

st.set_page_config(page_title="Transactions Viewer", page_icon="🧾", layout="wide")
SAMPLE_CSV = "sample_transactions.csv"

# Reset button at the top
col1, col2 = st.columns([4, 1])
with col1:
    st.title("🧾Transactions Viewer")
with col2:
    if st.button("🔄 Reset All", type="secondary", help="Clear all data and reset the app"):
        # Clear all session state
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# Upload data will be moved inside transactions table

@st.cache_data
def load_credit_cards():
    """Load credit card data from JSON file"""
    try:
        json_path = os.path.join(os.path.dirname(__file__), "cc_options.json")
        with open(json_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("Credit card data file (cc_options.json) not found")
        return None

@st.cache_data
def load_default():
    """Read the local sample CSV shipped next to the app."""
    return pd.read_csv(SAMPLE_CSV)

def get_all_card_options(transaction_category, amount, cc_data, total_monthly_spend=0):
    """Get all credit card options for a given transaction, factoring in annual fees"""
    if not cc_data:
        return []
    
    # Category mapping from transaction categories to credit card categories
    category_mapping = {
        "groceries": ["U.S._supermarkets", "grocery_stores", "grocery_stores_and_wholesale_clubs"],
        "dining": ["restaurants_worldwide", "dining"],
        "gas": ["gas_stations"],  # Add if available in cards
        "online_shopping": ["online_shopping"],  # Add if available
        "utilities": ["utilities"],  # Add if available
        "airfare": ["flights_booked_direct"],
        "hotels": ["hotels"],  # Add if available
        "subscriptions": ["streaming_services"],
        "entertainment": ["entertainment"],
        "drugstores": ["drugstores"],
        "travel_portal": ["travel_portal"],
        "home_improvement": ["home_improvement"],  # Add if available
        "rideshare": ["rideshare"]  # Add if available
    }
    
    card_options = []
    
    for card in cc_data["credit_cards"]:
        # Check base rate first
        base_rate = card["base_rate_x"]
        
        # Check category multipliers
        multipliers = card.get("category_multipliers_x", {})
        max_multiplier = base_rate
        matched_category = "Base Rate"
        
        # Map transaction category to credit card categories
        mapped_categories = category_mapping.get(transaction_category.lower(), [])
        for cc_category in mapped_categories:
            if cc_category in multipliers:
                if multipliers[cc_category] > max_multiplier:
                    max_multiplier = multipliers[cc_category]
                    matched_category = cc_category.replace("_", " ").title()
        
        # Calculate rewards for this transaction
        transaction_rewards = amount * max_multiplier / 100
        
        # Parse annual cost (remove $ and convert to float)
        annual_cost_str = card["annual_cost"].replace("$", "").replace(",", "")
        annual_cost = float(annual_cost_str) if annual_cost_str else 0
        
        # Calculate monthly annual cost
        monthly_annual_cost = annual_cost / 12
        
        # Calculate net rewards (rewards minus monthly portion of annual fee)
        net_rewards = transaction_rewards - monthly_annual_cost
        
        card_options.append({
            "card_name": card["card_name"],
            "network": card["network"],
            "annual_cost": card["annual_cost"],
            "annual_cost_numeric": annual_cost,
            "reward_rate": max_multiplier,
            "matched_category": matched_category,
            "rewards": transaction_rewards,
            "monthly_annual_cost": monthly_annual_cost,
            "net_rewards": net_rewards
        })
    
    # Sort by net rewards (highest first)
    card_options.sort(key=lambda x: x["net_rewards"], reverse=True)
    return card_options

def find_best_card(transaction_category, amount, cc_data):
    """Find the best credit card for a given transaction"""
    options = get_all_card_options(transaction_category, amount, cc_data)
    if not options:
        return "No card data", 0, 0
    
    best = options[0]  # Already sorted by rewards
    return best["card_name"], best["reward_rate"], best["rewards"]

# --- Transactions table ---
with st.expander("📊 View Transactions Table", expanded=False):
    # Upload data section nested inside
    uploaded = st.file_uploader("Upload CSV", type=["csv"], label_visibility="collapsed")
    st.caption("If no file is uploaded, a small sample dataset is used.")
    
    # Load data
    if uploaded is not None:
        try:
            df = pd.read_csv(uploaded)
        except Exception as e:
            st.error(f"Could not read file: {e}")
            st.stop()
    else:
        df = load_default()

    # --- Validation ---
    required = {"date","vendor","category","price"}
    missing = required - set(map(str.lower, df.columns))
    if missing:
        st.error(f"Missing required columns: {sorted(list(missing))}. Expected: {sorted(list(required))}")
        st.stop()

    # --- Normalize and parse ---
    df.columns = [c.lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    # 🔽 sort by date descending
    df = df.sort_values("date", ascending=False)

    st.dataframe(df, use_container_width=True, hide_index=True)


# Load credit card data
cc_data = load_credit_cards()

# --- Filters + bar chart ---
st.subheader("Total spend by category")

month_series = df["date"].dt.to_period("M").astype(str).unique().tolist()
month_series.sort()
month_options = ["All"] + month_series
selected_month = st.selectbox("Select month", month_options, index=0)

if selected_month != "All":
    target = pd.Period(selected_month)
    filtered = df[df["date"].dt.to_period("M") == target]
else:
    filtered = df.copy()

by_cat = (
    filtered
    .groupby("category", as_index=False)["price"]
    .sum()
    .rename(columns={"price": "total_spend"})
    .sort_values("total_spend", ascending=False)
    .head(20)
)

if by_cat.empty:
    st.info("No data for the selected month.")
else:
    sort_order = by_cat["category"].tolist()
    bars = (
        alt.Chart(by_cat)
        .mark_bar()
        .encode(
            y=alt.Y("category:N", sort=sort_order, title="Category"),
            x=alt.X("total_spend:Q", title="Total Spend ($)", axis=alt.Axis(format="$,.0f")),
            tooltip=[
                alt.Tooltip("category:N", title="Category"),
                alt.Tooltip("total_spend:Q", title="Total Spend", format="$,.2f"),
            ],
        )
    )

    labels = (
        alt.Chart(by_cat)
        .mark_text(align="left", baseline="middle", dx=4)
        .encode(
            y=alt.Y("category:N", sort=sort_order),
            x=alt.X("total_spend:Q"),
            text=alt.Text("total_spend:Q", format="$,.2f"),
        )
    )

    chart_height = min(max(300, 35 * len(by_cat)), 800)
    chart = (bars + labels).properties(height=chart_height)
    st.altair_chart(chart, use_container_width=True)

"""
All Available Cards section shows the full list of cards loaded from cc_options.json.
It is collapsed by default to keep the main view clean.
"""
# --- Credit Card Optimization ---
if cc_data:
    st.subheader("💳 Credit Card Optimization")
    
    # Future purchases section
    with st.expander("🔮 Future Purchases", expanded=False):
        st.write("**Add planned future purchases to see how they affect optimal card strategy:**")
        
        # Initialize session state
        if 'future_purchases' not in st.session_state:
            st.session_state.future_purchases = []
        
        # Create editable dataframe for future purchases
        if st.session_state.future_purchases:
            # Convert to DataFrame for editing
            future_df = pd.DataFrame(st.session_state.future_purchases)
            
            # Add empty row for new entries
            empty_row = pd.DataFrame([{
                'date': pd.Timestamp.now().date(),
                'vendor': '',
                'category': 'groceries',
                'amount': 0.0
            }])
            future_df = pd.concat([future_df, empty_row], ignore_index=True)
            
            # Display editable dataframe
            edited_df = st.data_editor(
                future_df,
                column_config={
                    "date": st.column_config.DateColumn("Date", width="small"),
                    "vendor": st.column_config.TextColumn("Vendor", width="medium"),
                    "category": st.column_config.SelectboxColumn(
                        "Category",
                        options=["groceries", "dining", "gas", "online_shopping", "utilities", 
                                "airfare", "hotels", "subscriptions", "entertainment", "drugstores", 
                                "travel_portal", "home_improvement", "rideshare"],
                        width="medium"
                    ),
                    "amount": st.column_config.NumberColumn("Amount ($)", min_value=0.01, step=0.01, format="$%.2f")
                },
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True
            )
            
            # Update session state with edited data
            if not edited_df.empty:
                # Filter out empty rows
                valid_rows = edited_df[(edited_df['vendor'] != '') & (edited_df['amount'] > 0) & (edited_df['date'].notna())]
                st.session_state.future_purchases = valid_rows.to_dict('records')
            
            # Action buttons
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Clear All", type="secondary"):
                    st.session_state.future_purchases = []
                    st.rerun()
            with col2:
                if st.button("Refresh Analysis", type="primary"):
                    st.rerun()
        else:
            # Show empty state with instructions
            st.info("No future purchases added yet. Use the table below to add planned purchases.")
            
            # Create initial empty dataframe
            empty_df = pd.DataFrame([{
                'date': pd.Timestamp.now().date(),
                'vendor': '',
                'category': 'groceries',
                'amount': 0.0
            }])
            
            edited_df = st.data_editor(
                empty_df,
                column_config={
                    "date": st.column_config.DateColumn("Date", width="small"),
                    "vendor": st.column_config.TextColumn("Vendor", width="medium"),
                    "category": st.column_config.SelectboxColumn(
                        "Category",
                        options=["groceries", "dining", "gas", "online_shopping", "utilities", 
                                "airfare", "hotels", "subscriptions", "entertainment", "drugstores", 
                                "travel_portal", "home_improvement", "rideshare"],
                        width="medium"
                    ),
                    "amount": st.column_config.NumberColumn("Amount ($)", min_value=0.01, step=0.01, format="$%.2f")
                },
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True
            )
            
            # Update session state
            if not edited_df.empty:
                valid_rows = edited_df[(edited_df['vendor'] != '') & (edited_df['amount'] > 0) & (edited_df['date'].notna())]
                if not valid_rows.empty:
                    st.session_state.future_purchases = valid_rows.to_dict('records')
                    st.success("Future purchases added! Analysis will update automatically.")
    
    # Calculate optimal cards for each transaction (including future purchases)
    optimization_data = []
    total_gross_rewards = 0
    total_annual_costs = 0
    unique_cards_used = set()
    
    # Process historical transactions
    for _, row in df.iterrows():
        options = get_all_card_options(row['category'], row['price'], cc_data)
        if options:
            best_option = options[0]  # Already sorted by net rewards
            optimization_data.append({
                'Date': row['date'].strftime('%Y-%m-%d'),
                'Vendor': row['vendor'],
                'Category': row['category'],
                'Amount': f"${row['price']:.2f}",
                'Best Card': best_option['card_name'],
                'Reward Rate': f"{best_option['reward_rate']:.1f}%",
                'Rewards': f"${best_option['rewards']:.2f}"
            })
            
            total_gross_rewards += best_option['rewards']
            if best_option['card_name'] not in unique_cards_used:
                total_annual_costs += best_option['annual_cost_numeric']
                unique_cards_used.add(best_option['card_name'])
    
    # Process future purchases if any
    if 'future_purchases' in st.session_state and st.session_state.future_purchases:
        for future_purchase in st.session_state.future_purchases:
            options = get_all_card_options(future_purchase['category'], future_purchase['amount'], cc_data)
            if options:
                best_option = options[0]
                optimization_data.append({
                    'Date': future_purchase['date'].strftime('%Y-%m-%d') if isinstance(future_purchase['date'], pd.Timestamp) else str(future_purchase['date']),
                    'Vendor': future_purchase['vendor'],
                    'Category': future_purchase['category'],
                    'Amount': f"${future_purchase['amount']:.2f}",
                    'Best Card': best_option['card_name'],
                    'Reward Rate': f"{best_option['reward_rate']:.1f}%",
                    'Rewards': f"${best_option['rewards']:.2f}"
                })
                
                total_gross_rewards += best_option['rewards']
                if best_option['card_name'] not in unique_cards_used:
                    total_annual_costs += best_option['annual_cost_numeric']
                    unique_cards_used.add(best_option['card_name'])
    
    opt_df = pd.DataFrame(optimization_data)
    
    # Add row selection
    st.write("Click on a row below to see all credit card options for that transaction:")
    selected_rows = st.dataframe(
        opt_df, 
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        hide_index=True
    )
    
    # Show detailed comparison in sidebar for selected row
    if selected_rows.selection.rows:
        selected_idx = selected_rows.selection.rows[0]
        selected_transaction = optimization_data[selected_idx]
        
        # Get all card options for this transaction
        transaction_row = df.iloc[selected_idx]
        all_options = get_all_card_options(transaction_row['category'], transaction_row['price'], cc_data)
        
        # Create sidebar for card comparison
        with st.sidebar:
            st.subheader(f"💳 Card Options")
            st.write(f"**Transaction**: {selected_transaction['Vendor']}")
            st.write(f"**Category**: {selected_transaction['Category']}")
            st.write(f"**Amount**: {selected_transaction['Amount']}")
            
            # Highlight the best option
            best_option = all_options[0]
            st.success(f"🏆 **Best**: {best_option['card_name']}")
            st.write(f"**Rate**: {best_option['reward_rate']:.1f}% ({best_option['matched_category']})")
            st.write(f"**Gross Rewards**: ${best_option['rewards']:.2f}")
            st.write(f"**Annual Cost**: {best_option['annual_cost']}")
            st.write(f"**Net Rewards**: ${best_option['net_rewards']:.2f}")
            
            st.divider()
            
            # Show all options
            st.write("**All Options:**")
            for i, option in enumerate(all_options):
                if i == 0:
                    st.write(f"🥇 **{option['card_name']}** - {option['reward_rate']:.1f}% = ${option['net_rewards']:.2f} net")
                elif i == 1:
                    st.write(f"🥈 **{option['card_name']}** - {option['reward_rate']:.1f}% = ${option['net_rewards']:.2f} net")
                elif i == 2:
                    st.write(f"🥉 **{option['card_name']}** - {option['reward_rate']:.1f}% = ${option['net_rewards']:.2f} net")
                else:
                    st.write(f"**{option['card_name']}** - {option['reward_rate']:.1f}% = ${option['net_rewards']:.2f} net")
                
                if i < len(all_options) - 1:
                    st.write("---")
    
    # Summary stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Gross Rewards", f"${total_gross_rewards:.2f}")
    with col2:
        st.metric("Total Annual Costs", f"${total_annual_costs:.2f}")
    with col3:
        net_total = total_gross_rewards - total_annual_costs
        st.metric("Net Rewards (After Fees)", f"${net_total:.2f}")
    
    st.info(f"💡 **Cards Used**: {len(unique_cards_used)} unique cards. Annual costs are only counted once per card.")
   
    # --- All Available Cards (collapsible) ---
    with st.expander("All Available Cards", expanded=False):
        card_rows = []
        for card in cc_data.get("credit_cards", []):
            # Build a readable multipliers string
            multipliers = card.get("category_multipliers_x", {})
            if multipliers:
                readable = ", ".join([
                    f"{k.replace('_',' ').title()}: {v:.1f}%" for k, v in multipliers.items()
                ])
            else:
                readable = "—"

            card_rows.append({
                "Card Name": card.get("card_name", ""),
                "Network": card.get("network", ""),
                "Annual Cost": card.get("annual_cost", ""),
                "Base Rate": f"{card.get('base_rate_x', 0):.1f}%",
                "Category Multipliers": readable,
            })

        cards_df = pd.DataFrame(card_rows)
        st.dataframe(cards_df, use_container_width=True, hide_index=True)
else:
    st.warning("Credit card data not available for optimization")

# --- Future Enhancements To-Do List ---
with st.expander("📋 Future Enhancements", expanded=False):
    st.write("**Planned improvements for the credit card optimization tool:**")
    
    todo_items = [
        "💰 **Annual Fee Analysis** - Factor in annual fees when calculating net rewards",
        "📊 **Rewards Rate Comparison** - Visual comparison of reward rates across cards",
        "➕ **Add More Cards** - Expand the credit card database with additional options",
        "🎁 **Intro Offers** - Include sign-up bonuses and introductory rates",
        "💳 **Recommended Credit Range** - Suggest cards based on credit score requirements"
    ]
    
    for item in todo_items:
        st.write(f"• {item}")
    
    st.caption("💡 *These features will be added in future updates to enhance the optimization experience.*")
