# Clues outside China

India has its own file, `india.md`.

General order for photos outside China: driving side and plate shape to exclude continents → language of the text and phone area codes → plate style to the state/province → infrastructure and municipal fixtures → architecture and vegetation.
Sections are by country; only clues that transfer to new photos are included.

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

### US Interstate shields
- Look for: the number on red-and-blue shield-shaped road signs
- Points to: one specific Interstate; add a skyline landmark or an exit number to fix the segment and direction
- Strength: strong (to one road)
- Counterexamples: a highway with the same number runs through several states or areas; the sign is small and easy to miss (in v010-4 the human didn't see it, the AI did)
- Sources: v010-4

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

## North America

### British Columbia, Canada plates
- Look for: blue characters on white, "two letters, one digit + small provincial flag in the middle + two digits, one letter"
- Points to: BC
- Strength: strong (when both the format and the provincial flag are clearly visible)
- Counterexamples: out-of-province cars are common in Vancouver; older formats differ
- Sources: v009

### Residential streets with dark green streetlight poles + a grass strip outside the sidewalk
- Look for: on residential streets, streetlight poles painted dark green with curved-arm lamp heads; a grass strip separating sidewalk and roadway; shallow gutters
- Points to: residential areas of Vancouver and Metro Vancouver (use together with plates)
- Strength: weak
- Counterexamples: residential areas in the US Northwest (around Seattle and Portland) look very similar; grass strips are very common in North American suburbs
- Sources: v009

## Inherited standards (overseas territories, former colonies)

When you recognize infrastructure built to "country X's standard", the candidates are the home country + overseas territories that keep the home country's standards + some former colonies. Intersect that with the IP location and the continent the puzzle setter named, and often only one place remains.

### Arched crossarms on the French distribution grid
- Look for: a crossarm arching upward on top of a concrete or metal pole, three conductors hanging from suspension insulators (the "arched" layout of medium-voltage lines); identical poles lined up into the distance
- Points to: the French grid system: metropolitan France and the overseas departments that keep its standards; some former North African colonies have similar pole types
- Strength: medium (narrows the whole world to a few regions in the French system; then use IP, continent, and climate to fix one)
- Counterexamples: border areas of neighboring countries have similar styles; former colonies later changed pole types; in small distant images an ordinary straight crossarm is easily seen as arched, so zoom in to verify
- Sources: v013

## Mexico

### Plate background color (usable even when blurry)
- Look for: the overall background color and graphic placement of the rear plate; no need to read the characters
- Points to: state level. Per the reference chart used in the video, nearly pure white plates are Mexico City and Nuevo León; most other states carry prominent colored graphics or color bands
- Strength: medium (single source)
- Counterexamples: vehicles from other states; states change plate designs; federal plates are a separate system; overexposure
- Sources: v002

### Tall single tubular steel transmission poles along roads
- Look for: a gray single tubular steel pole with three tiers of curved crossarms on one side and long insulator strings; the shorter poles beside it carry distribution lines
- Points to: a high-voltage transmission corridor; check OpenInfraMap for which roads lines of this voltage follow in that city, and use that to filter road segments within the city
- Strength: weak (can't fix the city)
- Counterexamples: different voltages look similar; OSM power data may be missing lines or lack voltage tags
- Sources: v002

## Japan

### Railway company names on level-crossing and station signs
- Look for: the company name printed on round "踏切 とまれ" (level crossing, stop) signs, warning signs, and crossing equipment boxes
- Points to: operating area. JR passenger service is split among six companies, each with its own territory (JR西日本 (JR West) = Kinki, the Chūgoku region, part of Hokuriku); private railway names can often pin the line directly
- Strength: medium (JR to the broad region, private railways to the line)
- Counterexamples: near company boundaries; old signs not replaced after a line was handed over to a third-party operator
- Sources: v003

### Telephone area codes (市外局番)
- Look for: TEL numbers on signs, construction notices, warning signs, vending machines
- Points to: the first digit after the 0 runs roughly north to south (01 Hokkaido … 09 Kyushu and Okinawa); look up the full area code in a table to get the city (e.g., 03 = Tokyo's 23 wards)
- Strength: medium
- Counterexamples: area codes vary from 2 to 5 digits; when only part of the number is visible, judge the length from the digit grouping; 0120, 0570, 050, 080, 090 don't map to a region
- Sources: v003

### Four parallel tracks at one level crossing
- Look for: the number of parallel tracks across the crossing, whether there is overhead catenary
- Points to: a quadruple-track section of a trunk line; adding conditions like "right on the coast" can narrow it to a few km (`osm.py crossings --kind level_crossing` estimates the track count from the node count)
- Strength: medium
- Counterexamples: station throats and two companies' lines running side by side also show 4 tracks; urban quadruple-track sections are mostly grade-separated, so places with level crossings are actually rare
- Sources: v003

### Issuing authority at the bottom of signs
- Look for: "〇〇警察署" (police station), "〇〇土木事務所" (civil engineering office), "〇〇区役所" (ward office) at the bottom of regulatory signs, construction signs, and notice boards
- Points to: ward, city
- Strength: medium
- Counterexamples: the name of a prefectural or cross-ward agency is not the ward you are in
- Sources: v003

## Southeast Asia

### Region/state codes on Myanmar plates
- Look for: a Latin-letter abbreviation on the plate (e.g., YGN) plus a number
- Points to: Myanmar; YGN = Yangon Region
- Strength: medium (single source)
- Counterexamples: vehicles from other regions; old plates from before 2013 are in Burmese script
- Sources: v007
