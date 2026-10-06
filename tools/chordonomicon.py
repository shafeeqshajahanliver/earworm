"""Chordonomicon (crowd) chords and section tags, matched by Spotify track ID.

Chordonomicon (ailsntua/Chordonomicon on Hugging Face, CC BY-NC 4.0) has chord
sequences scraped from fan chord sites, with section tags like <verse_1>, and a
Spotify track ID per row but no titles. So songs are matched only by Spotify ID.

Spotify IDs come from no-login public routes only (never the Spotify Web API):
  1. MusicBrainz url relations on our recording (already in facts.json)
  2. Wikidata P2207 on the song item (facts.json)
  3. MusicBrainz: other recordings sharing our recording's ISRCs, and other
     recordings by the same artist with the same title and a similar length
     (remasters, album/single reissues), each looked up for url relations.
     1 request per second, cached in _cache/http.
Odesli/song.link's public API was tried and now refuses keyless use (401
PUBLIC_API_ACCESS_DEPRECATED), so it is recorded as a gap.

Writes reference/spotify-ids.json, adds 'chordonomicon' sources to
songs/<id>/chords.json and structure.json (confidence 'crowd'; key estimated by
us, confidence 'computed'), then recomputes comparisons and *.none markers.

Run: PYTHONPATH=tools python3 tools/chordonomicon.py
"""
import csv, os, re, sys, urllib.parse
from common import *
import harmony as H
from expert_sets import merge_write, finalise

CSV_URL = "https://huggingface.co/datasets/ailsntua/Chordonomicon/resolve/main/chordonomicon_v2.csv"
CSV_PATH = os.path.join(ROOT, "_cache", "chordonomicon", "chordonomicon_v2.csv")
MB = "https://musicbrainz.org/ws/2/"
LICENCE = "CC BY-NC 4.0 (Chordonomicon, Kantarelis et al. 2024); chords are crowd transcriptions from fan sites"
SP = re.compile(r"open\.spotify\.com/(?:intl-[a-z]+/)?track/([A-Za-z0-9]{22})")
MAX_LOOKUPS = 25


def mbj(path):
    return fetch_json(MB + path + ("&" if "?" in path else "?") + "fmt=json")


def spotify_from_rels(rels):
    out = []
    for r in rels or []:
        u = (r.get("url") or {}).get("resource", "")
        m = SP.search(u)
        if m:
            out.append(m.group(1))
    return out


def gather_ids(song):
    f = read_json(os.path.join(SONGS, song["id"], "facts.json")) or {}
    mb = f.get("musicbrainz") or {}
    found = {}  # spotify id -> how

    def add(i, how):
        found.setdefault(i, how)

    for u in mb.get("urls", []):
        m = SP.search(u.get("url", ""))
        if m:
            add(m.group(1), "MusicBrainz url relation on our recording %s" % mb.get("recording_id"))
    for v in ((f.get("wikidata") or {}).get("claims") or {}).get("spotify_track_id", []):
        add(v if isinstance(v, str) else v.get("value", ""), "Wikidata P2207 on %s" % f["wikidata"].get("qid"))
    ours = mb.get("recording_id")
    length = (mb.get("length_ms") or 0) / 1000
    cands = []
    for isrc in mb.get("isrcs", []):
        d = mbj("isrc/%s" % isrc) or {}
        for r in d.get("recordings", []):
            if r["id"] != ours:
                cands.append((r["id"], "MusicBrainz recording %s sharing ISRC %s" % (r["id"], isrc)))
    artists = mb.get("artists") or []
    if artists and mb.get("title"):
        q = 'recording:"%s" AND arid:%s' % (mb["title"].replace('"', ""), artists[0]["mbid"])
        d = mbj("recording?query=%s&limit=50" % urllib.parse.quote(q)) or {}
        for r in d.get("recordings", []):
            if r["id"] == ours or norm(r.get("title")) != norm(mb["title"]):
                continue
            dis = (r.get("disambiguation") or "").lower()
            if re.search(r"live|remix|demo|instrumental|acoustic|karaoke|edit|version|mix", dis):
                continue
            rl = (r.get("length") or 0) / 1000
            if length and rl and abs(rl - length) > 10:
                continue
            cands.append((r["id"], "MusicBrainz recording %s, same artist and title, similar length" % r["id"]))
    seen = set()
    for rid, how in cands:
        if rid in seen or len(seen) >= MAX_LOOKUPS:
            continue
        seen.add(rid)
        d = mbj("recording/%s?inc=url-rels" % rid) or {}
        for i in spotify_from_rels(d.get("relations")):
            add(i, how)
    # Spotify artist IDs (for reporting when no track matches)
    art_ids = []
    for a in artists[:1]:
        d = mbj("artist/%s?inc=url-rels" % a["mbid"]) or {}
        for r in d.get("relations") or []:
            m = re.search(r"open\.spotify\.com/artist/([A-Za-z0-9]{22})", (r.get("url") or {}).get("resource", ""))
            if m:
                art_ids.append(m.group(1))
    return found, sorted(set(art_ids)), len(seen)


