# Brief: Swedish practice paragraphs

You are writing source text for a Swedish learning app. A later step blanks out the
adjectives and adverbs, and the learner must type the correctly inflected form given the
base form (e.g. `(stor)` -> `stora`, `(snabb)` -> `snabbt`, `(bra)` -> `bättre`).

Write natural, idiomatic, modern Swedish (the way a Swede writes today in a blog,
newspaper, email or conversation), level B1–B2. Grammar and spelling must be flawless:
learners will treat it as the reference answer.

Requirements for each paragraph:
- 3–4 sentences, roughly 40–70 words, self-contained (makes sense on its own).
- Rich in adjectives and adverbs, about 4–7 per paragraph, in VARIED forms:
  - indefinite en-word (en stor bil), indefinite ett-word (ett stort hus), plural (stora bilar)
  - definite after den/det/de (den stora bilen, det stora huset, de stora bilarna)
  - possessive + adjective (min gamla bil), predicative (huset är stort, bilarna är nya)
  - comparative and superlative (större, störst, den största), incl. irregular
    (bra/bättre/bäst, dålig/sämre/sämst, gammal/äldre/äldst, liten/lilla/små/mindre/minst,
    ung/yngre, många/fler/flest, mycket/mer/mest, lång/längre)
  - adverbs formed from adjectives with -t (snabbt, tydligt, ordentligt, lugnt)
  - tricky stems: -en adjectives (öppen/öppet/öppna, egen/eget/egna, vaken/vaket/vakna),
    -el/-er adjectives (enkel/enkla, vacker/vackra, gammal/gamla), adjectives ending in -t or -d
    (trött/trött, glad/glatt, röd/rött, god/gott), indeclinables (bra, extra, gratis, rosa)
- Vary sentence structure and vocabulary; don't reuse the same adjectives across paragraphs.

Output: a JSON Lines file (one JSON object per line, UTF-8, no trailing commentary):
{"topic": "<topic in English>", "text": "<the Swedish paragraph>"}

Write 4 paragraphs per topic. Write the file with the Write tool to the path given in your
task, then reply with only the number of paragraphs written.
