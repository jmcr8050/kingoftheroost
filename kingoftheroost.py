import streamlit as st
import pandas as pd
import numpy as np
import random
import plotly.express as px

# --- CONFIGURATION ---
st.set_page_config(page_title="King of the Roost", page_icon="👑", layout="wide")

# -- ECONOMICS --
SHED_COST = 1000            
SHED_START_COUNT = 3
BASE_INT_PRICE = 6.0        
LOCAL_PRICE = 4.0           
OPEX_PER_CHICKEN = 3.0      
BASE_PROD = 100
REGULATORY_FINE = 500.0     
FINE_CHANCE_SCALER = 2.0    

# -- ASSETS --
CARDS_DB = [
    {"name": "Master Breeder", "type": "Emp", "cost": 600, "prod_bonus": 20, "desc": "+20 Chickens/Shed", "icon": "👨‍🌾"},
    {"name": "Savvy Salesperson", "type": "Emp", "cost": 800, "price_bonus": 1.0, "desc": "+$1.00 Price/Chicken", "icon": "👩‍💼"},
    {"name": "Hatchery", "type": "Infra", "cost": 1000, "prod_bonus": 30, "desc": "+30 Chickens/Shed", "icon": "🏭"},
    {"name": "Adv. Biosecurity", "type": "Infra", "cost": 500, "flu_immune": True, "desc": "Immune to Bird Flu", "icon": "🛡️"},
    {"name": "Auto Feeder", "type": "Infra", "cost": 400, "opex_save": 0.1, "desc": "Reduces OpEx 10%", "icon": "🤖"},
    {"name": "Export Specialist", "type": "Emp", "cost": 500, "risk_mitigation": True, "desc": "Halves impact of Bad Events", "icon": "🚢"},
]

EVENTS = {
    "Normal": {"prob": 0.4, "price_mod": 0, "bad": False, "desc": "Market is stable."},
    "H5N1 Avian Flu": {"prob": 0.1, "price_mod": 0, "bad": True, "desc": "INTL MARKET WIPEOUT! (Vol = 0) 🦠"},
    "Chicken Frenzy": {"prob": 0.1, "price_mod": 2.5, "bad": False, "desc": "Demand is high! Price +$2.50 🔥"},
    "Trade Embargo": {"prob": 0.1, "price_mod": -2.0, "bad": True, "desc": "Exports blocked. Price -$2.00 🛑"},
    "Global Shortage": {"prob": 0.1, "price_mod": 1.5, "bad": False, "desc": "Supply chain issues. Price +$1.50 🚢"},
    "Fearmongering": {"prob": 0.1, "price_mod": -3.0, "bad": True, "desc": "Bad press. Price -$3.00 (Loss Territory) 📉"},
}

# --- CLASSES ---
class Farm:
    def __init__(self, name, sheds, cash, risk_profile, is_player=False):
        self.name = name
        self.sheds = sheds
        self.cash = cash
        self.risk_profile = risk_profile
        self.is_player = is_player
        self.cards = []
        self.bankrupt = False
        self.spent_last_turn = 0
        self.valuation = 0.0
        self.avg_ebitda = 0.0 
        self.last_turn_log = {}
        self.spent_last_turn = 0.0 # Track spending for Intel mechanic

    def update_valuation(self):
        asset_val = (self.sheds * SHED_COST) + sum(c['cost'] for c in self.cards)
        liquidation_value = self.cash + asset_val
        
        estimated_base_ebitda = self.sheds * 100 * 1.0 
        used_ebitda = max(estimated_base_ebitda, self.avg_ebitda)
        earnings_value = self.cash + (used_ebitda * 5.0)
        
        self.valuation = max(liquidation_value, earnings_value)

    def add_card(self, card):
        self.cards.append(card)
        if len(self.cards) > 4:
            self.cards.sort(key=lambda x: x['cost'], reverse=True)
            self.cards = self.cards[:4]

# --- SESSION STATE ---
if 'game_active' not in st.session_state: st.session_state.game_active = False
if 'game_over_msg' not in st.session_state: st.session_state.game_over_msg = ""
if 'pending_card' not in st.session_state: st.session_state.pending_card = None 
if 'next_event_name' not in st.session_state: st.session_state.next_event_name = "Normal" # Pre-generated event

def get_random_event():
    return random.choices(list(EVENTS.keys()), weights=[0.4, 0.1, 0.1, 0.1, 0.1, 0.2], k=1)[0]

