# Uzbekistan clues

Entries use the shared format (`references/clues/README.md`). Only clues whose "Points to" stays inside Uzbekistan belong here; clues that tell Uzbekistan apart from Kazakhstan, Kyrgyzstan, Tajikistan or Turkmenistan go into `references/clues/global.md`.

## Text and numbers

### Region code in the box on the left of a plate
- Look for: on a white plate with the flag and `UZ` at the **right** end, the two digits in a separate box on the left: `01 A 123 BC` or `01 123 ABC` (format since 2008)
- Points to: the region where the vehicle was **registered** → `clues.py lookup plate <plate or two digits> --country uz`. Each region holds a range of codes: 01–09 Tashkent city, 10–19 Tashkent Region, 20–24 Sirdaryo, 25–29 Jizzakh, 30–39 Samarkand, 40–49 Fergana, 50–59 Namangan, 60–69 Andijan, 70–74 Qashqadaryo, 75–79 Surxondaryo, 80–84 Bukhara, 85–89 Navoiy, 90–94 Xorazm, 95–99 Karakalpakstan
- Strength: weak for where the photo was taken; medium when most parked cars in a quiet residential street share one range
- Counterexamples: plates stay with the car after a move; yellow `H` plates (foreign residents), green `M` plates (foreign companies) and green diplomatic plates use other schemes; the English Wikipedia table gives only the first code of each range, so a code such as 39 is missing there but not here
- Sources: ru.wikipedia "Индекс автомобильных номеров Узбекистана", section "Таблица кодов регионов", https://ru.wikipedia.org/wiki/Индекс_автомобильных_номеров_Узбекистана; uz.wikipedia "Oʻzbekiston avtomobil raqamlari indeksi", section "Hududlar boʻyicha raqamlar", https://uz.wikipedia.org/wiki/Oʻzbekiston_avtomobil_raqamlari_indeksi; en.wikipedia "Vehicle registration plates of Uzbekistan" (formats, special plates), https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Uzbekistan

### Plates of the 1998–2008 format
- Look for: an older plate with the two-digit code in a box on the left in **blue** digits, then a letter and four digits (private cars, `10 A 1234`) or two letters and three digits (companies, `30 AB 123`)
- Points to: the region of registration at the time → `clues.py lookup plate-1998 <plate> --country uz`; the codes then were 10 or 30 Tashkent city, 11 Tashkent Region, 12 Sirdaryo … 23 Karakalpakstan, which overlap today's ranges, so look the plate up under the format it shows
- Strength: weak (single source; old plates are on old cars that may have moved since)
- Counterexamples: misreading the format sends the code to the wrong table (10 is Tashkent city on an old plate, Tashkent Region on a new one); Russian plates of the same years also put a code in a separate box, but on the right
- Sources: ru.wikipedia "Индекс автомобильных номеров Узбекистана", sections "Галерея номерных знаков формата 1998–2008 годов" and "Таблица кодов регионов", https://ru.wikipedia.org/wiki/Индекс_автомобильных_номеров_Узбекистана

