// Schwarzer unendlicher Raum – ein selbstähnlicher Spiegelraum als nahtlose Endlosschleife.
//
// Optische Täuschung:
//  1. Droste-Effekt: Der Torbogen in der Rückwand führt in eine exakte Kopie des
//     Raums im Maßstab S (= 0.5). Diese Kopie hat wieder einen Torbogen, usw.
//  2. Die Kamera bewegt sich auf einer Geraden zum Fixpunkt F der Ähnlichkeits-
//     abbildung M(p) = S*p + C, mit konstanter Geschwindigkeit im logarithmischen
//     Maß:  P(t) = F + S^t * (A - F).  Bei t = 1 steht sie an M(A), also an exakt
//     derselben relativen Stelle im nächsten (kleineren) Raum. Da Perspektive
//     maßstabsunabhängig ist, gilt Bild(t=1) == Bild(t=0): eine perfekte Schleife.
//  3. Die Seitenwände sind dunkle Spiegel, der Boden ist schwarz poliert:
//     Lichtlinien und Lichtkugeln wiederholen sich seitlich ins Unendliche.
//
// Build:  g++ -O3 -march=native -ffast-math -std=c++17 -pthread render.cpp -o render
// Usage:  ./render W H FRAMES SPP_GRID                 -> rohe RGB24-Frames auf stdout
//         ./render W H FRAMES SPP_GRID FRAME out.ppm    -> einzelnes Vorschaubild

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <thread>
#include <vector>

