"""Data audit: what we hold for every song, key values per layer, and every flag or doubt.
Writes reports/data-audit.md. Deterministic."""
import os, re
from common import *


def j(sid, *p):
    return read_json(os.path.join(SONGS, sid, *p)) or {}


def has(sid, *p):
    return os.path.exists(os.path.join(SONGS, sid, *p))


def audit(s):
    sid = s["id"]
    corr = j(sid, "corrections.json")
    f, w, c = j(sid, "facts.json"), j(sid, "wikipedia.json"), j(sid, "charts.json")
    lm, ls, a = j(sid, "lyrics", "measures.json"), j(sid, "lyrics", "source.json"), j(sid, "audio.json")
    cov, lin = j(sid, "cover", "cover.json").get("images", {}), j(sid, "lineage.json")
    st, ch = j(sid, "structure.json"), j(sid, "chords.json")
    mb = dict(f.get("musicbrainz", {}))
    for o in corr.get("overrides", []):  # apply recorded corrections
        if o.get("file") == "facts.json" and o.get("field") == "musicbrainz.length_ms":
            mb["length_ms"] = o["corrected_value"]
    wd = f.get("wikidata", {}).get("claims", {})
    work = mb.get("work", {})
    writers = sorted({x["name"] for x in work.get("credits", []) if x["role"] in ("composer", "lyricist", "writer")})
    producers = sorted({x["name"] for x in mb.get("recording_credits", []) if x["role"] == "producer"})
    if not producers:
        producers = [x.get("label") for x in wd.get("producer", [])]
    secs = [x["heading"] for x in w.get("sections", [])]
    comp = [x for x in w.get("sections", []) if re.search(r"compos|music|lyric|structure", x["heading"], re.I)]
    key_text = None
    for x in comp + w.get("sections", [])[:1]:
        m = re.search(r"in the key of ([A-G][♭♯b#]?(?:[- ]?(?:flat|sharp))? (?:major|minor))", x.get("text", ""))
        if m:
            key_text = m.group(1); break
    ms = a.get("measures", {})
    flags = []
    flags += ["lyrics: " + x for x in ls.get("flags", [])]
    flags += ["audio: " + x for x in a.get("flags", [])]
    if f.get("musicbrainz_match", "").startswith("recording search"):
        flags.append("facts: matched by recording search, not the single release")
    if not mb.get("length_ms"):
        flags.append("facts: no recording length in MusicBrainz")
    for k, v in cov.items():
        if v.get("missing"):
            flags.append("cover %s: %s" % (k, v["missing"]))
        types = [t.lower() for t in (v.get("types") or [])]
        if "medium" in types:
            flags.append("cover %s: image is the disc label (no picture sleeve)" % k)
    for kind in ("structure", "chords"):
        for src in j(sid, kind + ".json").get("sources", []):
            if src.get("version_note"):
                flags.append("%s %s: %s" % (kind, src["key"], src["version_note"]))
            if src.get("suspect_match"):
                flags.append("%s %s: suspect match" % (kind, src["key"]))
    if isinstance(st.get("comparison"), dict) and st["comparison"].get("section_order_agree") is False:
        flags.append("structure: sources disagree on section order")
    for o in corr.get("overrides", []) + corr.get("unusable_sources", []):
        flags.append("correction: " + o["reason"][:110])
    bridge = None
    if isinstance(st.get("comparison"), dict):
        bridge = st["comparison"].get("bridge_expert_value")
    elif st.get("sources"):
        bridge = st["sources"][0].get("bridge")
    chord_key = None
    if ch.get("sources"):
        chord_key = ch["sources"][0].get("key_info", {}).get("name")
    return {
        "song": "%s %s" % (s["chart_year"], s["title"]), "artist": s["artist"], "country": s["country"],
        "release": mb.get("first_release_date"), "length": round((mb.get("length_ms") or 0) / 1000) or None,
        "writers": writers, "producers": producers, "wd": s["wikidata"], "match": f.get("musicbrainz_match", "")[:20],
        "wiki": w.get("title"), "sections": len(secs), "composition_section": bool(comp), "wiki_key": key_text,
        "peak": c.get("peak_position"), "weeks": c.get("weeks_on_chart"), "debut": c.get("debut_position"),
        "no1": c.get("weeks_at_number_one"),
        "words": lm.get("words"), "repeat": lm.get("repeated_line_share"), "zlib": lm.get("zlib_compression_ratio"),
        "first_vocal": lm.get("first_vocal_s"),
        "bpm": ms.get("tempo_bpm"), "dz_bpm": (a.get("deezer_metadata") or {}).get("bpm"), "audio_key": ms.get("key"),
        "lufs": ms.get("lufs_approx") or ms.get("loudness_lufs_approx"),
        "covers": "/".join(k[0].upper() for k in ("single", "album", "itunes") if cov.get(k, {}).get("file")) or "-",
        "original": None if not lin else ("original" if lin["performance"]["is_original"] else
                                          "cover of " + str(lin["work"]["original_performer"])),
        "versions": lin.get("work", {}).get("versions") if lin else None,
        "struct_src": [x["key"] for x in st.get("sources", [])], "chord_src": [x["key"] for x in ch.get("sources", [])],
        "bridge": bridge, "chord_key": chord_key, "flags": flags,
    }


