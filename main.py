# main.py
import streamlit as st
import ui

st.set_page_config(page_title="King of the Roost", page_icon="👑", layout="wide")

if __name__ == "__main__":
    ui.render_dashboard()