def download():
    if os.path.exists(CSV_PATH):
        return
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    raise SystemExit("Download %s to %s first (264 MB), e.g. with curl -L -o" % (CSV_URL, CSV_PATH))


def scan(track_ids, artist_ids):
    csv.field_size_limit(10 ** 8)
    rows, art_count = {}, {}
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["spotify_song_id"] in track_ids:
                rows.setdefault(r["spotify_song_id"], []).append(r)
            if r["spotify_artist_id"] in artist_ids:
                art_count[r["spotify_artist_id"]] = art_count.get(r["spotify_artist_id"], 0) + 1
    return rows, art_count


def parse_chords(text):
    """'<intro_1> C G <verse_1> ...' -> [(tag, [tokens])]"""
    secs, cur = [], None
    for tok in text.split():
        m = re.match(r"^<([a-z_\-]+?)(?:_(\d+))?>$", tok)
        if m:
            cur = (tok.strip("<>"), [])
            secs.append(cur)
            continue
        if cur is None:
            cur = ("(untagged)", [])
            secs.append(cur)
        cur[1].append(tok)
    return secs


def build(row, how):
    secs = parse_chords(row["chords"])
    parsed_all = [H.parse_plain(t) for _, toks in secs for t in toks]
    est = H.estimate_key(parsed_all)
    tonic = est["tonic_pc"] if est else None
    flats = est and H.key_name(est["tonic_pc"], est["mode"]).split()[0] in H.FLAT_KEYS
    ssecs, csecs = [], []
    for tag, toks in secs:
        base = re.sub(r"_\d+$", "", tag)
        lab = H.normalise_label(base.replace("_", " "))
        ssecs.append({"label": tag, "normalised": lab, "start": None, "end": None})
        seq = H.collapse(toks)
        wr, rn = [], []
        for t in seq:
            ch = H.parse_plain(t)
            wr.append(H.written(ch, flats) if ch else t)
            rn.append(H.roman(ch, tonic) if ch else "?")
        csecs.append({"label": tag, "normalised": lab, "key": H.key_name(tonic, est["mode"]) if est else None,
                      "written": wr, "roman": rn, "raw": seq})
    labs = {s["normalised"] for s in ssecs}
    base = {"key": "chordonomicon", "dataset": "Chordonomicon v2", "source_id": row["id"],
              "match": {"spotify_song_id": row["spotify_song_id"], "matched_via": how,
                        "spotify_artist_id": row["spotify_artist_id"], "release_date": row["release_date"],
                        "genres": row["genres"], "main_genre": row["main_genre"]},
              "source": "Chordonomicon v2 row %s (chordonomicon_v2.csv)" % row["id"], "url": CSV_URL,
              "licence": LICENCE, "retrieved": TODAY, "confidence": "crowd",
              "version_note": "fan transcription; may follow a different version, key (capo) or simplification "
                              "than the charting recording; no timings"}
    st = dict(base, sections=ssecs, bridge="yes" if "bridge" in labs else "no",
              bridge_basis="a <bridge_n> tag in the transcription" if "bridge" in labs else
              "no <bridge_n> tag in the transcription (fan sites often omit or mislabel sections)")
    ch = dict(base, key_info={"tonic": H.note_name(tonic, flats) if est else None, "tonic_pc": tonic,
                                "mode": est["mode"] if est else None,
                                "name": H.key_name(tonic, est["mode"]) if est else None,
                                "basis": "estimated by us from the chord set (Krumhansl-Kessler profile on chord tones)",
                                "fit": est["score"] if est else None,
                                "runner_up": (H.key_name(est["runner_up"]["tonic_pc"], est["runner_up"]["mode"])
                                              + " (%.3f)" % est["runner_up"]["score"]) if est else None,
                                "confidence": "computed"},
              sections=csecs, chord_syntax="Chordonomicon tokens ('s' = sharp, e.g. Fsmin = F#m); raw kept under 'raw'")
    return st, ch


