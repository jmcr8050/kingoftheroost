import streamlit as st
import pandas as pd
import numpy as np
import random
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURATION ---
st.set_page_config(page_title="King of the Roost", page_icon="👑", layout="wide")

# -- ECONOMICS --
SHED_COST = 1000
SHED_START_COUNT = 3
BASE_PROD = 100
STORAGE_COST_PER_UNIT = 0.20
REGULATORY_FINE = 500.0
FINE_CHANCE_SCALER = 2.0

# -- MARKET CONSTANTS --
BASE_DEMAND = 2000.0
DEMAND_ELASTICITY = 1.0

# -- ASSETS --
CARDS_DB = [
    {"name": "Master Breeder", "type": "Emp", "cost": 600, "prod_bonus": 20, "desc": "+20 Chickens/Shed", "icon": "👨‍🌾"},
    {"name": "Efficiency Expert", "type": "Emp", "cost": 800, "opex_save": 0.5, "desc": "-$0.50 OpEx/Bird", "icon": "📉"},
    {"name": "Hatchery", "type": "Infra", "cost": 1000, "prod_bonus": 30, "desc": "+30 Chickens/Shed", "icon": "🏭"},
    {"name": "Solar Grid", "type": "Infra", "cost": 1200, "opex_save": 0.5, "desc": "-$0.50 OpEx/Bird", "icon": "☀️"},
    {"name": "Industrial Freezer", "type": "Infra", "cost": 500, "storage_save": True, "desc": "Halves Storage Costs", "icon": "❄️"},
]

EVENTS = {
    "Normal": {"prob": 0.4, "demand_mod": 1.0, "bad": False, "desc": "Stable demand."},
    "Protein Craze": {"prob": 0.1, "demand_mod": 1.4, "bad": False, "desc": "Demand SKYROCKETS! (+40%) 🔥"},
    "Recession": {"prob": 0.1, "demand_mod": 0.7, "bad": True, "desc": "Consumers cutting back. Demand -30% 📉"},
    "Export Deal": {"prob": 0.1, "demand_mod": 1.2, "bad": False, "desc": "New trade route opened. Demand +20% 🚢"},
    "Health Scare": {"prob": 0.1, "demand_mod": 0.6, "bad": True, "desc": "Chicken fearful. Demand -40% 🦠"},
}

# --- CLASSES ---
class Farm:
    def __init__(self, name, sheds, cash, personality="Normal", is_player=False):
        self.name = name
        self.sheds = sheds
        self.cash = cash
        self.is_player = is_player
        self.personality = personality 
        
        # State
        self.cards = []
        self.bankrupt = False
        self.valuation = 0.0
        self.avg_ebitda = 0.0
        self.spent_last_turn = 0.0
        self.inventory = 0.0
        self.breakeven_price = 3.50 
        self.last_turn_log = {}

    def recalculate_breakeven(self):
        cost = 3.50
        for c in self.cards:
            cost -= c.get('opex_save', 0)
        self.breakeven_price = max(0.5, cost)

    def update_valuation(self):
        asset_val = (self.sheds * SHED_COST) + sum(c['cost'] for c in self.cards) + (self.inventory * 2.0)
        liquidation_value = self.cash + asset_val
        
        estimated_base_ebitda = self.sheds * 100 * 1.0 
        used_ebitda = max(estimated_base_ebitda, self.avg_ebitda)
        earnings_value = self.cash + (used_ebitda * 5.0)
        
        self.valuation = max(liquidation_value, earnings_value)

    def add_card(self, card):
        # AI Logic: Discard cheapest if full
        if len(self.cards) >= 4:
            self.cards.sort(key=lambda x: x['cost'])
            self.cards.pop(0) 
        self.cards.append(card)
        self.recalculate_breakeven()
    
    def scrap_card(self, index):
        if 0 <= index < len(self.cards):
            self.cards.pop(index)
            self.recalculate_breakeven()

