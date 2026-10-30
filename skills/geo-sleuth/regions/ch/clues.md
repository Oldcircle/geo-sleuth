# Switzerland clues

Entries use the shared format (`references/clues/README.md`). Use these only after Switzerland is a candidate; cross-country clues belong in `references/clues/global.md`. Sources checked on 2026-10-31. The pack is a stub: it carries clues and a plate lookup, but no admin table yet, so `board.py children Switzerland` still needs one.

## Plates

### Two-letter canton code opening the plate
- Look for: a white plate with black lettering whose first two characters are letters, then digits, for example `ZH 123456`, `GE 1` or `TI 123 456`. Read the two letters, not the number.
- Points to: the canton where the vehicle is registered, for example `ZH` to Zürich, `GE` to Geneva, `TI` to Ticino. The full code-to-canton table is in `data/plates.json` and answers through the `plate` lookup.
- Strength: strong for the canton; the registered canton is not necessarily where the photo was taken.
- Counterexamples: customs, military, diplomat and short-term plates use other shapes and have no canton code. A misread letter pair (`BE`/`RE`, `SG`/`5G`) or a foreign plate also misses. Leased or company vehicles can be registered in a canton far from their usual route.
- Sources: [Wikipedia: Vehicle registration plates of Switzerland](https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Switzerland) describes the canton prefix and the special series.

### Cantonal coat of arms between the code and the number
- Look for: a small coloured shield printed on the rear plate only, between the canton letters and the digits.
- Points to: the same canton as the letters; the shield confirms a partially readable code and helps when the letters are obscured.
- Strength: medium (single source); the shield is small and often unreadable in a wide shot.
- Counterexamples: front plates carry no shield, so its absence says nothing. A rear plate can be replaced by a plain one after damage, and some special series print no shield.
- Sources: [Wikipedia: Vehicle registration plates of Switzerland](https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Switzerland) documents the rear-plate shield.

## Language and text

### Language of signs, shop names and public notices
- Look for: the language of fixed signs, not of a single advertisement: German (`Ausgang`, `Kasse`, `Apotheke`), French (`Sortie`, `Caisse`, `Pharmacie`), Italian (`Uscita`, `Cassa`, `Farmacia`) or Romansh in parts of Graubünden.
- Points to: the language region: German-speaking north and centre, French-speaking west, Italian-speaking Ticino and parts of Graubünden, Romansh valleys in Graubünden. It narrows the canton group, rarely a single canton.
- Strength: strong for the language region; the canton still needs another clue. Municipalities on a language border can post both languages.
- Counterexamples: bilingual towns (Biel/Bienne, Freiburg/Fribourg, Siders/Sierre) print both languages, so the pair does not pick one. English-only tourist signage is common in resort centres, and international brands keep English or their home language.
- Sources: [ch.ch: Languages in Switzerland](https://www.ch.ch/en/society-and-community/languages/) describes the four national languages and their areas.

### Trilingual railway signage
- Look for: station signs and tickets carrying the three official names of the federal railways in one line: `SBB CFF FFS`, or `SBB` alone on rolling stock and clocks.
- Points to: Switzerland as the country; the combination itself is a country-level confirmation rather than a cantonal clue.
- Strength: strong (single source) for the country, weak for any canton.
- Counterexamples: regional operators and private railways use their own brands (`BLS`, `RhB`, `MGB`), so their absence means nothing. Cross-border trains carry the neighbouring operator's branding too.
- Sources: [SBB](https://www.sbb.ch/en) is the federal railway; the trilingual abbreviation is its registered brand.

## Addresses and postal codes

### Four-digit postal code written before the town name
- Look for: a four-digit number immediately before a place name on mailboxes, forms, shop fronts or delivery vans, for example `8001 Zürich`, `1201 Genève` or `6900 Lugano`.
- Points to: a commune or city district in Switzerland; the first digit groups the country into regions (1xxx west, 3xxx Bern area, 8xxx Zürich area, 9xxx east).
- Strength: medium (single source); the code identifies the delivery area, not the exact building.
- Counterexamples: Liechtenstein shares the four-digit format (94xx) and is a separate country. Five-digit codes on the same sign point to a neighbouring country, and a code can be printed on a mail piece handled elsewhere.
- Sources: [Swiss Post](https://www.post.ch/en) publishes the postal-code directory and the four-digit format.