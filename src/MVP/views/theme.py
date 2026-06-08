# src/MVP/views/theme.py

# --- Colors: (Light Mode, Dark Mode) ---
# App background: soft sky-blue by day, deep charcoal-blue at night
BG_MAIN = ("#e3f2f7", "#122330") 

# Card background - at night we added a subtle bluish tint instead of plain gray
BG_CARD = ("#ffffff", "#1e2b3c") 
BG_CARD_HOVER = ("#f8f9fa", "#263648")

BORDER_DEFAULT = ("#dee2e6", "#2c3e50")

# Unified accent color! Deep blue by day (for contrast), and glowing sky-blue at night
BORDER_ACTIVE = ("#0077b6", "#38b6ff")  

TEXT_MAIN = ("#212529", "#ffffff")
TEXT_MUTED = ("#6c757d", "#9ba4b5")
TEXT_ACCENT = ("#0077b6", "#38b6ff")

SUCCESS = ("#198754", "#2ecc71")
SUCCESS_HOVER = ("#157347", "#27ae60")

DANGER = ("#dc3545", "#ff4d4d")
DANGER_HOVER = ("#c82333", "#ff6b6b")

TRANSPARENT = "transparent"

# --- Radiuses ---
RADIUS_CARD = 16
RADIUS_BUTTON = 8 

# --- Spacings ---
SPACING_SMALL = 8
SPACING_REGULAR = 16
SPACING_LARGE = 24
SPACING_SECTION = 32

# --- Fonts ---
FONT_FAMILY = "Rubik"
FONT_ICON = "Segoe UI Emoji"