# --- AI LOGIC BRAIN ---
def get_ai_decision(ai: Farm, player: Farm, market_cards):
    variance = random.uniform(0.9, 1.1) 
    wants_to_build = False
    card_idx = None
    capacity = 1.0
    sell_pct = 1.0 
    
    if ai.personality == "Conservative":
        if ai.cash > (SHED_COST * 2.5 * variance): wants_to_build = True
        
    elif ai.personality == "Aggressive":
        if ai.cash > (SHED_COST * 1.2 * variance): wants_to_build = True
        if random.random() < 0.3: capacity = 1.1

    elif ai.personality == "Predatory":
        is_player_weak = (player.cash < 1500) or (player.cash < (ai.cash * 0.2))
        
        if is_player_weak and ai.cash > 2000:
            capacity = 1.2 
            sell_pct = 1.0 
            wants_to_build = False 
        else:
            if ai.cash > (SHED_COST * 2.0 * variance): wants_to_build = True
            has_freezer = any(c['name'] == "Industrial Freezer" for c in ai.cards)
            if has_freezer and random.random() < 0.3:
                sell_pct = 0.5 

    best_card_idx = -1
    highest_cost = -1
    for i, card in enumerate(market_cards):
        threshold = 1.3 if ai.personality != "Predatory" else 1.1
        if card and ai.cash > (card['cost'] * threshold * variance):
            if card['cost'] > highest_cost:
                highest_cost = card['cost']
                best_card_idx = i
    
    if best_card_idx != -1:
        card_idx = best_card_idx

    return wants_to_build, card_idx, capacity, sell_pct


# --- SESSION STATE ---
if 'game_active' not in st.session_state: st.session_state.game_active = False
if 'game_over_msg' not in st.session_state: st.session_state.game_over_msg = ""
if 'pending_card' not in st.session_state: st.session_state.pending_card = None 
if 'next_event_name' not in st.session_state: st.session_state.next_event_name = "Normal"
if 'show_summary' not in st.session_state: st.session_state.show_summary = False
# New: Track total supply for forecasting
if 'last_total_supply' not in st.session_state: st.session_state.last_total_supply = 500 

def get_random_event():
    return random.choices(list(EVENTS.keys()), weights=[0.4, 0.1, 0.1, 0.1, 0.1], k=1)[0]

def init_game():
    st.session_state.game_active = True
    st.session_state.season = 1
    st.session_state.market_cards = random.sample(CARDS_DB, 4)
    st.session_state.game_over_msg = ""
    st.session_state.pending_card = None
    st.session_state.next_event_name = get_random_event()
    st.session_state.show_summary = False
    st.session_state.last_total_supply = 500
    
    st.session_state.player = Farm("You", SHED_START_COUNT, 2000.0, personality="Player", is_player=True)
    st.session_state.player.update_valuation() 
    
    st.session_state.opponents = [
        Farm("Small Fry", 3, 2000.0, personality="Conservative"),
        Farm("The Upstart", 4, 3000.0, personality="Aggressive"),
        Farm("THE TYCOON", 6, 8000.0, personality="Predatory")
    ]
    st.session_state.opponents[2].add_card(CARDS_DB[2]) 
    
    for ai in st.session_state.opponents:
        ai.recalculate_breakeven()
        ai.update_valuation() 
    
    st.session_state.history = pd.DataFrame(columns=["Season", "Price", "PlayerCash", "TycoonCash"])

# --- POPUP DIALOG (With Bankruptcy Check) ---
@st.dialog("Quarterly Report", width="large")
def show_season_summary_dialog():
    player = st.session_state.player
    log = player.last_turn_log
    
    st.subheader(f"Season {st.session_state.season - 1} Results")
    
    # Financials
    start_cash = player.cash - log['Profit']
    c1, c2, c3 = st.columns(3)
    c1.metric("Start Cash", f"${start_cash:,.0f}")
    c2.metric("End Cash", f"${player.cash:,.0f}", delta=f"${log['Profit']:,.0f}")
    c3.metric("Clearing Price", f"${log['Price']:.2f}")

    st.divider()

    # Event Context
    evt_label = f"**{log['Event_Name']}**: {log['Event_Desc']}"
    if log['Event_Bad']: st.error(evt_label)
    else: st.success(evt_label)
    
    # Bankruptcy Check
    if player.cash < 0:
        st.error("🚨 **INSOLVENCY NOTICE:** Your cash balance is negative. The bank has seized assets.")
        if st.button("Accept Bankruptcy (Game Over)", type="primary"):
            st.session_state.show_summary = False
            st.session_state.game_active = False
            st.session_state.game_over_msg = f"GAME OVER: Bankrupt in Season {st.session_state.season - 1}"
            st.rerun()
    else:
        # Standard Continue
        if st.button("Close & Start Next Season", type="primary"):
            st.session_state.show_summary = False
            st.rerun()

