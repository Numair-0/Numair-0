"""Builds the animated SVGs for the profile README from live GitHub data.

Usage: python scripts/generate.py <output-dir>
Env:   GH_TOKEN  token for the GitHub GraphQL API (a personal token also counts private work)
       GH_USER   GitHub username (default: Numair-0)
       FIXTURE   optional path to a JSON file with pre-fetched data, for local testing
"""
import base64, datetime as dt, html, json, os, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1]
USER = os.environ.get("GH_USER", "Numair-0")
TODAY = dt.datetime.now(dt.timezone.utc).date()

TEAL, INDIGO, PINK, AMBER = "#5eead4", "#818cf8", "#f472b6", "#fbbf24"
LANG_COLORS = {"TypeScript": "#3b82f6", "JavaScript": "#facc15", "PHP": "#8b93d6", "CSS": "#a78bfa",
               "HTML": "#f97316", "Python": "#34d399", "SCSS": "#f472b6", "Shell": "#94a3b8",
               "Jupyter Notebook": "#fb923c", "Java": "#f87171", "Dart": "#22d3ee", "Vue": "#4ade80",
               "Blade": "#fb7185", "Go": "#2dd4bf", "C++": "#f472b6", "Kotlin": "#c084fc"}
# Repos shown on the project cards
CARD_REPOS = {"smarted": "smarted_battalion_flow", "shifra": "assistant"}


# ---------------------------------------------------------------- data
QUERY = """query($login:String!){user(login:$login){
  contributionsCollection{contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}
  repositories(first:100,ownerAffiliations:OWNER,isFork:false,orderBy:{field:PUSHED_AT,direction:DESC}){nodes{
    name description isPrivate pushedAt stargazerCount url primaryLanguage{name color}
    languages(first:15,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}}
    defaultBranchRef{target{...on Commit{history{totalCount}}}}}}}}"""


def fetch():
    if os.environ.get("FIXTURE"):
        return json.load(open(os.environ["FIXTURE"]))
    req = urllib.request.Request("https://api.github.com/graphql",
                                 data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
                                 headers={"Authorization": f"bearer {os.environ['GH_TOKEN']}", "User-Agent": USER})
    res = json.load(urllib.request.urlopen(req))
    if "errors" in res:
        sys.exit(f"GitHub API error: {res['errors']}")
    u = res["data"]["user"]
    cal = u["contributionsCollection"]["contributionCalendar"]
    repos = []
    for r in u["repositories"]["nodes"]:
        ref = r["defaultBranchRef"]
        repos.append({
            "name": r["name"], "description": r["description"], "private": r["isPrivate"],
            "pushed_at": r["pushedAt"], "stars": r["stargazerCount"], "url": r["url"],
            "language": (r["primaryLanguage"] or {}).get("name"),
            "languages": [[e["node"]["name"], e["node"]["color"], e["size"]] for e in r["languages"]["edges"]],
            "commits": ref["target"]["history"]["totalCount"] if ref else 0,
        })
    return {"total": cal["totalContributions"],
            "calendar": [[d["date"], d["contributionCount"]] for w in cal["weeks"] for d in w["contributionDays"]],
            "repos": repos}


def ago(iso):
    days = (TODAY - dt.date.fromisoformat(iso[:10])).days
    if days <= 0:
        return "today"
    if days < 30:
        return f"{days}d ago"
    if days < 365:
        return f"{days // 30}mo ago"
    return f"{days // 365}y ago"


def streaks(calendar):
    counts = [c for d, c in sorted(calendar) if dt.date.fromisoformat(d) <= TODAY]
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    current = 0
    days = counts[:-1] if counts and counts[-1] == 0 else counts  # today may not have commits yet
    for c in reversed(days):
        if not c:
            break
        current += 1
    return current, longest, sum(1 for c in counts if c)


def esc(s):
    return html.escape(s or "", quote=True)


# ---------------------------------------------------------------- svg helpers
def b64(name):
    return base64.b64encode(open(os.path.join(HERE, "fonts", name + ".woff2"), "rb").read()).decode()


