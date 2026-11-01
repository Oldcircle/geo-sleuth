# Kazakhstan clues

Entries use the shared format (`references/clues/README.md`). Only clues whose "Points to" stays inside Kazakhstan belong here; clues that tell Kazakhstan apart from Russia, Kyrgyzstan or Uzbekistan go into `references/clues/global.md`.

## Text and numbers

### Region code in the square of a current number plate
- Look for: on a white plate with the Kazakh flag and `KZ` on the left, the two digits in the separate square on the right (`123 ABC 02`); plates in this format date from 2012 on
- Points to: the region where the vehicle was **registered** → `clues.py lookup plate <two digits> --country kz` or `board.py apply --kind plate --value <two digits>`; type only the two digits, not the whole plate
- Strength: weak for where the photo was taken; medium when most parked cars in a quiet residential street share one code
- Counterexamples: rental, fleet and company cars are often registered in 01 Astana or 02 Almaty; plates stay with the car after a move, so 05, 09 and 16 plates are still common in Jetisu, Ulytau and Abai, which got 19, 20 and 18 only in 2022; yellow plates (foreign-owned) and red plates (diplomatic) use other schemes
- Sources: en.wikipedia "Vehicle registration plates of Kazakhstan", Regional codes table, https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Kazakhstan; egov.kz "License plates of cars in Kazakhstan", https://egov.kz/cms/en/articles/vehicle/grnz

### Region letter at the start of a pre-2012 plate
- Look for: an older white plate starting with one Latin letter, then three digits and two or three letters (`A 644 DC`, `Z 123 ABC`)
- Points to: the region of registration at the time → `clues.py lookup plate <whole plate> --country kz`; O and W are each shared by two regions, and the board keeps both
- Strength: weak (old plates are on old cars that may have moved since)
- Counterexamples: these regions are the pre-2022 ones, so a B or V plate can be from today's Jetisu, F or U from Abai, K or M from Ulytau, X from Shymkent; misreading the letter as a digit (O and 0, Z and 2)
- Sources: en.wikipedia "Vehicle registration plates of Kazakhstan", sections "Design until August 2012" and "Regional codes", https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Kazakhstan

