# Application Defaults
THEME = (
    "darkly"  # cosmo, litera, minty, pulse, sandstone, solar, superhero, flatly, darkly
)

PASSWORD_MIN_LENGTH = 3

VERSION = "0.25"
DB_NAME = "outline.db"  # default db it will look for or create
GLOBAL_FONT_FAMILY = "Helvetica"  # Set the global font family
GLOBAL_FONT_SIZE = 12  # Set the global font size
GLOBAL_FONT = (GLOBAL_FONT_FAMILY, GLOBAL_FONT_SIZE)

# DOCX Exports
DOC_FONT = "Helvetica"
H1_SIZE = 18
H2_SIZE = 15
H3_SIZE = 12
H4_SIZE = 10
P_SIZE = 10
INDENT_SIZE = 0.25


# Timer
COLOR_THRESHOLDS = {
    "red": 100,       # Above 000 ms -> RED
    "orange": 50,     # 50-100 ms -> ORANGE
    "yellow": 20,     # 20-50 ms -> YELLOW
    "green": 10         # Below 20 ms -> GREEN
}