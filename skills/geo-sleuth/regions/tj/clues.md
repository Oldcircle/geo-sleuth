# Tajikistan clues

Entries use the shared format (`references/clues/README.md`). Only clues whose "Points to" stays inside Tajikistan belong here; clues that tell Tajikistan apart from Uzbekistan, Kyrgyzstan, Afghanistan or Kazakhstan go into `references/clues/global.md`.

## Text and numbers

### Region code at the right end of a plate
- Look for: a white plate with black characters, the flag with `TJ` under it at the **left** end, then four digits, two letters and two digits at the **right** end: `1234 AB 01` (format since 2009–2010; since April 2014 the letters are as large as the digits); companies have three digits first (`123 AB 01`); public transport has orange plates with the letters `TT`
- Points to: the region where the vehicle was **registered** → `clues.py lookup plate <last two digits> --country tj`: 01, 05 (and 10) Dushanbe; 02, 06 (and 20) Sughd; 03 Khatlon; 04 Gorno-Badakhshan; 07, 08 Districts of Republican Subordination
- Strength: weak for where the photo was taken; medium when most parked cars in a quiet residential street share one code
- Counterexamples: plates stay with the car after a move, and many cars are registered in Dushanbe; codes 10 and 20 are in ru.wikipedia only, and the en.wikipedia article is unreferenced; green non-resident plates and red diplomatic plates follow other schemes; Kazakh plates also end in a two-digit region code, so read `TJ` under the flag
- Sources: en.wikipedia "Vehicle registration plates of Tajikistan", sections "Codes" and "2009/2014 Series", https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Tajikistan; ru.wikipedia "Индекс автомобильных номеров Таджикистана", sections "Номерные знаки стандарта 2009—2010 года" and "Коды регионов Таджикистана", https://ru.wikipedia.org/wiki/Индекс_автомобильных_номеров_Таджикистана

### Plates of the 1996–2010 format
- Look for: a plate that looks Russian, a letter (later two letters) and four digits, but in the box at the right the two-digit code stands over small letters `RT` instead of `RUS` and a flag
- Points to: the region of registration at the time → `clues.py lookup plate-1996 <two digits> --country tj`: 01 Dushanbe and the Districts of Republican Subordination, 02 Sughd, 03 Khatlon, 04 Gorno-Badakhshan
- Strength: weak (old plates are on old cars that may have moved since); medium as a date: the car was registered before 2009–2010
- Counterexamples: a Russian plate has `RUS` and the flag in that box; company plates of the format put the letter after the digits
- Sources: ru.wikipedia "Индекс автомобильных номеров Таджикистана", sections "Номерные знаки стандарта 1996 года" and "Коды регионов Таджикистана", https://ru.wikipedia.org/wiki/Индекс_автомобильных_номеров_Таджикистана; en.wikipedia "Vehicle registration plates of Tajikistan", section "1996 Series", https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Tajikistan

### Landline code on signs and vehicles
- Look for: a fixed-line number on a shop sign, banner or company van: `372 21 23 45` or `+992 372 …` in Dushanbe, `(3422) 6 12 34` or `+992 3422 …` elsewhere
- Points to: the region of that landline → `clues.py lookup area-code <number> --country tj`: 372 Dushanbe, 31xx Districts of Republican Subordination, 32xx and 33xx Khatlon (3222 Bokhtar, 3322 Kulob), 34xx Sughd (3422 Khujand), 35xx Gorno-Badakhshan (3522 Khorog)
- Strength: medium (a shop's own landline is usually local)
- Counterexamples: most numbers on signs are mobile and say nothing about the region; Nurek (3138) and Yavan (3141) have codes in the 31 zone but are in Khatlon, which the table already handles; a chain's sign may show its Dushanbe head office
- Sources: en.wikipedia "Telephone numbers in Tajikistan", section "Area codes in Tajikistan" (from the ITU list), https://en.wikipedia.org/wiki/Telephone_numbers_in_Tajikistan; ru.wikipedia "Административное деление Таджикистана" (Nurek and Yavan district joined Khatlon in December 1992), https://ru.wikipedia.org/wiki/Административное_деление_Таджикистана

## Landscape

### High Pamir mountains
- Look for: high, bare mountain valleys and plateaus with very few people, in the east of the country
- Points to: the Gorno-Badakhshan Autonomous Region (Khorog, Murghab, the Pamirs): it covers nearly 45% of the country's land but has only about 2% of its people; plate code 04, phone codes 35xx
- Strength: weak on landscape alone; medium with a 04 plate or a 35xx number
- Counterexamples: the same mountains continue into Kyrgyzstan (Alay), Afghanistan (Wakhan, across the Panj) and China; parts of Sughd and the Districts of Republican Subordination (Rasht valley) are high mountains too
- Sources: en.wikipedia "Gorno-Badakhshan Autonomous Region" (lead: Pamir Mountains, share of land and population), https://en.wikipedia.org/wiki/Gorno-Badakhshan_Autonomous_Region

## Dating and transport

### Trolleybuses
- Look for: trolleybuses or their overhead wires in a city street
- Points to: Dushanbe, the only trolleybus system still running (since 1955); a trolleybus in Khujand dates the photo before about 2010 (service unstable from about 2006, officially closed in April 2013)
- Strength: medium
- Counterexamples: wires can stay after a system closes
- Sources: en.wikipedia "List of trolleybus systems", section "Tajikistan", https://en.wikipedia.org/wiki/List_of_trolleybus_systems; en.wikipedia "Dushanbe", section "Trolleybus system", https://en.wikipedia.org/wiki/Dushanbe

## Sun and time

### One time zone, UTC+5
- Look for: a clock, timestamp or shadow you want to compare with the sun (`sun.py`)
- Points to: the whole country is on UTC+5 (Asia/Dushanbe), without daylight saving time
- Strength: — (a setting for `sun.py`, not a place clue)
- Counterexamples: EXIF clocks are often wrong; the country spans about eight degrees of longitude (67°–75° E), so solar noon in eastern Gorno-Badakhshan comes roughly half an hour earlier by the clock than in the west (`sun.py` works from the coordinates, so check a candidate there, not only the capital)
- Sources: en.wikipedia "Time in Tajikistan", https://en.wikipedia.org/wiki/Time_in_Tajikistan
