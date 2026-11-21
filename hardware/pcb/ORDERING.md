# Pi 60 kHz Time-Signal pHAT v1.2 - ordering at JLCPCB (5 units)

## Files to upload
- pi_time_tx_gerbers_JLCPCB.zip  (board)
- jlcpcb_bom.csv                 (parts list, 9 lines)
- jlcpcb_cpl.csv                 (placement, 9 parts)

## Steps
1. jlcpcb.com > Order now > upload pi_time_tx_gerbers_JLCPCB.zip
   - 2 layers, 65 x 30 mm, qty 5, 1.6 mm, HASL lead-free, any colour
2. Tick "PCB Assembly", PCBA qty 5.
   - Choose Standard assembly (Economic can't do through-hole parts or both sides).
   - Assembly side: both sides. J1 goes on the BOTTOM, everything else on the top.
3. Upload jlcpcb_bom.csv and jlcpcb_cpl.csv.
   - C3, C4 and C5 are intentionally left empty (tuning spots).
   - Both connectors are factory-fitted: J1 (40-pin socket, C2977589) and
     J2 (screw terminal, C8465).
4. In the placement preview, check and rotate anything that's wrong:
   - Q1 (SOT-23): pin-1 dot top-left, single pin (drain) on the right.
   - C1, C2, C6, R1, R2, R3 sit centred on their pads.
   - J1 sits on the bottom, centred over its 40 holes.
   - J2's wire openings face the right-hand board edge.

## What you do yourself
- Wind the antenna: 3 x 9x180 mm ferrite rods (Jaycar LF1012), ~55 turns of
  0.25 mm enamelled wire, and screw its two leads into J2 (either way round).
- Mount on the Pi with ~11 mm standoffs (8.5 mm socket + the Pi header's plastic).

## v1.2 change
The strip of the board above the Pi Zero W / Zero 2 W's built-in Wi-Fi antenna (port edge,
between the mini-HDMI and USB sockets) has no copper on either layer, so the pHAT doesn't
shield Wi-Fi or Bluetooth. The circuit and parts are unchanged from v1.1.

## Circuit (parallel tank, as tested on the breadboard)
5V -> R1 220R -> TANK_B. The ferrite coil (J2) and C1 10nF + C2 1.5nF (+ optional C3/C4/C5)
sit in parallel between TANK_B and TANK_A. Q1 AO3400A drain on TANK_A, source to GND,
gate from GPIO4 via R2 470R; R3 100k holds Q1 off while the Pi boots. C6 10uF decouples 5V.
11.5 nF resonates at 60 kHz with about 610 uH of coil.

## Tuning
Run: sudo ./time-signal -s WWVB -c   (or -s MSF)
If a board needs trimming, add a small C0G cap in C3/C4 (1206) or a leaded cap in C5
until a clock syncs best, or a scope on TANK_B shows the largest clean sine wave.
