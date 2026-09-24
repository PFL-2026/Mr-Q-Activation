#!/usr/bin/env python3
"""
make_mrq.py — deterministic PFL x MrQ deck build.

Rebuilds from a pristine NetBet-Activation GitHub checkout in a single
verified pass. No stateful edits: run it twice, get byte-identical output.

Scope of this round:
  * NetBet logos -> MrQ throughout (topbar, cover, close, TV watermark,
    favicons, baked-in lockups on social_grid.jpg + Slide_14.jpg)
  * Palette -> MrQ blue
  * Slide 4: France -> Boxing (RMC Sport -> Sky Sports), UK -> MMA,
    France & UK (YouTube) box removed; broadcast detail pop-up to match
  * Slide 13 (LED Wristbands) removed, deck renumbered 18 -> 17
  * Commercials pop-up removed entirely (nav button, modal, edit tooling)

Usage:  python3 make_mrq.py
"""

import hashlib
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

ROOT = Path("/home/claude")
SRC = ROOT / "netbet_src"          # pristine NetBet-Activation checkout
AS = ROOT / "mrq_assets"           # supplied MrQ assets
OUT = ROOT / "mrq"                 # build target

# MrQ palette — core blue sampled from the supplied wordmark (10, 46, 204)
MQ_BLUE = "#0a2ecc"
MQ_BLUE_RGB = (10, 46, 204)
MQ_BLUE_DEEP = "#061d85"
MQ_BLUE_BRIGHT = "#5273ff"          # legible accent text on the dark UI
MQ_GLOW = "62, 98, 255"             # rgba() stem for glows/shadows on dark

TOTAL_OLD, TOTAL_NEW = 18, 17
REMOVED_SLIDE = 13

FAILURES = []
CHECKS = 0


def check(cond, label):
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILURES.append(label)


def rep(text, old, new, label, count=1):
    """Plain (non-regex) replace with an exact-hit-count assertion."""
    n = text.count(old)
    check(n == count, f"{label} (expected {count} hit(s), found {n})")
    return text.replace(old, new)


def cut(text, start, end, label, include_end=True):
    """Remove the span from `start` up to (and including) `end`, once."""
    i = text.find(start)
    j = text.find(end, i + len(start)) if i != -1 else -1
    check(i != -1 and j != -1, f"{label} (markers found)")
    check(text.count(start) == 1, f"{label} (start marker unique)")
    if i == -1 or j == -1:
        return text
    j = j + len(end) if include_end else j
    return text[:i] + text[j:]


# ---------------------------------------------------------------------------
# 1. Pristine source
# ---------------------------------------------------------------------------

def prepare_source():
    if SRC.exists():
        shutil.rmtree(SRC)
    subprocess.run(["git", "clone", "--depth", "1",
                    "https://github.com/PFL-2026/Netbet-Activation.git", str(SRC)],
                   check=True, capture_output=True)
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SRC, OUT, ignore=shutil.ignore_patterns(".git", "make_netbet.py"))
    print(f"  source staged -> {OUT}")


# ---------------------------------------------------------------------------
# 2. Logos + icons
# ---------------------------------------------------------------------------

def _mrq_alpha():
    """Key the supplied blue-on-white MrQ wordmark to an alpha mask."""
    a = np.asarray(Image.open(AS / "Mr_Q.png").convert("RGB")).astype(float)
    # Red channel runs 255 (white) -> 10 (brand blue): clean ramp for alpha
    alpha = np.clip((255 - a[..., 0]) / (255 - MQ_BLUE_RGB[0]), 0, 1)
    alpha = (alpha * 255).round().astype("uint8")
    ys, xs = np.nonzero(alpha > 8)
    return alpha[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def _solid(alpha, rgb):
    h, w = alpha.shape
    arr = np.dstack([np.full((h, w), c, "uint8") for c in rgb] + [alpha])
    return Image.fromarray(arr, "RGBA")


def build_logos():
    logo_dir = OUT / "assets" / "logos"
    alpha = _mrq_alpha()
    # Round 4: Mr Q runs in its supplied brand blue everywhere (one file).
    _solid(alpha, MQ_BLUE_RGB).save(logo_dir / "mrq.png", optimize=True)

    # MVP wordmark: supplied white-on-black JPEG -> white with alpha
    m = np.asarray(Image.open(AS / "r4" / "mvp_logo.jpeg").convert("L")).astype(float)
    a = np.clip((m - 40) / (235 - 40), 0, 1)
    a = (a * 255).round().astype("uint8")
    ys, xs = np.nonzero(a > 8)
    a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    mvp = _solid(a, (255, 255, 255))
    mvp.save(OUT / "assets" / "images" / "mvp_logo.png", optimize=True)
    ar = np.asarray(mvp)
    check(ar[..., 3].mean() > 60 and ar[0, 0, 3] == 0, "mvp_logo.png keyed (white on alpha)")
    for name in ("pfl_logo.png", "pfl_logo_white.png"):
        q = OUT / "assets" / "images" / name
        if q.exists():
            q.unlink()
        check(not q.exists(), f"retired PFL logo: {name}")

    # --- Sky Sports: white plate keyed out, navy "sky" reversed to white,
    # red "sports" plate (with its white lettering) kept as supplied.
    rgb = np.asarray(Image.open(AS / "Sky Sports.jpeg").convert("RGB")).astype(float)
    mn = rgb.min(axis=2)
    lab, _ = ndimage.label(mn > 232)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])))
    border.discard(0)
    bg = np.isin(lab, list(border))
    edge = ndimage.binary_dilation(bg, iterations=3) & ~bg
    alpha = np.ones(mn.shape)
    alpha[bg] = 0
    alpha[edge] = np.clip((255 - mn[edge]) / 225, 0, 1)
    out = rgb.copy()
    blue = (rgb[..., 2] > rgb[..., 0] + 25)          # the navy "sky" letters
    out[blue] = 255
    # Un-premultiply the red plate's anti-aliased rim against white
    red_edge = edge & ~blue & (alpha > 0.02)
    a3 = alpha[red_edge][:, None]
    out[red_edge] = np.clip((rgb[red_edge] - 255 * (1 - a3)) / a3, 0, 255)
    rgba = np.dstack([out, alpha * 255]).round().astype("uint8")
    sky = Image.fromarray(rgba, "RGBA")
    sky = sky.crop(sky.getbbox())
    sky.save(logo_dir / "sky-sports.png", optimize=True)

    ar = np.asarray(sky).astype(int)
    check(ar[0, 0, 3] == 0 and ar[-1, -1, 3] == 0, "sky-sports.png corners transparent")
    # white "sports" lettering inside the red plate must survive
    plate = ar[:, int(ar.shape[1] * 0.4):]
    check(((plate[..., :3].min(axis=2) > 235) & (plate[..., 3] > 250)).sum() > 3000,
          "sky-sports.png keeps white lettering inside red plate")
    check(((ar[..., 2] > ar[..., 0] + 40) & (ar[..., 3] > 200)).sum() < 50,
          "sky-sports.png has no residual navy")

    for name in ("netbet.png", "netbet-white.png", "rmc-sport.png", "youtube.png",
                 "mrq-white.png", "mrq-blue.png"):
        p = logo_dir / name
        if p.exists():
            p.unlink()
        check(not p.exists(), f"retired logo: {name}")
    for name in ("mrq.png", "sky-sports.png"):
        p = logo_dir / name
        check(p.exists() and Image.open(p).mode == "RGBA", f"logo written w/ alpha: {name}")
    print("  logos: mrq, mrq-white, mrq-blue, sky-sports (rmc-sport, youtube retired)")


