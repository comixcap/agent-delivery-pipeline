#!/usr/bin/env python3
"""
printcheck.py — measure a project's fingerprint against EVERY previously built app.

Why. Store review compares apps from one account (and from terminated accounts) by
"similar binary, metadata and/or concept". Type names end up in the binary as mangled
symbols, file names end up in the dSYM, keywords and privacy text are compared verbatim.
When agents build from one reference project, they reproduce it faithfully — and that
reproduction is exactly what gets flagged. This script makes similarity a NUMBER instead
of a paragraph in a registry.

Usage:
    python3 printcheck.py check    <ProjectDir>   # before handoff; exit 1 on FAIL
    python3 printcheck.py register <ProjectDir>   # after a build is accepted
    python3 printcheck.py index    <FolderWithProjects>   # once: seed history
    python3 printcheck.py list

Fingerprints are stored one JSON per app in $PIPELINE_ROOT/prints/, so parallel builds
never contend for one file.

Thresholds:
    FAIL  — type name from the infrastructure blacklist; ≥ 6 shared type names with one
            app; > 2 shared keywords; a verbatim privacy sentence (≥ 8 words); the same
            first sentence of the description.
    warn  — 3–5 shared type names; ≥ 2 shared file names; privacy text similar
            (≥ 40 % shared 5-word shingles); shared bundle ID prefix.
"""
import sys, os, re, json, glob

ROOT = os.environ.get("PIPELINE_ROOT", os.path.expanduser("~/pipeline"))
PRINTS = os.path.join(ROOT, "prints")

# Names that were shared by 12–14 consecutive apps before the rename policy — i.e. the
# reference project's vocabulary. Any of them in a new project is literally "similar binary".
INFRA_BLACKLIST = {
    "Glyph", "GlyphPen", "GlyphShape", "GlyphKind", "GlyphStyle", "GlyphLayer",
    "GlyphMetrics", "GlyphBadge", "ScreenScrollView", "DefaultsVault", "Haptics",
    "Typography", "TypeRole", "SignalKit", "Ink", "Workspace", "FramePanel", "RingGauge",
    "ActionKey", "CoverMotif", "CoverArt", "AppBackground", "ColorPalette", "DataManager",
    "CustomTabBar", "SectionCard", "PrimaryButton", "ContentView", "HomeView", "LoaderView",
    "OnboardingView", "SettingsView", "LoadingView", "RootView",
}

# Names any two Swift projects share; they say nothing about the fingerprint.
GENERIC = {
    "CodingKeys", "Tone", "Point", "Link", "Kind", "Style", "Layer", "Metrics", "Section",
    "Row", "Tab", "Card", "Badge", "Item", "Entry", "State", "Mode", "Phase", "Step", "Stage",
    "Level", "Constants", "Layout", "Theme", "Tag", "Note", "Filter", "Sort", "Field", "Unit",
    "Size", "Axis", "Direction", "Result", "Error", "Config", "Settings", "Snapshot",
}

# Files that must keep their name (preflight looks at them) or that Xcode dictates.
FILE_ALLOW = {"Glyphs.swift", "CoverArt.swift"}

TYPE_RE = re.compile(
    r"^\s*(?:public |private |fileprivate |internal |open )?(?:final )?(?:indirect )?"
    r"(?:struct|class|enum|actor|protocol)\s+([A-Z][A-Za-z0-9_]*)", re.M)


# ---------------------------------------------------------------- extraction
def project_root(path):
    path = os.path.abspath(path)
    for cand in (path, os.path.dirname(path)):
        if glob.glob(os.path.join(cand, "*.xcodeproj")):
            return cand
    return path


def app_name(root):
    xs = glob.glob(os.path.join(root, "*.xcodeproj"))
    return os.path.splitext(os.path.basename(xs[0]))[0] if xs else os.path.basename(root)


def source_dir(root, name):
    d = os.path.join(root, name)
    return d if os.path.isdir(d) else root


def swift_files(src):
    out = []
    for dp, dn, fn in os.walk(src):
        dn[:] = [d for d in dn if not d.endswith(".xcodeproj") and d not in ("build", "DerivedData")]
        out += [os.path.join(dp, f) for f in fn if f.endswith(".swift")]
    return out


