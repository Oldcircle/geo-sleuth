# Sri Lanka clues

Entries use the shared format (`references/clues/README.md`). Cross-country clues that lead here (Sinhala script, driving side) are in `references/clues/global.md`.

## Text and plates

### Province code on number plates
- Look for: two small Latin letters below the emblem on the left side of the plate, before the main registration (e.g. `WP CAB-1234`). Codes: WP Western, CP Central, SP Southern, NP Northern, EP Eastern, NW North Western, NC North Central, UP Uva, SG Sabaragamuwa
- Points to: the province where the vehicle was **registered**, not where the photo was taken
- Strength: weak for the photo location (registration province only; Western Province cars are common across the island)
- Counterexamples: vehicles travel and are sold across provinces, and existing plates often keep their code even after a sale; plates in the older format (e.g. `ශ්‍රී` between the numbers) have no code; the code is being removed from new plates (announced for new registrations and ownership transfers from 1 January 2023; gazette No. 2352/29 of 5 October 2023; a 2024 report still describes the full removal as planned from 1 January 2025; a 2026 report says the codes "have now been removed"), so the actual cutover was gradual and a plate without a code says little about its age
- Sources: Wikipedia "Vehicle registration plates of Sri Lanka" (format, codes, position), https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Sri_Lanka; Ada Derana 2022-12-30 (Commissioner General of Motor Traffic: removal from 1 January 2023), https://www.adaderana.lk/news/87222/provincial-letters-to-be-removed-from-number-plates-; Sunday Observer 2024-05-05 (gazette 2352/29, requirement dropped from 1 January 2025), https://www.sundayobserver.lk/2024/05/05/news-features/22447/why-the-province-is-being-dropped-from-number-plates; Ada Derana 2026-04-23 (identifiers removed), https://www.adaderana.lk/news/121629/standard-vehicle-number-plates-to-be-issued-from-late-may

### Landline area code on shop signs and notice boards
- Look for: a fixed-line number on a shop sign, notice board or vehicle: `0XX-XXXXXXX` (e.g. `011-2345678`, `081 222 3456`)
- Points to: the district of the exchange the code is named after (011 Colombo, 021 Jaffna, 081 Kandy, 091 Galle, …); several codes reach a neighbouring district → `clues.py lookup area-code <number> --country lk`
- Strength: medium (29 codes for 25 districts; a shop's or school's own landline is usually local)
- Counterexamples: `07x` numbers are mobile and used island-wide; hotels, bank branches and chain head offices often show a Colombo `011` number anywhere on the island; codes cross district borders (e.g. `031` Negombo reaches Puttalam District, `047` Hambantota reaches Kataragama in Monaragala); old numbers survive on faded signs after a business moves
- Sources: TRCSL numbering plan as filed with the ITU (communication of 12.III.2008, update 17.VIII.2009), https://www.itu.int/oth/T02020000C3; en.wikipedia "Telephone numbers in Sri Lanka", https://en.wikipedia.org/wiki/Telephone_numbers_in_Sri_Lanka; cross-border coverage counted from phone tags in OpenStreetMap, https://www.openstreetmap.org
