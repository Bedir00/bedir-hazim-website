# Black Week Story 3D (9:16, 38 s)

Quelle für `STORY_BW_3D.mp4`. Three.js-Szene + HTML-Overlay, Frame für Frame mit Playwright gerendert.

- Produkte (Stand 02.11.2026, homedeluxe.de): Sitzsack mit Hocker COZY 189 €, Couchtisch Marmor AMIRI XXL 399 €, Hängesessel faltbar LOMA 429 €
- Codes: BLACK15 (ab 100 €), BLACK75 (ab 500 €), BLACK150 (ab 1.000 €)
- Texte, Timings, Produkte: oben in `index.html` (`PRODUCTS`, `TIERS`, `STAGE_T`, `SC`)

Rendern:

```bash
python3 -m http.server 8765 --bind 127.0.0.1 &
./run_all.sh   # schreibt chunks/c0..c3.mp4
```

Danach Chunks verketten und die Tonspur der Original-Story (`STORY_BW_2.0.mp4`) darunterlegen.
