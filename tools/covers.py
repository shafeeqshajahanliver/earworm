"""Cover art: the original single sleeve and parent album (Cover Art Archive, via the
MusicBrainz release groups in facts.json) and the current digital artwork (iTunes).
Measures brightness, saturation and a 5-colour palette. Writes songs/<id>/cover/."""
import io, json, os, re, time, urllib.parse
from PIL import Image
from common import *

SIZE = 600  # stored image size (longest side)


def mb(path, **params):
    params["fmt"] = "json"
    return fetch_json("https://musicbrainz.org/ws/2/" + path + "?" + urllib.parse.urlencode(params))


def infobox_album(sid):
    w = read_json(os.path.join(SONGS, sid, "wikipedia.json")) or {}
    a = ((w.get("infobox") or {}).get("album") or "").strip()
    a = re.split(r"\{\{.*?\}\}|\n", a)[0].strip(" ,*")
    return a or None


def pick_groups(sid, facts, artist):
    """Earliest official single, and the album named in the song's Wikipedia infobox
    (falling back to the earliest studio album the recording appears on)."""
    rels = [r for r in facts.get("musicbrainz", {}).get("releases", []) if r["status"] in (None, "Official")]
    single = next((r for r in rels if r["primary_type"] == "Single"), None)
    name = infobox_album(sid)
    album, how = None, None
    if name:
        k = norm(name)
        albums = [r for r in rels if r["primary_type"] in ("Album", "EP")]
        album = next((r for r in albums if norm(r["title"]) == k), None) or \
            next((r for r in albums if norm(r["title"]).startswith(k[:25]) or k.startswith(norm(r["title"]))), None)
        if not album:  # not linked to this recording in MusicBrainz: search the release group
            a = re.split(r" featuring | feat\. ", artist)[0]
            qname = re.sub(r"[(\[].*?[)\]]|[\":!]", " ", name).strip()
            for q in ('releasegroup:(%s) AND artist:"%s"' % (qname, a), 'releasegroup:(%s)' % qname):
                j = mb("release-group", query=q, limit=10)
                gs = [g for g in j.get("release-groups", []) if g.get("primary-type") in ("Album", "EP")]
                g = next((g for g in gs if norm(g["title"]) == k), None) or \
                    next((g for g in gs if norm(g["title"]).startswith(k[:25])), None)
                if g:
                    album = {"release_group": g["id"], "title": g["title"], "date": g.get("first-release-date"),
                             "country": None}
                    break
        how = "Wikipedia infobox album: " + name
    if not album:
        album = next((r for r in rels if r["primary_type"] == "Album" and not r["secondary_types"]), None)
        how = "earliest studio album with this recording (MusicBrainz)" if album else None
    return single, album, how


def caa_front(rgid):
    try:
        j = fetch_json("https://coverartarchive.org/release-group/%s" % rgid)
    except Exception:  # archive.org backend errors are transient; retry once
        time.sleep(10)
        try:
            j = fetch_json("https://coverartarchive.org/release-group/%s" % rgid)
        except Exception as e:
            return {"error": str(e)}
    if not j:
        return None
    for im in j.get("images", []):
        if im.get("front"):
            url = im["thumbnails"].get("1200") or im["thumbnails"].get("large") or im["image"]
            return {"url": url, "caa_release": j.get("release"), "image_id": im.get("id"),
                    "types": im.get("types"), "comment": im.get("comment")}
    return None


def itunes(song, facts, prefer=()):
    term = "%s %s" % (re.split(r" featuring | feat\. ", song["artist"])[0], song["title"])
    j = fetch_json("https://itunes.apple.com/search?" + urllib.parse.urlencode(
        {"term": term, "entity": "song", "limit": 25, "country": "US"}))
    a = norm(re.split(r" featuring | feat\. |, | & | and ", song["artist"])[0])
    length = facts.get("musicbrainz", {}).get("length_ms") or 0
    best = None
    for r in j.get("results", []):
        if norm(r.get("trackName", "").split(" / ")[0]) != norm(song["title"]) or a not in norm(r.get("artistName")):
            continue
        name = (r.get("trackName", "") + " " + r.get("collectionName", "")).lower()
        if any(w in name for w in ("live", "karaoke", "remix", "instrumental", "acoustic", "re-record", "rerecord")):
            continue
        if "feat" in r.get("trackName", "").lower() and "feat" not in song["artist"].lower():
            continue  # later re-recording with a guest
        d = abs(r.get("trackTimeMillis", 0) - length) if length else 0
        # prefer the original album/single over compilations: earliest release date, then duration
        own = norm(r.get("collectionName", "").replace(" - Single", "")) in prefer
        key = (0 if own else 1, r.get("releaseDate", "9999"), d)
        if best is None or key < best[0]:
            best = (key, r)
    if not best:
        return None
    r = best[1]
    return {"url": r["artworkUrl100"].replace("100x100bb", "1200x1200bb"),
            "collection": r.get("collectionName"), "collection_id": r.get("collectionId"),
            "track_id": r.get("trackId"), "artist_name": r.get("artistName"), "release_date": r.get("releaseDate")}


