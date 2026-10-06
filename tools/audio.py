"""Audio layer: find each song's 30-second preview (Deezer by ISRC, then Deezer search,
then iTunes), analyse it, and keep only the measurements in songs/<id>/audio.json.

Previews are downloaded to _cache/previews/ (gitignored) and never leave it.

Usage (from repo root):  PYTHONPATH=tools python3 tools/audio.py [song-id ...]
"""
import json, os, re, subprocess, sys, unicodedata, urllib.parse
import numpy as np

from common import (ROOT, SONGS, TODAY, fetch, fetch_json, load_songs, norm, read_json,
                    write_json)

PREVIEWS = os.path.join(ROOT, "_cache", "previews")
BAD_VERSION = re.compile(r"\b(live|remix|mix\)|karaoke|instrumental|cover|tribute|acoustic|"
                         r"re-?recorded|rerecorded|demo|orchestral|cover|made famous|"
                         r"originally performed|in the style of|sped up|slowed|"
                         r"medley|a cappella|unplugged|in concert|on stage|version\))", re.I)
DUR_TOL = 5.0


def facts(sid):
    return read_json(os.path.join(SONGS, sid, "facts.json")) or {}


def title_ok(cand, title):
    c, t = norm(cand), norm(title)
    return bool(c) and (c == t or c.startswith(t) and len(c) - len(t) <= 4)


def _words(x):
    x = unicodedata.normalize("NFKD", x or "").encode("ascii", "ignore").decode().lower()
    x = re.sub(r"[^a-z0-9& ]+", " ", x.replace("'", ""))
    x = re.sub(r"\s+", " ", x.replace("&", " and ")).strip()
    return x[4:] if x.startswith("the ") else x


SEP = r",| & | and | featuring | feat\.? | ft\.? | with | x |\(|\)"


def artist_ok(cand, song):
    """Candidate artist must be the credited artist or one named member of the credit, optionally
    followed by a featuring/and clause. Containing the name is not enough: 'Hello I'm Adele' and
    'Adele Tribute Band' are not Adele."""
    c = _words(cand)
    credit = song["artist"]
    parts = {_words(p) for p in [credit] + re.split(SEP, credit) if _words(p)}
    if not c:
        return False
    for p in parts:
        if c == p:
            return True
        if c.startswith(p + " ") and re.match(r"(feat|featuring|ft|and|with|x)\b", c[len(p) + 1:]):
            return True
    return False


def ref_match(dur, refs):
    """First reference length (in priority order) within tolerance: (rank, diff, label) or None."""
    for i, (sec, label) in enumerate(refs):
        if abs(dur - sec) <= DUR_TOL:
            return (i, round(abs(dur - sec), 1), "%s (%.0fs)" % (label, sec))
    return None


OK_VERSION = re.compile(r"\b(single|mono|stereo|album|original|7\"?|45|lp)\s+(version|mix|edit)\b|"
                        r"\bremaster(ed)?\b", re.I)


def clean_version(text):
    """False for live, remix, re-recorded, karaoke etc. Single/mono/album versions and
    remasters are the same recording and pass."""
    return not BAD_VERSION.search(OK_VERSION.sub(" ", text or ""))


def deezer_by_isrc(isrcs, song, ref):
    hits = []
    for isrc in isrcs:
        d = fetch_json("https://api.deezer.com/track/isrc:" + isrc)
        if not d or "error" in d or not d.get("id"):
            continue
        name = d.get("title", "")
        art = (d.get("artist") or {}).get("name", "")
        if not (title_ok(d.get("title_short") or name, song["title"]) and artist_ok(art, song)):
            hits.append(("rejected", isrc, d, "title/artist mismatch: %s / %s" % (name, art)))
            continue
        if not clean_version(name + " " + (d.get("title_version") or "")):
            hits.append(("rejected", isrc, d, "version: %s" % name))
            continue
        hits.append(("ok", isrc, d, ""))
    hits += [("rejected", h[1], h[2], "matched but no preview available (readable=%s)" % h[2].get("readable"))
             for h in hits if h[0] == "ok" and not h[2].get("preview")]
    ok = [h for h in hits if h[0] == "ok" and h[2].get("preview")]
    if ref:
        ok.sort(key=lambda h: abs(h[2]["duration"] - ref))
    return (ok[0] if ok else None), [h for h in hits if h[0] == "rejected"]


