import pandas as pd
import streamlit as st
import io
import requests
import altair as alt
import json
import os

st.set_page_config(page_title="Credit Card Rewards Optimizer", page_icon="🧾", layout="wide")

# Reset button at the top
col1, col2, col3 = st.columns([3, 1, 1])
with col1:
    st.title("🧾Credit Card Rewards Optimizer")
# with col2:
#     if st.button("🚀 Optimize", type="primary", help="Recalculate optimization for all transactions"):
#         # Force recalculation by clearing editable transactions
#         if 'editable_transactions' in st.session_state:
#             st.session_state.editable_transactions = []
#         st.rerun()
with col3:
    if st.button("🔄 Reset All", type="secondary", help="Clear all data and reset the app"):
        # Clear all session state
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# Upload data will be moved inside transactions table

@st.cache_data
def load_credit_cards():
    """Load credit card data: try local file first, then GitHub fallback."""
    local_path = "cc_options.json"
    
    # 1. Try local file
    if os.path.exists(local_path):
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except Exception as e:
            st.warning(f"Local file found but could not be read: {e}")

    # 2. Fallback to GitHub URL
    try:
        url = "https://raw.githubusercontent.com/mhuh22/Python-workspace/master/Personal_Projects/Finance/cc_options.json"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching credit card data from GitHub: {e}")
        return None


@st.cache_data(show_spinner=False)
def load_default():
    # Try to load from local file first
    local_file = "sample_transactions.csv"
    if os.path.exists(local_file):
        return pd.read_csv(local_file)
    
    # Fall back to URL if local file doesn't exist
    url = "https://raw.githubusercontent.com/mhuh22/Python-workspace/master/Personal_Projects/Finance/sample_transactions.csv"
    r = requests.get(url, headers={"User-Agent": "streamlit-app/1.0"}, timeout=10)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text))

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

# --- Load transaction data ---
# Initialize df in session state if not exists
if 'transaction_df' not in st.session_state:
    st.session_state.transaction_df = load_default()
    # Normalize and parse
    st.session_state.transaction_df.columns = [c.lower() for c in st.session_state.transaction_df.columns]
    st.session_state.transaction_df["date"] = pd.to_datetime(st.session_state.transaction_df["date"], errors="coerce")
    st.session_state.transaction_df = st.session_state.transaction_df.dropna(subset=["date"])
    st.session_state.transaction_df = st.session_state.transaction_df.sort_values("date", ascending=False)

df = st.session_state.transaction_df

# Load credit card data
cc_data = load_credit_cards()

# --- Filters + bar chart ---
# Calculate optimization metrics from original dataframe
if cc_data:
    total_spend_from_df = 0
    total_gross_rewards_from_df = 0
    total_annual_costs_from_df = 0
    unique_cards_used_from_df = set()
    
    for _, row in df.iterrows():
        category = row['category']
        amount = float(row['price'])
        total_spend_from_df += amount
        
        options = get_all_card_options(category, amount, cc_data)
        if options:
            best_option = options[0]  # Already sorted by net rewards
            total_gross_rewards_from_df += best_option['rewards']
            if best_option['card_name'] not in unique_cards_used_from_df:
                total_annual_costs_from_df += best_option['annual_cost_numeric']
                unique_cards_used_from_df.add(best_option['card_name'])
    
    net_rewards_from_df = total_gross_rewards_from_df - total_annual_costs_from_df
    
    # Display all metrics in a row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Spend", f"${total_spend_from_df:.2f}")
    with col2:
        st.metric("Total Gross Rewards", f"${total_gross_rewards_from_df:.2f}")
    with col3:
        st.metric("Total Annual Costs", f"${total_annual_costs_from_df:.2f}")
    with col4:
        st.metric("Net Rewards (After Fees)", f"${net_rewards_from_df:.2f}")
