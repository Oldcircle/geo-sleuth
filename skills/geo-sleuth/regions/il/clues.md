# Israel clues

Entries use the shared format (`references/clues/README.md`). Clues that tell Israel apart from its neighbours belong in `references/clues/global.md`.

## Text and numbers

### Landline area code
- Look for: a fixed-line number on a shop sign or vehicle: `0X-XXX-XXXX` with X = 2, 3, 4, 8 or 9
- Points to: 02 Jerusalem area; 03 Tel Aviv and Gush Dan; 04 Haifa and the north; 08 the Shephelah and the south; 09 the Sharon → `clues.py lookup area-code <number> --country il`
- Strength: weak (five codes for the whole country; each covers several districts)
- Counterexamples: `05x` is mobile and `07x` is VoIP, both used nationwide; `1-700`/`1-800` business numbers; the same digits are used in the West Bank and Gaza under +970
- Sources: en.wikipedia "Telephone numbers in Israel", section "Geographic area codes", https://en.wikipedia.org/wiki/Telephone_numbers_in_Israel

## Roads

### Road number: digit count, parity and size
- Look for: the route number on a road sign or route shield
- Points to: digit count gives the class (1 national, 2 inter-city, 3 regional, 4 local). Even numbers run south–north, odd numbers west–east. Among roads with the same number of digits, numbers rise from south to north (west–east roads) and from west to east (south–north roads): 1x roads are in the far south, 9x roads in the far north-east. Pick the band, then `osm.py route` along that road
- Strength: medium (two sources)
- Counterexamples: there are exceptions (Highway 1 lies mostly north of Highway 3); roads in the West Bank and Golan Heights use the same scheme
- Sources: en.wikipedia "Roads in Israel", section "Numbering of the roads", https://en.wikipedia.org/wiki/Roads_in_Israel; he.wikipedia "כבישי ישראל" (even = south–north, odd = west–east, numbers rise northward and eastward), https://he.wikipedia.org/wiki/כבישי_ישראל
