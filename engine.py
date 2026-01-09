# engine.py
import streamlit as st
import random
import pandas as pd
import config
from classes import Farm

def init_deck():
    deck = []
    for evt, count in config.EVENT_DECK_COMPOSITION.items():
        deck.extend([evt] * count)
    random.shuffle(deck)
    deck.insert(0, "Normal")
    deck.insert(0, "Normal")
    return deck

def draw_event():
    if not st.session_state.event_deck:
        return "Normal" 
    return st.session_state.event_deck.pop(0)

# --- QUANT / ANALYST LOGIC ---
def update_quant_prediction():
    player = st.session_state.player
    quant_card = next((c for c in player.cards if c['name'] == "The Quant"), None)
    
    if not quant_card:
        st.session_state.quant_prediction = None
        return

    # Calculate Tenure
    hired_at = quant_card.get('hired_season', st.session_state.season)
    tenure = st.session_state.season - hired_at
    
    # Determine Accuracy Tier
    if tenure < 2:
        accuracy = 0.50
        status = "Rookie (50% Conf)"
    elif tenure < 5:
        accuracy = 0.80
        status = "Junior (80% Conf)"
    else:
        accuracy = 1.0
        status = "Senior (100% Conf)"

    # The Roll (Deterministic for this turn)
    true_event = st.session_state.next_event_name
    
    if random.random() < accuracy:
        pred = true_event
    else:
        options = [e for e in config.EVENTS.keys() if e != true_event]
        pred = random.choice(options)
        
    st.session_state.quant_prediction = {
        "prediction": pred,
        "status": status,
        "is_correct": (pred == true_event)
    }

# --- INITIALIZATION WITH PROFILES ---
def init_game(profile="founder"):
    st.session_state.game_active = True
    st.session_state.season = 1
    st.session_state.market_cards = random.sample(config.CARDS_DB, 4)
    st.session_state.game_over_msg = ""
    st.session_state.pending_card = None
    st.session_state.show_summary = False
    st.session_state.last_total_supply = 500
    st.session_state.event_deck = init_deck()
    st.session_state.next_event_name = draw_event()
    st.session_state.last_net_borrowing = 0
    st.session_state.quant_prediction = None
    
    # --- CEO LOADOUT LOGIC ---
    cards = []
    
    if profile == "shark": # Raider
        start_cash = 6000.0
        start_sheds = 3
        start_debt = 3500.0
    elif profile == "farmer": # Farmer
        start_cash = 200.0
        start_sheds = 5
        start_debt = 1500.0
        c = next(c for c in config.CARDS_DB if c['name'] == "Master Breeder").copy()
        cards = [c]
    elif profile == "tech": # Disruptor
        start_cash = 1000.0
        start_sheds = 3
        start_debt = 0.0
        c1 = next(c for c in config.CARDS_DB if c['name'] == "Solar Grid").copy()
        c2 = next(c for c in config.CARDS_DB if c['name'] == "Efficiency Expert").copy()
        cards = [c1, c2]
    elif profile == "insider": # Insider
        start_cash = 1500.0
        start_sheds = 3
        start_debt = 0.0
        c1 = next(c for c in config.CARDS_DB if c['name'] == "The Quant").copy()
        # Set hired season to -1 so (1 - (-1)) = Tenure 2 (Junior)
        c1['hired_season'] = -1 
        cards = [c1]
    else: # Founder
        start_cash = 2500.0
        start_sheds = 3
        start_debt = 0.0
        cards = []

    st.session_state.player = Farm("You", start_sheds, start_cash, personality="Player", is_player=True)
    st.session_state.player.debt = start_debt
    st.session_state.player.cards = cards
    st.session_state.player.recalculate_breakeven()
    st.session_state.player.update_valuation() 
    
    if profile == "insider":
        update_quant_prediction()
    
    # Init Opponents
    st.session_state.opponents = [
        Farm("Small Fry", 3, 2000.0, personality="Conservative"),
        Farm("The Upstart", 4, 3000.0, personality="Aggressive"),
        Farm("THE TYCOON", 6, 4000.0, personality="Predatory")
    ]
    st.session_state.opponents[2].add_card(config.CARDS_DB[2]) 
    
    for ai in st.session_state.opponents:
        ai.recalculate_breakeven()
        ai.update_valuation() 
    
    st.session_state.history = pd.DataFrame(columns=["Season", "Price", "PlayerCash", "TycoonCash"])