# --- GAME ENGINE ---
def execute_turn(player_capacity, player_sell_pct, player_build_req):
    player = st.session_state.player
    opponents = st.session_state.opponents
    
    player.spent_last_turn = 0
    for ai in opponents: ai.spent_last_turn = 0
    
    # Construction
    if player_build_req and player.cash >= SHED_COST:
        player.cash -= SHED_COST
        player.sheds += 1
        player.spent_last_turn += SHED_COST
        
    # Purchasing
    if st.session_state.pending_card is not None:
        c_idx = st.session_state.pending_card
        card = st.session_state.market_cards[c_idx]
        if len(player.cards) < 4:
            if card and player.cash >= card['cost']:
                player.cash -= card['cost']
                player.add_card(card)
                player.spent_last_turn += card['cost']
                st.session_state.market_cards[c_idx] = None 
    st.session_state.pending_card = None 

    # AI Actions
    for ai in opponents:
        if ai.bankrupt: continue
        
        build, card_idx, cap_pct, sell_pct = get_ai_decision(ai, player, st.session_state.market_cards)
        
        ai.temp_capacity = cap_pct
        ai.temp_sell_pct = sell_pct
        
        if build:
            ai.cash -= SHED_COST
            ai.sheds += 1
            ai.spent_last_turn += SHED_COST
            
        if card_idx is not None:
            if st.session_state.market_cards[card_idx] is not None:
                card = st.session_state.market_cards[card_idx]
                if ai.cash >= card['cost']:
                    ai.cash -= card['cost']
                    ai.add_card(card)
                    ai.spent_last_turn += card['cost']
                    st.session_state.market_cards[card_idx] = None 
    
    # --- SUPPLY & DEMAND CALCULATION ---
    
    evt_name = st.session_state.next_event_name
    evt_data = EVENTS[evt_name]
    
    current_demand = BASE_DEMAND * evt_data['demand_mod']
    total_supply_produced = 0
    
    all_farms = [player] + opponents
    
    for farm in all_farms:
        if farm.bankrupt: continue
        
        if farm.is_player: cap = player_capacity
        else: cap = farm.temp_capacity
            
        prod_bonus = sum(c.get('prod_bonus', 0) for c in farm.cards)
        raw_prod = farm.sheds * (BASE_PROD + prod_bonus) * cap
        
        fine = 0.0
        if cap > 1.0:
            chance = (cap - 1.0) * FINE_CHANCE_SCALER
            if random.random() < chance:
                fine = REGULATORY_FINE
        
        farm.inventory += raw_prod
        
        if farm.is_player: sales_vol = farm.inventory * player_sell_pct
        else: sales_vol = farm.inventory * farm.temp_sell_pct
            
        farm.temp_sales = sales_vol
        farm.temp_fine = fine
        total_supply_produced += sales_vol

    # Price Discovery
    safe_supply = max(500, total_supply_produced)
    market_price = (current_demand / safe_supply) * 4.0 
    market_price = max(0.50, market_price)
    
    # Save Supply for next turn's forecast
    st.session_state.last_total_supply = safe_supply
    
    # Settlement
    for farm in all_farms:
        if farm.bankrupt: continue
        
        revenue = farm.temp_sales * market_price
        farm.inventory -= farm.temp_sales
        
        if farm.is_player: cap = player_capacity
        else: cap = farm.temp_capacity
        
        prod_bonus = sum(c.get('prod_bonus', 0) for c in farm.cards)
        produced_this_turn = farm.sheds * (BASE_PROD + prod_bonus) * cap
        opex = produced_this_turn * farm.breakeven_price
        
        has_freezer = any(c.get('storage_save', False) for c in farm.cards)
        store_rate = STORAGE_COST_PER_UNIT * 0.5 if has_freezer else STORAGE_COST_PER_UNIT
        storage_fees = farm.inventory * store_rate
        
        profit = revenue - opex - farm.temp_fine - storage_fees
        farm.cash += profit
        
        farm.last_turn_log = {
            "Rev": revenue, "OpEx": opex, "Fine": farm.temp_fine, "Storage": storage_fees,
            "Profit": profit, "Price": market_price, "Sales": farm.temp_sales,
            "Event_Name": evt_name, "Event_Desc": evt_data['desc'], "Event_Bad": evt_data['bad']
        }
        
        if farm.avg_ebitda == 0: farm.avg_ebitda = profit
        else: farm.avg_ebitda = (farm.avg_ebitda * 0.7) + (profit * 0.3)
        
        farm.update_valuation()
        if farm.cash < 0: farm.bankrupt = True

    # Cleanup
    for i in range(4):
        if st.session_state.market_cards[i] is None:
            st.session_state.market_cards[i] = random.choice(CARDS_DB)

    st.session_state.season += 1
    st.session_state.next_event_name = get_random_event()
    st.session_state.show_summary = True
    
    tycoon = opponents[2]
    new_hist = {"Season": st.session_state.season-1, "Price": market_price, "PlayerCash": player.cash, "TycoonCash": tycoon.cash}
    st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([new_hist])], ignore_index=True)

    if st.session_state.season > 40:
        if not opponents[2].bankrupt: 
            st.session_state.game_active = False
            st.session_state.game_over_msg = "GAME OVER: Tycoon survived."

