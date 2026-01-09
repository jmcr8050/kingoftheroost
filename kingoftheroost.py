import streamlit as st
import pandas as pd
import numpy as np
import random
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURATION (EXPERT TUNED) ---
st.set_page_config(page_title="King of the Roost", page_icon="👑", layout="wide")

# -- ECONOMICS --
SHED_COST = 1000
SHED_START_COUNT = 3
BASE_PROD = 80          
FIXED_COST_PER_SHED = 50 
STORAGE_COST_PER_UNIT = 0.10
REGULATORY_FINE = 600.0
FINE_CHANCE_SCALER = 2.0

# -- DEBT CONSTANTS --
RATE_PRIME = 0.05       # 5% 
RATE_MEZZ = 0.09        # 9% 
RATE_JUNK = 0.15        # 15% 
TIER_1_LTV = 0.30       
TIER_2_LTV = 0.60       
MAX_LTV = 0.70          # Hard Debt Cap

# -- MARKET CONSTANTS --
BASE_DEMAND = 2500.0    
DEMAND_ELASTICITY = 1.2 

# -- ASSETS --
CARDS_DB = [
    {"name": "Master Breeder", "type": "Emp", "cost": 600, "prod_bonus": 10, "desc": "+10 Chickens/Shed", "icon": "👨‍🌾"},
    {"name": "Efficiency Expert", "type": "Emp", "cost": 700, "opex_save": 0.5, "desc": "-$0.50 OpEx/Bird", "icon": "📉"},
    {"name": "Hatchery", "type": "Infra", "cost": 1000, "prod_bonus": 20, "desc": "+20 Chickens/Shed", "icon": "🏭"},
    {"name": "Solar Grid", "type": "Infra", "cost": 1200, "opex_save": 0.5, "desc": "-$0.50 OpEx/Bird", "icon": "☀️"},
    {"name": "Industrial Freezer", "type": "Infra", "cost": 500, "storage_save": True, "desc": "Halves Storage Costs", "icon": "❄️"},
]

# -- EVENT DECK --
EVENT_DECK_COMPOSITION = {
    "Normal": 20, "Protein Craze": 5, "Recession": 5, "Export Deal": 5, "Health Scare": 5
}
EVENTS = {
    "Normal": {"demand_mod": 1.0, "bad": False, "desc": "Stable demand."},
    "Protein Craze": {"demand_mod": 1.4, "bad": False, "desc": "Demand SKYROCKETS! (+40%) 🔥"},
    "Recession": {"demand_mod": 0.7, "bad": True, "desc": "Consumers cutting back. Demand -30% 📉"},
    "Export Deal": {"demand_mod": 1.2, "bad": False, "desc": "New trade route opened. Demand +20% 🚢"},
    "Health Scare": {"demand_mod": 0.6, "bad": True, "desc": "Chicken fearful. Demand -40% 🦠"},
}

