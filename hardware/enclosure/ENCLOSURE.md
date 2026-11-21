# Enclosure: Pi 60 kHz Time-Signal Transmitter

One box holds the Raspberry Pi Zero, the pHAT stacked on it, and the 3-rod ferrite antenna
lying along the back wall.

- Outside size: 194.4 x 66.4 x 36 mm (base 34 mm + lid 2 mm)
- Parts: `base.stl`, `lid.stl` (the lid is already flipped for printing)
- Source: `pi_time_tx_enclosure.scad` (OpenSCAD; every dimension is a named variable at the top)

## Printing
- Needs a bed at least 200 mm long in one direction (Ender 3, Prusa, Bambu P1/X1/A1 are fine;
  a 180 mm bed such as the A1 mini is too small).
- PLA or PETG, 0.2 mm layers, 3 walls, 15-20 % infill, **no supports**.
- Base: print open side up. Lid: print as exported (flat face down, lip up).
- Rough material use: about 60-70 g (base) and 25 g (lid).
- Everything is designed to print without supports: the port openings are short bridges and
  the lid-screw bosses have 45-degree ramps underneath.

## Hardware
| Qty | Part | Used for |
|-----|------|----------|
| 4 | M2.5 x 11 mm male-female hex standoff (6 mm thread, brass or nylon) | between the Pi and the pHAT |
| 4 | M2.5 x 5 or 6 mm screw | pHAT into the standoffs |
| 4 | M3 x 10 mm countersunk self-tapping screw | lid |
| 2-3 | small cable ties, 2.5 mm wide | hold the antenna in its saddles |
| 4 | stick-on rubber feet (optional) | |

Keep metal screws and standoffs to the Pi end of the box; nothing metal sits near the ferrite.

## Assembly
1. Fit a microSD card in the Pi first (it's reachable through the slot in the left end later).
2. Screw the 4 male-female standoffs down through the Pi's mounting holes into the printed
   posts in the base. The male thread self-taps into the 2.2 mm holes; don't overtighten.
   The Pi's ports line up with the openings in the front wall.
3. Plug the pHAT onto the Pi's header and fix it to the standoffs with the M2.5 screws.
4. Lay the antenna bundle in the four saddles along the back wall, with the winding in the
   gap in the middle. Thread a cable tie through the tunnel in two of the saddles and around
   the bundle.
5. Run the two coil leads forward to the screw terminal (J2) and tighten them in, either way
   round. Keep the leads tidy and away from the Pi.
6. Fit the lid and screw it down. Power comes in through the Pi's micro-USB PWR port.

## Placement for best range
The rods radiate as a magnetic dipole along their length. Range is best with the clock's own
antenna parallel to the box: either a little way off one end in line with the rods, or beside
the long side. A clock turned 90 degrees to the box may not pick up the signal at all.

## Checks done
- Both STL files are single, watertight solids.
- The Pi, pHAT, standoffs, screw terminal and antenna were modelled in place and checked for
  collisions with the base and lid: none.
- Port positions use the Pi Zero's published mechanical drawing (mini-HDMI at 12.4 mm,
  USB at 41.4 mm, PWR at 54.0 mm from the left edge). The openings are oversized so moulded
  cable plugs fit. Print a test strip of the front wall first if your cables are unusually bulky.
