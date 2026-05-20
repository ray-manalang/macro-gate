import streamlit as st

st.set_page_config(page_title="Macro Gate", page_icon="📡", layout="wide")

st.markdown("# 📡 Macro Gate")
st.markdown(
    "Use the sidebar to navigate:\n\n"
    "- **📊 Macro** — L1: 6-signal macro deployment gate; composite score 0–100; 2-year backtest\n"
    "- **🧠 Analyst** — L3: Claude fundamental analysis; score any watchlist on earnings quality, growth, balance sheet"
)
st.info(
    "Start on **📊 Macro** to get the current deployment zone, then use **🧠 Analyst** to "
    "score the fundamental quality of individual stocks on your watchlist."
)
