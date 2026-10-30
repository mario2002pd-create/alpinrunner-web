import re, os, subprocess, sys, time, hashlib
from concurrent.futures import ThreadPoolExecutor

BASE = "https://www.alpinrunner.ch"
CACHE = "/tmp/claude-0/-home-user/0446de9f-85f4-50e0-a497-61171e26bb77/scratchpad/cache"
os.makedirs(CACHE, exist_ok=True)

def cpath(url):
    return os.path.join(CACHE, hashlib.md5(url.encode()).hexdigest() + ".html")

def fetch(url):
    p = cpath(url)
    if os.path.exists(p) and os.path.getsize(p) > 200:
        return open(p, encoding="utf-8", errors="ignore").read()
    for i in range(4):
        r = subprocess.run(["curl", "-sS", "-L", "--max-time", "40", "-o", p, "-w", "%{http_code}", url],
                           capture_output=True, text=True)
        if r.stdout.strip() == "200":
            time.sleep(0.15)
            return open(p, encoding="utf-8", errors="ignore").read()
        time.sleep(1.5 * (i + 1))
    print("FAIL", url, r.stdout, r.stderr[:100], file=sys.stderr)
    if os.path.exists(p):
        os.remove(p)
    return None

def internal_links(html):
    out = set()
    for h in re.findall(r'href="([^"#]+)"', html):
        h = h.replace("&amp;", "&")
        if h.startswith(BASE): h = h[len(BASE):]
        if h.startswith("http://www.alpinrunner.ch"): h = h[len("http://www.alpinrunner.ch"):]
        if not h.startswith("/"): continue
        if "?" in h: continue
        if not h.endswith(".html"): continue
        out.add(h)
    return out

def main():
    seeds = ["/", "/agenda.html", "/laufstrecken.html", "/news-von-alpinrunners.html", "/angebote.html",
             "/marktplatz.html", "/links.html", "/kontakt.html", "/unsere-partner.html", "/impressum.html",
             "/datenschutz.html", "/alpinrunner-trailrun.html", "/kontakt-neumitglied-alpinrunner.html", "/team.html"]
    # paginated route list
    lists = [f"/laufstrecken.html?page_e44={n}" for n in range(2, 16)]
    seen, todo = set(), list(seeds) + lists
    pages = {}
    with ThreadPoolExecutor(4) as ex:
        while todo:
            batch = [u for u in todo if u not in seen]
            todo = []
            for u in batch: seen.add(u)
            res = list(ex.map(lambda u: (u, fetch(BASE + u)), batch))
            for u, h in res:
                if h is None: continue
                pages[u] = h
                for l in internal_links(h):
                    if l not in seen and (l.startswith("/agenda-detail") or l.startswith("/streckendetail")
                                          or l.startswith("/news-detail") or l in seeds or l.count("/") == 1):
                        todo.append(l)
            print("fetched", len(pages), "queue", len(set(todo) - seen), flush=True)
    with open(os.path.join(CACHE, "_index.txt"), "w") as f:
        f.write("\n".join(sorted(pages)))
    print("TOTAL", len(pages))

main()