FONT_CSS = "".join(
    f"@font-face{{font-family:'{fam}';font-weight:{w};src:url(data:font/woff2;base64,{b64(f)}) format('woff2')}}"
    for fam, w, f in [("SG", 700, "sg700"), ("SG", 500, "sg500"), ("JB", 400, "jb400"), ("JB", 600, "jb600")]
)
STYLE = f"""<style>{FONT_CSS}
.d7{{font-family:'SG','Segoe UI',sans-serif;font-weight:700}}
.d5{{font-family:'SG','Segoe UI',sans-serif;font-weight:500}}
.m4{{font-family:'JB',Consolas,monospace;font-weight:400}}
.m6{{font-family:'JB',Consolas,monospace;font-weight:600}}
</style>"""


def svg(w, h, body, defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'{STYLE}<defs>{defs}</defs>{body}</svg>')


def write(name, content):
    with open(os.path.join(OUT, name), "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def chips(x, y, labels, color):
    out = []
    for label in labels:
        w = len(label) * 7.8 + 26
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="30" rx="15" fill="{color}" fill-opacity="0.1" stroke="{color}" stroke-opacity="0.45"/>'
                   f'<text x="{x + w / 2}" y="{y + 20}" text-anchor="middle" class="m4" font-size="13" fill="{color}">{label}</text>')
        x += w + 10
    return "".join(out)


def card_frame(w, h, accent, uid):
    """Dark card with a corner glow, dot grid and a light running around the border."""
    defs = (f'<radialGradient id="g{uid}" cx="100%" cy="0%" r="80%"><stop offset="0" stop-color="{accent}" stop-opacity="0.22"/>'
            f'<stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>'
            f'<pattern id="dots{uid}" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="#ffffff" fill-opacity="0.05"/></pattern>'
            f'<clipPath id="f{uid}"><rect width="{w}" height="{h}" rx="20"/></clipPath>')
    body = (f'<g clip-path="url(#f{uid})"><rect width="{w}" height="{h}" fill="#090d18"/>'
            f'<rect width="{w}" height="{h}" fill="url(#dots{uid})"/><rect width="{w}" height="{h}" fill="url(#g{uid})"/></g>'
            f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="19" fill="none" stroke="#ffffff" stroke-opacity="0.08"/>'
            f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="19" fill="none" stroke="{accent}" stroke-width="2" stroke-linecap="round" pathLength="1000" stroke-dasharray="140 860">'
            f'<animate attributeName="stroke-dashoffset" values="1000;0" dur="6s" repeatCount="indefinite"/></rect>')
    return defs, body


def status(x, y, color):
    return (f'<rect x="{x}" y="{y}" width="96" height="28" rx="14" fill="{color}" fill-opacity="0.1" stroke="{color}" stroke-opacity="0.4"/>'
            f'<circle cx="{x + 18}" cy="{y + 14}" r="4" fill="{color}"><animate attributeName="opacity" values="1;0.2;1" dur="1.6s" repeatCount="indefinite"/></circle>'
            f'<text x="{x + 30}" y="{y + 19}" class="m6" font-size="12" letter-spacing="1.5" fill="{color}">ACTIVE</text>')


def icon_box(x, y, s, color, glyph):
    return (f'<rect x="{x}" y="{y}" width="{s}" height="{s}" rx="16" fill="{color}" fill-opacity="0.12" stroke="{color}" stroke-opacity="0.45"/>'
            f'<g transform="translate({x},{y})" stroke="{color}" fill="none" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">{glyph}</g>')


def repo_meta(repo, fallback):
    """Short live line for a project card, e.g. 'TypeScript · 120 commits · 2d ago'."""
    if not repo:
        return fallback
    return f"{repo['language'] or fallback}  ·  {repo['commits']} commits  ·  {ago(repo['pushed_at'])}"