else:
    # If no credit card data, just show total spend
    total_spend_from_df = df["price"].sum()
    st.metric("Total Spend", f"${total_spend_from_df:.2f}")

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
    
    # Initialize editable cards in session state
    if 'editable_cards' not in st.session_state:
        st.session_state.editable_cards = cc_data.get("credit_cards", []).copy()
    
    # Use editable cards for optimization
    cc_data_for_optimization = {"credit_cards": st.session_state.editable_cards}
    
    # Initialize editable transactions in session state
    if 'editable_transactions' not in st.session_state:
        st.session_state.editable_transactions = []
    
    # Build initial transaction list from historical data (sorted by date desc)
    if not st.session_state.editable_transactions:
        temp_transactions = []
        for _, row in df.iterrows():
            temp_transactions.append({
                'Date': row['date'].strftime('%Y-%m-%d'),
                'Vendor': row['vendor'],
                'Category': row['category'],
                'Amount': float(row['price'])
            })
        # Sort by date descending (newest first)
        temp_transactions.sort(key=lambda x: x['Date'], reverse=True)
        st.session_state.editable_transactions = temp_transactions
    
    # Create initial combined dataframe for display (will be recalculated after edits)
    # Calculate optimal cards for each transaction from editable table
    optimization_data = []
    total_gross_rewards = 0
    total_annual_costs = 0
    total_spend = 0
    unique_cards_used = set()
    
    # Process editable transactions to get optimization results
    for trans in st.session_state.editable_transactions:
        category = trans['Category']
        amount = float(trans['Amount'])
        
        options = get_all_card_options(category, amount, cc_data_for_optimization)
        if options:
            best_option = options[0]  # Already sorted by net rewards
            optimization_data.append({
                'Date': trans['Date'],
                'Vendor': trans['Vendor'],
                'Category': category,
                'Amount': amount,
                'Best Card': best_option['card_name'],
                'Reward Rate': f"{best_option['reward_rate']:.1f}%",
                'Rewards': f"${best_option['rewards']:.2f}"
            })
            
            total_gross_rewards += best_option['rewards']
            total_spend += amount
            if best_option['card_name'] not in unique_cards_used:
                total_annual_costs += best_option['annual_cost_numeric']
                unique_cards_used.add(best_option['card_name'])
    
    
    # Create combined dataframe with transaction data and optimization results
    if optimization_data:
        combined_df = pd.DataFrame(optimization_data)
        
        # Sort by date descending (newest first)
        combined_df['Date'] = pd.to_datetime(combined_df['Date'], errors='coerce')
        combined_df = combined_df.sort_values('Date', ascending=False, na_position='last')
        combined_df['Date'] = combined_df['Date'].dt.strftime('%Y-%m-%d')
    else:
        # Create empty dataframe with all columns
        combined_df = pd.DataFrame(columns=['Date', 'Vendor', 'Category', 'Amount', 'Best Card', 'Reward Rate', 'Rewards'])
    
    # File uploader for CSV
    uploaded = st.file_uploader("Upload CSV", type=["csv"], key="optimization_file_uploader")
    
    # Handle file upload
    if uploaded is not None:
        try:
            new_df = pd.read_csv(uploaded)
            # Validation
            required = {"date", "vendor", "category", "price"}
            missing = required - set(map(str.lower, new_df.columns))
            if missing:
                st.error(f"Missing required columns: {sorted(list(missing))}. Expected: {sorted(list(required))}")
            else:
                # Normalize and parse
                new_df.columns = [c.lower() for c in new_df.columns]
                new_df["date"] = pd.to_datetime(new_df["date"], errors="coerce")
                new_df = new_df.dropna(subset=["date"])
                new_df = new_df.sort_values("date", ascending=False)
                
                # Update session state
                st.session_state.transaction_df = new_df
                # Reset editable transactions to trigger reload
                st.session_state.editable_transactions = []
                st.rerun()
        except Exception as e:
            st.error(f"Could not read file: {e}")
    
    # Add filters section
    with st.expander("🔍 Filters", expanded=False):
        filter_col1, filter_col2, filter_col3 = st.columns(3)
        
        with filter_col1:
            # Category filter
            all_categories = ["groceries", "dining", "gas", "online_shopping", "utilities", 
                             "airfare", "hotels", "subscriptions", "entertainment", "drugstores", 
                             "travel_portal", "home_improvement", "rideshare"]
            selected_categories = st.multiselect(
                "Filter by Category",
                options=all_categories,
                default=[],
                key="filter_categories"
            )
        
        with filter_col2:
            # Best Card filter
            if not combined_df.empty and 'Best Card' in combined_df.columns:
                all_cards = sorted([card for card in combined_df['Best Card'].unique() if card and card.strip()])
                selected_cards = st.multiselect(
                    "Filter by Best Card",
                    options=all_cards,
                    default=[],
                    key="filter_cards"
                )
            else:
                selected_cards = []
        
        with filter_col3:
            # Vendor search
            vendor_search = st.text_input(
                "Search Vendor",
                value="",
                key="filter_vendor",
                placeholder="Enter vendor name..."
            )
        
        # Date range filter
        if not combined_df.empty and 'Date' in combined_df.columns:
            date_col1, date_col2 = st.columns(2)
            with date_col1:
                min_date = st.date_input(
                    "From Date",
                    value=None,
                    key="filter_date_from"
                )
            with date_col2:
                max_date = st.date_input(
                    "To Date",
                    value=None,
                    key="filter_date_to"
                )
        else:
            min_date = None
            max_date = None
        
        # Clear filters button
        if st.button("Clear All Filters", type="secondary", key="clear_filters"):
            st.session_state.filter_categories = []
            st.session_state.filter_cards = []
            st.session_state.filter_vendor = ""
            st.session_state.filter_date_from = None
            st.session_state.filter_date_to = None
            st.rerun()
    
    # Apply filters to combined_df before adding empty row
    filtered_df = combined_df.copy()
    
    if not filtered_df.empty:
        # Filter by category
        if selected_categories:
            filtered_df = filtered_df[filtered_df['Category'].isin(selected_categories)]
        
        # Filter by best card
        if selected_cards and 'Best Card' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['Best Card'].isin(selected_cards)]
        
        # Filter by vendor search
        if vendor_search and vendor_search.strip():
            vendor_search_lower = vendor_search.lower().strip()
            filtered_df = filtered_df[
                filtered_df['Vendor'].astype(str).str.lower().str.contains(vendor_search_lower, na=False)
            ]
        
        # Filter by date range
        if (min_date is not None or max_date is not None) and 'Date' in filtered_df.columns:
            filtered_df['Date'] = pd.to_datetime(filtered_df['Date'], errors='coerce')
            if min_date is not None:
                filtered_df = filtered_df[filtered_df['Date'] >= pd.Timestamp(min_date)]
            if max_date is not None:
                filtered_df = filtered_df[filtered_df['Date'] <= pd.Timestamp(max_date)]
            filtered_df['Date'] = filtered_df['Date'].dt.strftime('%Y-%m-%d')
    
    # Show filter status
    total_rows = len(combined_df) if not combined_df.empty else 0
    filtered_rows = len(filtered_df) if not filtered_df.empty else 0
    has_filters = (selected_categories or selected_cards or (vendor_search and vendor_search.strip()) or 
                   min_date is not None or max_date is not None)
    
    if has_filters and total_rows > 0:
        st.caption(f"📊 Showing {filtered_rows} of {total_rows} transactions (filters applied)")
    elif total_rows > 0:
        st.caption(f"📊 Showing all {total_rows} transactions")
    
    # Store filtered_df before adding empty row (for merge logic later)
    filtered_df_before_empty = filtered_df.copy()
    
    # Add empty row at the TOP for new entries
    empty_row = pd.DataFrame([{
        'Date': pd.Timestamp.now().strftime('%Y-%m-%d'),
        'Vendor': '',
        'Category': 'groceries',
        'Amount': 0.0,
        'Best Card': '',
        'Reward Rate': '',
        'Rewards': ''
    }])
    filtered_df = pd.concat([empty_row, filtered_df], ignore_index=True)
    
    # Display combined editable table
    st.write("**Edit the table below to add or remove transactions. The optimization will update automatically:**")
    
    edited_df = st.data_editor(
        filtered_df,
        column_config={
            "Date": st.column_config.TextColumn("Date (YYYY-MM-DD)", width="small"),
            "Vendor": st.column_config.TextColumn("Vendor", width="medium"),
            "Category": st.column_config.SelectboxColumn(
                "Category",
                options=["groceries", "dining", "gas", "online_shopping", "utilities", 
                        "airfare", "hotels", "subscriptions", "entertainment", "drugstores", 
                        "travel_portal", "home_improvement", "rideshare"],
                width="medium"
            ),
            "Amount": st.column_config.NumberColumn("Amount ($)", min_value=0.0, step=0.01, format="$%.2f", width="small"),
            "Best Card": st.column_config.TextColumn("Best Card", width="medium", disabled=True),
            "Reward Rate": st.column_config.TextColumn("Reward Rate", width="small", disabled=True),
            "Rewards": st.column_config.TextColumn("Rewards", width="small", disabled=True)
        },
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="optimization_table_editor"
    )
    
    # Filter out empty/invalid rows and update session state
    if not edited_df.empty:
        valid_rows = edited_df[
            (edited_df['Vendor'].astype(str).str.strip() != '') & 
            (edited_df['Amount'] > 0) & 
            (edited_df['Date'].astype(str).str.strip() != '')
        ].copy()
        
        # If filters were applied, merge edited rows with rows that were filtered out
        if has_filters and not combined_df.empty and not valid_rows.empty:
            # Use the filtered_df before empty row was added for comparison
            original_filtered = filtered_df_before_empty[filtered_df_before_empty['Vendor'].astype(str).str.strip() != ''].copy() if not filtered_df_before_empty.empty else pd.DataFrame()
            
            # Create keys for matching rows
            valid_rows['_key'] = valid_rows['Date'].astype(str) + '|' + valid_rows['Vendor'].astype(str) + '|' + valid_rows['Category'].astype(str) + '|' + valid_rows['Amount'].astype(str)
            combined_df['_key'] = combined_df['Date'].astype(str) + '|' + combined_df['Vendor'].astype(str) + '|' + combined_df['Category'].astype(str) + '|' + combined_df['Amount'].astype(str)
            
            if not original_filtered.empty:
                original_filtered['_key'] = original_filtered['Date'].astype(str) + '|' + original_filtered['Vendor'].astype(str) + '|' + original_filtered['Category'].astype(str) + '|' + original_filtered['Amount'].astype(str)
                # Get rows from combined_df that weren't in the original filtered view
                filtered_out = combined_df[~combined_df['_key'].isin(original_filtered['_key'])].copy()
            else:
                # If no rows matched the filter, all rows were filtered out
                filtered_out = combined_df.copy()
            
            # Combine edited rows with filtered-out rows
            if not filtered_out.empty:
                # Keep only editable columns from filtered_out
                filtered_out_editable = filtered_out[['Date', 'Vendor', 'Category', 'Amount']].copy()
                valid_rows_editable = valid_rows[['Date', 'Vendor', 'Category', 'Amount']].copy()
                valid_rows = pd.concat([valid_rows_editable, filtered_out_editable], ignore_index=True)
            else:
                valid_rows = valid_rows[['Date', 'Vendor', 'Category', 'Amount']].copy()
        else:
            # No filters applied, just use the edited rows
            valid_rows = valid_rows[['Date', 'Vendor', 'Category', 'Amount']].copy()
        
        # Sort by date descending before saving to session state
        if not valid_rows.empty:
            valid_rows['Date'] = pd.to_datetime(valid_rows['Date'], errors='coerce')
            valid_rows = valid_rows.sort_values('Date', ascending=False, na_position='last')
            valid_rows['Date'] = valid_rows['Date'].dt.strftime('%Y-%m-%d')
            
            # Update session state with only editable columns
            st.session_state.editable_transactions = valid_rows.to_dict('records')
            
            # Recalculate totals based on updated transactions
            total_gross_rewards = 0
            total_annual_costs = 0
            total_spend = 0
            unique_cards_used = set()
            
            for trans in st.session_state.editable_transactions:
                category = trans['Category']
                amount = float(trans['Amount'])
                options = get_all_card_options(category, amount, cc_data_for_optimization)
                if options:
                    best_option = options[0]
                    total_gross_rewards += best_option['rewards']
                    total_spend += amount
                    if best_option['card_name'] not in unique_cards_used:
                        total_annual_costs += best_option['annual_cost_numeric']
                        unique_cards_used.add(best_option['card_name'])
        else:
            st.session_state.editable_transactions = []
            total_gross_rewards = 0
            total_annual_costs = 0
            total_spend = 0
            unique_cards_used = set()
    
    if not optimization_data:
        st.info("Add transactions to the table above to see optimization results.")
   
    # --- All Available Cards (collapsible) ---
    with st.expander("All Available Cards", expanded=False):
        st.write("**Edit the table below to add, remove, or modify credit cards. Changes will affect optimization calculations.**")
        
        # Prepare cards for editing
        card_rows = []
        for card in st.session_state.editable_cards:
            # Convert multipliers dict to JSON string for editing
            multipliers = card.get("category_multipliers_x", {})
            multipliers_str = json.dumps(multipliers) if multipliers else "{}"
            
            card_rows.append({
                "Card Name": card.get("card_name", ""),
                "Annual Cost": card.get("annual_cost", "$0"),
                "Base Rate": card.get("base_rate_x", 1.0),
                "Category Multipliers (JSON)": multipliers_str,
            })
        
        cards_df = pd.DataFrame(card_rows)
        
        # Display editable table
        edited_cards_df = st.data_editor(
            cards_df,
            column_config={
                "Card Name": st.column_config.TextColumn("Card Name", width="large", required=True),
                "Annual Cost": st.column_config.TextColumn("Annual Cost", width="small", help="Format: $0, $95, $250, etc."),
                "Base Rate": st.column_config.NumberColumn("Base Rate", min_value=0.0, step=0.1, format="%.1f", width="small"),
                "Category Multipliers (JSON)": st.column_config.TextColumn(
                    "Category Multipliers (JSON)", 
                    width="large",
                    help='JSON format: {"category_name": multiplier, ...}. Example: {"grocery_stores": 6.0, "dining": 3.0}'
                ),
            },
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key="cards_editor"
        )
        
        # Update session state with edited cards
        if not edited_cards_df.empty:
            valid_cards = []
            for _, row in edited_cards_df.iterrows():
                card_name = str(row['Card Name']).strip()
                if card_name:  # Only include cards with names
                    try:
                        # Parse multipliers JSON
                        multipliers_str = str(row['Category Multipliers (JSON)']).strip()
                        if multipliers_str:
                            multipliers = json.loads(multipliers_str)
                        else:
                            multipliers = {}
                        
                        # Ensure multipliers values are floats
                        multipliers = {k: float(v) for k, v in multipliers.items()}
                        
                        valid_cards.append({
                            "card_name": card_name,
                            "annual_cost": str(row['Annual Cost']).strip(),
                            "base_rate_x": float(row['Base Rate']),
                            "category_multipliers_x": multipliers
                        })
                    except (json.JSONDecodeError, ValueError) as e:
                        st.warning(f"Error parsing card '{card_name}': {e}. Please check the JSON format.")
                        # Still add the card but with empty multipliers
                        valid_cards.append({
                            "card_name": card_name,
                            "annual_cost": str(row['Annual Cost']).strip(),
                            "base_rate_x": float(row['Base Rate']),
                            "category_multipliers_x": {}
                        })
            
            st.session_state.editable_cards = valid_cards
            # Cards updated - optimization will use updated cards on next rerun
else:
    st.warning("Credit card data not available for optimization")

# --- Future Enhancements To-Do List ---
with st.expander("📋 Future Enhancements", expanded=False):
    st.write("**Planned improvements for the credit card optimization tool:**")
    
    todo_items = [
        " Add the ability for users to select the cards that they already have",
        " Sign up for cards 1 by 1, or optimize for maximum savings",
        " Likelihood for getting approved",
        "🎁 **Intro Offers** - Include sign-up bonuses and introductory rates",
    ]
    
    for item in todo_items:
        st.write(f"• {item}")
    
    st.caption("💡 *These features will be added in future updates to enhance the optimization experience.*")
