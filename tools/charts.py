"""Billboard Hot 100 chart run for each song, from the weekly history compiled by
utdata/rwd-billboard-data (scraped from billboard.com). Writes songs/<id>/charts.json."""
import csv, os, re
from common import *

URL = "https://raw.githubusercontent.com/utdata/rwd-billboard-data/main/data-out/hot-100-current.csv"
PATH = os.path.join(ROOT, "_cache", "hot100.csv")


def first_artist(a):
    return norm(re.split(r" featuring | feat\. | and Friends| \(|, | & | and ", a)[0])


def main():
    if not os.path.exists(PATH):
        with open(PATH, "wb") as f:
            f.write(fetch(URL, binary=True, cache=False))
    weeks = {}
    for r in csv.DictReader(open(PATH)):
        # double A-sides chart as "A/B"; index under the first title
        weeks.setdefault((norm(r["title"].split("/")[0]), norm(r["performer"])), []).append(r)
    for s in load_songs():
        t, a = norm(s["title"]), first_artist(s["artist"])
        if s["id"].startswith("1986-thats-what"):
            a = "dionne"
        keys = [k for k in weeks if k[0] == t and a in k[1]]
        if not keys:
            print("NO MATCH", s["id"]); open(song_dir(s["id"], "charts.none"), "w").close(); continue
        run = sorted((r for k in keys for r in weeks[k]), key=lambda r: r["chart_week"])
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
               "retrieved": TODAY, "confidence": "sourced"}
        del out["chart_entries"]
        write_json(song_dir(s["id"], "charts.json"), out)
        print(s["chart_year"], s["title"][:30], "debut", out["debut_position"], "peak", peak,
              "wks", out["weeks_on_chart"], "#1 wks", out["weeks_at_number_one"], keys)


if __name__ == "__main__":
    main()
