"""Shared music-theory helpers for the structure and chords layers:
chord parsing, Roman numerals, key estimation, section-label normalisation,
and the cross-source comparison block.

Conventions (also in docs/schema.md):
- Roman numerals are relative to the annotated tonic, whatever the mode, in the
  Rolling Stone corpus style: upper case = major third, lower case = minor third,
  flats/sharps for chromatic roots (so a minor-key song reads i bIII bVI bVII).
  Suffixes: 7, maj7, o (diminished), o7, ø7 (half-diminished), + (augmented),
  sus2/sus4, 5 (power chord), 6, 9, 11, 13. Inversions are dropped from the
  numeral (kept in the written chord).
- Written chords use plain names: A, F#m, E7, Dmaj7, Bdim, G/B.
"""
import re

NOTE_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
DEGREE = ["I", "bII", "II", "bIII", "III", "IV", "#IV", "V", "bVI", "VI", "bVII", "VII"]
FLAT_KEYS = {"F", "Bb", "Eb", "Ab", "Db", "Gb", "Cb", "Dm", "Gm", "Cm", "Fm", "Bbm", "Ebm"}

NORMALISED = ["intro", "verse", "prechorus", "chorus", "bridge", "solo", "instrumental", "outro", "other"]


def pc(name):
    """Pitch class of a note name like 'F#', 'Bb', 'Cs' (Chordonomicon sharp)."""
    m = re.match(r"^([A-Ga-g])((?:#|b|s)*)$", name or "")
    if not m:
        return None
    v = NOTE_PC[m.group(1).upper()]
    for a in m.group(2):
        v += 1 if a in "#s" else -1
    return v % 12


def note_name(p, flats=False):
    return (FLAT_NAMES if flats else SHARP_NAMES)[p % 12]


# ---- chord quality ---------------------------------------------------------
# canonical qualities: (third, suffix for written name, suffix for numeral)
#   third: 'M' major, 'm' minor, 'd' diminished, 'a' augmented, 'n' none
QUALITY = {
    "maj": ("M", "", ""), "": ("M", "", ""), "min": ("m", "m", ""), "m": ("m", "m", ""),
    "7": ("M", "7", "7"), "dom7": ("M", "7", "7"), "maj7": ("M", "maj7", "maj7"),
    "min7": ("m", "m7", "7"), "m7": ("m", "m7", "7"), "dim": ("d", "dim", "o"),
    "dim7": ("d", "dim7", "o7"), "hdim7": ("d", "m7b5", "ø7"), "m7b5": ("d", "m7b5", "ø7"),
    "aug": ("a", "aug", "+"), "sus4": ("n", "sus4", "sus4"), "sus2": ("n", "sus2", "sus2"),
    "sus": ("n", "sus4", "sus4"), "5": ("n", "5", "5"), "1": ("n", "5", "5"),
    "maj6": ("M", "6", "6"), "6": ("M", "6", "6"), "min6": ("m", "m6", "6"), "m6": ("m", "m6", "6"),
    "9": ("M", "9", "9"), "maj9": ("M", "maj9", "maj9"), "min9": ("m", "m9", "9"), "m9": ("m", "m9", "9"),
    "11": ("M", "11", "11"), "min11": ("m", "m11", "11"), "m11": ("m", "m11", "11"),
    "13": ("M", "13", "13"), "min13": ("m", "m13", "13"), "minmaj7": ("m", "mMaj7", "maj7"),
    "add9": ("M", "add9", "add9"), "madd9": ("m", "madd9", "add9"), "7sus4": ("n", "7sus4", "7sus4"),
}
# chord tones relative to root, for key estimation
TONES = {"M": (0, 4, 7), "m": (0, 3, 7), "d": (0, 3, 6), "a": (0, 4, 8), "n": (0, 7)}


def _quality(q):
    q = (q or "").strip()
    if q in QUALITY:
        return QUALITY[q]
    q2 = re.sub(r"\(.*?\)", "", q)
    if q2 in QUALITY:
        return QUALITY[q2]
    # loose fallbacks
    if q2.startswith(("min", "m")) and not q2.startswith("maj"):
        return ("m", "m" + re.sub(r"^(min|m)", "", q2), re.sub(r"^(min|m)", "", q2))
    if q2.startswith("dim"):
        return ("d", "dim", "o")
    if q2.startswith("aug"):
        return ("a", "aug", "+")
    if q2.startswith("sus"):
        return ("n", q2, q2)
    return ("M", q2, q2)


def parse_harte(tok):
    """McGill/Isophonics (Harte) chord 'A:maj', 'E:7', 'D:maj/3', 'N', 'X'.
    Returns dict(root, third, written_suffix, rn_suffix, bass_interval) or None for no-chord."""
    if tok in ("N", "X", "*", "&pause") or not tok:
        return None
    m = re.match(r"^([A-G][#b]*)(?::([^/]*))?(?:/(.+))?$", tok)
    if not m:
        return None
    root = pc(m.group(1))
    third, ws, rs = _quality(m.group(2) if m.group(2) is not None else "maj")
    bass = None
    if m.group(3):
        b = m.group(3)
        deg = {"1": 0, "b2": 1, "2": 2, "b3": 3, "3": 4, "4": 5, "#4": 6, "b5": 6, "5": 7,
               "#5": 8, "b6": 8, "6": 9, "b7": 10, "7": 11}
        bass = deg.get(b)
    return {"root": root, "third": third, "ws": ws, "rs": rs, "bass": bass, "spelled": m.group(1)}


