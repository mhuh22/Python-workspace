import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from io import BytesIO

# App title
st.title('Portfolio Projection Comparison')

# Create columns for side-by-side input
col1, col2 = st.columns(2)

# User inputs for Portfolio 1
with col1:
    st.header("Portfolio 1")
    initial_investment1 = st.number_input("Initial Investment ($)", min_value=0, value=10000, step=1000, key="initial_investment1")
    annual_return1 = st.number_input("Annual Return Rate (%)", min_value=0.0, value=7.0, step=0.1, key="annual_return1") / 100
    annual_contribution1 = st.number_input("Annual Contribution ($)", min_value=0, value=5000, step=500, key="annual_contribution1")

# User inputs for Portfolio 2
with col2:
    st.header("Portfolio 2")
    initial_investment2 = st.number_input("Initial Investment ($)", min_value=0, value=10000, step=1000, key="initial_investment2")
    annual_return2 = st.number_input("Annual Return Rate (%)", min_value=0.0, value=5.0, step=0.1, key="annual_return2") / 100
    annual_contribution2 = st.number_input("Annual Contribution ($)", min_value=0, value=5000, step=500, key="annual_contribution2")

# Input for number of years
years = st.number_input("Number of Years", min_value=1, value=30, step=1, key="years")

# Compute portfolio projection for both portfolios
years_range = np.arange(0, years + 1)
portfolio_values1 = []
portfolio_values2 = []
performance_diff = []
current_value1 = initial_investment1
current_value2 = initial_investment2

for year in years_range:
    if year > 0:
        current_value1 = current_value1 * (1 + annual_return1) + annual_contribution1
        current_value2 = current_value2 * (1 + annual_return2) + annual_contribution2
    portfolio_values1.append(round(current_value1))  # Round the total portfolio value to nearest dollar
    portfolio_values2.append(round(current_value2))  # Round the total portfolio value to nearest dollar
    
    # Calculate the difference (Portfolio 1 - Portfolio 2) and format it with +/- and commas
    diff = current_value1 - current_value2
    performance_diff.append({
        'Year': year,
        'Portfolio 1 Value': f"${round(current_value1):,}",
        'Portfolio 2 Value': f"${round(current_value2):,}",
        'Difference': f"{'+' if diff >= 0 else '-'}${abs(round(diff)):,.0f}"
    })

# Create Plotly figure with no performance difference in hover
fig = go.Figure()

# Portfolio 1 trace
fig.add_trace(go.Scatter(x=years_range, y=portfolio_values1, mode='lines+markers', name="Portfolio 1", 
                         marker=dict(symbol='circle'),
                         hovertemplate='Year: %{x}<br>Portfolio 1: $%{y:,.0f}<extra></extra>'))

# Portfolio 2 trace
fig.add_trace(go.Scatter(x=years_range, y=portfolio_values2, mode='lines+markers', name="Portfolio 2", 
                         marker=dict(symbol='square'),
                         hovertemplate='Year: %{x}<br>Portfolio 2: $%{y:,.0f}<extra></extra>'))

fig.update_layout(
    title="Portfolio Growth Comparison",
    xaxis_title="Year",
    yaxis_title="Portfolio Value ($)",
    legend_title="Portfolios",
    template="plotly_dark"
)

# Display chart
st.plotly_chart(fig)

# Display the performance difference table below the chart
st.subheader("Performance Comparison Table")
performance_df = pd.DataFrame(performance_diff).reset_index(drop=True)
st.table(performance_df)

# Export options (CSV and Excel)
st.subheader("Download Data")
csv = performance_df.to_csv(index=False)

# Create an in-memory buffer to save the Excel file
excel_buffer = BytesIO()
performance_df.to_excel(excel_buffer, index=False, engine="openpyxl")
excel_buffer.seek(0)  # Rewind the buffer to the beginning

# Buttons for downloading
col1, col2 = st.columns(2)
with col1:
    st.download_button(label="Download as CSV", data=csv, file_name="portfolio_comparison.csv", mime="text/csv")
with col2:
    st.download_button(label="Download as Excel", data=excel_buffer, file_name="portfolio_comparison.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
