# Armenia clues

Entries use the shared format (`references/clues/README.md`). Only clues whose "Points to" stays inside Armenia belong here; clues that tell Armenia apart from Georgia, Azerbaijan, Turkey or Iran go into `references/clues/global.md`.

## Text and numbers

### Region code at the left of a vehicle plate
- Look for: a white rectangular plate with black characters, the Armenian flag with `AM` under it at the **left** end, followed by two digits, two letters, and three digits: `12 LL 345` (standard private series); state and police vehicles use `123 LL 45` or specific letter pairs
- Points to: the province (*marz*) or city where the vehicle was **registered** → `clues.py lookup plate <two digits> --country am`: 01–11, 13, 19, 61–68 Yerevan; 12, 27–29 Armavir; 14, 45–49 Shirak; 15, 21, 23, 24 Aragatsotn; 16, 31–35 Gegharkunik; 17, 42, 43 Kotayk; 18, 56 Vayots Dzor; 25, 26 Ararat; 36–39, 41 Lori; 51–54 Syunik; 57–59 Tavush
- Strength: weak for where the photo was taken; medium when multiple parked vehicles in a quiet residential street share one regional code
- Counterexamples: vehicles frequently travel across provinces or are purchased secondhand and keep their original plates; a disproportionate fraction of vehicles in Armenia are registered in Yerevan; codes 20, 30, 40, 44, 50, 55, 60, 70–89, 91–99 are non-regional or personalized series; codes 22 and 90 were historically used in Nagorno-Karabakh / Artsakh; diplomatic (red) and military (black) plates follow distinct numbering schemes
- Sources: en.wikipedia "Vehicle registration plates of Armenia", sections "Regional codes" and "Format", https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Armenia; ru.wikipedia "Индекс автомобильных номеров Армении", section "Коды регионов", https://ru.wikipedia.org/wiki/Индекс_автомобильных_номеров_Армении

### Landline area codes on signage and commercial vehicles
- Look for: a fixed-line telephone number on storefronts, billboards, or commercial delivery vans: `10 12 34 56` or `+374 10 …` in Yerevan, `312 12 345` in Gyumri, `322 12 345` in Vanadzor, or three digits (`2xx`) in other marz centers
- Points to: the province and municipality of the landline subscription → `clues.py lookup area-code <number> --country am`: 10, 11, 12 Yerevan; 222 Abovyan; 223 Hrazdan; 231 Etchmiadzin; 232 Ashtarak; 235 Artashat; 237 Armavir; 244 Artik; 261 Sevan; 263 Ijevan; 268 Dilijan; 281 Yeghegnadzor; 284 Goris; 285 Kapan; 312 Gyumri; 322 Vanadzor
- Strength: medium (commercial storefront landlines usually denote the local business premises)
- Counterexamples: most contact numbers on modern advertising are mobile phones (prefixes 033, 041, 043, 044, 055, 077, 091, 093, 094, 095, 096, 098, 099) and carry no geographic destination; national banks and chains display a central Yerevan (+374 10 / +374 11 / +374 12) hotline on branches nationwide
- Sources: en.wikipedia "Telephone numbers in Armenia", section "Geographic codes", https://en.wikipedia.org/wiki/Telephone_numbers_in_Armenia; ITU National Numbering Plan for the Republic of Armenia (E.129), https://www.itu.int/dms_pub/itu-t/oth/02/02/T020200000A0002PDFE.pdf

