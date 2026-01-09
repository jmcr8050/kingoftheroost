# main.py
import streamlit as st
import ui

st.set_page_config(page_title="King of the Roost", page_icon="👑", layout="wide")

# --- INITIALIZE SESSION STATE ---
# We must set these defaults before the UI tries to read them
if 'game_active' not in st.session_state:
    st.session_state.game_active = False

if 'game_over_msg' not in st.session_state:
    st.session_state.game_over_msg = ""

if __name__ == "__main__":
    ui.render_dashboard()