import re, os, sys, json, html as H, hashlib, subprocess, datetime
from concurrent.futures import ThreadPoolExecutor

ROOT = "/home/user/alpinrunner"
CACHE = "/tmp/claude-0/-home-user/0446de9f-85f4-50e0-a497-61171e26bb77/scratchpad/cache"
LIVE = "https://www.alpinrunner.ch"
TODAY = datetime.date.today()

def cget(u):
    p = os.path.join(CACHE, hashlib.md5((LIVE + u).encode()).hexdigest() + ".html")
    return open(p, encoding="utf-8", errors="ignore").read() if os.path.exists(p) else None

index = [l for l in open(os.path.join(CACHE, "_index.txt")).read().split("\n") if l]
PAGES = {u: cget(u) for u in index}
SITE_URLS = {u for u in PAGES if "?" not in u}
ASSETS = set()      # local files to download

def outpath(u):
    return "index.html" if u == "/" else u.lstrip("/")

def relp(frm, to):
    return os.path.relpath(to, os.path.dirname(frm) or ".")

# ---------------------------------------------------------------- link/asset rewriting
def norm_url(h):
    h = h.replace("&amp;", "&").strip()
    for b in (LIVE, "http://www.alpinrunner.ch", "https://alpinrunner.ch", "http://alpinrunner.ch"):
        if h.startswith(b):
            h = h[len(b):] or "/"
    return h

def local_asset(path):
    path = path.lstrip("/")
    path = re.sub(r"%20", "%20", path)
    ASSETS.add(path)
    return path

def rewrite(frag, frm):
    """frm = output path of the page, used to build relative links."""
    def img(m):
        tag = m.group(0)
        src = re.search(r'src="([^"]+)"', tag)
        if not src: return tag
        s = norm_url(src.group(1))
        if s.startswith("/assets/") or s.startswith("assets/") or s.startswith("/files/") or s.startswith("files/"):
            lp = local_asset(s)
            new = relp(frm, lp)
        else:
            new = src.group(1)
        alt = re.search(r'alt="([^"]*)"', tag)
        cl = re.search(r'class="([^"]*)"', tag)
        return f'<img src="{new}" alt="{alt.group(1) if alt else ""}"' + (f' class="{cl.group(1)}"' if cl else ' loading="lazy"') + '>'
    frag = re.sub(r"<img\b[^>]*>", img, frag)

    # lightbox links: point to the (local) image inside
    def lb(m):
        inner = m.group(2)
        im = re.search(r'<img src="([^"]+)"', inner)
        attrs = m.group(1)
        if im:
            return f'<a href="{im.group(1)}" data-lightbox="1">{inner}</a>'
        return m.group(0)
    frag = re.sub(r'<a\b([^>]*data-lightbox[^>]*)>([\s\S]*?)</a>', lb, frag)

    def a(m):
        tag = m.group(0)
        hm = re.search(r'href="([^"]*)"', tag)
        if not hm: return tag
        raw = hm.group(1)
        if raw.startswith("mailto:") or raw.startswith("tel:") or raw.startswith("#"): return tag
        h = norm_url(raw)
        new = None
        if h.startswith("/") or not re.match(r"^[a-z]+:", h):
            hh = h if h.startswith("/") else "/" + h
            base = hh.split("#")[0]
            frag_ = ("#" + hh.split("#")[1]) if "#" in hh else ""
            if base in SITE_URLS and base != "/":
                new = relp(frm, outpath(base)) + frag_
            elif base == "/":
                new = relp(frm, "index.html") + frag_
            elif base.lower().endswith(".pdf") and base.startswith("/files/"):
                lp = local_asset(base)
                new = relp(frm, lp)
            else:
                new = LIVE + (hh if hh.startswith("/") else "/" + hh)
        else:
            new = raw
        tag = tag.replace(f'href="{raw}"', f'href="{new}"')
        if new.startswith("http") and "target=" not in tag:
            tag = tag[:-1] + ' target="_blank" rel="noopener">'
        return tag
    frag = re.sub(r"<a\b[^>]*>", a, frag)
    return frag