# --- CLASSES ---
class Farm:
    def __init__(self, name, sheds, cash, personality="Normal", is_player=False):
        self.name = name
        self.sheds = sheds
        self.cash = cash
        self.debt = 0.0 
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
    
    def get_asset_value(self):
        # Collateral Value for Banks (Conservative)
        # Cash + (Sheds * Cost * 80%) + (Inv * $1.50)
        return self.cash + (self.sheds * SHED_COST * 0.8) + (self.inventory * 1.5)

    def get_ltv(self):
        assets = self.get_asset_value()
        if assets <= 0: return 9.99 # Infinite leverage
        return self.debt / assets

    def get_interest_rate(self):
        ltv = self.get_ltv()
        if ltv < TIER_1_LTV: return RATE_PRIME
        elif ltv < TIER_2_LTV: return RATE_MEZZ
        else: return RATE_JUNK

    def update_valuation(self):
        # 1. Liquidation Value (Net of Debt)
        asset_val = (self.sheds * SHED_COST) + sum(c['cost'] for c in self.cards) + (self.inventory * 2.0)
        liquidation_value = (self.cash + asset_val) - self.debt
        
        # 2. Earnings Value (4x EBITDA) (Net of Debt)
        estimated_base_ebitda = self.sheds * BASE_PROD * 1.0 
        used_ebitda = max(estimated_base_ebitda, self.avg_ebitda)
        earnings_value = (self.cash + (used_ebitda * 4.0)) - self.debt
        
        self.valuation = max(liquidation_value, earnings_value)

    def add_card(self, card):
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
    
    # 0. SURVIVAL CHECK
    est_interest = ai.debt * ai.get_interest_rate()
    burn_rate = (ai.sheds * FIXED_COST_PER_SHED) + est_interest
    if ai.cash < (burn_rate * 2.0):
        return False, None, 1.0, 1.0 # Panic Mode

    # 1. Expansion
    if ai.personality == "Conservative":
        if ai.cash > (SHED_COST * 2.5 * variance): wants_to_build = True
    elif ai.personality == "Aggressive" or ai.personality == "Predatory":
        if ai.cash > (SHED_COST * 1.5 * variance): wants_to_build = True

    # 2. Capacity
    if ai.personality == "Aggressive" and random.random() < 0.3: 
        capacity = 1.1

    # 3. Predatory
    if ai.personality == "Predatory":
        is_player_weak = (player.cash < 1500) or (player.cash < (ai.cash * 0.2))
        if is_player_weak and ai.cash > 2000:
            capacity = 1.2 
            sell_pct = 1.0 
            wants_to_build = False 
        else:
            has_freezer = any(c['name'] == "Industrial Freezer" for c in ai.cards)
            if has_freezer and random.random() < 0.3:
                sell_pct = 0.5 

    # 4. Cards
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
if 'last_total_supply' not in st.session_state: st.session_state.last_total_supply = 500 
if 'event_deck' not in st.session_state: st.session_state.event_deck = []
# NEW: Track Net Borrowing for Reports
if 'last_net_borrowing' not in st.session_state: st.session_state.last_net_borrowing = 0 

def init_deck():
    deck = []
    for evt, count in EVENT_DECK_COMPOSITION.items():
        deck.extend([evt] * count)
    random.shuffle(deck)
    deck.insert(0, "Normal")
    deck.insert(0, "Normal")
    return deck

def draw_event():
    if not st.session_state.event_deck:
        return "Normal" 
    return st.session_state.event_deck.pop(0)

def init_game():
    st.session_state.game_active = True
    st.session_state.season = 1
    st.session_state.market_cards = random.sample(CARDS_DB, 4)
    st.session_state.game_over_msg = ""
    st.session_state.pending_card = None
    st.session_state.show_summary = False
    st.session_state.last_total_supply = 500
    st.session_state.event_deck = init_deck()
    st.session_state.next_event_name = draw_event()
    st.session_state.last_net_borrowing = 0
    
    st.session_state.player = Farm("You", SHED_START_COUNT, 2500.0, personality="Player", is_player=True)
    st.session_state.player.update_valuation() 
    
    st.session_state.opponents = [
        Farm("Small Fry", 3, 2000.0, personality="Conservative"),
        Farm("The Upstart", 4, 3000.0, personality="Aggressive"),
        Farm("THE TYCOON", 6, 4000.0, personality="Predatory")
    ]
    st.session_state.opponents[2].add_card(CARDS_DB[2]) 
    
    for ai in st.session_state.opponents:
        ai.recalculate_breakeven()
        ai.update_valuation() 
    
    st.session_state.history = pd.DataFrame(columns=["Season", "Price", "PlayerCash", "TycoonCash"])

