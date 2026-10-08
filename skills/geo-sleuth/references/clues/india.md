# India clues

Same entry format and rules as `README.md`. Unlike `china.md`, these entries come from public documents, not video breakdowns, so `Sources` cites URLs (Wikipedia pages pinned to the revision that was read, Indian Roads Congress / ministry documents, news reports). Nothing here is from a solved puzzle; treat every "medium" as needing a second clue. Ordered by the layers in `observe.md`.

Lookups that go with these entries (local tables, see `data/README.md`):
`clues.py lookup plate "KA 05"`, `lookup std-code "0484 2345678"`, `lookup pin 682001`, `lookup in-admin <state or code>`, `lookup script Gurmukhi`.

## Text and plates

### Registration plates: state code + RTO number
- Look for: `AA 00 A(AA) 0000`: two-letter state/UT code, two-digit RTO number, a series of 0–3 letters, then up to four digits (e.g. `MH 12 AB 1234`); Latin letters and Western digits on every plate
- Points to: state/UT from the letters; district (RTO office) from the number — `clues.py lookup plate "MH 12"`
- Strength: medium (single source); several street plates agreeing raises it, exactly as in the China plate entry
- Counterexamples: out-of-state cars in metros, tourist spots and on highways; Andhra Pradesh registers new vehicles statewide under the common number AP 39, so AP plates stop at state level; older codes stay valid after a rename/split (OR → OD, UA → UK, DN/DD → DD, TS → TG; Hyderabad-area cars still carry pre-2014 `AP 09`–`AP 13` plates, which the lookup maps to Telangana); some states register luxury cars elsewhere for tax reasons (the source names Puducherry)
- Sources: [Vehicle registration plates of India](https://en.wikipedia.org/w/index.php?title=Vehicle_registration_plates_of_India&oldid=1372866191); [List of RTO districts in India](https://en.wikipedia.org/w/index.php?title=List_of_Regional_Transport_Office_districts_in_India&oldid=1377425763)

### Plate colours (vehicle class, not place)
- Look for: black on white = private; black on yellow = commercial (taxis, trucks, autos); yellow on black = rental/self-drive; white or yellow text on green = electric; white on blue = diplomatic (`CD`, `UN`); red on yellow = temporary; white on red = trade; upward arrow + year + letter on military vehicles
- Points to: India (country) and vehicle class; yellow commercial plates make a local-fleet reading of the RTO code more reliable than a private car
- Strength: weak for place (single source)
- Counterexamples: colour depends on lighting and white balance; neighbouring countries also use yellow commercial plates; hand-painted non-standard plates are common on older vehicles
- Sources: [Vehicle registration plates of India — Colour coding](https://en.wikipedia.org/w/index.php?title=Vehicle_registration_plates_of_India&oldid=1372866191)

### BH (Bharat) series plates
- Look for: `YY BH 0000 AA`, two-digit year first, then `BH`
- Points to: India only: issued to central/state government employees and staff of firms with offices in four or more states so the car can move between states; it carries no state or district
- Strength: medium (single source), and it works as a negative: don't infer a state from it
- Counterexamples: none for place; just don't read the year as an RTO number
- Sources: [Vehicle registration plates of India — BH series](https://en.wikipedia.org/w/index.php?title=Vehicle_registration_plates_of_India&oldid=1372866191) (MoRTH notification of 26 August 2021, as cited there)

### Landline STD codes on shop boards and ads
- Look for: numbers written `0xxx-xxxxxxx`, `(0xxx) xxxxxx`, `+91 xx xxxx xxxx`; code + number always total 10 digits, so the code length follows from the subscriber digits (2-digit metros: 011 Delhi, 022 Mumbai, 033 Kolkata, 044 Chennai, 040 Hyderabad, 080 Bengaluru, 020 Pune, 079 Ahmedabad)
- Points to: the short-distance charging area (SDCA, roughly a tehsil/town) and its state — `clues.py lookup std-code`
- Strength: medium (a full code reaches a town; the table is the 2003 plan, a few codes have been renumbered)
- Counterexamples: ten-digit mobiles starting 6–9 don't map to a place; `1800` toll-free and `140` telemarketing numbers; head-office numbers on chain boards and ads; SDCAs straddling a state/UT border (Una-Diu) are returned as two candidates
- Sources: [DoT National Numbering Plan 2003, Annex II](https://www.dot.gov.in/static/uploads/2026/05/9ed5f19dbf38307edc38a54377d82cd5.pdf); [Telephone numbers in India](https://en.wikipedia.org/w/index.php?title=Telephone_numbers_in_India&oldid=1376736701); [TRAI recommendations on numbering, 2020](https://www.trai.gov.in/sites/default/files/2024-09/Recommendations_29052020.pdf) (mobile levels 9/8/7 and parts of 6)

### PIN codes on shop boards, letterheads, signboards
- Look for: six digits, often after the city name (`Kochi - 682 001`); never starts with 0
- Points to: first digit = postal zone, first two = state/circle, first three = sorting district — `clues.py lookup pin` (the table resolves 2–3 digit prefixes to a state, not to a district)
- Strength: medium (single source)
- Counterexamples: 9xxxxx is the Army Postal Service, not a place; one prefix can cover two states (80–85 Bihar and Jharkhand; 20–28 Uttar Pradesh and Uttarakhand); the PIN is the delivery head office's, which may be a neighbouring town; company letterheads carry head-office PINs
- Sources: [Postal Index Number](https://en.wikipedia.org/w/index.php?title=Postal_Index_Number&oldid=1377692482)

### Script on official signs (and what shop signs can't tell you)
- Look for: the non-Latin script on government boards, road signs and bus destination boards: Gurmukhi → Punjab; Bengali–Assamese → West Bengal, Tripura, Assam; Odia → Odisha; Gujarati → Gujarat; Tamil → Tamil Nadu/Puducherry; Telugu → Andhra Pradesh/Telangana; Kannada → Karnataka; Malayalam → Kerala; Meitei Mayek → Manipur; Devanagari covers Hindi, Marathi, Konkani, Nepali, Bodo, Dogri, so on its own it only says "not the south or east"
- Points to: a state or a few states — `clues.py lookup script <script>` lists states with an official language in that script
- Strength: medium on official signage (single source for the language-to-state table); weak on shop signs
- Counterexamples: Hindi and English appear everywhere; Bengali is also Bangladesh, Gurmukhi and Urdu also Pakistan, Tamil also Sri Lanka, Nepali (Devanagari) also Nepal; migrants' shops and restaurants advertise in their home script; read with `ocr.py --backend tesseract`, RapidOCR's model does not read Indic scripts
- Sources: [Languages with official recognition in India](https://en.wikipedia.org/w/index.php?title=Languages_with_official_recognition_in_India&oldid=1378602338); [States and union territories of India](https://en.wikipedia.org/w/index.php?title=States_and_union_territories_of_India&oldid=1376547964)

### Mandatory local-language shop boards (Maharashtra, Karnataka)
- Look for: shop boards where Marathi in Devanagari leads (Maharashtra) or Kannada fills the upper part of the board (Karnataka, 60% rule)
- Points to: Maharashtra / Karnataka, mainly their big cities where the rules were enforced (Mumbai, Bengaluru)
- Strength: medium (3 independent reports per state, but enforcement is uneven and recent: the Supreme Court gave Mumbai shops until late November 2023; Karnataka amended its law in 2024 and the High Court stayed sealing of non-compliant shops)
- Counterexamples: photos older than the enforcement drives; Devanagari leading a board is also just Hindi anywhere in the north; Kannada-dominant boards don't exclude border towns in neighbouring states
- Sources: Maharashtra — [Hindustan Times, 25 Sep 2023](https://www.hindustantimes.com/cities/mumbai-news/sc-tells-mumbai-retailers-to-install-marathi-signboards-in-2-months-101695669545547.html), [Indian Express](https://indianexpress.com/article/cities/mumbai/supreme-court-mumbai-retailers-marathi-signboards-benefit-festive-season-8956576/), [Free Press Journal](https://www.freepressjournal.in/mumbai/mumbai-shops-violating-marathi-signboard-rules-to-face-penalties-bmc-to-initiate-action-from-november-28); Karnataka — [Business Standard](https://www.business-standard.com/india-news/what-is-the-60-kannada-signage-rule-here-s-all-to-know-about-the-law-124032100291_1.html), [The Hindu](https://www.thehindu.com/news/national/karnataka/trade-licences-of-businesses-that-dont-implement-kannada-signboard-rule-not-to-be-renewed/article69136360.ece), [LawBeat](https://lawbeat.in/news-updates/karnataka-high-court-stays-sealing-shops-not-complying-60-kannada-mandate-signboards)

## Vehicles and traffic

### Driving side
- Look for: traffic on the left, right-hand-drive cars
- Points to: India shares this with its neighbours Pakistan, Nepal, Bangladesh, Sri Lanka, Bhutan; it separates India from Myanmar and China (right-hand traffic)
- Strength: weak inside South Asia — `clues.py lookup driving-side --country India`
- Counterexamples: one-way streets, parked cars
- Sources: `data/driving_side.json` (Wikipedia table already in this repo)

### Auto-rickshaw liveries
- Look for: three-wheeler colours: green-and-yellow (CNG) versus black-and-yellow (older petrol) autos
- Points to: green-and-yellow CNG autos are named for cities such as Delhi and Agra; in Mumbai, CNG autos look like the others with a "CNG" print
- Strength: weak (single source)
- Counterexamples: Bangladesh's CNG autos are all green; liveries vary by city and change with fuel policy; electric three-wheelers have their own colours
- Sources: [Auto rickshaw — India](https://en.wikipedia.org/w/index.php?title=Auto_rickshaw&oldid=1379012288)

### Taxi liveries
- Look for: black lower half + yellow upper half; all-yellow; plain cars with yellow commercial plates
- Points to: black-and-yellow in Delhi and Maharashtra (also some in Tamil Nadu and Andhra Pradesh); yellow taxis in Kolkata/West Bengal; Chennai taxis look like private cars with yellow plates
- Strength: weak (single source)
- Counterexamples: app cabs (white, private-looking) dominate every metro; Mumbai's Premier Padmini black-and-yellow cabs reached their 20-year age limit on 29 Oct 2023, so that model dates a photo rather than placing it; Goa motorcycle taxis are also yellow-and-black
- Sources: [Taxicabs of India](https://en.wikipedia.org/w/index.php?title=Taxicabs_of_India&oldid=1361396594); Mumbai retirement: [Indian Express](https://indianexpress.com/article/cities/mumbai/six-decades-on-the-trip-ends-for-mumbais-iconic-premier-padmini-taxis-9004618/), [Times of India](https://timesofindia.indiatimes.com/city/mumbai/last-premier-padmini-taxis-into-the-sunset/articleshow/104808819.cms), [Hindustan Times](https://www.hindustantimes.com/india-news/mumbais-iconic-kaali-peeli-taxis-to-go-off-roads-after-6-decades-101698512040134.html)

### Reserved letters in the plate series
- Look for: the series letters after the RTO number on buses and official vehicles
- Points to: state-specific conventions, e.g. Tamil Nadu: G government, N state transport buses; AP/Telangana: Z state RTC buses, P police; Goa: X Kadamba buses, G government; Gujarat GJ 18 Y/Z state buses; Jammu and Kashmir: Y government buses
- Strength: weak (single source); only confirms a state already read from the code
- Counterexamples: conventions change as series run out; most states have none
- Sources: [Vehicle registration plates of India — Letters](https://en.wikipedia.org/w/index.php?title=Vehicle_registration_plates_of_India&oldid=1372866191)

## Infrastructure

### Kilometre stones: cap colour = road class
- Look for: the classic stone (white body, coloured semicircular top with the route number): canary yellow top = National Highway, brilliant green = State Highway, white = Major District Road; orange top = rural road built under PMGSY
- Points to: road class, and India (the stone design is an IRC standard); NH/SH number on the cap narrows to a corridor
- Strength: strong for road class (IRC:8 plus independent explanations); for the country itself medium (no source compares the design with neighbouring countries)
- Counterexamples: newer roads use reflective sheet-metal markers or green signboards instead; faded or repainted caps; the orange PMGSY colour is from a page that didn't load from our box (seen via the search index) and one news explainer, so treat orange as weak
- Sources: [IRC:8-1980 Type Designs for Highway Kilometre Stones](https://archive.org/details/govlawircy1980sp08_0) §6.1; [India Today, 2018](https://www.indiatoday.in/education-today/gk-current-affairs/story/why-indian-roads-have-coloured-milestones-1397059-2018-11-27); [OrissaPOST](https://www.orissapost.com/this-is-why-milestones-along-the-road-are-differently-coloured/); [PMGSY type design for ordinary kilometre stone](https://pmgsy.nic.in/type-design-ordinary-kilometer-stone)

### Kilometre stone script and destinations
- Look for: which script the place name is in, and which town it names
- Points to: on NH/SH ordinary stones the script rotates Roman → Hindi → local language, so the "local language" stones name the state's script; fifth-kilometre stones are Roman only; on district and village roads the stone is in Hindi or the regional script; the named towns are the next town and the terminal
- Strength: medium (one official standard; the road authority may change the order)
- Counterexamples: where the local script is Devanagari, Hindi and local stones look alike; road authorities may change the order; roads to tourist sites add Roman
- Sources: [IRC:8-1980](https://archive.org/details/govlawircy1980sp08_0) §4.1–4.4

### Direction signs
- Look for: language combination on green/blue guide signs
- Points to: urban roads and state highways: state language + English; National Highways: state language + Hindi + English — so the third script on an NH sign names the state's language
- Strength: medium where the state language isn't Hindi (single source); in Hindi-belt states it collapses to Hindi + English
- Counterexamples: older and municipal signs ignore the norm; hand-painted signs
- Sources: [Road signs in India](https://en.wikipedia.org/w/index.php?title=Road_signs_in_India&oldid=1365930382) (citing IRC:67-2022)

## Climate and phenology

### Monsoon state of the landscape
- Look for: monsoon clouds, standing water, saturated green versus dust and dry grass
- Points to: the southwest monsoon normally reaches the Kerala coast at the start of June, covers the country by mid-July, and withdraws from early September to early October; Tamil Nadu's main rain is the northeast monsoon from about 20 October for ~50 days — so a wet green Chennai in November is normal, a wet green Rajasthan in April isn't
- Strength: weak (single source; needs the photo date)
- Counterexamples: irrigation keeps fields green in the dry season; year-to-year onset varies by weeks
- Sources: [Monsoon of South Asia](https://en.wikipedia.org/w/index.php?title=Monsoon_of_South_Asia&oldid=1378435602)

### Kharif and rabi crops in fields
- Look for: flooded paddy, maize, cotton (kharif: sown with the first rains, May–July, harvested Sept–Nov) versus wheat, mustard (yellow flowers), barley, peas (rabi: sown around mid-November, harvested April–May)
- Points to: with a known date, which farming belt fits; flowering mustard in winter suggests the northern plains, flooded paddy in the dry season suggests irrigated deltas
- Strength: weak (single source per season; Pakistan and Bangladesh share the same calendar)
- Counterexamples: irrigated double/triple cropping; the summer zaid crop; hill farming calendars differ
- Sources: [Kharif crop](https://en.wikipedia.org/w/index.php?title=Kharif_crop&oldid=1373324852); [Rabi crop](https://en.wikipedia.org/w/index.php?title=Rabi_crop&oldid=1362469759)

### Climate zones
- Look for: overall vegetation and dryness
- Points to: tropical wet (Malabar coast, Western Ghats, southern Assam, the island UTs); tropical savanna over most of inland peninsula; hot semi-arid rain-shadow east of the Western Ghats (inland Karnataka, Tamil Nadu, western Andhra, central Maharashtra); hot desert in western Rajasthan; humid subtropical in the north and northeast; alpine in the Himalaya
- Strength: weak (single source); excludes more than it confirms
- Counterexamples: zones blur at the edges; irrigation and urban parks
- Sources: [Climate of India](https://en.wikipedia.org/w/index.php?title=Climate_of_India&oldid=1369804978)

## Terrain and water

### Physiographic zones
- Look for: horizon shape and ground: dead-flat alluvial plain with brick kilns and canals; flat-topped basalt mesas; a steep forested escarpment near the sea; sand dunes; snow peaks
- Points to: Indo-Gangetic plain (Punjab to Assam); Deccan plateau (most of the south, mostly 300–600 m); Western Ghats/Sahyadri along the west coast; Eastern Ghats (broken hills, West Bengal to Tamil Nadu); Thar desert (61% of Rajasthan's area); Himalaya along the northern border
- Strength: weak (single source); useful to drop whole regions
- Counterexamples: the Thar continues into Pakistan, the Gangetic plain into Bangladesh and Pakistan's Punjab; hills like the Aravalli break up the plain
- Sources: [Geography of India](https://en.wikipedia.org/w/index.php?title=Geography_of_India&oldid=1369825104)

## Deliberately not included

- Architecture and urban form (roof types, temple styles, colour of houses): no sources of the right quality were found; add them only with sources.
- Bus liveries of state transport corporations: change often, no consolidated source.
- Bollards, kerb paint, utility poles: no source found.
