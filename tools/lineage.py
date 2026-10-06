"""Lineage from SecondHandSongs: is the charting recording an original or a cover, how often
it has been covered, adaptations (new lyrics / translations), and samples in both directions.
Writes songs/<id>/lineage.json."""
import os, re, urllib.parse
from common import *

API = "https://api.secondhandsongs.com/"


def brief(x):
    out = {"title": x.get("title"), "uri": x.get("uri")}
    if x.get("performer"):
        out["performer"] = x["performer"].get("name")
    return out


def find_performance(song):
    main = re.split(r" featuring | feat\. | and Friends", song["artist"])[0]
    a = norm(re.split(r", | & | and ", main)[0])
    for q in ({"title": song["title"], "performer": main}, {"title": song["title"]}):
        j = fetch_json(API + "search/performance?" + urllib.parse.urlencode(q))
        hits = [p for p in (j or {}).get("resultPage", [])
                if a in norm((p.get("performer") or {}).get("name"))
                and norm(p["title"].split(" / ")[0]) == norm(song["title"])]
        if hits:
            # earliest-numbered entry first is usually the canonical one; prefer originals
            hits.sort(key=lambda p: (not p.get("isOriginal"), int(p["uri"].rsplit("/", 1)[-1])))
            return hits[0]
    return None


def main():
    for s in load_songs():
        if os.path.exists(os.path.join(SONGS, s["id"], "lineage.json")):
            continue
        try:
            hit = find_performance(s)
        except Exception as e:  # SecondHandSongs answers 403 once its anonymous quota is used up
            print("STOPPED at", s["id"], e); return
        if not hit:
            open(song_dir(s["id"], "lineage.none"), "w").close()
            print(s["chart_year"], "no match"); continue
        try:
            p = fetch_json(hit["uri"])
            works = p.get("works", [])
            w = fetch_json(works[0]["uri"]) if works else {}
        except Exception as e:
            print("STOPPED at", s["id"], e); return
        out = {"source": "SecondHandSongs API", "retrieved": TODAY, "confidence": "crowd",
               "performance": {"uri": p["uri"], "title": p["title"], "performer": p["performer"]["name"],
                               "is_original": p.get("isOriginal"), "first_release_date": p.get("firstReleaseDate"),
                               "releases": [brief(r) for r in p.get("releases", [])]},
               "originals": [brief(x) for x in p.get("originals", [])],
               "covers_of_this_recording": len(p.get("covers", [])),
               "samples_used": [brief(x) for x in p.get("usesSamplesFrom", [])],
               "sampled_by": [brief(x) for x in p.get("sampledBy", [])],
               "work": {"uri": w.get("uri"), "title": w.get("title"), "language": w.get("language"),
                        "writers": [c.get("commonName") for c in w.get("credits", [])],
                        "original_performer": ((w.get("original") or {}).get("performer") or {}).get("name"),
                        "versions": len(w.get("versions", [])),
                        "based_on": [brief(x) for x in w.get("basedOn", [])],
                        "derived_works": [brief(x) for x in w.get("derivedWorks", [])]}}
        write_json(song_dir(s["id"], "lineage.json"), out)
        print(s["chart_year"], s["title"][:26], "orig" if p.get("isOriginal") else "COVER of " +
              str(out["work"]["original_performer"]), "| versions", out["work"]["versions"],
              "| derived", len(out["work"]["derived_works"]), "| samples", len(out["samples_used"]),
              "| sampled by", len(out["sampled_by"]), flush=True)


if __name__ == "__main__":
    main()
