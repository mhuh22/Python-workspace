# app.py
# Streamlit app: SQL query editor with example datasets
# --------------------------------------------------------------
# Features
# - Load example CSV files from example_datasets directory
# - Simple table browser on the right sidebar
# - Write SQL queries with DuckDB
# - Preview tables with click
# - Query history and results download
#
# Run locally:
#   pip install streamlit duckdb pandas pyarrow openpyxl
#   streamlit run app.py
# --------------------------------------------------------------

import io
import re
from typing import Dict, List
import json

import duckdb
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="SQL Query Editor", layout="wide")
st.title("🧠 SQL Query Editor")
st.caption("Write SQL queries against example datasets — powered by DuckDB.")

# --- Helpers --------------------------------------------------
SANITIZE_RE = re.compile(r"[^A-Za-z0-9_]")

def sanitize_name(name: str) -> str:
    """Turn arbitrary file/sheet names into safe SQL identifiers."""
    name = name.strip().replace(" ", "_")
    name = SANITIZE_RE.sub("_", name)
    name = re.sub(r"_+", "_", name)
    if not name or name[0].isdigit():
        name = f"t_{name}"
    return name.lower()

# --- Session state: DuckDB connection and table registry ------
if "con" not in st.session_state:
    st.session_state.con = duckdb.connect(database=":memory:")
if "tables" not in st.session_state:
    st.session_state.tables = {}  # name -> DataFrame
if "history" not in st.session_state:
    st.session_state.history = []  # list of (sql, ok, rows)
if "example_loaded" not in st.session_state:
    st.session_state.example_loaded = False
if "selected_table" not in st.session_state:
    st.session_state.selected_table = None

con: duckdb.DuckDBPyConnection = st.session_state.con

# --- Load example tables from example_datasets directory ------
def load_example_tables():
    """Load CSVs directly from GitHub raw links and register them as tables."""
    base_url = "https://raw.githubusercontent.com/mhuh22/Python-workspace/master/Personal_Projects/Code_Assistant/example_datasets/"

    files = [
        "customers.csv",
        "orders.csv",
        "products.csv",
        "sales_2023.csv",
        "sales_2024.csv"
        # add more CSVs here if you add to the repo
    ]

    for fname in files:
        try:
            url = base_url + fname
            df = pd.read_csv(url)
            tname = sanitize_name(fname.replace(".csv", ""))
            st.session_state.tables[tname] = df
            con.register(tname, df)
        except Exception as e:
            st.error(f"Could not load {fname}: {e}")


def load_sql_questions():
    """Load SQL questions directly from GitHub raw link."""
    url = "https://raw.githubusercontent.com/mhuh22/Python-workspace/master/Personal_Projects/Code_Assistant/sql_questions.json"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.sidebar.warning(f"Could not load SQL questions: {e}")
        return None

# Load examples on first run
if not st.session_state.example_loaded:
    load_example_tables()
    st.session_state.example_loaded = True

# Re-register everything (ensures persistence across reruns)
for tname, df in st.session_state.tables.items():
    try:
        con.unregister(tname)
    except Exception:
        pass
    con.register(tname, df)

# --- Sidebar: Simple table list -------------------------------
st.sidebar.header("Tables")

# Add search box
search_query = st.sidebar.text_input("🔍 Search tables", placeholder="Type to filter...", key="table_search")

if st.session_state.tables:
    # Filter tables based on search query
    filtered_tables = [
        tname for tname in sorted(st.session_state.tables.keys())
        if search_query.lower() in tname.lower()
    ]
    
    if filtered_tables:
        for tname in filtered_tables:
            if st.sidebar.button(tname, key=f"tbl_{tname}", use_container_width=True):
                st.session_state.selected_table = tname
    else:
        st.sidebar.info(f"No tables match '{search_query}'")
else:
    st.sidebar.info("No tables loaded")

# --- Main area: Query editor and results ----------------------
row_limit = 1000

# --- Practice Questions Section at Top ------------------------
questions_data = load_sql_questions()
if questions_data:
    with st.expander("💡 Practice Questions - Click to explore SQL challenges", expanded=False):
        # Count questions by difficulty
        beginner_count = len(questions_data.get("beginner", []))
        intermediate_count = len(questions_data.get("intermediate", []))
        advanced_count = len(questions_data.get("advanced", []))
        
        st.markdown(f"""
        Practice your SQL skills with **{beginner_count + intermediate_count + advanced_count} questions** across three difficulty levels:
        - 🟢 **Beginner** ({beginner_count} questions) - Basic queries, filtering, and aggregations
        - 🟡 **Intermediate** ({intermediate_count} questions) - Joins, grouping, and time-based analysis  
        - 🔴 **Advanced** ({advanced_count} questions) - Window functions, CTEs, and complex analytics
        
        Select a difficulty level below to get started.
        """)
        
        # Difficulty selection
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🟢 Beginner", use_container_width=True, key="btn_beginner"):
                st.session_state.selected_difficulty = "beginner"
        with col2:
            if st.button("🟡 Intermediate", use_container_width=True, key="btn_intermediate"):
                st.session_state.selected_difficulty = "intermediate"
        with col3:
            if st.button("🔴 Advanced", use_container_width=True, key="btn_advanced"):
                st.session_state.selected_difficulty = "advanced"
        
        # Show questions if a difficulty is selected
        if "selected_difficulty" in st.session_state:
            difficulty = st.session_state.selected_difficulty
            st.markdown("---")
            st.markdown(f"### {difficulty.capitalize()} Questions")
            
            questions = questions_data.get(difficulty, [])
            if questions:
                # Group by category
                categories = {}
                for q in questions:
                    cat = q.get("category", "Other")
                    if cat not in categories:
                        categories[cat] = []
                    categories[cat].append(q)
                
                # Display questions by category
                for category, cat_questions in categories.items():
                    st.markdown(f"**📂 {category}**")
                    for q in cat_questions:
                        col1, col2 = st.columns([4, 1])
                        with col1:
                            st.markdown(f"**Q{q['id']}:** {q['question']}")
                            st.caption(f"💾 Tables: {', '.join(q['tables'])}")
                        with col2:
                            if st.button("💡", key=f"hint_{q['id']}", use_container_width=True, help="Show hint"):
                                st.info(f"**Hint:** {q['hint']}")
                    st.markdown("---")

