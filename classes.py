# classes.py
import config

class Farm:
    def __init__(self, name, sheds, cash, personality="Normal", is_player=False):
        self.name = name
        self.sheds = sheds
        self.cash = cash
        self.debt = 0.0 
        self.is_player = is_player
        self.personality = personality 
        
        # New Flag for Margin Call Default
        self.credit_damaged = False
        
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
        # Inventory haircut set to 0.4 (was 1.5 in original code)
        return self.cash + (self.sheds * config.SHED_COST * 0.8) + (self.inventory * 0.4)

    def get_ltv(self):
        assets = self.get_asset_value()
        if assets <= 0: return 9.99 
        return self.debt / assets

    def get_interest_rate(self):
        # 1. Permanent Penalty Check
        if self.credit_damaged:
            return config.RATE_JUNK
            
        # 2. Standard Matrix
        ltv = self.get_ltv()
        if ltv < config.TIER_1_LTV: return config.RATE_PRIME
        elif ltv < config.TIER_2_LTV: return config.RATE_MEZZ
        else: return config.RATE_JUNK

    def update_valuation(self):
        # 1. Liquidation Value (Net of Debt)
        asset_val = (self.sheds * config.SHED_COST) + sum(c['cost'] for c in self.cards) + (self.inventory * 1.0)
        liquidation_value = (self.cash + asset_val) - self.debt
        
        # 2. Earnings Value (4x EBITDA) (Net of Debt)
        estimated_base_ebitda = self.sheds * config.BASE_PROD * 1.0 
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