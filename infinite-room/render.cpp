// Schwarzer unendlicher Raum (futuristisch) – Portale in der Leere als nahtlose Endlosschleife.
//
// Optische Täuschung:
//  1. Selbstähnlichkeit: Hinter jedem Portal steht ein exakt halb so großes Portal, dahinter
//     wieder eines, usw. Die ganze Szene ist invariant unter der Ähnlichkeitsabbildung
//     M(p) = S*p + C (Streckung um den Fixpunkt F auf dem Boden) – auch das Bodenraster:
//     Strahlen durch F und geometrisch gestaffelte Querlinien (log-polares Raster).
//  2. Die Kamera bewegt sich mit konstanter logarithmischer Geschwindigkeit auf F zu:
//     P(t) = F + S^t * (A - F). Bei t = 1 steht sie an M(A) – an exakt derselben relativen
//     Stelle vor dem nächsten, halb so großen Portal. Da Perspektive maßstabsunabhängig ist,
//     gilt Bild(t=1) == Bild(t=0): eine perfekte, nahtlose Schleife ohne Ende.
//  3. Links und rechts gibt es keine Wände: der schwarze Spiegelboden läuft ins Leere aus.
//
// Build:  g++ -O3 -march=native -ffast-math -std=c++17 -pthread render.cpp -o render
// Usage:  ./render W H FRAMES SPP_GRID                 -> rohe RGB24-Frames auf stdout
//         ./render W H FRAMES SPP_GRID FRAME out.ppm    -> einzelnes Vorschaubild
// Farbe:  PALETTE=cyan (Standard) | gold | white

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
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
};
static inline float dot(const V& a, const V& b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
static inline V nrm(const V& a) { return a * (1.0f / std::sqrt(dot(a, a))); }
static inline float clampf(float x, float a, float b) { return x < a ? a : (x > b ? b : x); }
static inline V mix(const V& a, const V& b, float t) { return a * (1 - t) + b * t; }
static const float PI = 3.14159265358979f;
static const float LN2 = 0.69314718f;

// ---------------------------------------------------------------- Szene (lokale Einheiten)
// Ein "Segment" reicht von z = 0 bis z = L; am Ende (z = D .. L) steht das Portal.
static const float D = 10.0f;
static const float TP = 0.35f;            // Tiefe des Portalrahmens
static const float L = D + TP;
static const float S = 0.5f;              // Maßstab des nächsten Segments
static const float FZ = L / (1.0f - S);   // Fixpunkt F = (0, 0, FZ)
static const float EYE = 1.7f;
static const int MAXSEG = 22;

// Portal: Öffnung = Rechteck mit abgeschrägten oberen Ecken
static const float R2 = 0.70710678f;
static const float AI = 1.25f, HI = 3.0f, CI = 0.62f, FW = 0.2f;
static const float KI = HI + AI - CI;            // Schräge:  y + |x| <= KI
static const float AO = AI + FW, HO = HI + FW, KO = KI + FW * 1.41421356f;
static const float PORTAL_TOP = HO + 0.01f;

struct HP { float nx, ny, b; };
static const HP INNER[5] = {{1, 0, AI}, {-1, 0, AI}, {0, 1, HI}, {R2, R2, KI * R2}, {-R2, R2, KI * R2}};
static const HP OUTER[6] = {{1, 0, AO}, {-1, 0, AO}, {0, 1, HO}, {R2, R2, KO * R2}, {-R2, R2, KO * R2}, {0, -1, 0}};

// Boden: log-polares Raster um F
static const float TH_L = AI / (FZ - D);   // "Landebahn"-Linien laufen exakt durch die Portalfüße
static const float DTH = TH_L * 0.5f;      // Abstand der Strahlen (Winkelmaß x / (FZ - z))
static const int UCROSS = 8;               // Querlinien pro Segment (pro Halbierung)
static const float THFADE = 0.17f;         // seitliches Auslaufen ins Leere
static const float PULSE_SPEED = 2.0f;     // Lichtimpulse: 2 Segmente pro Schleife (Kamera: 1)
static const int PULSES = 2;               // Impulse pro Segment

static V C_NEON(0.30f, 0.78f, 1.0f);
static const float E_PORTAL = 5.0f;
static const float E_GRID = 0.45f;
static const float E_LANE = 1.0f;
static const float E_MEMBRANE = 0.30f;  // Energiefeld-Schimmer in der Portalöffnung
static const float E_PULSE = 7.0f;

static float gTime = 0.0f;  // Schleifenphase 0..1 (für die Lichtimpulse)

// ---------------------------------------------------------------- Hilfsfunktionen
static inline float band(float u, float a, float b, float w) {
    w = std::max(w, 1e-6f);
    float lo = std::max(u - 0.5f * w, a), hi = std::min(u + 0.5f * w, b);
    return clampf((hi - lo) / w, 0.0f, 1.0f);
}
static inline float footAxis(const V& d, const V& n, const V& e, float base) {
    float dn = std::max(0.02f, std::fabs(dot(d, n)));
    V dt = d - n * dot(d, n);
    float lt = std::sqrt(dot(dt, dt));
    if (lt < 1e-6f) return base;
    float c = dot(e, dt) / lt;
    return base * std::sqrt(c * c / (dn * dn) + (1.0f - c * c));
}
static inline float sdPoly(const HP* hp, int n, float x, float y) {
    float m = -1e30f;
    for (int i = 0; i < n; ++i) m = std::max(m, hp[i].nx * x + hp[i].ny * y - hp[i].b);
    return m;
}

// Hintergrund: absolute Leere, nur ein Hauch Licht am Fluchtpunkt (nur richtungsabhängig)
static V background(const V& d) {
    static const V f = nrm(V(0.0f, -EYE, FZ));
    float c = clampf(dot(d, f), -1.0f, 1.0f);
    float a = std::acos(c);
    return C_NEON * (0.12f * std::exp(-(a * a) / (0.05f * 0.05f)) + 0.018f * std::exp(-(a * a) / (0.3f * 0.3f)));
}

// ---------------------------------------------------------------- Portal-Schnitt
enum Part { P_FRONT, P_WALL_IN, P_WALL_OUT };

static bool hitPortal(const V& o, const V& d, float tmax, float& tHit, V& n, int& part) {
    if (d.z <= 0) return false;
    float t0 = 0.0f;
    V p0 = o;
    bool before = o.z < D;
    if (before) {
        t0 = (D - o.z) / d.z;
        if (t0 > tmax) return false;
        p0 = o + d * t0;
    }
    float t1 = std::min(tmax, (L - o.z) / d.z);
    float si = sdPoly(INNER, 5, p0.x, p0.y);
    float so = sdPoly(OUTER, 6, p0.x, p0.y);
    if (si > 0.0f && so <= 0.0f) {
        if (!before) return false;
        tHit = t0; n = V(0, 0, -1); part = P_FRONT;
        return true;
    }
    if (si <= 0.0f) {
        // in der Öffnung: trifft der Strahl die Innenwand, bevor er das Portal verlässt?
        float te = 1e30f; int best = -1;
        for (int i = 0; i < 5; ++i) {
            float den = INNER[i].nx * d.x + INNER[i].ny * d.y;
            if (den > 1e-9f) {
                float tau = (INNER[i].b - (INNER[i].nx * p0.x + INNER[i].ny * p0.y)) / den;
                if (tau < te) { te = tau; best = i; }
            }
        }
        if (best >= 0 && t0 + te < t1) {
            tHit = t0 + te; n = V(-INNER[best].nx, -INNER[best].ny, 0); part = P_WALL_IN;
            return true;
        }
        return false;
    }
    // außerhalb: trifft der Strahl seitlich die Außenwand des Rahmens? (Liang-Barsky)
    float tin = 0.0f, tout = 1e30f; int bi = -1;
    for (int i = 0; i < 6; ++i) {
        float den = OUTER[i].nx * d.x + OUTER[i].ny * d.y;
        float num = OUTER[i].b - (OUTER[i].nx * p0.x + OUTER[i].ny * p0.y);
        if (std::fabs(den) < 1e-12f) { if (num < 0) return false; }
        else if (den > 0) tout = std::min(tout, num / den);
        else { float tau = num / den; if (tau > tin) { tin = tau; bi = i; } }
    }
    if (bi < 0 || tin > tout || t0 + tin >= t1) return false;
    tHit = t0 + tin; n = V(OUTER[bi].nx, OUTER[bi].ny, 0); part = P_WALL_OUT;
    return true;
}

// ---------------------------------------------------------------- Shading
static V shadePortal(const V& p, const V& n, const V& d, float base, int part) {
    V body(0.006f, 0.007f, 0.009f);
    float e = 0.0f;
    if (part == P_FRONT) {
        float w = std::max(footAxis(d, n, V(1, 0, 0), base), footAxis(d, n, V(0, 1, 0), base));
        float si = sdPoly(INNER, 5, p.x, p.y);
        float so = -sdPoly(OUTER, 6, p.x, p.y);
        e = band(si, 0.022f, 0.062f, w) + band(so, 0.022f, 0.062f, w);
        e += 0.06f * band(si, 0.09f, FW - 0.09f, w);  // feine Mittellinie (gedimmt)
    } else {
        float wz = footAxis(d, n, V(0, 0, 1), base);
        float zc = D + 0.5f * TP;
        e = band(p.z, zc - 0.02f, zc + 0.02f, wz);
    }
    e = std::min(1.0f, e);
    return mix(body, C_NEON * E_PORTAL, e);
}

// Neon-Schein der Portalfüße auf dem Boden (q in lokalen Koordinaten des Portals)
static inline float portalGlow(const V& q) {
    float dz = std::max(0.0f, std::max(D - q.z, q.z - L));
    float dx = std::max(0.0f, std::fabs(std::fabs(q.x) - (AI + 0.5f * FW)) - 0.5f * FW);
    float dd = std::sqrt(dx * dx + dz * dz);
    return std::exp(-dd / 0.28f);
}

static V shadeFloorEmission(const V& p, const V& d, float base) {
    const V n(0, 1, 0);
    float r = FZ - p.z;                         // > 0 vor dem Fixpunkt
    float th = p.x / r;                         // Strahl-Koordinate (maßstabsinvariant)
    float u = std::log2(r / (FZ - D));          // 0 am Portal, +1 je Verdopplung des Abstands zu F
    float wth = footAxis(d, n, V(1, 0, 0), base) / r;
    float wu = footAxis(d, n, V(0, 0, 1), base) / (r * LN2);
    float fade = std::exp(-(th * th) / (THFADE * THFADE));

    // Strahlen durch F
    float jt = th / DTH;
    float ft = (jt - std::round(jt)) * DTH;
    float radial = band(ft, -0.0012f, 0.0012f, wth);
    // geometrisch gestaffelte Querlinien
    float ju = u * UCROSS;
    float fu = (ju - std::round(ju)) / UCROSS;
    float cross = band(fu, -0.0022f, 0.0022f, wu);
    // "Landebahn": zwei hellere Linien durch alle Portalfüße + Lichtimpulse
    float lane = band(std::fabs(th) - TH_L, -0.0016f, 0.0016f, wth);
    float v = (u + PULSE_SPEED * gTime) * PULSES;
    float x = v - std::floor(v);                // 0 = Kopf des Impulses, Schweif zur Kamera hin
    float head = clampf((1.0f - x) / 0.02f, 0.0f, 1.0f);
    float pulse = std::exp(-x * 9.0f) * head;

    V e = C_NEON * (fade * E_GRID * std::min(1.0f, radial + cross));
    e += C_NEON * (lane * (E_LANE + E_PULSE * pulse));
    // Schein der Portalfüße (eigenes Portal und das doppelt so große davor)
    V qprev(p.x * S, p.y * S, FZ + (p.z - FZ) * S);
    e += C_NEON * (0.55f * (portalGlow(p) + portalGlow(qprev)));
    return e;
}

// ---------------------------------------------------------------- Raytracing
static V trace(V o, V d, float travel, int seg, int refl, float pixAng) {
    V acc(0.0f);
    for (int iter = 0; iter < 64; ++iter) {
        if (seg > MAXSEG || d.z <= 0.0f) return acc + background(d);
        if (d.y >= 0.0f && o.y > PORTAL_TOP) return acc + background(d);
        float tSlab = (L - o.z) / d.z;
        float tFloor = d.y < 0.0f ? -o.y / d.y : 1e30f;
        float tP; V nP; int part;
        if (hitPortal(o, d, std::min(tSlab, tFloor), tP, nP, part)) {
            V p = o + d * tP;
            return acc + shadePortal(p, nP, d, (travel + tP) * pixAng, part);
        }
        if (o.z < D) {
            // Strahl passiert die Portalöffnung: weicher Energiefeld-Schimmer zum Rand hin
            float tD = (D - o.z) / d.z;
            if (tD < std::min(tSlab, tFloor)) {
                V q = o + d * tD;
                float si = sdPoly(INNER, 5, q.x, q.y);
                if (si < 0.0f) acc += C_NEON * (E_MEMBRANE * std::exp(si / 0.11f));
            }
        }
        if (tFloor < tSlab) {
            V p = o + d * tFloor;
            float trav = travel + tFloor;
            V col = shadeFloorEmission(p, d, trav * pixAng);
            if (refl == 0) {
                // schwarz polierter Boden: Fresnel-Spiegelung
                float c = std::fabs(d.y);
                float F = 0.08f + 0.92f * std::pow(1.0f - c, 5.0f);
                V rc = trace(V(p.x, 1e-4f, p.z), V(d.x, -d.y, d.z), trav, seg, 1, pixAng);
                col += rc * (F * 0.85f);
            }
            return acc + col;
        }
        // weiter ins nächste, halb so große Segment
        V p = o + d * tSlab;
        o = V(p.x / S, p.y / S, 0.0f);
        travel = (travel + tSlab) / S;
        seg++;
    }
    return acc + background(d);
}

// ---------------------------------------------------------------- Kamera & Bild
struct Image { int w, h; std::vector<V> px; };

// ---------------------------------------------------------------- Lichtpartikel in der Leere
// Pro Segment dieselben Partikel (lokal), d. h. die Partikelwolke ist ebenfalls selbstähnlich.
struct Particle { V p; float r, I, ph; };
static std::vector<Particle> gParticles;

static void buildParticles() {
    uint32_t st = 12345u;
    auto rnd = [&]() { st = st * 1664525u + 1013904223u; return (st >> 8) / 16777216.0f; };
    while (gParticles.size() < 70) {
        float x = (rnd() * 2.0f - 1.0f) * 7.0f;
        float y = 0.25f + rnd() * 5.5f;
        float z = rnd() * L;
        if (std::fabs(x) < 0.9f && y < 2.6f) continue;          // Kamerapfad freihalten
        if (std::fabs(x) < AO + 0.3f && y < HO + 0.3f && z > D - 0.4f) continue;  // nicht im Portal
        float big = rnd();
        gParticles.push_back({V(x, y, z), 0.012f + 0.03f * big * big, 0.6f + 1.6f * rnd(), rnd()});
    }
}

static void splat(Image& img, float px, float py, float sigma, V energy) {
    float s = std::max(sigma, 0.55f);
    int r = (int)std::ceil(s * 3.0f);
    int x0 = (int)std::floor(px), y0 = (int)std::floor(py);
    float norm = 1.0f / (2.0f * PI * s * s);
    for (int y = y0 - r; y <= y0 + r; ++y) {
        if (y < 0 || y >= img.h) continue;
        for (int x = x0 - r; x <= x0 + r; ++x) {
            if (x < 0 || x >= img.w) continue;
            float dx = x + 0.5f - px, dy = y + 0.5f - py;
            float g = std::exp(-(dx * dx + dy * dy) / (2.0f * s * s)) * norm;
            img.px[y * img.w + x] += energy * g;
        }
    }
}

static void drawParticles(Image& img, const V& cam, float tx, float ty, float shiftY, float cr, float sr, float t) {
    const float fpx = 0.5f * img.w / tx;  // Pixel pro Einheit bei Abstand 1
    for (int k = -1; k <= 14; ++k) {
        float sk = std::pow(S, (float)k);
        for (const Particle& pa : gParticles) {
            float tw = 0.65f + 0.35f * std::sin(2.0f * PI * (2.0f * t + pa.ph));  // Funkeln (periodisch)
            for (int mirror = 0; mirror < 2; ++mirror) {
                V lp = pa.p;
                if (mirror) lp.y = -lp.y;                    // Spiegelbild im Boden
                V P(lp.x * sk, lp.y * sk, FZ + (lp.z - FZ) * sk);
                V rel = P - cam;
                if (rel.z < 0.08f) continue;
                float a = rel.x / rel.z, b = rel.y / rel.z - shiftY;
                float X = a * cr + b * sr, Y = -a * sr + b * cr;
                float px = (X / tx + 1.0f) * 0.5f * img.w;
                float py = (1.0f - Y / ty) * 0.5f * img.h;
                if (px < -20 || px > img.w + 20 || py < -20 || py > img.h + 20) continue;
                float rpx = pa.r * sk / rel.z * fpx;
                float area = PI * rpx * rpx;                  // Energie ~ projizierte Fläche
                V col = mix(C_NEON, V(1.0f), 0.55f) * (pa.I * 5.0f * tw * area * (mirror ? 0.22f : 1.0f));
                splat(img, px, py, rpx * 0.7f, col);
            }
        }
    }
}

static V cameraAt(float t) {
    V A(0.0f, EYE, 0.0f);
    V F(0.0f, 0.0f, FZ);
    V off(0.16f * std::sin(2.0f * PI * t), 0.0f, 0.0f);  // sanftes, periodisches Schweben
    return F + (A - F + off) * std::pow(S, t);
}

static void renderFrame(Image& img, float t, int grid) {
    gTime = t;
    V cam = cameraAt(t);
    // Sichtfeld an der kürzeren Bildseite festgemacht (16:9 -> 74° horizontal)
    const float tShort = std::tan(37.0f * PI / 180.0f) * 9.0f / 16.0f;
    const float tx = img.w >= img.h ? tShort * (float)img.w / (float)img.h : tShort;
    const float ty = img.w >= img.h ? tShort : tShort * (float)img.h / (float)img.w;
    const float shiftY = -EYE / FZ;  // Fluchtpunkt F in der Bildmitte (Shift-Objektiv)
    const float pixAng = 2.0f * tx / (float)img.w / (float)grid;
    const float roll = -0.022f * std::sin(2.0f * PI * t);  // leichtes Rollen in die Bewegung
    const float cr = std::cos(roll), sr = std::sin(roll);

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
                            float X = u * tx, Y = v * ty;
                            V d = nrm(V(X * cr - Y * sr, X * sr + Y * cr + shiftY, 1.0f));
                            sum += trace(cam, d, 0.0f, 0, 0, pixAng);
                        }
                    img.px[y * img.w + x] = sum * (1.0f / (grid * grid));
                }
            }
        });
    }
    for (auto& tt : th) tt.join();
    drawParticles(img, cam, tx, ty, shiftY, cr, sr, t);
}

