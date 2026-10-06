"""Timed-lyrics layer: fetch each song's lyrics from LRCLIB (no login), match them to the
charting recording, and compute simple measures.

Writes songs/<id>/lyrics/timed.lrc (or plain.txt), lyrics/source.json, lyrics/measures.json,
or songs/<id>/lyrics.none when nothing matches.

Usage (from repo root):  PYTHONPATH=tools python3 tools/lyrics.py [song-id ...]
Run tools/audio.py first: the Deezer track matched by ISRC is used as a second reference length.
"""
import os, re, sys, urllib.parse, zlib
from collections import Counter

from common import SONGS, TODAY, fetch_json, load_songs, norm, read_json, ref_lengths, write_json
from audio import artist_ok, clean_version, title_ok, ref_match

API = "https://lrclib.net/api/"
TS = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")


def wiki_album(sid):
    w = read_json(os.path.join(SONGS, sid, "wikipedia.json")) or {}
    a = (w.get("infobox") or {}).get("album", "") or ""
    a = re.split(r"\{\{|<|\n", a)[0]
    return re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", a).strip(" '\"")


def candidates(song, mb, album, refs):
    seen, out = set(), []
    titles = {mb.get("title") or song["title"], song["title"]}
    artists = {mb.get("artist_credit") or song["artist"], song["artist"],
               re.split(r" featuring | feat\.? ", song["artist"])[0]}
    queries = []
    if album and refs:
        for t in titles:
            for a in artists:
                queries.append(("get", {"track_name": t, "artist_name": a, "album_name": album,
                                        "duration": int(round(refs[0][0]))}))
    for t in titles:
        for a in artists:
            queries.append(("search", {"track_name": t, "artist_name": a}))
    plain_title = re.sub(r"\(.*?\)", "", song["title"]).strip()
    queries.append(("search", {"q": "%s %s" % (re.split(r" featuring | feat\.? ", song["artist"])[0], plain_title)}))
    for kind, params in queries:
        r = fetch_json(API + kind + "?" + urllib.parse.urlencode(params))
        items = r if isinstance(r, list) else ([r] if isinstance(r, dict) and r.get("id") else [])
        for c in items:
            if c["id"] not in seen:
                seen.add(c["id"])
                out.append(c)
    return out


def words(text):
    return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", (text or "").lower().replace("’", "'"))


def norm_line(t):
    return " ".join(words(t))


def title_phrase(title):
    t = re.sub(r"\s*(’|')?(19|20)?97\b$", "", title)  # "Candle in the Wind 1997"
    inner = re.sub(r"\(.*?\)", "", t).strip()
    return norm_line(inner or t)


def parse_lrc(text):
    rows = []
    for raw in (text or "").splitlines():
        stamps = TS.findall(raw)
        body = TS.sub("", raw).strip()
        for m, s in stamps:
            rows.append((int(m) * 60 + float(s), body))
    rows.sort(key=lambda r: r[0])
    return rows


def plain_from_synced(text):
    return "\n".join(b for _, b in parse_lrc(text) if b)


def jaccard(a, b):
    a, b = set(words(a)), set(words(b))
    return len(a & b) / len(a | b) if a | b else 0


STOP = {"the", "a", "an", "of", "to", "and", "in", "on", "for", "it", "is", "be", "i", "you", "me", "my"}


def title_word_share(title, text):
    """Share of the title's content words that appear in the lyric (prefix match, so 'blinding'
    finds 'blinded'). A check that the lyric belongs to this song."""
    tw = [w for w in words(title_phrase(title)) if w not in STOP and not w.isdigit()] or words(title_phrase(title))
    lw = set(words(text))
    hit = sum(any(l[:5] == w[:5] if len(w) >= 5 else l == w for l in lw) for w in tw)
    return hit / len(tw) if tw else 1.0


