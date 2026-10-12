"""Billboard Hot 100 chart run for each song, from the weekly history compiled by
utdata/rwd-billboard-data (scraped from billboard.com). Writes songs/<id>/charts.json."""
import csv, os, re
from common import *

URL = "https://raw.githubusercontent.com/utdata/rwd-billboard-data/main/data-out/hot-100-current.csv"
PATH = os.path.join(ROOT, "_cache", "hot100.csv")


def first_artist(a):
    a = norm(re.split(r" featuring | feat\. | and Friends| \(|, | & | and ", a)[0])
    return a[3:] if a.startswith("the") and len(a) > 6 else a


def tkeys(title):
    """Comparable forms of a title: whole, without brackets, bracket content, 'part' as 'pt'."""
    t = title.replace("Part ", "Pt ").replace("Pt. ", "Pt ")
    out = {norm(t), norm(re.sub(r"\(.*?\)", "", t))}
    out |= {norm(b) for b in re.findall(r"\((.*?)\)", t) if len(norm(b)) > 4}
    return {k for k in out if k}


def main():
    if not os.path.exists(PATH):
        with open(PATH, "wb") as f:
            f.write(fetch(URL, binary=True, cache=False))
    weeks = {}
    for r in csv.DictReader(open(PATH)):
        # double A-sides chart as "A/B" (in either order); index under every part
        for part in r["title"].split("/"):
            for tk in tkeys(part):
                weeks.setdefault((tk, norm(r["performer"])), []).append(r)
    for s in load_songs():
        t, a = norm(s["title"]), first_artist(s["artist"])
        if s["id"].startswith("1986-thats-what"):
            a = "dionne"
        keys = [k for k in weeks if k[0] == t and (a in k[1] or (len(k[1]) > 4 and k[1] in a))]
        full = norm(s["artist"])
        exact = [k for k in keys if k[1] in (a, full, "the" + a)]
        keys = exact or keys  # don't merge in a novelty re-recording by "X, Mickey, Minnie and Goofy"
        how = "exact title, artist contained"
        if not keys:
            # fallback: title variant (brackets, parts, slashes, censored words) charting in the
            # chart year or the year before; artist must share its first 4 letters or the title must be unique
            y = int(s["chart_year"])
            t2 = norm(re.sub(r"\(.*?\)", "", s["title"]))
            mine = tkeys(s["title"])
            def close(k):
                return k[0] in mine or (len(t2) > 5 and len(k[0]) > 5 and (k[0].startswith(t2) or t2.startswith(k[0]))) \
                    or (len(t2) > 8 and t2 in k[0])
            cands = [k for k in weeks if close(k)
                     and any(r["chart_week"][:4] in (str(y), str(y - 1)) for r in weeks[k])]
            same = [k for k in cands if a[:4] in k[1]]
            keys = same or (cands if len({k[1] for k in cands}) == 1 else [])
            how = "title variant (%s)" % ", ".join("%s / %s" % k for k in keys)
        if not keys:
            print("NO MATCH", s["id"]); open(song_dir(s["id"], "charts.none"), "w").close(); continue
        uniq = {}
        for k in keys:
            for r in weeks[k]:
                uniq[(r["chart_week"], r["performer"], r["title"])] = r
        best = {}
        for r in uniq.values():  # two versions charting in the same week: keep the higher one
            if r["chart_week"] not in best or int(r["current_week"]) < int(best[r["chart_week"]]["current_week"]):
                best[r["chart_week"]] = r
        run = sorted(best.values(), key=lambda r: r["chart_week"])
        pos = [int(r["current_week"]) for r in run]
        peak = min(pos)
        out = {"chart": "Billboard Hot 100", "performer_as_charted": sorted({r["performer"] for r in run}),
               "title_as_charted": sorted({r["title"] for r in run}),
               "debut_week": run[0]["chart_week"], "debut_position": pos[0],
               "peak_position": peak, "weeks_at_peak": pos.count(peak),
               "first_week_at_peak": run[pos.index(peak)]["chart_week"],
               "weeks_to_peak": pos.index(peak), "weeks_on_chart": len(run),
               "last_week": run[-1]["chart_week"], "weeks_at_number_one": pos.count(1),
               "chart_entries": len({r["chart_week"][:4] for r in run}) if False else None,
               "run": [[r["chart_week"], int(r["current_week"])] for r in run],
               "source": URL, "source_note": "Weekly Hot 100 history compiled from billboard.com by the "
               "University of Texas data-reporting course (utdata/rwd-billboard-data)",
               "retrieved": TODAY, "confidence": "sourced", "match": how}
        del out["chart_entries"]
        write_json(song_dir(s["id"], "charts.json"), out)
        print(s["chart_year"], s["title"][:30], "debut", out["debut_position"], "peak", peak,
              "wks", out["weeks_on_chart"], "#1 wks", out["weeks_at_number_one"], keys)


if __name__ == "__main__":
    main()
