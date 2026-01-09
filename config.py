# config.py

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
    {"name": "The Quant", "type": "Emp", "cost": 1000, "salary": 100, "desc": "Forecasts Markets (Accuracy ↑ with tenure)", "icon": "🔮"},
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