# ---------------------------------------------------------------- header
def header():
    nodes = [(70, 50), (170, 110), (90, 200), (250, 60), (260, 180), (150, 280), (330, 250), (40, 140),
             (1150, 60), (1030, 120), (1120, 200), (950, 70), (940, 200), (1060, 280), (870, 260), (1170, 150)]
    hubs = {(170, 110), (1030, 120)}
    defs = f'''
<radialGradient id="glow" cx="50%" cy="0%" r="75%"><stop offset="0" stop-color="#1e293b"/><stop offset="1" stop-color="#06080e"/></radialGradient>
<linearGradient id="beam" x1="0" x2="1"><stop offset="0" stop-color="{TEAL}" stop-opacity="0"/><stop offset="0.5" stop-color="{TEAL}"/><stop offset="1" stop-color="{INDIGO}" stop-opacity="0"/></linearGradient>
<linearGradient id="shine" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="260" y2="0">
  <stop offset="0" stop-color="{TEAL}" stop-opacity="0"/><stop offset="0.5" stop-color="{TEAL}"/><stop offset="1" stop-color="{INDIGO}" stop-opacity="0"/>
  <animateTransform attributeName="gradientTransform" type="translate" values="-300 0;1300 0" dur="5s" repeatCount="indefinite"/>
</linearGradient>
<clipPath id="frame"><rect width="1200" height="340" rx="20"/></clipPath>
<clipPath id="track"><rect x="430" y="208" width="340" height="4"/></clipPath>
<path id="p1" d="M70 50 L170 110 L260 180 L330 250"/><path id="p2" d="M1150 60 L1030 120 L940 200 L870 260"/>
<path id="p3" d="M40 140 L170 110 L250 60"/><path id="p4" d="M950 70 L1030 120 L1120 200 L1060 280"/>'''
    body = f'''<g clip-path="url(#frame)">
<rect width="1200" height="340" fill="url(#glow)"/>
<g fill="none" stroke="#94a3b8" stroke-opacity="0.16">
  <path d="M40 140 L170 110 M70 50 L170 110 L250 60 M170 110 L260 180 L330 250 L150 280 L90 200 L170 110 M90 200 L40 140"/>
  <path d="M1170 150 L1150 60 L1030 120 L950 70 M1030 120 L1120 200 L1170 150 M1030 120 L940 200 L870 260 M940 200 L1060 280 L1120 200"/>
</g>
<g fill="#cbd5e1" fill-opacity="0.4">{"".join(f'<circle cx="{x}" cy="{y}" r="{4 if (x, y) in hubs else 2.6}"/>' for x, y in nodes)}</g>
<g fill="none" stroke="{TEAL}" stroke-opacity="0.5">
  <circle cx="170" cy="110" r="4"><animate attributeName="r" values="4;18" dur="2.4s" repeatCount="indefinite"/><animate attributeName="stroke-opacity" values="0.6;0" dur="2.4s" repeatCount="indefinite"/></circle>
  <circle cx="1030" cy="120" r="4" stroke="{INDIGO}"><animate attributeName="r" values="4;18" dur="2.4s" begin="1.2s" repeatCount="indefinite"/><animate attributeName="stroke-opacity" values="0.6;0" dur="2.4s" begin="1.2s" repeatCount="indefinite"/></circle>
</g>
<circle r="3" fill="{TEAL}"><animateMotion dur="4s" repeatCount="indefinite"><mpath href="#p1"/></animateMotion></circle>
<circle r="3" fill="{INDIGO}"><animateMotion dur="5s" begin="1s" repeatCount="indefinite"><mpath href="#p2"/></animateMotion></circle>
<circle r="2.5" fill="{INDIGO}"><animateMotion dur="4.5s" begin="2s" repeatCount="indefinite"><mpath href="#p3"/></animateMotion></circle>
<circle r="2.5" fill="{TEAL}"><animateMotion dur="3.5s" begin="0.5s" repeatCount="indefinite"><mpath href="#p4"/></animateMotion></circle>

<g text-anchor="middle">
  <text x="600" y="112" class="m6" font-size="14" letter-spacing="7" fill="{TEAL}">SOFTWARE ENGINEER<animate attributeName="opacity" values="0;1" dur="0.8s"/></text>
  <g><animate attributeName="opacity" values="0;0;1" keyTimes="0;0.4;1" dur="1.3s"/>
    <text x="600" y="186" class="d7" font-size="72" letter-spacing="-1.5" fill="#f1f5f9">Numair Ahmad Khan</text>
    <text x="600" y="186" class="d7" font-size="72" letter-spacing="-1.5" fill="url(#shine)">Numair Ahmad Khan</text>
  </g>
  <text x="600" y="256" class="d5" font-size="21" fill="#94a3b8">Architecting scalable systems  ·  Integrating machine learning<animate attributeName="opacity" values="0;0;1" keyTimes="0;0.6;1" dur="1.8s"/></text>
  <text x="600" y="298" class="m4" font-size="13" letter-spacing="1.5" fill="#64748b">curelex.in   ·   india   ·   open to collaborate<animate attributeName="opacity" values="0;0;1" keyTimes="0;0.7;1" dur="2.2s"/></text>
</g>
<rect x="430" y="209" width="340" height="1" fill="#ffffff" fill-opacity="0.08"/>
<g clip-path="url(#track)"><rect x="330" y="208" width="120" height="3" rx="1.5" fill="url(#beam)"><animate attributeName="x" values="330;770;330" dur="6s" repeatCount="indefinite"/></rect></g>
</g>
<rect x="0.5" y="0.5" width="1199" height="339" rx="20" fill="none" stroke="#ffffff" stroke-opacity="0.08"/>'''
    write("header.svg", svg(1200, 340, body, defs))