def deezer_search(song, refs):
    title = re.sub(r"\(.*?\)", "", song["title"]).strip() or song["title"]
    main = song["artist"].split(" featuring ")[0].split(" feat")[0]
    q = "%s %s" % (main, title)  # Deezer's advanced artist:/track: syntax returns nothing here
    r = fetch_json("https://api.deezer.com/search?q=" + urllib.parse.quote(q) + "&limit=50") or {}
    rejected = []
    best = None
    for d in r.get("data", []):
        name = d.get("title", "")
        art = (d.get("artist") or {}).get("name", "")
        if not (title_ok(d.get("title_short") or name, song["title"]) and artist_ok(art, song)):
            continue
        if not clean_version(name + " " + (d.get("title_version") or "") + " " +
                             ((d.get("album") or {}).get("title") or "")):
            rejected.append("deezer %s: version (%s)" % (d["id"], name))
            continue
        if not d.get("preview"):
            continue
        rm = ref_match(d["duration"], refs) if refs else (0, 0, "no reference length")
        if not rm:
            rejected.append("deezer %s: duration %ss matches no reference length" % (d["id"], d["duration"]))
            continue
        if best is None or rm[:2] < best[0][:2]:
            best = (rm, d)
    if best:
        best[1]["_duration_match"] = best[0][2]
    return (best[1] if best else None), rejected


def itunes_search(song, refs):
    title = re.sub(r"\(.*?\)", "", song["title"]).strip() or song["title"]
    main = song["artist"].split(" featuring ")[0].split(" feat")[0]
    r = fetch_json("https://itunes.apple.com/search?" + urllib.parse.urlencode(
        {"term": "%s %s" % (main, title), "entity": "song", "limit": 50, "country": "US"})) or {}
    best, rejected = None, []
    for d in r.get("results", []):
        if not (title_ok(d.get("trackName", ""), song["title"]) and artist_ok(d.get("artistName", ""), song)):
            continue
        if not clean_version(d.get("trackName", "") + " " + d.get("collectionName", "")):
            rejected.append("itunes %s: version (%s)" % (d.get("trackId"), d.get("trackName")))
            continue
        if not d.get("previewUrl"):
            continue
        dur = (d.get("trackTimeMillis") or 0) / 1000
        rm = ref_match(dur, refs) if refs else (0, 0, "no reference length")
        if not rm:
            rejected.append("itunes %s: duration %.0fs matches no reference length" % (d.get("trackId"), dur))
            continue
        if best is None or rm[:2] < best[0][:2]:
            best = (rm, d)
    if best:
        best[1]["_duration_match"] = best[0][2]
    return (best[1] if best else None), rejected


def download(url, path, refresh=None):
    if os.path.exists(path) and os.path.getsize(path) > 10000:
        return True
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for attempt in range(2):
        try:
            data = fetch(url, binary=True, cache=False)
        except Exception:
            data = None
        if data and len(data) > 10000:
            with open(path, "wb") as f:
                f.write(data)
            return True
        if refresh:
            url = refresh() or url
    return False


def decode(path, sr, channels):
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", str(channels),
                          "-ar", str(sr), "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(out, dtype=np.float32)
    return x.reshape(-1, channels).T if channels > 1 else x


# ---------- analysis ----------

KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
PITCH = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def key_estimate(chroma_mean):
    scores = []
    for i in range(12):
        for mode, prof in (("major", KS_MAJOR), ("minor", KS_MINOR)):
            r = float(np.corrcoef(chroma_mean, np.roll(prof, i))[0, 1])
            scores.append((r, PITCH[i], mode))
    scores.sort(reverse=True)
    return scores


def k_weight(x, sr=48000):
    """ITU-R BS.1770 K-weighting (coefficients for 48 kHz)."""
    from scipy.signal import lfilter
    b1 = [1.53512485958697, -2.69169618940638, 1.19839281085285]
    a1 = [1.0, -1.69065929318241, 0.73248077421585]
    b2 = [1.0, -2.0, 1.0]
    a2 = [1.0, -1.99004745483398, 0.99007225036621]
    return lfilter(b2, a2, lfilter(b1, a1, x, axis=-1), axis=-1)


def integrated_lufs(stereo, sr=48000):
    y = k_weight(stereo, sr)
    block, hop = int(0.4 * sr), int(0.1 * sr)
    zs = []
    for s in range(0, y.shape[-1] - block + 1, hop):
        zs.append(np.mean(y[:, s:s + block] ** 2, axis=-1).sum())
    zs = np.array(zs)
    lk = -0.691 + 10 * np.log10(np.maximum(zs, 1e-12))
    g = zs[lk > -70]
    if not len(g):
        return None
    rel = -0.691 + 10 * np.log10(g.mean()) - 10
    g2 = zs[(lk > -70) & (lk > rel)]
    return float(-0.691 + 10 * np.log10(g2.mean()))


