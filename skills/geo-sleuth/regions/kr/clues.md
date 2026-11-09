# South Korea clues

Entries use the shared format (`references/clues/README.md`). Only clues whose "Points to" stays inside South Korea belong here; clues that tell countries apart go into `references/clues/global.md`. Sources checked on 2026-11-05.

## Text and plates

### Landline area code on shop signs and banners
- Look for: a fixed-line number on a shop sign, banner, van or notice board: `0XX-XXX(X)-XXXX`, or `02-XXX(X)-XXXX` for Seoul (e.g. `02-312-3456`, `051-212-3456`)
- Points to: the province-level unit the code belongs to (02 Seoul, 031 Gyeonggi, 032 Incheon, 051 Busan, 064 Jeju, …); a few codes also reach a neighbouring unit → `clues.py lookup area-code <number> --country kr`
- Strength: medium (one code per province-level unit; a shop's own landline is usually local)
- Counterexamples: `010` numbers are mobile and used nationwide, as are `070` VoIP and `15xx`/`16xx` business numbers; a branch can print its head office's number; codes cross borders where exchanges do (Gwacheon and Gwangmyeong use 02, Bucheon uses 032, Gyeongsan uses 053, Gyeryong uses 042, Daegu's Gunwi-gun kept 054); before 2012 most of the Sejong area (former Yeongi-gun) used 041; signs printed before July 2000 show old 4-digit codes
- Sources: ko.wikipedia "대한민국의 전화번호 체계" (current codes and exceptions), https://ko.wikipedia.org/wiki/대한민국의_전화번호_체계; en.wikipedia "Telephone numbers in South Korea", https://en.wikipedia.org/wiki/Telephone_numbers_in_South_Korea

### Region name on commercial plates
- Look for: a Hangul region name before the number on a taxi, bus or truck plate (`서울 70바 1234`, `부산 12사 3456`); taxis, buses and commercial trucks use 바/사/아/자; courier (택배) vehicles use 배. Old two-line plates (before 2004) also show it on private cars
- Points to: the province-level unit where the vehicle was registered (서울, 경기, 충북, 전남, 제주, …) → `clues.py lookup plate <plate> --country kr`
- Strength: weak (registration only)
- Counterexamples: trucks and coaches travel nationwide; private cars since 2004 (`12가 3456`, `123가 4567`) have no region, so most cars say nothing; 광주 and 전남 plates now both belong to the merged 전남광주통합특별시
- Sources: en.wikipedia "Vehicle registration plates of South Korea" (commercial format and region names), https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_South_Korea; ko.wikipedia "대한민국의 차량 번호판" (national plates without region from 2004; 배 for courier vehicles), https://ko.wikipedia.org/wiki/대한민국의_차량_번호판

## Roads

### Expressway route numbers
- Look for: the red, white and blue expressway shield on a direction sign or route marker
- Points to: the corridor of that route. Two-digit trunk routes form a grid: odd numbers run north–south and grow from west to east, even numbers run east–west and grow from south to north; three-digit branches start with their trunk's number. Ring routes name a metro area: 100 Seoul (Capital Region First Ring), 300 Daejeon, 400 Capital Region Second Ring, 500 Gwangju, 600 Busan, 700 Daegu
- Strength: medium (single source); a route number narrows to a corridor, not a place along it
- Counterexamples: route 1 (Gyeongbu) breaks the grid and runs the whole country from Seoul to Busan; long trunk routes cross several provinces; signs for an expressway also stand on approach roads some distance from it; national highway numbers follow a different scheme and are not expressways
- Sources: en.wikipedia "Expressways in South Korea" (2001 grid numbering, ring route numbers, Gyeongbu exception), https://en.wikipedia.org/wiki/Expressways_in_South_Korea

## Landscape

### Black basalt field walls on Jeju
- Look for: low, winding walls of dark, porous volcanic stone piled without mortar around fields, homes and graves, often with gaps between the stones; stone grandfather statues (dol hareubang) nearby
- Points to: Jeju (제주특별자치도)
- Strength: medium
- Counterexamples: dry-stone walls exist on the mainland but are rarely black basalt; landscaping and resorts elsewhere use basalt as decoration; dol hareubang replicas are sold as souvenirs; tangerine and hallabong orchards are no longer Jeju-only (hallabong is grown in Haenam and elsewhere in the former South Jeolla)
- Sources: en.wikipedia "Doldam", https://en.wikipedia.org/wiki/Doldam; en.wikipedia "Jeju Province" (batdam, dol hareubang), https://en.wikipedia.org/wiki/Jeju_Province; en.wikipedia "Globally Important Agricultural Heritage Systems" (Jeju Batdam agricultural system, designated 2014), https://en.wikipedia.org/wiki/Globally_Important_Agricultural_Heritage_Systems; en.wikipedia "Haenam County" (hallabong outside Jeju), https://en.wikipedia.org/wiki/Haenam_County
