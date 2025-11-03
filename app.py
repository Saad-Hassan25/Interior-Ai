import streamlit as st
import pandas as pd

# --- Title and description ---
st.title("🚀 My Streamlit App")
st.write("This app is based on my Jupyter notebook logic!")

# --- Inputs ---
user_input = st.text_input("Enter something:")

# --- Processing ---
if st.button("Run"):
    result = f"Processed result: {user_input.upper()}"
    st.success(result)

# --- Display output ---
st.write("Done ✅")