def analyse(path):
    import librosa
    sr = 22050
    y = decode(path, sr, 1).astype(np.float32)
    dur = len(y) / sr
    hop = 128  # finer than the default 512, so tempo is not snapped to coarse lag bins
    tempo_grid, beats = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop)
    tempo_grid = float(np.atleast_1d(tempo_grid)[0])
    bt = librosa.frames_to_time(beats, sr=sr, hop_length=hop)
    tempo = tempo_grid
    if len(bt) >= 8:
        # beat period from a straight-line fit of beat times against beat number
        slope = np.polyfit(np.arange(len(bt)), bt, 1)[0]
        if slope > 0 and abs(60 / slope - tempo_grid) / tempo_grid < 0.08:
            tempo = 60 / slope
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    # tempo candidates from the tempogram, to spot double/half-time ambiguity
    tg = librosa.feature.tempogram(onset_envelope=onset_env, sr=sr)
    bpms = librosa.tempo_frequencies(tg.shape[0], sr=sr)
    prof = tg.mean(axis=1)
    cands = []
    for i in np.argsort(prof)[::-1]:
        b = bpms[i]
        if 40 <= b <= 240 and all(abs(b - c) / c > 0.04 for c in cands):
            cands.append(float(b))
        if len(cands) == 3:
            break
    onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, units="time")
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    scores = key_estimate(chroma.mean(axis=1))
    cent = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    rms = librosa.feature.rms(y=y)[0]
    stereo = decode(path, 48000, 2).astype(np.float64)
    peak = float(np.max(np.abs(stereo)))
    return {
        "clip_seconds": round(dur, 2),
        "tempo_bpm": round(tempo, 1),
        "tempo_bpm_grid": round(tempo_grid, 1),
        "tempo_candidates_bpm": [round(c, 1) for c in cands],
        "beats_detected": int(len(beats)),
        "key": "%s %s" % (scores[0][1], scores[0][2]),
        "key_tonic": scores[0][1], "key_mode": scores[0][2],
        "key_correlation": round(scores[0][0], 3),
        "key_runner_up": "%s %s" % (scores[1][1], scores[1][2]),
        "key_runner_up_correlation": round(scores[1][0], 3),
        "chroma_profile": [round(float(v), 3) for v in chroma.mean(axis=1) / chroma.mean(axis=1).max()],
        "rms_dbfs": round(float(20 * np.log10(np.sqrt(np.mean(y ** 2)) + 1e-12)), 2),
        "rms_dbfs_p95_frame": round(float(20 * np.log10(np.percentile(rms, 95) + 1e-12)), 2),
        "peak_dbfs": round(float(20 * np.log10(peak + 1e-12)), 2),
        "loudness_lufs_approx": (lambda v: round(v, 2) if v is not None else None)(integrated_lufs(stereo)),
        "spectral_centroid_hz_mean": round(float(cent.mean()), 1),
        "spectral_centroid_hz_median": round(float(np.median(cent)), 1),
        "onsets": int(len(onsets)),
        "onset_density_per_s": round(len(onsets) / dur, 3),
    }