# --- AI LOGIC ---
def get_ai_decision(ai: Farm, player: Farm, market_cards):
    variance = random.uniform(0.9, 1.1) 
    wants_to_build = False
    card_idx = None
    capacity = 1.0
    sell_pct = 1.0 
    
    # 0. SURVIVAL CHECK
    est_interest = ai.debt * ai.get_interest_rate()
    burn_rate = (ai.sheds * config.FIXED_COST_PER_SHED) + est_interest
    if ai.cash < (burn_rate * 2.0):
        return False, None, 1.0, 1.0 # Panic Mode

    # 1. Expansion
    if ai.personality == "Conservative":
        if ai.cash > (config.SHED_COST * 2.5 * variance): wants_to_build = True
    elif ai.personality == "Aggressive" or ai.personality == "Predatory":
        if ai.cash > (config.SHED_COST * 1.5 * variance): wants_to_build = True

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

# --- PLAYER ACTIONS ---
def instant_borrow(amount):
    player = st.session_state.player
    assets = player.get_asset_value()
    max_debt = assets * config.MAX_LTV
    if (player.debt + amount) > max_debt:
        return 
    player.debt += amount
    player.cash += amount
    st.session_state.last_net_borrowing += amount

def instant_repay(amount):
    player = st.session_state.player
    actual = min(amount, player.cash, player.debt)
    player.debt -= actual
    player.cash -= actual
    st.session_state.last_net_borrowing -= actual

def attempt_buyout(ai_index):
    player = st.session_state.player
    target = st.session_state.opponents[ai_index]
    
    # 1. Calculate Purchase Price (Equity Value)
    multiplier = 1.1 
    if target.cash < 500: multiplier = 0.8 
    equity_cost = max(1.0, target.valuation * multiplier)
    
    # 2. Check Feasibility
    if player.cash < equity_cost:
        st.error(f"Insufficient Cash. Need ${equity_cost:,.0f} (Equity Value).")
        return

    # 3. Bank Covenant (Pro Forma LTV)
    combined_debt = player.debt + target.debt
    pro_forma_cash = (player.cash - equity_cost) + target.cash
    pro_forma_sheds = player.sheds + target.sheds
    pro_forma_inv = player.inventory + target.inventory
    
    combined_assets = pro_forma_cash + (pro_forma_sheds * config.SHED_COST * 0.8) + (pro_forma_inv * 0.4)
    pro_forma_ltv = combined_debt / combined_assets if combined_assets > 0 else 9.99
    
    if pro_forma_ltv > config.MAX_LTV:
        st.error(f"⛔ DEAL BLOCKED BY BANK. Pro Forma LTV ({pro_forma_ltv:.1%}) exceeds 70%.")
        return

    # 4. EXECUTE DEAL
    player.cash -= equity_cost
    player.sheds += target.sheds
    player.inventory += target.inventory
    player.debt += target.debt # ASSUME DEBT
    player.cash += target.cash
    
    for c in target.cards: 
        if len(player.cards) < 4:
            player.add_card(c)
            
    target.bankrupt = True
    target.name = f"Owned by {player.name}"
    target.sheds = 0
    target.cash = 0
    target.debt = 0
    
    if ai_index == 2: 
        st.session_state.game_active = False
        st.session_state.game_over_msg = "🏆 VICTORY! You acquired The Tycoon. Monopoly achieved."
        st.rerun()
        
    st.success(f"Acquired {target.name}! Assumed ${target.debt:,.0f} debt.")
    st.rerun()

def perform_bailout():
    player = st.session_state.player
    deficit = abs(player.cash)
    buffer = 500
    total_rescue = deficit + buffer
    player.cash += total_rescue
    player.debt += total_rescue
    player.credit_damaged = True
    st.toast(f"Rescue Financing Secured. Rate locked at 15%.")
    st.rerun()

def select_card(idx):
    if st.session_state.pending_card == idx: st.session_state.pending_card = None
    else: st.session_state.pending_card = idx

def scrap_asset(idx):
    st.session_state.player.scrap_card(idx)
    st.rerun()

