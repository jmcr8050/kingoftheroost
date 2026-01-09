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

def init_game():
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
    
    st.session_state.player = Farm("You", config.SHED_START_COUNT, 2500.0, personality="Player", is_player=True)
    st.session_state.player.update_valuation() 
    
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
    
    multiplier = 1.1 
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
        
        if ai_index == 2: 
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

def execute_turn(player_capacity, player_sell_pct, player_build_req):
    player = st.session_state.player
    opponents = st.session_state.opponents
    
    st.session_state.last_net_borrowing = 0 
    player.spent_last_turn = 0
    for ai in opponents: ai.spent_last_turn = 0
    
    # 1. Construction
    if player_build_req and player.cash >= config.SHED_COST:
        player.cash -= config.SHED_COST
        player.sheds += 1
        player.spent_last_turn += config.SHED_COST
        
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
            if random.random() < chance: fine = config.REGULATORY_FINE
        
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
        
        net_inv_change = farm.temp_prod - farm.temp_sales 
        
        # Expenses
        prod_bonus = sum(c.get('prod_bonus', 0) for c in farm.cards)
        cap = player_capacity if farm.is_player else farm.temp_capacity
        produced_this_turn = farm.sheds * (config.BASE_PROD + prod_bonus) * cap
        
        opex = produced_this_turn * farm.breakeven_price
        fixed_cost = farm.sheds * config.FIXED_COST_PER_SHED
        interest = farm.debt * farm.get_interest_rate()
        
        has_freezer = any(c.get('storage_save', False) for c in farm.cards)
        store_rate = config.STORAGE_COST_PER_UNIT * 0.5 if has_freezer else config.STORAGE_COST_PER_UNIT
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
            st.session_state.market_cards[i] = random.choice(config.CARDS_DB)

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