def measure(img):
    small = img.convert("RGB").resize((150, 150))
    hsv = small.convert("HSV")
    px = list(hsv.get_flattened_data() if hasattr(hsv, 'get_flattened_data') else hsv.getdata())
    bright = sum(p[2] for p in px) / len(px) / 255
    sat = sum(p[1] for p in px) / len(px) / 255
    q = small.quantize(colors=5, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[:15]
    counts = sorted(q.getcolors(), reverse=True)
    palette = [{"hex": "#%02x%02x%02x" % tuple(pal[i * 3:i * 3 + 3]), "share": round(c / len(px), 3)}
               for c, i in counts]
    dark = sum(1 for p in px if p[2] < 50) / len(px)
    return {"brightness": round(bright, 3), "saturation": round(sat, 3),
            "dark_share": round(dark, 3), "palette": palette}


def save(url, path):
    data = fetch(url, binary=True)
    img = Image.open(io.BytesIO(data))
    w, h = img.size
    img = img.convert("RGB")
    img.thumbnail((SIZE, SIZE))
    img.save(path, "JPEG", quality=88)
    return img, [w, h]


def main():
    for s in load_songs():
        facts = read_json(os.path.join(SONGS, s["id"], "facts.json")) or {}
        single, album, album_how = pick_groups(s["id"], facts, s["artist"])
        out = {"retrieved": TODAY, "images": {}}
        for kind, rel in (("single", single), ("album", album)):
            if not rel:
                continue
            front = caa_front(rel["release_group"])
            entry = {"release_group": rel["release_group"], "release_title": rel["title"],
                     "release_date": rel["date"], "release_country": rel.get("country"),
                     "source": "Cover Art Archive", "confidence": "sourced"}
            if kind == "album":
                entry["chosen_by"] = album_how
            if front and front.get("error"):
                entry["missing"] = "Cover Art Archive error: " + front["error"]
            elif front:
                img, dims = save(front["url"], song_dir(s["id"], "cover", kind + ".jpg"))
                entry.update(front, file="cover/%s.jpg" % kind, original_size=dims, measures=measure(img))
                entry["measures"]["confidence"] = "computed"
            else:
                entry["missing"] = "no front image in Cover Art Archive"
            out["images"][kind] = entry
        prefer = {norm(r["title"].split(" / ")[0]) for r in (single, album) if r}
        it = itunes(s, facts, prefer)
        if it:
            img, dims = save(it["url"], song_dir(s["id"], "cover", "itunes.jpg"))
            it.update(file="cover/itunes.jpg", original_size=dims, measures=measure(img),
                      source="iTunes Search API", confidence="sourced",
                      note="current digital release artwork; may be a later reissue or compilation")
            it["measures"]["confidence"] = "computed"
            out["images"]["itunes"] = it
        # credits for the artwork from Wikidata (P736 cover art by)
        cab = facts.get("wikidata", {}).get("claims", {}).get("cover_art_by")
        if cab:
            out["credits"] = [{"name": c.get("label"), "qid": c.get("qid"), "source": "Wikidata",
                               "confidence": "sourced"} for c in cab]
        if out["images"]:
            write_json(song_dir(s["id"], "cover", "cover.json"), out)
        else:
            open(song_dir(s["id"], "cover.none"), "w").close()
        print(s["chart_year"], s["title"][:28], {k: (v.get("release_title") or v.get("collection"), "img" if v.get("file") else "-")
                                                 for k, v in out["images"].items()}, flush=True)


if __name__ == "__main__":
    main()