def parse_plain(tok):
    """Chordonomicon-style 'Csmin', 'A/Cs', 'Fs7', 'Bbmaj7', 'Gsus4', 'E5'."""
    m = re.match(r"^([A-G](?:s|b|#)?)([^/]*)(?:/([A-G](?:s|b|#)?))?$", tok or "")
    if not m:
        return None
    root = pc(m.group(1))
    q = m.group(2)
    third, ws, rs = _quality(q)
    bass = None
    if m.group(3):
        bass = (pc(m.group(3)) - root) % 12
    return {"root": root, "third": third, "ws": ws, "rs": rs, "bass": bass,
            "spelled": m.group(1).replace("s", "#")}


def written(ch, flats=False, spelled=True):
    if ch is None:
        return "N"
    r = ch["spelled"] if spelled and ch.get("spelled") else note_name(ch["root"], flats)
    s = r + ch["ws"]
    if ch.get("bass") not in (None, 0):
        s += "/" + note_name(ch["root"] + ch["bass"], flats)
    return s


def roman(ch, tonic):
    """Numeral of a parsed chord relative to tonic pitch class."""
    if ch is None or tonic is None:
        return "N"
    deg = DEGREE[(ch["root"] - tonic) % 12]
    acc, num = re.match(r"^([b#]?)(.*)$", deg).groups()
    if ch["third"] in ("m", "d"):
        num = num.lower()
    return acc + num + ch["rs"]


def chord_tones(ch):
    return [(ch["root"] + t) % 12 for t in TONES.get(ch["third"], (0, 4, 7))]


# ---- key estimation --------------------------------------------------------
# Krumhansl-Kessler profiles
KK_MAJ = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
KK_MIN = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]


