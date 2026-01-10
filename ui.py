# ui.py
import streamlit as st
import plotly.graph_objects as go
import config
import engine

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
    if st.button("🔄 Return to CEO Selection", type="primary"):
        st.session_state.game_state = "WELCOME"
        st.rerun()

@st.dialog("Quarterly Report", width="large")
def show_season_summary_dialog():
    player = st.session_state.player
    log = player.last_turn_log
    
    st.subheader(f"Season {st.session_state.season - 1} Performance")
    
    # --- UPDATED HEADER SECTION ---
    # We display the Event and the resulting Market Price side-by-side
    
    col_evt, col_price = st.columns([3, 1])
    
    with col_evt:
        evt_label = f"**MARKET EVENT:** {log['Event_Name']} ({log['Event_Desc']})"
        if log['Event_Bad']: st.error(evt_label)
        else: st.success(evt_label)
        
    with col_price:
        # Display the Clearing Price big and bold
        st.metric("Clearing Price", f"${log['Price']:.2f}", help="Final price per bird based on supply/demand")

    st.divider()

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
    # Added reference to Price here as well for clarity
    c1.write(f"➕ **Revenue** ({int(log['Sales']):,} birds x ${log['Price']:.2f})")
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

    # 3. CASH FLOW & SOLVENCY
    st.markdown("### 💵 Liquidity Position")
    
    start_cash_op = player.cash - log['Profit']
    cf1, cf2, cf3 = st.columns(3)
    cf1.metric("Start Cash", f"${start_cash_op:,.0f}")
    cf2.metric("Net Income", f"${log['Profit']:+,.0f}")
    color = "red" if player.cash < 0 else "green"
    cf3.markdown(f"**End Cash:** :{color}[${player.cash:,.0f}]")

    if player.cash < 0:
        if player.bankrupt:
            st.error("🚨 **INSOLVENCY:** Liabilities exceed Assets. The bank has seized your farm.")
            if st.button("Accept Bankruptcy", type="primary"):
                st.session_state.show_summary = False
                st.session_state.game_active = False
                st.session_state.game_over_msg = f"GAME OVER: Bankrupt in Season {st.session_state.season - 1}"
                st.rerun()
        else:
            st.warning("⚠️ **MARGIN CALL:** Account Overdrawn.")
            st.markdown("""
            You are out of cash, but your hard assets verify sufficient collateral for a **Rescue Loan**.
            
            **The Terms:**
            * Amount: Enough to cover deficit + $500 buffer.
            * **PENALTY:** Credit Rating downgraded to **JUNK (15%)** permanently.
            """)
            
            deficit = abs(player.cash)
            rescue_amt = deficit + 500
            new_debt = player.debt + rescue_amt
            hard_assets = (player.sheds * config.SHED_COST * 0.8) + (player.inventory * 0.4)
            pf_ltv = new_debt / hard_assets if hard_assets > 0 else 9.99
            
            c1, c2 = st.columns(2)
            c1.metric("Rescue Amount", f"${rescue_amt:,.0f}")
            c2.metric("Pro Forma LTV", f"{pf_ltv:.1%}")
            
            col_bail, col_die = st.columns([2, 1])
            if col_bail.button("✍️ Sign Rescue Financing (Rate -> 15%)", type="primary"):
                engine.perform_bailout()
            if col_die.button("Decline & Default"):
                player.bankrupt = True
                st.rerun()

    else:
        if st.button("Close & Start Next Season", type="primary"):
            st.session_state.show_summary = False
            st.rerun()

