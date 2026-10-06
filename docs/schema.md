# Schema

Draft. Files are added here as each layer is collected.

## `songs.csv`

| Column | Meaning |
|---|---|
| `id` | `<chart_year>-<slugified title>`, e.g. `1983-every-breath-you-take`. Matches the folder in `songs/` |
| `title`, `artist` | As credited on the charting single |
| `chart_year` | Year used for selection (e.g. Billboard year-end chart) |
| `country`, `region` | Artist's country of origin and its region |
| `selection` | Why the song is in the corpus, e.g. `billboard-year-end-1` |
| `pilot` | `yes` for the 10 pilot songs |
| `wikidata`, `musicbrainz` | IDs, blank until matched (`musicbrainz` is the recording ID of the charting version) |
| `status` | Semicolon list of layers present, e.g. `listed; facts; structure; chords; cover` |

## Per song: `songs/<id>/` (planned)

| Path | Contents |
|---|---|
| `facts.json` | Credits, label, release dates, genres, awards, IDs (MusicBrainz, Wikidata) |
| `wikipedia.json` | Article text by section |
| `structure.json` | Sections with start and end times, one list per source, plus a reconciled list and bridge yes/no per source |
| `lyrics/timed.lrc`, `lyrics/measures.json` | Timed lyrics (LRCLIB) and measures: words, lines, repetition, time to first chorus |
| `chords.json` | Chord sequence per section, as written and as Roman numerals, with key and source per entry |
| `theory.json` | Derived: progression family, borrowed chords, key changes, distinct chords, bridge contrast |
| `audio.json` | Key, tempo, loudness from the preview (preview itself not kept) |
| `cover/album.jpg`, `cover/single.jpg`, `cover/cover.json` | Artwork and measures: palette, brightness, saturation, faces, text share, credits |
| `lineage.json` | Covers, samples, interpolations, each with source and confidence |
| `corrections.json` | Overrides to upstream data with reasons; source files stay untouched |
| `*.none` | Marker that a source was checked and had nothing, so it isn't rechecked |

Every fact-bearing entry carries `source`, `retrieved` (date) and `confidence` (see `CLAUDE.md`).
