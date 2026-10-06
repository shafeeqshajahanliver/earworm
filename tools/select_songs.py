"""Build songs.csv: the Billboard Year-End Hot 100 number one for each chosen year,
read from Wikipedia's year-end list pages. Writes reference/selection.json with the evidence."""
import csv, os, re, sys
from common import ROOT, TODAY, wiki_raw, slug, write_json, read_json

YEARS = [1959, 1961, 1964, 1966, 1969, 1971, 1973, 1975, 1977, 1979, 1981, 1983, 1984,
         1986, 1988, 1991, 1993, 1995, 1997, 1999, 2001, 2004, 2006, 2008, 2011, 2013,
         2016, 2018, 2020, 2023]
LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def unlink(s):
    s = re.sub(r'^\s*rowspan="\d+"\s*\|', "", s)
    s = LINK.sub(lambda m: m.group(2) or m.group(1), s)
    s = re.sub(r"<ref.*?(</ref>|/>)", "", s)
    return re.sub(r"'''?|\{\{.*?\}\}", "", s).strip().strip('"').strip()


def page_title(year):
    return ("Billboard Year-End Hot 100 singles of %d" % year)


def number_one(year):
    t = wiki_raw(page_title(year))
    m = re.search(r"\n\|\s*1\s*\|\|(.+?)\|\|(.+?)\n", t)
    if not m:  # 'scope="row" | 1' then the cells on the next line
        m = re.search(r'\n\|\s*scope="row"\s*\|\s*1\s*\n\|(.+?)\|\|(.+?)\n', t)
    title_cell, artist_cell = m.group(1), m.group(2)
    first = title_cell.split('" /')[0]
    links = LINK.findall(first)
    article = links[0][0].split("#")[0] if links else None
    artist_links = [a for a, _ in LINK.findall(artist_cell)]
    return {"year": year, "title": unlink(first), "artist": unlink(artist_cell),
            "article": article, "artist_articles": artist_links,
            "double_a_side": '" /' in title_cell, "raw_row": m.group(0).strip(),
            "source": "https://en.wikipedia.org/wiki/" + page_title(year).replace(" ", "_"),
            "retrieved": TODAY, "confidence": "sourced"}


def main():
    old = {r["id"]: r for r in csv.DictReader(open(os.path.join(ROOT, "songs.csv")))}
    rows, evidence = [], []
    for y in YEARS:
        e = number_one(y)
        evidence.append(e)
        sid = "%d-%s" % (y, slug(e["title"]))
        prev = old.get(sid, {})
        rows.append({"id": sid, "title": e["title"], "artist": e["artist"], "chart_year": y,
                     "country": prev.get("country", ""), "region": prev.get("region", ""),
                     "selection": "billboard-year-end-1", "pilot": "yes",
                     "wikidata": prev.get("wikidata", ""), "musicbrainz": prev.get("musicbrainz", ""),
                     "status": prev.get("status", "listed")})
        print(y, e["title"], "|", e["artist"], "|", e["article"])
    write_json(os.path.join(ROOT, "reference", "selection.json"), evidence)
    with open(os.path.join(ROOT, "songs.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main()
