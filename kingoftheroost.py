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
    {"name": "Crisis Mgmt Firm", "type": "Emp", "cost": 500, "risk_mitigation": True, "desc": "Mitigates Bad PR Events", "icon": "📢"},
    {"name": "Adv. Biosecurity", "type": "Infra", "cost": 500, "bio_secure": True, "desc": "Prevents Recall Wipeouts", "icon": "🛡️"},
]

# -- EVENTS (THEMATIC OVERHAUL) --
EVENTS = {
    "Normal": {
        "prob": 0.4, "demand_mod": 1.0, "bad": False, "destroy_inv": False,
        "desc": "Market is stable."
    },
    "Keto Diet Trend": {
        "prob": 0.1, "demand_mod": 1.4, "bad": False, "destroy_inv": False,
        "desc": "Carbs are out. Chicken is in. Demand SKYROCKETS (+40%)! 🔥"
    },
    "Supply Chain Scandal": {
        "prob": 0.1, "demand_mod": 0.6, "bad": True, "destroy_inv": False,
        "desc": "Leaked report shows bad practices. Consumers boycott (-40%). 📉"
    },
    "Chicken Sandwich War": {
        "prob": 0.1, "demand_mod": 1.2, "bad": False, "destroy_inv": False,
        "desc": "Fast food chains fighting for supply. Demand +20%. 🍔"
    },
    "Salmonella Recall": {
        "prob": 0.1, "demand_mod": 0.5, "bad": True, "destroy_inv": True,
        "desc": "CONTAMINATION DETECTED! Unsold inventory destroyed. Demand crashes. 🦠"
    },
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
if 'game_won' not in st.session_state: st.session_state.game_won = False
if 'pending_card' not in st.session_state: st.session_state.pending_card = None 
if 'next_event_name' not in st.session_state: st.session_state.next_event_name = "Normal"
if 'show_summary' not in st.session_state: st.session_state.show_summary = False
if 'show_game_over' not in st.session_state: st.session_state.show_game_over = False
if 'last_sell_pct' not in st.session_state: st.session_state.last_sell_pct = 100 # Default to 100%

def get_random_event():
    return random.choices(list(EVENTS.keys()), weights=[0.4, 0.1, 0.1, 0.1, 0.1], k=1)[0]

def init_game():
    st.session_state.game_active = True
    st.session_state.game_won = False
    st.session_state.show_game_over = False
    st.session_state.season = 1
    st.session_state.market_cards = random.sample(CARDS_DB, 4)
    st.session_state.game_over_msg = ""
    st.session_state.pending_card = None
    st.session_state.next_event_name = get_random_event()
    st.session_state.show_summary = False
    st.session_state.last_sell_pct = 100
    
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

# --- POPUP DIALOGS ---

@st.dialog("📋 Quarterly Report")
def show_season_summary_dialog():
    player = st.session_state.player
    log = player.last_turn_log
    
    st.markdown(f"### Season {st.session_state.season - 1} Results")
    
    # Event Context
    evt_label = f"**{log['Event_Name']}**: {log['Event_Desc']}"
    if log['Event_Bad']: st.error(evt_label)
    else: st.success(evt_label)
    
    c1, c2 = st.columns(2)
    c1.metric("Revenue", f"${log['Rev']:,.0f}")
    c2.metric("OpEx", f"-${log['OpEx']:,.0f}")
    
    c3, c4 = st.columns(2)
    c3.metric("Fines/Storage", f"-${log['Storage'] + log['Fine']:,.0f}")
    c4.metric("Net Profit", f"${log['Profit']:,.0f}", delta_color="normal" if log['Profit']>0 else "inverse")
    
    st.divider()
    st.caption(f"Market Clearing Price: ${log['Price']:.2f}")
    
    if st.button("Close & Start Next Season"):
        st.session_state.show_summary = False
        st.rerun()

@st.dialog("🏁 GAME OVER")
def show_game_over_dialog():
    if st.session_state.game_won:
        st.markdown("## 🏆 VICTORY!")
        st.balloons()
        st.success("You have acquired all competitors!")
        st.markdown("""
        **Apex Global Foods** has arrived. 
        As the sole remaining operator, they have written you a check for **$50,000,000**.
        
        You are the King of the Roost.
        """)
    elif st.session_state.player.bankrupt:
        st.markdown("## 💸 BANKRUPT")
        st.error("You ran out of cash.")
        st.markdown("""
        Your creditors have seized your farm. 
        The Tycoon bought your assets at auction for pennies on the dollar.
        
        **Tip:** Watch your cash flow. Expanding too fast is the quickest way to die.
        """)
    else:
        st.markdown("## 💀 TIME'S UP")
        st.error("Season 40 has arrived.")
        st.markdown("""
        **Apex Global Foods** has arrived. 
        They found **The Tycoon** (or others) still operating in the valley.
        
        Because you failed to consolidate the monopoly, Apex acquired The Tycoon instead.
        You have been pushed out of the market.
        """)
        
    st.divider()
    if st.button("Return to Main Menu"):
        st.session_state.game_active = False
        st.session_state.show_game_over = False
        st.rerun()

# --- GAME ENGINE ---
def execute_turn(player_capacity, player_sell_pct, player_build_req):
    player = st.session_state.player
    opponents = st.session_state.opponents
    
    # Update Memory for Slider
    st.session_state.last_sell_pct = int(player_sell_pct * 100)
    
    # 1. Reset Spend Logic
    player.spent_last_turn = 0
    for ai in opponents: ai.spent_last_turn = 0
    
    # 2. Player Construction
    if player_build_req and player.cash >= SHED_COST:
        player.cash -= SHED_COST
        player.sheds += 1
        player.spent_last_turn += SHED_COST
        
    # 3. Player Purchase
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

    # 4. AI ACTIONS
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
    
    # --- 5. SUPPLY & DEMAND ENGINE ---
    
    evt_name = st.session_state.next_event_name
    evt_data = EVENTS[evt_name]
    
    # Calculate Demand
    current_demand = BASE_DEMAND * evt_data['demand_mod']
    total_supply_produced = 0
    
    all_farms = [player] + opponents
    
    # PRODUCTION PHASE
    for farm in all_farms:
        if farm.bankrupt: continue
        
        # Determine Capacity
        if farm.is_player: cap = player_capacity
        else: cap = farm.temp_capacity
            
        prod_bonus = sum(c.get('prod_bonus', 0) for c in farm.cards)
        raw_prod = farm.sheds * (BASE_PROD + prod_bonus) * cap
        
        # Regulatory Fine Check
        fine = 0.0
        if cap > 1.0:
            chance = (cap - 1.0) * FINE_CHANCE_SCALER
            if random.random() < chance:
                fine = REGULATORY_FINE
        
        # Add to Inventory
        farm.inventory += raw_prod
        
        # CHECK RECALL EVENT (Destroy Inventory)
        if evt_data['destroy_inv']:
            has_protection = any(c.get('bio_secure', False) for c in farm.cards)
            if not has_protection:
                # Inventory Destroyed
                farm.inventory = 0
                # Note: They produced, so they pay OpEx, but they have 0 to sell.
        
        # Determine Sales
        if farm.is_player: sales_vol = farm.inventory * player_sell_pct
        else: sales_vol = farm.inventory * farm.temp_sell_pct
            
        farm.temp_sales = sales_vol
        farm.temp_fine = fine
        total_supply_produced += sales_vol

    # PRICE DISCOVERY
    safe_supply = max(500, total_supply_produced)
    market_price = (current_demand / safe_supply) * 4.0 
    market_price = max(0.50, market_price)
    
    # FINANCIAL SETTLEMENT
    for farm in all_farms:
        if farm.bankrupt: continue
        
        revenue = farm.temp_sales * market_price
        farm.inventory -= farm.temp_sales
        
        # Recalc OpEx (Based on Production, not sales)
        if farm.is_player: cap = player_capacity
        else: cap = farm.temp_capacity
        prod_bonus = sum(c.get('prod_bonus', 0) for c in farm.cards)
        produced_this_turn = farm.sheds * (BASE_PROD + prod_bonus) * cap
        
        # OpEx modifiers
        opex_base = farm.breakeven_price 
        # Note: farm.breakeven_price is calculated on card add. 
        # But we also have Crisis Firm logic to add:
        # If event is BAD, and you have Crisis Firm, we need to mitigate the badness?
        # Actually, Crisis Firm in this engine should probably mitigate Demand drops?
        # Implementing Crisis Firm as a Revenue Buffer for simplicity here:
        # If Event is Bad, and you have Crisis Firm, you get +$0.50 premium on price.
        has_crisis_firm = any(c.get('risk_mitigation', False) for c in farm.cards)
        price_mod = 0
        if evt_data['bad'] and has_crisis_firm:
            price_mod = 0.50
            
        final_price_for_farm = market_price + price_mod
        revenue = farm.temp_sales * final_price_for_farm
        
        opex = produced_this_turn * opex_base
        
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
        # BANKRUPTCY CHECK IN LOOP (For AI)
        if farm.cash < 0: farm.bankrupt = True

    # CLEANUP
    for i in range(4):
        if st.session_state.market_cards[i] is None:
            st.session_state.market_cards[i] = random.choice(CARDS_DB)

    st.session_state.season += 1
    st.session_state.next_event_name = get_random_event()
    
    # Trigger Summary Popup
    st.session_state.show_summary = True
    
    tycoon = opponents[2]
    new_hist = {"Season": st.session_state.season-1, "Price": market_price, "PlayerCash": player.cash, "TycoonCash": tycoon.cash}
    st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([new_hist])], ignore_index=True)

    # CHECK PLAYER BANKRUPTCY
    if player.cash < 0:
        player.bankrupt = True
        st.session_state.game_won = False
        st.session_state.show_game_over = True
        st.session_state.show_summary = False
        return

    # CHECK TIME LIMIT
    if st.session_state.season > 40:
        if not opponents[2].bankrupt: 
            st.session_state.game_won = False
            st.session_state.show_game_over = True
            st.session_state.show_summary = False 

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
        
        # CHECK WIN CONDITION
        active_opponents = [ai for ai in st.session_state.opponents if not ai.bankrupt]
        if len(active_opponents) == 0:
            st.session_state.game_won = True
            st.session_state.show_game_over = True
            st.rerun()
        else:
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
        st.title("👑 King of the Roost: Trading Floor")
        st.caption("Supply, Demand, and Hostile Takeovers")
        
        col1, col2 = st.columns([1.5, 1])
        with col1:
            st.markdown("### 📜 The Situation")
            st.markdown("""
            You are a small-time operator in a cutthroat poultry market. 
            **The Tycoon** dominates the region with deep pockets.
            
            But you have a secret: **Apex Global Foods** is entering the market in exactly **40 Seasons** (10 Years). 
            They will write **one check** to the last player standing.
            """)
            
            st.info("""
            **OBJECTIVE:** Acquire all 3 competitors before Season 40. 
            **WARNING:** If your Cash hits $0, you are Bankrupt and the game ends immediately.
            """)
            
            st.markdown("### 📉 Market Dynamics (Price Calculation)")
            st.markdown("""
            Unlike simpler markets, the price here is **floating** based on Supply & Demand.
            
            1.  **Global Demand:** Set by events (e.g., *Chicken Sandwich War* = High Demand).
            2.  **Global Supply:** The total chickens sold by **You + The AI** this turn.
            3.  **The Formula:** `Price = Total Demand / Total Supply`
            
            **The Strategy:** If the Tycoon floods the market, Supply spikes and Price crashes. 
            You must decide whether to **Liquidate** (Sell into a crash) or **Hoard** (Hold stock in Freezer).
            """)
            
            if st.button("Open Trading Desk", type="primary"):
                init_game()
                st.rerun()
        
        with col2:
            st.warning("### Unit Economics")
            st.markdown(f"""
            * **Shed Cost:** ${SHED_COST:,.0f}
            * **Base Cost:** ~$3.50/bird
            * **Fine Risk:** $500 + Production Loss
            """)

        return

    # --- POPUP LOGIC ---
    if st.session_state.show_game_over:
        show_game_over_dialog()
    elif st.session_state.show_summary:
        show_season_summary_dialog()

    # --- DASHBOARD ---
    player = st.session_state.player
    tycoon = st.session_state.opponents[2]
    
    st.markdown(f"### 🗓️ Season {st.session_state.season} / 40")
    
    # 1. MARKET INTEL
    has_intel = (st.session_state.season > 1) and (player.spent_last_turn < tycoon.spent_last_turn)
    if has_intel:
        next_evt = st.session_state.next_event_name
        is_bad = EVENTS[next_evt]['bad']
        st.info(f"🕵️ **INSIDER INTEL:** Analysts predict **{next_evt}** next season.")

    # 2. KEY METRICS
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Cash", f"${player.cash:,.0f}", delta=f"${player.last_turn_log.get('Profit', 0):,.0f}")
    m2.metric("Inventory", f"{player.inventory:,.0f} Units", delta=f"{player.last_turn_log.get('Sales', 0) * -1:,.0f} Sold")
    m3.metric("Your Cost Basis", f"${player.breakeven_price:.2f}", delta=f"${player.breakeven_price - 3.50:.2f}", delta_color="inverse")
    m4.metric("Tycoon Cost", f"${tycoon.breakeven_price:.2f}", "Target to Beat", delta_color="off")

    st.markdown("---")

    # 3. TRADING DESK & COMPETITION
    c_trade, c_comp = st.columns([1.2, 1])
    
    with c_trade:
        st.subheader("📊 Trading Desk")
        
        cost_diff = tycoon.breakeven_price - player.breakeven_price
        if cost_diff > 0:
            st.success(f"✅ **Efficiency Advantage:** You are ${cost_diff:.2f} cheaper than Tycoon.")
        else:
            st.error(f"⚠️ **Efficiency Warning:** Tycoon produces cheaper than you.")
            
        st.write("---")
        
        st.write("**1. Production Intensity**")
        capacity_int = st.slider("Overclock", 100, 120, 100)
        capacity = capacity_int / 100.0
        if capacity_int > 100:
            risk = int((capacity - 1.0) * FINE_CHANCE_SCALER * 100)
            st.warning(f"🔥 +{capacity_int-100}% Supply | ⚠️ {risk}% Fine Risk")
            
        st.write("**2. Inventory Strategy (Sell vs Hold)**")
        # Load previous value from state
        default_sell = st.session_state.last_sell_pct
        sell_int = st.slider("Percentage to Liquidate", 0, 100, default_sell)
        sell_pct = sell_int / 100.0
        
        if sell_int < 100:
            st.caption(f"❄️ Hoarding {100-sell_int}% in Freezer (Speculating on future price)")
        else:
            st.caption("🔥 Liquidating 100% (Cash Out Now)")

        st.markdown("###")
        can_build = player.cash >= SHED_COST
        build_btn = st.checkbox(f"Expand Production (+1 Shed: ${SHED_COST})", disabled=not can_build)
        
        if st.button("🔴 EXECUTE TRADES", type="primary", use_container_width=True):
            execute_turn(capacity, sell_pct, build_btn)
            st.rerun()

    with c_comp:
        st.subheader("🎯 M&A Targets")
        for i, ai in enumerate(st.session_state.opponents):
            buyout_cost = ai.valuation * 1.3
            status = "red" if ai.bankrupt else "green"
            
            with st.container():
                st.markdown(f"**{ai.name}** :{status}[●]")
                if not ai.bankrupt:
                    c1, c2 = st.columns(2)
                    c1.caption(f"Sheds: {ai.sheds}")
                    c2.caption(f"Cost: ${ai.breakeven_price:.2f}")
                    if st.button(f"ACQUIRE (${buyout_cost:,.0f})", key=f"buy_{i}", disabled=(player.cash < buyout_cost)):
                        attempt_buyout(i)
                else:
                    st.caption("❌ BANKRUPT / ACQUIRED")
                st.divider()
                
    # 4. MARKET ROW (With Inventory Logic)
    st.subheader("🛒 Capital Improvements")
    
    inventory_full = len(player.cards) >= 4
    if inventory_full:
        st.error("⚠️ **Inventory Full (4/4):** You must scrap an asset below to buy a new one.")
    
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
            
            disable_btn = (st.session_state.pending_card is not None and not is_selected) or \
                          (player.cash < card['cost']) or \
                          (inventory_full and not is_selected)
            
            label = "DESELECT" if is_selected else "BUY"
            if col.button(label, key=f"card_{i}", disabled=disable_btn):
                select_card(i)
                st.rerun()

    # 5. PLAYER ASSETS
    if player.cards:
        st.markdown("### 🏚️ Your Assets (Max 4)")
        ac_cols = st.columns(4)
        for i, c in enumerate(player.cards):
            with ac_cols[i % 4]:
                st.success(f"{c['icon']} {c['name']}")
                if st.button("❌ SCRAP", key=f"scrap_{i}", help="Destroy this asset to make room."):
                    scrap_asset(i)

    # 6. CHART
    if len(st.session_state.history) > 1:
        st.markdown("### Market History")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=st.session_state.history['Season'], y=st.session_state.history['PlayerCash'], name='Your Cash', line=dict(color='green')))
        fig.add_trace(go.Scatter(x=st.session_state.history['Season'], y=st.session_state.history['TycoonCash'], name='Tycoon Cash', line=dict(color='red')))
        fig.add_trace(go.Scatter(x=st.session_state.history['Season'], y=st.session_state.history['Price'], name='Spot Price', line=dict(color='blue', dash='dot'), yaxis='y2'))
        
        fig.update_layout(
            yaxis=dict(title="Cash Balance"),
            yaxis2=dict(title="Spot Price ($)", overlaying='y', side='right'),
            legend=dict(orientation="h", y=1.1)
        )
        st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()