def _corr(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
    return num / den if den else 0


def estimate_key(chords):
    """chords: parsed chords (one per chord change; repeats count as weight).
    Builds a pitch-class histogram from chord tones (root double weight),
    plus a bonus for the first and last chord roots, and correlates with
    Krumhansl-Kessler profiles. Returns (tonic_pc, 'major'|'minor', score, runner_up)."""
    hist = [0.0] * 12
    chords = [c for c in chords if c]
    if not chords:
        return None
    for c in chords:
        for i, t in enumerate(chord_tones(c)):
            hist[t] += 2 if i == 0 else 1
    hist[chords[0]["root"]] += 2
    hist[chords[-1]["root"]] += 2
    scores = []
    for t in range(12):
        rot = hist[t:] + hist[:t]
        scores.append((_corr(rot, KK_MAJ), t, "major"))
        scores.append((_corr(rot, KK_MIN), t, "minor"))
    scores.sort(reverse=True)
    best, second = scores[0], scores[1]
    return {"tonic_pc": best[1], "mode": best[2], "score": round(best[0], 3),
            "runner_up": {"tonic_pc": second[1], "mode": second[2], "score": round(second[0], 3)}}


def key_name(tonic_pc, mode=None):
    flats = (note_name(tonic_pc, True) + ("m" if mode == "minor" else "")) in FLAT_KEYS
    n = note_name(tonic_pc, flats)
    return n + (" minor" if mode == "minor" else " major" if mode == "major" else "")


def collapse(seq):
    out = []
    for x in seq:
        if not out or out[-1] != x:
            out.append(x)
    return out


# ---- section label normalisation -------------------------------------------
# Order matters: first match wins. Patterns are matched against the raw label,
# lower-cased, with digits / primes / trailing letters stripped where noted.
LABEL_RULES = [
    (r"^(pre[- ]?chorus|prechorus|pc|pre|pr)\b", "prechorus"),
    (r"^post[- ]?chorus|^postchorus", "chorus"),
    (r"^(pre[- ]?verse|pre[- ]?intro|intro|in|fadein)\b", "intro"),
    (r"^(verse|vr|vs|vp|spoken verse|spoken)\b", "verse"),
    (r"^(chorus|ch|refrain|rf|rfb|cp|hook)\b", "chorus"),
    (r"^(bridge|br|middle ?eight|mid)\b", "bridge"),
    (r"^(solo|so|gs|guitar solo)\b", "solo"),
    (r"^(instrumental|inst|instrumental break|interlude|il|break|brk|theme|main theme|secondary theme|head)\b", "instrumental"),
    (r"^(outro|ou|out|fadeout|fade|coda|co|ending|end)\b", "outro"),
]


RS_PREFIX = [  # Rolling Stone corpus rule names (CamelCase shorthand), checked by prefix
    (("pre", "pc", "pr"), "prechorus"),
    (("ins", "brea", "bk", "break", "il"), "instrumental"),
    (("intr", "in"), "intro"),
    (("v",), "verse"),
    (("ch", "re", "rf", "cp"), "chorus"),
    (("br",), "bridge"),
    (("so",), "solo"),
    (("ou", "fade", "co", "end"), "outro"),
]


def normalise_label(raw, rs=False):
    if rs:
        s = re.sub(r"\d+[a-z]?$", "", (raw or "").strip().lower())
        if len(s) < 2 or s in ("zz", "ta", "tg", "tag", "ln", "link", "bp", "pt", "part", "tr"):
            return "other"
        for prefixes, lab in RS_PREFIX:
            if s.startswith(prefixes):
                return lab
        return "other"
    s = (raw or "").strip().lower()
    s = re.sub(r"[\"'’]+", "", s)
    # Rolling Stone nonterminal names: 'Vr1a' -> 'vr', 'Ch3' -> 'ch', 'Br2' -> 'br'
    s = re.sub(r"^([a-z]+?)\d+[a-z]?$", r"\1", s)
    s = re.sub(r"\s+(a|b|one|two|three|four|five|\d+)$", "", s)
    for pat, lab in LABEL_RULES:
        if re.search(pat, s):
            return lab
    return "other"


# ---- comparison -------------------------------------------------------------
def _lev(a, b):
    d = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, y in enumerate(b, 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (x != y))
            prev, d[j] = d[j], cur
    return d[len(b)]


def form_of(sections):
    return collapse([s["normalised"] for s in sections if s["normalised"] != "other"])


def compare(structure, chords, today):
    """Build comparison blocks from all sources present. Returns (struct_cmp, chord_cmp)."""
    sc = None
    srcs = (structure or {}).get("sources", [])
    if len(srcs) > 1:
        forms = {s["key"]: form_of(s["sections"]) for s in srcs}
        bridges = {s["key"]: s["bridge"] for s in srcs}
        pairs = []
        keys = list(forms)
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                a, b = forms[keys[i]], forms[keys[j]]
                dist = _lev(a, b)
                pairs.append({"a": keys[i], "b": keys[j], "same_order": a == b,
                              "edit_distance": dist,
                              "similarity": round(1 - dist / max(len(a), len(b), 1), 2)})
        known = {v for v in bridges.values() if v in ("yes", "no")}
        expert_known = {s["bridge"] for s in srcs if s["confidence"] == "expert" and s["bridge"] in ("yes", "no")}
        sc = {
            "form_by_source": {k: " ".join(v) for k, v in forms.items()},
            "section_order": pairs,
            "section_order_agree": all(p["same_order"] for p in pairs),
            "bridge_by_source": bridges,
            "bridge_agree": len(known) <= 1,
            "bridge_expert_value": (expert_known.pop() if len(expert_known) == 1 else
                                    "disputed" if expert_known else "unknown"),
            "notes": [s["key"] + ": " + s["version_note"] for s in srcs if s.get("version_note")],
            "method": "Forms are the normalised labels in order with repeats merged and 'other' dropped. "
                      "Edit distance counts inserted, deleted or changed sections.",
            "computed": today, "confidence": "computed",
        }
    cc = None
    csrcs = (chords or {}).get("sources", [])
    if len(csrcs) > 1:
        tonics = {s["key"]: s["key_info"]["tonic_pc"] for s in csrcs}
        names = {s["key"]: s["key_info"]["name"] for s in csrcs}
        expert = [s for s in csrcs if s["confidence"] == "expert"]
        ref = expert[0] if expert else csrcs[0]
        rows = []
        for s in csrcs:
            if s is ref:
                continue
            shift = (s["key_info"]["tonic_pc"] - ref["key_info"]["tonic_pc"]) % 12
            # compare the chord vocabularies in Roman numerals (roots only)
            ra = {re.match(r"^[b#]?[ivIV]+", r).group(0).upper() for r in all_romans(ref) if re.match(r"^[b#]?[ivIV]+", r)}
            rb = {re.match(r"^[b#]?[ivIV]+", r).group(0).upper() for r in all_romans(s) if re.match(r"^[b#]?[ivIV]+", r)}
            jac = round(len(ra & rb) / len(ra | rb), 2) if ra | rb else None
            row = {"reference": ref["key"], "other": s["key"], "same_tonic": shift == 0,
                   "semitones_apart": shift if shift <= 6 else shift - 12,
                   "roman_root_overlap": jac}
            rows.append(row)
        cc = {"key_by_source": names, "key_agree": len(set(tonics.values())) == 1, "pairs": rows,
              "method": "Tonic compared as pitch class (enharmonics equal). roman_root_overlap is the share of "
                        "scale-degree roots (I, IV, bVII ...) used by both sources (Jaccard index), so a "
                        "transposed fan transcription can still agree in Roman numerals.",
              "computed": today, "confidence": "computed"}
    return sc, cc


def all_romans(src):
    out = []
    for sec in src["sections"]:
        out += sec["roman"]
    return out