def fmt(v):
    return "–" if v in (None, "", [], 0) else str(v)


def main():
    rows = [audit(s) for s in load_songs()]
    n = len(rows)
    count = lambda pred: sum(1 for r in rows if pred(r))
    out = ["# Data audit", "", "Generated by `tools/audit.py` from the files in `songs/`. %d songs. "
           "`–` means not held." % n, "",
           "## Field completeness", "", "| Field | Songs | Notes |", "|---|---|---|",
           "| Writers (MusicBrainz work) | %d | |" % count(lambda r: r["writers"]),
           "| Producers (MusicBrainz, else Wikidata) | %d | |" % count(lambda r: r["producers"]),
           "| Recording length | %d | |" % count(lambda r: r["length"]),
           "| Wikipedia composition/music section | %d | where key, tempo and form are usually described |" % count(lambda r: r["composition_section"]),
           "| Key stated in Wikipedia text | %d | sourced key, usually citing sheet music |" % count(lambda r: r["wiki_key"]),
           "| Chart run | %d | |" % count(lambda r: r["peak"]),
           "| Lyrics measures | %d | |" % count(lambda r: r["words"]),
           "| Tempo (preview) | %d | |" % count(lambda r: r["bpm"]),
           "| Any cover image | %d | |" % count(lambda r: r["covers"] != "-"),
           "| Lineage | %d | |" % count(lambda r: r["original"]),
           "| Structure (any source) | %d | |" % count(lambda r: r["struct_src"]),
           "| Chords (any source) | %d | |" % count(lambda r: r["chord_src"]),
           "| Songs with at least one flag | %d | listed below |" % count(lambda r: r["flags"]), "",
           "## Identity and credits", "", "| Song | Artist | Country | First release | Length (s) | Writers | Producers |",
           "|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append("| %s | %s | %s | %s | %s | %s | %s |" % (r["song"], r["artist"], r["country"], fmt(r["release"]),
                   fmt(r["length"]), fmt(", ".join(r["writers"])), fmt(", ".join(p for p in r["producers"] if p))))
    out += ["", "## Chart, lyrics, sound", "",
            "| Song | Debut | Peak | Weeks on chart | Weeks at #1 | Words | Repeated lines | First vocal (s) | BPM (ours / Deezer) | Key (preview) | Key (Wikipedia) |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        rep = "%d%%" % round(100 * r["repeat"]) if r["repeat"] is not None else "–"
        out.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s / %s | %s | %s |" % (
            r["song"], fmt(r["debut"]), fmt(r["peak"]), fmt(r["weeks"]), r["no1"] if r["no1"] is not None else "–",
            fmt(r["words"]), rep, fmt(r["first_vocal"]), fmt(r["bpm"]), fmt(r["dz_bpm"]), fmt(r["audio_key"]), fmt(r["wiki_key"])))
    out += ["", "## Covers, lineage, structure, chords", "",
            "Covers: S = single sleeve, A = album, I = iTunes digital artwork.", "",
            "| Song | Covers | Original or cover | Recorded versions (SHS) | Structure sources | Bridge | Chord sources | Chord key |",
            "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (r["song"], r["covers"], fmt(r["original"]), fmt(r["versions"]),
                   fmt(", ".join(r["struct_src"])), fmt(r["bridge"]), fmt(", ".join(r["chord_src"])), fmt(r["chord_key"])))
    out += ["", "## Flags and doubts", ""]
    for r in rows:
        if r["flags"]:
            out.append("**%s**" % r["song"])
            out += ["- " + x for x in r["flags"]]
            out.append("")
    os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
    with open(os.path.join(ROOT, "reports", "data-audit.md"), "w") as fh:
        fh.write("\n".join(out).rstrip() + "\n")


if __name__ == "__main__":
    main()
