---
name: car-search
description: Search large used-car sites (CarGurus, Autotrader, Cars.com, Carvana) near the family's ZIP using the shared family filters in config.json, rank cars by price vs. market, put local dealers you can test-drive ahead of online/delivery sellers, and summarize what the family has voted on. Use when the user wants to find, shop for, or compare used cars.
---

# Car search

The project in this repo (`car_agent.py` + `carsearch/`) does the crawling. Your job is to run it with the right filters and summarize the results.

If `config.json` doesn't exist yet, ask the user to run setup first (`setup.bat` on Windows, `./setup.sh` on Mac/Linux).

## Family filters come first

The family shares one set of filters: `family_profile` in `config.json`. Use them unless the user asks for something different.
For a one-off question, pass CLI flags; change `family_profile` only when the user says the family's criteria changed.

| Flag | Meaning |
|---|---|
| `--zip` / `--radius` | location |
| `--body` | `suv sedan truck coupe convertible hatchback minivan van wagon` |
| `--sizes` | SUV sizes: `subcompact,compact,midsize,fullsize` |
| `--max-price` / `--max-miles` / `--min-year` | caps |
| `--make` | repeatable make/model text, e.g. `--make "Toyota RAV4"` |
| `--min-tier` | seller quality: 2 = franchise/high-volume and up (default) |

```bash
python car_agent.py search --open        # family filters (use .venv's python if it exists)
```

It saves `results/<stamp>.json` (the live page loads the newest one for everyone) and `reports/<stamp>.html`.

## Family votes

`results/votes.json`: `{url: {"listing": {...}, "votes": {name: "love"|"like"|"hate"}, "manual": bool, "added_by", "note"}}`.
Rank by points (love +3, like +1, hate -3), with the lower price breaking ties. Votes count for the whole make and model: put last any model whose
summed points are negative, and lean slightly toward models with positive points. `"manual": true` means a family member added the car.
Never edit or delete votes.json.

## Report back

- Lead with **local dealers** (channel `local`), the cars the family can go see; list online/delivery sellers separately.
- For each car give year, make, model, mileage, price, and the estimated difference from market (`price_diff`; negative = below market).
- Name the dealers with the most good matches, and mention any site that errored.
- Use only listings the run returned.