### Armenian municipal and civic facility signage
- Look for: institutional name boards on schools, clinics, and municipal offices in Armenian script (Հայոց գրեր): `միջնակարգ դպրոց` (secondary school) or `հիմնական դպրոց` (basic school) with a number `N-րդ դպրոց` or `N հիմնական դպրոց`, `մանկապարտեզ` (kindergarten), `պոլիկլինիկա` (polyclinic / health centre), `բժշկական կենտրոն` (medical centre / hospital), `համայնքապետարան` (community municipality / town hall), `թանգարան` (museum), `փողոց` (abbreviated `փ.` for street), `պողոտա` (abbreviated `պող.` for avenue)
- Points to: settlement type and administrative center; searching OpenStreetMap Nominatim or Overpass with the Armenian Latin or Armenian script name tags (`name:hy` or `name`) resolves facilities that return 0 matches for Russian or English transliterations
- Strength: strong for pinpointing local municipal institutions when cross-referenced with `poi.py`
- Counterexamples: village schools often share identical numbering across different marzer (e.g., School No. 1 exists in Yerevan, Gyumri, Vanadzor, and Goris); combine with settlement name on the plaque
- Sources: Armenian Ministry of Education, Science, Culture and Sports school registry (https://escs.am); OpenStreetMap Armenia institutional taggings (amenity=school, amenity=hospital, amenity=townhall)

## Architecture and urban form

### Pink and black volcanic tuff stone architecture
- Look for: monumental neoclassical facades, colonnades, arched windows, and residential facades built or clad in carved volcanic tuff stone: distinctive warm pink, rose, terracotta, or purple hues, or contrasting charcoal black and reddish basalt/tuff ashlar masonry
- Points to: urban Armenia; pink tuff masonry is the hallmark of Yerevan ("The Pink City" / Վարդագույն քաղաք) and the Ararat Valley; dark charcoal basalt combined with orange tuff bands is characteristic of historic Gyumri (Kumayri historic district)
- Strength: medium (characteristic of Armenian civic and residential architecture; differentiates from neighboring Georgian or Azerbaijani urban centers)
- Counterexamples: individual modern villas or churches clad in tuff can be found across the South Caucasus and diaspora communities; Soviet-era concrete panel buildings (khrushchyovkas) coexist in peripheral residential microdistricts
- Sources: Alexander Tamanian architectural master plan of Yerevan; Encyclopedia Britannica "Yerevan" (The Pink City), https://www.britannica.com/place/Yerevan; Kumayri historic district preservation records, Gyumri

### Pulpulak stone drinking water fountains
- Look for: a freestanding carved stone drinking water memorial fountain, roughly one meter high, carved from pink or gray volcanic tuff, continuously spouting a gentle vertical stream of cold spring drinking water from a brass nozzle at its top, often accompanied by a dedicatory stone relief or inscription
- Points to: Armenia (a ubiquitous civic and cultural landscape fixture across public squares, street corners, parks, and courtyard entrances in Yerevan and Armenian towns)
- Strength: medium (strong indicator of an Armenian public urban or village outdoor space)
- Counterexamples: modern decorative park fountains in other countries; some diaspora Armenian memorial fountains exist abroad, but ubiquitous sidewalk spring bubblers on every street block are unique to Armenia
- Sources: en.wikipedia "Pulpulak", https://en.wikipedia.org/wiki/Pulpulak; Yerevan Municipality Department of Public Utilities (drinking water fountain registry); UNESCO Intangible Cultural Heritage Armenian spring water traditions

## Infrastructure and landscape

### Above-ground natural gas distribution pipe network
- Look for: narrow steel natural gas distribution pipelines painted bright yellow (or occasionally unpainted gray/silver) running above ground along sidewalks, front yard stone fences, and residential property boundaries, elevated on metal posts and forming rectangular overhead portal arches ("П-образные арки") across driveways, gates, and street crossings
- Points to: residential neighborhoods, private housing sectors, and suburban settlements in Armenia (and neighboring South Caucasus regions)
- Strength: weak on its own (indicates residential settlement infrastructure; combine with Armenian script, plates, or tuff stonework)
- Counterexamples: Georgia and Azerbaijan also use extensive above-ground gas distribution networks in residential sectors; underground gas infrastructure in newly redeveloped central commercial avenues
- Sources: Gazprom Armenia distribution network technical documentation; South Caucasus residential infrastructure surveys

### Yerevan Metro and urban transit
- Look for: underground metro station entrances marked with a stylized red Cyrillic/Armenian capital letter `Մ` (for Metropoliten / Մետրոպոլիտեն), or municipal trolleybus overhead catenary wire pairs with blue-and-white LiAZ / Bogdan trolleybuses
- Points to: Yerevan — the Karen Demirchyan Yerevan Metro (1 line, 10 stations) is the sole rapid transit subway in Armenia, and Yerevan operates the only active trolleybus system in the country (Gyumri's trolleybus ceased operations in 2005)
- Strength: strong for narrowing a location within Armenia to Yerevan
- Counterexamples: overhead catenary wires can be mistaken for tramway wires (Yerevan trams closed in 2004); Russian or post-Soviet metro systems also use the red "M" logo, but Yerevan's logo features distinctive Armenian architectural flourishes and bilingual Armenian/English station signage
- Sources: en.wikipedia "Yerevan Metro", https://en.wikipedia.org/wiki/Yerevan_Metro; en.wikipedia "Trolleybuses in Yerevan", https://en.wikipedia.org/wiki/Trolleybuses_in_Yerevan

## Sun and time

### One time zone, UTC+4
- Look for: timestamped photo EXIF metadata, clock displays, or cast shadow lengths to correlate with `sun.py`
- Points to: the entire territory of Armenia observes UTC+4 (Asia/Yerevan) year-round without daylight saving time (abolished in January 2012)
- Strength: — (operational parameter for solar calculation tools, not an isolating geographical clue)
- Counterexamples: uncalibrated digital camera clocks; Armenia spans roughly 3 degrees of longitude (43.5°–46.5° E), meaning true solar noon occurs around 13:00 local standard time across the nation
- Sources: en.wikipedia "Time in Armenia", https://en.wikipedia.org/wiki/Time_in_Armenia; Law of the Republic of Armenia on the Procedure of Calculation of Time (2012 amendment)