# ---------------------------------------------------------------- sanitising
def clean(frag):
    frag = re.sub(r"<!--[\s\S]*?-->", "", frag)
    frag = re.sub(r"<script[\s\S]*?</script>", "", frag)
    frag = re.sub(r"<style[\s\S]*?</style>", "", frag)
    frag = re.sub(r'\s(style|onclick|onchange|data-rsts-[a-z-]+)="[^"]*"', "", frag)
    frag = re.sub(r'<(span|div)[^>]*class="invisible"[^>]*>[\s\S]*?</\1>', "", frag)
    frag = re.sub(r"<span[^>]*class=\"invisible\"[^>]*></span>", "", frag)
    frag = frag.replace("&nbsp;", " ")
    # accordions -> details
    def acc_start(m):
        title = m.group(1).strip()
        op = " open" if str(TODAY.year) in title else ""
        return f'<details class="acc"{op}><summary>{title}</summary><div class="acc-body">'
    frag = re.sub(r'<section class="ce_accordionStart[^>]*>\s*<div class="toggler">([\s\S]*?)</div>\s*<div class="accordion">\s*<div>', acc_start, frag)
    frag = re.sub(r"</div>\s*</div>\s*</section>", "</div></details>", frag)
    return frag

def form_cta(pageurl, label):
    return (f'<div class="cta-box"><b>{label}</b>'
            f'<p>Dieses Formular läuft weiterhin auf der bestehenden Website von alpinrunner.ch.</p>'
            f'<a class="btn blue" href="{LIVE}{pageurl}" target="_blank" rel="noopener">Zum Formular</a></div>')

def replace_forms(frag, pageurl, label):
    return re.sub(r"<form\b[\s\S]*?</form>", lambda m: form_cta(pageurl, label), frag)

def get_main(h):
    a = h.find('<div class="mod_article')
    e = h.find("</main>")
    return h[a:e] if a >= 0 else ""

def get_title(h):
    m = re.search(r"<title>([^<]*)</title>", h)
    t = H.unescape(m.group(1)).strip() if m else ""
    return re.sub(r"\s*-\s*alpinrunner\s*$", "", t)

# ---------------------------------------------------------------- layout
NAV = [("Alpinrunner", "alpinrunner-trailrun.html"), ("Team", "team.html"), ("Agenda", "agenda.html"),
       ("Laufstrecken", "laufstrecken.html")]
SUB = [("News von Alpinrunners", "news-von-alpinrunners.html"), ("Alpinrunner - Shop", "angebote.html"),
       ("Marktplatz", "marktplatz.html")]
FOOT = [("Links", "links.html"), ("Kontakt", "kontakt.html"), ("Unsere Partner", "unsere-partner.html"),
        ("Impressum", "impressum.html"), ("Datenschutz", "datenschutz.html")]

def header(frm, current=""):
    p = lambda t: relp(frm, t)
    cur = ' aria-current="page"'
    items = "".join(f'<li><a href="{p(u)}"{cur if u == current else ""}>{n}</a></li>' for n, u in NAV)
    sub = "".join(f'<li><a href="{p(u)}">{n}</a></li>' for n, u in SUB)
    return (f'<header class="top"><div class="wrap nav"><a class="logo" href="{p("index.html")}" aria-label="alpinrunner.ch Startseite">'
            f'<img src="{p("img/logo.png")}" alt="alpinrunner.ch"></a>'
            f'<button class="burger" id="burger" aria-expanded="false" aria-controls="menu">Menü</button>'
            f'<ul class="menu" id="menu">{items}<li class="has-sub"><a href="{p("news-von-alpinrunners.html")}" aria-haspopup="true">Dies und Das</a>'
            f'<ul class="sub">{sub}</ul></li></ul></div></header>')

def footer(frm):
    p = lambda t: relp(frm, t)
    nav = "".join(f'<li><a href="{p(u)}">{n}</a></li>' for n, u in NAV + SUB)
    more = "".join(f'<li><a href="{p(u)}">{n}</a></li>' for n, u in FOOT)
    return (f'<footer><div class="wrap"><div class="big">Alpin<br>runner</div><div class="cols">'
            f'<div><h4>Spenden</h4><div class="twint"><img src="{p("img/qr.png")}" alt="QR-Code Alpinrunner Twint">'
            f'<div>Spenden Twint<br><a href="https://www.facebook.com/pages/alpinrunnerch/118657284837463?fref=ts" target="_blank" rel="noopener">Alpinrunner auf Facebook</a></div></div></div>'
            f'<div><h4>Navigation</h4><ul>{nav}</ul></div><div><h4>Mehr</h4><ul>{more}</ul></div></div>'
            f'<p class="photos">Fotos: Alpinrunner.ch. Stimmungsbilder von Unsplash: Marek Piwnicki / Thierry Lemaitre, Alban Rozes, Vincent Tavernier.</p>'
            f'<div class="credit"><span>© Alpinrunner.ch</span><span>Original-Website: beba.ch, Landquart</span></div></div></footer>')

