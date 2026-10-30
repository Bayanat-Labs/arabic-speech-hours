# Open Arabic Speech Hours Counter

Counts released Arabic speech hours by licence class, hour type, dialect and genre, from published metadata and quoted publisher statements. By [Bayanat Labs](https://www.bayanatlabs.com). Code: Apache-2.0. Data and documentation: CC BY 4.0.

As of 30 October 2026, **36,221 hours** of released Arabic speech audio carry an open licence that allows commercial use, across 8 corpora, after removing overlap that the publishers state. 99.5% of these hours come from corpora derived from YouTube videos (as their publishers state), and 3.0 hours (0.008%) carry a dialect label other than Modern Standard Arabic from the source. YODAS v3 accounts for 92.4% of the figure; its Arabic subset is filed by caption-track language. By uploader locale, 6,898.4 of its 33,460.7 hours are Arabic, 16,310.0 another language and 10,252.3 not given.

Beside it, never added to it: open, non-commercial only 667 h (1 corpus); no derivatives 16 h (1 corpus); research use or on request 3,216 h (4 corpora); no licence found 4,639 h (3 corpora).

- Data: [https://huggingface.co/datasets/Bayanat-Labs/arabic-speech-hours](https://huggingface.co/datasets/Bayanat-Labs/arabic-speech-hours) (CC BY 4.0)
- Chart and table: [https://huggingface.co/spaces/Bayanat-Labs/arabic-speech-hours](https://huggingface.co/spaces/Bayanat-Labs/arabic-speech-hours)
- Page: https://www.bayanatlabs.com/open/arabic-speech-hours

## Released audio by licence class (as of 30 October 2026)

| Licence class | Released audio hours (overlap-adjusted) | Gross | Corpora |
|---|---:|---:|---:|
| Open, commercial use allowed | 36,221.0 | 36,223.7 | 8 |
| Open, non-commercial only | 667.0 | 667.0 | 1 |
| No derivatives | 15.9 | 15.9 | 1 |
| Research use or on request | 3,216.3 | 3,216.3 | 4 |
| No licence found | 4,639.1 | 7,672.1 | 3 |

## Install

The tool reads the configuration and evidence in this repository, so clone it at the release tag:

```bash
git clone --branch v0.1.0 https://github.com/Bayanat-Labs/arabic-speech-hours.git
cd arabic-speech-hours
python -m pip install .
```

The package alone (for `import arabic_speech_hours`): `pip install "git+https://github.com/Bayanat-Labs/arabic-speech-hours@v0.1.0"`.

## Run

```bash
python scripts/measure.py            # hours from metadata -> evidence/measurements/ (one request per second per host)
python scripts/discover.py           # candidate datasets -> evidence/candidates.json
python scripts/build.py --as-of 2026-10-30
python scripts/second_check.py --snapshots DIR   # re-derivation by a separate script -> qa/second_check.csv
python scripts/build.py --as-of 2026-10-30      # only rows that pass the check enter the headline
```

`scripts/snapshot.py --out DIR` re-fetches the evidence pages listed in `config/snapshots.yaml` for the second check. Every request sends the User-Agent `BayanatLabs-OpenData/1.0 (+https://bayanatlabs.com/open; hello@bayanatlabs.com)`, waits at least one second between requests to the same host (three seconds for arXiv), sends no credentials, and stops on HTTP 401, 403 or 429. Gated repositories are not opened, and no audio is fetched.

The `Refresh the counter` workflow runs the same steps when started by hand and uploads the results for review; it does not commit or publish.

## Layout

- `config/corpora.yaml`: each corpus with its licence evidence, rows, stated quotes and overlaps; `config/measurements.yaml`: what metadata each computed figure reads; `config/licence_classes.yaml`, `config/dialect_taxonomy.yaml`, `config/snapshots.yaml`, `config/excluded.yaml`
- `src/arabic_speech_hours/`: polite HTTP access, range reads of Parquet columns, measurements, discovery, build
- `scripts/second_check.py`: the second check, a separate script that does not import the package
- `data/`, `feed/`, `embed/speech-hours.js`, `space/` (the static page), `evidence/`, `qa/`
- `docs/METHOD.md`: the method in full

## Embed

```html
<arabic-speech-hours src="https://huggingface.co/datasets/Bayanat-Labs/arabic-speech-hours/resolve/main/feed/latest.json"></arabic-speech-hours>
<script src="https://huggingface.co/datasets/Bayanat-Labs/arabic-speech-hours/resolve/main/embed/speech-hours.js" defer></script>
```

## Licence

Code (`src/`, `scripts/`, `tests/`, `embed/`, `space/*.js|html|css`, workflows): Apache License 2.0 (`LICENSE`). Data, configuration and documentation: CC BY 4.0 (`LICENSES/CC-BY-4.0.txt`). Each counted corpus keeps its own licence (`LICENSE-sources.md`). Licence classes are informational and are not legal advice.

Corrections: hello@bayanatlabs.com.