def attempt_buyout(ai_index):
    player = st.session_state.player
    target = st.session_state.opponents[ai_index]
    cost = target.valuation * 1.3 
    if player.cash >= cost:
        player.cash -= cost
        player.sheds += target.sheds
        for c in target.cards: 
            if len(player.cards) < 4:
                player.add_card(c)
        target.bankrupt = True
        target.name = f"Owned by {player.name}"
        target.sheds = 0
        target.cash = 0
        st.success(f"Acquired {target.name}!")
        st.rerun()

def select_card(idx):
    if st.session_state.pending_card == idx: st.session_state.pending_card = None
    else: st.session_state.pending_card = idx

def scrap_asset(idx):
    st.session_state.player.scrap_card(idx)
    st.rerun()

# --- UI RENDERER ---
def main():
    if not st.session_state.game_active:
        st.title("King of the Roost")
        st.caption("Supply, Demand, and Hostile Takeovers")
        
        # --- LANDING PAGE ---
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("The Situation")
            st.markdown("""
            You are a small-time operator in a cutthroat poultry market. 
            **The Tycoon** dominates the region with deep pockets.
            
            But you have received an inside tip: **Apex Global Foods** is entering the market in exactly **10 Years (40 Seasons)**. 
            They are looking to acquire the regional monopoly and will write **one check** to the last player standing.
            
            If The Tycoon is still alive when the clock strikes Season 40, he gets the deal. You get nothing.
            
            🎯 **OBJECTIVE:** Bankrupt or Acquire all 3 competitors (especially The Tycoon) before Season 40.
            """)
            
            st.error("💀 **WARNING:** If your Cash hits $0, you are liquidated immediately.")
            
            if st.button("Open Trading Desk", type="primary"):
                init_game()
                st.rerun()

        with col2:
            st.subheader("Rules of Engagement")
            st.markdown("""
            **1. Production & Inventory**
            Produce chickens and sell them on the market.
            * **Sell:** Cash in immediately at the current market price.
            * **Freeze:** Store inventory in the freezer to sell later (hoping for a price spike).
            
            **2. Supply & Demand**
            The market price is determined by **Total Supply** (You + Competitors).
            * **Flood the Market:** Price crashes.
            * **Withhold Supply:** Price rises.
            
            **3. The Cost Curve (Strategy)**
            * *Hint:* If you reduce your price of production below the Tycoon, you can **flood the market** to drive the price below *their* operating costs.
            * **Result:** You profit; The Tycoon bleeds cash on every bird sold.
            
            **4. Overclocking (Risk)**
            * You can push production to **120%** for extra revenue.
            * **Risk:** 120% Capacity = **40% Chance** of a **Regulatory Fine** per turn.
            
            **5. Insider Intel**
            * If you spend **LESS** money than the Tycoon in a turn (saving cash), you gain **Insider Intel**.
            * This reveals the next season's Demand Forecast *before* you act.
            """)
            
            if st.session_state.game_over_msg:
                st.error(st.session_state.game_over_msg)
        return

    # --- POPUP BLOCKER (BUG FIX) ---
    # If the summary is active, we STOP here. We do not render the dashboard.
    # This prevents you from changing variables while the popup is "technically" open.
    if st.session_state.show_summary:
        show_season_summary_dialog()
        
        # Background "Waiting Room" UI
        st.info("📝 **Season Complete.** Please review and close the Quarterly Report popup to continue.")
        st.caption("If you closed the popup with 'X' by mistake, click below to re-open it.")
        if st.button("Re-open Report"):
            show_season_summary_dialog()
        
        # CRITICAL: Stop execution so the rest of the UI doesn't load
        return

    # --- MAIN DASHBOARD (Only loads if summary is closed) ---
    player = st.session_state.player
    tycoon = st.session_state.opponents[2]
    
    # 1. HEADER METRICS
    prod_bonus = sum(c.get('prod_bonus', 0) for c in player.cards)
    max_capacity = player.sheds * (BASE_PROD + prod_bonus)
    
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Season", f"{st.session_state.season}/40")
    m2.metric("Cash", f"${player.cash:,.0f}")
    m3.metric("Inventory", f"{player.inventory:,.0f}")
    m4.metric("Sheds Owned", f"{player.sheds}")
    m5.metric("Max Capacity", f"{max_capacity:,.0f}", help="Total potential output at 100% intensity")
    
    st.markdown("---")

    # 2. TWO-COLUMN LAYOUT
    left_col, right_col = st.columns([1, 1])

    with left_col:
        st.subheader("⚙️ Operations")
        
        # Efficiency Alert
        cost_diff = tycoon.breakeven_price - player.breakeven_price
        if cost_diff > 0:
            st.success(f"✅ **Efficiency Advantage:** You are ${cost_diff:.2f} cheaper than Tycoon.")
        else:
            st.error(f"⚠️ **Efficiency Warning:** Tycoon produces cheaper than you (Diff: ${abs(cost_diff):.2f}).")
            
        # Production Controls
        st.write("**Production Intensity**")
        capacity_int = st.slider("Intensity %", 0, 120, 100)
        capacity = capacity_int / 100.0
        
        if capacity_int == 0: st.caption("🛑 Mothballed ($0 OpEx)")
        elif capacity_int > 100: 
            risk = int((capacity - 1.0) * FINE_CHANCE_SCALER * 100)
            st.warning(f"🔥 Overclocked ({risk}% Fine Risk)")
        
        st.write("**Sales Strategy**")
        sell_int = st.slider("Sell %", 0, 100, 100)
        sell_pct = sell_int / 100.0
        if sell_int < 100: st.caption(f"❄️ Storing {100-sell_int}%")

        st.divider()
        st.subheader("🛒 Market")
        
        # Expansion
        can_build = player.cash >= SHED_COST
        build_btn = st.checkbox(f"Build Shed (${SHED_COST})", disabled=not can_build)
        
        # Cards Grid
        inventory_full = len(player.cards) >= 4
        if inventory_full: st.error("Inventory Full (4/4). Scrap to buy.")
        
        c1, c2 = st.columns(2)
        for i, card in enumerate(st.session_state.market_cards):
            col = c1 if i % 2 == 0 else c2 
            if card:
                with col.container(border=True):
                    is_selected = (st.session_state.pending_card == i)
                    
                    if is_selected: st.markdown(f"**:red[{card['icon']} {card['name']}]**")
                    else: st.markdown(f"**{card['icon']} {card['name']}**")
                    
                    st.caption(card['desc'])
                    st.write(f"**${card['cost']}**")
                    
                    btn_label = "DESELECT" if is_selected else "BUY"
                    disable = (inventory_full and not is_selected) or (player.cash < card['cost'])
                    
                    if st.button(btn_label, key=f"c_{i}", disabled=disable):
                        select_card(i)
                        st.rerun()
            else:
                col.info("Sold")

        st.markdown("###")
        if st.button("🔴 RUN SEASON", type="primary", use_container_width=True):
            execute_turn(capacity, sell_pct, build_btn)
            st.rerun()

    with right_col:
        st.subheader("📡 Market Intel")
        
        has_intel = (st.session_state.season > 1) and (player.spent_last_turn < tycoon.spent_last_turn)
        next_evt = st.session_state.next_event_name
        
        last_price = player.last_turn_log.get('Price', 4.00)
        st.caption(f"Last Season Clearing Price: **${last_price:.2f}**")
        
        with st.container(border=True):
            if has_intel:
                evt_bad = EVENTS[next_evt]['bad']
                icon = "📉" if evt_bad else "📈"
                st.markdown(f"**Forecast:** {icon} {next_evt}")
                
                demand_impact = int((EVENTS[next_evt]['demand_mod'] - 1.0) * 100)
                if demand_impact > 0: st.caption(f"Demand Impact: +{demand_impact}%")
                else: st.caption(f"Demand Impact: {demand_impact}%")
                
                last_supply = st.session_state.get('last_total_supply', 2000)
                proj_demand = BASE_DEMAND * EVENTS[next_evt]['demand_mod']
                proj_price = (proj_demand / last_supply) * 4.0
                st.metric("Proj. Price", f"${proj_price:.2f}", help="Estimated price if supply stays flat")
            else:
                st.markdown("**Forecast:** ???")
                st.caption("Save cash to unlock intel.")
        
        st.subheader("🎯 Competitors")
        for i, ai in enumerate(st.session_state.opponents):
            if not ai.bankrupt:
                with st.container(border=True):
                    c_head, c_btn = st.columns([2, 1])
                    c_head.markdown(f"**{ai.name}**")
                    
                    buyout_cost = ai.valuation * 1.3
                    if c_btn.button(f"Buy (${buyout_cost:,.0f})", key=f"acq_{i}", disabled=player.cash < buyout_cost):
                        attempt_buyout(i)
                    
                    s1, s2, s3 = st.columns(3)
                    s1.caption(f"🏰 {ai.sheds}")
                    s2.caption(f"💰 ${ai.cash:,.0f}")
                    s3.caption(f"📉 ${ai.breakeven_price:.2f}")

            else:
                st.caption(f"❌ {ai.name} (Eliminated)")

        if player.cards:
            st.divider()
            st.caption("Your Upgrades (Click to Scrap)")
            for i, c in enumerate(player.cards):
                if st.button(f"🗑️ {c['name']} ({c['desc']})", key=f"scrap_{i}"):
                    scrap_asset(i)

    # Chart
    if len(st.session_state.history) > 1:
        st.divider()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=st.session_state.history['Season'], y=st.session_state.history['PlayerCash'], name='You', line=dict(color='green')))
        fig.add_trace(go.Scatter(x=st.session_state.history['Season'], y=st.session_state.history['TycoonCash'], name='Tycoon', line=dict(color='red')))
        fig.add_trace(go.Scatter(x=st.session_state.history['Season'], y=st.session_state.history['Price'], name='Price', line=dict(color='blue', dash='dot'), yaxis='y2'))
        fig.update_layout(height=300, margin=dict(t=0, b=0, l=0, r=0), yaxis2=dict(overlaying='y', side='right'))
        st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()