def process(song):
    sid = song["id"]
    out_path = os.path.join(SONGS, sid, "audio.json")
    none_path = os.path.join(SONGS, sid, "audio.none")
    mb = facts(sid).get("musicbrainz") or {}
    ref = (mb.get("length_ms") or 0) / 1000 or None
    from common import ref_lengths
    refs = ref_lengths(sid)
    refs = [r for r in refs if r[1].startswith(("musicbrainz", "wikipedia"))]  # not our own earlier match
    rejected = []
    preview = None
    hit, rej = deezer_by_isrc(mb.get("isrcs") or [], song, ref)
    rejected += ["deezer isrc %s: %s" % (r[1], r[3]) for r in rej]
    if hit:
        _, isrc, d, _ = hit
        preview = {"service": "deezer", "track_id": d["id"], "matched_by": "isrc", "isrc": isrc,
                   "title": d.get("title"), "artist": (d.get("artist") or {}).get("name"),
                   "album": (d.get("album") or {}).get("title"), "track_duration_s": d.get("duration"),
                   "link": d.get("link"), "url": d["preview"], "deezer": d}
        if ref and abs(d["duration"] - ref) > DUR_TOL:
            preview["duration_note"] = ("Deezer track (ISRC match) is %ss; MusicBrainz length is %.0fs. "
                                        "ISRC match kept; one of the two lengths may refer to another edit."
                                        % (d["duration"], ref))
    if not preview:
        d, rej = deezer_search(song, refs)
        rejected += rej
        if d:
            full = fetch_json("https://api.deezer.com/track/%s" % d["id"]) or d
            preview = {"service": "deezer", "track_id": d["id"], "matched_by": "search (artist, title, duration)",
                       "isrc": full.get("isrc"), "title": d.get("title"),
                       "artist": (d.get("artist") or {}).get("name"),
                       "album": (d.get("album") or {}).get("title"), "track_duration_s": d.get("duration"),
                       "link": d.get("link"), "url": d["preview"], "deezer": full,
                       "duration_matched_to": d.get("_duration_match")}
    if not preview:
        d, rej = itunes_search(song, refs)
        rejected += rej
        if d:
            preview = {"service": "itunes", "track_id": d.get("trackId"), "matched_by": "search (artist, title, duration)",
                       "isrc": None, "title": d.get("trackName"), "artist": d.get("artistName"),
                       "album": d.get("collectionName"), "track_duration_s": round((d.get("trackTimeMillis") or 0) / 1000, 1),
                       "link": d.get("trackViewUrl"), "url": d.get("previewUrl"),
                       "duration_matched_to": d.get("_duration_match")}
    if not preview:
        with open(none_path, "w") as f:
            f.write("No matching preview on Deezer or iTunes (%s). Rejected: %s\n" % (TODAY, "; ".join(rejected) or "none"))
        print(sid, "NONE", rejected)
        return
    path = os.path.join(PREVIEWS, "%s.%s-%s.mp3" % (sid, preview["service"], preview["track_id"]))
    refresh = None
    if preview["service"] == "deezer":
        tid = preview["track_id"]
        refresh = lambda: (fetch_json("https://api.deezer.com/track/%s" % tid, cache=False) or {}).get("preview")
    if not download(preview["url"], path, refresh):
        print(sid, "download failed")
        return
    m = analyse(path)
    d = preview.pop("deezer", None) or {}
    preview.pop("url", None)
    deezer_fields = None
    if preview["service"] == "deezer":
        deezer_fields = {"bpm": d.get("bpm") or None, "gain": d.get("gain"),
                         "note": "Deezer's own track metadata; bpm 0 means not set (recorded as null). "
                                 "gain is Deezer's replay-gain style value in dB.",
                         "source": "Deezer API track/%s" % preview["track_id"],
                         "retrieved": TODAY, "confidence": "sourced"}
    flags = []
    if deezer_fields and deezer_fields["bpm"]:
        ratio = m["tempo_bpm"] / deezer_fields["bpm"]
        if abs(ratio - 2) < 0.12 or abs(ratio - 0.5) < 0.03:
            flags.append("tempo is about %s Deezer's bpm (%.1f): octave error likely"
                         % ("double" if ratio > 1 else "half", deezer_fields["bpm"]))
        elif abs(ratio - 1) > 0.04:
            flags.append("tempo differs from Deezer's bpm (%.1f) by %.0f%%" % (deezer_fields["bpm"], abs(ratio - 1) * 100))
    if m["tempo_bpm"] > 160 or m["tempo_bpm"] < 65:
        flags.append("tempo outside 65-160 BPM; may be a double- or half-time reading")
    if m["key_correlation"] - m["key_runner_up_correlation"] < 0.03:
        flags.append("key is close between %s and %s" % (m["key"], m["key_runner_up"]))
    rec = {
        "id": sid,
        "preview": {**preview, "segment_caveat": "30-second preview clip; where in the song it starts is not known, "
                    "so values describe that clip, not the whole recording",
                    "retrieved": TODAY, "source": "%s preview (kept only in _cache, not committed)" % preview["service"]},
        "measures": {**m, "method": "librosa %s: beat_track tempo (hop 128, refined by a line fit through beat times), chroma_cqt + Krumhansl-Schmuckler key profiles, "
                     "RMS, spectral centroid, onset_detect; loudness is BS.1770 K-weighted gated loudness on the "
                     "clip (approximate LUFS, not the full track)" % __import__("librosa").__version__,
                     "source": "computed from %s preview %s" % (preview["service"], preview["track_id"]),
                     "retrieved": TODAY, "confidence": "computed"},
        "deezer_metadata": deezer_fields,
        "flags": flags,
        "rejected_candidates": rejected,
    }
    write_json(out_path, rec)
    if os.path.exists(none_path):
        os.remove(none_path)
    print(sid, preview["service"], preview["matched_by"], m["tempo_bpm"], m["key"], flags)


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
