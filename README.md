# Svenska practice

A small local web app for drilling Swedish grammar and vocabulary. It tracks your accuracy per word, introduces new words in frequency order, keeps repeating the ones you get wrong, and stops showing words once you've learned them.

## Modes

| Mode | What you do |
|---|---|
| **Substantiv** (nouns) | See a noun and its English meaning. Type `en`/`ett`, the definite singular, the indefinite plural and the definite plural. 5,000 nouns. |
| **Verb** | See a verb (a random present, past or supine form, or the infinitive). Type the English translation, the imperative, infinitive, present, preterite and supine, and its conjugation group (1–4). 2,000 verbs. |
| **Adjektiv & adverb** | Read a short Swedish paragraph where adjectives and adverbs are blanked out and only their base form is shown. Type the form that fits the context. 168 paragraphs, about 1,300 blanks, each with a short rule explanation. |
| **Översätt** (translate) | Upload a CSV of Swedish/English pairs and get quizzed in either or both directions. |
| **Framsteg** (progress) | Accuracy per mode and per word, which parts of each word you get wrong most, and buttons to mark words learned or bring them back. |

## Running it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --port 8000
```

Then open http://localhost:8000. Progress is saved in `data/progress.db` (SQLite). Set `SWEDISH_APP_DB=/some/path.db` to keep it somewhere else.

Keyboard: `Tab` moves between fields, `Enter` checks the answer, and `Enter` again goes to the next card.

## How words are picked

Each mode keeps a small working set of words you're currently learning: 15 for nouns and verbs, 12 for translation decks, 6 for paragraphs.

- While the working set has room, the next unseen item is introduced in frequency order (most common first).
- Once it's full, you get a word from the working set, weighted towards the ones you get wrong most. The last couple of words shown are skipped so you don't get the same card twice in a row.
- A word counts as learned when you get every part right on the first try, or right 3 times in a row (2 for paragraphs). Learned words stop appearing.
- **I already know this** marks a word learned without answering. **I was right** turns your last answer into a correct one (useful when you typed a valid English synonym the dictionary doesn't list). **Skip (bad item)** hides an entry that looks wrong.

## Translation CSVs

Two columns, Swedish then English. A header row is optional. If you include one, the columns can be in either order (`swedish,english`, `svenska;engelska`, `sv\ten` and so on). Commas, semicolons and tabs all work.

```csv
swedish,english
en bil,car; automobile
att springa,to run
hund,dog
```

Separate alternative answers with `;` or `/`. Articles are optional when you answer: `bil` matches `en bil`, and `run` matches `to run`.

## Data sources

| What | Source | License |
|---|---|---|
| Word frequencies | [wordfreq](https://github.com/rspeer/wordfreq) 3.1, which pools Swedish Wikipedia, OpenSubtitles 2018, the OSCAR web crawl, Twitter and Reddit | CC BY-SA 4.0 |
| Swedish→English meanings, noun and verb inflections | [Folkets lexikon](https://folkets-lexikon.csc.kth.se/folkets/) (KTH), via the mirror in [dpriskorn/lexfolketslexicon](https://github.com/dpriskorn/lexfolketslexicon) | CC BY-SA 2.5 |
| Full inflection tables | [UniMorph Swedish](https://github.com/unimorph/swe) (from Wiktionary) | CC BY-SA 3.0 |
| Cloze paragraphs | Written for this app by Claude agents across 42 everyday topics. Adjectives and adverbs were tagged by Claude Haiku agents and checked against the UniMorph adjective tables. | — |

Because the noun and verb lists are built from CC BY-SA data, `data/nouns.json` and `data/verbs.json` are shared under CC BY-SA too.

### Rebuilding the word lists

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python scripts/build_lexicon.py --nouns 5000 --verbs 2000
```

This downloads the Folkets and UniMorph files into `data/raw/` (pinned to fixed commits) and writes `data/nouns.json` and `data/verbs.json`.

How the build works:

- **Frequency per word.** wordfreq counts word forms, not dictionary words, and many forms are shared: *man* is both a pronoun and a noun, and *lag* is the past tense of *ligga* as well as two different nouns. So a word's frequency is estimated from its forms that belong to no other word, scaled up by how much of a typical noun's or verb's usage those forms account for.
- **en/ett.** Comes from the definite singular: `-n` means en, `-t` means ett.
- **Verb groups.**
  - Group 1: -ar / -ade / -at
  - Group 2a: -er / -de / -t
  - Group 2b: -er / -te / -t
  - Group 3: short verbs with -r / -dde / -tt
  - Group 4: strong and irregular verbs

  Typing `2` counts as right for both 2a and 2b.
- **Homographs** like *lag* (law) and *lag* (team) are separate cards, and each shows its own meaning.

### Rebuilding the paragraphs

The source paragraphs and Haiku's tags are in `data/cloze_source/`. The prompts used are in `scripts/prompts/`. `scripts/build_cloze.py` checks every tag (the word must appear in the text, and an adjective form must belong to its base word's inflection table), drops the ones that fail, and writes `data/cloze.json`:

```bash
.venv/bin/python scripts/build_cloze.py
```

To add more paragraphs, add entries to `paragraphs.json`, tag them with the prompt in `scripts/prompts/tagger.md`, save the tags as another `tags_N.json`, and rerun the script.

## Tests

```bash
.venv/bin/python -m pytest
```
