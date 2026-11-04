# Kyrgyzstan clues

Entries use the shared format (`references/clues/README.md`). Only clues whose "Points to" stays inside Kyrgyzstan belong here; clues that tell Kyrgyzstan apart from Kazakhstan, Uzbekistan, Tajikistan or China go into `references/clues/global.md`.

## Text and numbers

### Region code at the left of a plate
- Look for: a white plate with black characters, a two-digit code at the **left** end with the flag and `KG` under it, then three digits and three letters: `01 123 ABC` (format since June 2016); motorcycles `01 123 AB`, government vehicles `01 123 PT`; green-marked plates for electric cars since August 2024
- Points to: the region where the vehicle was **registered** → `clues.py lookup plate <plate or two digits> --country kg`: 01 Bishkek, 02 Osh city, 03 Batken, 04 Jalal-Abad, 05 Naryn, 06 Osh Region, 07 Talas, 08 Chüy, 09 Issyk-Kul
- Strength: weak for where the photo was taken; medium when most parked cars in a quiet residential street share one code
- Counterexamples: plates stay with the car after a move, and many cars from all regions are registered in Bishkek; 10 is given to cars legalized since 2025 (mostly right-hand-drive cars that had Armenian or Russian plates) and 11 to temporary registrations, neither is a region; yellow plates with four digits and one letter (`01 1234 H`, foreign residents and companies) and red diplomatic or blue UN plates (`D 01 123`) follow other schemes; ru.wikipedia says the flag and the region code swapped places in September 2025, which I could not confirm elsewhere, so read the code by its two digits, not by its position
- Sources: en.wikipedia "Vehicle registration plates of Kyrgyzstan", sections "Formats" and "Region identifiers", https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Kyrgyzstan; ru.wikipedia "Индекс автомобильных номеров Кыргызстана", sections "История" and "Коды", https://ru.wikipedia.org/wiki/Индекс_автомобильных_номеров_Кыргызстана; Kaktus.media "«Унаа» начала выдавать номера 11-го региона", https://kaktus.media/doc/542163_ynaa_nachala_vydavat_nomera_11_go_regiona.html

### Plates of the 1994–2016 format
- Look for: the flag in a narrow band at the left end, then a Latin letter, four digits and one or two letters (`B 1234 AB`; one letter at the end before about 2008–2009); company plates of the same years put the four digits first (`1234 BA`)
- Points to: the region of registration at the time → `clues.py lookup plate-1994 <plate or letter> --country kg`: A Batken, B (and E, F) Bishkek, C or S Chüy, D Jalal-Abad, I Issyk-Kul, N (earlier H) Naryn, T Talas, O and Z Osh city and Osh Region; on company plates the first of the two letters is the region letter
- Strength: weak (old plates are on old cars that may have moved since); medium as a date: a car with this plate was registered before June 2016
- Counterexamples: the two Wikipedia articles swap O and Z (en: O Osh city, Z Osh Region; ru: the reverse), so the lookup returns both; E is "Bishkek outskirts" in en.wikipedia and "Bishkek, about 2004–2008" in ru.wikipedia, and F (non-residents) is in ru.wikipedia only; the issue and replacement of these plates stopped on 24 July 2025, but plates already on cars stay; personalised plates (2–7 characters, first two letters) have no region
- Sources: en.wikipedia "Vehicle registration plates of Kyrgyzstan", sections "1994" and "1994-2016", https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Kyrgyzstan; ru.wikipedia "Индекс автомобильных номеров Кыргызстана", sections "Типы выдаваемых номерных знаков" and "Коды", https://ru.wikipedia.org/wiki/Индекс_автомобильных_номеров_Кыргызстана; Akchabar "С 24 июля в Кыргызстане прекращается регистрация номеров старого образца", https://www.akchabar.kg/en/news/s-24-iyulya-v-kirgizstane-prekrashchaetsya-registratsiya-nomerov-starogo-obraztsa-wwwjinjpvlmvwvin