# ---------------------------------------------------------------- Curelex (wide)
def card_curelex():
    w, h = 1200, 320
    fdefs, frame = card_frame(w, h, TEAL, "c")
    glyph = ('<circle cx="18" cy="20" r="3.5"/><circle cx="18" cy="44" r="3.5"/><circle cx="46" cy="16" r="3.5"/>'
             '<circle cx="46" cy="32" r="3.5"/><circle cx="46" cy="48" r="3.5"/>'
             '<path d="M21 20 L43 16 M21 20 L43 32 M21 20 L43 48 M21 44 L43 16 M21 44 L43 32 M21 44 L43 48" stroke-width="1.4" stroke-opacity="0.7"/>')

    def box(x, y, bw, label, color):
        return (f'<rect x="{x}" y="{y}" width="{bw}" height="44" rx="10" fill="#0f172a" stroke="{color}" stroke-opacity="0.55"/>'
                f'<text x="{x + bw / 2}" y="{y + 27}" text-anchor="middle" class="m6" font-size="14" fill="#e2e8f0">{label}</text>')

    links = ["M790 92 H840", "M990 92 H1030", "M1090 114 V152 H955 V190", "M880 212 H790", "M725 114 V190"]
    flow = "".join(
        f'<path d="{d}" fill="none" stroke="#334155" stroke-width="1.5" stroke-dasharray="4 4"/>'
        f'<circle r="3.5" fill="{TEAL if i % 2 == 0 else INDIGO}"><animateMotion dur="{1.6 + i * 0.3:.1f}s" begin="{i * 0.4:.1f}s" repeatCount="indefinite" path="{d}"/></circle>'
        for i, d in enumerate(links))
    body = f'''{frame}
{icon_box(50, 44, 64, TEAL, glyph)}
<text x="134" y="70" class="m6" font-size="13" letter-spacing="2" fill="{TEAL}">FEATURED  ·  CURRENT ROLE</text>
<text x="134" y="98" class="m4" font-size="14" fill="#64748b">curelex.in  ↗</text>
{status(470, 52, TEAL)}
<text x="50" y="176" class="d7" font-size="50" letter-spacing="-1" fill="#f8fafc">Curelex</text>
<text x="50" y="212" class="d5" font-size="19" fill="#94a3b8">Platform architecture &amp; machine learning integration.</text>
<text x="50" y="238" class="d5" font-size="19" fill="#64748b">Services, data pipelines and model serving, built to scale.</text>
{chips(50, 262, ["System Design", "ML Pipelines", "APIs", "Scalable Backends"], TEAL)}
<text x="660" y="50" class="m4" font-size="12" fill="#475569">// system map</text>
{flow}
{box(660, 70, 130, "Client", INDIGO)}{box(840, 70, 150, "API Gateway", TEAL)}{box(1030, 70, 120, "Services", TEAL)}
{box(660, 190, 130, "Data", INDIGO)}{box(880, 190, 150, "ML Models", PINK)}
<text x="660" y="282" class="m4" font-size="12" fill="#475569">requests → services → models → insights</text>'''
    write("card-curelex.svg", svg(w, h, body, fdefs))