def choose(song, cands, refs, albums=()):
    rejected, ok = [], []
    for c in cands:
        tag = "lrclib %s (%s / %s / %s, %ss)" % (c["id"], c.get("trackName"), c.get("artistName"),
                                                  c.get("albumName"), c.get("duration"))
        if not (title_ok(c.get("trackName", ""), song["title"]) and artist_ok(c.get("artistName", ""), song)):
            continue  # a different song or artist; not worth listing
        if not clean_version("%s %s" % (c.get("trackName"), c.get("albumName"))):
            rejected.append(tag + ": live/remix/other version")
            continue
        if c.get("instrumental"):
            rejected.append(tag + ": marked instrumental")
            continue
        if not (c.get("syncedLyrics") or c.get("plainLyrics")):
            rejected.append(tag + ": no lyrics")
            continue
        rm = ref_match(float(c.get("duration") or 0), refs) if refs else (0, 0, "no reference length")
        if not rm:
            rejected.append(tag + ": duration matches no reference length")
            continue
        text = c.get("plainLyrics") or plain_from_synced(c.get("syncedLyrics"))
        share = title_word_share(song["title"], text)
        if share < 0.6:
            rejected.append(tag + ": only %.0f%% of title words in the lyric (wrong song?)" % (share * 100))
            continue
        n_refs = sum(abs(float(c.get("duration") or 0) - sec) <= 5 for sec, _ in refs)
        alb = norm(c.get("albumName"))
        album_tier = 0 if alb and (alb in albums or norm(song["title"]) in alb) else 1
        ok.append((rm, c, text, n_refs, album_tier))
    if not ok:
        return None, rejected, None
    # agreement: how similar each candidate's words are to the other candidates'
    def agree(i):
        others = [jaccard(ok[i][2], o[2]) for j, o in enumerate(ok) if j != i]
        return sorted(others)[len(others) // 2] if others else None
    scored = []
    for i, (rm, c, text, n_refs, album_tier) in enumerate(ok):
        a = agree(i)
        # synced first; then lengths agreeing with most references; then best reference;
        # then entries that agree with the others; then the song's own album or single
        scored.append(((0 if c.get("syncedLyrics") else 1), -n_refs, rm[0], (a is not None and a < 0.5),
                       album_tier, rm[1], -(a or 0), i))
    scored.sort()
    i = scored[0][-1]
    rm, c, text = ok[i][:3]
    return (c, rm, agree(i), len(ok)), rejected, text


def measures(song, c, length_s):
    synced = c.get("syncedLyrics")
    title = title_phrase(song["title"])
    if synced:
        rows = parse_lrc(synced)
        lyr = [(t, b) for t, b in rows if b and norm_line(b)]
        texts = [b for _, b in lyr]
    else:
        rows, lyr = [], []
        texts = [l.strip() for l in (c.get("plainLyrics") or "").splitlines() if norm_line(l)]
    normed = [norm_line(t) for t in texts]
    toks = [w for t in texts for w in words(t)]
    full = "\n".join(normed)
    seen, repeats = set(), 0
    for n in normed:
        repeats += n in seen
        seen.add(n)
    comp = len(zlib.compress(full.encode(), 9)) / max(1, len(full.encode()))
    tw = " ".join(toks)
    cnt = Counter(toks)
    pron = {
        "first_singular": sum(cnt[w] for w in ("i", "me", "my", "mine", "myself", "i'm", "i'll", "i've", "i'd")),
        "second": sum(cnt[w] for w in ("you", "your", "yours", "yourself", "you're", "you'll", "you've", "you'd", "ya", "y'all")),
        "first_plural": sum(cnt[w] for w in ("we", "us", "our", "ours", "ourselves", "we're", "we'll", "we've", "we'd")),
    }
    m = {
        "lines": len(texts),
        "words": len(toks),
        "unique_words": len(cnt),
        "type_token_ratio": round(len(cnt) / max(1, len(toks)), 3),
        "repeated_line_share": round(repeats / max(1, len(normed)), 3),
        "distinct_lines": len(set(normed)),
        "zlib_compression_ratio": round(comp, 3),
        "zlib_note": "compressed size / original size of the lower-cased lyric text; lower = more repetitive",
        "title_phrase": title,
        "title_phrase_occurrences": len(re.findall(r"(?<![a-z0-9'])%s(?![a-z0-9'])" % re.escape(title), tw)) if title else None,
        "pronouns": pron,
        "pronoun_note": "word counts; contractions (I'm, you're, we're) count with their pronoun",
    }
    if lyr:
        starts = [t for t, _ in lyr]
        all_starts = [t for t, _ in rows]
        sung = 0.0
        for t, b in lyr:
            nxt = [s for s in all_starts if s > t]
            dur = (nxt[0] - t) if nxt else 4.0
            sung += min(dur, 8.0)
        gaps = [(starts[i + 1] - starts[i], starts[i]) for i in range(len(starts) - 1)]
        g = max(gaps) if gaps else (None, None)
        block = None
        for i in range(len(normed) - 1):
            if normed[i] == normed[i + 1]:
                continue
            for j in range(i + 2, len(normed) - 1):
                if normed[j] == normed[i] and normed[j + 1] == normed[i + 1]:
                    if block is None or starts[j] < block["recurs_at_s"]:
                        block = {"first_at_s": round(starts[i], 2), "recurs_at_s": round(starts[j], 2),
                                 "lines": [texts[i], texts[i + 1]]}
                    break
        m.update({
            "first_vocal_s": round(starts[0], 2),
            "last_line_s": round(starts[-1], 2),
            "sung_time_s": round(sung, 1),
            "sung_time_note": "sum of each lyric line's time to the next timestamp, capped at 8 s per line",
            "words_per_minute_sung": round(len(toks) / sung * 60, 1) if sung else None,
            "words_per_minute_track": round(len(toks) / length_s * 60, 1) if length_s else None,
            "longest_gap_between_lines_s": round(g[0], 2) if g[0] is not None else None,
            "longest_gap_starts_at_s": round(g[1], 2) if g[1] is not None else None,
            "first_repeated_block": block,
            "first_repeated_block_note": "computed, chorus proxy: the earliest-recurring pair of consecutive "
                                         "distinct lines; first_at_s is when it is first sung, recurs_at_s when it "
                                         "comes back. A crude stand-in for time to first chorus.",
        })
    return m


def process(song):
    sid = song["id"]
    d = os.path.join(SONGS, sid, "lyrics")
    none_path = os.path.join(SONGS, sid, "lyrics.none")
    mb = (read_json(os.path.join(SONGS, sid, "facts.json")) or {}).get("musicbrainz") or {}
    refs = ref_lengths(sid)
    album = wiki_album(sid)
    cands = candidates(song, mb, album, refs)
    albums = {norm(album)} if album else set()
    albums |= {norm(r.get("title")) for r in mb.get("releases") or [] if r.get("title")}
    pick, rejected, text = choose(song, cands, refs, albums)
    if not pick:
        with open(none_path, "w") as f:
            f.write("No matching LRCLIB entry (%s); %d candidates seen. Rejected: %s\n"
                    % (TODAY, len(cands), "; ".join(rejected) or "none"))
        print(sid, "NONE", rejected[:5])
        return
    c, rm, agreement, n_ok = pick
    os.makedirs(d, exist_ok=True)
    for stale in ("timed.lrc", "plain.txt"):
        p = os.path.join(d, stale)
        if os.path.exists(p):
            os.remove(p)
    if c.get("syncedLyrics"):
        with open(os.path.join(d, "timed.lrc"), "w") as f:
            f.write(c["syncedLyrics"].rstrip() + "\n")
        kind = "synced"
    else:
        with open(os.path.join(d, "plain.txt"), "w") as f:
            f.write(c["plainLyrics"].rstrip() + "\n")
        kind = "plain"
    flags = []
    if agreement is not None and agreement < 0.5:
        flags.append("words differ a lot from other matching LRCLIB entries (median Jaccard %.2f)" % agreement)
    if not rm[2].startswith("musicbrainz"):
        flags.append("duration matched %s, not the MusicBrainz recording length (missing or another edit)" % rm[2])
    src = {
        "source": "LRCLIB (lrclib.net)", "lrclib_id": c["id"], "kind": kind,
        "matched": {"track": c.get("trackName"), "artist": c.get("artistName"), "album": c.get("albumName"),
                    "duration_s": c.get("duration")},
        "duration_matched_to": rm[2], "duration_diff_s": rm[1],
        "reference_lengths": [{"seconds": s, "source": l} for s, l in refs],
        "matching_candidates": n_ok,
        "agreement_with_other_candidates": round(agreement, 3) if agreement is not None else None,
        "agreement_note": "median word-set Jaccard similarity to the other LRCLIB entries that passed the checks",
        "checks": "artist and title match; not live/remix/karaoke/cover; not instrumental; duration within 5 s "
                  "of a reference length; at least 60% of the title's words appear in the lyric. Preference: synced, "
                  "agrees with most reference lengths, MusicBrainz length, agrees with other entries, own album/single",
        "flags": flags,
        "rejected_candidates": rejected,
        "retrieved": TODAY, "confidence": "crowd",
    }
    write_json(os.path.join(d, "source.json"), src)
    length_s = refs[0][0] if refs else c.get("duration")
    if rm[2].startswith("deezer") or rm[2].startswith("wikipedia"):
        length_s = c.get("duration")
    m = measures(song, c, length_s)
    write_json(os.path.join(d, "measures.json"), {
        "id": sid, "lyrics_kind": kind, "lrclib_id": c["id"], **m,
        "source": "computed from LRCLIB %s" % c["id"], "retrieved": TODAY, "confidence": "computed"})
    if os.path.exists(none_path):
        os.remove(none_path)
    print(sid, kind, c["id"], c.get("artistName"), "|", c.get("albumName"), c.get("duration"), rm[2],
          "agree=%s" % (round(agreement, 2) if agreement is not None else None), flags)


def main():
    ids = sys.argv[1:]
    for s in load_songs():
        if ids and s["id"] not in ids:
            continue
        try:
            process(s)
        except Exception as e:
            print(s["id"], "ERROR", repr(e))


if __name__ == "__main__":
    main()
