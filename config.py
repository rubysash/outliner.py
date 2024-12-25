# Application Defaults
THEME = (
    "darkly"  # cosmo, litera, minty, pulse, sandstone, solar, superhero, flatly, darkly
)
VERSION = "0.31"
DB_NAME = "outline.db"  # default db it will look for or create
PASSWORD_MIN_LENGTH = 3

# UI Fonts
GLOBAL_FONT_FAMILY = "Helvetica"  # Set the global font family
GLOBAL_FONT_SIZE = 12  # Set the global font size
GLOBAL_FONT = (GLOBAL_FONT_FAMILY, GLOBAL_FONT_SIZE)
NOTES_FONT_FAMILY = "Consolas"  # Set the notes font family
NOTES_FONT_SIZE = 10  # Set the notes font size
NOTES_FONT = (NOTES_FONT_FAMILY, NOTES_FONT_SIZE)

# DOCX Exports
DOC_FONT = "Helvetica"
H1_SIZE = 18
H2_SIZE = 15
H3_SIZE = 12
H4_SIZE = 10
P_SIZE = 10
INDENT_SIZE = 0.25


# Timer Settings
TIMER_ENABLED = True                  # Enable/disable all performance monitoring
MIN_TIME_IN_MS_THRESHOLD = 19.0        # Only show operations taking longer than this
MAX_TIME_IN_MS_THRESHOLD = 2000.0     # Don't show operations taking longer than this

# Timer color thresholds (only for operations under MAX_TIME_IN_MS_THRESHOLD)
COLOR_THRESHOLDS = {
    "red": 100,       # Above 100 ms -> RED
    "orange": 50,     # 50-100 ms -> ORANGE
    "yellow": 20,     # 20-50 ms -> YELLOW
    "green": 10        # Below 10 ms -> GREEN
}

'''
Versions
.31 - STABLE - Load DB holding encryption from other db

.30 - STABLE. Adjusted initialize password to exit if cancelled

.29 - STABLE. Adjusted verbosity of timer

.28 - STABLE. New DB cache and optimizations

.27 - STABLE. Fonts for Notes section

.26 - STABLE. fixed search
Removed the old search controls and replaced them with a new search frame
Added proper grid layout for the search components
Added the global search checkbox with the BooleanVar
Proper binding for the Enter key to execute search
Search decrypts specific keys only, or global with warning
Keys are cached for 300s before decrypting again
Treeview shows plaintext vs encrypted (bug fix)



.25 - DEV. movement works, lazy loading, cached keys, search not working
'''