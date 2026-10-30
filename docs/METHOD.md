# Method

Version 0.1.0, as of 30 October 2026.

## Unit

Hours of Arabic speech audio per corpus partition, stored in seconds and rounded only for display. A row is one corpus, partition, licence class, dialect group, genre and hour type.

## Licence evidence

For each corpus the licence-bearing page of the publisher is saved as served and as rendered text, with SHA-256 hashes and the retrieval time (`evidence/index.jsonl`). The exact licence sentence is quoted in `config/corpora.yaml`. Copies of a corpus elsewhere are read too; when they declare another licence, the row notes it and the publisher's licence is used. Two different licences stated by the publisher itself put the corpus in the class "disputed".

## Licence classes

- **Open, commercial use allowed** (`open-commercial`)
- **Open, non-commercial only** (`open-noncommercial`)
- **No derivatives** (`no-derivatives`)
- **Research use or on request** (`research-or-request`)
- **Manifests only (no audio)** (`manifests-only`)
- **Disputed** (`disputed`)
- **No licence found** (`unknown`)

The rules are in `config/licence_classes.yaml`. ND decides the class when a licence carries both NC and ND. A software licence declared for data (MIT, Apache, BSD) is open-commercial with the flag `software_licence_on_data`. When the publisher requires a signed agreement or a request process before the audio is shared, the row is classed research use or on request, whatever licence string the card carries (`licence_class_override` in `config/corpora.yaml`, with the quote that says so).

- MASC: the licence (CC BY 4.0) is read from the dataset metadata of the publisher's IEEE DataPort page; the visible page text states no licence. A third-party copy on the Hugging Face Hub (abdusah/masc) states CC BY-NC 4.0. The counter uses the publisher's licence, so MASC is in the class “Open, commercial use allowed”.
- QASR: the publisher's card states CC BY-NC 2.0, holds no files and links to a page where the data is obtained through a request process, so QASR is in the class “Research use or on request”.

## Hours

In order of preference: computed from metadata (duration columns, manifests, viewer statistics), computed from release statistics, stated by the publisher (quoted, with its location). Hour types (released audio, transcribed, validated, clean, manifest) are stored separately and never added together. The headline uses released audio of rows in the open-commercial class that passed the second check, after overlap adjustment.

YODAS v3 Arabic: the length column of 208 metadata files (138,179 recordings) was read with range requests (20.4 MB of 1.6 GB). Rows are split by the uploader-locale field (`locale_lang`): Arabic 6,898.4 h, another language 16,310.0 h, not given 10,252.3 h. The measuring code writes the same split into `evidence/measurements/yodas3-ar.json` (`locale_hours`), and `python scripts/measure.py --summaries-only` recomputes it from the saved table without any request.

## Overlap

Shared hours are removed once, from the corpus later in the priority list of `config/corpora.yaml`, when both corpora are in the same licence class. Sources: publisher statements (YODAS v3 states that its videos are distinct from YODAS v1 and v2; ArVoice Part 3 is a modified subset of the Arabic Speech Corpus; ADI-20 extends ADI17) and published video IDs (MASC segment tables, ADI17 validation and test segment IDs, the ADI-20-53h manifest), compared as SHA-256-truncated hashes. YODAS recording IDs are publisher IDs, so overlap with YODAS could not be measured. Overlap that could not be measured is not removed: MASC with YODAS v3 and YODAS2 (open, commercial use allowed); QASR with MGB-2 (research use or on request). Those class figures may count shared hours twice.

## Dialect and genre

Dialect groups follow `config/dialect_taxonomy.yaml`. A group is set only when the source states a dialect or a country; country labels are marked "source-stated country". The non-MSA dialect figure counts open-commercial released audio in the groups Gulf, Levantine, Egyptian, Maghrebi, Iraqi, Sudanese and Yemeni. Quran recitation is a separate genre so that it does not count as dialect coverage.

## Second check

`scripts/second_check.py`, a separate script that does not import the package, re-derives each row's hours (re-summing the measurement tables, recomputing viewer and release statistics, re-reading each stated number from its quote in the saved page) and its licence class (with keyword rules written separately from the class table), re-computes the video-ID overlaps, the YODAS v3 locale split and the headline, checks the licence each recorded third-party copy declares, and writes `qa/second_check.csv`. A row enters the headline only when its hours agree within 0.1 % (and 0.01 h) and its class is identical. As of 2026-10-30: 31 of 31 rows agree.

## Candidates

`scripts/discover.py` lists datasets on the Hugging Face Hub tagged Arabic with audio, speech recognition or speech synthesis tags, Zenodo records matching Arabic speech, and Arabic entries of the OpenSLR index. Candidates are never added automatically; each is listed in `candidates_rejected` with a reason until it is reviewed.

## Access

One fixed User-Agent, at least one second between requests to the same host (three seconds for arXiv), no credentials, stop on HTTP 401, 403 or 429, no audio fetched, gated repositories not opened.