# --- END GAME REPORT ---
def draw_end_game_report():
    st.divider()
    msg = st.session_state.game_over_msg
    is_win = "VICTORY" in msg
    
    if is_win:
        st.success(f"# 🏆 MISSION ACCOMPLISHED")
        st.markdown(f"### {msg}")
        st.balloons()
    else:
        st.error(f"# 💀 TERMINATED")
        st.markdown(f"### {msg}")

    player = st.session_state.player
    years_played = st.session_state.season / 4.0
    start_val = 5500 
    end_val = player.valuation
    if end_val <= 0: cagr = -1.0 
    else: cagr = (end_val / start_val) ** (1 / max(years_played, 0.25)) - 1
    
    if not is_win: grade = "F"
    elif cagr > 0.25: grade = "A+"
    elif cagr > 0.15: grade = "A"
    elif cagr > 0.10: grade = "B"
    elif cagr > 0.05: grade = "C"
    else: grade = "D"

    st.markdown("### 📋 The Board's Review")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Final Valuation", f"${end_val:,.0f}")
    col2.metric("Tenure", f"{years_played:.1f} Years")
    col3.metric("CAGR (Return)", f"{cagr:.1%}")
    col4.metric("CEO Grade", grade)
    
    if len(st.session_state.history) > 0:
        st.markdown("### 📈 Shareholder Value History")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=st.session_state.history['Season'], y=st.session_state.history['PlayerCash'], name='Your Cash', line=dict(color='green', width=3)))
        fig.add_trace(go.Scatter(x=st.session_state.history['Season'], y=st.session_state.history['TycoonCash'], name='Tycoon Cash', line=dict(color='red', width=2)))
        st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    if st.button("🔄 Start New Career", type="primary"):
        init_game()
        st.rerun()

# --- POPUP DIALOG (Reports) ---
@st.dialog("Quarterly Report", width="large")
def show_season_summary_dialog():
    player = st.session_state.player
    log = player.last_turn_log
    net_borrowing = st.session_state.last_net_borrowing
    
    st.subheader(f"Season {st.session_state.season - 1} Performance")
    
    # Event Banner
    evt_label = f"**MARKET EVENT:** {log['Event_Name']} ({log['Event_Desc']})"
    if log['Event_Bad']: st.error(evt_label)
    else: st.success(evt_label)

    # 1. VOLUME STATS
    st.caption("📦 OPERATIONS (VOLUME)")
    v1, v2, v3, v4 = st.columns(4)
    v1.metric("Produced", f"{int(log.get('Prod', 0))}", help="New birds hatched")
    v2.metric("Sold", f"{int(log['Sales'])}", help="Birds sold")
    net_inv = int(log.get('Net_Inv_Change', 0))
    v3.metric("Net Frozen", f"{net_inv:+}", help="Change in inventory")
    v4.metric("Closing Inv.", f"{int(player.inventory)}")

    st.divider()

    # 2. INCOME STATEMENT (P&L)
    st.markdown("### 📉 Income Statement")
    
    c1, c2 = st.columns([3, 1])
    c1.write("➕ **Revenue** (Sales x Price)")
    c2.write(f"**${log['Rev']:,.0f}**")
    
    c1, c2 = st.columns([3, 1])
    c1.write(f"➖ OpEx (Production x ${player.breakeven_price:.2f})")
    c2.write(f":red[-${log['OpEx']:,.0f}]")

    c1, c2 = st.columns([3, 1])
    c1.write(f"➖ Fixed Costs & Interest")
    overhead = log['FixedCost'] + log.get('Interest', 0)
    c2.write(f":red[-${overhead:,.0f}]")
    
    if log['Storage'] + log['Fine'] > 0:
        c1, c2 = st.columns([3, 1])
        c1.write("➖ Storage & Fines")
        c2.write(f":red[-${(log['Storage'] + log['Fine']):,.0f}]")

    c1, c2 = st.columns([3, 1])
    c1.markdown("**🟰 Net Profit (Loss)**")
    color = "green" if log['Profit'] > 0 else "red"
    c2.markdown(f":{color}[**${log['Profit']:,.0f}**]")

    st.divider()

    # 3. CASH FLOW STATEMENT
    st.markdown("### 💵 Cash Flow Statement")
    start_cash = player.cash - log['Profit'] - net_borrowing
    
    cf1, cf2, cf3, cf4 = st.columns(4)
    cf1.metric("Start Cash", f"${start_cash:,.0f}")
    cf2.metric("Operations", f"${log['Profit']:+,.0f}", help="Net Profit")
    cf3.metric("Financing", f"${net_borrowing:+,.0f}", help="Net Loans Taken/Repaid")
    cf4.metric("End Cash", f"${player.cash:,.0f}")

    if player.cash < 0:
        st.error("🚨 **INSOLVENCY NOTICE:** Cash balance negative. Assets seized.")
        if st.button("Accept Bankruptcy", type="primary"):
            st.session_state.show_summary = False
            st.session_state.game_active = False
            st.session_state.game_over_msg = f"GAME OVER: Bankrupt in Season {st.session_state.season - 1}"
            st.rerun()
    else:
        if st.button("Close & Start Next Season", type="primary"):
            st.session_state.show_summary = False
            st.rerun()