### Landline code on signs and vehicles
- Look for: a fixed-line number on a shop sign, banner or company van: nine digits, `71 123 45 67`, `(66) 233-45-67` or `+998 65 221 23 45`
- Points to: the region of that landline → `clues.py lookup area-code <number> --country uz`: 71 Tashkent city, 61 Karakalpakstan, 62 Xorazm, 65 Bukhara, 66 Samarkand, 67 Sirdaryo, 69 Namangan, 72 Jizzakh, 73 Fergana, 74 Andijan, 75 Qashqadaryo, 76 Surxondaryo, 79 Navoiy, 70 Tashkent Region
- Strength: medium (a shop's own landline is usually local)
- Counterexamples: most numbers on signs are mobile (90–99, 33, 50, 77, 88 …) and say nothing about the region; 70 is also listed as an Uzmobile mobile range, and 78 is a non-geographic fixed range used by companies across the country; 36 is not in the table: goldenpages.uz lists it for most of Navoiy Region, but the ITU numbering plan, Ucell's dialing guide and the 2015 conversion plan (0436 → 79) give 79, so a `36` number is left unscored until a dated operator or regulator source settles it; a chain's sign may show its Tashkent head office; numbers on signs older than 2018–2020 may still be in the seven-digit local format
- Sources: en.wikipedia "Telephone numbers in Uzbekistan", section "Area codes", https://en.wikipedia.org/wiki/Telephone_numbers_in_Uzbekistan; goldenpages.uz "Телефонные коды городов Узбекистана" (codes by settlement and district), https://www.goldenpages.uz/uzcodes/; goldenpages.uz prefix table, https://www.goldenpages.uz/phone/; ITU Operational Bulletin 1263, Uzbekistan numbering plan, https://www.ituob.org/issues/1263-en/; Ucell dialing guide, https://ucell.uz/ru/information/how_to_call; norma.uz "Телефонные номера станут девятизначными" (0436 → 79), https://www.norma.uz/nashi_obzori/telefonnye_nomera_stanut_devyatiznachnymi1

## Language and script

### Karakalpak letters on signs
- Look for: Latin letters with acute accents and a dotless i on official signs: á, ǵ, ń, ó, ú, ı (`wálayatı`, `Qaraqalpaqstan`), or Cyrillic Ә, Ө, Ү, Ң next to Ў and Қ
- Points to: the Republic of Karakalpakstan (Nukus and the north-west), where Karakalpak is official next to Uzbek
- Strength: medium for an official sign
- Counterexamples: Kazakh Cyrillic also has Ә Ө Ү Ң, but not Ў, so look for Ў or read the region name or the plate; a Uzbek-only sign does not exclude Karakalpakstan
- Sources: en.wikipedia "Karakalpak language" (official status, Latin–Cyrillic letter table); en.wikipedia "Kazakh alphabets" (no Ў in Kazakh Cyrillic), https://en.wikipedia.org/wiki/Kazakh_alphabets, https://en.wikipedia.org/wiki/Karakalpak_language

### Ö, Ğ, Ş, Ç in Uzbek words
- Look for: Uzbek words written with Ö, Ğ, Ş or Ç (`köçasi` for `koʻchasi`, street) instead of Oʻ, Gʻ, Sh and Ch
- Points to: a sign made after the 2026 alphabet law: it replaces Oʻ with Ö, Gʻ with Ğ, Sh with Ş and Ch with Ç, was approved on 21 October 2026 and comes into force on 22 April 2027. Older signs keep the 1995 spelling and are replaced gradually
- Strength: medium as a date (the earliest date for that sign); none as a place
- Counterexamples: the same letters are Turkish and Azerbaijani, so a Turkish shop or brand name is not an Uzbek sign; a 2021 draft already proposed Ŏ, Ğ, Ş and Ç, so a few signs may use them earlier
- Sources: en.wikipedia "Uzbek alphabet", sections on the 1995 alphabet and the 2026 reform, https://en.wikipedia.org/wiki/Uzbek_alphabet; The Times of Central Asia, "Uzbekistan alphabet reform" (old signs stay until they wear out), https://timesca.com/uzbekistan-alphabet-reform-latin-cyrillic/

### Public facility and civic service signage (institutions, utilities, and POIs)
- Look for: standard Uzbek institutional terms, numbered prefixes, and acronyms on entrance archways, facade plaques, and public signs:
  - Education: `X-sonli maktab` (or `X-maktab`, `umumiy o'rta ta'lim maktabi` — public school №X); `X-sonli bog'cha` (or `maktabgacha ta'lim tashkiloti` — kindergarten №X); `akademik litsey` (academic lyceum); `kasb-hunar maktabi` / `kollej` (vocational college); `universitet` / `institut` (higher education)
  - Healthcare: `shifoxona` (hospital / inpatient clinic); `X-sonli oilaviy poliklinika` (family outpatient clinic №X); `QVP` (`Qishloq vrachlik punkti` — rural medical post); `dorixona` (pharmacy); `tez tibbiy yordam` (ambulance service / 103)
  - Civic administration and community: `MFY` (`Mahalla fuqarolar yig'ini` — mahalla citizens' assembly/committee office, present in every neighborhood); `DXM` (`Davlat xizmatlari markazi` — public service center / one-stop government office); `hokimiyat` (`shahar/tuman hokimiyati` — city/district administration); `pochta` (`O'zbekiston pochtasi` — post office)
  - Law enforcement and emergency: `IIB` / `IIV` (`Ichki ishlar bo'limi` — police precinct / interior affairs); `YHXBB` / `YPX` (traffic police post); `FVB` / `yong'in xavfsizligi` (fire and rescue / 101)
  - Markets and transit: `dehqon bozori` (farmers' agricultural market); `buyum bozori` (clothing/goods bazaar); `avtovokzal` / `avtostansiya` (bus terminal); `temir yo'l vokzali` (railway station); `bekat` (public transit stop)
- Points to: formulating queries for OpenStreetMap (Nominatim/Overpass), search engines, or local gazetteers using the exact Uzbek naming patterns (`89-sonli maktab`, `3-sonli oilaviy poliklinika`, `Chorsu bozori`, `Rakat MFY`). Russian searches (`Школа №89`, `Поликлиника 3`, `Рынок Чорсу`) routinely yield 0 results in Uzbek OSM due to absence of Cyrillic `name:ru` tags, leading agents to falsely discard valid spatial evidence
- Strength: medium (resolves facility identification and prevents false negative query discarding; numbers require city or district context as numbers 1–50+ repeat across provinces)
- Counterexamples: private international schools or clinics may use branded English or Russian names (`Cambridge`, `Akfa Medline`); Russian signage remains in older Tashkent commercial districts, but municipal databases still index under the official Uzbek state title
- Sources: Lex.uz "O‘zbekiston Respublikasining davlat tili haqida" (State Language Law on official signage), https://lex.uz/docs/108915; OpenStreetMap Wiki "Uzbekistan/Tagging guidelines for public facilities and education", https://wiki.openstreetmap.org/wiki/Uzbekistan; Lex.uz "Mahalla fuqarolar yig'inlari to'g'risidagi qonun", https://lex.uz/docs/2154477

## Roads and transport

### Kamchik Pass corridor (A373)
- Look for: an electrified railway line with tunnels or a double-lane mountain highway winding through steep, arid rocky gorges with concrete avalanche galleries, snow sheds, retaining walls, heavy truck traffic, or police checkpoint gates with barrier gantries
- Points to: the Kamchik Pass (A373 highway and Angren–Pap railway line), linking Tashkent Region (Ohangaron/Angren) with Namangan and the Fergana Valley through the Qurama and Chatkal ranges
- Strength: strong (the only direct overland road corridor between the Fergana Valley and the rest of Uzbekistan)
- Counterexamples: other mountain roads exist in Surxondaryo (Baysun/Derbent canyon) or Jizzax/Samarqand (Takhtakaracha pass on M39 between Samarqand and Shahrisabz), but Takhtakaracha has narrower roads and no heavy transit freight or snow galleries comparable to A373; border checkpoints with Kyrgyzstan or Tajikistan also have inspection gantries
- Sources: en.wikipedia "Kamchik Pass", https://en.wikipedia.org/wiki/Kamchik_Pass; en.wikipedia "Angren–Pap railway line", https://en.wikipedia.org/wiki/Angren–Pap_railway_line; en.wikipedia "A373 road (Uzbekistan)", https://en.wikipedia.org/wiki/A373_road_(Uzbekistan)

## Public transport

### Metro stations
- Look for: a metro station, metro trains, or an elevated metro line on a viaduct
- Points to: Tashkent: it has the country's only metro (4 lines, 50 stations). The Circle (Halqa) line, opened in stages since 2020, runs almost entirely on elevated overpasses (50.5 of 52.1 km when complete), and the Yunusobod line reached Turkiston and Yunusobod stations on 29 August 2020
- Strength: medium for a station interior (single source)
- Counterexamples: Almaty (Kazakhstan) also has a metro; a station sign in Uzbek Latin or Cyrillic separates them
- Sources: en.wikipedia "Tashkent Metro" (lines, stations, opening dates, Circle line overpasses), https://en.wikipedia.org/wiki/Tashkent_Metro

## Landscape and architecture

### Traditional earthen duval walls in historic mahallas
- Look for: tall, continuous windowless perimeter walls made of dried mud brick or packed clay (pakhsa/duval), wooden carved entry gates (darvoza), narrow winding unpaved or cobblestone alleys between blank earthen facades, with flat roofs and poplars behind the walls
- Points to: historical mahallas in ancient oasis cities: Bukhara, Khiva (Ichan Kala and surrounding Ditshan Kala), Samarqand, Shahrisabz, or older traditional parts of Fergana Valley towns
- Strength: medium (points to an oasis historic settlement in Central Asia)
- Counterexamples: modern suburban mahallas across all regions use fired red brick or cinderblocks and corrugated metal roofs; rural adobe compounds also exist across southern Kazakhstan, southern Kyrgyzstan and Tajikistan
- Sources: en.wikipedia "Mahalla", https://en.wikipedia.org/wiki/Mahalla; en.wikipedia "Itchan Kala", https://en.wikipedia.org/wiki/Itchan_Kala; en.wikipedia "Historic Centre of Bukhara", https://en.wikipedia.org/wiki/Historic_Centre_of_Bukhara

## Time and sun

### One time zone, no daylight saving time
- Look for: a time from EXIF, a watermark or a visible clock, used with `sun.py`
- Points to: the whole country is on UTC+5 all year; it has used no daylight saving time since the single zone was adopted in 1991. Pass `+05:00` for any date since then
- Strength: — (it settles the offset for `sun.py`, not the place)
- Counterexamples: cameras whose clock was never set or stayed on the owner's home zone; Kazakhstan next door has also been on UTC+5 since 1 March 2024, so the clock does not tell the two apart
- Sources: en.wikipedia "Time in Uzbekistan", https://en.wikipedia.org/wiki/Time_in_Uzbekistan; en.wikipedia "Time in Kazakhstan" (single UTC+5 zone since 1 March 2024), https://en.wikipedia.org/wiki/Time_in_Kazakhstan

## Coverage

### Yandex panoramas, not Google Street View, for comparison
- Look for: nothing in the photo; this is about what you compare it with
- Points to: Yandex Maps published street panoramas of most of Tashkent, Samarkand, Bukhara, Khiva and Nukus in December 2019 (more than 73,000 panoramas), and re-shot Tashkent in 2026 (about 130,000 panoramas over 3,400 km of streets). No core script reads Yandex panoramas, so check `gsv.py` first and open Yandex panoramas by hand for these cities
- Strength: — (a search-planning note, not a clue)
- Counterexamples: Google Street View coverage of Uzbekistan could not be confirmed when this pack was written, so `gsv.py` may return nothing; outside these five cities, compare with satellite imagery or `terrain.py view` ridgelines instead
- Sources: Fergana Agency, "Uzbek city panoramas now available on Yandex Maps", https://en.fergana.agency/news/113393/; Kun.uz, "Панорамы Узбекистана появились на Яндекс.Картах" (13 December 2019), https://kun.uz/ru/news/2019/12/13/panoramy-uzbekistana-poyavilis-na-yandekskartax; UzDaily, "Yandex Maps updates street panoramas of Tashkent", https://www.uzdaily.uz/en/yandex-maps-updates-street-panoramas-of-tashkent/