# ---------------------------------------------------------------- SmartEd
def card_smarted(repo):
    w, h = 600, 320
    fdefs, frame = card_frame(w, h, INDIGO, "s")
    glyph = '<path d="M8 24 L28 14 L48 24 L28 34 Z"/><path d="M16 28 V38 C16 42 40 42 40 38 V28"/><path d="M48 24 V36"/>'
    heights = [38, 56, 30, 64, 48, 72]
    bars = "".join(
        f'<rect x="{410 + i * 26}" width="16" rx="4" fill="{INDIGO}" fill-opacity="{0.45 + i * 0.09:.2f}">'
        f'<animate attributeName="height" values="{hh * 0.4:.0f};{hh};{hh * 0.6:.0f};{hh * 0.4:.0f}" dur="{3 + (i % 3) * 0.5}s" repeatCount="indefinite"/>'
        f'<animate attributeName="y" values="{290 - hh * 0.4:.0f};{290 - hh};{290 - hh * 0.6:.0f};{290 - hh * 0.4:.0f}" dur="{3 + (i % 3) * 0.5}s" repeatCount="indefinite"/></rect>'
        for i, hh in enumerate(heights))
    body = f'''{frame}
{icon_box(40, 40, 56, INDIGO, glyph)}
<text x="114" y="64" class="m6" font-size="12" letter-spacing="2" fill="{INDIGO}">SCHOOL ERP</text>
<text x="114" y="88" class="m4" font-size="13" fill="#64748b">{esc(repo_meta(repo, "TypeScript"))}</text>
{status(464, 44, INDIGO)}
<text x="40" y="160" class="d7" font-size="42" letter-spacing="-1" fill="#f8fafc">SmartEd</text>
<text x="40" y="194" class="d5" font-size="17" fill="#94a3b8">ERP for schools and institutions.</text>
<text x="40" y="218" class="d5" font-size="17" fill="#64748b">Students, staff, attendance, fees, reports.</text>
{chips(40, 256, ["TypeScript", "ERP", "Dashboards"], INDIGO)}
<path d="M402 291 H566" stroke="#334155"/>
{bars}'''
    write("card-smarted.svg", svg(w, h, body, fdefs))


# ---------------------------------------------------------------- Shifra
def card_shifra(repo):
    w, h = 600, 320
    fdefs, frame = card_frame(w, h, PINK, "a")
    glyph = '<path d="M28 10 C30 22 34 26 46 28 C34 30 30 34 28 46 C26 34 22 30 10 28 C22 26 26 22 28 10 Z"/>'
    wave = "".join(
        f'<rect x="{412 + i * 13}" width="6" rx="3" fill="{PINK}" fill-opacity="0.8">'
        f'<animate attributeName="height" values="6;{20 + (i * 7) % 28};6" dur="{0.9 + (i % 4) * 0.15:.2f}s" begin="{i * 0.08:.2f}s" repeatCount="indefinite"/>'
        f'<animate attributeName="y" values="268;{268 - (20 + (i * 7) % 28) / 2 + 3:.0f};268" dur="{0.9 + (i % 4) * 0.15:.2f}s" begin="{i * 0.08:.2f}s" repeatCount="indefinite"/></rect>'
        for i in range(12))
    body = f'''{frame}
<defs><clipPath id="type"><rect x="56" y="246" height="30" width="0"><animate attributeName="width" values="0;250;250;0" keyTimes="0;0.45;0.9;1" dur="6s" repeatCount="indefinite"/></rect></clipPath></defs>
{icon_box(40, 40, 56, PINK, glyph)}
<text x="114" y="64" class="m6" font-size="12" letter-spacing="2" fill="{PINK}">AI ASSISTANT</text>
<text x="114" y="88" class="m4" font-size="13" fill="#64748b">{esc(repo_meta(repo, "JavaScript"))}</text>
{status(464, 44, PINK)}
<text x="40" y="160" class="d7" font-size="42" letter-spacing="-1" fill="#f8fafc">Shifra</text>
<text x="40" y="194" class="d5" font-size="17" fill="#94a3b8">A personal AI assistant that understands</text>
<text x="40" y="218" class="d5" font-size="17" fill="#64748b">natural language and automates tasks.</text>
<rect x="40" y="244" width="330" height="40" rx="12" fill="#0f172a" stroke="{PINK}" stroke-opacity="0.35"/>
<text x="56" y="269" class="m4" font-size="14" fill="#e2e8f0" clip-path="url(#type)"><tspan fill="{PINK}">&gt; </tspan>hey shifra, plan my day</text>
{wave}'''
    write("card-shifra.svg", svg(w, h, body, fdefs))