def main():
    download()
    songs = load_songs()
    ids, arts, info = {}, {}, {}
    for s in songs:
        found, art, looked = gather_ids(s)
        ids[s["id"]] = found
        arts[s["id"]] = art
        info[s["id"]] = looked
        print(s["id"], len(found), "spotify ids;", looked, "MB recordings checked", file=sys.stderr)
    all_ids = {i for v in ids.values() for i in v}
    all_arts = {a for v in arts.values() for a in v}
    rows, art_count = scan(all_ids, all_arts)
    ref = {"retrieved": TODAY, "method": __doc__.split("Writes")[0].strip(), "songs": {}}
    matched = 0
    for s in songs:
        sid = s["id"]
        hits = [(r, ids[sid][i]) for i in ids[sid] for r in rows.get(i, [])]
        seen, srcs = set(), []
        for r, how in hits:
            if r["chords"] in seen:
                continue
            seen.add(r["chords"])
            srcs.append(build(r, how))
        for n, (st, ch) in enumerate(srcs):
            if len(srcs) > 1:
                st["key"] = ch["key"] = "chordonomicon_%d" % (n + 1)
        st_doc = merge_write(sid, "structure", [x for x, _ in srcs], ("chordonomicon",))
        ch_doc = merge_write(sid, "chords", [y for _, y in srcs], ("chordonomicon",))
        write_json(os.path.join(SONGS, sid, "structure.json"), st_doc)
        write_json(os.path.join(SONGS, sid, "chords.json"), ch_doc)
        finalise(sid)
        matched += bool(srcs)
        ref["songs"][sid] = {
            "spotify_track_ids": [{"id": i, "via": how} for i, how in ids[sid].items()],
            "spotify_artist_ids": arts[sid],
            "musicbrainz_recordings_checked": info[sid],
            "chordonomicon_rows": [r["id"] for r, _ in hits],
            "chordonomicon_rows_for_artist": sum(art_count.get(a, 0) for a in arts[sid]),
            "status": ("matched" if srcs else
                       "no Spotify track ID found via MusicBrainz or Wikidata" if not ids[sid] else
                       "Spotify IDs found but none is in Chordonomicon"),
            "source": "MusicBrainz (CC0) url relations; Wikidata (CC0)", "confidence": "sourced",
        }
        print(sid, ref["songs"][sid]["status"], len(srcs))
    ref["matched"] = matched
    ref["gaps"] = {"odesli": "api.song.link public API returns 401 PUBLIC_API_ACCESS_DEPRECATED without a key",
                   "spotify_web_api": "needs a key; not used"}
    write_json(os.path.join(ROOT, "reference", "spotify-ids.json"), ref)
    print("matched", matched, "of", len(songs))


if __name__ == "__main__":
    main()