def build_icons():
    """Favicon set — MrQ blue tile with the white Q glyph from the wordmark."""
    icon_dir = OUT / "assets" / "icons"
    alpha = _mrq_alpha()
    # The Q is the right-hand glyph: take columns right of the widest empty gap
    cols = (alpha > 40).sum(axis=0)
    xs = np.nonzero(cols)[0]
    # Q is the last glyph: start after the right-most empty-column run
    gaps = [xs[i + 1] for i in range(len(xs) - 1) if xs[i + 1] - xs[i] > 2]
    check(len(gaps) >= 2, f"wordmark splits into 3 glyphs ({len(gaps) + 1})")
    q_start = gaps[-1]
    q = alpha[:, q_start:]
    ys = np.nonzero((q > 8).any(axis=1))[0]
    q = q[ys.min():ys.max() + 1]
    check(0.8 < q.shape[1] / q.shape[0] < 1.6, f"favicon glyph is the Q alone ({q.shape[1]}x{q.shape[0]})")
    glyph = _solid(q, (255, 255, 255))

    def tile(size):
        im = Image.new("RGBA", (size, size), (*MQ_BLUE_RGB, 255))
        g = glyph.copy()
        g.thumbnail((int(size * 0.74), int(size * 0.74)), Image.LANCZOS)
        im.paste(g, ((size - g.width) // 2, (size - g.height) // 2), g)
        return im

    tile(32).save(icon_dir / "favicon-32.png")
    tile(192).save(icon_dir / "favicon-192.png")
    tile(180).save(icon_dir / "apple-touch-icon.png")
    tile(64).save(icon_dir / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    for name in ("favicon-32.png", "favicon-192.png", "apple-touch-icon.png"):
        im = np.asarray(Image.open(icon_dir / name).convert("RGB"))
        check(tuple(im[1, 1]) == MQ_BLUE_RGB, f"icon corner is MrQ blue: {name}")
        c = im[im.shape[0] // 2 - 3: im.shape[0] // 2 + 3].reshape(-1, 3)
        check((c.min(axis=1) > 200).any(), f"icon has white glyph: {name}")
    print("  icons: favicon set regenerated (MrQ blue + Q)")


# ---------------------------------------------------------------------------
# 3. Images
# ---------------------------------------------------------------------------

def _tracked_text(draw, xy, text, font, fill, track):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + track


def _tracked_width(draw, text, font, track):
    return sum(draw.textlength(c, font=font) + track for c in text) - track


def build_images():
    img_dir = OUT / "assets" / "images"

    # netbet_* -> mrq_* (content unchanged; replacement photography to follow)
    renamed = 0
    for p in sorted(img_dir.glob("netbet_*")):
        p.rename(img_dir / p.name.replace("netbet_", "mrq_", 1))
        renamed += 1
    check(not list(img_dir.glob("netbet_*")), "no netbet_* images remain")

    # Orphans from removed slide 13 (LED Wristbands)
    for name in ("mrq_led_1.jpg", "mrq_led_2.jpg",
                 "wristband_1_still.jpg", "wristband_2_still.jpg"):
        p = img_dir / name
        if p.exists():
            p.unlink()
        check(not p.exists(), f"deleted orphan image: {name}")

    # Baked-in NetBet lockups (painted by the NetBet build) -> MrQ lockups,
    # same bands, same deterministic fill/grain treatment.
    logo = _solid(_mrq_alpha(), MQ_BLUE_RGB)       # round 4: blue Mr Q lockups
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    p = img_dir / "social_grid.jpg"
    im = Image.open(p).convert("RGB")
    w, h = im.size
    check((w, h) == (540, 799), "social_grid.jpg has expected dimensions")
    y0, y1 = 668, 730
    d = ImageDraw.Draw(im)
    d.rectangle([0, y0, w, y1], fill=(4, 4, 6))
    font = ImageFont.truetype(font_path, 15)
    label, track = "PRESENTED BY:", 3.2
    lw = _tracked_width(d, label, font, track)
    lg = logo.copy()
    lg.thumbnail((400, 34), Image.LANCZOS)
    gap = 16
    sx = (w - (lw + gap + lg.width)) / 2
    cy = (y0 + y1) / 2
    _tracked_text(d, (sx, cy - 9), label, font, (255, 255, 255), track)
    im.paste(lg, (int(sx + lw + gap), int(cy - lg.height / 2)), lg)
    im.save(p, "JPEG", quality=92, optimize=True)

    p = img_dir / "Slide_14.jpg"
    im = Image.open(p).convert("RGB")
    w, h = im.size
    check((w, h) == (1568, 784), "Slide_14.jpg has expected dimensions")
    y0, y1 = 636, 763
    d = ImageDraw.Draw(im)
    for y in range(y0, y1):
        t = (y - y0) / (y1 - y0)
        v = int(19 - 8 * t)
        d.line([(0, y), (w, y)], fill=(int(v * 0.75), int(v * 0.8), v))
    rnd = random.Random(7)
    px = im.load()
    for _ in range(9000):
        x = rnd.randrange(w)
        y = rnd.randrange(y0, y1)
        r, g, b = px[x, y]
        n = rnd.randint(-3, 4)
        px[x, y] = (max(0, r + n), max(0, g + n), max(0, b + n))
    lg = logo.copy()
    lg.thumbnail((520, 66), Image.LANCZOS)
    lg.putalpha(lg.getchannel("A").point(lambda v: int(v * 0.92)))
    for i in range(4):
        cx = int(w * (i + 0.5) / 4)
        im.paste(lg, (cx - lg.width // 2, (y0 + y1) // 2 - lg.height // 2), lg)
    im.save(p, "JPEG", quality=92, optimize=True)

    # NetBet red must be gone from both patched bands
    for name, (a0, a1) in (("social_grid.jpg", (668, 730)), ("Slide_14.jpg", (636, 763))):
        a = np.asarray(Image.open(img_dir / name).convert("RGB")).astype(int)[a0:a1]
        red = (a[..., 0] > 120) & (a[..., 0] > a[..., 1] * 2) & (a[..., 0] > a[..., 2] * 2)
        check(red.sum() < 30, f"{name}: NetBet red cleared from band ({red.sum()}px)")
    print(f"  images: {renamed} netbet_* renamed to mrq_*, 4 orphans deleted, "
          "2 baked-in lockups repainted")

# MrQ photography (Archive.zip) -> target filename. Mapped by content.
PHOTO_MAP = {
    "Brand Awareness and Cage Branding.png": ["mrq_brand_awareness.jpg",   # slide 2, pillar 01
                                              "mrq_cage_branding.jpg"],    # slide 6
    "Mr Q Acquisition.png":        ["mrq_acquisition.jpg"],          # slide 2, pillar 02
    "Integrated Content.png":      ["mrq_integrated_content.jpg"],   # slide 2, pillar 03
    "Center Canvas.png":           ["mrq_centre_canvas.jpg"],        # slide 5
    "Prediction Walkout.png":      ["mrq_prediction_walkouts.jpg"],  # slide 9
    "Social Series 1.png":         ["mrq_social_port_1.jpg"],        # slide 11, By the Numbers
    "Social Series 2.png":         ["mrq_social_port_2.jpg"],        # slide 11, 24-4 Shabily
    "Mr Q Live Odds.png":          ["mrq_live_odds_cutin.jpg"],      # slide 12
    "Watch + Bet background.png":  ["mrq_watch_bet.png"],            # slide 14
    "Mr Q Highlights.png":         ["mrq_highlights.jpg"],           # slide 15
    "T shirt.png":                 ["mrq_tshirt.jpg"],               # slide 8
    "Cap.png":                     ["mrq_cap.jpg"],
    "Mr Q Hoodie.png":             ["mrq_hoodie.jpg"],
    "Mr Q shorts.png":             ["mrq_shorts.jpg"],
    "Social Integration.png":      ["mrq_social_integration.jpg"],   # slide 10 (round 4)
}
WATCH_BET_MAX_W = 2400   # supplied at 3450px; the panel never renders that wide


def build_photos():
    img_dir = OUT / "assets" / "images"
    src_dir = AS / "photos"
    n = 0
    for src_name, targets in PHOTO_MAP.items():
        src = src_dir / src_name
        check(src.exists(), f"photo supplied: {src_name}")
        if not src.exists():
            continue
        im = Image.open(src)
        for target in targets:
            dst = img_dir / target
            check(dst.exists(), f"photo target exists in deck: {target}")
            if target.endswith(".png"):
                out = im.convert("RGB")
                if out.width > WATCH_BET_MAX_W:
                    out = out.resize((WATCH_BET_MAX_W,
                                      round(out.height * WATCH_BET_MAX_W / out.width)),
                                     Image.LANCZOS)
                out.save(dst, "PNG", optimize=True)
            else:
                im.convert("RGB").save(dst, "JPEG", quality=88, optimize=True,
                                       progressive=True)
            got = Image.open(dst)
            ratio_ok = abs(got.width / got.height - im.width / im.height) < 0.01
            check(ratio_ok, f"{target}: aspect matches supplied {src_name}")
            n += 1
    print(f"  photos: {n} deck images replaced from {len(PHOTO_MAP)} supplied files")


def build_video():
    vid_dir = OUT / "assets" / "video"
    for name in ("wristband_1.mp4", "wristband_2.mp4"):
        p = vid_dir / name
        if p.exists():
            p.unlink()
        check(not p.exists(), f"deleted orphan video: {name}")
    print("  video: wristband_1/2 removed with slide 13")


# ---------------------------------------------------------------------------
# 4. HTML
# ---------------------------------------------------------------------------

SLIDE4_OLD = """    <div class="slide-body">Co-branded NetBet placements run live across the RMC Sport, talkSPORT and YouTube broadcasts — banner overlays, sponsor graphics and on-screen promos.</div>"""
SLIDE4_NEW = """    <div class="slide-body">Co-branded NetBet placements run live across the Sky Sports and talkSPORT broadcasts — banner overlays, sponsor graphics and on-screen promos.</div>"""

BOXES_OLD = """        <div class="bcast-partner">
          <div class="bcast-country">France</div>
          <img src="assets/logos/rmc-sport.png" alt="RMC Sport" class="bcast-logo-lg" loading="lazy">
        </div>
        <div class="bcast-partner">
          <div class="bcast-country">UK</div>
          <img src="assets/logos/talksport.png" alt="talkSPORT" class="bcast-logo-lg" loading="lazy">
        </div>
        <div class="bcast-partner">
          <div class="bcast-country">France &amp; UK</div>
          <img src="assets/logos/youtube.png" alt="YouTube" class="bcast-logo-lg" loading="lazy">
        </div>
"""
BOXES_NEW = """        <div class="bcast-partner">
          <div class="bcast-country">Boxing</div>
          <img src="assets/logos/sky-sports.png" alt="Sky Sports" class="bcast-logo-lg" loading="lazy">
        </div>
        <div class="bcast-partner">
          <div class="bcast-country">MMA</div>
          <img src="assets/logos/talksport.png" alt="talkSPORT" class="bcast-logo-lg" loading="lazy">
        </div>
"""

MODAL_BOXING_OLD = """        <h3 class="terms-section-title">France</h3>
        <div class="dist-channel-grid">
          <div class="dist-channel">
            <div class="dist-channel-tag">Linear feed</div>
            <h4>RMC Sport</h4>
            <ul>
              <li>All broadcast integrations delivered via the <strong>RMC Sport French feed</strong></li>
              <li>Banner overlays, sponsor graphics and on-screen promos across <strong>all RMC Sport coverage</strong></li>
              <li>Geo-targeted to France</li>"""
MODAL_BOXING_NEW = """        <h3 class="terms-section-title">Boxing</h3>
        <div class="dist-channel-grid">
          <div class="dist-channel">
            <div class="dist-channel-tag">Linear feed</div>
            <h4>Sky Sports</h4>
            <ul>
              <li>All broadcast integrations delivered via the <strong>Sky Sports feed</strong></li>
              <li>Banner overlays, sponsor graphics and on-screen promos across <strong>all Sky Sports coverage</strong></li>
              <li>Geo-targeted to the United Kingdom</li>"""

MODAL_STREAMING = """      <section class="dist-section">
        <h3 class="terms-section-title">Streaming</h3>"""


def build_html():
    p = OUT / "index.html"
    h = p.read_text(encoding="utf-8")
    check("data:" not in h, "index.html carries no data: URIs (safe for text edits)")

    # --- Commercials pop-up: nav button, modal, inline edit tooling -------
    h = rep(h, '<button class="section-btn section-btn-modal" data-open-dist-modal="commercialsModal">Commercials</button>\n',
            "", "remove Commercials nav button")
    h = cut(h, "<!-- Commercials Modal — opens from the top nav.",
            "<!-- COMMERCIALS_MODAL_END -->\n", "remove Commercials modal")
    h = cut(h, '<style id="editToolsStyles">', "</style>\n", "remove edit-tools styles")
    h = cut(h, '<script id="editToolsScript">', "</script>\n", "remove edit-tools script")

    # --- Slide 13 (LED Wristbands) + its video popup ----------------------
    h = cut(h, '<section class="slide content-slide flip" data-slide="13">',
            "</section>\n\n\n", "remove slide 13 section")
    h = cut(h, "<!-- LED Wristband video popup", "<!-- === See Brand in Action",
            "remove wristband modal", include_end=False)

    # --- Slide 4 ------------------------------------------------------------
    h = rep(h, SLIDE4_OLD, SLIDE4_NEW, "slide 4 body copy")
    h = rep(h, '<div class="stat-card"><div class="num">FR &middot; UK</div><div class="label">Territories</div></div>',
            '<div class="stat-card"><div class="num">UK</div><div class="label">Territory</div></div>',
            "slide 4 territory stat")
    h = rep(h, BOXES_OLD, BOXES_NEW, "slide 4 broadcast boxes")

    # --- Broadcast detail pop-up -------------------------------------------
    h = rep(h, '<div class="terms-print-meta">PFL × NetBet · 2026–2027 · France &amp; United Kingdom</div>',
            '<div class="terms-print-meta">PFL × NetBet · 2026–2027 · Boxing &amp; MMA</div>',
            "broadcast modal print meta")
    h = rep(h, "<!-- Headline metrics row — 2026 France & UK viewership -->",
            "<!-- Headline metrics row — 2026 Boxing & MMA viewership -->", "broadcast modal comment")
    h = rep(h, '2026 Viewership <span class="dist-section-sub">France &amp; UK broadcast</span>',
            '2026 Viewership <span class="dist-section-sub">Boxing &amp; MMA broadcast</span>',
            "broadcast modal viewership sub")
    h = rep(h, "<!-- France & UK distribution -->", "<!-- Boxing & MMA distribution -->",
            "broadcast modal section comment")
    h = rep(h, MODAL_BOXING_OLD, MODAL_BOXING_NEW, "broadcast modal Boxing / Sky Sports")
    h = rep(h, '<h3 class="terms-section-title">United Kingdom</h3>',
            '<h3 class="terms-section-title">MMA</h3>', "broadcast modal MMA title")
    h = cut(h, MODAL_STREAMING, "</section>\n\n", "remove broadcast modal Streaming/YouTube")
    h = rep(h, """        <div>PFL × NetBet · Broadcast Distribution · Confidential</div>
        <div>2026–2027 · France &amp; United Kingdom</div>""",
            """        <div>PFL × NetBet · Broadcast Distribution · Confidential</div>
        <div>2026–2027 · Boxing &amp; MMA</div>""", "broadcast modal footer")

    # --- Brand labels in uppercase UI keep MrQ casing ----------------------
    h = rep(h, '<span class="pillar-presented">Presented by NetBet</span>',
            '<span class="pillar-presented">Presented by <span class="brand-name">NetBet</span></span>',
            "pillar presented-by label")
    h = rep(h, '<div class="close-tagline">Powered by NetBet</div>',
            '<div class="close-tagline">Powered by <span class="brand-name">NetBet</span></div>',
            "close tagline")
    h = rep(h, 'Powered by <span class="ls-accent">NetBet</span>',
            'Powered by <span class="ls-accent brand-name">NetBet</span>', "TV sponsor bug")

    # --- Renumber slides 14..18 -> 13..17 ----------------------------------
    for n in range(REMOVED_SLIDE + 1, TOTAL_OLD + 1):
        h = rep(h, f'data-slide="{n}"', f'data-slide="{n - 1}"', f"renumber data-slide {n}")
    h = re.sub(r'<div class="slide-num">\d\d / 18</div>', "SLIDENUM", h)
    k = 0

    def _num(_m):
        nonlocal k
        k += 1
        return f'<div class="slide-num">{k:02d} / {TOTAL_NEW:02d}</div>'
    # slide 1 has no slide-num badge; badges run 02..17
    k = 1
    h = re.sub("SLIDENUM", _num, h)
    check(k == TOTAL_NEW, f"slide-num badges renumbered to {TOTAL_NEW} (got {k})")
    h = rep(h, '<span class="cur" id="curSlide">01</span> / 18',
            f'<span class="cur" id="curSlide">01</span> / {TOTAL_NEW}', "slide counter total")
    h = rep(h, 'data-section="4" data-target="14">Content', 'data-section="4" data-target="13">Content',
            "nav target Content")
    h = rep(h, 'data-section="5" data-target="17">Hospitality', 'data-section="5" data-target="16">Hospitality',
            "nav target Hospitality")
    h = rep(h, 'data-section="6" data-target="18">Close', 'data-section="6" data-target="17">Close',
            "nav target Close")

    # --- Branding sweep (no base64 in this file — asserted above) ---------
    h = h.replace("assets/logos/netbet-white.png", "assets/logos/mrq-white.png")
    h = h.replace("assets/logos/netbet.png", "assets/logos/mrq.png")
    h = h.replace("assets/images/netbet_", "assets/images/mrq_")
    h = h.replace("NetBet", "MrQ")
    p.write_text(h, encoding="utf-8")
    print("  html: slide 4 + broadcast modal updated, slide 13 + commercials removed")


# ---------------------------------------------------------------------------
# 5. CSS
# ---------------------------------------------------------------------------

def _print_spans(css):
    spans = []
    for m in re.finditer(r"@media print\s*\{", css):
        depth, i = 1, m.end()
        while depth:
            depth += {"{": 1, "}": -1}.get(css[i], 0)
            i += 1
        spans.append((m.start(), i))
    return spans


def build_css():
    p = OUT / "css" / "styles.css"
    c = p.read_text(encoding="utf-8")
    c = rep(c, "/* PFL × Liga Stavok Activation Strategy 2026 — Stylesheet */",
            "/* PFL × MrQ Activation Strategy 2026 — Stylesheet */", "css header")
    c = rep(c, """    /* NetBet red — sampled from the supplied NetBet wordmark (#c62026).
       Variable names kept as --ls-* so all existing references update at once. */""",
            f"""    /* MrQ blue — sampled from the supplied MrQ wordmark ({MQ_BLUE}).
       --ls-green-bright is a lifted tint for accent text on the dark UI.
       Variable names kept as --ls-* so all existing references update at once. */""",
            "palette comment")
    c = rep(c, "/* NetBet broadcast watermark", "/* MrQ broadcast watermark", "watermark comment")

    # Accent *text* on the dark screen UI uses the lifted tint for legibility;
    # fills/borders keep the core brand blue. Print (white paper) keeps core.
    spans = _print_spans(c)
    check(len(spans) == 4, f"found 4 @media print blocks (got {len(spans)})")
    pat = re.compile(r"(?<![-\w])color:\s*(var\(--pfl-red\)|var\(--ls-green\)|#c62026)")
    out, last, n_txt = [], 0, 0
    for m in pat.finditer(c):
        if any(a <= m.start() < b for a, b in spans):
            continue
        out.append(c[last:m.start()])
        out.append("color: var(--ls-green-bright)")
        last = m.end()
        n_txt += 1
    out.append(c[last:])
    c = "".join(out)
    check(n_txt >= 9, f"screen accent text moved to bright tint ({n_txt})")

    # Tokens
    c = rep(c, "--pfl-red: #c62026;", f"--pfl-red: {MQ_BLUE};", "token --pfl-red")
    c = rep(c, "--pfl-red-deep: #8e1319;", f"--pfl-red-deep: {MQ_BLUE_DEEP};", "token --pfl-red-deep")
    c = rep(c, "--ls-green: #c62026;", f"--ls-green: {MQ_BLUE};", "token --ls-green")
    c = rep(c, "--ls-green-deep: #8e1319;", f"--ls-green-deep: {MQ_BLUE_DEEP};", "token --ls-green-deep")
    c = rep(c, "--ls-green-bright: #e63a41;", f"--ls-green-bright: {MQ_BLUE_BRIGHT};", "token --ls-green-bright")

    # Hardcoded reds + inherited cyan accents -> MrQ blues
    for old, new in (("#c62026", MQ_BLUE), ("#8e1319", MQ_BLUE_DEEP), ("#e63a41", MQ_BLUE_BRIGHT),
                     ("#0a86c0", MQ_BLUE), ("#19b0e8", MQ_BLUE_BRIGHT)):
        c = re.sub(re.escape(old), new, c, flags=re.I)
    c = re.sub(r"rgba\(198,\s*32,\s*38\s*,", f"rgba({MQ_GLOW},", c)
    c = rep(c, "rgba(40,6,8,0.96)", "rgba(6,14,52,0.96)", "sponsor bug dark-red wash")
    c = re.sub(r"rgba\(10,\s*134,\s*192\s*,", f"rgba({MQ_GLOW},", c)
    c = re.sub(r"rgba\(26,\s*176,\s*230\s*,", f"rgba({MQ_GLOW},", c)
    check(not re.search(r"#c62026|#8e1319|#e63a41|#0a86c0|#19b0e8|rgba\((198,\s*32,\s*38|10,\s*134,\s*192|26,\s*176,\s*230)",
                        c, re.I), "no NetBet red / legacy cyan remains in CSS")

    # Slide 4 now has two broadcast boxes
    c = rep(c, """.broadcast-on-logos {
    display: grid;
    grid-template-columns: repeat(3, 1fr);""", """.broadcast-on-logos {
    display: grid;
    grid-template-columns: repeat(2, 1fr);""", "broadcast grid 3 -> 2 columns")

    check("data:" not in c, "styles.css carries no data: URIs (safe for text edits)")
    c = c.replace("NetBet", "MrQ")   # comments only
    c += """
/* MrQ — brand name keeps its own casing inside uppercase labels */
.brand-name { text-transform: none; }
"""
    p.write_text(c, encoding="utf-8")
    print(f"  css: palette -> MrQ blue ({n_txt} accent-text rules lifted)")


# ---------------------------------------------------------------------------
# 6. JS
# ---------------------------------------------------------------------------

def build_js():
    p = OUT / "js" / "deck.js"
    j = p.read_text(encoding="utf-8")
    j = rep(j, "/* PFL × NetBet Activation Strategy 2026 — Navigation logic */",
            "/* PFL × MrQ Activation Strategy 2026 — Navigation logic */", "js header")
    j = rep(j, """    { idx: 3, slides: [9, 10, 11, 12, 13] },
    { idx: 4, slides: [14, 15, 16] },
    { idx: 5, slides: [17] },
    { idx: 6, slides: [18] },""", """    { idx: 3, slides: [9, 10, 11, 12] },
    { idx: 4, slides: [13, 14, 15] },
    { idx: 5, slides: [16] },
    { idx: 6, slides: [17] },""", "section ranges")
    j = rep(j, "const TOTAL_LOGICAL = 18;", f"const TOTAL_LOGICAL = {TOTAL_NEW};", "TOTAL_LOGICAL")
    # Watch & Bet player: selector pointed at slide 16 (Highlights) in the
    # NetBet deck, so "Watch Live" never opened. Target the frame directly.
    j = rep(j, "const frame = document.querySelector('[data-slide=\"16\"] .wb-frame');",
            "const frame = document.querySelector('.wb-stage .wb-frame');", "watch & bet selector")
    j = cut(j, "/* LED wristband video popup", "})();\n\n", "remove wristband popup JS")
    j = cut(j, "/* ===================================================================\n   Commercials modal",
            "})();\n", "remove commercials edit JS")
    j = j.replace("NetBet", "MrQ")
    p.write_text(j, encoding="utf-8")
    print("  js: section map + totals updated, wristband + commercials code removed")


# ---------------------------------------------------------------------------
# 5b. Round 4 — MVP x Mr Q
# ---------------------------------------------------------------------------

AMB_FE = {  # Fabian Edwards replaces Antonio Carlos Jr. (left)
    "img_old": "https://pflmma-prod.s3.amazonaws.com/fighters/bodyshots/ba5216de863796dc313092bd7777cc81-1-1.png",
    "img_new": "https://pflmma-prod.s3.amazonaws.com/fighters/bodyshots/97d927d1ef30e310cbac2613bccaf334-1-1.png",
}
AMB_CD = {  # Caroline Dubois replaces Taylor Lapilus (right)
    "img_old": "https://pflmma-prod.s3.amazonaws.com/fighters/bodyshots/9cf13eefc6ab3bd880106403a12e79ce-2-1.png",
    "img_new": "https://www.mostvaluablepromotions.com/wp-content/uploads/2026/03/MVP-Caroline-Dubois-Profile-1.webp",
}


def build_round4():
    p = OUT / "index.html"
    h = p.read_text(encoding="utf-8")

    # --- remove Broadcast + Social detail buttons and pop-ups -------------
    for which in ("broadcast", "social"):
        h = cut(h, f'    <button type="button" class="dist-trigger" data-open-dist-modal="{which}DistModal">',
                "    </button>\n", f"remove {which} detail button")
    h = cut(h, "<!-- Broadcast Distribution Modal", "<!-- Social Distribution Modal",
            "remove broadcast pop-up", include_end=False)
    h = cut(h, "<!-- Social Distribution Modal", "<!-- FGC Detail Modal",
            "remove social pop-up", include_end=False)

    # --- ambassadors -------------------------------------------------------
    h = rep(h, AMB_FE["img_old"], AMB_FE["img_new"], "Fabian Edwards image")
    h = rep(h, AMB_CD["img_old"], AMB_CD["img_new"], "Caroline Dubois image")
    h = rep(h, '<div class="full">Antonio Carlos Jr.</div>', '<div class="full">Fabian Edwards</div>',
            "Fabian Edwards name")
    h = rep(h, '<div class="country">BRA · Light Heavyweight Champion</div>',
            '<div class="country">GBR · Middleweight</div>', "Fabian Edwards detail line")
    h = rep(h, 'href="https://www.instagram.com/caradesapato/" target="_blank" rel="noopener noreferrer" aria-label="Antonio Carlos Jr. on Instagram"',
            'href="https://www.instagram.com/fabian_edwardsmma/?hl=en" target="_blank" rel="noopener noreferrer" aria-label="Fabian Edwards on Instagram"',
            "Fabian Edwards IG link")
    h = rep(h, "<span>@caradesapato</span>\n            <span class=\"amb-ig-followers\">2M</span>",
            "<span>@fabian_edwardsmma</span>\n            <span class=\"amb-ig-followers\">86K</span>",
            "Fabian Edwards handle + followers")
    h = rep(h, '<div class="full">Taylor Lapilus</div>', '<div class="full">Caroline Dubois</div>',
            "Caroline Dubois name")
    h = rep(h, '<div class="country">FRA · Bantamweight Contender</div>',
            '<div class="country">GBR · Lightweight</div>', "Caroline Dubois detail line")
    h = rep(h, 'href="https://www.instagram.com/taylor_d.i_lapilus/" target="_blank" rel="noopener noreferrer" aria-label="Taylor Lapilus on Instagram"',
            'href="https://www.instagram.com/__carolinedubois1/?hl=en" target="_blank" rel="noopener noreferrer" aria-label="Caroline Dubois on Instagram"',
            "Caroline Dubois IG link")
    h = rep(h, "<span>@taylor_d.i_lapilus</span>\n            <span class=\"amb-ig-followers\">61K</span>",
            "<span>@__carolinedubois1</span>\n            <span class=\"amb-ig-followers\">137K</span>",
            "Caroline Dubois handle + followers")

    # --- stats -------------------------------------------------------------
    h = rep(h, '<div class="stat-card"><div class="num">2</div><div class="label">PFL Events across territories</div></div>',
            '<div class="stat-card"><div class="num">3</div><div class="label">Events in the UK</div></div>',
            "slide 4 events stat")
    h = rep(h, '<div class="stat-card"><div class="num">450k</div><div class="label">Average Unique Viewers</div></div>',
            '<div class="stat-card"><div class="num">420k</div><div class="label">Average Unique Viewers Per Event</div></div>',
            "slide 4 viewers stat")
    h = rep(h, '<div class="stat-card"><div class="num">2.7M</div><div class="label">Followers Reached</div></div>',
            '<div class="stat-card"><div class="num">2.9M</div><div class="label">Followers Reached</div></div>',
            "slide 10 followers stat")

    # --- logos ---------------------------------------------------------------
    h = h.replace("assets/images/pfl_logo_white.png", "assets/images/mvp_logo.png")
    h = h.replace("assets/images/pfl_logo.png", "assets/images/mvp_logo.png")
    h = h.replace("assets/logos/mrq-white.png", "assets/logos/mrq.png")

    # --- naming: PFL -> MVP, MrQ -> Mr Q (text only; no data: URIs here) ----
    check("data:" not in h, "index.html still free of data: URIs")
    h = rep(h, "Professional Fighters League", "Most Valuable Promotions", "close slide wordmark")
    h = re.sub(r"\bPFL\b", "MVP", h)
    h = re.sub(r"\bMrQ\b", "Mr Q", h)
    p.write_text(h, encoding="utf-8")

    j = OUT / "js" / "deck.js"
    js = j.read_text(encoding="utf-8")
    js = re.sub(r"\bPFL\b", "MVP", js)
    js = re.sub(r"\bMrQ\b", "Mr Q", js)
    j.write_text(js, encoding="utf-8")

    c = OUT / "css" / "styles.css"
    css = c.read_text(encoding="utf-8")
    css = re.sub(r"\bPFL\b", "MVP", css)
    css = re.sub(r"\bMrQ\b", "Mr Q", css)
    c.write_text(css, encoding="utf-8")

    vis = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
    check(not re.search(r"\bPFL\b|Professional Fighters", vis), "no PFL references left in deck text")
    check(not re.search(r"\bMrQ\b", h + js), "no 'MrQ' spellings left")
    check("dist-trigger\"" not in h and "DistModal" not in h, "no distribution buttons / pop-ups left")
    check("Antonio" not in h and "Lapilus" not in h, "old ambassadors gone")
    # bg_dark.jpg carries four small red PFL crowns in its corners — patch
    # each with the neighbouring background texture (shifted inward).
    bgp = OUT / "assets" / "images" / "bg_dark.jpg"
    im = Image.open(bgp).convert("RGB")
    W, H = im.size
    for x0, y0 in ((19, 15), (1390, 15), (19, 767), (1390, 767)):
        w_, h_ = 48, 34
        dx = 70 if x0 < W / 2 else -70
        patch = im.crop((x0 + dx, y0, x0 + dx + w_, y0 + h_))
        im.paste(patch, (x0, y0))
    im.save(bgp, "JPEG", quality=92, optimize=True)
    a = np.asarray(Image.open(bgp).convert("RGB")).astype(int)
    red = (a[..., 0] > 120) & (a[..., 0] > a[..., 1] * 2) & (a[..., 0] > a[..., 2] * 2)
    check(red.sum() < 20, f"bg_dark.jpg: PFL corner crowns removed ({red.sum()}px red)")

    print("  round 4: pop-ups removed, ambassadors swapped, stats updated, MVP / Mr Q naming")


# ---------------------------------------------------------------------------
# 6b. Text editing (opt-in via ?edit)
# ---------------------------------------------------------------------------

from html.parser import HTMLParser

INLINE_TAGS = {"span", "strong", "em", "b", "i", "br", "small", "sup", "sub", "u", "wbr"}
VOID_TAGS = {"br", "img", "input", "source", "meta", "link", "hr", "wbr", "area",
             "base", "col", "embed", "track", "param"}
EXCLUDE_TAGS = {"button", "a", "nav", "script", "style", "svg", "video", "select",
                "textarea", "option", "header", "iframe"}
EXCLUDE_CLASSES = {"slide-num", "slide-counter", "dist-trigger", "sbia-btn",
                   "wb-live-pill", "bcast-live-pip"}


class _Tagger(HTMLParser):
    """Find maximal text blocks whose content is only text + inline tags,
    inside the slides (#deck) and the distribution pop-ups (.dist-modal)."""

    def __init__(self, src):
        super().__init__(convert_charrefs=True)
        self.line_off = [0]
        for line in src.splitlines(keepends=True):
            self.line_off.append(self.line_off[-1] + len(line))
        self.stack = []
        self.found = []

    def _off(self):
        ln, col = self.getpos()
        return self.line_off[ln - 1] + col

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = set((a.get("class") or "").split())
        parent = self.stack[-1] if self.stack else None
        in_scope = (parent["in_scope"] if parent else False) or a.get("id") == "deck" \
            or "dist-modal" in cls
        excluded = (parent["excluded"] if parent else False) or tag in EXCLUDE_TAGS \
            or bool(cls & EXCLUDE_CLASSES) or "data-e" in a
        node = {"tag": tag, "off": self._off(), "in_scope": in_scope, "excluded": excluded,
                "pure": True, "text": False, "cands": []}
        if tag in VOID_TAGS:
            if parent and tag not in INLINE_TAGS:
                parent["pure"] = False
            return
        self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        parent = self.stack[-1] if self.stack else None
        if parent and tag not in INLINE_TAGS:
            parent["pure"] = False

    def handle_data(self, data):
        if self.stack and data.strip():
            self.stack[-1]["text"] = True

    def handle_endtag(self, tag):
        if tag in VOID_TAGS or not self.stack:
            return
        # tolerate stray closers: pop to the matching open tag
        while self.stack and self.stack[-1]["tag"] != tag:
            self._close(self.stack.pop())
        if self.stack:
            self._close(self.stack.pop())

    def _close(self, node):
        ok = node["pure"] and node["text"] and node["in_scope"] and not node["excluded"]
        cands = [node] if ok else node["cands"]
        parent = self.stack[-1] if self.stack else None
        if parent is None:
            self.found.extend(cands)
            return
        if node["tag"] not in INLINE_TAGS or not node["pure"]:
            parent["pure"] = False
        parent["text"] = parent["text"] or node["text"]
        parent["cands"].extend(cands)


def build_editing():
    p = OUT / "index.html"
    h = p.read_text(encoding="utf-8")
    t = _Tagger(h)
    t.feed(h)
    t.close()
    while t.stack:
        t._close(t.stack.pop())
    blocks = sorted(t.found, key=lambda n: n["off"])
    check(len(blocks) > 100, f"editable text blocks tagged ({len(blocks)})")
    for i, n in enumerate(reversed(blocks)):
        idx = len(blocks) - i
        at = n["off"] + 1 + len(n["tag"])
        check(h[n["off"]:at] == "<" + n["tag"], f"tag insertion point valid (block {idx})")
        h = h[:at] + f' data-e="{idx}"' + h[at:]
    ids = re.findall(r' data-e="(\d+)"', h)
    check(ids == [str(i) for i in range(1, len(blocks) + 1)], "data-e ids sequential + unique")

    h = rep(h, '<script src="js/deck.js?v=', '<script src="js/edit.js?v=pending" defer></script>\n'
            '<script src="js/deck.js?v=', "inject edit.js")
    p.write_text(h, encoding="utf-8")

    shutil.copy2(AS / "edit.js", OUT / "js" / "edit.js")
    css = OUT / "css" / "styles.css"
    css.write_text(css.read_text(encoding="utf-8") + (AS / "edit.css").read_text(encoding="utf-8"),
                   encoding="utf-8")
    print(f"  editing: {len(blocks)} text blocks tagged, edit.js wired (opt-in via ?edit)")


# ---------------------------------------------------------------------------
# 7. Audit + cache bust
# ---------------------------------------------------------------------------

def audit():
    h = (OUT / "index.html").read_text(encoding="utf-8")
    c = (OUT / "css" / "styles.css").read_text(encoding="utf-8")
    j = (OUT / "js" / "deck.js").read_text(encoding="utf-8")
    allt = h + c + j

    check(not re.search(r"net\s?bet", allt, re.I), "no NetBet references in html/css/js")
    check(not list(OUT.rglob("*netbet*")), "no netbet-named files in repo")
    for s in ("commercialsModal", "Commercials", "COMMERCIALS_MODAL", "editToolsScript",
              "wristbandModal", "data-open-wb-modal", "LED<br>", "rmc-sport", "youtube.png"):
        check(s not in h, f"html free of '{s}'")
    # Slide 4 + its broadcast pop-up: no France / RMC / YouTube left
    s4 = h[h.index('data-slide="4"'):h.index('data-slide="5"')]
    for s in ("France", "FR &middot;", "RMC", "YouTube", "French"):
        check(s not in s4, f"slide 4 free of '{s}'")
    check("Commercials" not in j and "wristbandModal" not in j, "js free of commercials/wristband code")

    nums = [int(n) for n in re.findall(r'<section class="slide[^"]*" data-slide="(\d+)"', h)]
    check(nums == list(range(1, TOTAL_NEW + 1)), f"slides numbered 1..{TOTAL_NEW} in order ({nums})")
    badges = re.findall(r'<div class="slide-num">(\d\d) / (\d\d)</div>', h)
    check([int(a) for a, _ in badges] == list(range(2, TOTAL_NEW + 1))
          and {b for _, b in badges} == {f"{TOTAL_NEW:02d}"}, "slide-num badges 02..17 / 17")
    check(h.count('class="bcast-partner"') == 2, "slide 4 has exactly two broadcast boxes")
    check('bcast-country">Boxing<' in h and 'bcast-country">MMA<' in h, "slide 4 labels Boxing / MMA")
    check("Streaming</h3>" not in h, "broadcast modal Streaming section removed")
    check(h.count("Sky Sports") >= 1, "Sky Sports present on slide 4")

    # Every referenced local asset resolves
    refs = set(re.findall(r"""(?:src|href|poster)=["']((?:assets|css|js)/[^"'?]+)""", h))
    refs |= set(re.findall(r"""url\(['"]?((?:\.\./)?assets/[^'")]+)""", h + c))
    refs |= set(re.findall(r"""['"]((?:assets)/[^'"]+\.(?:mp4|jpg|png|webp))['"]""", j))
    missing = []
    for r in refs:
        rp = r[3:] if r.startswith("../") else r
        if not (OUT / rp).exists():
            missing.append(r)
    check(not missing, f"all referenced assets resolve (missing: {missing})")

    # Orphan sweep: every file under assets/ is referenced somewhere
    used = h + c + j
    orphans = [str(p.relative_to(OUT)) for p in (OUT / "assets").rglob("*")
               if p.is_file() and p.stem not in used and p.parent.name != "icons"]
    check(not orphans, f"no orphan assets ({orphans})")
    print(f"  audit: {len(refs)} asset refs resolved")


def stamp_cache_bust():
    css = (OUT / "css" / "styles.css").read_bytes()
    js = (OUT / "js" / "deck.js").read_bytes() + (OUT / "js" / "edit.js").read_bytes()
    v = hashlib.sha256(css + js).hexdigest()[:12]
    p = OUT / "index.html"
    h = p.read_text(encoding="utf-8")
    h, n = re.subn(r'(css/styles\.css|js/deck\.js|js/edit\.js)\?v=[0-9a-z]+', lambda m: f"{m.group(1)}?v={v}", h)
    check(n == 3, f"cache-bust stamped on css + deck.js + edit.js ({n})")
    p.write_text(h, encoding="utf-8")
    print(f"  cache-bust: v={v}")


def main():
    print("Building PFL x MrQ …")
    prepare_source()
    build_logos()
    build_icons()
    build_images()
    build_photos()
    build_video()
    build_html()
    build_css()
    build_js()
    build_round4()
    build_editing()
    audit()
    stamp_cache_bust()
    shutil.copy2(Path(__file__), OUT / "make_mrq.py")
    print(f"\n{CHECKS - len(FAILURES)}/{CHECKS} checks passed")
    if FAILURES:
        for f in FAILURES:
            print("  FAIL:", f)
        sys.exit(1)


if __name__ == "__main__":
    main()
