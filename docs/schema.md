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
| `structure.json` | Sections per source (`tools/expert_sets.py`, `tools/chordonomicon.py`); see "Structure and chords" below. A reconciled list is not built yet |
| `structure.none`, `chords.none` | No structure / chord source covers the song (expert sets checked, Chordonomicon checked by Spotify ID) |
| `lyrics/timed.lrc` (or `lyrics/plain.txt` when only unsynced lyrics exist) | Lyrics exactly as LRCLIB has them (`tools/lyrics.py`). Confidence `crowd` |
| `lyrics/source.json` | LRCLIB id; matched track, artist, album, duration; which reference length it matched (MusicBrainz length first, then the Deezer track matched by ISRC or the preview track, then Wikipedia infobox lengths), how many LRCLIB entries passed the checks and how similar they are; flags; rejected candidates with reasons |
| `lyrics/measures.json` | Computed from the lyric: lines, words, unique words, repeated-line share, zlib compression ratio (lower = more repetitive), title-phrase occurrences, pronoun counts (I/me/my, you/your, we/us/our), first vocal time, sung time and words per minute, longest gap between lines, and `first_repeated_block` (the earliest pair of consecutive lines that recurs, a crude chorus proxy). Confidence `computed` |
| `lyrics.none` | LRCLIB checked, nothing matched (reasons inside) |
| `chords.json` | Chord sequence per section, as written and as Roman numerals, with key and source per entry; see "Structure and chords" below |
| `theory.json` | Derived: progression family, borrowed chords, key changes, distinct chords, bridge contrast |
| `audio.json` | From the 30 s preview (`tools/audio.py`; preview kept only in `_cache/previews/`). `preview`: service (Deezer by ISRC, else Deezer search, else iTunes), track id, matched ISRC, matched title/artist/album/length, segment caveat. `measures` (confidence `computed`): tempo (BPM, plus tempogram candidates for spotting double/half time), key and mode (Krumhansl-Schmuckler on chroma, with runner-up and correlations), RMS and peak dBFS, approximate LUFS (BS.1770 on the clip), spectral centroid (brightness), onset density. `deezer_metadata`: Deezer's own `bpm` and `gain` (confidence `sourced`). `flags`: doubtful values. `rejected_candidates`: with reasons |
| `audio.none` | No matching preview found (reasons inside) |
| `cover/album.jpg`, `cover/single.jpg`, `cover/cover.json` | Artwork and measures: palette, brightness, saturation, faces, text share, credits |
| `lineage.json` | Covers, samples, interpolations, each with source and confidence |
| `corrections.json` | Overrides to upstream data with reasons; source files stay untouched |
| `*.none` | Marker that a source was checked and had nothing, so it isn't rechecked |

Every fact-bearing entry carries `source`, `retrieved` (date) and `confidence` (see `CLAUDE.md`).

## Structure and chords

Written by `tools/expert_sets.py` (McGill Billboard 2.0, Harmonix Set, Rolling Stone corpus, Isophonics; confidence `expert`) and `tools/chordonomicon.py` (Chordonomicon; confidence `crowd`). Shared code in `tools/harmony.py`. Each tool replaces only its own sources, so they can run in either order; both recompute `comparison` and the `.none` markers. Indexes: `reference/expert-sets.json` (what matched), `reference/spotify-ids.json` (Spotify IDs found per song and how).

**`structure.json`**: `{id, updated, note, sources: [...], comparison}`. Each source has `key` (`mcgill_billboard`, `harmonix`, `rolling_stone_dt`, `rolling_stone_tdc` (the two RS analysts are separate sources), `isophonics`, `chordonomicon`), `dataset`, `source_id`, `match` (the source's own title/artist and IDs), `source`, `url`, `licence`, `retrieved`, `confidence`, `version_check` (duration compared with our recording) and `version_note` when the annotated audio is a different edit or version, `bridge` (`yes` / `no` / `unknown`) with `bridge_basis`, and `sections`: `[{start, end, label, normalised, ...}]` in seconds from the start of the audio the annotators used (`null` for Chordonomicon, which has no timings). McGill sections also carry `letter` (A, B, C' ...: same letter = same music) and `bars`; RS sections carry `first_bar` and `bars`; Harmonix sections carry `bars` (counted from its downbeats). Silence and end markers are dropped.

**`chords.json`**: same envelope. Each source has `key_info` (`tonic`, `tonic_pc` 0–11, `mode`, `name`, `basis`, `confidence`: `expert` when annotated, `computed` when we estimated it), optional `key_changes`, `chord_syntax`, and `sections`: `[{label, normalised, key, written: [...], roman: [...], raw: [...]}]`. `written` and `roman` are parallel lists of chord changes (the same chord repeated across bars is merged). `key` is the tonic in force, written `C -> G` when it changes inside the section.
- Roman numerals are relative to the tonic whatever the mode (RS style): upper case major, lower case minor, `b`/`#` for chromatic roots, so a minor-key song reads `i bVI bIII bVII`. Suffixes: `7`, `maj7`, `o` diminished, `o7`, `ø7` half-diminished, `+` augmented, `sus4`, `5` power chord, `6`, `9`. Inversions are kept in `written` but dropped from the numeral. RS numerals are kept exactly as analysed (e.g. `V7/V`, `Vs4`); their `written` names are derived by us.
- Chordonomicon keys are estimated from the chord set (Krumhansl-Kessler profile on chord tones, root double-weighted, first and last chord boosted), with `fit` and `runner_up`. Fan transcriptions are often capo-shifted, so compare them in Roman numerals.

**Normalised section labels** (`normalised`): `intro`, `verse`, `prechorus`, `chorus`, `bridge`, `solo`, `instrumental`, `outro`, `other`.

| Normalised | McGill / Harmonix / Isophonics / Chordonomicon labels | Rolling Stone rule names (prefix) |
|---|---|---|
| intro | intro, pre-intro, pre-verse, fadein | In, Intr |
| verse | verse (one, two ...), spoken verse | V..., Vr, VP |
| prechorus | pre-chorus, prechorus, pre chorus | Pre, PC, Pr |
| chorus | chorus (a, b), refrain, postchorus (Harmonix), hook | Ch, Re, Rf, CP |
| bridge | bridge, middle eight | Br |
| solo | solo, guitar solo | So |
| instrumental | instrumental, inst, interlude, break, theme, main/secondary theme, head | Ins, Inst, Break, Bk |
| outro | outro, fadeout, coda, ending | Ou, Fade, Co, End |
| other | trans, transition, modulation, key change, vocal, anything else | single-letter patterns (A, B ...), Ln (link), Ta/Tg (tag), Zz |

RS rule names are the analysts' informal shorthand; a rule made only of other rules (e.g. `Zz: $Vr $Ch`) is opened into its parts. Harmonix `postchorus` maps to chorus (raw label kept).

**`comparison`** (when a song has two or more sources; otherwise the string `only one source`): in `structure.json`, `form_by_source` (normalised labels in order, repeats merged, `other` dropped), `section_order` (pairwise `same_order`, `edit_distance`, `similarity`), `section_order_agree`, `bridge_by_source`, `bridge_agree`, `bridge_expert_value` (`yes`, `no`, `disputed` when expert sources disagree, `unknown`), `notes` (version caveats). In `chords.json`, `key_by_source`, `key_agree`, and pairs against the expert reference with `same_tonic`, `semitones_apart` and `roman_root_overlap` (Jaccard share of scale-degree roots used by both). Confidence `computed`.
