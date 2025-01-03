# Application Defaults
THEME = (
    "darkly"  # cosmo, litera, minty, pulse, sandstone, solar, superhero, flatly, darkly
)
VERSION = "0.49"
DB_NAME = "outline.db"  # default db it will look for or create
PASSWORD_MIN_LENGTH = 3

# WARNING FOR DECRYPTION TIMES
WARNING_LIMIT_ITEM_COUNT = 20   # decrypt/encrypt more than this amount, will give warning
WARNING_DISPLAY_TIME_MS = 3000  # How long warning shows (3 seconds)

# UI Fonts
GLOBAL_FONT_FAMILY = "Helvetica"  # Set the global font family
GLOBAL_FONT_SIZE = 14  # Set the global font size
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
    "yellow": 20,     # 20-50 ms -> YELLOWgit 
    "green": 10        # Below 10 ms -> GREEN
}


# Version Info
'''
.49 - STABLE minor ui issues related to scaling fonts and password dialogue
removed ok/cancel and confirmed enter/escape for passwords/changing passwords
.48 - STABLE added default file names for all exports
.47 - STABLE found/fixed export bug for json, and keybinding bug for headers 1//4
rearranged Readme in DB
added notes on colors, reorganized colors of buttons
changed button order and method names for consistentcy
.46 - DEV Export section as db, pdf, docx, json
Wrote unittest, 1st attempt.
.45 - STABLE Expand/Collapse all children context
refactored recursive tree refresh
.44 - STABLE Clone Everything option
.43 - STABLE db_dump.py troubleshooting tool was not dumping all tables, corrected
Clone section (titles only)
.42 - STABLE Right click Notes copy, paste, select all
.41 - STABLE Right click tree delete node
.40 - STABLE Right click tree add section to tree
moved password management to it's own class, can't force autofocus from CLI
.39 - STABLE - colorama init somehow vanished, re-added.
set {PASSWORD_MIN_LENGTH} everywhere instead of hard coding
.38 - STABLE - Deleting of entire trees, with warning added
.37 - STABLE added pdf export like docx/json
.36 - STABLE controls for export all/some because no "unselect" exists
added dynamic title version, db file name, # records
.35 - STABLE node exports for json and docx working.
Error in json imports fixed, padding was required
.34 - DEV - Export JSON/Import seems broken at moment
.34 - Fixed saving text was stripping blank lines.  
Change to rstrip only and preserve blank lines
.33 - STABLE - Only exports selected sections to docx
.32 - STABLE - Properly decrypts for docx export
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


# 40000d6f