FONTS = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;500;700&family=Prompt:wght@900&display=swap">'

def page(frm, title, body, current="", desc=""):
    p = lambda t: relp(frm, t)
    d = desc or "Alpinrunner Chur: Laufstrecken in Graubünden seit 2004, Lauftreff jeden Mittwoch, Agenda, Team und mehr."
    return (f'<!doctype html>\n<html lang="de"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'<title>{H.escape(title)}</title><meta name="description" content="{H.escape(d)}">'
            f'{FONTS}<link rel="stylesheet" href="{p("style.css")}"></head><body>\n'
            f'{header(frm, current)}\n{body}\n{footer(frm)}\n<script src="{p("site.js")}"></script></body></html>')

# ---------------------------------------------------------------- generic pages
SECTION = {"agenda-detail": ("Agenda", "agenda.html"), "streckendetail": ("Laufstrecken", "laufstrecken.html"),
           "news-detail": ("News", "news-von-alpinrunners.html")}
LABELS = {"/alpinrunner-trailrun.html": "Alpinrunner", "/links.html": "Links", "/kontakt.html": "Kontakt",
          "/unsere-partner.html": "Partner", "/impressum.html": "Impressum", "/datenschutz.html": "Datenschutz",
          "/angebote.html": "Shop", "/marktplatz.html": "Marktplatz", "/news-von-alpinrunners.html": "News",
          "/agenda.html": "Agenda", "/kontakt-neumitglied-alpinrunner.html": "Alpinrunner Freund"}
FORMS = {"/kontakt.html": "Deine Fragen an alpinrunner.ch", "/kontakt-neumitglied-alpinrunner.html": "Anmeldung Alpinrunner Freund",
         "/marktplatz.html": "Deinen Eintrag im Marktplatz erfassen", "/news-von-alpinrunners.html": "Deine News für uns"}

def render_generic(u):
    h = PAGES[u]
    frm = outpath(u)
    main = get_main(h)
    main = replace_forms(main, u, FORMS.get(u, "Formular"))
    main = clean(main)
    t = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", main)
    heading = H.unescape(re.sub(r"<[^>]+>", "", t.group(1))).strip() if t else get_title(h)
    if t: main = main.replace(t.group(0), "", 1)
    main = re.sub(r"<h1\b", "<h2", main); main = main.replace("</h1>", "</h2>")
    main = rewrite(main, frm)
    seg = u.split("/")[1] if u.count("/") > 1 else ""
    if seg == "streckendetail":
        wm = re.search(r'<div class="field wegname">[\s\S]*?<span class="text">([^<]*)</span>', h)
        if wm:
            nm = H.unescape(wm.group(1)).strip()
            mm = re.match(r"^(\d{4})_(\d\d)_(\d\d)_(.*)$", nm)
            heading = (mm.group(4) if mm else nm).replace("_", " ").strip()
            heading = re.sub(r"(?<=[a-zäöü])(?=[A-ZÄÖÜ])", " ", heading)
    if seg in SECTION:
        eyebrow, back = SECTION[seg]
        crumb = f'<a class="back" href="{relp(frm, back)}">← {eyebrow}</a>'
    else:
        eyebrow = LABELS.get(u, "Alpinrunner"); crumb = ""
    kind = seg or u.strip("/").replace(".html", "")
    hero = (f'<section class="page-hero"><div class="wrap">{crumb or "<span class=label>" + eyebrow + "</span>"}'
            f'<h1>{H.escape(heading)}</h1></div></section>')
    body = f'<main data-kind="{kind}">{hero}<section class="prose-sec"><div class="wrap prose">{main}</div></section></main>'
    cur = {"/agenda.html": "agenda.html", "/team.html": "team.html"}.get(u, "")
    if seg == "agenda-detail": cur = "agenda.html"
    if seg == "streckendetail": cur = "laufstrecken.html"
    return page(frm, f"{heading} | Alpinrunner Chur", body, cur)

