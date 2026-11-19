# Uzbekistan clues

Entries use the shared format (`references/clues/README.md`). Only clues whose "Points to" stays inside Uzbekistan belong here; clues that tell Uzbekistan apart from Kyrgyzstan, Kazakhstan, Tajikistan or Turkmenistan go into `references/clues/global.md`. Sources checked on 2026-11-13.

## Text and plates

### Region code at the left of a plate
- Look for: a white plate with black characters, a two-digit code in a box at the **left** end, then either one letter, three digits and two letters (`01 A 123 BC` private) or three digits and three letters (`01 123 ABC` commercial/legal entities), with the Uzbekistan flag and `UZ` at the right end; green band or green characters on electric vehicle plates since 2021
- Points to: the province or city where the vehicle was **registered** → `clues.py lookup plate <plate or two digits> --country uz`: 01–09 Tashkent city, 10–19 Tashkent Region, 20–24 Syrdarya, 25–29 Jizzakh, 30–39 Samarkand, 40–49 Fergana, 50–59 Namangan, 60–69 Andijan, 70–74 Kashkadarya, 75–79 Surkhandarya, 80–84 Bukhara, 85–89 Navoiy, 90–94 Khorezm, 95–99 Karakalpakstan
- Strength: weak for a moving vehicle; medium when most parked vehicles in a quiet street or residential area share the same code
- Counterexamples: cars frequently travel between provinces; Tashkent city (01) has many cars from all regions; older plates issued before October 2008 had a different layout with blue region digits on the left; yellow plates for foreign residents/companies (`01 H 123456`) and specialized green, blue or red plates for state or diplomatic services follow separate numbering; Kyrgyzstan, Kazakhstan and Russia also use two-digit region codes, so check the flag and `UZ` at the right end
- Sources: en.wikipedia "Vehicle registration plates of Uzbekistan", https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Uzbekistan; ru.wikipedia "Индекс автомобильных номеров Узбекистана", https://ru.wikipedia.org/wiki/Индекс_автомобильных_номеров_Узбекистана; Lex.uz "Vazirlar Mahkamasining 2007-yil 27-iyundagi 131-son qarori", https://lex.uz/docs/1218774

