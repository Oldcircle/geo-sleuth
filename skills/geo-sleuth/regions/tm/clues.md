# Turkmenistan clues

Entries use the shared format (`references/clues/README.md`). Only clues whose "Points to" stays inside Turkmenistan belong here; clues that tell Turkmenistan apart from Uzbekistan, Kazakhstan, Iran or Afghanistan go into `references/clues/global.md`.

## Text and numbers

### Region letters at the right end of a plate
- Look for: a white plate with the flag and `TM` at the **left**, then two letters, four digits and two letters: `AB 1234 AG` (one letter at the start before 2009–2010); green company and government plates have four digits and three letters (`1234 AGA`), of which the first two are the region
- Points to: the region where the vehicle was **registered** → `clues.py lookup plate <two letters> --country tm`: AG Ashgabat, AH Ahal, AK Arkadag (the capital of Ahal), BN Balkan, DZ Daşoguz, LB Lebap, MR Mary
- Strength: weak for where the photo was taken; medium when most parked cars in a quiet residential street share one code
- Counterexamples: plates stay with the car after a move, and many cars are registered in Ashgabat; on a white plate the first two letters are only a serial, so read the last two; yellow plates (`2H 50035`, foreign residents and companies), blue diplomatic plates (`12 CD 345`) and export plates (`TDG`) have no region; trailers of private owners put the region in the first two letters, with `TR` last
- Sources: en.wikipedia "Vehicle registration plates of Turkmenistan", sections "Current series" and "Province identifiers", https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Turkmenistan; ru.wikipedia "Индекс автомобильных номеров Туркмении", sections "Типы выдаваемых регистрационных знаков" and "Коды регионов", https://ru.wikipedia.org/wiki/Индекс_автомобильных_номеров_Туркмении

### Landline code on signs and vehicles
- Look for: a fixed-line number on a shop sign, banner or company van: `(12) 34-56-78` in Ashgabat, `(322) 5-12-34` or `+993 422 6 12 34` elsewhere
- Points to: the region of that landline → `clues.py lookup area-code <number without the trunk 8> --country tm`: 12 Ashgabat (12 57 … Arkadag), 1xx Ahal, 2xx Balkan (243 Türkmenbaşy, 222 Balkanabat), 3xx Daşoguz (322), 4xx Lebap (422 Türkmenabat), 5xx Mary (522)
- Strength: medium (a shop's own landline is usually local)
- Counterexamples: most numbers on signs are mobile (61–65, 71, 72) and say nothing about the region; Gypjak (Ahal) also has numbers under Ashgabat's 12 (12 33 6 …, ru.wikipedia only); a chain's sign may show its Ashgabat head office
- Sources: en.wikipedia "Telephone numbers in Turkmenistan", section "Area codes", https://en.wikipedia.org/wiki/Telephone_numbers_in_Turkmenistan; ru.wikipedia "Телефонный план нумерации Туркмении", section "Географические коды", https://ru.wikipedia.org/wiki/Телефонный_план_нумерации_Туркмении

## Cities and buildings

### White marble buildings and white cars
- Look for: avenues of monumental buildings clad in white marble, and traffic in which nearly every car is white
- Points to: Ashgabat, which entered the Guinness Book of Records in 2013 for the world's highest concentration of white marble buildings; by 2018 non-white cars were effectively banned in the city, and black cars were impounded
- Strength: strong when both appear together
- Counterexamples: Arkadag and other new government projects follow the same white style, so check the plate (AG Ashgabat, AK Arkadag); the car rule is reported for the capital, and mixed colours are normal elsewhere
- Sources: en.wikipedia "Ashgabat" (white marble record; non-white cars), https://en.wikipedia.org/wiki/Ashgabat; The Guardian "Turkmenistan enters record books for having the most white marble buildings" (2013), https://www.theguardian.com/world/2013/may/26/turkmenistan-world-record-white-marble-buildings; RFE/RL "'Bad Luck' For Black Car Owners in Turkmen Capital" (2018), https://www.rferl.org/a/turkmenistan-black-car-owners-bad-luck/28963539.html

### Arkadag, the new city
- Look for: a brand-new planned "smart city", signs reading `Arkadag`, plates with `AK`
- Points to: Ahal Province; Arkadag became the province's capital on 20 December 2022 and was formally opened on 29 June 2023, so a finished-looking photo of it dates from 2023 or later
- Strength: medium as a date (the earliest date for a finished street there)
- Counterexamples: Ashgabat looks much the same; construction photos predate the opening
- Sources: en.wikipedia "Arkadag" (regional capital from 20 December 2022, opening set for 29 June 2023), https://en.wikipedia.org/wiki/Arkadag

### Awaza resort on the Caspian
- Look for: a row of new resort hotels on a Caspian beach
- Points to: Awaza, a tourist zone and borough of Türkmenbaşy, 12 km west of the city centre, in Balkan Province
- Strength: medium
- Counterexamples: other Caspian resorts (Kazakhstan's Aktau, Azerbaijan, Iran) look similar; read the plates or signs
- Sources: en.wikipedia "Avaza", https://en.wikipedia.org/wiki/Avaza

## Sun and time

### One time zone, UTC+5
- Look for: a clock, timestamp or shadow you want to compare with the sun (`sun.py`)
- Points to: the whole country is on UTC+5, without daylight saving time, although most of its territory lies in the geographical zone of UTC+4, so the sun is lower in the morning by the clock than the longitude alone suggests
- Strength: — (a setting for `sun.py`, not a place clue)
- Counterexamples: EXIF clocks are often wrong
- Sources: en.wikipedia "Time in Turkmenistan", https://en.wikipedia.org/wiki/Time_in_Turkmenistan
