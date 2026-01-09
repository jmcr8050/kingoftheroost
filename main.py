# main.py
import streamlit as st
import ui
import engine
import config

st.set_page_config(page_title="King of the Roost", page_icon="👑", layout="wide")

# --- INITIALIZE SESSION STATE ---
if 'game_state' not in st.session_state:
    st.session_state.game_state = "WELCOME" # WELCOME, PLAYING, GAME_OVER

if 'ceo_profile' not in st.session_state:
    st.session_state.ceo_profile = None

if 'game_over_msg' not in st.session_state:
    st.session_state.game_over_msg = ""

def start_game(profile_id):
    st.session_state.ceo_profile = profile_id
    engine.init_game(profile_id)
    st.session_state.game_state = "PLAYING"
    st.rerun()

# --- RENDER LOGIC ---
if st.session_state.game_state == "WELCOME":
    st.title("King of the Roost 👑")
    st.markdown("### Select your CEO Archetype")
    
    # ROW 1: The Basics (3 Cols)
    c1, c2, c3 = st.columns(3)
    
    with c1:
        with st.container(border=True):
            st.subheader("The Founder")
            st.caption("Standard Start-up")
            st.markdown("You are starting from scratch with a clean balance sheet. No baggage.")
            st.divider()
            st.markdown("💰 **$2,500 Cash**")
            st.markdown("🏦 **$0 Debt**")
            st.markdown("🏰 **3 Sheds**")
            st.divider()
            st.markdown("✨ **Edge:** Flexibility")
            st.markdown("🛑 **Drag:** None")
            if st.button("Select Founder", use_container_width=True): start_game("founder")

    with c2:
        with st.container(border=True):
            st.subheader("The Raider")
            st.caption("Private Equity Shark")
            st.markdown("Wall Street roll-up vehicle. Massive buying power, bleeding interest.")
            st.divider()
            st.markdown("💰 **$6,000 Cash**")
            st.markdown("🏦 **$3,500 Debt**")
            st.markdown("🏰 **3 Sheds**")
            st.divider()
            st.markdown("✨ **Edge:** Dry Powder (M&A)")
            st.markdown("🛑 **Drag:** Debt Service ($175/turn)")
            if st.button("Select Raider", use_container_width=True): start_game("shark")

    with c3:
        with st.container(border=True):
            st.subheader("The Farmer")
            st.caption("4th Generation")
            st.markdown("Asset rich, cash poor. Massive capacity but a liquidity crisis waiting to happen.")
            st.divider()
            st.markdown("💰 **$200 Cash**")
            st.markdown("🏦 **$1,500 Debt**")
            st.markdown("🏰 **5 Sheds + Breeder Card**")
            st.divider()
            st.markdown("✨ **Edge:** Scale (450 birds/turn)")
            st.markdown("🛑 **Drag:** Insolvency Risk")
            if st.button("Select Farmer", use_container_width=True): start_game("farmer")

    # ROW 2: The Specialists (2 Cols)
    c4, c5 = st.columns(2)
    
    with c4:
        with st.container(border=True):
            st.subheader("The Disruptor")
            st.caption("Silicon Valley Tech")
            st.markdown("Bio-protein platform. Amazing margins, but hardware is overpriced.")
            st.divider()
            st.markdown("💰 **$1,000 Cash**")
            st.markdown("⚡ **Solar + Efficiency Cards**")
            st.markdown("🏰 **3 Sheds**")
            st.divider()
            st.markdown("✨ **Edge:** Gross Margin (Low OpEx)")
            st.markdown("🛑 **Drag:** Build Cost $1,500 (+50%)")
            if st.button("Select Disruptor", use_container_width=True): start_game("tech")

    with c5:
        with st.container(border=True):
            st.subheader("The Insider")
            st.caption("Ex-Regulator")
            st.markdown("You know how the market moves, but the SEC is watching you closely.")
            st.divider()
            st.markdown("💰 **$1,500 Cash**")
            st.markdown("🔮 **The Quant (Junior Level)**")
            st.markdown("🏰 **3 Sheds**")
            st.divider()
            st.markdown("✨ **Edge:** Alpha (Forecasts)")
            st.markdown("🛑 **Drag:** Fines Doubled ($1,200)")
            if st.button("Select Insider", use_container_width=True): start_game("insider")

elif st.session_state.game_state == "PLAYING":
    ui.render_dashboard()