### Landline area code on signs and vehicles
- Look for: a fixed-line number on a shop sign, banner or company van, usually written `8 (7xxx) xx-xx-xx` or `+7 (7xx) xxx xx xx`
- Points to: the region of that landline → `clues.py lookup area-code <number without +7> --country kz`; zones 710–729 are one per region, a code ending in 2 after the zone (7172, 7252, 7282) is the regional centre, and Almaty city is 727 followed by 2 or 3
- Strength: medium (a shop's own landline is usually local)
- Counterexamples: numbers starting 70x, 747 or 77x are mobile and say nothing about the region; a chain's sign may show the head office (often Almaty or Astana); +7 is shared with Russia, whose zones start 3, 4, 8 or 9; zones 710 and 722 also covered Karaganda and East Kazakhstan regions before the 2022 split, and district codes moved to Abai may still sit under 723
- Sources: ru.wikipedia "Телефонный план нумерации Казахстана" (zones after 2022, city and district codes), https://ru.wikipedia.org/wiki/Телефонный_план_нумерации_Казахстана; en.wikipedia "Telephone numbers in Kazakhstan" (zones before 2022, mobile ranges), https://en.wikipedia.org/wiki/Telephone_numbers_in_Kazakhstan

## Names that date a photo

### Regions created in June 2022
- Look for: `Абай облысы`, `Жетісу облысы` or `Ұлытау облысы` (Abai, Jetisu, Ulytau Region) on official signs, police cars, akimat buildings or region-border signs; plates with region code 18, 19 or 20
- Points to: that region, and a photo taken after June 2022
- Strength: medium (two sources); for an official sign the region follows from the name itself
- Counterexamples: a car with an 18–20 plate can be driven anywhere; older signs in the same area still name East Kazakhstan, Almaty or Karaganda Region
- Sources: en.wikipedia "ISO 3166-2:KZ" (subdivision list and change history), https://en.wikipedia.org/wiki/ISO_3166-2:KZ; en.wikipedia "Vehicle registration plates of Kazakhstan" (codes 18–20), https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Kazakhstan

### Nur-Sultan and Kapshagay
- Look for: the capital written `Нур-Султан` / `Nur-Sultan` on a sign, timetable or vehicle; the town north of Almaty written `Капшагай` / `Kapshagay` instead of `Конаев` / `Konaev`
- Points to: the capital was called Nur-Sultan from 2019 to September 2022, then Astana again; Kapshagay was renamed Konaev in 2022 and became the centre of Almaty Region. A new-looking sign with the old name narrows the photo's date
- Strength: medium (old signs survive for years, so the name gives an earliest date only when the sign is new)
- Counterexamples: faded or unreplaced signs; business names that keep the old city name
- Sources: en.wikipedia "Astana", https://en.wikipedia.org/wiki/Astana; en.wikipedia "Konaev", https://en.wikipedia.org/wiki/Konaev

## Roads

### Road index `KZ<region code>-<nn>` on route markers
- Look for: a road index such as `KZ04-02` or `KZ08-04` on a route marker, kilometre post or direction sign (introduced by a ministerial order of 30 October 2024)
- Points to: the two digits after `KZ` are the region's plate code → `clues.py lookup plate <two digits> --country kz`; the road is a national road that stays inside that region. `KAZ01`–`KAZ23` (no region digits) are inter-regional trunk roads: trace the number with `osm.py route`
- Strength: medium (three sources, but all go back to one Ministry of Transport announcement); in practice decisive when the marker stands on the road itself
- Counterexamples: signs are replaced gradually during maintenance, so many roads still show the abolished `M-`, `A-` and `P-` numbers (`M-36`, `A-2`, `P-17`), which carry no region code; a direction sign at a junction can name a road that starts in the next region; European `E` and Asian Highway `AH` numbers stay as they were
- Sources: en.wikipedia "Roads in Kazakhstan", section "current system" (order of 30 October 2024, KAZ/KZ## definitions, per-region tables), https://en.wikipedia.org/wiki/Roads_in_Kazakhstan; Otandastar Foundation / gov.kz "New indexes KAZ and KZ installed on Kazakhstani highways" (KZ04-02 = Aktobe Region, 88 KZ roads, gradual sign replacement), https://oq.gov.kz/en/qazalemnews/139; Informburo "Казахстан вводит новые индексы для дорог – KAZ и KZ" (22 November 2024, quoting the Ministry of Transport), https://informburo.kz/novosti/kazaxstan-vvodit-novye-indeksy-dlya-dorog-kaz-i-kz-cto-eto-izmenit

### Kilometre post (sign 5.28) on a small white post
- Look for: a small white roadside post carrying sign 5.28, a plate with a kilometre number, normally blue; nearby, a route marker with the road index
- Points to: the number is the distance from the start (or end) of that road. With the road index known, it places the photo within about a kilometre along that road: find the road with `osm.py along --line '["highway"]["ref"~"^K[AА]Z02$"]' --step 1000` (or the `KZ..-..` index), then measure from the road's start (the first town in its "Direction" in the roads list). No script computes the distance along a road yet, so count from the sampled points and check the result against satellite imagery
- Strength: medium (single source for the sign; the method then needs the road index)
- Counterexamples: OSM tags the inter-regional roads with a Cyrillic А inside the Latin letters (`KАZ02`), so a query for `KAZ02` typed in Latin finds nothing, hence the `[AА]` in the pattern above; `KZ..-..` refs are Latin and keep the abolished number in `old_ref`; roads renumbered in 2024 were stitched from older roads (`KAZ06` joins M-32, A-2 and others), and posts may still count from the old road's start; posts are missing or illegible on many rural roads
- Sources: 24pdd.kz "5. Информационно-указательные знаки" (official text of sign 5.28: distance to the start or end of the road), https://24pdd.kz/5-informatsionno-ukazatelnye-znaki/; en.wikipedia "Roads in Kazakhstan" (start and end of each KAZ and KZ road), https://en.wikipedia.org/wiki/Roads_in_Kazakhstan; OSM ref tags checked between Astana and Shchuchinsk on 2026-11-01 (`KАZ02` with Cyrillic А; `KZ03-02` with `old_ref=P-6`)

### Green kilometre plates and green direction signs
- Look for: kilometre plates (sign 5.28) or direction signs on a green background instead of blue
- Points to: a motorway section. Outside towns, green on direction signs means the route runs along a motorway and blue that it runs along another road; the maintainer has seen green kilometre plates on the Astana–Shchuchinsk road (part of `KAZ02`)
- Strength: weak (single source for the green kilometre plates)
- Counterexamples: inside a town, green on a direction sign means the motorway starts after leaving the town, not that you are on it; sections are upgraded and re-signed at different times
- Sources: 24pdd.kz "5. Информационно-указательные знаки" (green or blue background on signs 5.20.1, 5.20.2, 5.21.1 and 5.21.2), https://24pdd.kz/5-informatsionno-ukazatelnye-znaki/; maintainer observation (@wntic), Astana–Shchuchinsk road

## Time and sun

### Clock time before and after 1 March 2024
- Look for: a time from EXIF, a watermark or a visible clock, used with `sun.py`
- Points to: since 1 March 2024 the whole country is on UTC+5. From 21 December 2018 to 29 February 2024, West Kazakhstan, Atyrau, Mangystau, Aktobe and Kyzylorda regions used UTC+5 and every other region UTC+6 (Kostanay was UTC+6 too). Pass the offset that matches the date and the candidate region; a one-hour error shifts the sun's hour angle by 15°
- Strength: medium (it decides whether a sun computation is right, not where the photo is)
- Counterexamples: phones that kept an outdated time-zone database; cameras whose clock was never set; Kyzylorda used UTC+6 from 2004 to December 2018. The single zone puts solar noon near 11:30 in Oskemen and near 13:35 in Aktau (about 11:10 and 13:55 at the eastern and western extremes), so "midday" shadows can mislead
- Sources: en.wikipedia "Time in Kazakhstan" (single UTC+5 zone since 1 March 2024; 2018–2024 two-zone split; per-city history), https://en.wikipedia.org/wiki/Time_in_Kazakhstan

## Public transport

### Trams, trolleybuses and light rail
- Look for: tram tracks or tramcars, overhead wires for trolleybuses, or a light-rail line on a viaduct
- Points to: trams run only in Pavlodar, Oskemen and Temirtau; trolleybuses only in Almaty; the Astana light rail (Tarlan Astana) opened on 16 May 2026
- Strength: medium for a current photo (the list is short and closed, but the source is Wikipedia's lists only); weak for an undated one
- Counterexamples: older photos: Almaty had trams until October 2015 and Karaganda until 1997; trolleybuses ran in Astana until 2008, Shymkent and Kostanay until 2005, Karaganda until 2010, Taraz until 2013, Aktobe until 2013 and Petropavl until 2014; disused rails and wire poles can stay in the street for years
- Sources: en.wikipedia "List of town tramway systems in Asia", section Kazakhstan, https://en.wikipedia.org/wiki/List_of_town_tramway_systems_in_Asia; en.wikipedia "List of trolleybus systems", section Kazakhstan, https://en.wikipedia.org/wiki/List_of_trolleybus_systems; en.wikipedia "Astana Light Metro" (opened 16 May 2026), https://en.wikipedia.org/wiki/Astana_Light_Metro

### City bus generations in Astana
- Look for: the make and colour of city buses
- Points to: in Astana, the bus dates the photo rather than placing it: white MAZ buses until about 2018, then white-and-green Iveco buses, now Yutong buses in white, green or blue. Bus colour is not a reliable city marker in Kazakhstan, because one city runs several liveries at once
- Strength: weak (single source for the liveries and their dates)
- Counterexamples: older buses stay on some routes for years after a new fleet arrives; private operators run their own buses alongside the city parks; other cities renew their fleets on their own schedules and also buy Yutong buses
- Sources: maintainer observation (@wntic, Astana); bizmedia.kz "Госавтопарк в Астане намерен потратить почти 23 млрд на лизинг китайских автобусов" (2023, 204 Yutong buses for Bus Park No. 1), https://bizmedia.kz/2023-03-10-gosavtopark-v-astane-nameren-potratit-pochti-23-mlrd-na-lizing-kitajskih-avtobusov/; bes.media "Коммунальный автобусный парк Астаны взял китайские Yutong за 35,5 млрд тенге в лизинг" (300 gas Yutong buses), https://bes.media/news/kommunalniy-avtobusniy-park-astani-vzyal-kitayskie-yutong-za-355-mlrd-tenge-v-lizing-9df8b1/

## Population and signs

### Russian-only private signs, Orthodox churches, Slavic surnames on signs
- Look for: shop signs, ads and notices written only in Russian, Orthodox churches with onion domes, Slavic surnames on business names or memorials
- Points to: the north and east. Russians are about 44% of the population in North Kazakhstan and East Kazakhstan, 31–34% in Karaganda and Kostanay, 26–29% in Akmola and Pavlodar, and 18% in Almaty city, but under 2% in Kyzylorda and Turkistan and 4–7% in Atyrau, Mangystau, Aktobe, Jambyl and Shymkent (2026 estimates)
- Strength: weak (a population share shifts the odds; it doesn't place a photo)
- Counterexamples: official signs are bilingual everywhere, so they say nothing about the region; Russian is widely used in every city, including in the south; Orthodox churches also stand in southern and western cities
- Sources: ru.wikipedia "Русские в Казахстане", section "Численность русских по областям" (2023–2026 estimates by region, from the Bureau of National Statistics), https://ru.wikipedia.org/wiki/Русские_в_Казахстане; en.wikipedia "Languages of Kazakhstan" (Russian strongest in the north), https://en.wikipedia.org/wiki/Languages_of_Kazakhstan

## Landscape and crops

### Wheat fields to the horizon
- Look for: huge flat grain fields, grain elevators in villages, shelterbelts of trees between fields
- Points to: the northern grain belt: Kostanay, North Kazakhstan and Akmola produce most of the country's wheat; East Kazakhstan, Abai and Pavlodar also grow grain on a large scale
- Strength: weak (needs the month and a second clue)
- Counterexamples: grain is also grown in the foothills of the south and east; fallow fields and dry steppe look alike outside the growing season
- Sources: trade.gov "Kazakhstan – Agricultural Sector" (three northern regions produce most grain), https://www.trade.gov/country-commercial-guides/kazakhstan-agricultural-sector; Library of Congress country study "Kazakhstan – Agriculture" (grain in the north-central region), https://countrystudies.us/kazakstan/26.htm

### Rice paddies and cotton fields
- Look for: flooded, levelled paddy fields with irrigation canals; cotton bushes with white bolls in autumn
- Points to: the irrigated south along the Syr Darya: rice mainly in Kyzylorda Region, cotton in the old South Kazakhstan (today's Turkistan Region)
- Strength: medium for rice or cotton you can identify with the month known (these crops are confined to the far south)
- Counterexamples: flooded fields early in the season can be mistaken for lakes or salt flats; Uzbekistan across the border grows the same crops
- Sources: Library of Congress country study "Kazakhstan – Agriculture" (cotton and rice in the south, cotton only in South Kazakhstan oblast), https://countrystudies.us/kazakstan/26.htm; The Times of Central Asia "Kazakhstan gathers record-high grain and rice harvest", https://timesca.com/kazakhstan-gathers-record-high-grain-and-rice-harvest/

### Birch and aspen groves in open steppe
- Look for: small round groves of white-barked birch and aspen ("kolky") scattered over flat grassland; long strips of pine on sandy soil ("ribbon forests")
- Points to: the forest-steppe fringe along the Russian border: North Kazakhstan and the north of Kostanay, Akmola and Pavlodar
- Strength: weak (vegetation without a month)
- Counterexamples: the same landscape continues for hundreds of kilometres in Russia; birches are planted in parks and along roads in many cities
- Sources: en.wikipedia "Kazakh forest steppe" (birch, aspen and pine; kolky; ribbon forests; along the Russian border), https://en.wikipedia.org/wiki/Kazakh_forest_steppe

## Coverage

### Google Street View exists only from 2024
- Look for: nothing in the photo; this is about what you compare it with
- Points to: Google Street View launched in Kazakhstan in March 2024, covering regional centres (Almaty, Astana, Shymkent, Aktobe, Semey and others) and main roads. A photo older than that can only be compared with imagery taken later
- Strength: — (a search-planning note, not a clue)
- Counterexamples: user-uploaded panoramas predate the official coverage in some places; rural roads may have no coverage at all, so confirm with `terrain.py view` ridgelines or satellite imagery instead
- Sources: Google Keyword blog "Street View comes to Kazakhstan" (March 2024), https://blog.google/products/maps/google-street-view-kazakhstan/; The Astana Times "Google Launches Street View in Kazakhstan", https://astanatimes.com/2024/03/google-launches-street-view-in-kazakhstan/
