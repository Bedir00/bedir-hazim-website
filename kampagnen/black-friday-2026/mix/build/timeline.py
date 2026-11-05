"""Shared timeline of the MIX version (all times in seconds): new UGC hook + original product footage.

Same voice-over timeline as v4 (vo_v4.py). The picture is assembled by assemble_v5.py: new Higgsfield
UGC hook and door fly-through, then the product shots of the original spot re-timed to the VO.
"""
FPS = 24
OUT_DURATION = 34.40
OUT_FRAMES = int(round(OUT_DURATION * FPS))

# scene cuts (see assemble_v4.py)
CUT_UGC = 5.40          # S1 UGC  -> S2 camera flies through the patio door (zoom-through)
CUT_FREEZE = CUT_UGC    # (v3 name) record-scratch moment of the music
CUT_GARDEN = 7.40       # S2 -> original garden: burst through the patio door on the beat drop
CUT_FENCE_HERO = 13.13  # S3a -> S3b seamless (identical keyframe)
CUT_SAUNA = 18.75       # S3b -> S4 whip pan, sauna falls in
CUT_WHIRL = 22.42       # S4 -> S5 crash zoom, whirlpool falls in
CUT_WIDE = 26.17        # S5 -> S6 spin zoom into the blue-hour hero shot
CUT_END = 31.30         # S6 -> end card (zoom into the savings box)

# physical events measured in the generated clips (motion analysis)
# original spot (30 fps) -> mix timeline: fence drop 157..318 -> 7.40..13.13, sauna/whirl shot 406..640 -> 18.75..26.17
_fence = lambda s: CUT_GARDEN + (s - 157 / 30) / ((318 - 157) / 30 / (CUT_FENCE_HERO - CUT_GARDEN))
_sw = lambda s: CUT_SAUNA + (s - 406 / 30) / ((640 - 406) / 30 / (CUT_WIDE - CUT_SAUNA))
FENCE_THUDS = [round(_fence(s), 3) for s in (6.60, 6.93, 7.13, 7.50, 7.86, 8.15, 8.50, 8.98, 9.40, 9.80, 10.18)]
SAUNA_LAND = round(_sw(15.20), 3)      # dirt explosion
WHIRL_IN = round(_sw(17.33), 3)        # whirlpool enters the frame (no cut in the original shot)
WHIRL_LAND = round(_sw(18.95), 3)
WHIRL_XZOOM = False                    # v4 had a crash-zoom cut sauna -> whirlpool; here it is one continuous shot

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
    fence_card=15.35, sauna_card=20.40, whirl_card=23.30,
    sum_chips=(26.50, 26.62, 26.74), merge=(26.95, 27.13), total_in=27.03,
)

SRC_FRAMES = int(round(CUT_END * FPS))   # frames of base_v4.mp4

# graphic anchors measured on the generated footage (1080x1920)
HOOK_POS = {"badge": (540, 200), "ten": (895, 560), "door": (880, 420)}
# anchors on the original footage (source coordinates, before the slow push-ins below)
ANCHORS = {
    "fence": [(15.35, (420, 790)), (18.75, (420, 790))],
    "sauna": [(20.40, (560, 690)), (22.42, (560, 690))],
    "whirl": [(round(_sw(a), 3), p) for a, p in ((18.30, (560, 740)), (18.55, (560, 760)), (18.9, (560, 780)),
                                                  (20.9, (520, 860)), (21.4, (515, 870)))],
}
SHOCK_POS = {"fence": (540, 900), "sauna": (540, 1000), "whirl": (585, 1150)}
# slow digital push-ins on the (locked-off) original shots: (t0, t1, scale0, scale1, cx, cy)
KEN = [(CUT_GARDEN, CUT_SAUNA, 1.00, 1.14, 560, 880), (CUT_SAUNA, CUT_WIDE, 1.00, 1.07, 560, 950),
       (CUT_WIDE, CUT_END, 1.00, 1.10, 540, 1060)]
# door burst (S2 -> original garden): centre in the door opening / centre in the sun of the garden shot
DOOR_PRE, DOOR_POST = (540, 820), (600, 760)
