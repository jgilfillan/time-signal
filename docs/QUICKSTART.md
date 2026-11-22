# Your radio time-signal transmitter — quick start

This little box sets radio-controlled watches and clocks by sending the
Japanese **JJY 60 kHz** time signal (Japan time; your watch adds your own
time-zone offset). It gets the exact time from the internet, so it needs your
Wi-Fi.

## 1. Plug it in

Use a USB phone charger (5 V, 1 A or more) in the port marked **PWR**.
Give it about a minute to start.

## 2. Connect it to your Wi-Fi (first time only)

1. On your phone, open Wi-Fi settings and join the network with the name
   on the label, e.g. **jjy-1a2b**. (It has no password.)
2. A set-up page should open by itself. If it doesn't, open a browser and go
   to any web address, e.g. `http://example.com`.
3. Choose your home Wi-Fi, type its password and tap **Connect**.
4. Your phone drops off the jjy network. That's normal. Rejoin your home
   Wi-Fi.

It remembers your Wi-Fi from now on. If it ever can't find it (new router,
moved house), the **jjy-…** network appears again and you repeat this step.

## 3. Set your watch

The box starts transmitting on its own as soon as it has the correct time.
Then:

- Put the watch **close to the box (within about 1 m)**, lined up **parallel**
  to the box's long side.
- Start a manual time reception on the watch (see its manual; usually a
  long-press of a button) with the watch set to receive **JJY**.
- Leave it still for a few minutes until reception completes.

Keep it away from computers, monitors and metal surfaces, which can drown out
the signal.

## Checking what it's doing

Open **http://jjy-1a2b.local:8080** (use the name on your label) in a
browser on the same Wi-Fi. The page shows:

- **Transmitting / Waiting for time sync / Stopped**
- the **station time** being sent
- whether the **clock is synced** to internet time
- the device's address and a live log

If `.local` doesn't open on your phone (some Android phones), use the
number address shown on the page or listed in your router.

## Good to know

- It's safe to just unplug it. Nothing gets corrupted.
- It only reaches a few metres. That's deliberate: it's a very low-power
  transmitter for your own clocks.
- If the status page says **Waiting for time sync** for more than a few
  minutes, the box isn't reaching the internet. Check your Wi-Fi.
