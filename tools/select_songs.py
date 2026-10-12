"""Build songs.csv: the Billboard Year-End Hot 100 top 10 for every year 1959-2023
(65 years x 10 = 650 songs), read from Wikipedia's year-end list pages, which cite Billboard's
year-end issues. A song already in the corpus from an earlier year is recorded as a repeat and
that year's next-ranked song is taken instead, so every year contributes 10 distinct songs.
Writes reference/selection.json with the evidence for every pick."""
import csv, os, re
from common import ROOT, TODAY, wiki_raw, slug, write_json, norm

YEARS = list(range(1959, 2024))
PER_YEAR = 10
LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def unlink(s):
    s = re.sub(r"<ref[^>/]*/>|<ref.*?</ref>|<!--.*?-->", "", s, flags=re.S)
    s = LINK.sub(lambda m: m.group(2) or m.group(1), s)
    s = re.sub(r"\{\{(?:sort|sortname)\|[^|}]*\|([^}]*)\}\}", r"\1", s)
    s = re.sub(r"\{\{[^}]*\}\}|'''?", "", s)
    return s.strip().strip('"').strip()


def attrs_off(cell):
    """Drop a cell's attribute prefix (scope="row" | ..., rowspan="2" | ...) and return (rowspan, text)."""
    m = re.match(r'\s*((?:[a-z-]+\s*=\s*(?:"[^"]*"|[^\s|"]+)\s*)+)\|(?!\|)(.*)$', cell, re.S)
    if m:
        rs = re.search(r'rowspan\s*=\s*"?(\d+)', m.group(1))
        return (int(rs.group(1)) if rs else 1), m.group(2).strip()
    return 1, cell.strip()


def rows_of(text):
    """Yield (rank, title_cell, artist_cell) for the main year-end table, carrying rowspans."""
    start = text.find("{|")
    end = text.find("\n|}", start)
    table = text[start:end]
    carry = {}  # column index -> [remaining rows, text]
    out = []
    for chunk in table.split("\n|-")[1:]:
        body = "\n".join(l for l in chunk.split("\n") if not l.startswith("!") and not l.startswith("|+"))
        body = body.strip()
        if not body or not body.startswith("|"):
            continue
        cells = re.split(r"\|\||\n\|", body[1:])
        cells = [attrs_off(c) for c in cells if c.strip() != ""]
        row, ci = [], 0
        queue = list(cells)
        while queue or ci in carry:
            if ci in carry:
                rem, txt = carry[ci]
                row.append(txt)
                if rem - 1 > 0:
                    carry[ci] = [rem - 1, txt]
                else:
                    del carry[ci]
            else:
                rs, txt = queue.pop(0)
                row.append(txt)
                if rs > 1:
                    carry[ci] = [rs - 1, txt]
            ci += 1
            if ci > 6:
                break
        if len(row) >= 3 and re.match(r"^\s*(T-)?\d+\s*$", unlink(row[0])):
            out.append((int(re.sub(r"\D", "", unlink(row[0]))), row[1], row[2]))
    return out


def page_title(year):
    return "Billboard Year-End Hot 100 singles of %d" % year


def song_key(title, artist):
    a = re.split(r" featuring | feat\. | with | and | & |, |/", unlink(artist))[0]
    return norm(title.split('" /')[0]) + "|" + norm(a)


def main():
    old = {}
    if os.path.exists(os.path.join(ROOT, "songs.csv")):
        old = {r["id"]: r for r in csv.DictReader(open(os.path.join(ROOT, "songs.csv")))}
    seen, rows, evidence = {}, [], []
    for y in YEARS:
        text = wiki_raw(page_title(y))
        table = rows_of(text)
        assert len(table) >= 90, (y, len(table))
        taken = 0
        for rank, tcell, acell in table:
            if taken == PER_YEAR:
                break
            first = re.split(r'"\s*/\s*"', tcell)[0]
            links = LINK.findall(first)
            title, artist = unlink(first), unlink(acell)
            k = song_key(title, acell)
            e = {"year": y, "rank": rank, "title": title, "artist": artist,
                 "article": links[0][0].split("#")[0] if links else None,
                 "article_section": links[0][0].split("#")[1] if links and "#" in links[0][0] else None,
                 "double_a_side": bool(re.search(r'"\s*/\s*"', tcell)),
                 "source": "https://en.wikipedia.org/wiki/" + page_title(y).replace(" ", "_"),
                 "retrieved": TODAY, "confidence": "sourced"}
            if k in seen:
                e["repeat_of"] = seen[k]
                evidence.append(e)
                continue
            sid = "%d-%s" % (y, slug(title))
            if sid in seen.values():  # same title, same year, different song (1990: Hold On x2)
                sid += "-" + slug(re.split(r" featuring | and | & |, ", artist)[0])
            seen[k] = e["id"] = sid
            evidence.append(e)
            taken += 1
            prev = old.get(sid, {})
            rows.append({"id": sid, "title": title, "artist": artist, "chart_year": y, "year_end_rank": rank,
                         "country": prev.get("country", ""), "region": prev.get("region", ""),
                         "selection": "billboard-year-end-top-10" + ("" if rank <= 10 else "-replacement"),
                         "pilot": prev.get("pilot", "no") or "no",
                         "wikidata": prev.get("wikidata", ""), "musicbrainz": prev.get("musicbrainz", ""),
                         "status": prev.get("status", "listed")})
        print(y, taken, [r["title"][:18] for r in rows[-10:]][:3], flush=True)
    write_json(os.path.join(ROOT, "reference", "selection.json"), evidence)
    with open(os.path.join(ROOT, "songs.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    print(len(rows), "songs;", sum(1 for e in evidence if "repeat_of" in e), "repeats skipped")


if __name__ == "__main__":
    main()
