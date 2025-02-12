import streamlit as st
import numpy as np
import pandas as pd
import time

# -------------------------------------------------------
# st.write("Here's our first attempt at using data to create a table:")

# st.write(pd.DataFrame({
# 'first column': [1,2,3,4],
# 'second column':[10,20,30,40]
# }))
# -------------------------------------------------------

# 1st example of generating tables
# # Build a 10x20 table with random numbers
# dataframe = np.random.randn(10,20)
# st.dataframe(dataframe)

# 2nd example of generating tables - includes randomly highlighted cells
# dataframe = pd.DataFrame(
#     np.random.randn(10, 20),
#     columns=('col %d' % i for i in range(20)))

# st.dataframe(dataframe.style.highlight_max(axis=0))

# -------------------------------------------------------

# # Creates a chart x-axis 0-20, y-axis -1.5-1.5, 3 categories
# chart_data = pd.DataFrame(
#     np.random.randn(20,3),
#     columns = ['a','b','c'])
# st.line_chart(chart_data)

# -------------------------------------------------------

# # Plot random points on top of San Francisco
# map_data = pd.DataFrame(
#     np.random.randn(1000,2) / [50,50] + [37.76, -122.4],
#     columns = ['lat','lon'])
# st.map(map_data)

# -------------------------------------------------------
# # Widgets

# # Creates a slider [0-100 by default] and returns the squared value
# x = st.slider('x')
# st.write(x, 'squared is ', x*x)

# -------------------------------------------------------

# st.text_input("Your name", key="name")
# # You can access the value at any point with: 
# st.session_state.name

# -------------------------------------------------------

# # Hide by default, show dataframe if clicked
# if st.checkbox("Show dataframe"):
#     chart_data = pd.DataFrame(
#         np.random.randn(20,3),
#         columns = ['a','b','c'])

#     chart_data

# -------------------------------------------------------

# # Checkbox for options
# df = pd.DataFrame({
#     'first column': [1, 2, 3, 4],
#     'second column': [10, 20, 30, 40]
#     })

# option = st.selectbox(
#     'Which number do you like best?',
#      df['first column'])

# 'You selected: ', option

# -------------------------------------------------------
# # Layout

# # Add a selectbox to the sidebar:
# add_selectbox = st.sidebar.selectbox(
#     'How would you like to be contacted?',
#     ('Email', 'Home phone', 'Mobile phone'))

# # Add a slider to the sidebar:
# # Range from 0-100, default is 25-75
# add_slider = st.sidebar.slider(
#     'Select a range of values',
#     0.0, 100.0, (25.0, 75.0))
# ------------------------------

# left_column, right_column = st.columns(2)
# # You can use a column just like st.sidebar:
# left_column.button('Press me!')

# # Or even better, call Streamlit functions inside a "with" block:
# with right_column:
#     chosen = st.radio(
#         'Sorting hat',
#         ("Gryffindor", "Ravenclaw", "Hufflepuff", "Slytherin"))
#     st.write(f"You are in {chosen} house!")

# -------------------------------------------------------
# # # Progress

# 'Starting a long computation...'

# # Add a placeholder
# latest_iteration = st.empty()
# bar = st.progress(0)

# for i in range(100):
#   # Update the progress bar with each iteration.
#   latest_iteration.text(f'Iteration {i+1}')
#   bar.progress(i + 1)
#   time.sleep(0.1)

# '...and now we\'re done!'