# ---------------------------------------------------------------- languages chart
def languages(repos):
    totals, colors = {}, {}
    for r in repos:
        for name, color, size in r["languages"]:
            totals[name] = totals.get(name, 0) + size
            colors[name] = LANG_COLORS.get(name, color or "#94a3b8")
    total = sum(totals.values()) or 1
    ranked = sorted(totals.items(), key=lambda x: -x[1])
    data = [(k, 100 * v / total) for k, v in ranked[:5]]
    other = 100 - sum(p for _, p in data)
    top = data[0][1] if data else 1
    cx, cy, r = 250, 212, 76
    off, segs, rows = 0.0, [], []
    for i, (name, p) in enumerate(data + ([("Other", other)] if other > 0.5 else [])):
        c = colors.get(name, "#475569")
        segs.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{c}" stroke-width="26" pathLength="100" '
                    f'stroke-dasharray="{max(p - 0.6, 0.1):.2f} {100 - p + 0.6:.2f}" stroke-dashoffset="{-off:.2f}" transform="rotate(-90 {cx} {cy})">'
                    f'<animate attributeName="stroke-dasharray" values="0 100;{max(p - 0.6, 0.1):.2f} {100 - p + 0.6:.2f}" dur="1.2s" begin="{i * 0.15:.2f}s" fill="freeze"/></circle>')
        off += p
    for i, (name, p) in enumerate(data):
        c = colors[name]
        y = 128 + i * 44
        bw = 380 * p / top
        rows.append(f'<circle cx="530" cy="{y - 5}" r="5" fill="{c}"/>'
                    f'<text x="546" y="{y}" class="m6" font-size="15" fill="#e2e8f0">{esc(name)}</text>'
                    f'<rect x="680" y="{y - 11}" width="380" height="10" rx="5" fill="#ffffff" fill-opacity="0.05"/>'
                    f'<rect x="680" y="{y - 11}" width="{bw:.1f}" height="10" rx="5" fill="{c}">'
                    f'<animate attributeName="width" values="0;{bw:.1f}" dur="1.4s" begin="{i * 0.15:.2f}s" fill="freeze"/></rect>'
                    f'<text x="1140" y="{y}" text-anchor="end" class="m6" font-size="14" fill="{c}">{p:.1f}%</text>')
    scope = "all repositories, including private" if any(r["private"] for r in repos) else "all public repositories"
    fdefs, frame = card_frame(1200, 340, TEAL, "l")
    body = f'''{frame}
<text x="60" y="62" class="m6" font-size="13" letter-spacing="4" fill="{TEAL}">LANGUAGE BREAKDOWN</text>
<text x="60" y="88" class="d5" font-size="15" fill="#64748b">Across {scope}  ·  updated {TODAY:%d %b %Y}</text>
<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#ffffff" stroke-opacity="0.05" stroke-width="26"/>
{"".join(segs)}
<text x="{cx}" y="{cy + 6}" text-anchor="middle" class="d7" font-size="40" fill="#f8fafc">{len(totals)}</text>
<text x="{cx}" y="{cy + 30}" text-anchor="middle" class="m4" font-size="12" letter-spacing="2" fill="#64748b">LANGUAGES</text>
{"".join(rows)}'''
    write("languages.svg", svg(1200, 340, body, fdefs))