# --- Query editor ---------------------------------------------
st.subheader("✏️ SQL Query")

# Sample queries based on available tables
sample_query = ""
if st.session_state.tables:
    table_list = sorted(st.session_state.tables.keys())
    if "customers" in table_list and "orders" in table_list:
        sample_query = """-- Example: Join customers and orders
SELECT 
    c.name,
    c.country,
    o.product_name,
    o.quantity,
    o.unit_price * o.quantity as total_amount
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
WHERE o.status = 'delivered'
ORDER BY total_amount DESC
LIMIT 10;"""
    else:
        first_table = table_list[0]
        sample_query = f"-- Example query\nSELECT * FROM {first_table} LIMIT 10;"

sql = st.text_area("Write your SQL here", value=sample_query, height=250, key="sql_editor")

col1, col2 = st.columns([1, 5])
with col1:
    run = st.button("▶️ Run Query", type="primary", use_container_width=True)
with col2:
    if st.session_state.tables:
        st.caption(f"💡 Available tables: {', '.join(sorted(st.session_state.tables.keys()))}")

# --- Execute query --------------------------------------------
if run:
    if not st.session_state.tables:
        st.warning("No tables available. Add CSV files to the example_datasets folder.")
    else:
        try:
            # Apply row limit if user didn't specify a LIMIT
            user_sql = sql.strip().rstrip(";")
            has_limit = re.search(r"\blimit\b\s+\d+\s*$", user_sql, flags=re.I) is not None
            final_sql = user_sql if has_limit else f"{user_sql} LIMIT {row_limit}"

            res = con.execute(final_sql)
            try:
                df = res.df()
            except Exception:
                df = pd.DataFrame()

            st.success(f"✅ Query executed successfully — {len(df):,} rows returned")
            st.dataframe(df, use_container_width=True, height=400)

            # Download button
            if not df.empty:
                csv_bytes = df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "⬇️ Download Results (CSV)",
                    data=csv_bytes,
                    file_name="query_results.csv",
                    mime="text/csv",
                )

            st.session_state.history.insert(0, (final_sql, True, len(df)))
        except Exception as e:
            st.error(f"❌ SQL Error: {e}")
            st.session_state.history.insert(0, (sql, False, 0))

# --- Table Preview --------------------------------------------
if st.session_state.selected_table:
    st.divider()
    st.subheader(f"🔍 Table Preview: `{st.session_state.selected_table}`")
    
    preview_df = st.session_state.tables[st.session_state.selected_table]
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Rows", f"{len(preview_df):,}")
    with col2:
        st.metric("Columns", len(preview_df.columns))
    with col3:
        preview_rows = st.number_input("Preview rows", min_value=5, max_value=len(preview_df), value=min(100, len(preview_df)), step=25, key="preview_rows")
    with col4:
        st.write("")  # spacer
        if st.button("✖️ Close Preview"):
            st.session_state.selected_table = None
            st.rerun()
    
    st.dataframe(preview_df.head(preview_rows), use_container_width=True, height=300)
    
    # Quick actions
    col1, col2 = st.columns(2)
    with col1:
        st.code(f"SELECT * FROM {st.session_state.selected_table} LIMIT 100;", language="sql")
    with col2:
        # Download full table as CSV
        csv_bytes = preview_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download Full Table",
            data=csv_bytes,
            file_name=f"{st.session_state.selected_table}.csv",
            mime="text/csv",
            key="download_preview"
        )

# --- Query history --------------------------------------------
if st.session_state.history:
    st.divider()
    with st.expander(f"📜 Query History ({len(st.session_state.history[:10])} recent)"):
        for i, (q, ok, n) in enumerate(st.session_state.history[:10], start=1):
            status = "✅" if ok else "❌"
            st.markdown(f"**{i}. {status} {n:,} rows**")
            st.code(q, language="sql")
            if i < len(st.session_state.history[:10]):
                st.markdown("---")

# --- Footer ----------------------------------------------------
st.caption(
    "💾 All queries run in-memory with DuckDB. No data is sent to external databases. "
    "Place CSV files in the `example_datasets` folder to load them automatically."
)