"""Shared timeline for the v4 Home Deluxe Black Friday spot (all times in seconds).

All footage is AI-generated in Higgsfield (see README); the picture is assembled by
assemble_v4.py, the voice-over by vo_v4.py. Names of the v3 constants are kept where the
renderer / sound design re-use them.
"""
FPS = 24
OUT_DURATION = 34.40
OUT_FRAMES = int(round(OUT_DURATION * FPS))

# scene cuts (see assemble_v4.py)
CUT_UGC = 5.40          # S1 UGC  -> S2 camera flies through the patio door (zoom-through)
CUT_FREEZE = CUT_UGC    # (v3 name) record-scratch moment of the music
CUT_GARDEN = 7.40       # S2 -> S3a: camera lands in the garden, beat drop
CUT_FENCE_HERO = 13.13  # S3a -> S3b seamless (identical keyframe)
CUT_SAUNA = 18.75       # S3b -> S4 whip pan, sauna falls in
CUT_WHIRL = 22.42       # S4 -> S5 crash zoom, whirlpool falls in
CUT_WIDE = 26.17        # S5 -> S6 spin zoom into the blue-hour hero shot
CUT_END = 31.30         # S6 -> end card (zoom into the savings box)

# physical events measured in the generated clips (motion analysis)
FENCE_THUDS = [7.56, 8.18, 8.76, 9.25, 9.75, 10.14, 10.50, 11.37]
SAUNA_LAND = 20.09
WHIRL_IN = CUT_WHIRL
WHIRL_LAND = 23.04

# music grid: 12 bars between the drop and the end card (~120.5 BPM)
BAR = (CUT_END - CUT_GARDEN) / 12.0
BEAT = BAR / 4.0
DROP_A = CUT_GARDEN
GROOVE_BARS = 9
BREAK = DROP_A + 9 * BAR      # one-bar break under the spin into the hero shot
DROP_B = DROP_A + 10 * BAR    # re-drop on "2.700"
END_HIT = CUT_END

SUBS = [
    (0.00, 1.10, "Leute, Leute,"),
    (1.12, 2.20, "Black Friday!"),
    (2.24, 4.24, "Es gibt wieder 10 % Rabatt."),
    (4.28, 5.40, "Ich dreh durch."),
    (5.62, 7.40, "Schluss mit Minirabatten."),
    (7.95, 9.12, "Nicht 15,"),
    (9.15, 10.47, "nicht 20,"),
    (10.51, 13.10, "25 % auf alles."),
    (13.83, 15.36, "Klingt nach wenig?"),
    (15.41, 16.42, "Zaun Alira:"),
    (16.45, 19.15, "über 280 € gespart."),
    (19.21, 20.80, "Sauna Lagom Deluxe:"),
    (20.83, 22.72, "über 1.200 €."),
    (22.77, 24.42, "Whirlpool Stream Big:"),
    (24.45, 26.30, "noch mal über 1.200."),
    (26.35, 29.02, "Zusammen über 2.700 €,"),
    (29.04, 31.25, "nur am Black-Friday-Wochenende."),
]

# counter (start, landing) — lands while the amount is spoken
COUNTERS = {"fence": (16.50, 17.19), "sauna": (20.88, 21.50), "whirl": (24.76, 25.58), "total": (27.10, 27.95)}

T = dict(
    bf=1.16, ten=2.84, strike10=4.32, fall10=4.70,
    n15_in=7.95, n15_strike=8.62, n15_out=9.14,
    n20_in=9.18, n20_strike=10.12, n20_out=10.38,
    slam25=10.53, auf=12.18, wobble=99.0, out25=12.92,
    banner=29.03, home=31.88,
    fence_card=15.35, sauna_card=20.25, whirl_card=23.30,
    sum_chips=(26.50, 26.62, 26.74), merge=(26.95, 27.13), total_in=27.03,
)

SRC_FRAMES = int(round(CUT_END * FPS))   # frames of base_v4.mp4

# graphic anchors measured on the generated footage (1080x1920)
HOOK_POS = {"badge": (540, 200), "ten": (895, 560), "door": (880, 420)}
ANCHORS = {
    "fence": [(15.35, (840, 780)), (18.75, (690, 900))],
    "sauna": [(20.25, (520, 800)), (22.42, (450, 770))],
    "whirl": [(23.30, (770, 900)), (26.17, (720, 880))],
}
SHOCK_POS = {"fence": (760, 1100), "sauna": (430, 1250), "whirl": (720, 1250)}