struct V {
    float x, y, z;
    V() : x(0), y(0), z(0) {}
    explicit V(float a) : x(a), y(a), z(a) {}
    V(float a, float b, float c) : x(a), y(b), z(c) {}
    V operator+(const V& o) const { return V(x + o.x, y + o.y, z + o.z); }
    V operator-(const V& o) const { return V(x - o.x, y - o.y, z - o.z); }
    V operator*(const V& o) const { return V(x * o.x, y * o.y, z * o.z); }
    V operator*(float s) const { return V(x * s, y * s, z * s); }
    V& operator+=(const V& o) { x += o.x; y += o.y; z += o.z; return *this; }
    V& operator*=(const V& o) { x *= o.x; y *= o.y; z *= o.z; return *this; }
};
static inline float dot(const V& a, const V& b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
static inline V nrm(const V& a) { return a * (1.0f / std::sqrt(dot(a, a))); }
static inline float clampf(float x, float a, float b) { return x < a ? a : (x > b ? b : x); }
static inline V mix(const V& a, const V& b, float t) { return a * (1 - t) + b * t; }

// ---------------------------------------------------------------- Szene (lokale Raum-Einheiten)
static const float HW = 4.0f;   // halbe Breite
static const float H = 5.0f;    // Höhe
static const float D = 10.0f;   // Tiefe
static const float TH = 0.6f;   // Dicke der Rückwand (Laibung des Torbogens)
static const float S = 0.5f;    // Maßstab des nächsten Raums
static const float DA = 1.0f;   // halbe Torbreite
static const float DHR = 1.3f;  // Höhe des geraden Torteils (darüber Halbkreis, Radius DA)
static const float EYE = 1.7f;  // Augenhöhe am Eingang
static const float FZ = (D + TH) / (1.0f - S);  // Fixpunkt F = (0, 0, FZ)
static const int MAXROOM = 20;

static const float LW = 0.05f;      // Breite der Lichtlinien
static const float RING = 2.0f;     // Abstand der Lichtrahmen
static const int NRING = 4;         // Lichtrahmen bei z = 2, 4, 6, 8

enum Mat { M_NONE, M_FLOOR, M_CEIL, M_SIDE, M_BACK, M_FRONT, M_ORB, M_TUNNEL };

struct Orb { V c; float r; float I; };
static std::vector<Orb> gOrbs;

static const V C_LIGHT(1.0f, 0.86f, 0.68f);   // warmweißes Licht (Kugeln)
static const V C_GOLD(1.0f, 0.66f, 0.30f);    // goldene Lichtlinien
static const float E_LINE = 1.9f;             // Leuchtdichte der Raum-Linien
static const float E_ARCH = 4.8f;             // Leuchtdichte der Torbogen-Kontur (Blickfang)
static const float E_ORB = 6.5f;              // Leuchtdichte der Kugeln
static const V C_MIRROR(0.70f, 0.71f, 0.73f); // dunkles Spiegelglas
static const V C_BLACK(0.018f, 0.018f, 0.02f);
static const V C_AMB(0.010f, 0.011f, 0.014f);

static void buildScene() {
    // schwebende Lichtkugeln (fest platziert, abseits des Kamerapfads)
    const float P[][4] = {
        // x,     y,     z,    r
        {-2.30f, 3.55f, 1.05f, 0.16f}, { 2.30f, 3.05f, 1.05f, 0.16f},
        {-2.30f, 2.95f, 3.00f, 0.16f}, { 2.30f, 3.70f, 3.00f, 0.16f},
        {-2.30f, 3.75f, 5.00f, 0.16f}, { 2.30f, 2.90f, 5.00f, 0.16f},
        {-2.30f, 3.00f, 7.00f, 0.16f}, { 2.30f, 3.60f, 7.00f, 0.16f},
        {-2.30f, 3.50f, 9.00f, 0.16f}, { 2.30f, 3.10f, 9.00f, 0.16f},
    };
    // Mitte über dem Torbogen bleibt frei (Platz für Headline)
    for (auto& p : P) gOrbs.push_back({V(p[0], p[1], p[2]), p[3] * 0.85f, 1.9f});
}

// ---------------------------------------------------------------- Hilfsfunktionen
static inline bool inDoor(float x, float y) {
    if (y < 0) return false;
    if (y <= DHR) return std::fabs(x) <= DA;
    float dy = y - DHR;
    return x * x + dy * dy <= DA * DA;
}
// Abstand zur Torkontur (positiv außerhalb)
static inline float doorDist(float x, float y) {
    if (y <= DHR) return std::fabs(x) - DA;
    float dy = y - DHR;
    return std::sqrt(x * x + dy * dy) - DA;
}

// Box-gefilterte Abdeckung eines Bandes [a,b] bei Koordinate u und Filterbreite w
// (antialiasierte Lichtlinien, energieerhaltend -> kein Flimmern in der Tiefe)
static inline float band(float u, float a, float b, float w) {
    w = std::max(w, 1e-5f);
    float lo = std::max(u - 0.5f * w, a), hi = std::min(u + 0.5f * w, b);
    return clampf((hi - lo) / w, 0.0f, 1.0f);
}
// Linien bei z = RING*k (k = 1..NRING)
static inline float ringLines(float z, float w) {
    int k = (int)std::lround(z / RING);
    k = std::max(1, std::min(NRING, k));
    float zc = k * RING;
    return band(z, zc - 0.5f * LW, zc + 0.5f * LW, w);
}

static inline float filteredChecker(float u, float v, float wu, float wv) {
    wu = std::max(wu, 1e-4f); wv = std::max(wv, 1e-4f);
    auto fi = [](float x) { x *= 0.5f; return std::fabs(x - std::floor(x) - 0.5f); };
    float ix = 2.0f * (fi(u - 0.5f * wu) - fi(u + 0.5f * wu)) / wu;
    float iy = 2.0f * (fi(v - 0.5f * wv) - fi(v + 0.5f * wv)) / wv;
    return 0.5f - 0.5f * ix * iy;
}

// Pixel-Fußabdruck entlang einer Flächenachse e (Strahldifferential einer Ebene)
static inline float footAxis(const V& d, const V& n, const V& e, float base) {
    float dn = std::max(0.03f, std::fabs(dot(d, n)));
    V dt = d - n * dot(d, n);
    float lt = std::sqrt(dot(dt, dt));
    if (lt < 1e-6f) return base;
    float c = dot(e, dt) / lt;
    return base * std::sqrt(c * c / (dn * dn) + (1.0f - c * c));
}

// Licht der Kugeln im aktuellen Raum (lokal => jeder Raum identisch beleuchtet)
static V lighting(const V& p, const V& n, const V& rd, float spec) {
    V sum = C_AMB;
    for (const Orb& o : gOrbs) {
        V L = o.c - p;
        float d2 = dot(L, L);
        V l = L * (1.0f / std::sqrt(d2));
        float ndl = dot(n, l);
        if (ndl <= 0) continue;
        float att = o.I / (d2 + 0.2f);
        float s = 0.0f;
        if (spec > 0) {
            V h = nrm(l - rd);
            float nh = std::max(0.0f, dot(n, h));
            s = spec * std::pow(nh, 60.0f) * 6.0f;
        }
        sum += C_LIGHT * ((ndl + s) * att);
    }
    return sum;
}

// ---------------------------------------------------------------- Schnitttests
static inline bool hitSphere(const V& o, const V& d, const V& c, float r, float tmax, float& tOut) {
    V oc = o - c;
    float b = dot(oc, d);
    float cc = dot(oc, oc) - r * r;
    float disc = b * b - cc;
    if (disc < 0) return false;
    float t = -b - std::sqrt(disc);
    if (t < 1e-4f || t > tmax) return false;
    tOut = t;
    return true;
}

struct Hit { float t; Mat m; V n; int id; };

static Hit intersectInterior(const V& o, const V& d) {
    Hit h{1e30f, M_NONE, V(0.0f), -1};
    auto take = [&](float t, Mat m, V n) { if (t > 1e-5f && t < h.t) { h.t = t; h.m = m; h.n = n; } };
    if (d.y < 0) take(-o.y / d.y, M_FLOOR, V(0, 1, 0));
    if (d.y > 0) take((H - o.y) / d.y, M_CEIL, V(0, -1, 0));
    if (d.x > 0) take((HW - o.x) / d.x, M_SIDE, V(-1, 0, 0));
    if (d.x < 0) take((-HW - o.x) / d.x, M_SIDE, V(1, 0, 0));
    if (d.z > 0) take((D - o.z) / d.z, M_BACK, V(0, 0, -1));
    if (d.z < 0) take(-o.z / d.z, M_FRONT, V(0, 0, 1));
    for (size_t i = 0; i < gOrbs.size(); ++i) {
        float t;
        if (hitSphere(o, d, gOrbs[i].c, gOrbs[i].r, h.t, t)) {
            h.t = t; h.m = M_ORB; h.id = (int)i;
            h.n = nrm(o + d * t - gOrbs[i].c);
        }
    }
    return h;
}

// Laibung des Torbogens: z in [D, D+TH], Querschnitt = Torform (konvex)
static Hit intersectTunnel(const V& o, const V& d) {
    Hit h{(d.z > 0) ? (D + TH - o.z) / d.z : 1e30f, M_NONE, V(0.0f), -1};
    auto take = [&](float t, Mat m, V n) { if (t > 1e-5f && t < h.t) { h.t = t; h.m = m; h.n = n; } };
    if (d.y < 0) take(-o.y / d.y, M_FLOOR, V(0, 1, 0));
    if (d.x > 0) { float t = (DA - o.x) / d.x; if (o.y + d.y * t <= DHR) take(t, M_TUNNEL, V(-1, 0, 0)); }
    if (d.x < 0) { float t = (-DA - o.x) / d.x; if (o.y + d.y * t <= DHR) take(t, M_TUNNEL, V(1, 0, 0)); }
    float ox = o.x, oy = o.y - DHR;
    float a = d.x * d.x + d.y * d.y;
    if (a > 1e-12f) {
        float b = ox * d.x + oy * d.y;
        float c = ox * ox + oy * oy - DA * DA;
        float disc = b * b - a * c;
        if (disc >= 0) {
            float t = (-b + std::sqrt(disc)) / a;
            V p = o + d * t;
            if (p.y >= DHR) take(t, M_TUNNEL, nrm(V(-p.x, -(p.y - DHR), 0)));
        }
    }
    return h;
}

// ---------------------------------------------------------------- Shading
// Leuchtende Linien (Emission) einer Fläche, antialiasiert über den Fußabdruck
static float lineEmission(Mat m, const V& p, const V& d, const V& n, float base, float& arch) {
    arch = 0.0f;
    switch (m) {
    case M_SIDE: {
        float wy = footAxis(d, n, V(0, 1, 0), base), wz = footAxis(d, n, V(0, 0, 1), base);
        float e = band(p.y, 0.0f, LW, wy) + band(p.y, H - LW, H, wy) + ringLines(p.z, wz);
        return std::min(1.0f, e);
    }
    case M_CEIL: {
        float wx = footAxis(d, n, V(1, 0, 0), base), wz = footAxis(d, n, V(0, 0, 1), base);
        float e = ringLines(p.z, wz) + band(p.z, D - LW, D, wz) + band(std::fabs(p.x), HW - LW, HW, wx);
        return std::min(1.0f, e);
    }
    case M_BACK: {
        float wx = footAxis(d, n, V(1, 0, 0), base), wy = footAxis(d, n, V(0, 1, 0), base);
        float wr = std::max(wx, wy);
        arch = band(doorDist(p.x, p.y), 0.06f, 0.06f + 1.4f * LW, wr);        // Torbogen-Kontur
        float e = band(std::fabs(p.x), HW - LW, HW, wx)                         // Ecken
                + band(p.y, 0.0f, LW, wy) + band(p.y, H - LW, H, wy);           // Boden-/Deckenkante
        return std::min(1.0f, e + arch);
    }
    default:
        return 0.0f;
    }
}

static V shadeSurface(Mat m, const V& p, const V& n, const V& rd, float base, int id, float& emitCov) {
    emitCov = 0.0f;
    if (m == M_ORB) {
        float f = std::fabs(dot(n, rd));
        return C_LIGHT * (E_ORB * (0.6f + 0.4f * f));
    }
    V alb = C_BLACK;
    float spec = 0.25f;
    if (m == M_FLOOR) {
        // schwarzer Marmor, kaum sichtbares Schachbrett
        const float tile = 0.8f;
        const float r = 0.70710678f;
        float u = (p.x + p.z) * r / tile, v = (p.z - p.x) * r / tile;
        float wu = footAxis(rd, n, V(r, 0, r), base) / tile;
        float wv = footAxis(rd, n, V(-r, 0, r), base) / tile;
        float c = filteredChecker(u + 0.5f, v + 0.5f, wu, wv);
        alb = mix(V(0.006f, 0.006f, 0.007f), V(0.030f, 0.029f, 0.028f), c);
        spec = 0.0f;  // Glanz kommt über die echte Spiegelung
    }
    V col = alb * lighting(p, n, rd, spec);
    float arch = 0.0f;
    float e = lineEmission(m, p, rd, n, base, arch);
    emitCov = e;
    float ea = (e > 0.0f) ? arch / e : 0.0f;
    V emitCol = C_GOLD * (E_LINE * (1.0f - ea) + E_ARCH * ea);
    return mix(col, emitCol, e);
}

// ---------------------------------------------------------------- Raytracing
static const V FARCOL(0.03f, 0.026f, 0.022f);

static V trace(V o, V d, float travel, int room, bool inTunnel, int reflLevel, float pixAng) {
    V thr(1.0f), acc(0.0f);
    for (int iter = 0; iter < 160; ++iter) {
        if (room > MAXROOM) { acc += thr * FARCOL; break; }
        Hit h = inTunnel ? intersectTunnel(o, d) : intersectInterior(o, d);
        V p = o + d * h.t;
        float trav = travel + h.t;
        if (inTunnel && h.m == M_NONE) {
            // durch den Bogen -> in den nächsten, halb so großen Raum
            o = V(p.x / S, p.y / S, 0.0f);
            travel = trav / S;
            room++;
            inTunnel = false;
            continue;
        }
        if (h.m == M_BACK && inDoor(p.x, p.y)) {
            o = p; travel = trav; inTunnel = true;
            continue;
        }
        float base = trav * pixAng;
        float cov = 0.0f;
        V col = shadeSurface(h.m, p, h.n, d, base, h.id, cov);
        if (h.m == M_SIDE && cov < 1.0f) {
            // dunkler Spiegel: Rest des Strahls wird reflektiert
            acc += thr * col * cov;
            thr *= C_MIRROR * (1.0f - cov);
            if (thr.x + thr.y + thr.z < 0.006f) break;
            o = p; d.x = -d.x; travel = trav;
            continue;
        }
        if (h.m == M_FLOOR && reflLevel == 0) {
            float c = std::fabs(d.y);
            float F = 0.10f + 0.90f * std::pow(1.0f - c, 5.0f);
            V refl = trace(p + V(0, 1e-4f, 0), V(d.x, -d.y, d.z), trav, room, false, 1, pixAng);
            col = col * (1.0f - F) + refl * (F * 0.92f);
        }
        acc += thr * col;
        break;
    }
    return acc;
}

// ---------------------------------------------------------------- Kamera & Bild
struct Image { int w, h; std::vector<V> px; };

static V cameraAt(float t) {
    const float TWO_PI = 6.28318530718f;
    V A(0.0f, EYE, 0.0f);
    V F(0.0f, 0.0f, FZ);
    V off(0.18f * std::sin(TWO_PI * t), 0.0f, 0.0f);  // sanftes, periodisches Schweben
    return F + (A - F + off) * std::pow(S, t);
}

static void renderFrame(Image& img, float t, int grid) {
    V cam = cameraAt(t);
    // Sichtfeld an der kürzeren Bildseite festgemacht: 16:9 -> 74° horizontal,
    // Hoch-/Quadratformate behalten denselben Bildausschnitt in der Breite bzw. Höhe.
    const float tShort = std::tan(37.0f * 3.14159265f / 180.0f) * 9.0f / 16.0f;
    const float tx = img.w >= img.h ? tShort * (float)img.w / (float)img.h : tShort;
    const float ty = img.w >= img.h ? tShort : tShort * (float)img.h / (float)img.w;
    const float shiftY = -EYE / FZ;  // Fluchtpunkt F in der Bildmitte (Shift-Objektiv)
    const float pixAng = 2.0f * tx / (float)img.w / (float)grid;
    const bool inTunnel = cam.z >= D;

    std::atomic<int> nextRow(0);
    unsigned nth = std::max(1u, std::thread::hardware_concurrency());
    std::vector<std::thread> th;
    for (unsigned k = 0; k < nth; ++k) {
        th.emplace_back([&]() {
            for (;;) {
                int y = nextRow.fetch_add(1);
                if (y >= img.h) break;
                for (int x = 0; x < img.w; ++x) {
                    V sum(0.0f);
                    for (int sy = 0; sy < grid; ++sy)
                        for (int sx = 0; sx < grid; ++sx) {
                            float u = ((x + (sx + 0.5f) / grid) / img.w) * 2.0f - 1.0f;
                            float v = 1.0f - ((y + (sy + 0.5f) / grid) / img.h) * 2.0f;
                            V d = nrm(V(u * tx, v * ty + shiftY, 1.0f));
                            sum += trace(cam, d, 0.0f, 0, inTunnel, 0, pixAng);
                        }
                    img.px[y * img.w + x] = sum * (1.0f / (grid * grid));
                }
            }
        });
    }
    for (auto& tt : th) tt.join();
}

// ---------------------------------------------------------------- Bloom + Tonemapping
static void blur1D(std::vector<V>& buf, int w, int h, float sigma, bool horiz) {
    int r = (int)std::ceil(sigma * 3.0f);
    std::vector<float> k(2 * r + 1);
    float s = 0;
    for (int i = -r; i <= r; ++i) { k[i + r] = std::exp(-0.5f * i * i / (sigma * sigma)); s += k[i + r]; }
    for (auto& v : k) v /= s;
    std::vector<V> out(buf.size());
    for (int y = 0; y < h; ++y)
        for (int x = 0; x < w; ++x) {
            V acc(0.0f);
            for (int i = -r; i <= r; ++i) {
                int xx = horiz ? std::clamp(x + i, 0, w - 1) : x;
                int yy = horiz ? y : std::clamp(y + i, 0, h - 1);
                acc += buf[yy * w + xx] * k[i + r];
            }
            out[y * w + x] = acc;
        }
    buf.swap(out);
}

static inline float aces(float x) {
    x = std::max(0.0f, x);
    return clampf((x * (2.51f * x + 0.03f)) / (x * (2.43f * x + 0.59f) + 0.14f), 0.0f, 1.0f);
}
static inline float toSRGB(float c) {
    return c <= 0.0031308f ? 12.92f * c : 1.055f * std::pow(c, 1.0f / 2.4f) - 0.055f;
}

static inline float hashU(uint32_t x) {
    x ^= x >> 16; x *= 0x7feb352dU; x ^= x >> 15; x *= 0x846ca68bU; x ^= x >> 16;
    return (x & 0xffffff) / 16777216.0f;
}

static void postprocess(const Image& img, std::vector<uint8_t>& out, uint32_t seed) {
    const int ds = 4;
    int bw = img.w / ds, bh = img.h / ds;
    std::vector<V> bright(bw * bh);
    for (int y = 0; y < bh; ++y)
        for (int x = 0; x < bw; ++x) {
            V acc(0.0f);
            for (int j = 0; j < ds; ++j)
                for (int i = 0; i < ds; ++i) {
                    V c = img.px[(y * ds + j) * img.w + x * ds + i];
                    acc += V(std::max(0.0f, c.x - 0.8f), std::max(0.0f, c.y - 0.8f), std::max(0.0f, c.z - 0.8f));
                }
            bright[y * bw + x] = acc * (1.0f / (ds * ds));
        }
    std::vector<V> b1 = bright, b2 = bright;
    float scale = img.w / 1920.0f;
    blur1D(b1, bw, bh, 2.0f * scale, true);  blur1D(b1, bw, bh, 2.0f * scale, false);
    blur1D(b2, bw, bh, 9.0f * scale, true);  blur1D(b2, bw, bh, 9.0f * scale, false);

    out.resize((size_t)img.w * img.h * 3);
    const float exposure = 1.15f;
    for (int y = 0; y < img.h; ++y)
        for (int x = 0; x < img.w; ++x) {
            float fx = (x + 0.5f) / ds - 0.5f, fy = (y + 0.5f) / ds - 0.5f;
            int x0 = std::clamp((int)std::floor(fx), 0, bw - 1), y0 = std::clamp((int)std::floor(fy), 0, bh - 1);
            int x1 = std::min(x0 + 1, bw - 1), y1 = std::min(y0 + 1, bh - 1);
            float ax = clampf(fx - x0, 0, 1), ay = clampf(fy - y0, 0, 1);
            auto bil = [&](const std::vector<V>& b) {
                return mix(mix(b[y0 * bw + x0], b[y0 * bw + x1], ax), mix(b[y1 * bw + x0], b[y1 * bw + x1], ax), ay);
            };
            V c = img.px[y * img.w + x] + bil(b1) * 0.30f + bil(b2) * 0.28f;
            float u = (x + 0.5f) / img.w - 0.5f, v = (y + 0.5f) / img.h - 0.5f;
            float vig = 1.0f - 0.9f * (u * u + v * v);
            c = c * (exposure * vig);
            // dreiecksverteiltes Dithering (+-1 LSB) gegen Banding in den dunklen Verläufen
            uint32_t hs = (uint32_t)(y * img.w + x) * 2654435761U + seed * 97531U;
            float dith = hashU(hs) + hashU(hs ^ 0x9e3779b9U) - 1.0f;
            uint8_t* o = &out[((size_t)y * img.w + x) * 3];
            o[0] = (uint8_t)clampf(std::round(toSRGB(aces(c.x)) * 255.0f + dith), 0, 255);
            o[1] = (uint8_t)clampf(std::round(toSRGB(aces(c.y)) * 255.0f + dith), 0, 255);
            o[2] = (uint8_t)clampf(std::round(toSRGB(aces(c.z)) * 255.0f + dith), 0, 255);
        }
}

int main(int argc, char** argv) {
    if (argc < 5) {
        std::fprintf(stderr, "usage: %s W H FRAMES GRID [FRAME out.ppm]\n", argv[0]);
        return 1;
    }
    int W = std::atoi(argv[1]), Hh = std::atoi(argv[2]), N = std::atoi(argv[3]), grid = std::atoi(argv[4]);
    buildScene();
    Image img{W, Hh, std::vector<V>((size_t)W * Hh)};
    std::vector<uint8_t> out;
    if (argc >= 7) {
        renderFrame(img, (float)std::atoi(argv[5]) / N, grid);
        postprocess(img, out, (uint32_t)std::atoi(argv[5]));
        FILE* fp = std::fopen(argv[6], "wb");
        if (!fp) return 1;
        std::fprintf(fp, "P6\n%d %d\n255\n", W, Hh);
        std::fwrite(out.data(), 1, out.size(), fp);
        std::fclose(fp);
        return 0;
    }
    for (int f = 0; f < N; ++f) {
        renderFrame(img, (float)f / N, grid);
        postprocess(img, out, (uint32_t)f);
        std::fwrite(out.data(), 1, out.size(), stdout);
        std::fflush(stdout);
        std::fprintf(stderr, "\rframe %d/%d", f + 1, N);
    }
    std::fprintf(stderr, "\n");
    return 0;
}
