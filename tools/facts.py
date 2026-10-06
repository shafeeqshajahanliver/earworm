"""Facts layer: Wikipedia article (sections + infobox), Wikidata claims, MusicBrainz
recording / work / release-group. Writes songs/<id>/wikipedia.json and facts.json,
and fills wikidata / musicbrainz in songs.csv."""
import csv, json, os, re, sys, unicodedata, urllib.parse
from common import *

WD_PROPS = {  # property: label
    "P175": "performer", "P86": "composer", "P676": "lyricist", "P162": "producer",
    "P264": "record_label", "P577": "publication_date", "P136": "genre", "P361": "part_of",
    "P826": "tonality", "P1725": "beats_per_minute", "P2047": "duration", "P407": "language",
    "P495": "country_of_origin", "P166": "award_received", "P1411": "nominated_for",
    "P155": "follows", "P156": "followed_by", "P144": "based_on", "P5059": "modified_version_of",
    "P2207": "spotify_track_id", "P4404": "musicbrainz_recording_id", "P435": "musicbrainz_work_id",
    "P436": "musicbrainz_release_group_id", "P1243": "isrc", "P6218": "genius_song_id",
    "P2909": "secondhandsongs_song_id", "P1651": "youtube_video_id", "P483": "recorded_at",
    "P7937": "form_of_creative_work", "P1552": "has_quality", "P736": "cover_art_by",
}
LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def clean(s):
    s = re.sub(r"<ref[^>/]*/>|<ref.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = LINK.sub(lambda m: m.group(2) or m.group(1), s)
    s = re.sub(r"'''?", "", s)
    return s


def resolve(title):
    for _ in range(3):
        t = wiki_raw(title)
        m = re.match(r"\s*#REDIRECT\s*\[\[([^\]#|]+)", t or "", re.I)
        if not m:
            return title, t
        title = m.group(1).strip()
    return title, t


def split_sections(text):
    out, cur, buf = [], "Lead", []
    for line in text.split("\n"):
        m = re.match(r"^(={2,4})\s*(.+?)\s*\1\s*$", line)
        if m:
            out.append({"heading": cur, "level": len(m.group(1)) if cur != "Lead" else 1,
                        "wikitext": "\n".join(buf).strip()})
            cur, buf = m.group(2), []
        else:
            buf.append(line)
    out.append({"heading": cur, "wikitext": "\n".join(buf).strip()})
    for s in out:
        s["text"] = clean(s["wikitext"])
    return out


def infoboxes(text):
    """All song/single infoboxes in the article (multi-version articles have several)."""
    out = []
    for m in re.finditer(r"\{\{\s*Infobox (song|single)(.*?)\n\}\}", text, re.S | re.I):
        fields = {}
        for line in m.group(2).split("\n|"):
            if "=" in line:
                k, v = line.split("=", 1)
                fields[k.strip(" |\n")] = clean(v).strip()
        out.append(fields)
    return out


def artist_key(artist):
    return norm(re.split(r" featuring | feat\. | and Friends| \(|, | & | and ", artist)[0])


def pick_infobox(boxes, artist):
    a = artist_key(artist)
    for b in boxes:
        if a and a in norm(b.get("artist", "")):
            return b
    return boxes[0] if boxes else None


def version_article(text, artist):
    """In a multi-version article with no infobox for our artist, follow the {{Main|...}}
    link under the artist's version section (e.g. Whitney Houston's I Will Always Love You)."""
    a = artist_key(artist)
    if any(a in norm(b.get("artist", "")) for b in infoboxes(text)):
        return None
    for m in re.finditer(r"\n(=+)\s*([^=\n]+?)\s*\1\s*\n\{\{\s*Main\s*\|\s*([^}|]+)", text):
        if a in norm(m.group(2)):
            return m.group(3).strip()
    return None


def qid_for(article):
    q = ('SELECT ?item WHERE { ?a schema:about ?item; schema:isPartOf <https://en.wikipedia.org/>; '
         'schema:name "%s"@en }' % article.replace('"', '\\"'))
    r = fetch_json("https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(q))
    b = r["results"]["bindings"]
    return b[0]["item"]["value"].rsplit("/", 1)[-1] if b else None


def labels(qids):
    qids = sorted(set(qids))
    out = {}
    for i in range(0, len(qids), 150):
        vals = " ".join("wd:" + q for q in qids[i:i + 150])
        q = ('SELECT ?i ?l WHERE { VALUES ?i {%s} ?i rdfs:label ?l FILTER(lang(?l)="en") }' % vals)
        r = fetch_json("https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(q))
        for b in r["results"]["bindings"]:
            out[b["i"]["value"].rsplit("/", 1)[-1]] = b["l"]["value"]
    return out


def wikidata_claims(qid):
    ent = fetch_json("https://www.wikidata.org/wiki/Special:EntityData/%s.json" % qid)
    ent = ent["entities"][qid]
    claims = {}
    for p, lab in WD_PROPS.items():
        vals = []
        for c in ent["claims"].get(p, []):
            dv = c["mainsnak"].get("datavalue")
            if not dv:
                continue
            v = dv["value"]
            if dv["type"] == "wikibase-entityid":
                vals.append({"qid": v["id"]})
            elif dv["type"] == "time":
                vals.append({"time": v["time"][1:11]})
            elif dv["type"] == "quantity":
                vals.append({"amount": v["amount"].lstrip("+"), "unit": v["unit"].rsplit("/", 1)[-1]})
            else:
                vals.append(v)
        if vals:
            claims[lab] = vals
    return ent.get("labels", {}).get("en", {}).get("value"), claims


MB = "https://musicbrainz.org/ws/2/"


def mb(path, **params):
    params["fmt"] = "json"
    return fetch_json(MB + path + "?" + urllib.parse.urlencode(params))


VARIANT = ("live", "remix", "demo", "instrumental", "acoustic", "edit", "mix", "version",
           "karaoke", "a cappella", "reprise", "mono", "stereo", "remaster", "single")


def full_key(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", s.replace("&", "and"))


def title_ok(cand, target):
    if full_key(cand) == full_key(target):
        return True
    extra = " ".join(re.findall(r"[(\[](.*?)[)\]]", cand)).lower()
    return norm(cand) == norm(target) and not any(w in extra for w in VARIANT)


def main_artist(artist):
    return re.split(r" featuring | feat\. | and Friends| \(", artist)[0]


def mb_find_recording(title, artist, year):
    """Find the charting recording: the earliest single release group with this title by the
    main artist, then the matching track on its earliest release. Falls back to a recording
    search (exact title, no variant markers, earliest first release)."""
    a = main_artist(artist)
    r = mb("release-group", query='releasegroup:"%s" AND artist:"%s" AND primarytype:single'
           % (title.replace('"', ''), a), limit=25)
    groups = [g for g in r.get("release-groups", [])
              if any(title_ok(part, title) for part in g["title"].split(" / "))
              and (g.get("first-release-date") or "9999")[:4] <= str(year)]
    groups.sort(key=lambda g: g.get("first-release-date") or "9999")
    for g in groups[:3]:
        rels = mb("release", **{"release-group": g["id"], "inc": "recordings", "limit": 25})
        for rel in sorted(rels.get("releases", []), key=lambda x: x.get("date") or "9999"):
            for m in rel.get("media", []):
                for t in m.get("tracks", []):
                    if title_ok(t["recording"]["title"], title) or title_ok(t["title"], title):
                        return t["recording"]["id"], "single release group %s (%s)" % (g["id"], g.get("first-release-date"))
    r = mb("recording", query='recording:"%s" AND artist:"%s"' % (title.replace('"', ''), a), limit=50)
    cands = []
    for rec in r.get("recordings", []):
        dis = (rec.get("disambiguation") or "").lower()
        if not title_ok(rec["title"], title) or any(w in dis for w in VARIANT):
            continue
        cands.append((rec.get("first-release-date") or "9999", -rec.get("score", 0), rec["id"]))
    cands.sort()
    return (cands[0][2], "recording search (exact title, earliest release)") if cands else (None, None)


def mb_details(rid):
    rec = mb("recording/" + rid, inc="artist-credits+isrcs+releases+release-groups+work-rels+"
             "artist-rels+url-rels+tags+genres")
    out = {"recording_id": rid, "title": rec["title"], "length_ms": rec.get("length"),
           "first_release_date": rec.get("first-release-date"),
           "artist_credit": "".join(a["name"] + a.get("joinphrase", "") for a in rec.get("artist-credit", [])),
           "artists": [{"name": a["artist"]["name"], "mbid": a["artist"]["id"]} for a in rec.get("artist-credit", [])],
           "isrcs": rec.get("isrcs", []),
           "recording_credits": [{"role": r["type"], "attributes": r.get("attributes", []),
                                  "name": r["artist"]["name"], "mbid": r["artist"]["id"]}
                                 for r in rec.get("relations", []) if r.get("target-type") == "artist"],
           "urls": [{"type": r["type"], "url": r["url"]["resource"]}
                    for r in rec.get("relations", []) if r.get("target-type") == "url"],
           "genres": [g["name"] for g in rec.get("genres", [])],
           "tags": [t["name"] for t in sorted(rec.get("tags", []), key=lambda t: -t["count"])[:10]]}
    rels = sorted(rec.get("releases", []), key=lambda r: r.get("date") or "9999")
    out["releases"] = [{"id": r["id"], "title": r["title"], "date": r.get("date"), "country": r.get("country"),
                        "status": r.get("status"),
                        "release_group": r.get("release-group", {}).get("id"),
                        "primary_type": r.get("release-group", {}).get("primary-type"),
                        "secondary_types": r.get("release-group", {}).get("secondary-types", [])}
                       for r in rels]
    works = [r["work"] for r in rec.get("relations", []) if r.get("target-type") == "work"]
    if works:
        w = mb("work/" + works[0]["id"], inc="artist-rels+url-rels")
        out["work"] = {"id": w["id"], "title": w["title"], "iswcs": w.get("iswcs", []),
                       "credits": [{"role": r["type"], "name": r["artist"]["name"], "mbid": r["artist"]["id"]}
                                   for r in w.get("relations", []) if r.get("target-type") == "artist"],
                       "urls": [r["url"]["resource"] for r in w.get("relations", []) if r.get("target-type") == "url"]}
    # country of the main artist
    if out["artists"]:
        a = mb("artist/" + out["artists"][0]["mbid"])
        out["main_artist"] = {"name": a["name"], "type": a.get("type"), "country": a.get("country"),
                              "area": (a.get("area") or {}).get("name"),
                              "begin_area": (a.get("begin-area") or {}).get("name")}
    return out


def main(only=None):
    songs = load_songs()
    sel = {e["year"]: e for e in read_json(os.path.join(ROOT, "reference", "selection.json"))}
    for s in songs:
        if only and s["id"] not in only:
            continue
        sid, e = s["id"], sel[int(s["chart_year"])]
        article, text = resolve(e["article"])
        alt = version_article(text, s["artist"])
        if alt:
            article, text = resolve(alt)
        write_json(song_dir(sid, "wikipedia.json"), {
            "title": article, "url": "https://en.wikipedia.org/wiki/" + article.replace(" ", "_"),
            "retrieved": TODAY, "source": "Wikipedia (index.php?action=raw)",
            "infobox": pick_infobox(infoboxes(text), s["artist"]),
            "infoboxes": infoboxes(text), "sections": split_sections(text)})
        facts = {"id": sid, "retrieved": TODAY, "wikipedia_article": article}
        qid = s["wikidata"] or qid_for(article)
        if qid:
            label, claims = wikidata_claims(qid)
            names = labels([v["qid"] for vs in claims.values() for v in vs if isinstance(v, dict) and "qid" in v])
            for vs in claims.values():
                for v in vs:
                    if isinstance(v, dict) and "qid" in v:
                        v["label"] = names.get(v["qid"])
            facts["wikidata"] = {"qid": qid, "label": label, "claims": claims,
                                 "source": "Wikidata (CC0)", "confidence": "sourced"}
            s["wikidata"] = qid
        rid = s["musicbrainz"]
        if not rid and qid:
            ids = facts["wikidata"]["claims"].get("musicbrainz_recording_id", [])
            # Wikidata may list several recordings; prefer the earliest-released one below
            if ids:
                dated = []
                for i in ids:
                    r = mb("recording/" + i)
                    if r:
                        dated.append((r.get("first-release-date") or "9999", i))
                rid = sorted(dated)[0][1] if dated else None
                facts["musicbrainz_match"] = "wikidata"
        if not rid:
            rid, how = mb_find_recording(s["title"], s["artist"], int(s["chart_year"]))
            facts["musicbrainz_match"] = how
        if rid:
            facts["musicbrainz"] = mb_details(rid)
            facts["musicbrainz"].update({"source": "MusicBrainz (CC0)", "confidence": "sourced"})
            s["musicbrainz"] = rid
            ma = facts["musicbrainz"].get("main_artist", {})
            if ma.get("country") and not s["country"]:
                s["country"] = ma["country"]
        write_json(song_dir(sid, "facts.json"), facts)
        print(sid, qid, rid, s["country"], flush=True)
    with open(os.path.join(ROOT, "songs.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(songs[0]))
        w.writeheader(); w.writerows(songs)


if __name__ == "__main__":
    main(set(sys.argv[1:]) or None)
