# Russia clues

Entries use the shared format (`references/clues/README.md`). Only clues whose "Points to" stays inside Russia belong here; clues that tell Russia apart from Belarus, Kazakhstan or Ukraine go into `references/clues/global.md`.

## Text and numbers

### Region code on a number plate
- Look for: on a white plate with one letter, three digits and two letters (`А 123 ВС`), the two or three digits in the separate field on the right, above `RUS` and the flag (`77`, `799`). The letters are only the 12 Cyrillic letters that look like Latin ones (А В Е К М Н О Р С Т У Х)
- Points to: the federal subject where the vehicle was **registered** → `clues.py lookup plate <digits> --country ru` or `board.py apply --kind plate --value <digits>`; type only the digits on the right, not the whole plate
- Strength: weak for where the photo was taken; medium when most parked cars in a quiet residential street share one code
- Counterexamples: plates stay with the car after a move; company cars are registered where the company is, and Moscow alone has eleven codes (77, 97, 99, 177 … 997); code 82 was issued in about a dozen other regions in 2016–2017 because of a number shortage; 80, 81, 82, 84 and 85 also survive on old plates of autonomous okrugs merged into neighbouring regions (the lookup lists both places); a three-digit code missing from the table falls back to its first two digits, which is usually another region; route buses (yellow), trailers, military (black) and diplomatic (red) plates use other formats
- Sources: ru.wikipedia "Регистрационные знаки транспортных средств в России", sections "Формат" (12 letters, 1-3-2 pattern) and "Код региона регистрации" (codes, dates, code 82 outside Crimea), https://ru.wikipedia.org/wiki/Регистрационные_знаки_транспортных_средств_в_России; ru.wikipedia "Коды субъектов Российской Федерации" (plate code per subject, earlier owners of reused codes), https://ru.wikipedia.org/wiki/Коды_субъектов_Российской_Федерации