### Landline code on signs and vehicles
- Look for: a fixed-line number on a shop sign, banner or company van: `0312 12-34-56` in Bishkek, `(03922) 5-12-34` or `+996 3922 51234` elsewhere
- Points to: the region of that landline → `clues.py lookup area-code <number without the leading 0> --country kg`: 312 Bishkek, 31xx Chüy, 3222 Osh city, 32xx Osh Region, 34xx Talas, 35xx Naryn, 36xx Batken, 37xx Jalal-Abad, 39xx Issyk-Kul (3922 Karakol)
- Strength: medium (a shop's own landline is usually local)
- Counterexamples: most numbers on signs are mobile (50X, 55X, 70X, 77X, 99X, 22X …) and say nothing about the region; 6XX numbers are fixed but have no place; both sources put 3765 (Kara-Kulja) in the Jalal-Abad block although Kara-Kulja district is in Osh Region, so the lookup returns both; a chain's sign may show its Bishkek head office
- Sources: en.wikipedia "Telephone numbers in Kyrgyzstan", section "National Numbering Plan (NNP) of the Kyrgyz Republic", https://en.wikipedia.org/wiki/Telephone_numbers_in_Kyrgyzstan; ru.wikipedia "Телефонный план нумерации Кыргызстана", https://ru.wikipedia.org/wiki/Телефонный_план_нумерации_Кыргызстана

## Language and script

### Uzbek text in the south
- Look for: shop signs or banners in Uzbek (Latin oʻ, gʻ, or Cyrillic Ў, Қ, Ҳ) next to Kyrgyz and Russian
- Points to: the south: Osh, Jalal-Abad and Özgön, where most of Kyrgyzstan's Uzbeks (about 15% of the population, the largest minority) live
- Strength: weak to medium (one Uzbek sign can be anywhere; several in a residential street point south)
- Counterexamples: Uzbekistan itself is a few kilometres from Osh and Jalal-Abad, so check the plate (two-digit code at the left with `KG`, or the Kyrgyz letters Ң, Ү, Ө) before you place the photo in Kyrgyzstan; Batken Region also borders Uzbekistan and Tajikistan
- Sources: en.wikipedia "Uzbeks in Kyrgyzstan", https://en.wikipedia.org/wiki/Uzbeks_in_Kyrgyzstan; en.wikipedia "Kyrgyz alphabets" (Ң, Ү, Ө as the three extra Cyrillic letters), https://en.wikipedia.org/wiki/Kyrgyz_alphabets

## Dating

### National flag with straight rays
- Look for: the red flag with the yellow sun: forty **straight** rays and four crossed lines in each direction over the centre (the yurt crown), instead of forty wavy rays and three lines
- Points to: a flag made after the change of 26 December 2023; the flag of 1992–2023 has wavy rays
- Strength: medium as a date (the earliest date for that flag); none as a place
- Counterexamples: old flags stay up on poles, plates, painted walls and signs for years, so a wavy-ray flag does not prove a photo is older than 2024; at a distance the two suns look alike
- Sources: en.wikipedia "Flag of Kyrgyzstan", sections "History" and "2023 change", https://en.wikipedia.org/wiki/Flag_of_Kyrgyzstan

### Trolleybuses
- Look for: trolleybuses or their overhead wires in a city street
- Points to: Osh (the only system still running, since 1977) for a recent photo; a trolleybus in Bishkek dates the photo before 3 November 2024, one in Naryn before 31 May 2024
- Strength: medium
- Counterexamples: overhead wires can stay after a system closes (Naryn's were due to be taken down in summer 2025); Balykchy has trolleybus wiring that was never used
- Sources: en.wikipedia "List of trolleybus systems", section "Kyrgyzstan", https://en.wikipedia.org/wiki/List_of_trolleybus_systems

## Sun and time

### One time zone, UTC+6
- Look for: a clock, timestamp or shadow you want to compare with the sun (`sun.py`)
- Points to: the whole country is on UTC+6 (Asia/Bishkek) without daylight saving since 12 August 2005; from 1991 to 2005 it was UTC+5 with summer time
- Strength: — (a setting for `sun.py`, not a place clue)
- Counterexamples: photos from before August 2005 use the older offset; EXIF clocks are often wrong
- Sources: en.wikipedia "Kyrgyzstan Time", section "History", https://en.wikipedia.org/wiki/Kyrgyzstan_Time

## Imagery

### Google Street View coverage
- Look for: a matching place on Google Street View
- Points to: Kyrgyzstan has had public Street View since May 2016, the first country in Central Asia, with Bishkek, Jalal-Abad, Osh, Naryn, Karakol and more places → `gsv.py` for comparison
- Strength: — (a comparison source)
- Counterexamples: coverage of mountain roads and villages is thin, and the imagery may be years old (before the 2024 trolleybus closures and the 2023 flag)
- Sources: en.wikipedia "Google Street View coverage", sections "2016" and the country table, https://en.wikipedia.org/wiki/Google_Street_View_coverage