# ---------------------------------------------------------------- Laufstrecken
def parse_routes():
    items = []
    keys = ["/laufstrecken.html"] + [f"/laufstrecken.html?page_e44={n}" for n in range(2, 16)]
    seen = set()
    for k in keys:
        h = PAGES.get(k)
        if not h: continue
        for it in re.findall(r'<div class="item[^"]*">([\s\S]*?)</div>\s*(?=<div class="item|</div>\s*</div>\s*(?:<!--|<div class="pagination|<nav|\n))', h):
            pass
        for blk in h.split('<div class="item')[1:]:
            blk = blk.split('<div class="item')[0]
            def f(n):
                m = re.search(rf'<div class="field {n}">[\s\S]*?<div class="value">([\s\S]*?)</div>\s*</div>', blk)
                return H.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""
            link = re.search(r'<a href="(/streckendetail/[^"]+)">Details', blk)
            if not link: continue
            href = link.group(1)
            if href in seen: continue
            seen.add(href)
            items.append(dict(name=f("wegname"), art=f("streckenart"), kat=f("kategorie"), reg=f("region"),
                              len=f("streckenlaenge"), desc=f("kurzbeschrieb"), href=href))
    return items

def detail_date(href):
    h = PAGES.get(href)
    if not h: return None
    m = re.search(r'<div class="field datum">[\s\S]*?<span class="text">\s*(\d\d)\.(\d\d)\.(\d\d)', h)
    if m: return datetime.date(2000 + int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return None

def bucket(km):
    if km is None: return ""
    if km <= 10: return "bis 10 km"
    if km <= 15: return "11–15 km"
    if km <= 20: return "16–20 km"
    if km <= 25: return "21–25 km"
    if km <= 30: return "26–30 km"
    return "über 30 km"

def render_routes():
    items = parse_routes()
    out = []
    for r in items:
        m = re.match(r"^(\d{4})_(\d\d)_(\d\d)_(.*)$", r["name"])
        date = None
        if m:
            date = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))); title = m.group(4)
        else:
            date = detail_date(r["href"]); title = r["name"]
        title = title.replace("_", " ").strip()
        km = None
        mk = re.search(r"([\d.,]+)", r["len"])
        if mk:
            try: km = float(mk.group(1).replace(",", "."))
            except: pass
        out.append(dict(r, date=date, title=title, km=km, year=date.year if date else 0))
    out.sort(key=lambda r: (r["date"] or datetime.date(1900, 1, 1)), reverse=True)
    frm = "laufstrecken.html"
    def opts(key, extra=None):
        vals = sorted({r[key] for r in out if r[key]}) if not extra else extra
        return "".join(f'<option value="{H.escape(v)}">{H.escape(v)}</option>' for v in vals)
    years = sorted({str(r["year"]) for r in out if r["year"]}, reverse=True)
    buckets = ["bis 10 km", "11–15 km", "16–20 km", "21–25 km", "26–30 km", "über 30 km"]
    cards = []
    for r in out:
        href = relp(frm, outpath(r["href"])) if r["href"] in SITE_URLS else LIVE + r["href"]
        ds = r["date"].strftime("%d.%m.%Y") if r["date"] else ""
        meta = " · ".join(x for x in [r["len"], r["kat"], r["reg"]] if x)
        cards.append(
            f'<a class="route" href="{href}" data-art="{H.escape(r["art"])}" data-reg="{H.escape(r["reg"])}" '
            f'data-kat="{H.escape(r["kat"])}" data-dist="{bucket(r["km"])}" data-year="{r["year"] or ""}" '
            f'data-q="{H.escape((r["title"] + " " + r["desc"]).lower())}">'
            f'<span class="label">{H.escape(ds or r["art"])}</span><h3>{H.escape(r["title"])}</h3>'
            f'<p>{H.escape(r["desc"])}</p><span class="meta">{H.escape(meta)}</span><span class="art">{H.escape(r["art"])}</span></a>')
    sel = lambda i, lab, o: f'<label for="f-{i}"><span class="label">{lab}</span><select id="f-{i}" data-f="{i}"><option value="">Alle</option>{o}</select></label>'
    intro = ('<p>Laufend wird diese Datenbank erweitert, Links zu Berichten älteren Datums ist auf dem '
             f'<a href="{LIVE}/_Archiv/" target="_blank" rel="noopener">Alpinrunner Archiv</a> zu finden, sowie auf dieser Seite in der <a href="agenda.html">AGENDA</a>.</p>')
    body = (f'<main data-kind="routes"><section class="page-hero"><div class="wrap"><span class="label">Laufstrecken</span><h1>Streckenauswahl</h1>'
            f'<div class="prose" style="margin-top:24px">{intro}</div></div></section>'
            f'<section class="prose-sec" style="padding-top:0"><div class="wrap">'
            f'<div class="filters"><label for="f-q"><span class="label">Suche</span><input id="f-q" type="search" placeholder="Ort, Berg, Strecke …"></label>'
            f'{sel("art", "Streckenart", opts("art"))}{sel("reg", "Region", opts("reg"))}{sel("kat", "Kategorie", opts("kat"))}'
            f'{sel("dist", "Distanz", opts("x", buckets))}{sel("year", "Jahr", opts("x", years))}'
            f'<button class="btn line" id="f-reset" type="button">Zurücksetzen</button></div>'
            f'<p class="count" id="f-count" aria-live="polite"></p><div class="routes" id="routes">{"".join(cards)}</div>'
            f'<div class="more-row"><button class="btn" id="f-more" type="button">Mehr anzeigen</button></div></div></section></main>')
    return page(frm, "Laufstrecken | Alpinrunner Chur", body, "laufstrecken.html"), len(out)