# --- HELPER ACTIONS ---
def instant_borrow(amount):
    player = st.session_state.player
    # Cap check
    assets = player.get_asset_value()
    max_debt = assets * MAX_LTV
    if (player.debt + amount) > max_debt:
        return # Denied
    player.debt += amount
    player.cash += amount
    st.session_state.last_net_borrowing += amount

def instant_repay(amount):
    player = st.session_state.player
    actual = min(amount, player.cash, player.debt)
    player.debt -= actual
    player.cash -= actual
    st.session_state.last_net_borrowing -= actual

# --- GAME ENGINE ---
def execute_turn(player_capacity, player_sell_pct, player_build_req):
    player = st.session_state.player
    opponents = st.session_state.opponents
    
    # Reset Per-Turn Logs
    st.session_state.last_net_borrowing = 0 
    player.spent_last_turn = 0
    for ai in opponents: ai.spent_last_turn = 0
    
    # 1. Construction
    if player_build_req and player.cash >= SHED_COST:
        player.cash -= SHED_COST
        player.sheds += 1
        player.spent_last_turn += SHED_COST
        
    # 2. Purchasing
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
    
    # --- MARKET ENGINE ---
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
            if random.random() < chance: fine = REGULATORY_FINE
        
        farm.temp_prod = raw_prod # Save for log
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
    
    st.session_state.last_total_supply = safe_supply
    
    # Settlement
    for farm in all_farms:
        if farm.bankrupt: continue
        
        revenue = farm.temp_sales * market_price
        farm.inventory -= farm.temp_sales
        
        net_inv_change = farm.temp_prod - farm.temp_sales # Fix "Net Frozen" bug
        
        # Expenses
        prod_bonus = sum(c.get('prod_bonus', 0) for c in farm.cards)
        # Recalc cap for accurate OpEx
        cap = player_capacity if farm.is_player else farm.temp_capacity
        produced_this_turn = farm.sheds * (BASE_PROD + prod_bonus) * cap
        
        opex = produced_this_turn * farm.breakeven_price
        fixed_cost = farm.sheds * FIXED_COST_PER_SHED
        interest = farm.debt * farm.get_interest_rate()
        
        has_freezer = any(c.get('storage_save', False) for c in farm.cards)
        store_rate = STORAGE_COST_PER_UNIT * 0.5 if has_freezer else STORAGE_COST_PER_UNIT
        storage_fees = farm.inventory * store_rate
        
        profit = revenue - opex - fixed_cost - farm.temp_fine - storage_fees - interest
        farm.cash += profit
        
        farm.last_turn_log = {
            "Rev": revenue, "OpEx": opex, "FixedCost": fixed_cost, 
            "Interest": interest, "Fine": farm.temp_fine, "Storage": storage_fees,
            "Profit": profit, "Price": market_price, "Sales": farm.temp_sales,
            "Prod": farm.temp_prod, "Net_Inv_Change": net_inv_change,
            "Event_Name": evt_name, "Event_Desc": evt_data['desc'], "Event_Bad": evt_data['bad']
        }
        
        if farm.avg_ebitda == 0: farm.avg_ebitda = profit
        else: farm.avg_ebitda = (farm.avg_ebitda * 0.7) + (profit * 0.3)
        
        farm.update_valuation()
        if farm.cash < 0: farm.bankrupt = True

    # Cleanup & Game Over Checks
    for i in range(4):
        if st.session_state.market_cards[i] is None:
            st.session_state.market_cards[i] = random.choice(CARDS_DB)

    st.session_state.season += 1
    st.session_state.next_event_name = draw_event()
    st.session_state.show_summary = True
    
    tycoon = opponents[2]
    new_hist = {"Season": st.session_state.season-1, "Price": market_price, "PlayerCash": player.cash, "TycoonCash": tycoon.cash}
    st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([new_hist])], ignore_index=True)

    if opponents[2].bankrupt:
        st.session_state.game_active = False
        st.session_state.game_over_msg = "🏆 VICTORY! The Tycoon has gone bankrupt. You are the King of the Roost!"
        
    if st.session_state.season > 40:
        st.session_state.game_active = False
        st.session_state.game_over_msg = "💀 GAME OVER: Time is up. Apex Global acquired The Tycoon."

