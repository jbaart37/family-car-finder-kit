# Family Car Finder 🚗

A little app for shopping for a used car **as a family**. Instead of texting links and screenshots back and forth, everyone opens the
same page on your home Wi-Fi, votes on cars, and the family's favorites (and the local dealers worth a visit) rise to the top.

It runs on one computer in your house. It's not a polished product or a hosted service, just a handy family tool. Curious builders
are welcome to take it further.

## What it does

- **Searches the big sites for you:** CarGurus, Autotrader, Cars.com and Carvana, near your ZIP, for the body style, budget and mileage you set.
- **Keeps the list short:** ranks cars by price vs. estimated market value and shows the top picks, so you see a few dozen good options, not thousands.
- **Puts cars you can go see first:** 📍 local dealers you can visit and test-drive are listed ahead of 🚚 online sellers that deliver.
- **Lets everyone vote:** each person taps their name, then marks cars **love / like / hate**. Votes show up for everyone.
- **Learns from votes:** hate one Chevy Trax and every Trax sinks; like a model and it moves up a little. The **Family list** tab ranks everything you've voted on.
- **Shows which dealers are worth the drive:** the **Dealers to visit** tab ranks nearby dealers by how many good matches (and family favorites) they have.
- **Takes cars you found yourself:** **➕ Add a car we found** lets you paste a link and it fills in the details.
- **Has a look for everyone:** each person picks a theme: 🚗 Classic, 🥎 Ballpark (softball, dogs, capybaras), 💖 Farmhouse (hearts, dogs, goats, sheep) or 🛻 Truck Yard. Votes come with little reaction flurries.
- **Works on phones and computers.**

## Setup (about 5 minutes)

You need **Python 3.10+** ([python.org](https://www.python.org/downloads/); on Windows tick *"Add python.exe to PATH"*).

1. Download this repo (green **Code** button → *Download ZIP*, then unzip, or `git clone`).
2. Run the setup:
   - **Windows:** double-click `setup.bat`
   - **Mac / Linux:** open a terminal in the folder and run `./setup.sh`

   It installs what it needs into a private `.venv` folder (nothing system-wide), then asks for:
   - your ZIP code and search radius;
   - the vehicle type, max price and max mileage;
   - each family member's name and theme;
   - optionally, big dealer groups near you.

   It can run the first search right away.
3. Start the family page:
   - **Windows:** double-click `start.bat`
   - **Mac / Linux:** `./start.sh`

   It prints a **Family link** like `http://192.168.1.20:8765`. Text that link to the family **once**. The first time Windows asks about
   the firewall, allow **Private networks** so phones can connect.

Run setup again any time to change your answers. Votes and past searches are kept.

## How the family uses it

1. Open the family link (on the same Wi-Fi) and **tap your name**. Your phone remembers you.
2. Vote **love / like / hate** on cars. Tap a car's **photo** to see it big; tap **anywhere else on the car** to open the dealer's listing.
3. Check the **Family list** tab for the ranked shortlist, and **Dealers to visit** to plan test drives.
4. Found a car somewhere else? **➕ Add a car we found** and paste the link.

To refresh the listings in a few days, click **Edit filters → Search**. Votes carry over, price changes are flagged, and cars that
disappeared are marked *may be sold*.

## How it works (for the curious)

- **`carsearch/sources/`:** one small reader per site. It reads the same public search pages your browser does, a page at a time with short pauses.
- **`carsearch/engine.py`:** merges the same car across sites (by VIN), filters, ranks, and saves each search to `results/`.
- **`carsearch/market.py`:** estimates market value: CarGurus' own estimate where available, otherwise a fit over similar cars.
- **`carsearch/reputation.py`:** rates sellers (national retailer → dealer group → franchise / high-volume → independent), since sites don't publish dealer sales volume.
- **`car_agent.py`:** a tiny Flask server, plus a command line: `python car_agent.py search --open` writes a standalone HTML report.
- **`web/index.html`:** the whole page in one file (no build step).

Votes live in `results/votes.json`. Your settings live in `config.json`. Neither is committed to git.

**Porting it to a hosted app?** You'd want real sign-in instead of "tap your name" (there's no password: it's meant for a home
network), a database instead of JSON files, a background job for searches, and a careful read of each site's terms of use.

## Good to know

- **Personal use:** keep it to your own family's car hunt, a few searches a week. It isn't affiliated with any of these sites.
- **Sites change their pages.** If a site shows a red error chip after a search, its reader in `carsearch/sources/` needs a tweak.
- **Some sites block reading single listings.** Cars.com does, so a pasted Cars.com link that your searches haven't seen needs the details typed in.
- **Estimates are estimates.** Always confirm price, history and availability with the dealer.

## License

MIT. See [LICENSE](LICENSE).