def render_dashboard():
    # If game ended (Win/Loss), show report and exit
    if not st.session_state.game_active:
        st.title("King of the Roost")
        st.caption("Supply, Demand, and Hostile Takeovers")
        if st.session_state.game_over_msg:
            draw_end_game_report()
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
    max_capacity = player.sheds * (config.BASE_PROD + prod_bonus)
    
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Season", f"{st.session_state.season}/40")
    m2.metric("Cash", f"${player.cash:,.0f}")
    m3.metric("Debt", f"${player.debt:,.0f}")
    m4.metric("Sheds", f"{player.sheds}")
    m5.metric("Max Capacity", f"{max_capacity:,.0f}", help="Chicken production at 100% utilization")
    m6.metric("Inventory", f"{int(player.inventory):,}") # New Metric
    
    # --- RESTORED MISSION BRIEF ---
    with st.expander("📖 Mission Brief & Rules of Engagement", expanded=False):
        c_info1, c_info2 = st.columns(2)
        with c_info1:
            st.markdown("""
            **The Situation**
            **Apex Global Foods** is entering the market in exactly **10 Years (40 Seasons)**. 
            They will acquire the regional monopoly for a massive premium.
            
            * **Goal:** Be the last farm standing OR Own 100% of the market (Monopoly).
            * **The Threat:** If **The Tycoon** is still alive at Season 40, he wins the deal. You get nothing.
            * **Game Over:** If Cash hits < $0 and you have no assets to borrow against, you are liquidated.
            """)
        with c_info2:
            st.markdown("""
            **Mechanics**
            * **Price:** Determined by Total Supply vs. Demand. Withholding supply (Freezing) raises prices.
            * **Interest Rates:** 5% (Prime) → 9% (Mezz) → 15% (Junk). Rates jump if LTV > 30% or 60%.
            * **Debt Cap:** Banks will NOT lend if LTV > 70%.
            * **M&A:** You can buy competitors. You pay Equity Value but **assume their Debt**.
            * **Intel:** The "Quant" predicts demand, but is unreliable until he gains tenure.
            """)
    
    st.markdown("---")

    left_col, right_col = st.columns([1, 1])
    ops_tab, analyst_tab = left_col.tabs(["🎛️ Operations", "📊 Analyst"])

    with ops_tab:
        st.subheader("⚙️ Decisions")
        
        # FINANCE
        with st.expander("🏦 Corporate Finance (Debt Facility)", expanded=False):
            ltv = player.get_ltv()
            curr_rate = player.get_interest_rate()
            
            rating_color = "green"
            if curr_rate > 0.09: rating_color = "red"
            elif curr_rate > 0.05: rating_color = "orange"
            
            st.markdown(f"**Credit Rating:** :{rating_color}[{curr_rate*100:.0f}% Interest] (LTV: {ltv:.1%})")
            st.progress(min(ltv, 1.0))
            if ltv >= config.MAX_LTV: st.error("⛔ CREDIT LIMIT REACHED")

            fc1, fc2 = st.columns(2)
            if fc1.button("Borrow $1,000"):
                engine.instant_borrow(1000)
                st.rerun()
            if fc2.button("Repay $1,000"):
                engine.instant_repay(1000)
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
        
        if capacity_int == 0: st.caption(f"🛑 Mothballed (${player.sheds*config.FIXED_COST_PER_SHED} Fixed Cost)")
        elif capacity_int > 100: 
            risk = int((capacity - 1.0) * config.FINE_CHANCE_SCALER * 100)
            st.warning(f"🔥 Overclocked ({risk}% Fine Risk)")
        
        st.write("**Sales Strategy**")
        sell_int = st.slider("Sell %", 0, 100, 100)
        sell_pct = sell_int / 100.0
        if sell_int < 100: st.caption(f"❄️ Storing {100-sell_int}%")

        st.divider()
        st.subheader("🛒 Market")
        
        # Build Button with Dynamic Cost based on profile
        profile = st.session_state.ceo_profile
        build_cost = 1500 if profile == "tech" else config.SHED_COST
        
        can_build = player.cash >= build_cost
        build_btn = st.checkbox(f"Build Shed (${build_cost}) - Adds {config.BASE_PROD} Chickens", disabled=not can_build)
        
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
                        engine.select_card(i)
                        st.rerun()
            else:
                col.info("Sold")

        st.markdown("###")
        if st.button("🔴 RUN SEASON", type="primary", use_container_width=True):
            engine.execute_turn(capacity, sell_pct, build_btn)
            st.rerun()

    with analyst_tab:
        st.subheader("📊 Financial Models")
        
        with st.container(border=True):
            st.markdown("**1. Overclocking Risk Model (EV)**")
            st.caption("Should you push production beyond 100%?")
            
            an_cap = st.slider("Simulated Intensity", 0, 120, 100, key="an_cap") / 100.0
            last_p = player.last_turn_log.get('Price', 4.00)
            
            # Base Calcs
            est_vol = max_capacity * an_cap
            est_rev = est_vol * last_p
            
            # EV Calcs
            base_fine = config.REGULATORY_FINE
            if profile == "insider": base_fine = 1200 # Insider Penalty
            
            fine_prob = 0.0
            if an_cap > 1.0:
                fine_prob = (an_cap - 1.0) * config.FINE_CHANCE_SCALER
            
            expected_fine = base_fine * fine_prob
            net_ev = est_rev - expected_fine
            
            # Display
            c1, c2 = st.columns(2)
            c1.metric("Est. Volume", f"{int(est_vol)}")
            c2.metric("Est. Revenue", f"${est_rev:,.0f}", help="Assumes Price = Last Season's Price")
            
            if an_cap > 1.0:
                st.divider()
                st.markdown("#### 🎲 Expected Value Analysis")
                e1, e2, e3 = st.columns(3)
                e1.metric("Fine Risk", f"{int(fine_prob*100)}%")
                e2.metric("Expected Fine", f"-${expected_fine:.0f}")
                
                # EV Color Coding
                ev_color = "green" if (est_rev - expected_fine) > (max_capacity * last_p) else "orange"
                e3.markdown(f"**Net EV:** :{ev_color}[${net_ev:,.0f}]")
                
                if profile == "insider":
                    st.caption("⚠️ **Insider Penalty Active:** Fines are doubled.")
            
        with st.container(border=True):
            st.markdown("**2. Liquidity Stress Test**")
            st.caption("Can you survive a market crash to **$2.00**?")
            stress_prod = st.slider("Simulated Production %", 0, 100, 100, key="stress_slider") / 100.0
            stress_vol = max_capacity * stress_prod
            stress_rev = stress_vol * 2.00 
            stress_opex = stress_vol * player.breakeven_price
            stress_fixed = (player.sheds * config.FIXED_COST_PER_SHED) + (player.debt * curr_rate)
            net_stress = stress_rev - stress_opex - stress_fixed
            if net_stress < 0: 
                st.error(f"🔥 **Burn:** -${abs(net_stress):,.0f} / turn")
            else: 
                st.success(f"✅ **Survive:** +${net_stress:,.0f} / turn")

        with st.container(border=True):
            st.markdown("**3. M&A Deal Room**")
            target_names = [op.name for op in st.session_state.opponents if not op.bankrupt]
            if not target_names:
                st.info("No active targets.")
            else:
                sel_name = st.selectbox("Select Target", target_names)
                target = next(op for op in st.session_state.opponents if op.name == sel_name)
                mult = 1.1 if target.cash >= 500 else 0.8
                cost = target.valuation * mult
                synergy_per_turn = (4.00 - player.breakeven_price) - (4.00 - target.breakeven_price)
                total_synergy = synergy_per_turn * 80 * target.sheds
                total_synergy = max(0, total_synergy)
                c1, c2 = st.columns(2)
                c1.metric("Acq. Cost", f"${cost:,.0f}")
                c2.metric("Synergy/Turn", f"${total_synergy:,.0f}")
                if total_synergy > 0:
                    payback = cost / total_synergy
                    st.caption(f"Payback Period: **{payback:.1f} Seasons**")
                else:
                    st.caption("No operational synergy.")

    with right_col:
        st.subheader("📡 Market Intel")
        quant_data = st.session_state.get('quant_prediction')
        last_price = player.last_turn_log.get('Price', 4.00)
        st.caption(f"Last Season Clearing Price: **${last_price:.2f}**")
        
        with st.container(border=True):
            if quant_data:
                pred_evt = quant_data['prediction']
                status = quant_data['status']
                evt_bad = config.EVENTS[pred_evt]['bad']
                icon = "📉" if evt_bad else "📈"
                st.markdown(f"**Quant Forecast:** {icon} {pred_evt}")
                st.caption(f"Analyst Status: **{status}**")
                demand_impact = int((config.EVENTS[pred_evt]['demand_mod'] - 1.0) * 100)
                st.caption(f"Proj. Demand: {demand_impact:+}%")
                last_supply = st.session_state.get('last_total_supply', 2000)
                proj_demand = config.BASE_DEMAND * config.EVENTS[pred_evt]['demand_mod']
                proj_price = (proj_demand / last_supply) * 4.0
                st.metric("Model Price Target", f"${proj_price:.2f}")
            else:
                st.markdown("**Forecast:** 🔒 LOCKED")
                st.caption("Hire 'The Quant' ($1k + $100/turn) to unlock market predictions.")
        
        st.subheader("🎯 Competitors")
        for i, ai in enumerate(st.session_state.opponents):
            if not ai.bankrupt:
                with st.container(border=True):
                    c_head, c_btn = st.columns([2, 1])
                    c_head.markdown(f"**{ai.name}**")
                    
                    multiplier = 1.1
                    if ai.cash < 500: multiplier = 0.8 
                    equity_cost = max(1.0, ai.valuation * multiplier)
                    
                    btn_label = f"Buy (${equity_cost:,.0f})"
                    if ai.debt > 0:
                        btn_label = f"Buy (${equity_cost:,.0f} + ${ai.debt:,.0f} Debt)"
                    
                    can_afford = player.cash >= equity_cost
                    if c_btn.button(btn_label, key=f"acq_{i}", disabled=not can_afford):
                        engine.attempt_buyout(i)
                    
                    if ai.cash < 500: st.caption(":red[⚠️ DISTRESSED ASSET (20% OFF)]")

                    their_margin = 4.00 - ai.breakeven_price
                    your_margin = 4.00 - player.breakeven_price
                    delta = (your_margin - their_margin) * 80 
                    if delta > 0: st.caption(f"⚡ **Synergy:** +${delta:.0f}/shed profit.")
                    
                    s1, s2, s3, s4 = st.columns(4)
                    s1.caption(f"🏰 {ai.sheds}")
                    s2.caption(f"💰 ${ai.cash:,.0f}")
                    s3.caption(f"🏦 ${ai.debt:,.0f}")
                    s4.caption(f"📉 ${ai.breakeven_price:.2f}")

            else:
                st.caption(f"❌ {ai.name} (Eliminated)")

        if player.cards:
            st.divider()
            st.caption("Your Upgrades (Click to Scrap)")
            for i, c in enumerate(player.cards):
                if st.button(f"🗑️ {c['name']} ({c['desc']})", key=f"scrap_{i}"):
                    engine.scrap_asset(i)

    if len(st.session_state.history) > 1:
        st.divider()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=st.session_state.history['Season'], y=st.session_state.history['PlayerCash'], name='You', line=dict(color='green')))
        fig.add_trace(go.Scatter(x=st.session_state.history['Season'], y=st.session_state.history['TycoonCash'], name='Tycoon', line=dict(color='red')))
        fig.add_trace(go.Scatter(x=st.session_state.history['Season'], y=st.session_state.history['Price'], name='Price', line=dict(color='blue', dash='dot'), yaxis='y2'))
        fig.update_layout(height=300, margin=dict(t=0, b=0, l=0, r=0), yaxis2=dict(overlaying='y', side='right'))
        st.plotly_chart(fig, use_container_width=True)