# --- MAIN TURN LOGIC ---
def execute_turn(player_capacity, player_sell_pct, player_build_req):
    player = st.session_state.player
    opponents = st.session_state.opponents
    profile = st.session_state.ceo_profile
    
    st.session_state.last_net_borrowing = 0 
    player.spent_last_turn = 0
    for ai in opponents: ai.spent_last_turn = 0
    
    # 1. Construction (With Disruptor Penalty)
    build_cost = config.SHED_COST
    if profile == "tech": build_cost = 1500
        
    if player_build_req and player.cash >= build_cost:
        player.cash -= build_cost
        player.sheds += 1
        player.spent_last_turn += build_cost
        
    # 2. Purchasing
    if st.session_state.pending_card is not None:
        c_idx = st.session_state.pending_card
        card = st.session_state.market_cards[c_idx]
        if len(player.cards) < 4:
            if card and player.cash >= card['cost']:
                player.cash -= card['cost']
                if card['name'] == "The Quant":
                    card['hired_season'] = st.session_state.season
                player.add_card(card)
                player.spent_last_turn += card['cost']
                st.session_state.market_cards[c_idx] = None 
                if card['name'] == "The Quant":
                    update_quant_prediction()
    st.session_state.pending_card = None 

    # AI Actions
    for ai in opponents:
        if ai.bankrupt: continue
        build, card_idx, cap_pct, sell_pct = get_ai_decision(ai, player, st.session_state.market_cards)
        ai.temp_capacity = cap_pct
        ai.temp_sell_pct = sell_pct
        if build:
            ai.cash -= config.SHED_COST
            ai.sheds += 1
            ai.spent_last_turn += config.SHED_COST
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
    evt_data = config.EVENTS[evt_name]
    current_demand = config.BASE_DEMAND * evt_data['demand_mod']
    total_supply_produced = 0
    
    all_farms = [player] + opponents
    
    for farm in all_farms:
        if farm.bankrupt: continue
        if farm.is_player: cap = player_capacity
        else: cap = farm.temp_capacity
            
        prod_bonus = sum(c.get('prod_bonus', 0) for c in farm.cards)
        raw_prod = farm.sheds * (config.BASE_PROD + prod_bonus) * cap
        
        fine = 0.0
        if cap > 1.0:
            chance = (cap - 1.0) * config.FINE_CHANCE_SCALER
            if random.random() < chance: 
                base_fine = config.REGULATORY_FINE
                # Insider Penalty
                if farm.is_player and profile == "insider": base_fine = 1200
                fine = base_fine
        
        farm.temp_prod = raw_prod
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
        net_inv_change = farm.temp_prod - farm.temp_sales 
        
        # Expenses
        prod_bonus = sum(c.get('prod_bonus', 0) for c in farm.cards)
        cap = player_capacity if farm.is_player else farm.temp_capacity
        produced_this_turn = farm.sheds * (config.BASE_PROD + prod_bonus) * cap
        
        opex = produced_this_turn * farm.breakeven_price
        salary_cost = sum(c.get('salary', 0) for c in farm.cards)
        fixed_cost = (farm.sheds * config.FIXED_COST_PER_SHED) + salary_cost
        interest = farm.debt * farm.get_interest_rate()
        
        has_freezer = any(c.get('storage_save', False) for c in farm.cards)
        store_rate = config.STORAGE_COST_PER_UNIT * 0.5 if has_freezer else config.STORAGE_COST_PER_UNIT
        storage_fees = farm.inventory * store_rate
        
        profit = revenue - opex - fixed_cost - farm.temp_fine - storage_fees - interest
        
        # AI EMERGENCY BORROWING
        if not farm.is_player and (farm.cash + profit) < 0:
            deficit = -(farm.cash + profit)
            target_buffer = 500
            needed = deficit + target_buffer
            assets = farm.get_asset_value()
            max_borrow = (assets * config.MAX_LTV) - farm.debt
            if max_borrow > 0:
                borrow_amount = min(needed, max_borrow)
                farm.debt += borrow_amount
                farm.cash += borrow_amount
        
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
        
        # BANKRUPTCY CHECK (With Rescue Logic for Player)
        if farm.cash < 0:
            if farm.is_player:
                # Check Solvency
                hard_assets = (farm.sheds * config.SHED_COST * 0.8) + (farm.inventory * 0.4)
                needed = abs(farm.cash)
                pro_forma_debt = farm.debt + needed
                if hard_assets > 0 and (pro_forma_debt / hard_assets) <= config.MAX_LTV:
                    pass # Allow Bailout in UI
                else:
                    farm.bankrupt = True
            else:
                farm.bankrupt = True

    # Cleanup
    for i in range(4):
        if st.session_state.market_cards[i] is None:
            st.session_state.market_cards[i] = random.choice(config.CARDS_DB)

    st.session_state.season += 1
    st.session_state.next_event_name = draw_event()
    update_quant_prediction()
    st.session_state.show_summary = True
    
    tycoon = opponents[2]
    new_hist = {"Season": st.session_state.season-1, "Price": market_price, "PlayerCash": player.cash, "TycoonCash": tycoon.cash}
    st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([new_hist])], ignore_index=True)

    if opponents[2].bankrupt:
        st.session_state.game_active = False
        st.session_state.game_over_msg = "🏆 VICTORY! The Tycoon has gone bankrupt."
        
    if st.session_state.season > 40:
        st.session_state.game_active = False
        st.session_state.game_over_msg = "💀 GAME OVER: Time is up."