def attempt_buyout(ai_index):
    player = st.session_state.player
    target = st.session_state.opponents[ai_index]
    
    # UPDATED M&A LOGIC
    # Standard: 1.1x (Down from 1.3x)
    multiplier = 1.1 
    # Distressed Discount: If cash < $500, pay 0.8x
    if target.cash < 500: multiplier = 0.8
        
    cost = target.valuation * multiplier 
    
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
        
        if ai_index == 2: # Tycoon Index
            st.session_state.game_active = False
            st.session_state.game_over_msg = "🏆 VICTORY! You acquired The Tycoon. Complete Monopoly achieved."
            st.rerun()
            
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
        
        if st.session_state.game_over_msg:
            draw_end_game_report()
            return 

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
            * **Sell:** Cash in immediately at the current market price.
            * **Freeze:** Store inventory to sell later (hoping for a price spike).
            
            **2. Supply & Demand**
            The market price is determined by **Total Supply**.
            * **Flood the Market:** Price crashes.
            * **Withhold Supply:** Price rises.
            
            **3. M&A Strategy (The Growth Hack)**
            * **Hint:** Building sheds is often cheaper than buying them, unless the rival is distressed (low cash) or you have massive synergy.
            
            **4. Corporate Debt (Leverage)**
            * **Interest Rates:** 5% (Safe) -> 9% (Risky) -> 15% (Junk).
            * **Warning:** Banks cap lending at **70% LTV**. Don't over-leverage!
            
            **5. Insider Intel**
            * Spend **LESS** than the Tycoon to gain **Insider Intel** on next season's Demand Forecast.
            """)
        return

    # --- POPUP BLOCKER ---
    if st.session_state.show_summary:
        show_season_summary_dialog()
        st.info("📝 **Season Complete.** Please review and close the Quarterly Report popup to continue.")
        if st.button("Re-open Report"):
            show_season_summary_dialog()
        return

    # --- MAIN DASHBOARD ---
    player = st.session_state.player
    tycoon = st.session_state.opponents[2]
    
    # 1. HEADER
    prod_bonus = sum(c.get('prod_bonus', 0) for c in player.cards)
    max_capacity = player.sheds * (BASE_PROD + prod_bonus)
    
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Season", f"{st.session_state.season}/40")
    m2.metric("Cash", f"${player.cash:,.0f}")
    m3.metric("Debt", f"${player.debt:,.0f}")
    m4.metric("Sheds", f"{player.sheds}")
    m5.metric("Max Capacity", f"{max_capacity:,.0f}")
    
    st.markdown("---")

    left_col, right_col = st.columns([1, 1])

    # --- LEFT COLUMN TABS ---
    ops_tab, analyst_tab = left_col.tabs(["🎛️ Operations", "📊 Analyst"])

    with ops_tab:
        st.subheader("⚙️ Decisions")
        
        # FINANCE DEPARTMENT (Instant Updates)
        with st.expander("🏦 Corporate Finance (Debt Facility)", expanded=False):
            ltv = player.get_ltv()
            curr_rate = player.get_interest_rate()
            
            # Credit Rating UI
            rating_color = "green"
            if curr_rate > 0.09: rating_color = "red"
            elif curr_rate > 0.05: rating_color = "orange"
            
            st.markdown(f"**Credit Rating:** :{rating_color}[{curr_rate*100:.0f}% Interest] (LTV: {ltv:.1%})")
            st.progress(min(ltv, 1.0))
            if ltv >= MAX_LTV: st.error("⛔ CREDIT LIMIT REACHED")

            fc1, fc2 = st.columns(2)
            if fc1.button("Borrow $1,000"):
                instant_borrow(1000)
                st.rerun()
            if fc2.button("Repay $1,000"):
                instant_repay(1000)
                st.rerun()

        st.divider()
        
        st.caption(f"Current Unit Cost: **${player.breakeven_price:.2f} / bird**")
        cost_diff = tycoon.breakeven_price - player.breakeven_price
        
        if cost_diff > 0.001:
            st.success(f"✅ **Efficiency Advantage:** You are ${cost_diff:.2f} cheaper than Tycoon.")
        elif cost_diff < -0.001:
            st.error(f"⚠️ **Efficiency Warning:** Tycoon produces cheaper than you (Diff: ${abs(cost_diff):.2f}).")
        else:
            st.info(f"⚖️ **Cost Parity:** You match the Tycoon's efficiency.")
            
        st.write("**Production Intensity**")
        capacity_int = st.slider("Intensity %", 0, 120, 100)
        capacity = capacity_int / 100.0
        
        if capacity_int == 0: st.caption(f"🛑 Mothballed (${player.sheds*FIXED_COST_PER_SHED} Fixed Cost)")
        elif capacity_int > 100: 
            risk = int((capacity - 1.0) * FINE_CHANCE_SCALER * 100)
            st.warning(f"🔥 Overclocked ({risk}% Fine Risk)")
        
        st.write("**Sales Strategy**")
        sell_int = st.slider("Sell %", 0, 100, 100)
        sell_pct = sell_int / 100.0
        if sell_int < 100: st.caption(f"❄️ Storing {100-sell_int}%")

        st.divider()
        st.subheader("🛒 Market")
        
        can_build = player.cash >= SHED_COST
        build_btn = st.checkbox(f"Build Shed (${SHED_COST}) - Adds {BASE_PROD} Chickens", disabled=not can_build)
        
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

    with analyst_tab:
        st.subheader("📊 Financial Analyst Tools")
        st.caption("Use these tools to model scenarios before you commit capital.")
        
        with st.container(border=True):
            st.write("**Marginal Revenue Calculator**")
            last_p = player.last_turn_log.get('Price', 4.00)
            st.caption(f"Est. Revenue @ ${last_p:.2f} (Last Season Price)")
            est_vol = max_capacity * capacity * sell_pct
            st.metric("Est. Revenue", f"${est_vol * last_p:,.0f}", help="Volume x Last Price")
            
        with st.container(border=True):
            st.write("**Stress Test (Recession Sim)**")
            st.caption("Simulate cash flow at $2.00/bird price.")
            
            # Using a unique key for this slider so it doesn't conflict
            stress_prod = st.slider("Test Production %", 0, 120, 100, key="stress_slider") / 100.0
            
            stress_vol = max_capacity * stress_prod
            stress_rev = stress_vol * 2.00 # $2.00 crash price
            stress_cost = (stress_vol * player.breakeven_price) + (player.sheds * FIXED_COST_PER_SHED) + (player.debt * curr_rate)
            net_stress = stress_rev - stress_cost
            
            st.write(f"**Scenario:** Price Drops to $2.00")
            if net_stress < 0: 
                st.error(f"🔥 **Burn Rate:** -${abs(net_stress):,.0f} / turn")
                st.caption("You will lose money.")
            else: 
                st.success(f"✅ **Survival:** +${net_stress:,.0f} / turn")
                st.caption("You remain profitable.")

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
                    
                    multiplier = 1.1
                    if ai.cash < 500: multiplier = 0.8 
                    buyout_cost = ai.valuation * multiplier
                    
                    if c_btn.button(f"Buy (${buyout_cost:,.0f})", key=f"acq_{i}", disabled=player.cash < buyout_cost):
                        attempt_buyout(i)
                    
                    if ai.cash < 500: st.caption(":red[⚠️ DISTRESSED ASSET (20% OFF)]")

                    their_margin = 4.00 - ai.breakeven_price
                    your_margin = 4.00 - player.breakeven_price
                    delta = (your_margin - their_margin) * 80 
                    
                    if delta > 0:
                        st.caption(f"⚡ **Operational Synergy:** +${delta:.0f}/shed profit vs current management.")
                    
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