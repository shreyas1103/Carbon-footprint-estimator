import streamlit as st

st.set_page_config(
    page_title="Carbon Footprint Estimator",
    page_icon="🌱",
    layout="wide"
)

st.title("🌱 Carbon Footprint Estimator")

st.write(
    "Upload your transaction CSV to estimate your carbon footprint."
)

st.info("Go to the Upload page from the sidebar to get started.")
