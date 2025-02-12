# To load, open terminal
# streamlit run flights.py

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

st.title('Flights')

def load_data(nrows):
    data = pd.read_csv('itineraries.csv', nrows=10000)
    lowercase = lambda x: str(x).lower()
    data.rename(lowercase, axis='columns', inplace=True)
    return data

data = load_data(10000)

if st.checkbox('Show raw data'):
    st.subheader('Raw data')
    st.write(data)

# Draw histogram
st.subheader('Number of flights by airport')
hist_values = np.histogram(
    data['startingairport'], bins=24, range=(0,24))[0]
st.bar_chart(hist_values)

plt.figure(figsize=(10, 6))
plt.hist(data['startingairport'], bins=20, edgecolor='k', alpha=0.7)
plt.xlabel('Starting Airport')
plt.ylabel('Frequency')
plt.title('Histogram of Starting Airport')
st.pyplot(plt.gcf())

fig = pd.histogram(data, x='startingairport', title='Histogram of Starting Airport', nbins=20)
st.plotly_chart(fig)