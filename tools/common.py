"""Shared helpers: polite HTTP with caching, paths, dates."""
import hashlib, json, os, re, time, unicodedata, urllib.parse, urllib.request
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "_cache", "http")
SONGS = os.path.join(ROOT, "songs")
UA = "Earworm-research/0.1 (private research corpus; contact via github.com/shafeeqshajahanliver)"
TODAY = date.today().isoformat()
_last = {}
# seconds between requests, per host
DELAY = {"en.wikipedia.org": 3, "musicbrainz.org": 1.1, "query.wikidata.org": 2,
         "lrclib.net": 1, "api.deezer.com": 0.5, "itunes.apple.com": 3,
         "coverartarchive.org": 1, "api.secondhandsongs.com": 6}


def fetch(url, binary=False, cache=True, headers=None):
    os.makedirs(CACHE, exist_ok=True)
    key = os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest())
    if cache and os.path.exists(key):
        with open(key, "rb") as f:
            data = f.read()
        return data if binary else data.decode("utf-8", "replace")
    host = urllib.parse.urlparse(url).netloc
    wait = DELAY.get(host, 1) - (time.time() - _last.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                _last[host] = time.time()
                return None
            # iTunes signals throttling with 403
            # Cloudflare 52x (seen on lrclib.net) are transient too
            throttled = e.code == 429 or e.code >= 500 or (e.code == 403 and host == "itunes.apple.com")
            if throttled and attempt < 3:
                time.sleep((30 if e.code == 403 else 5) * (attempt + 1))
                continue
            raise
    _last[host] = time.time()
    if cache:
        with open(key, "wb") as f:
            f.write(data)
    return data if binary else data.decode("utf-8", "replace")


def fetch_json(url, **kw):
    t = fetch(url, **kw)
    return json.loads(t) if t else None


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s.lower().replace("'", ""))
    return s.strip("-")


def norm(s):
    """Loose title/artist key for matching."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(.*?\)|\[.*?\]", " ", s)
    s = s.replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "", s)


def song_dir(sid, *parts):
    p = os.path.join(SONGS, sid, *parts)
    os.makedirs(os.path.dirname(p) if parts else p, exist_ok=True)
    return p


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def read_json(path):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def load_songs():
    import csv
    with open(os.path.join(ROOT, "songs.csv")) as f:
        return list(csv.DictReader(f))


def wiki_raw(title):
    return fetch("https://en.wikipedia.org/w/index.php?title=%s&action=raw"
                 % urllib.parse.quote(title.replace(" ", "_")))


def infobox_lengths(sid):
    """Track lengths (seconds) listed in the Wikipedia infobox, e.g. single and album versions."""
    w = read_json(os.path.join(SONGS, sid, "wikipedia.json")) or {}
    raw = (w.get("infobox") or {}).get("length", "") or ""
    out = []
    for m in re.finditer(r"\{\{\s*duration\s*\|\s*(?:h=(\d+)\s*\|\s*)?m=(\d+)\s*\|\s*s=(\d+)", raw, re.I):
        out.append(int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60 + int(m.group(3)))
    for m in re.finditer(r"(?<![\d=])(\d{1,2}):(\d{2})(?!\d)", raw):
        out.append(int(m.group(1)) * 60 + int(m.group(2)))
    return sorted(set(out))


def ref_lengths(sid):
    """Reference lengths for matching, best first: [(seconds, label)].
    MusicBrainz charting recording, then the Deezer track matched by ISRC (from audio.json),
    then Wikipedia infobox lengths (last, because infoboxes can list other versions,
    or another artist's recording when the article is about the song)."""
    out = []
    f = read_json(os.path.join(SONGS, sid, "facts.json")) or {}
    mb = f.get("musicbrainz") or {}
    if mb.get("length_ms"):
        out.append((mb["length_ms"] / 1000, "musicbrainz recording length"))
    a = read_json(os.path.join(SONGS, sid, "audio.json")) or {}
    p = a.get("preview") or {}
    if p.get("matched_by") == "isrc" and p.get("track_duration_s"):
        out.append((float(p["track_duration_s"]), "deezer track matched by ISRC"))
    elif p.get("track_duration_s"):
        out.append((float(p["track_duration_s"]), "%s preview track matched by search" % p.get("service")))
    for s in infobox_lengths(sid):
        out.append((float(s), "wikipedia infobox length"))
    return out