# ---------------------------------------------------------------- agenda events (for home)
DE_DAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
DE_MON = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]

def parse_events():
    h = PAGES["/agenda.html"]
    ev = []
    for m in re.finditer(r'<div class="event[^"]*?(specialevent)?[^"]*">\s*<time datetime="(\d{4}-\d\d-\d\d)"[^>]*>([^<]*)</time>\s*<a href="([^"]+)"[^>]*>([^<]*)</a>', h):
        ev.append(dict(s=bool(m.group(1)), d=m.group(2), l=m.group(3), u=m.group(4), t=H.unescape(m.group(5))))
    seen = set(); out = []
    for e in ev:
        k = (e["d"], e["u"])
        if k in seen: continue
        seen.add(k); out.append(e)
    return out

def event_rows(events, frm):
    up = [e for e in events if e["d"] >= TODAY.isoformat()]
    up.sort(key=lambda e: e["d"])
    rows = ""
    for e in up[:3]:
        d = datetime.date.fromisoformat(e["d"])
        href = relp(frm, outpath(e["u"])) if e["u"] in SITE_URLS else LIVE + e["u"]
        rows += (f'<a class="row-ev" href="{href}"><div class="d">{d.day:02d}. {DE_MON[d.month-1]}<small>{DE_DAYS[d.weekday()]}</small></div>'
                 f'<div><h3>{H.escape(e["t"])}</h3></div><span class="go" aria-hidden="true">→</span></a>')
    return rows, up

# ---------------------------------------------------------------- home & team
def parse_home():
    h = PAGES["/"]
    slides = []
    for src in re.findall(r'<img src="(/files/NewsbilderStartseite/[^"]+)"', h.replace("\\/", "/")):
        if src not in slides: slides.append(src)
    cap = re.search(r'<div class="rte">\s*<p>([\s\S]*?)</p>', h[h.find("rocksolid"):])
    caption_html = cap.group(1) if cap else ""
    news = []
    for blk in h.split('<div class="layout_latest')[1:]:
        blk = blk.split('<div class="layout_latest')[0]
        t = re.search(r"<h2>([^<]*)</h2>", blk)
        im = re.search(r'<img src="([^"]+)"', blk)
        tz = re.search(r'<div class="teaser">([\s\S]*?)</div>', blk)
        ln = re.search(r'<p class="more"><a href="([^"]+)"', blk)
        if t and im and ln:
            news.append(dict(t=H.unescape(t.group(1)), img=im.group(1), teaser=H.unescape(re.sub(r"<[^>]+>", " ", tz.group(1)) if tz else "").strip(), u=ln.group(1)))
    return slides, caption_html, news