# ---------------------------------------------------------------- contribution activity
def activity(data):
    current, longest, active = streaks(data["calendar"])
    tiles = [(f"{data['total']:,}", "CONTRIBUTIONS · 12 MO", TEAL), (f"{current}", "CURRENT STREAK · DAYS", PINK),
             (f"{longest}", "LONGEST STREAK · DAYS", INDIGO), (f"{active}", "ACTIVE DAYS · 12 MO", AMBER)]
    tile_svg = "".join(
        f'<rect x="{60 + i * 275}" y="108" width="255" height="84" rx="14" fill="{c}" fill-opacity="0.06" stroke="{c}" stroke-opacity="0.3"/>'
        f'<text x="{82 + i * 275}" y="154" class="d7" font-size="36" fill="#f8fafc">{v}</text>'
        f'<text x="{82 + i * 275}" y="178" class="m6" font-size="11" letter-spacing="1.5" fill="{c}">{label}</text>'
        for i, (v, label, c) in enumerate(tiles))

    days = [c for d, c in sorted(data["calendar"]) if dt.date.fromisoformat(d) <= TODAY][-60:]
    peak = max(days + [1])
    step = 1080 / max(len(days), 1)
    base = 318
    bars = []
    for i, c in enumerate(days):
        x = 60 + i * step + 2
        hgt = 3 if c == 0 else 8 + 92 * c / peak
        fill = "url(#barg)" if c else "#1e293b"
        bars.append(f'<rect x="{x:.1f}" y="{base - hgt:.1f}" width="{step - 5:.1f}" height="{hgt:.1f}" rx="3" fill="{fill}">'
                    f'<animate attributeName="height" values="0;{hgt:.1f}" dur="0.9s" begin="{i * 0.02:.2f}s" fill="freeze"/>'
                    f'<animate attributeName="y" values="{base};{base - hgt:.1f}" dur="0.9s" begin="{i * 0.02:.2f}s" fill="freeze"/></rect>')
    start = TODAY - dt.timedelta(days=len(days) - 1)
    fdefs, frame = card_frame(1200, 360, PINK, "v")
    fdefs += f'<linearGradient id="barg" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="{INDIGO}"/><stop offset="1" stop-color="{TEAL}"/></linearGradient>'
    body = f'''{frame}
<text x="60" y="62" class="m6" font-size="13" letter-spacing="4" fill="{PINK}">CONTRIBUTION ACTIVITY</text>
<text x="60" y="88" class="d5" font-size="15" fill="#64748b">Live from GitHub  ·  updated {TODAY:%d %b %Y}</text>
{tile_svg}
<path d="M60 {base + 0.5} H1140" stroke="#ffffff" stroke-opacity="0.06"/>
{"".join(bars)}
<text x="60" y="342" class="m4" font-size="11" fill="#475569">{start:%d %b}</text>
<text x="600" y="342" text-anchor="middle" class="m4" font-size="11" fill="#475569">last 60 days</text>
<text x="1140" y="342" text-anchor="end" class="m4" font-size="11" fill="#475569">today</text>'''
    write("activity.svg", svg(1200, 360, body, fdefs))


# ---------------------------------------------------------------- latest repositories
def recent(repos):
    public = [r for r in repos if not r["private"]][:3]
    accents = [TEAL, INDIGO, PINK]
    cards = []
    for i, r in enumerate(public):
        x, c = 60 + i * 365, accents[i]
        name = r["name"] if len(r["name"]) <= 24 else r["name"][:22] + "..."
        lang = r["language"] or "Code"
        lc = LANG_COLORS.get(lang, "#94a3b8")
        cards.append(f'<rect x="{x}" y="100" width="350" height="140" rx="14" fill="#0f172a" fill-opacity="0.7" stroke="{c}" stroke-opacity="0.35"/>'
                     f'<rect x="{x}" y="100" width="4" height="140" rx="2" fill="{c}"/>'
                     f'<text x="{x + 24}" y="142" class="d7" font-size="21" fill="#f8fafc">{esc(name)}</text>'
                     f'<text x="{x + 326}" y="142" text-anchor="end" class="m4" font-size="16" fill="{c}">↗</text>'
                     f'<circle cx="{x + 30}" cy="176" r="5" fill="{lc}"/>'
                     f'<text x="{x + 44}" y="181" class="m6" font-size="13" fill="#cbd5e1">{esc(lang)}</text>'
                     f'<text x="{x + 24}" y="214" class="m4" font-size="12" fill="#64748b">{r["commits"]} commits  ·  ★ {r["stars"]}  ·  {ago(r["pushed_at"])}</text>')
    fdefs, frame = card_frame(1200, 280, INDIGO, "r")
    body = f'''{frame}
<text x="60" y="62" class="m6" font-size="13" letter-spacing="4" fill="{INDIGO}">LATEST REPOSITORIES</text>
<text x="60" y="84" class="d5" font-size="15" fill="#64748b">Most recently updated  ·  refreshed daily</text>
{"".join(cards)}'''
    write("recent.svg", svg(1200, 280, body, fdefs))


if __name__ == "__main__":
    data = fetch()
    data["repos"] = [r for r in data["repos"] if r["name"].lower() != USER.lower()]  # skip this profile repo
    by_name = {r["name"]: r for r in data["repos"]}
    header()
    card_curelex()
    card_smarted(by_name.get(CARD_REPOS["smarted"]))
    card_shifra(by_name.get(CARD_REPOS["shifra"]))
    languages(data["repos"])
    activity(data)
    recent(data["repos"])
    print(f"Generated SVGs for {USER}: {len(data['repos'])} repos, {data['total']} contributions")