def init_game():
    st.session_state.game_active = True
    st.session_state.season = 1
    st.session_state.market_cards = random.sample(CARDS_DB, 4)
    st.session_state.game_over_msg = ""
    st.session_state.pending_card = None
    st.session_state.next_event_name = get_random_event() # Pre-generate Season 1 event
    
    st.session_state.player = Farm("You", SHED_START_COUNT, 2000.0, 1.0, is_player=True)
    st.session_state.player.update_valuation() 
    
    st.session_state.opponents = [
        Farm("Small Fry", 3, 2000.0, 1.0),
        Farm("The Upstart", 4, 3000.0, 1.1),
        Farm("THE TYCOON", 6, 8000.0, 1.2)
    ]
    st.session_state.opponents[2].add_card(CARDS_DB[2]) 
    
    for ai in st.session_state.opponents:
        ai.update_valuation() 
    
    st.session_state.history = pd.DataFrame(columns=["Season", "PlayerCash", "TycoonCash"])

# --- GAME ENGINE ---
def execute_turn(capacity_pct, split_pct, construction_requested):
    player = st.session_state.player
    opponents = st.session_state.opponents
    
    # Reset spending trackers
    player.spent_last_turn = 0
    for ai in opponents: ai.spent_last_turn = 0
    
    # 1. Player Construction
    if construction_requested and player.cash >= SHED_COST:
        player.cash -= SHED_COST
        player.sheds += 1
        player.spent_last_turn += SHED_COST
        
    # 2. Player Purchase
    purchased_idx = st.session_state.pending_card
    if purchased_idx is not None:
        card = st.session_state.market_cards[purchased_idx]
        if card and player.cash >= card['cost']:
            player.cash -= card['cost']
            player.add_card(card)
            player.spent_last_turn += card['cost']
            st.session_state.market_cards[purchased_idx] = None 
    
    st.session_state.pending_card = None 

    # 3. AI Actions
    for ai in opponents:
        if ai.bankrupt: continue
        
        # AI Builds Shed
        if ai.cash > (SHED_COST * 2.0):
            ai.cash -= SHED_COST
            ai.sheds += 1
            ai.spent_last_turn += SHED_COST
            
        # AI Scans Market
        best_idx = -1
        highest_cost = -1
        for i, card in enumerate(st.session_state.market_cards):
            if card and ai.cash > (card['cost'] * 1.5): 
                if card['cost'] > highest_cost:
                    highest_cost = card['cost']
                    best_idx = i
        
        if best_idx != -1:
            card = st.session_state.market_cards[best_idx]
            ai.cash -= card['cost']
            ai.add_card(card)
            ai.spent_last_turn += card['cost']
            st.session_state.market_cards[best_idx] = None 
                
    # 4. Use Pre-Generated Event
    evt_name = st.session_state.next_event_name
    evt_data = EVENTS[evt_name]
    
    # 5. Production & Sales
    all_farms = [player] + opponents
    for farm in all_farms:
        if farm.bankrupt: continue
        
        cap = capacity_pct if farm.is_player else farm.risk_profile
        splt = split_pct if farm.is_player else 0.5 
        
        prod_bonus = sum(c.get('prod_bonus', 0) for c in farm.cards)
        price_bonus = sum(c.get('price_bonus', 0) for c in farm.cards)
        flu_immune = any(c.get('flu_immune', False) for c in farm.cards)
        risk_mit = any(c.get('risk_mitigation', False) for c in farm.cards)
        opex_saver = any(c.get('opex_save', 0) > 0 for c in farm.cards)
        
        raw_prod = farm.sheds * (BASE_PROD + prod_bonus) * cap
        
        fine = 0.0
        if cap > 1.0:
            chance = (cap - 1.0) * FINE_CHANCE_SCALER
            if random.random() < chance:
                fine = REGULATORY_FINE
                
        base_mod = evt_data['price_mod']
        if risk_mit and evt_data['bad']: base_mod /= 2
        
        int_price = max(0.5, BASE_INT_PRICE + base_mod + price_bonus)
        
        vol_local = raw_prod * (1 - splt)
        vol_int = raw_prod * splt
        
        if evt_name == "H5N1 Avian Flu" and not flu_immune:
            vol_int = 0 
            
        revenue = (vol_local * LOCAL_PRICE) + (vol_int * int_price)
        
        rate = OPEX_PER_CHICKEN * 0.9 if opex_saver else OPEX_PER_CHICKEN
        opex = raw_prod * rate
        
        profit = revenue - opex - fine
        farm.cash += profit
        
        if farm.avg_ebitda == 0: farm.avg_ebitda = profit
        else: farm.avg_ebitda = (farm.avg_ebitda * 0.7) + (profit * 0.3)
        
        farm.last_turn_log = {
            "Rev": revenue, "OpEx": opex, "Fine": fine, "Profit": profit, 
            "Price_Int": int_price,
            "Event_Name": evt_name,
            "Event_Desc": evt_data['desc'],
            "Event_Bad": evt_data['bad']
        }
        
        farm.update_valuation()
        if farm.cash < 0: farm.bankrupt = True

    # 6. Market Refill
    for i in range(4):
        if st.session_state.market_cards[i] is None:
            st.session_state.market_cards[i] = random.choice(CARDS_DB)

    # 7. Cleanup & Prep NEXT Turn
    st.session_state.season += 1
    st.session_state.next_event_name = get_random_event() # GENERATE NEXT SEASON'S EVENT NOW
    
    tycoon = opponents[2]
    new_hist = {"Season": st.session_state.season-1, "PlayerCash": player.cash, "TycoonCash": tycoon.cash}
    st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([new_hist])], ignore_index=True)

    if st.session_state.season > 40:
        if not opponents[2].bankrupt: 
            st.session_state.game_active = False
            st.session_state.game_over_msg = "GAME OVER: You failed to eliminate the Tycoon by Season 40."

