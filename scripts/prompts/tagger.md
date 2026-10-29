# Brief: tag adjectives and adverbs in Swedish paragraphs

You are preparing fill-in-the-blank exercises for a Swedish learner. For each paragraph,
find the words the learner should inflect themselves: adjectives and adjective-derived
adverbs. The app will blank each one out and show its base form in brackets, and the
learner must type the exact form used in the text.

## What to tag

Tag, in order of appearance:

1. **ADJ**: every adjective, attributive or predicative, in any form: positive,
   comparative, superlative, definite (-a/-e), neuter (-t), plural (-a). Include
   adjectival participles (stängd, stängt, stängda, spännande, intresserad) and
   indeclinable adjectives (bra, extra, gratis, rosa, sämre stays ADJ).
   Include the quantifiers många/fler/flest, få/färre/färst, and egen/eget/egna.
2. **ADV**: adverbs formed from an adjective (snabbt ← snabb, tydligt ← tydlig,
   ordentligt ← ordentlig, lugnt ← lugn), and comparative/superlative adverbs
   (oftare ← ofta, mer ← mycket, mest ← mycket, bättre ← bra, längre ← länge, senare ← sent).

Do NOT tag:
- plain adverbs that never inflect (inte, här, där, nu, sedan, redan, också, ganska, väldigt,
  sällan, ofta (positive), mycket (positive), riktigt as an intensifier is fine to tag only if
  clearly the adverb of riktig), pronouns, articles, numerals (en, ett, två, första),
  possessives (min, din, vår), nouns, verbs.
- adjectives that are part of a proper noun or compound word.

## Base form

`base` is the dictionary form: positive degree, indefinite, singular, common gender
(en-form). Examples: stora → stor, stort → stor, största → stor, större → stor, lilla → liten,
små → liten, mindre → liten, gamla → gammal, äldre → gammal, bättre → bra, bäst → bra,
sämre → dålig, fler → många, mer → mycket, öppet → öppen, egna → egen, vackra → vacker,
snabbt (adverb) → snabb, oftare → ofta, stängda → stängd.

## Output

For each paragraph output an object:

{"id": "<paragraph id>", "blanks": [
  {"form": "<exact word as written in the text, same capitalisation>",
   "occurrence": <1 for the first time this exact word appears in the paragraph, 2 for the second, ...>,
   "pos": "ADJ" or "ADV",
   "base": "<base form>",
   "rule": "<one short English sentence explaining why this form is used here, e.g. 'definite form after det: -a ending', 'ett-word, indefinite singular: add -t', 'adverb from adjective: -t ending', 'comparative of bra is irregular'>"}
]}

Write all paragraph objects as a JSON array (UTF-8) to the output path given in your task,
using the Write tool. Double-check each `form` appears verbatim in the text. Then reply
with only the total number of blanks written.
