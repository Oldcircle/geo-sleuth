# Cross-country clues

Clues that tell countries and continents apart, or that work the same way in many countries. Clues that only narrow things down inside one country live in that country's region pack (`regions/<cc>/clues.md`; `regions.py list` shows which exist).

General order when the country is still open: driving side and plate shape to exclude continents → script and language of the text, phone calling codes → plate style to the state/province → infrastructure and municipal fixtures → architecture and vegetation.

## General

### Driving side, driver's seat
- Look for: whether the driver's seat is on the left or the right; which side of the road traffic keeps to; which way cars parked at the roadside face
- Points to: right-hand traffic excludes the UK, Ireland, Japan, Australia, New Zealand, South Africa, India, some Southeast Asian countries, and Hong Kong/Macau; and vice versa
- Strength: strong (exclusion type; one clue excludes a batch of countries)
- Counterexamples: left-hand-traffic countries have a few imported left-hand-drive cars; **the photo or video may be mirrored**, first check for reversed text
- Sources: v009 v010-4

### Plate aspect ratio
- Look for: the plate's shape; no need to read the characters
- Points to: long narrow strip → Europe; rectangle close to 2:1 → North America; refine further by background color and graphics
- Strength: medium
- Counterexamples: Japanese plates are also close to 2:1 (exclude them with the driver's seat side); some European vehicles carry square plates; motorcycle plates are generally squarish
- Sources: v009

### Plate background and graphics in countries that issue plates by state/province
- Look for: when the characters can't be read: the plate's overall background color, color bands, central graphic (state or provincial flag), border color
- Points to: state/province level (US, Mexico, Canada, Brazil's old format, Australia, etc.)
- Strength: medium (filter to a few states against a chart of state plate designs; narrows by an order of magnitude in one step)
- Counterexamples: out-of-state vehicles crossing state lines (especially common on freight corridors and in border cities); old and new formats coexist, and reference charts go out of date; overexposure in strong light renders light-colored graphics as white
- Sources: v002 v009

### Official bilingual or multilingual signs
- Look for: two languages with the same content on one official traffic sign or street-name sign
- Points to: an officially multilingual admin area, not "near a country that speaks that language" (e.g., German-Italian bilingual signs in Italy → Province of Bolzano/South Tyrol)
- Strength: strong
- Counterexamples: bilingual private shop signs don't count; foreign-language signs added for tourists in tourist areas don't count
- Sources: v001

### Simplified vs traditional Chinese script on signs
- Look for: characters whose simplified and traditional forms differ (门/門, 车/車, 东/東); shared ones (中, 大, 山) say nothing. Judge official signs (street names, road signs, notices) apart from shop signs. Any kana → Japanese, not this clue
- Points to: consistent simplified on official signs → mainland China or Singapore; consistent traditional → Taiwan (China), Hong Kong (China) or Macau (China); Malaysia and overseas Chinatowns mix both
- Strength: medium when several independent official signs agree (still needs one more clue); weak for one sign or shop signs only; never excludes a candidate alone
- Counterexamples: traditional on handwritten, calligraphic and old-brand shop signs in mainland China (legal there); simplified on tourist-facing shops in Hong Kong/Macau; Japanese kanji keep traditional forms (門, 車)
- Sources: Wikipedia "Simplified Chinese characters", "Traditional Chinese characters"; PRC Law on the Standard Spoken and Written Chinese Language, Art. 17

### Sub-brands and business lines of chain brands
- Look for: small marks on the sign besides the parent brand (truck tire retreading, commercial vehicle service, etc.)
- Points to: sub-brands have far fewer stores, so listing all their stores nationwide gives a candidate point list; also suggests a freight corridor or the outskirts of an industrial zone
- Strength: weak (alone); medium together with a store search
- Counterexamples: store data on maps is incomplete
- Sources: v002

### Ads for regional consumer goods
- Look for: drink and snack brand ads on vehicles and along the street
- Points to: the country or region where the brand mainly sells
- Strength: weak
- Counterexamples: multinational brands, imported brands
- Sources: v007

### Bus operator abbreviation + route number
- Look for: the operator abbreviation and route number at the top of the bus front and rear
- Points to: city; route number → look up the route corridor with `osm.py route` and search along it
- Strength: strong (to the city); with a route map, to one line
- Counterexamples: second-hand imported buses keep text from the country of origin on the body, so it can't be used to judge the country; route numbers get changed
- Sources: v007

## Europe

### Roof color: red terracotta tile vs gray pitched roofs (northern Italy, etc.)
- Look for: the color of roofs across an area in distant views of the photo or in satellite imagery
- Points to: Italian-speaking areas are mostly red terracotta; many gray or dark pitched roofs → towns in the German-speaking cultural area (Austria, Germany, South Tyrol)
- Strength: weak (meaningful only as a statistic over a whole area)
- Counterexamples: new apartment buildings often use flat roofs or gray metal roofs
- Sources: v001

### Arch form: round or pointed
- Look for: whether door and window arches are round or pointed; biforate windows (two small arches inside one large arch)
- Points to: round arch → Romanesque or Renaissance; pointed arch → Gothic. If sources say a city has few medieval remains but the photo shows an intact "medieval courtyard" → prefer 19th-century-or-later replicas (exposition pavilions, mock-historic streets, film studio sets)
- Strength: weak (narrows the building type, helps choose search terms)
- Counterexamples: there are many replicas; reverse image search in a Chinese-language interface mixes in large numbers of modern-era Chinese red-brick buildings
- Sources: v004

### Uniform streetlight design within an area
- Look for: streetlight pole color, lamp head shape
- Points to: procured uniformly by one city or area; use it for spot-check confirmation between candidate towns
- Strength: weak (for verifying, not for finding)
- Counterexamples: one manufacturer's lights are sold to many cities
- Sources: v001 v009

## Inherited standards (overseas territories, former colonies)

When you recognize infrastructure built to "country X's standard", the candidates are the home country + overseas territories that keep the home country's standards + some former colonies. Intersect that with the IP location and the continent the puzzle setter named, and often only one place remains.

### Arched crossarms on the French distribution grid
- Look for: a crossarm arching upward on top of a concrete or metal pole, three conductors hanging from suspension insulators (the "arched" layout of medium-voltage lines); identical poles lined up into the distance
- Points to: the French grid system: metropolitan France and the overseas departments that keep its standards; some former North African colonies have similar pole types
- Strength: medium (narrows the whole world to a few regions in the French system; then use IP, continent, and climate to fix one)
- Counterexamples: border areas of neighboring countries have similar styles; former colonies later changed pole types; a straight crossarm can look arched in a small distant image, so zoom in
- Sources: v013

## South Asia

### Sinhala script on official signs (Sri Lanka)
- Look for: Sinhala script (round, looping letters with no line along the top, unlike Hindi) on road signs, street-name boards and government signs; official signs often repeat the text in Sinhala, Tamil and English, but many show only one or two
- Points to: Sri Lanka; Sinhala is official there and written almost nowhere else
- Strength: medium
- Counterexamples: Sinhala on temples, shops or embassies abroad; Malayalam (Kerala, India) looks similar at low resolution; a sign with only Tamil and English fits Tamil Nadu and Sri Lanka alike, so missing Sinhala does not exclude Sri Lanka
- Sources: Constitution of Sri Lanka, Articles 18–19; Wikipedia "Sinhala script"

## Central Asia

### Chevrolet-dominated traffic (Uzbekistan)
- Look for: nearly every car in the street a Chevrolet built in Uzbekistan, or the same model under its older Daewoo or Ravon badge: Cobalt sedans, Damas microvans and Labo micro-trucks, Nexia, Spark, Tracker, Malibu
- Points to: Uzbekistan. Chevrolet held 94% of new-car sales in 2010, 89% in the first nine months of 2024 and 83% in the same period of 2025; the Cobalt alone was 30.1% of the 2025 market and the Damas the second-best seller
- Strength: strong for a street where almost all cars are Chevrolets or Daewoos, with Damas or Labo vans among them; weak for one or two Chevrolets
- Counterexamples: Uzbek-built Chevrolets are exported, so a few of them in a street prove nothing; Chevrolet's share is falling (BYD, Kia, Chery and Haval gained from 2024), so recent photos of Tashkent show more mixed traffic
- Sources: GM Authority "Chevrolet market share is 94 percent in Uzbekistan" (2010), https://gmauthority.com/blog/2010/07/chevrolet-market-share-is-94-percent-in-uzbekistan/; Kun.uz "Uzbekistan's car market sees growing competition as Chevrolet share drops" (83% in nine months of 2025, 89% a year earlier; BYD, ADM Jizzakh), https://kun.uz/en/news/2025/10/10/uzbekistans-car-market-sees-growing-competition-as-chevrolet-share-drops; Best Selling Cars Blog "Uzbekistan full year 2025: Chevrolet Cobalt at 30.1% share", https://bestsellingcarsblog.com/2026/02/uzbekistan-full-year-2025-chevrolet-cobalt-at-30-1-share/; Kun.uz "Passenger car production rises in Uzbekistan as Cobalt leads the market" (Cobalt first, Damas second, 2026), https://kun.uz/en/news/2026/07/06/passenger-car-production-rises-in-uzbekistan-as-cobalt-leads-the-market-d42fbd; Kun.uz "UzAuto Motors begins selling cars in export markets under Chevrolet brand", https://kun.uz/en/18651868; Drom.ru "Автомобильный Узбекистан: всё, что вы хотели об этом знать" (Damas built as Daewoo, Chevrolet and Ravon), https://www.drom.ru/info/misc/88822.html

### Uzbek letters on signs
- Look for: Latin text with oʻ and gʻ (a letter followed by a turned comma or apostrophe) and the digraphs sh and ch, with many q and x (`koʻchasi`, `Oʻzbekiston`, `xizmatlari`); or Cyrillic with Ў next to Қ, Ғ and Ҳ
- Points to: Uzbekistan. Latin has been the official script since 1995, but Cyrillic is still widely used on signs, in the metro and in official papers, so both appear side by side
- Strength: strong for Ў together with Қ or Ҳ, or for Latin oʻ/gʻ on an official sign
- Counterexamples: Belarusian also has Ў, but no Қ, Ғ or Ҳ (it has І instead); Tajik has Қ, Ғ and Ҳ, but writes Ӯ, not Ў; Uzbek minorities live in Kyrgyzstan, Tajikistan, Turkmenistan, Kazakhstan and northern Afghanistan (where Uzbek is written in Arabic script); signs made after the 2026 reform (in force from 22 April 2027) write Ö, Ğ, Ş and Ç instead of oʻ, gʻ, sh and ch, which looks Turkish or Azerbaijani
- Sources: en.wikipedia "Uzbek alphabet" (Cyrillic extra letters Ў, Қ, Ғ, Ҳ; 1995 Latin alphabet; 2026 reform), https://en.wikipedia.org/wiki/Uzbek_alphabet; Eurasianet "Latin alphabet in Uzbekistan: to B or not to B" (both scripts on road signs and in the metro), https://eurasianet.org/latin-alphabet-in-uzbekistan-to-b-or-not-to-b; The Times of Central Asia, "Uzbekistan alphabet reform" (both scripts remain widely visible), https://timesca.com/uzbekistan-alphabet-reform-latin-cyrillic/; en.wikipedia "Tajik alphabet", https://en.wikipedia.org/wiki/Tajik_alphabet; en.wikipedia "Belarusian alphabet", https://en.wikipedia.org/wiki/Belarusian_alphabet; en.wikipedia "Uzbek language" (countries where it is spoken), https://en.wikipedia.org/wiki/Uzbek_language

### Plate with the region code on the left and the flag on the right (Uzbekistan)
- Look for: a white plate with black characters, a two-digit region code in a box at the **left** end and the flag with `UZ` at the **right** end (`01 A 123 BC`)
- Points to: Uzbekistan. Kazakhstan, Tajikistan and Turkmenistan put their flag and country code at the left, and Kazakhstan and Tajikistan their region code at the right; Russia puts both the region code and the flag at the right
- Strength: medium (the layout is visible at a distance where the letters are not)
- Counterexamples: Kyrgyzstan has also put a two-digit region code at the left since 2016, but its flag and `KG` sit under that code at the left, not at the right end (ru.wikipedia reports the two swapped places in September 2025, which no other source confirms); older Uzbek plates (1998–2008) have the region code in blue digits; yellow, green and diplomatic Uzbek plates differ; read the country letters when you can
- Sources: en.wikipedia "Vehicle registration plates of Uzbekistan", https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Uzbekistan; en.wikipedia "Vehicle registration plates of Kazakhstan", https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Kazakhstan; en.wikipedia "Vehicle registration plates of Tajikistan", https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Tajikistan; en.wikipedia "Vehicle registration plates of Turkmenistan", https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Turkmenistan; en.wikipedia "Vehicle registration plates of Kyrgyzstan" (two-digit codes since July 2016, flag and KG under the code), https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Kyrgyzstan; ru.wikipedia "Индекс автомобильных номеров Кыргызстана" (September 2025 change), https://ru.wikipedia.org/wiki/Индекс_автомобильных_номеров_Кыргызстана; en.wikipedia "Vehicle registration plates of Russia" (region and RUS at the right), https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Russia

### Tajik letters on signs
- Look for: Cyrillic text with Ӣ, Ӯ or Ҷ, usually next to Ғ, Қ and Ҳ (`Ҷумҳурии Тоҷикистон`, `кӯчаи`, street)
- Points to: Tajikistan. The Tajik Cyrillic alphabet adds Ғ, Ӣ, Қ, Ӯ, Ҳ and Ҷ to the Russian letters; Ӣ, Ӯ and Ҷ are in none of the neighbours' alphabets (Uzbek Cyrillic has Ў instead of Ӯ, Kyrgyz has Ң, Ө, Ү, Kazakh has Ә, Ғ, Қ, Ң, Ө, Ұ, Ү, Һ, І)
- Strength: medium for Ӯ or Ҷ on an official sign (single source: all from Wikipedia); weak for Ғ, Қ, Ҳ alone, which Uzbek Cyrillic also has
- Counterexamples: Tajik is also spoken by ethnic Tajiks in Uzbekistan (the standard language is based on the dialects of the Samarkand region); in Afghanistan the closely related Dari, and Tajik itself, are written in the Persian alphabet, not Cyrillic; a sign in Russian only says nothing
- Sources: en.wikipedia "Tajik alphabet" (Cyrillic letter table, Persian alphabet in Afghanistan), https://en.wikipedia.org/wiki/Tajik_alphabet; en.wikipedia "Tajik language" (spoken in Tajikistan and Uzbekistan; Samarkand dialects; Dari), https://en.wikipedia.org/wiki/Tajik_language; en.wikipedia "Uzbek alphabet", https://en.wikipedia.org/wiki/Uzbek_alphabet; en.wikipedia "Kyrgyz alphabets", https://en.wikipedia.org/wiki/Kyrgyz_alphabets; en.wikipedia "Kazakh alphabets", https://en.wikipedia.org/wiki/Kazakh_alphabets

### Four digits, two letters, region code at the right end (Tajikistan)
- Look for: a white plate with the flag and `TJ` at the **left**, then four digits, two letters and a two-digit region code at the right end, with no separate box for the code: `1234 AB 01` (companies `123 AB 01`)
- Points to: Tajikistan. Kazakhstan also has its flag at the left and its code at the right, but writes three digits and three letters (`123 ABC 01`) and puts the code in a square box; Uzbekistan and Kyrgyzstan put the region code at the left; Russia puts the code and flag at the right
- Strength: medium (the digit–letter pattern is readable before the country letters are)
- Counterexamples: older Kazakh non-private plates (`A 644 DC`, until 2012) also have two letters, but start with a region letter; Tajik plates of 1996–2010 look Russian, with the code over `RT` in a box at the right; read `TJ` or `KZ` when you can
- Sources: en.wikipedia "Vehicle registration plates of Tajikistan", section "2009/2014 Series", https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Tajikistan; en.wikipedia "Vehicle registration plates of Kazakhstan", https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Kazakhstan; ru.wikipedia "Индекс автомобильных номеров Таджикистана", https://ru.wikipedia.org/wiki/Индекс_автомобильных_номеров_Таджикистана

### Turkmen letters on signs
- Look for: Latin text with Ň, Ý or Ž next to Ä, Ç, Ş, Ö or Ü (`Türkmenistan`, `köçesi`, street, `şäheri`, city, `welaýaty`, province)
- Points to: Turkmenistan, where the Latin alphabet (in its 1999 form) is official. Ň, Ý and Ž are in none of the other Turkic Latin alphabets of the region: Turkish has Ç, Ş, Ö, Ü and Ğ but no Ä, Ň, Ý or Ž; Azerbaijani writes Ə, not Ä; Kazakh Latin writes Ñ, not Ň; Uzbek uses oʻ, gʻ, sh and ch
- Strength: medium for Ň or Ý together with Ş, Ç or Ä on an official sign (single source: all from Wikipedia)
- Counterexamples: Slovak also has Ä, Ň, Ý and Ž, and Czech Ň, Ý and Ž, but neither has Ş or Ç; Turkmen also has Cyrillic and Arabic-script alphabets, so Turkmen text outside Turkmenistan may not use these letters at all
- Sources: en.wikipedia "Turkmen alphabet" (letter table; 1993 alphabet, symbols replaced in 1999; official status), https://en.wikipedia.org/wiki/Turkmen_alphabet; en.wikipedia "Turkish alphabet", https://en.wikipedia.org/wiki/Turkish_alphabet; en.wikipedia "Azerbaijani alphabet", https://en.wikipedia.org/wiki/Azerbaijani_alphabet; en.wikipedia "Kazakh alphabets", https://en.wikipedia.org/wiki/Kazakh_alphabets; en.wikipedia "Slovak orthography", https://en.wikipedia.org/wiki/Slovak_orthography; en.wikipedia "Czech orthography", https://en.wikipedia.org/wiki/Czech_orthography

### Letters, four digits, letters, with no region number (Turkmenistan)
- Look for: a white plate with the flag and `TM` at the **left**, then two letters, four digits and two letters (`AB 1234 AG`), and no two-digit region number anywhere
- Points to: Turkmenistan, where the region is the two letters at the end (AG Ashgabat … MR Mary). Uzbekistan, Kyrgyzstan, Kazakhstan and Tajikistan all write a two-digit region number, and Russia a two- or three-digit number in a box at the right
- Strength: medium (the letter–digit–letter pattern is readable before the country letters are)
- Counterexamples: Turkmen plates before 2009–2010 have one letter at the start; green company and government plates read `1234 AGA`; yellow foreign-resident plates (`2H 50035`) look different again; read `TM` when you can
- Sources: en.wikipedia "Vehicle registration plates of Turkmenistan", section "Current series", https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Turkmenistan; ru.wikipedia "Индекс автомобильных номеров Туркмении", https://ru.wikipedia.org/wiki/Индекс_автомобильных_номеров_Туркмении; en.wikipedia "Vehicle registration plates of Uzbekistan", https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Uzbekistan; en.wikipedia "Vehicle registration plates of Kyrgyzstan", https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Kyrgyzstan; en.wikipedia "Vehicle registration plates of Kazakhstan", https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Kazakhstan; en.wikipedia "Vehicle registration plates of Tajikistan", https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Tajikistan
