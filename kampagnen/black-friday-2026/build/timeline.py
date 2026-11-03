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
SAUNA_LAND = 15.20         # dirt explosion, frame 456
WHIRL_IN = 17.33
WHIRL_LAND = 18.95         # touches the lawn, frame 569

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

# ---------------------------------------------------------------------------
# New native-German voice-over: timings come from vo_assemble.py (vo_timing.json)
import json as _json
import os as _os

_VO = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "vo_timing.json")
if _os.path.exists(_VO):
    _t = _json.load(open(_VO))
    _w = {int(k): v for k, v in _t["words"].items()}
    SUBS = SUBS[:4] + [tuple(s) for s in _t["subs"]]   # woman's 4 intro lines + new VO lines

    def _wt(i, which=0):
        return _w[i][which]

    # counters land while the amount is being spoken (not after the long number word ends)
    COUNTERS = {"fence": (_wt(17), min(_wt(18, 1), _wt(18) + 0.45)),
                "sauna": (_wt(24), min(_wt(25, 1), _wt(25) + 0.40)),
                "whirl": (_wt(32), min(_wt(33, 1), _wt(33) + 0.40)),
                "total": (22.04, max(22.45, _wt(36) + 0.22))}
    T = dict(
        n15_in=_wt(4), n15_strike=_wt(5, 1) - 0.08, n15_out=_wt(6) - 0.06,
        n20_in=_wt(6), n20_strike=_wt(7, 1) - 0.08, n20_out=_wt(8) - 0.16,
        slam25=_wt(8), auf=_wt(10), wobble=_wt(12), out25=_wt(15) - 0.30,
        banner=_wt(38) - 0.05, home=_wt(43),
    )
else:  # fallback: original speaker timing
    COUNTERS = {"fence": (10.82, 11.70), "sauna": (15.55, 15.95), "whirl": (18.88, 19.85), "total": (22.10, 23.10)}
    T = dict(n15_in=5.74, n15_strike=6.22, n15_out=6.36, n20_in=6.40, n20_strike=6.98, n20_out=7.10,
             slam25=7.24, auf=8.38, wobble=9.46, out25=10.18, banner=24.05, home=26.74)