### Landline zone on signs and vehicles
- Look for: a fixed-line number on a shop sign, banner or company van, written `8 (495) 123-45-67`, `+7 (8552) 12-34-56` or `8-3812-12-34-56`
- Points to: the federal subject of that landline → `clues.py lookup area-code <8 + ten digits> --country ru` (write `+7` as `8`); 495 is shared by Moscow and its nearest suburbs, 818 by Arkhangelsk Oblast and the Nenets Okrug, and some subjects have a second zone for one city (855 Naberezhnye Chelny, 862 Sochi, 848 Tolyatti, 820 Cherepovets)
- Strength: medium (a shop's own landline is usually local)
- Counterexamples: numbers starting 9 are mobile and say nothing about the region; 8-800 is toll-free; a chain's sign may show the head office (often Moscow); +7 is shared with Kazakhstan, whose zones start with 7 (look it up with `--country kz`); the zones for occupied Zaporizhzhia (810) and Kherson (860) come from one source only
- Sources: ru.wikipedia "Телефонный план нумерации России", section "Список географических кодов зоны" (citing Приказ Минцифры России от 31.01.2022 № 75), https://ru.wikipedia.org/wiki/Телефонный_план_нумерации_России

### Regional road number with a region prefix
- Look for: a road number such as `47К-021`, `46Н-1234` or `71-100К-27` on a route sign, kilometre post or road-works board, or in OSM `ref` tags along the road
- Points to: the leading digits are the federal subject's **OKATO** code, not its plate code (46 = Moscow Oblast, 47 = Murmansk Oblast) → `clues.py lookup road <number> --country ru`; then find the road with `osm.py along --line '["highway"]["ref"="47К-021"]' --step 1000`. The letter after the code is the class: Р and А regional roads, К other regional roads, Н intermunicipal roads. The Nenets, Khanty-Mansi and Yamalo-Nenets okrugs use five digits (`11-100`, `71-100`, `71-140`)
- Strength: strong when the sign stands on the road itself (one road, one region)
- Counterexamples: federal roads (`М-11`, `Р-255`, `А-289`) carry no region code, and several were renumbered (R255 is the former M53, R258 the former M55), so old signs survive; OSM writes the class letter in Cyrillic (`47К`), so a Latin `47K` in an Overpass query finds nothing; some roads inside today's Moscow city limits still carry Moscow Oblast's 46 in OSM; a direction sign at a junction can name a road that starts in the next region
- Sources: en.wikipedia "Russian federal highways", sections "Roads of regional and intermunicipal importance" (OKATO prefix, letter classes) and "Former routes", https://en.wikipedia.org/wiki/Russian_federal_highways; ru.wikipedia "Коды субъектов Российской Федерации" (OKATO code per subject), https://ru.wikipedia.org/wiki/Коды_субъектов_Российской_Федерации; OSM `ref` tags checked on 2026-11-01 in Murmansk Oblast (`47К-…`), Crimea (`35К-…`), Sevastopol (`67К-…`), the Nenets (`11-100К-…`), Khanty-Mansi (`71-100К-…`) and Yamalo-Nenets (`71-140Р-…`) okrugs, and Moscow city (`46Н-…`)

## Language and religion

### Letters of a republic's own language on official signs
- Look for: Cyrillic letters that Russian does not use on official signs, street-name plates or government buildings, usually next to the Russian text
- Points to: the republic whose language is co-official there: Ӑ Ӗ Ӳ → Chuvashia; Ҙ Ҡ Ҫ (with Ғ) → Bashkortostan; Ҕ Ҥ → Sakha (Yakutia); Җ with Ә Ң Ө Ү Һ → Tatarstan (Kalmyk uses the same extra letters, so also Kalmykia); only Ң Ө Ү → Tuva; only Ө Ү Һ → Buryatia. Kazakh letters Қ Ұ І point to Kazakhstan instead
- Strength: strong for an official bilingual sign; medium for a private sign
- Counterexamples: Tatar, Bashkir and Chuvash speakers also live in neighbouring regions, so a shop or mosque sign can carry the language outside its republic; the smaller sets (Ө Ү Һ, Ң Ө Ү) overlap with each other and with Mongolian Cyrillic; OCR may read Ҫ as С and Ә as Э, so check the letters by eye
- Sources: en.wikipedia "Languages of Russia", section "Official languages" (Tatar, Bashkir, Chuvash, Yakut, Tuvan, Buryat, Kalmyk by republic), https://en.wikipedia.org/wiki/Languages_of_Russia; en.wikipedia "Tatar alphabets", https://en.wikipedia.org/wiki/Tatar_alphabets; en.wikipedia "Bashkir alphabet", https://en.wikipedia.org/wiki/Bashkir_alphabet; en.wikipedia "Chuvash language", https://en.wikipedia.org/wiki/Chuvash_language; en.wikipedia "Yakut language", https://en.wikipedia.org/wiki/Yakut_language; en.wikipedia "Kalmyk Oirat", https://en.wikipedia.org/wiki/Kalmyk_Oirat; en.wikipedia "Tuvan language", https://en.wikipedia.org/wiki/Tuvan_language; en.wikipedia "Buryat language", https://en.wikipedia.org/wiki/Buryat_language

### Buddhist temples, stupas and prayer flags
- Look for: a datsan (Tibetan-style temple), white stupas, prayer wheels or prayer flags
- Points to: Buryatia, Tuva or Kalmykia, the three republics where Buddhism is traditional (62% of Tuva, 48% of Kalmykia and 20% of Buryatia in 2012); also Zabaykalsky Krai, east of Lake Baikal
- Strength: medium
- Counterexamples: single temples stand far from these regions, such as the Datsan Gunzechoinei in Saint Petersburg; Mongolia across the border looks very similar
- Sources: en.wikipedia "Buddhism in Russia" (2012 shares for Tuva, Kalmykia and Buryatia; Transbaikalia; Datsan Gunzechoinei), https://en.wikipedia.org/wiki/Buddhism_in_Russia

### Mosques in villages and small towns
- Look for: a mosque with a minaret in a village or a small town, more than one per settlement
- Points to: Tatarstan and Bashkortostan, where Muslims are the majority, or the North Caucasus republics (Dagestan, Chechnya, Ingushetia, Kabardino-Balkaria, Karachay-Cherkessia)
- Strength: weak (a population mix, not a place)
- Counterexamples: large cities everywhere have mosques, and Moscow is among the regions with the most Muslims; Tatar and Bashkir villages also lie outside their republics
- Sources: en.wikipedia "Islam in Russia" (majority in Tatarstan and Bashkortostan, predominant in the North Caucasian Federal District; Moscow among the main regions), https://en.wikipedia.org/wiki/Islam_in_Russia

## Time and sun

### Clock time and the changes of 2011–2020
- Look for: a time from EXIF, a watermark or a visible clock, used with `sun.py`
- Points to: Russia has 11 zones from UTC+2 (Kaliningrad) to UTC+12 (Kamchatka, Chukotka) and no daylight saving time since 26 October 2014. From 27 March 2011 to 26 October 2014 the clocks stayed on summer time all year (Moscow UTC+4). Regional offsets then changed: on 27 March 2016 Astrakhan and Ulyanovsk (to UTC+4), Altai Krai and the Altai Republic (to UTC+7), Zabaykalsky Krai (to UTC+9) and Sakhalin (to UTC+11); Magadan on 24 April 2016 (UTC+11), Tomsk on 29 May 2016 and Novosibirsk on 24 July 2016 (UTC+7), Saratov on 4 December 2016 (UTC+4); Volgograd used UTC+4 from 28 October 2018 to 27 December 2020. Pass the offset that matches the date and the candidate region; a one-hour error shifts the sun's hour angle by 15°
- Strength: medium (it decides whether a sun computation is right, not where the photo is)
- Counterexamples: phones with an outdated time-zone database around a change; cameras whose clock was never set or stayed on the owner's home zone; Russian Railways timetables followed Moscow time until 2018; Sakha spans three zones and Sakhalin's Severo-Kurilsky District differs from the rest of the oblast
- Sources: en.wikipedia "Time in Russia" (zone table since 27 December 2020; 2011, 2014, 2016, 2018 and 2020 changes), https://en.wikipedia.org/wiki/Time_in_Russia

## Public transport

### Metro stations
- Look for: an underground station with a metro logo, platform signs or rolling stock of a metro
- Points to: one of the seven cities with a metro: Moscow, Saint Petersburg, Nizhny Novgorod, Novosibirsk, Samara, Yekaterinburg, Kazan
- Strength: strong for a station interior (the list is short and closed); then compare station names with OSM (`poi.py`)
- Counterexamples: Volgograd's Metrotram is a light-rail line with a tunnel section and underground stations, which look like a metro
- Sources: en.wikipedia "List of metro systems", Russia rows, https://en.wikipedia.org/wiki/List_of_metro_systems; en.wikipedia "Volgograd Metrotram" (22 stations, surface and tunnel sections), https://en.wikipedia.org/wiki/Volgograd_Metrotram

## Annexed territories

### Russian plates and codes in Crimea and in occupied Ukrainian regions
- Look for: Russian-format plates with codes 82 or 92, or 80, 81, 84, 85 and 180–185; Russian phone zones 365, 869, 856, 857; regional road numbers starting 35 or 67
- Points to: Crimea and Sevastopol (Russian plates since June 2014, after code 777 was issued there from March to July 2014) or the Russian-occupied parts of Donetsk, Luhansk, Zaporizhzhia and Kherson oblasts of Ukraine (Russian codes since October 2022). The lookups name the OSM areas: Республика Крым and Севастополь, which OSM maps inside Russia's boundary, and Донецька, Луганська, Запорізька and Херсонська область, which OSM maps in Ukraine. A Russian plate also dates a photo there after the code was introduced
- Strength: medium (plates move with cars, but these codes are issued nowhere else today except 82 and the 2016–2017 shortage series)
- Counterexamples: before 2022 the self-proclaimed Donetsk and Luhansk "republics" issued their own plates in a similar format; 80–85 also survive on old plates from merged autonomous okrugs in Siberia and the Far East; code 188 was issued in occupied Kharkiv Oblast only in August 2022; ISO 3166-2 and most UN members treat all of these areas as Ukraine
- Sources: ru.wikipedia "Коды субъектов Российской Федерации" (codes and the note on non-recognition), https://ru.wikipedia.org/wiki/Коды_субъектов_Российской_Федерации; ru.wikipedia "Регистрационные знаки транспортных средств в России" (code 92 since 24 June 2014, 777 in Crimea March–July 2014, 188), https://ru.wikipedia.org/wiki/Регистрационные_знаки_транспортных_средств_в_России; RBC, "МВД опубликовало коды автомобильных номеров для новых субъектов России" (5 October 2022), https://www.rbc.ru/politics/05/10/2022/633d60ac9a794704e61519d5; ru.wikipedia "Телефонный план нумерации России" (zones 365, 869, 856, 857), https://ru.wikipedia.org/wiki/Телефонный_план_нумерации_России

## Coverage

### Street-level imagery to compare with
- Look for: nothing in the photo; this is about what you compare it with
- Points to: Google Street View in Russia has public coverage, but it was "museum view only" until 2012 and was added city by city afterwards; Yandex Maps publishes its own street panoramas, shot by Yandex cars. No core script reads Yandex panoramas, so `gsv.py` is the pack's street-view service: check coverage there first and open Yandex panoramas by hand where it is thin
- Strength: — (a search-planning note, not a clue)
- Counterexamples: coverage dates vary a lot between cities, so an old panorama may show a street before renovation; rural roads may have neither, so confirm with `terrain.py view` ridgelines or satellite imagery instead
- Sources: en.wikipedia "Google Street View coverage" (Russia: public coverage, museum view only until 2012; 2012–2013 additions), https://en.wikipedia.org/wiki/Google_Street_View_coverage; en.wikipedia "Yandex Maps" (street panoramas), https://en.wikipedia.org/wiki/Yandex_Maps
