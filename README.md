# Racro (v1.3)

**An auto-miner for the elected-Administrator mining game — grind credits while you sleep.**

Racro plays the boring part for you. It auto-mines ore at the speed you choose,
auto-votes to keep your Administrator elected, and even pays the host. Set it up,
walk away, and come back to a pile of credits. And because every copy runs on its
own, it has **first-class alt-account support** — launch one per account and farm
a whole row of alts at once.

![Racro](docs/preview.png)

## What it does
- **Auto-mines** — finds the ore on its own and holds to mine it. No setup beyond a click.
- **Auto-votes the elected admin** — keeps your pick in power without you watching.
- **Auto-pays the host** — types `;pay <host> 10000` every 10,000 mines.
- **Never sits dead** — rejoins if the game crashes, reconnects when the disconnect
  popup shows up, and walks back to the ore after it respawns you.

## Make 20,000–40,000 credits overnight
Pick a speed, hit Start, go to sleep. On a single account, hands-off, Racro can
pull in roughly **20k–40k credits a night** all on its own (depending on your
mining speed and the server). Stack it across alts and that number just multiplies.

## Built for alts
Every instance is fully self-contained and self-healing: it finds its *own* ore,
votes, pays, and rejoins independently, and runs with **no console window**. So you
can fire one up on each account and they'll all grind in parallel without stepping
on each other. (Running many instances on one PC also needs a multi-instance/RDP
setup — that part lives outside this repo.)

## Install (it's easy)
1. Click the green **Code** button up top → **Download ZIP**, and unzip it anywhere.
2. Double-click **`Install.bat`**. If it installs Python for you, close it and run
   it **one more time** so it can finish.
3. Double-click **`Start Racro`**. That's it — the little Racro window pops up, no
   scary black terminal.

(Already have Python 3? You can skip the installer; `pip install keyboard` is
optional and only adds the F2 hotkey.)

## How to use
1. Open the game and stand near the ore.
2. Pick a speed and click **Start** — it finds the ore and starts mining. (Or hover
   the ore and tap **F2** to set the spot by hand.)
3. Flip on whatever extras you want — auto-rejoin, auto-vote, auto-pay.

## Tuning
Speeds, the pay amount, and the detection thresholds are plain constants at the top
of `mining_macro.py` — change a number, save, done.

## Heads up
This automates Roblox and supports running alt accounts, both of which are against
the Roblox Terms of Service and can get accounts banned. It's for learning and
personal use — use it at your own risk. Not affiliated with or endorsed by Roblox.

## License
MIT — see [LICENSE](LICENSE).
