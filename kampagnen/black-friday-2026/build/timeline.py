"""Shared timeline for the Home Deluxe Black Friday spot (all times in seconds)."""
FPS = 30
SRC_FRAMES = 881            # source video frames (29.367 s)
OUT_DURATION = 29.9         # final length (animated end card incl. CTA tap)
OUT_FRAMES = int(round(OUT_DURATION * FPS))

# Hard cuts in the source edit (frame-accurate, from frame-difference analysis)
CUT_FREEZE = 121 / FPS      # 4.033  colour -> B&W freeze frame
CUT_GARDEN = 157 / FPS      # 5.233  freeze -> garden (beat drop)
CUT_SAUNA = 406 / FPS       # 13.533 sauna flies in
CUT_WIDE = 640 / FPS        # 21.333 wide shot with both products
CUT_END = 791 / FPS         # 26.367 end card

# Physical events in the footage
FENCE_THUDS = [6.60, 6.93, 7.13, 7.50, 7.86, 8.15, 8.50, 8.98, 9.40, 9.80, 10.18]
SAUNA_LAND = 15.15
WHIRL_IN = 17.33
WHIRL_LAND = 18.45

# Music grid: 11 bars exactly between the drop and the end card
BAR = (CUT_END - CUT_GARDEN) / 11.0   # 1.9212 s  (~124.9 BPM)
BEAT = BAR / 4.0
DROP_A = CUT_GARDEN                   # bars 0..7
BREAK = DROP_A + 8 * BAR              # 20.603  one-bar break
DROP_B = DROP_A + 9 * BAR             # 22.524  re-drop on "2.700"
END_HIT = CUT_END

# Subtitles (TikTok classic), cleaned-up wording + product names
SUBS = [
    (0.00, 1.20, "Leute, Leute,"),
    (1.26, 1.90, "Black Friday!"),
    (1.94, 3.00, "Es gibt wieder 10 % Rabatt."),
    (3.06, 4.00, "Ich dreh durch!"),
    (4.26, 5.66, "Schluss mit Minirabatten."),
    (5.74, 6.36, "Nicht 15,"),
    (6.40, 7.20, "nicht 20,"),
    (7.24, 9.36, "25 % auf alles."),
    (9.46, 10.40, "Klingt nach wenig?"),
    (10.46, 11.36, "Zaun Alira:"),
    (11.40, 13.50, "über 280 € gespart."),
    (13.74, 15.22, "Sauna Lagom Deluxe:"),
    (15.28, 17.45, "über 1.200 €."),
    (17.62, 19.10, "Whirlpool Stream Big:"),
    (19.16, 20.80, "noch mal über 1.200."),
    (21.08, 23.98, "Zusammen über 2.700 €,"),
    (24.04, 26.30, "nur am Black-Friday-Wochenende."),
]