def render_home(events):
    frm = "index.html"
    main = open(os.path.join(ROOT, "_src/index.main.html"), encoding="utf-8").read()
    slides, caption, news = parse_home()
    # hero slider
    sl = "".join(f'<img src="{local_asset(s)}" alt=""{" class=on" if i == 0 else ""}>'.replace(" class=on", ' class="on"') for i, s in enumerate(slides))
    cap = rewrite(caption, frm)
    fig = (f'<figure class="slider" id="slider">{sl}<figcaption>{cap}</figcaption></figure>')
    main = re.sub(r'<figure><img src="img/runner-clouds\.jpg"[^>]*></figure>', lambda m: fig, main)
    # tag -> next event
    rows, up = event_rows(events, frm)
    if up:
        e = up[0]; d = datetime.date.fromisoformat(e["d"])
        href = relp(frm, outpath(e["u"])) if e["u"] in SITE_URLS else LIVE + e["u"]
        tag = f'<a class="tag" id="next-ev" href="{href}"><b>Nächster Termin · {d.day}. {DE_MON[d.month-1]}</b> {H.escape(e["t"])} → Details</a>'
    else:
        tag = f'<a class="tag" id="next-ev" href="agenda.html"><b>Agenda</b> Alle Termine ansehen →</a>'
    main = re.sub(r'<a class="tag"[\s\S]*?</a>', lambda m: tag, main, count=1)
    # news
    cards = ""
    for n in news[:4]:
        href = relp(frm, outpath(n["u"])) if n["u"] in SITE_URLS else LIVE + n["u"]
        img = local_asset(n["img"])
        lbl = n["teaser"][:60]
        cards += (f'<a class="post rv" href="{href}"><div class="ph"><img src="{img}" alt="{H.escape(n["t"])}" loading="lazy"></div>'
                  f'<span class="label">{H.escape(lbl)}</span><h3>{H.escape(n["t"])}</h3><span class="more">Weiterlesen …</span></a>')
    main = re.sub(r'<div class="news">[\s\S]*?</div>\s*</div>\s*</section>\s*<section class="band">',
                  lambda m: f'<div class="news">{cards}</div></div></section><section class="band">', main, count=1)
    # agenda rows
    main = re.sub(r'<div class="rows rv" id="home-rows">[\s\S]*?</div>\s*<p class="note', lambda m: f'<div class="rows rv" id="home-rows">{rows}</div><p class="note', main, count=1) \
        if 'id="home-rows"' in main else re.sub(r'<div class="rows rv">[\s\S]*?</div>\s*<p class="note', lambda m: f'<div class="rows rv" id="home-rows">{rows}</div><p class="note', main, count=1)
    main = rewrite(main, frm)
    main = main.replace('href="https://www.alpinrunner.ch"', 'href="index.html"')
    js = json.dumps([dict(d=e["d"], t=e["t"], u=(outpath(e["u"]) if e["u"] in SITE_URLS else LIVE + e["u"])) for e in events], ensure_ascii=False)
    main += f'<script>window.AR_EVENTS={js};</script>'
    return page(frm, "Alpinrunner Chur", main, ""), len(news), len(slides)

def render_team():
    frm = "team.html"
    main = open(os.path.join(ROOT, "_src/team.main.html"), encoding="utf-8").read()
    main = rewrite(main, frm)
    return page(frm, "Team | Alpinrunner Chur", main, "team.html")

# ---------------------------------------------------------------- run
def write(path, content):
    fp = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(fp) or ROOT, exist_ok=True)
    open(fp, "w", encoding="utf-8").write(content)

def download(path):
    fp = os.path.join(ROOT, urldecode(path))
    if os.path.exists(fp) and os.path.getsize(fp) > 0: return path, 0
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    for i in range(3):
        r = subprocess.run(["curl", "-sS", "-L", "--max-time", "60", "-o", fp, "-w", "%{http_code}", f"{LIVE}/{path}"], capture_output=True, text=True)
        if r.stdout.strip() == "200": return path, os.path.getsize(fp)
    if os.path.exists(fp): os.remove(fp)
    return path, -1

def urldecode(p):
    from urllib.parse import unquote
    return unquote(p)

def main():
    events = parse_events()
    n = 0
    skip = {"/", "/team.html", "/laufstrecken.html"}
    for u in sorted(SITE_URLS):
        if u in skip: continue
        write(outpath(u), render_generic(u)); n += 1
    rt, nroutes = render_routes(); write("laufstrecken.html", rt)
    hm, nn, ns = render_home(events); write("index.html", hm)
    write("team.html", render_team())
    print("pages", n, "routes", nroutes, "events", len(events), "home news", nn, "slides", ns, "assets", len(ASSETS))
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(download, sorted(ASSETS)))
    bad = [p for p, s in res if s < 0]
    tot = sum(s for p, s in res if s > 0)
    print("downloaded", len(res), "bytes", tot, "failed", len(bad), bad[:8])
    big = sorted(((s, p) for p, s in res if s > 3_000_000), reverse=True)[:8]
    print("big", big)

main()
