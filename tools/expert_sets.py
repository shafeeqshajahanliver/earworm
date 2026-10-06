"""Structure and chords from hand-annotated research datasets (confidence 'expert').

Sources (downloaded once into _cache/expert/<source>/, each archive extracted
into its own empty folder and read as data only):
  - McGill Billboard 2.0 (salami_chords + index), CC0. Hosted on Dropbox links
    published by DDMAL and used by the mirdata loader (the DDMAL page now 404s).
  - Harmonix Set (segments, beats/downbeats, metadata), MIT licence, GitHub raw.
  - Rolling Stone corpus RS 200 (de Clercq & Temperley): raw harmonic analyses
    by two analysts, timed chord lists, bar timings. CC BY 4.0.
  - Isophonics reference annotations (The Beatles: chords, keys, segments).
    No licence stated on the page.

Writes songs/<id>/structure.json and songs/<id>/chords.json (merging with any
Chordonomicon entries written by tools/chordonomicon.py), and *.none markers
when no source covers a song. Also writes reference/expert-sets.json (index of
what matched).

Run: PYTHONPATH=tools python3 tools/expert_sets.py
"""
import csv, glob, io, os, re, sys, tarfile, zipfile
from common import *
import harmony as H

E = os.path.join(ROOT, "_cache", "expert")
FILES = {
    "mcgill/billboard-2.0-index.csv": "https://www.dropbox.com/s/o0olz0uwl9z9stb/billboard-2.0-index.csv?dl=1",
    "mcgill/billboard-2.0-salami_chords.tar.gz": "https://www.dropbox.com/s/2lvny9ves8kns4o/billboard-2.0-salami_chords.tar.gz?dl=1",
    "rs/rs200.txt": "https://rockcorpus.midside.com/overview/rs200.txt",
    "rs/rs200_harmony.zip": "https://rockcorpus.midside.com/harmonic_analyses/rs200_harmony.zip",
    "rs/rs200_harmony_clt.zip": "https://rockcorpus.midside.com/harmonic_analyses/rs200_harmony_clt.zip",
    "rs/timing_data.zip": "https://rockcorpus.midside.com/timing_data/timing_data.zip",
    "rs/audio_sources.txt": "https://rockcorpus.midside.com/timing_data/audio_sources.txt",
    "isophonics/The_Beatles_Annotations.tar.gz": "https://isophonics.net/files/annotations/The%20Beatles%20Annotations.tar.gz",
    "harmonix/metadata.csv": "https://raw.githubusercontent.com/urinieto/harmonixset/master/dataset/metadata.csv",
}
EXTRACT = {
    "mcgill/billboard-2.0-salami_chords.tar.gz": "mcgill/x_salami",
    "isophonics/The_Beatles_Annotations.tar.gz": "isophonics/x_beatles",
    "rs/rs200_harmony.zip": "rs/x_harmony",
    "rs/rs200_harmony_clt.zip": "rs/x_clt",
    "rs/timing_data.zip": "rs/x_timing",
}
HX_RAW = "https://raw.githubusercontent.com/urinieto/harmonixset/master/dataset/"
LICENCE = {
    "mcgill_billboard": "CC0 1.0 (per the DDMAL release, as quoted in the mirdata loader)",
    "harmonix": "MIT licence (repository LICENSE); annotations only, no audio",
    "rolling_stone": "CC BY 4.0 (credit: Trevor de Clercq and David Temperley, rock corpus)",
    "isophonics": "No licence stated on the Isophonics page; cite Harte (2010) / Mauch et al. (2009)",
}
VERSION_TOLERANCE = 12  # seconds; larger duration gaps flag a different edit or version


def download():
    for p, u in FILES.items():
        d = os.path.join(E, p)
        if os.path.exists(d):
            continue
        os.makedirs(os.path.dirname(d), exist_ok=True)
        b = fetch(u, binary=True, cache=False)
        if b is None:
            print("missing", u)
            continue
        with open(d, "wb") as f:
            f.write(b)
    for a, d in EXTRACT.items():
        src, dst = os.path.join(E, a), os.path.join(E, d)
        if os.path.isdir(dst) or not os.path.exists(src):
            continue
        os.makedirs(dst)  # new, empty folder per archive
        if a.endswith(".zip"):
            z = zipfile.ZipFile(src)
            for n in z.namelist():
                if n.startswith("/") or ".." in n.split("/"):
                    raise ValueError("unsafe path in %s: %s" % (a, n))
            z.extractall(dst)
        else:
            tarfile.open(src).extractall(dst, filter="data")