def read(p):
    try:
        with open(p, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except OSError:
        return ""


def bundle_id(root):
    for p in glob.glob(os.path.join(root, "*.xcodeproj", "project.pbxproj")):
        m = re.search(r"PRODUCT_BUNDLE_IDENTIFIER = \"?([^\";]+)", read(p))
        if m:
            return m.group(1).strip()
    return ""


def sections(md):
    """[(heading, body)] split on markdown headings."""
    out, cur, buf = [], None, []
    for line in md.splitlines():
        if re.match(r"^#{1,4}\s+", line):
            if cur is not None:
                out.append((cur, "\n".join(buf)))
            cur, buf = re.sub(r"^#+\s+", "", line).strip(), []
        else:
            buf.append(line)
    if cur is not None:
        out.append((cur, "\n".join(buf)))
    return out


def clean(line):
    return re.sub(r"[`*>_]", "", line).strip()


def find_section(secs, pattern):
    rx = re.compile(pattern, re.I)
    for h, b in secs:
        if rx.search(h):
            return b
    return ""


def parse_metadata(root):
    md = read(os.path.join(root, "APP_STORE_METADATA.md"))
    meta = {"keywords": [], "privacy": "", "first_sentence": "", "review_note_chars": 0,
            "has_support_url": False}
    if not md:
        return meta, False
    secs = sections(md)

    body = find_section(secs, r"keyword")
    for line in body.splitlines():
        c = clean(line)
        if c and "," in c and not c.startswith("#") and len(c) <= 200:
            meta["keywords"] = [k.strip().lower() for k in c.split(",") if k.strip()]
            break

    body = find_section(secs, r"privacy policy|privacy text|privacy")
    paras = [p for p in re.split(r"\n\s*\n", body) if clean(p)]
    if paras:
        para = max(paras, key=lambda p: len(clean(p)))
        meta["privacy"] = " ".join(clean(l) for l in para.splitlines() if clean(l))

    body = find_section(secs, r"first sentence|^description|description \(full\)")
    # First sentence = first ENGLISH paragraph; helper captions ("First sentence:") are skipped,
    # otherwise ten apps "match" on a template line.
    for para in re.split(r"\n\s*\n", body):
        c = " ".join(clean(l) for l in para.splitlines() if clean(l))
        if not c or c.startswith("#") or len(c.split()) < 5:
            continue
        if re.search(r"[А-Яа-яЁё]", c) or c.rstrip().endswith(":"):
            continue
        meta["first_sentence"] = re.split(r"(?<=[.!?])\s", c)[0].lower()
        break

    body = find_section(secs, r"review(er)? note|notes for review|app review")
    meta["review_note_chars"] = len(clean(body))
    meta["has_support_url"] = bool(re.search(r"support url", md, re.I))
    return meta, True


def fingerprint(path):
    root = project_root(path)
    name = app_name(root)
    src = source_dir(root, name)
    types, files = set(), set()
    for f in swift_files(src):
        files.add(os.path.basename(f))
        for m in TYPE_RE.finditer(read(f)):
            t = m.group(1)
            if t in (name, name + "App"):
                continue
            types.add(t)
    meta, has_meta = parse_metadata(root)
    return {
        "app": name, "root": root, "bundle": bundle_id(root),
        "types": sorted(types), "files": sorted(files - {name + "App.swift"}),
        "has_metadata": has_meta, **meta,
    }


# ---------------------------------------------------------------- comparison
def sentences(text):
    out = set()
    for s in re.split(r"(?<=[.!?])\s+", text.lower()):
        w = re.findall(r"[a-z0-9']+", s)
        if len(w) >= 8:
            out.add(" ".join(w))
    return out


def shingles(text, n=5):
    w = re.findall(r"[a-z0-9']+", text.lower())
    return {" ".join(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}


def load_prints(exclude=None):
    out = []
    for p in sorted(glob.glob(os.path.join(PRINTS, "*.json"))):
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            if exclude and d.get("app", "").lower() == exclude.lower():
                continue
            out.append(d)
        except Exception:
            pass
    return out


def compare(me, others):
    fails, warns, oks = [], [], []

    black = sorted(set(me["types"]) & INFRA_BLACKLIST)
    if black:
        fails.append("type names from the reference/infrastructure vocabulary: " + ", ".join(black))
    else:
        oks.append("no type name from the infrastructure blacklist")

    my_types = set(me["types"]) - GENERIC
    worst = []
    for o in others:
        shared = sorted(my_types & (set(o["types"]) - GENERIC))
        if len(shared) >= 3:
            worst.append((len(shared), o["app"], shared))
    worst.sort(reverse=True)
    for n, app, shared in worst[:5]:
        line = f"{n} shared type names with {app}: " + ", ".join(shared[:12]) + (" …" if n > 12 else "")
        (fails if n >= 6 else warns).append(line)
    if not worst:
        oks.append(f"type names ({len(my_types)}) do not overlap with {len(others)} indexed apps (threshold 3)")

    fshared = {}
    for o in others:
        s = (set(me["files"]) & set(o["files"])) - FILE_ALLOW
        for f in s:
            fshared.setdefault(f, []).append(o["app"])
    if len(fshared) >= 2:
        warns.append("shared file names: " + ", ".join(f"{f} ({', '.join(a[:3])})" for f, a in sorted(fshared.items())[:8]))
    else:
        oks.append("file names are unique (except Glyphs.swift and CoverArt.swift)")

    if me["has_metadata"]:
        if me["keywords"]:
            for o in others:
                ov = sorted(set(me["keywords"]) & set(o.get("keywords", [])))
                if len(ov) > 2:
                    fails.append(f"keywords: {len(ov)} shared with {o['app']} ({', '.join(ov)}) — at most 2 allowed")
            if not any(len(set(me["keywords"]) & set(o.get("keywords", []))) > 2 for o in others):
                oks.append("keywords: overlap with every app ≤ 2")
        else:
            warns.append("could not read keywords from APP_STORE_METADATA.md (needs a Keywords heading and a comma-separated line)")

        if me["privacy"]:
            mine_s, mine_sh = sentences(me["privacy"]), shingles(me["privacy"])
            dup = sim = None
            for o in others:
                op = o.get("privacy", "")
                if not op:
                    continue
                if mine_s & sentences(op):
                    dup = o["app"]; break
                osh = shingles(op)
                if mine_sh and osh:
                    j = len(mine_sh & osh) / len(mine_sh | osh)
                    if j >= 0.4:
                        sim = (o["app"], round(j, 2))
            if dup:
                fails.append(f"privacy text contains a verbatim sentence from {dup} — rephrase")
            elif sim:
                warns.append(f"privacy text resembles {sim[0]} (Jaccard {sim[1]}) — rephrase further")
            else:
                oks.append("privacy text is original")
        else:
            warns.append("could not read privacy text from APP_STORE_METADATA.md")

        if me["first_sentence"]:
            same = [o["app"] for o in others if o.get("first_sentence") and o["first_sentence"] == me["first_sentence"]]
            if same:
                fails.append("first sentence of the description repeats " + ", ".join(same))
            else:
                oks.append("first sentence of the description is original")

        if me["review_note_chars"] < 500:
            fails.append(f"reviewer note missing or shorter than 500 chars ({me['review_note_chars']}) — features must be described with specificity")
        else:
            oks.append(f"reviewer note: {me['review_note_chars']} chars")
        if not me["has_support_url"]:
            warns.append("no Support URL line in metadata")
    else:
        warns.append("no APP_STORE_METADATA.md — metadata not compared")

    b = me["bundle"]
    if b:
        segs = b.lower().split(".")
        pref = ".".join(segs[:2])
        same = [o["app"] for o in others if o.get("bundle", "").lower().startswith(pref + ".") and pref not in ("com.app",)]
        if same and pref.split(".")[1] not in (me["app"].lower().replace("_", ""),):
            warns.append(f"bundle ID prefix «{pref}» shared with {', '.join(same[:4])}")
        else:
            oks.append(f"bundle ID {b}")
    else:
        warns.append("bundle ID not found in project.pbxproj")
    return fails, warns, oks


# ---------------------------------------------------------------- commands
def cmd_check(path):
    me = fingerprint(path)
    others = load_prints(exclude=me["app"])
    if not others:
        print("  warn  fingerprint index is empty — seed it: printcheck.py index <folder with projects>")
    fails, warns, oks = compare(me, others)
    for o in oks:    print("  ok    " + o)
    for w in warns:  print("  warn  " + w)
    for f in fails:  print("  FAIL  " + f)
    print(f"  printcheck: {len(fails)} FAIL, {len(warns)} warn (index: {len(others)} apps)")
    return 1 if fails else 0


def cmd_register(path):
    os.makedirs(PRINTS, exist_ok=True)
    me = fingerprint(path)
    out = os.path.join(PRINTS, me["app"] + ".json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(me, f, ensure_ascii=False, indent=1)
    print(f"  ok    fingerprint {me['app']} written: {len(me['types'])} types, {len(me['files'])} files, "
          f"{len(me['keywords'])} keywords → {out}")
    return 0


def cmd_index(folder):
    n = 0
    for d in sorted(glob.glob(os.path.join(folder, "*"))):
        if os.path.isdir(d) and glob.glob(os.path.join(d, "*.xcodeproj")):
            cmd_register(d); n += 1
    print(f"  index: {n} projects")
    return 0


def cmd_list():
    ps = load_prints()
    for p in ps:
        print(f"  {p['app']:<24} {len(p['types']):>4} types  {p.get('bundle','')}")
    print(f"  total: {len(ps)}")
    return 0


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__); return 2
    c = a[0]
    if c == "check":    return cmd_check(a[1] if len(a) > 1 else ".")
    if c == "register": return cmd_register(a[1] if len(a) > 1 else ".")
    if c == "index":    return cmd_index(a[1]) if len(a) > 1 else (print("  ! index <folder>") or 2)
    if c == "list":     return cmd_list()
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main())
