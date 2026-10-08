# Clue library

Check against it in steps 2 and 4. Entry sources are marked `vNNN` (the number of a creator video the author broke down; the breakdown notes are not public) or `case` (a real case); `india.md` cites public documents by URL instead.

## Files

| File | Scope |
|---|---|
| `china.md` | Mainland China: platform metadata, text and plates, vehicles and traffic, infrastructure, climate and phenology, terrain and water, urban form |
| `global.md` | Outside China: general (driving side, plate shape), Europe, North America, Mexico, Japan, Southeast Asia |
| `india.md` | India: plates and plate colours, STD codes, PIN codes, scripts and signboard laws, autos and taxis, kilometre stones and road signs, monsoon and crop seasons, climate and terrain zones (public sources, by URL) |

## Entry format

```markdown
### <clue name>
- Look for: exactly what to find in the image and how to recognize it
- Points to: country / province / city / type of area within a city
- Strength: strong (a single clue reaches this level) / medium (needs one more) / weak (can only exclude or boost)
- Counterexamples: when it leads to a wrong call
- Sources: vNNN or case (or URLs, as in india.md)
```

## Rules

- Every entry must state strength and counterexamples. A clue with no counterexample usually just hasn't been seen to mislead yet; that doesn't make it reliable.
- A clue can be marked "strong" only when three or more sources mention it independently; for a single source, write "(single source)".
- **Only include clues that transfer to new photos.** What one particular landmark looks like (a certain bridge, fountain, or building) doesn't go into the library: it won't help with the next photo, and it contaminates evaluations built from video puzzles.
- **Counterexamples and source notes also never state a specific puzzle's place names or conclusion** (writing "puzzle X's IP was in province A, actually in city B" amounts to writing the answer into the skill). When citing a puzzle, state only method-level facts ("the photo was in a province neighboring the IP province"). The same goes for script examples: use places unrelated to eval puzzles, or `<placeholders>`.
- Strength changes with context: the same plate is strong evidence on the street and weak evidence in a parking lot; vegetation without a month is always weak.
- Write methods in your own words; don't copy the video's wording verbatim.