def rd(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


# ---- matching ---------------------------------------------------------------
def artist_ok(ours, theirs):
    """Artist check: any significant word-run of the main credited artist appears in theirs."""
    a, b = norm(ours), norm(theirs)
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    main = re.split(r"(?i)\s+(?:featuring|feat\.?|ft\.?|with|and|&|,)\s+", ours)[0]
    m = norm(re.sub(r"(?i)^the\s+", "", main))
    return bool(m) and (m in b)


def title_key(t):
    return norm(re.sub(r"(?i)^the\s+", "", t or ""))


def song_meta(s):
    f = read_json(os.path.join(SONGS, s["id"], "facts.json")) or {}
    mb = f.get("musicbrainz") or {}
    length, basis = (mb.get("length_ms") or 0) / 1000 or None, "MusicBrainz recording length"
    if not length:  # fall back to the Wikipedia infobox length of the single
        w = read_json(os.path.join(SONGS, s["id"], "wikipedia.json")) or {}
        m = re.match(r"^\s*(\d+):(\d\d)", ((w.get("infobox") or {}).get("length") or ""))
        if m:
            length, basis = int(m.group(1)) * 60 + int(m.group(2)), "Wikipedia infobox length"
    return {"length": length, "length_basis": basis, "recording": mb.get("recording_id"),
            "artist_credit": mb.get("artist_credit") or s["artist"]}


def version_check(meta, theirs_len, same_recording=False):
    ours_len = meta["length"]
    if same_recording:
        return None, "same MusicBrainz recording"
    if not ours_len or not theirs_len:
        return None, "duration not comparable (missing length)"
    gap = theirs_len - ours_len
    ref = "our recording (%s)" % meta["length_basis"]
    if abs(gap) > VERSION_TOLERANCE:
        return ("annotated audio is %.0f s vs %.0f s for %s: a different edit or version; "
                "section times do not line up with the charting recording" % (theirs_len, ours_len, ref)), \
            "duration differs by %+.0f s from %s" % (gap, ref)
    return None, "duration within %d s (%+.1f s) of %s" % (VERSION_TOLERANCE, gap, ref)


# ---- McGill Billboard -------------------------------------------------------
def mcgill_index():
    rows = list(csv.DictReader(open(os.path.join(E, "mcgill/billboard-2.0-index.csv"))))
    return [r for r in rows if r["title"]]


def parse_salami(text):
    """Returns header dict and sections [{start,end,letter,label,bars,chords,keys}]."""
    head, secs, tonic = {}, [], None
    events = []
    for line in text.splitlines():
        if line.startswith("#"):
            m = re.match(r"#\s*(\w+):\s*(.*)", line)
            if m:
                head.setdefault(m.group(1), m.group(2).strip())
                if m.group(1) == "tonic":
                    tonic = m.group(2).strip()
            continue
        if not line.strip():
            continue
        t, _, rest = line.partition("\t")
        events.append((float(t), rest, tonic))
    cur = None
    for i, (t, rest, tonic) in enumerate(events):
        parts = [p.strip() for p in rest.split(",")]
        letter, label = None, None
        if parts and re.match(r"^[A-Z]'*$", parts[0]):
            letter = parts.pop(0)
        if parts and re.match(r"^[a-z][a-z \-]*$", parts[0]) and not parts[0].startswith("|"):
            label = parts.pop(0)
        if label in ("silence", "end") or rest.strip() in ("silence", "end"):
            if cur:
                cur["end"] = t
                cur = None
            continue
        if label or letter:
            if cur:
                cur["end"] = t
            cur = {"start": t, "end": None, "letter": letter, "label": label or "", "bars": 0,
                   "tokens": [], "keys": []}
            secs.append(cur)
        if cur is None:
            continue
        bars = "|".join(p for p in parts if "|" in p)
        m = re.search(r"\|\s*x(\d+)", rest)
        rep = int(m.group(1)) if m else 1
        cells = [c.strip() for c in bars.split("|")[1:-1]]
        line_tokens, nb = [], 0
        for c in cells:
            if re.match(r"^x\d+$", c):
                continue
            nb += 1
            for tok in c.split():
                if tok == "." or re.match(r"^\(\d+/\d+\)$", tok):
                    continue
                line_tokens.append((tok, tonic))
        for _ in range(rep):
            cur["tokens"] += line_tokens
            cur["bars"] += nb
    if cur and cur["end"] is None and events:
        cur["end"] = events[-1][0]
    return head, secs


def mcgill_sources(song, meta):
    out = []
    seen = set()
    for r in mcgill_index():
        if title_key(r["title"]) != title_key(song["title"]) or not artist_ok(song["artist"], r["artist"]):
            continue
        path = os.path.join(E, "mcgill/x_salami/McGill-Billboard/%04d/salami_chords.txt" % int(r["id"]))
        if not os.path.exists(path):
            continue
        text = rd(path)
        if text in seen:  # the index lists some songs twice with identical annotations
            out[-1][0]["also_ids"].append(r["id"])
            continue
        seen.add(text)
        head, secs = parse_salami(text)
        end = max(float(l.split("\t")[0]) for l in text.splitlines() if re.match(r"^\d", l))
        vnote, vcheck = version_check(meta, end)
        sections = [{"start": round(s["start"], 3), "end": round(s["end"], 3), "label": s["label"],
                     "letter": s["letter"], "normalised": H.normalise_label(s["label"]) if s["label"] else "other",
                     "bars": s["bars"]} for s in secs]
        base = {"key": "mcgill_billboard", "dataset": "McGill Billboard 2.0", "source_id": r["id"],
                "also_ids": [], "match": {"title": r["title"], "artist": r["artist"],
                                          "chart_date": r["chart_date"], "peak_rank": r["peak_rank"]},
                "source": "McGill Billboard Project 2.0, salami_chords.txt id %s (Burgoyne, Wild & Fujinaga 2011)" % r["id"],
                "url": FILES["mcgill/billboard-2.0-salami_chords.tar.gz"], "licence": LICENCE["mcgill_billboard"],
                "retrieved": TODAY, "confidence": "expert", "annotated_duration": round(end, 3),
                "version_check": vcheck}
        if vnote:
            base["version_note"] = vnote
        labs = {s["normalised"] for s in sections}
        basis = ("a section labelled 'bridge' by the annotator" if "bridge" in labs else
                 "no section labelled 'bridge' by the annotator")
        ch_letters = {(x["letter"] or "").rstrip("'") for x in sections if x["normalised"] == "chorus"}
        br_letters = {(x["letter"] or "") for x in sections if x["normalised"] == "bridge"}
        shared = sorted(l for l in br_letters if l.rstrip("'") in ch_letters)
        if shared:
            basis += ("; note: the annotator's letter for it (%s) marks it as a variant of the chorus "
                      "material, not new music" % ", ".join(shared))
        st = dict(base, sections=sections, bridge="yes" if "bridge" in labs else "no", bridge_basis=basis)
        # chords
        tonic0 = head.get("tonic")
        csecs = []
        for s, ss in zip(secs, sections):
            toks = [(t, k) for t, k in s["tokens"]]
            seq = H.collapse([(t, k) for t, k in toks if t not in ("*", "&pause")])
            wr, rn, keys = [], [], []
            for t, k in seq:
                ch = H.parse_harte(t)
                kp = H.pc(k) if k else None
                wr.append(H.written(ch))
                rn.append(H.roman(ch, kp))
                keys.append(k)
            sec = {"label": ss["label"], "letter": ss["letter"], "normalised": ss["normalised"],
                   "start": ss["start"], "end": ss["end"], "bars": ss["bars"],
                   "key": H.collapse(keys)[0] if len(set(keys)) == 1 else " -> ".join(H.collapse(keys)) if keys else tonic0,
                   "written": wr, "roman": rn, "raw": H.collapse([t for t, _ in toks])}
            csecs.append(sec)
        changes = []
        prev = None
        for s in secs:
            for _, k in s["tokens"][:1]:
                if prev and k != prev:
                    changes.append({"at": round(s["start"], 3), "tonic": k})
                prev = k
        ch = dict(base, key_info={"tonic": tonic0, "tonic_pc": H.pc(tonic0), "mode": None,
                                  "name": tonic0, "basis": "annotated tonic (McGill gives tonic only, not mode)",
                                  "confidence": "expert"},
                  key_changes=changes, sections=csecs,
                  chord_syntax="Harte (root:quality); raw tokens kept under 'raw'")
        out.append((st, ch))
    return out


# ---- Harmonix Set -----------------------------------------------------------
HX_LABEL_NOTE = "Harmonix labels: intro, verse, prechorus, chorus, postchorus, bridge, inst, solo, outro, break, end ..."


def harmonix_sources(song, meta):
    out = []
    rows = list(csv.DictReader(open(os.path.join(E, "harmonix/metadata.csv"), encoding="utf-8")))
    for r in rows:
        if title_key(r["Title"]) != title_key(song["title"]) or not artist_ok(song["artist"], r["Artist"]):
            # Harmonix sometimes credits a featured act (e.g. 'Yeah!' to Lil Jon); accept if a
            # featured artist of ours matches theirs
            if not (title_key(r["Title"]) == title_key(song["title"]) and
                    any(artist_ok(a, r["Artist"]) for a in re.split(r"(?i)\s+(?:featuring|feat\.?|and|&|,)\s+", song["artist"])[1:])):
                continue
        seg = fetch(HX_RAW + "segments/%s.txt" % r["File"])
        if not seg:
            continue
        beats = fetch(HX_RAW + "beats_and_downbeats/%s.txt" % r["File"]) or ""
        pts = []
        for line in seg.splitlines():
            p = line.split()
            if len(p) >= 2:
                pts.append((float(p[0]), " ".join(p[1:])))
        secs = []
        for (t, lab), nxt in zip(pts, pts[1:] + [(None, None)]):
            if lab in ("end", "silence"):
                continue
            secs.append({"start": round(t, 3), "end": round(nxt[0], 3) if nxt[0] is not None else None,
                         "label": lab, "normalised": H.normalise_label(lab)})
        downbeats = [float(l.split()[0]) for l in beats.splitlines() if len(l.split()) >= 3 and l.split()[1] == "1"]
        for s in secs:
            s["bars"] = sum(1 for d in downbeats if s["start"] - 0.05 <= d < (s["end"] or 1e9) - 0.05)
        same = r["MusicBrainz Id"] == meta["recording"]
        vnote, vcheck = version_check(meta, float(r["Duration"]), same)
        labs = {s["normalised"] for s in secs}
        st = {"key": "harmonix", "dataset": "Harmonix Set", "source_id": r["File"],
              "match": {"title": r["Title"], "artist": r["Artist"], "release": r["Release"],
                        "musicbrainz_id": r["MusicBrainz Id"], "same_recording_as_ours": same},
              "source": "Harmonix Set, dataset/segments/%s.txt (Nieto et al. 2019)" % r["File"],
              "url": HX_RAW + "segments/%s.txt" % r["File"], "licence": LICENCE["harmonix"],
              "retrieved": TODAY, "confidence": "expert", "annotated_duration": float(r["Duration"]),
              "bpm": float(r["BPM"]), "time_signature": r["Time Signature"].replace("|", "/"),
              "version_check": vcheck, "sections": secs,
              "bridge": "yes" if "bridge" in labs else "no",
              "bridge_basis": "a segment labelled 'bridge'" if "bridge" in labs else "no segment labelled 'bridge'"}
        if vnote:
            st["version_note"] = vnote
            st["bridge"] = st["bridge"] if st["bridge"] == "yes" else "unknown"
            if st["bridge"] == "unknown":
                st["bridge_basis"] += "; annotated audio is a shorter edit, so a bridge may have been cut"
        out.append((st, None))
    return out


# ---- Rolling Stone corpus ---------------------------------------------------
def rs_list():
    rows = []
    for line in rd(os.path.join(E, "rs/rs200.txt")).splitlines():
        p = line.split("\t")
        if len(p) >= 5:
            rows.append({"file": p[0], "rank": p[1], "title": p[2], "artist": p[3], "year": p[4]})
    return rows


def rs_audio_sources():
    out = {}
    for line in rd(os.path.join(E, "rs/audio_sources.txt")).splitlines():
        p = line.split("\t")
        if len(p) >= 3:
            out[p[0]] = {"artist": p[1], "album": p[2], "publication": p[3].strip() if len(p) > 3 else ""}
    return out


def rs_rules(text):
    rules = {}
    for line in text.splitlines():
        line = line.split("%")[0].strip()
        if ":" not in line:
            continue
        lhs, rhs = line.split(":", 1)
        rules[lhs.strip()] = rhs.split()
    return rules


def rs_measures(rules, sym, depth=0):
    """Count measures produced by a nonterminal (following the expander's syntax)."""
    n = 0
    for tok in rules[sym]:
        m = re.match(r"^\$(.+?)(?:\*(\d+))?$", tok)
        if m:
            n += rs_measures(rules, m.group(1), depth + 1) * int(m.group(2) or 1)
            continue
        m = re.match(r"^\|(?:\*(\d+))?$", tok)
        if m:
            n += int(m.group(1) or 1)
            continue
        # chord / R / . / [key] / [meter] tokens do not count on their own
    return n


def rs_sections(rules):
    """Top-level sections of S: [(label, first_measure, n_measures)]. A nonterminal whose
    rule holds only other nonterminals of two or more kinds (e.g. Zz: $Vr $Ch) is a grouping
    and is opened; repeats (*n) of one section become one span."""
    out = []

    def walk(sym, start):
        pos = start
        for tok in rules[sym]:
            m = re.match(r"^\$(.+?)(?:\*(\d+))?$", tok)
            if m:
                name, rep = m.group(1), int(m.group(2) or 1)
                body = rules[name]
                nts = {re.match(r"^\$(.+?)(?:\*\d+)?$", t).group(1) for t in body if t.startswith("$")}
                only_nts = all(t.startswith("$") or t.startswith("[") for t in body)
                if only_nts and len(nts) >= 2 and H.normalise_label(name, rs=True) == "other":
                    for _ in range(rep):
                        pos = walk(name, pos)
                else:
                    n = rs_measures(rules, name) * rep
                    out.append((name, pos, n))
                    pos += n
                continue
            m = re.match(r"^\|(?:\*(\d+))?$", tok)
            if m and sym == "S":
                k = int(m.group(1) or 1)
                if out and out[-1][0] == "" and out[-1][1] + out[-1][2] == pos:
                    out[-1] = ("", out[-1][1], out[-1][2] + k)
                else:
                    out.append(("", pos, k))
                pos += k
            elif m:
                pos += int(m.group(1) or 1)
        return pos

    total = walk("S", 0)
    return out, total


def rs_timing(path):
    t = {}
    for line in rd(path).splitlines():
        p = line.split()
        if len(p) >= 2:
            t[int(float(p[1]))] = float(p[0])
    return t


def rs_clt(path):
    out = []
    for line in rd(path).splitlines():
        p = line.split()
        if len(p) >= 7:
            out.append({"time": float(p[0]), "measure": float(p[1]), "rn": p[2], "rel_root": int(p[3]),
                        "key_pc": int(p[5]), "abs_root": int(p[6])})
    return out


def rs_written(rn, abs_root, flats):
    """Plain chord name from an RS numeral and its absolute root (derived by us)."""
    m = re.match(r"^([b#]?)([ivIV]+)([^/]*)(/.*)?$", rn)
    if not m:
        return rn
    num, q = m.group(2), m.group(3)
    minor = num.islower()
    name = H.note_name(abs_root, flats)
    if q.startswith("o") or q.startswith("x"):
        return name + "dim" + ("7" if "7" in q else "")
    if q.startswith("h"):
        return name + "m7b5"
    if q.startswith("a"):
        return name + "aug"
    suffix = ""
    if "d7" in q or (num.upper() == "V" and q.startswith("7")):
        suffix = "7"
    elif q.startswith("7"):
        suffix = "m7" if minor else "maj7"
        minor = False
    elif q.startswith("s4") or q.startswith("s"):
        suffix = "sus4"
    elif q.startswith("9"):
        suffix = "9"
    elif re.match(r"^(65|43|42)", q):
        suffix = "7"
    return name + ("m" if minor else "") + suffix


def rs_sources(song, meta):
    out = []
    aud = rs_audio_sources()
    for r in rs_list():
        if title_key(r["title"]) != title_key(song["title"]) or not artist_ok(song["artist"], r["artist"]):
            continue
        tim_path = os.path.join(E, "rs/x_timing/timing_data/%s.tim" % r["file"])
        timing = rs_timing(tim_path) if os.path.exists(tim_path) else {}
        last_t = max(timing.values()) if timing else None
        a = aud.get(r["file"], {})
        # the last barline falls before the end of the audio (fade-outs, final chord), so allow
        # up to 30 s short; a last barline later than our recording ends means a longer version
        vnote, vcheck = None, "duration not comparable (missing length)"
        if last_t and meta["length"]:
            gap = last_t - meta["length"]
            vcheck = "last barline at %.0f s; our recording %.0f s" % (last_t, meta["length"])
            if gap > VERSION_TOLERANCE or gap < -30:
                vnote = ("annotated audio runs to %.0f s vs %.0f s for our recording (%s): a different "
                         "version; section times do not line up with the charting recording"
                         % (last_t, meta["length"], a.get("album") or "album unknown"))
        for analyst in ("dt", "tdc"):
            har = os.path.join(E, "rs/x_harmony/rs200_harmony/%s_%s.har" % (r["file"], analyst))
            clt = os.path.join(E, "rs/x_clt/rs200_harmony_clt/%s_%s.clt" % (r["file"], analyst))
            if not os.path.exists(har):
                continue
            rules = rs_rules(rd(har))
            secs, total = rs_sections(rules)
            chords = rs_clt(clt) if os.path.exists(clt) else []
            last_measure = int(max(c["measure"] for c in chords)) if chords else None
            m0 = re.search(r"\[([A-G][#b]?)\]", " ".join(rules["S"]))
            tonic = m0.group(1) if m0 else None

            def tm(measure):
                if measure in timing:
                    return round(timing[measure], 3)
                ks = sorted(timing)
                if not ks:
                    return None
                if measure < ks[0] and len(ks) > 1:  # pickup bar before the first timed barline
                    step = timing[ks[1]] - timing[ks[0]]
                    return round(max(0.0, timing[ks[0]] - step * (ks[0] - measure)), 3)
                if measure > ks[-1] and len(ks) > 1:  # extrapolate the last bar length
                    step = timing[ks[-1]] - timing[ks[-2]]
                    return round(timing[ks[-1]] + step * (measure - ks[-1]), 3)
                return None

            sections, csecs = [], []
            for name, start, n in secs:
                lab = name
                norm_l = H.normalise_label(lab, rs=True) if lab else "other"
                sec = {"start": tm(start), "end": tm(start + n), "label": lab or "(unnamed bars in S)",
                       "normalised": norm_l, "first_bar": start, "bars": n}
                sections.append(sec)
                in_sec = [c for c in chords if start <= c["measure"] < start + n]
                # a chord sounding from the previous section carries over
                prev = [c for c in chords if c["measure"] < start]
                if prev and (not in_sec or in_sec[0]["measure"] > start):
                    in_sec = [prev[-1]] + in_sec
                keys = [H.key_name(c["key_pc"]).split()[0] for c in in_sec]
                wr = [rs_written(c["rn"], c["abs_root"], H.key_name(c["key_pc"]).split()[0] in H.FLAT_KEYS) for c in in_sec]
                rn = [c["rn"] for c in in_sec]
                pairs = H.collapse(list(zip(wr, rn, keys)))
                csecs.append({"label": sec["label"], "normalised": norm_l, "start": sec["start"], "end": sec["end"],
                              "bars": n, "key": " -> ".join(H.collapse([k for _, _, k in pairs])) if pairs else tonic,
                              "written": [w for w, _, _ in pairs], "roman": [x for _, x, _ in pairs],
                              "raw_rule": " ".join(rules.get(name, [])) if name else None})
            labs = {s["normalised"] for s in sections}
            check = "expanded %d bars; timed chord list ends in bar %s" % (total, last_measure)
            base = {"key": "rolling_stone_" + analyst, "dataset": "Rolling Stone corpus (RS 200)",
                    "analyst": {"dt": "David Temperley", "tdc": "Trevor de Clercq"}[analyst],
                    "source_id": "%s_%s" % (r["file"], analyst),
                    "match": {"title": r["title"], "artist": r["artist"], "year": r["year"], "rs500_rank": r["rank"],
                              "audio_used": a},
                    "source": "de Clercq & Temperley rock corpus v2.1, %s_%s.har/.clt + %s.tim" % (r["file"], analyst, r["file"]),
                    "url": "https://rockcorpus.midside.com/harmonic_analyses.html", "licence": LICENCE["rolling_stone"],
                    "retrieved": TODAY, "confidence": "expert", "version_check": vcheck,
                    "parse_check": check}
            if vnote:
                base["version_note"] = vnote
            if a.get("album") and re.search(r"(?i)greatest|hits|best of", a["album"]):
                base["version_check"] += "; audio taken from compilation '%s'" % a["album"]
            st = dict(base, sections=sections,
                      bridge="yes" if "bridge" in labs else "no",
                      bridge_basis=("a section the analyst named Br (bridge)" if "bridge" in labs else
                                    "no section the analyst named Br; RS form names are informal shorthand"),
                      label_note="Labels are the analyst's rule names (Vr verse, Ch chorus, Br bridge, In intro, "
                                 "Ou outro, Rf refrain ...); bar spans from our expansion of the raw rules, "
                                 "times from the corpus bar timings")
            ch = dict(base, key_info={"tonic": tonic, "tonic_pc": H.pc(tonic), "mode": None, "name": tonic,
                                      "basis": "annotated key symbol (RS marks tonic only; numerals show mode)",
                                      "confidence": "expert"},
                      sections=csecs,
                      chord_syntax="Roman numerals as analysed (RS notation, e.g. V7/V applied, Vs4 suspended); "
                                   "'written' names derived by us from the numeral and its absolute root")
            out.append((st, ch))
    return out


# ---- Isophonics ---------------------------------------------------------------
def isophonics_sources(song, meta):
    out = []
    base_dir = os.path.join(E, "isophonics/x_beatles")
    if not artist_ok(song["artist"], "The Beatles"):
        return out
    for path in glob.glob(os.path.join(base_dir, "seglab/The Beatles/*/*.lab")):
        name = os.path.basename(path)[:-4]
        title = re.sub(r"^(CD\d_-_)?\d+_-_", "", name).replace("_", " ")
        if title_key(title) != title_key(song["title"]):
            continue
        rel = os.path.relpath(path, os.path.join(base_dir, "seglab"))
        segs = []
        for line in rd(path).splitlines():
            p = line.split(None, 2)
            if len(p) == 3:
                lab = p[2].strip()
                if lab.lower() in ("silence", "end"):
                    continue
                segs.append({"start": float(p[0]), "end": float(p[1]), "label": lab,
                             "normalised": H.normalise_label(re.sub(r"_?\(.*\)|_\d+$", "", lab))})
        labs = {s["normalised"] for s in segs}
        base = {"key": "isophonics", "dataset": "Isophonics Beatles reference annotations", "source_id": rel,
                "source": "Isophonics, The Beatles annotations, %s" % rel, "licence": LICENCE["isophonics"],
                "url": FILES["isophonics/The_Beatles_Annotations.tar.gz"], "retrieved": TODAY, "confidence": "expert"}
        st = dict(base, sections=segs, bridge="yes" if "bridge" in labs else "no",
                  bridge_basis="segment labelled bridge" if "bridge" in labs else "no segment labelled bridge")
        chordlab = os.path.join(base_dir, "chordlab", rel)
        keylab = os.path.join(base_dir, "keylab", rel)
        ch = None
        if os.path.exists(chordlab):
            keys = []
            if os.path.exists(keylab):
                for line in rd(keylab).splitlines():
                    p = line.split()
                    if len(p) >= 4 and p[2] == "Key":
                        keys.append((float(p[0]), float(p[1]), p[3]))
            def key_at(t):
                for a, b, k in keys:
                    if a <= t < b:
                        return k.split(":")[0]
                return keys[0][2].split(":")[0] if keys else None
            cl = [(float(p[0]), float(p[1]), p[2]) for p in (l.split() for l in rd(chordlab).splitlines()) if len(p) >= 3]
            csecs = []
            for s in segs:
                inn = [(c, key_at(a)) for a, b, c in cl if s["start"] <= a < s["end"]]
                inn = H.collapse(inn)
                csecs.append({"label": s["label"], "normalised": s["normalised"], "start": s["start"], "end": s["end"],
                              "key": " -> ".join(H.collapse([k for _, k in inn if k])),
                              "written": [H.written(H.parse_harte(c)) for c, _ in inn],
                              "roman": [H.roman(H.parse_harte(c), H.pc(k) if k else None) for c, k in inn]})
            k0 = keys[0][2] if keys else None
            ch = dict(base, key_info={"tonic": k0.split(":")[0] if k0 else None, "tonic_pc": H.pc(k0.split(":")[0]) if k0 else None,
                                      "mode": ("minor" if k0 and ":min" in k0 else "major") if k0 else None,
                                      "name": k0, "basis": "annotated key (keylab)", "confidence": "expert"},
                      sections=csecs, chord_syntax="Harte")
        out.append((st, ch))
    return out


# ---- writing ------------------------------------------------------------------
STRUCT_NOTE = ("Sections per source. 'label' is the source's own label; 'normalised' maps it to "
               "intro/verse/prechorus/chorus/bridge/solo/instrumental/outro/other (mapping in docs/schema.md). "
               "Times in seconds from the start of the audio the annotators used.")
CHORD_NOTE = ("Chord changes per section (repeats of the same chord merged). 'written' as chord names, "
              "'roman' relative to the key tonic (upper case major, lower case minor, b/# chromatic roots).")


def merge_write(sid, kind, new_sources, managed_prefixes):
    """Replace this tool's sources in songs/<id>/<kind>.json, keep other tools' sources."""
    path = os.path.join(SONGS, sid, kind + ".json")
    cur = read_json(path) or {"id": sid, "sources": []}
    keep = [s for s in cur.get("sources", []) if not s["key"].startswith(managed_prefixes)]
    cur["sources"] = new_sources + keep
    cur["note"] = STRUCT_NOTE if kind == "structure" else CHORD_NOTE
    cur["updated"] = TODAY
    return cur


def finalise(sid):
    """Recompute the comparison blocks and the .none markers for one song."""
    sp = os.path.join(SONGS, sid, "structure.json")
    cp = os.path.join(SONGS, sid, "chords.json")
    st, ch = read_json(sp), read_json(cp)
    st = st if st and st.get("sources") else None
    ch = ch if ch and ch.get("sources") else None
    sc, cc = H.compare(st, ch, TODAY)
    for obj, cmp_, path, kind in ((st, sc, sp, "structure"), (ch, cc, cp, "chords")):
        none = os.path.join(SONGS, sid, kind + ".none")
        if obj:
            order = {"expert": 0, "sourced": 1, "crowd": 2}
            obj["sources"].sort(key=lambda x: order.get(x["confidence"], 3))
            obj["comparison"] = cmp_ if cmp_ else "only one source"
            obj = {k: obj[k] for k in ["id", "updated", "note", "sources", "comparison"] if k in obj}
            write_json(path, obj)
            if os.path.exists(none):
                os.remove(none)
        else:
            if os.path.exists(path):
                os.remove(path)
            open(none, "w").close()


MANAGED = ("mcgill_billboard", "harmonix", "rolling_stone", "isophonics")


def main():
    download()
    index = {}
    for s in load_songs():
        meta = song_meta(s)
        found = []
        for fn in (mcgill_sources, harmonix_sources, rs_sources, isophonics_sources):
            found += fn(s, meta)
        sts = [x for x, _ in found if x]
        chs = [y for _, y in found if y]
        st = merge_write(s["id"], "structure", sts, MANAGED)
        ch = merge_write(s["id"], "chords", chs, MANAGED)
        write_json(os.path.join(SONGS, s["id"], "structure.json"), st)
        write_json(os.path.join(SONGS, s["id"], "chords.json"), ch)
        finalise(s["id"])
        index[s["id"]] = sorted({x["key"] for x in sts})
        print(s["id"], index[s["id"]])
    counts = {k: sum(1 for v in index.values() if any(x.startswith(k) for x in v)) for k in MANAGED}
    write_json(os.path.join(ROOT, "reference", "expert-sets.json"), {
        "retrieved": TODAY, "songs": len(index), "matched_per_source": counts, "by_song": index,
        "sources": {k: {"licence": LICENCE[k]} for k in LICENCE},
        "downloads": FILES,
        "notes": {
            "mcgill_billboard": "DDMAL project page returns 404; files fetched from the Dropbox links used by mirdata "
                                "(index CSV + salami_chords). Covers sampled Hot 100 entries 1958-1991.",
            "harmonix": "Annotations of the audio Harmonix used (often game or compilation edits); durations compared.",
            "rolling_stone": "Two independent analysts (dt, tdc) kept as separate sources.",
            "isophonics": "Beatles annotations cover the 12 UK studio albums plus Magical Mystery Tour; "
                          "non-album singles such as 'I Want to Hold Your Hand' are not included.",
        }})
    print(counts)


if __name__ == "__main__":
    main()
