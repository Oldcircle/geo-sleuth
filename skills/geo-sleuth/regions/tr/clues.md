# Turkey clues

Entries use the shared format (`references/clues/README.md`). Clues that tell Turkey apart from other countries belong in `references/clues/global.md`.

## Text and numbers

### Province code at the start of a civil number plate
- Look for: the two digits before the letters on a white civil plate (`34 ABC 123`, `06 AB 1234`); the blue band on the left reads `TR`
- Points to: the province where the vehicle was **registered** → `clues.py lookup plate <digits> --country tr` or `board.py apply --kind plate --value <digits>`
- Strength: weak for where the photo was taken; medium when most parked cars in a quiet residential street share one code
- Counterexamples: rental and fleet cars are often registered in 34 İstanbul, 06 Ankara, 07 Antalya or 35 İzmir and driven anywhere; holiday traffic carries plates far from home; 33, 46 and 63 date from the old names İçel, Maraş and Urfa; some owners cover the blue band with a red sticker
- Sources: tr.wikipedia "Türkiye taşıt plaka kodu" (codes, 1962 alphabetical order, 68–81 for later provinces), https://tr.wikipedia.org/wiki/Türkiye_taşıt_plaka_kodu; tr.wikipedia "Türkiye'nin illeri" (code per province), https://tr.wikipedia.org/wiki/Türkiye'nin_illeri

### Letter group of an older plate → district tax office
- Look for: on plates issued before sequential allocation, the first letter(s) after the province code (Ankara `06 P..` Polatlı, `06 N..` Nallıhan; Edirne `22 K..` Havsa, `22 L..` Uzunköprü, `22 F..` Keşan)
- Points to: the district (ilçe) tax office where the vehicle was registered
- Strength: weak (single source)
- Counterexamples: in recent years every province hands out `AAA 999` to `ZZZ 999` in sequence, so new plates say nothing about the district; the letter scheme differs per province and is not published as one table; school and staff-shuttle plates use reserved letters
- Sources: tr.wikipedia "Türkiye taşıt plaka kodu", section "Plaka türleri", https://tr.wikipedia.org/wiki/Türkiye_taşıt_plaka_kodu

### Landline area code on shop signs and vehicles
- Look for: a fixed-line number on a shop sign, awning, delivery van or banner: `0 (2xx)`, `0 (3xx)` or `0 (4xx)` followed by seven digits
- Points to: the province of that landline → `clues.py lookup area-code <number> --country tr`; in İstanbul, 212 is the European side and 216 the Asian side
- Strength: medium (a shop's own landline is usually local; a single source of the code list is enough here because two tables agree)
- Counterexamples: `0850`, `0800` and `444 xx xx` are nationwide numbers; `05xx` numbers are mobile; a chain's sign can show its head-office number; `0392` is Northern Cyprus, which is dialled through +90 but is not a Turkish province; old numbers survive on faded signs after a business moves
- Sources: tr.wikipedia "Türkiye'nin illeri" (telephone code column), https://tr.wikipedia.org/wiki/Türkiye'nin_illeri; en.wikipedia "Telephone numbers in Turkey" (212/216 split, full table), https://en.wikipedia.org/wiki/Telephone_numbers_in_Turkey

## Roads

### Provincial road number = plate code + two digits
- Look for: a road number in the form `NN-NN` on a route marker or kilometre post (`34-03`, `04-28`)
- Points to: the first two digits are the province's plate code → `clues.py lookup plate <first two digits> --country tr`; the road is a secondary road maintained by that province's highways division
- Strength: medium (single source)
- Counterexamples: a sign at a junction can name a road that starts in the next province; misreading a state road `D 300` as a provincial number
- Sources: tr.wikipedia "Türkiye'deki il yolları listesi" (every listed road starts with its province's plate code), https://tr.wikipedia.org/wiki/Türkiye'deki_il_yolları_listesi

### State road numbers: first digit → direction and band
- Look for: a state road number `D 010` … `D 990` on route markers and kilometre posts
- Points to: `D 0xx`–`D 4xx` run west–east and are numbered from north to south (`D 010` along the Black Sea coast, `D 400` along the south); `D 5xx`–`D 9xx` run north–south and are numbered from west to east. Use the number to pick a latitude band (west–east roads) or a longitude band (north–south roads), then `osm.py route` or `osm.py along` on that road
- Strength: medium (single source)
- Counterexamples: branch roads (`D 014`, `D 052`) are short spurs that may lie away from the main road's band; overlapping routes share a carriageway and only one number may be signed
- Sources: tr.wikipedia "Türkiye'deki devlet yolları listesi", section "Yolların numaralandırılması", https://tr.wikipedia.org/wiki/Türkiye'deki_devlet_yolları_listesi

## Landscape and crops

### Tea gardens on steep slopes
- Look for: low, clipped, dark-green bushes in tight rows covering steep hillsides, often with small houses scattered between them
- Points to: the eastern Black Sea coast, Rize above all, with Artvin, Trabzon and Giresun
- Strength: weak by default, as for any vegetation without a month; medium when the month is known and the bushes show the clipped, flat-topped rows of a harvested plantation (Turkey's tea is grown almost only here)
- Counterexamples: clipped hedges and boxwood plantings in gardens and parks; Georgia's Adjara coast across the border has the same landscape
- Sources: en.wikipedia "Tea in Turkey" (Rize as the main region since the mid-20th century), https://en.wikipedia.org/wiki/Tea_in_Turkey; en.wikipedia "Rize Province", https://en.wikipedia.org/wiki/Rize_Province

### Hazelnut orchards
- Look for: multi-stemmed bushy trees 3–5 m high in irregular clumps on slopes, the ground underneath bare or grassy; nuts in green husks in late summer
- Points to: the Black Sea region between Artvin and Kocaeli; most production is in Ordu, Giresun and Samsun, with Sakarya and Düzce in the west
- Strength: weak (needs the month, and a second clue)
- Counterexamples: hazel grows wild and in gardens elsewhere; from a distance the clumps look like any mixed scrub
- Sources: tr.wikipedia "Türkiye'de fındık üretimi", https://tr.wikipedia.org/wiki/Türkiye'de_fındık_üretimi