// ---------------------------------------------------------------- Post: Bloom, Farbsaum, Tonemapping
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
static V sampleBilinear(const std::vector<V>& b, int w, int h, float fx, float fy) {
    fx = clampf(fx, 0.0f, w - 1.001f); fy = clampf(fy, 0.0f, h - 1.001f);
    int x0 = (int)fx, y0 = (int)fy;
    float ax = fx - x0, ay = fy - y0;
    const V& a = b[y0 * w + x0]; const V& bb = b[y0 * w + x0 + 1];
    const V& c = b[(y0 + 1) * w + x0]; const V& d = b[(y0 + 1) * w + x0 + 1];
    return mix(mix(a, bb, ax), mix(c, d, ax), ay);
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
                    acc += V(std::max(0.0f, c.x - 0.7f), std::max(0.0f, c.y - 0.7f), std::max(0.0f, c.z - 0.7f));
                }
            bright[y * bw + x] = acc * (1.0f / (ds * ds));
        }
    std::vector<V> b1 = bright, b2 = bright;
    float scale = img.w / 1920.0f;
    blur1D(b1, bw, bh, 1.8f * scale, true);  blur1D(b1, bw, bh, 1.8f * scale, false);
    blur1D(b2, bw, bh, 9.0f * scale, true);  blur1D(b2, bw, bh, 9.0f * scale, false);

    out.resize((size_t)img.w * img.h * 3);
    const float exposure = 1.1f;
    const float ca = 0.0016f;  // chromatische Aberration (Farbsaum zu den Rändern)
    const float cx = 0.5f * img.w, cy = 0.5f * img.h;
    for (int y = 0; y < img.h; ++y)
        for (int x = 0; x < img.w; ++x) {
            float dx = x - cx, dy = y - cy;
            V cR = sampleBilinear(img.px, img.w, img.h, cx + dx * (1 + ca), cy + dy * (1 + ca));
            V cG = img.px[y * img.w + x];
            V cB = sampleBilinear(img.px, img.w, img.h, cx + dx * (1 - ca), cy + dy * (1 - ca));
            V c(cR.x, cG.y, cB.z);
            float fx = (x + 0.5f) / ds - 0.5f, fy = (y + 0.5f) / ds - 0.5f;
            c += sampleBilinear(b1, bw, bh, fx, fy) * 0.35f + sampleBilinear(b2, bw, bh, fx, fy) * 0.32f;
            float u = (x + 0.5f) / img.w - 0.5f, v = (y + 0.5f) / img.h - 0.5f;
            float vig = 1.0f - 1.0f * (u * u + v * v);
            c = c * (exposure * vig);
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
    if (const char* pal = std::getenv("PALETTE")) {
        if (!std::strcmp(pal, "gold")) C_NEON = V(1.0f, 0.62f, 0.26f);
        else if (!std::strcmp(pal, "white")) C_NEON = V(0.85f, 0.9f, 1.0f);
    }
    int W = std::atoi(argv[1]), Hh = std::atoi(argv[2]), N = std::atoi(argv[3]), grid = std::atoi(argv[4]);
    buildParticles();
    Image img{W, Hh, std::vector<V>((size_t)W * Hh)};
    std::vector<uint8_t> out;
    if (argc >= 7) {
        int f = std::atoi(argv[5]);
        renderFrame(img, (float)f / N, grid);
        postprocess(img, out, (uint32_t)f);
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
