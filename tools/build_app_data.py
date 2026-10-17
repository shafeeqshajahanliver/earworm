"""Derived per-song data for the Earworm app (no lyrics text, no images): writes app/data.json."""
import os, re, json, statistics as st
from common import *
from audit import audit

def j(sid, *p): return read_json(os.path.join(SONGS, sid, *p)) or {}

out = []
for s in load_songs():
    sid = s["id"]; a = audit(s)
    lm, au, ch = j(sid, "lyrics", "measures.json"), j(sid, "audio.json"), j(sid, "charts.json")
    cv = j(sid, "cover", "cover.json").get("images", {})
    st_, cd, lin = j(sid, "structure.json"), j(sid, "chords.json"), j(sid, "lineage.json")
    m = au.get("measures") or {}
    bpm = m.get("tempo_bpm"); dz = (au.get("deezer_metadata") or {}).get("bpm")
    if bpm and dz and (abs(bpm * 2 - dz) < dz * .06 or abs(bpm / 2 - dz) < dz * .06): bpm = dz
    img = cv.get("album") if (cv.get("album") or {}).get("measures") else (cv.get("itunes") if (cv.get("itunes") or {}).get("measures") else None)
    cm = (img or {}).get("measures") or {}
    # structure: prefer an expert source with timings
    form, bridge = None, None
    for src in st_.get("sources", []):
        if src.get("sections") and not src["key"].startswith("chordonomicon"):
            form = [[x["normalised"], x.get("start"), x.get("end")] for x in src["sections"] if x["normalised"] != "other"]
            break
    if not form:
        for src in st_.get("sources", []):
            if src.get("sections"):
                form = [[x["normalised"], None, None] for x in src["sections"] if x["normalised"] != "other"]; break
    comp = st_.get("comparison")
    if isinstance(comp, dict): bridge = comp.get("bridge_expert_value") or (comp.get("bridge_by_source") or {}).get("chordonomicon")
    elif st_.get("sources"): bridge = st_["sources"][0].get("bridge")
    # chords: roman numerals across the song, first expert source else crowd
    romans, key, csrc = [], None, None
    srcs = sorted(cd.get("sources", []), key=lambda x: x["key"].startswith("chordonomicon"))
    if srcs:
        c0 = srcs[0]; csrc = c0["key"]; key = (c0.get("key_info") or {}).get("name") or (c0.get("key_info") or {}).get("tonic")
        mode = (c0.get("key_info") or {}).get("mode")
        for sec in c0.get("sections", []):
            romans += [[sec["normalised"], r] for r in sec.get("roman", [])]
    else:
        mode = None
    out.append({
        "id": sid, "t": s["title"], "a": s["artist"], "y": int(s["chart_year"]), "r": int(s["year_end_rank"]),
        "c": s["country"], "reg": s["region"],
        "len": a["length"], "w": len(a["writers"]), "p": len(a["producers"]),
        "pw": bool(set(a["producers"]) & set(a["writers"])),
        "debut": ch.get("debut_position"), "peak": ch.get("peak_position"), "wks": ch.get("weeks_on_chart"),
        "no1": ch.get("weeks_at_number_one"), "topeak": ch.get("weeks_to_peak"),
        "words": lm.get("words"), "rep": lm.get("repeated_line_share"), "fv": lm.get("first_vocal_s"),
        "title_n": lm.get("title_phrase_occurrences"), "wpm": lm.get("words_per_minute_sung"),
        "I": (lm.get("pronouns") or {}).get("first_singular"), "you": (lm.get("pronouns") or {}).get("second"),
        "we": (lm.get("pronouns") or {}).get("first_plural"), "instr": os.path.exists(os.path.join(SONGS, sid, "lyrics.none")),
        "bpm": round(bpm, 1) if bpm else None, "lufs": m.get("loudness_lufs_approx"),
        "bright": cm.get("brightness"), "sat": cm.get("saturation"), "dark": cm.get("dark_share"),
        "pal": [p["hex"] for p in cm.get("palette", [])[:5]], "palw": [p["share"] for p in cm.get("palette", [])[:5]],
        "orig": None if not lin else bool(lin["performance"]["is_original"]),
        "origby": None if not lin or lin["performance"]["is_original"] else lin["work"].get("original_performer"),
        "versions": (lin.get("work") or {}).get("versions") if lin else None,
        "form": form, "bridge": bridge, "key": key, "mode": mode, "csrc": csrc,
        "romans": [r for _, r in romans][:200],
    })
os.makedirs(os.path.join(ROOT, "app"), exist_ok=True)
with open(os.path.join(ROOT, "app", "data.json"), "w") as f:
    json.dump(out, f, separators=(",", ":"), ensure_ascii=False)
print(len(out), os.path.getsize(os.path.join(ROOT, "app", "data.json")))