### Landline area code on signs and advertising
- Look for: a fixed-line telephone number on a shop sign, billboard, banner or company vehicle: `(71) 123-45-67`, `+998 71 123 45 67`, `78 150-xx-xx`, `(66) 234-xx-xx`
- Points to: the province or city of that landline → `clues.py lookup area-code <number> --country uz`: 71 Tashkent city and suburban districts, 70 Tashkent Region, 78 Tashkent commercial/alternative networks, 66 Samarkand, 73 Fergana, 74 Andijan, 69 Namangan, 65 Bukhara, 61 Karakalpakstan (Nukus), 62 Khorezm (Urgench), 75 Kashkadarya, 76 Surkhandarya, 72 Jizzakh, 67 Syrdarya, 79 Navoiy
- Strength: medium (a business's landline is usually local)
- Counterexamples: most numbers on signs are mobile (90, 91 Beeline; 93, 94, 55 Ucell; 97, 88 Mobiuz; 99, 95, 77 Uzmobile; 33 Humans) and carry no geographic information; national hotlines or Tashkent company headquarters often advertise nationwide with a 71 or 78 number
- Sources: en.wikipedia "Telephone numbers in Uzbekistan", https://en.wikipedia.org/wiki/Telephone_numbers_in_Uzbekistan; ru.wikipedia "Телефонный план нумерации Узбекистана", https://ru.wikipedia.org/wiki/Телефонный_план_нумерации_Узбекистана; Goldenpages.uz "Телефонные коды городов Узбекистана", https://www.goldenpages.uz/spravka/phone_codes/

## Language and script

### Karakalpak language and signage in Karakalpakstan
- Look for: bilingual public signs with Karakalpak text alongside Uzbek and Russian: Latin text with letters *á, ó, ú, ı, ǵ, ń* (`Qaraqalpaqstan`, `qalası`, `rayonı`, `respublikası`), or Cyrillic with *ә, ө, ү, і, ғ, ң, ҳ, қ*; blue-yellow-green Karakalpak republican flags; references to Nukus, Moynaq, Kungrad, Chimbay or Beruniy
- Points to: the Republic of Karakalpakstan (Qoraqalpogʻiston Respublikasi), western Uzbekistan
- Strength: strong for official Karakalpak Latin/Cyrillic signage or institutional names; medium for commercial signage
- Counterexamples: Karakalpak diaspora exists elsewhere, but public and administrative signage in Karakalpak is exclusive to Karakalpakstan; Kazakh also has *ә, ө, ү, і, ғ, ң*, but Kazakh in Uzbekistan uses Cyrillic without Karakalpak government seals, and Kazakhstani border areas differ in vehicle plates (`KZ`)
- Sources: en.wikipedia "Karakalpak language", https://en.wikipedia.org/wiki/Karakalpak_language; en.wikipedia "Karakalpakstan", https://en.wikipedia.org/wiki/Karakalpakstan; Constitution of the Republic of Karakalpakstan, Article 4, https://karakalpakstan.uz/en/page/show/4

## Roads and transport

### Kamchik Pass corridor (A373)
- Look for: an electrified railway tunnel or double-lane mountain highway winding through steep, arid rocky gorges with concrete avalanche galleries, snow sheds, retaining walls, heavy truck traffic, or police checkpoint gates with barrier gantries
- Points to: the Kamchik Pass (A373 highway and Angren–Pap railway line), linking Tashkent Region (Ohangaron/Angren) with Namangan/Fergana Valley through the Qurama and Chatkal ranges
- Strength: strong (the only direct overland corridor between the Fergana Valley and the rest of Uzbekistan)
- Counterexamples: other mountain roads exist in Surkhandarya (Baysun/Derbent canyon) or Jizzakh/Samarkand (Takhtakaracha pass on M39 between Samarkand and Shahrisabz), but Takhtakaracha has narrower roads and no heavy transit freight or snow galleries comparable to A373; border checkpoints with Kyrgyzstan or Tajikistan also have inspection gantries
- Sources: en.wikipedia "Kamchik Pass", https://en.wikipedia.org/wiki/Kamchik_Pass; en.wikipedia "Angren–Pap railway line", https://en.wikipedia.org/wiki/Angren–Pap_railway_line; en.wikipedia "A373 road (Uzbekistan)", https://en.wikipedia.org/wiki/A373_road_(Uzbekistan)

## Landscape and architecture

### Traditional earthen duval walls in historic mahallas
- Look for: tall, continuous windowless perimeter walls made of dried mud brick or packed clay (pakhsa/duval), wooden carved entry gates (darvoza), narrow winding unpaved or cobblestone alleys between blank earthen facades, with flat roofs and poplars behind the walls
- Points to: historical mahallas in ancient oasis cities: Bukhara, Khiva (Ichan Kala and surrounding Ditshan Kala), Samarkand, Shahrisabz, or older traditional parts of Fergana Valley towns
- Strength: medium (points to an oasis historic settlement in Central Asia)
- Counterexamples: modern suburban mahallas across all regions use fired red brick or cinderblocks and corrugated metal roofs; rural adobe compounds also exist across southern Kazakhstan, southern Kyrgyzstan and Tajikistan
- Sources: en.wikipedia "Mahalla", https://en.wikipedia.org/wiki/Mahalla; en.wikipedia "Itchan Kala", https://en.wikipedia.org/wiki/Itchan_Kala; en.wikipedia "Historic Centre of Bukhara", https://en.wikipedia.org/wiki/Historic_Centre_of_Bukhara

### Yellow above-ground residential gas piping
- Look for: bright yellow steel pipes mounted on tall metal poles running along the sidewalk or roadside, looping high over driveways and courtyard gates into residential houses
- Points to: residential areas with gas infrastructure in Uzbekistan and neighboring post-Soviet Central Asian countries
- Strength: weak for a specific region; useful as a confirmation of a residential street in an urban/suburban gasified settlement
- Counterexamples: yellow above-ground gas distribution pipes are also standard in Russia, Kazakhstan, Azerbaijan and Kyrgyzstan; industrial pipelines or unpainted utility pipes do not indicate household gas networks
- Sources: en.wikipedia "Natural gas in Uzbekistan", https://en.wikipedia.org/wiki/Natural_gas_in_Uzbekistan