def attempt_buyout(ai_index):
    player = st.session_state.player
    target = st.session_state.opponents[ai_index]
    cost = target.valuation * 1.3 
    if player.cash >= cost:
        player.cash -= cost
        player.sheds += target.sheds
        for c in target.cards: player.add_card(c)
        target.bankrupt = True
        target.name = f"Owned by {player.name}"
        target.sheds = 0
        target.cash = 0
        st.success(f"Acquisition Successful! You bought {target.name}")
        st.rerun()

def select_card(idx):
    if st.session_state.pending_card == idx:
        st.session_state.pending_card = None
    else:
        st.session_state.pending_card = idx

# --- UI RENDERER ---
def main():
    if not st.session_state.game_active:
        st.title("👑 King of the Roost")
        st.caption("A High-Stakes Agricultural M&A Simulator")
        st.markdown("---")
        
        col1, col2 = st.columns([1.3, 1])
        with col1:
            st.subheader("The Situation")
            st.markdown("""
            You are a small-time operator in a cutthroat poultry market. 
            **The Tycoon** dominates the region with deep pockets.
            
            But you have a secret: **Apex Global Foods** is entering the market in exactly **40 Seasons** (10 Years). 
            They are looking to acquire the regional monopoly and will write **one check** to the last player standing.
            
            **OBJECTIVE:** Bankrupt or Acquire all 3 competitors (especially The Tycoon) before Season 40.
            """)
            st.info("### Executive Summary (Rules)")
            st.markdown(f"""
            **1. The Economy**
            * **Safe:** Local Market (${LOCAL_PRICE:.2f}). Low Margin.
            * **Risky:** Intl Market (${BASE_INT_PRICE:.2f} base). Can crash to $0.
            
            **2. Market Intel (The Secret Mechanic)**
            * If you spend **LESS** money than the Tycoon in a turn, you gain **Insider Intel** for the next season.
            * You will see the Event Forecast *before* you choose your strategy.
            
            **3. Mergers & Acquisitions**
            * Organic growth is slow (Sheds cost ${SHED_COST:,.0f}).
            * Win by **Acquiring** rivals at a 30% premium.
            """)
            if st.session_state.game_over_msg:
                st.error(st.session_state.game_over_msg)
            if st.button("Start 10-Year Campaign", type="primary"):
                init_game()
                st.rerun()

        with col2:
            st.warning("### Unit Economics (2025 Update)")
            st.markdown(f"""
            * **Shed Cost:** ${SHED_COST:,.0f}
            * **OpEx:** ${OPEX_PER_CHICKEN:.2f} per bird
            * **Overclocking:** 120% Prod = 40% Fine Risk.
            """)
        return

    # --- MAIN DASHBOARD ---
    player = st.session_state.player
    tycoon = st.session_state.opponents[2]
    
    st.markdown(f"### Season {st.session_state.season} / 40")
    
    # METRICS
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Your Cash", f"${player.cash:,.0f}", delta=f"${player.last_turn_log.get('Profit', 0):,.0f}")
    m2.metric("Sheds", f"{player.sheds}", delta_color="off")
    m3.metric("Valuation", f"${player.valuation:,.0f}")
    m4.metric("Tycoon Status", "ALIVE" if not tycoon.bankrupt else "ELIMINATED", 
              delta=f"${tycoon.valuation:,.0f}", delta_color="inverse")
    
    st.markdown("---")

    # INTELLIGENCE REPORT (NEW!)
    # Logic: Did Player spend less than Tycoon last turn?
    # Season 1 exception: No history, so no intel.
    has_intel = (st.session_state.season > 1) and (player.spent_last_turn < tycoon.spent_last_turn)
    
    if has_intel:
        next_evt = st.session_state.next_event_name
        is_bad = EVENTS[next_evt]['bad']
        box_color = "red" if is_bad else "green"
        with st.container():
            st.info(f"🕵️ **INSIDER INTEL:** Sources forecast **{next_evt}** next season.")
    
    # M&A TARGETS
    st.caption("COMPETITION")
    o1, o2, o3 = st.columns(3)
    for i, ai in enumerate(st.session_state.opponents):
        with [o1, o2, o3][i]:
            buyout_cost = ai.valuation * 1.3
            status = "red" if ai.bankrupt else "green"
            st.markdown(f"**{ai.name}** :{status}[●]")
            if not ai.bankrupt:
                st.write(f"Sheds: {ai.sheds} | Cash: ${ai.cash:,.0f}")
                if st.button(f"ACQUIRE (${buyout_cost:,.0f})", key=f"buy_{i}", disabled=(player.cash < buyout_cost)):
                    attempt_buyout(i)
            else:
                st.caption("ACQUIRED")

    st.markdown("---")

    # OPERATIONS & MARKET
    c_strat, c_market = st.columns([1, 2])
    
    with c_strat:
        st.subheader("🛠️ Ops")
        can_build = player.cash >= SHED_COST
        build_btn = st.checkbox(f"Build New Shed (${SHED_COST})", disabled=not can_build)
        
        st.write("**Production Intensity (%)**")
        # FIXED: Slider is now 100 to 120 (Integer)
        capacity_int = st.slider("Cap", 100, 120, 100, label_visibility="collapsed")
        capacity = capacity_int / 100.0
        
        if capacity_int == 100:
            st.caption("✅ Safe Mode")
        else:
            risk = int((capacity - 1.0) * FINE_CHANCE_SCALER * 100)
            st.warning(f"🔥 **OVERCLOCKED!** +{capacity_int-100}% Rev | ⚠️ {risk}% Fine Risk")

        st.write("**Export Allocation (%)**")
        # FIXED: Slider is now 0 to 100 (Integer)
        split_int = st.slider("Split", 0, 100, 50, label_visibility="collapsed")
        split = split_int / 100.0
        st.caption(f"Local: {100-split_int}% | Intl: {split_int}%")

    with c_market:
        st.subheader("🛒 Upgrade Market")
        mc1, mc2, mc3, mc4 = st.columns(4)
        
        for i, card in enumerate(st.session_state.market_cards):
            col = [mc1, mc2, mc3, mc4][i]
            if card is None:
                col.info("SOLD")
            else:
                is_selected = (st.session_state.pending_card == i)
                if is_selected: col.markdown(f"**:red[SELECTED]**")
                
                col.write(f"**{card['icon']} {card['name']}**")
                col.caption(f"{card['desc']}")
                col.write(f"**${card['cost']}**")
                
                disable_btn = (st.session_state.pending_card is not None and not is_selected) or (player.cash < card['cost'])
                label = "DESELECT" if is_selected else "BUY"
                if col.button(label, key=f"card_{i}", disabled=disable_btn):
                    select_card(i)
                    st.rerun()

    st.markdown("###")
    if st.button("🚀 END SEASON & RUN PRODUCTION", type="primary", use_container_width=True):
        execute_turn(capacity, split, build_btn)
        st.rerun()

    # REPORTING
    if st.session_state.season > 1:
        st.markdown("---")
        st.subheader("📋 Quarterly Report (Last Season)")
        
        log = player.last_turn_log
        
        # Market Context
        evt_label = f"**Event:** {log['Event_Name']} - {log['Event_Desc']}"
        if log['Event_Bad']:
            st.error(evt_label)
        else:
            st.success(evt_label)
            
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Rev", f"${log['Rev']:,.0f}")
        r2.metric("OpEx", f"-${log['OpEx']:,.0f}")
        r3.metric("Profit", f"${log['Profit']:,.0f}", delta_color="normal" if log['Profit']>0 else "inverse")
        r4.info(f"Intl Price: **${log['Price_Int']:.2f}**")
        
        st.write("**Active Cards:**")
        if not player.cards: st.caption("None")
        cols = st.columns(4)
        for i, c in enumerate(player.cards):
            cols[i % 4].success(f"{c['icon']} {c['name']}")

    if len(st.session_state.history) > 1:
        fig = px.line(st.session_state.history, x="Season", y=["PlayerCash", "TycoonCash"], 
                      color_discrete_map={"PlayerCash": "green", "TycoonCash": "red"})
        st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()