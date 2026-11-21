# Ferrite rod antenna

A long-wave transmitting antenna would need to be hundreds of metres tall, so
this uses a compact ferrite rod antenna instead. It's inefficient, but at
these tiny power levels it's plenty for setting watches within a few metres.

This design bundles three long rods to get more ferrite area than an AM-radio
antenna, and is wound for 60 kHz.

## Parts

| Part | Notes |
|---|---|
| 3 × ferrite rod, 9 mm × 180 mm | Jaycar LF1012 |
| ~4 m of 0.25 mm enamelled copper wire | Jaycar WW4012 or similar |
| Electrical tape | Not metal tape, which would form a shorted turn |
| Fine (400-grit) sandpaper | To strip the enamel |

Litz wire is slightly better but isn't needed. At 60 kHz the skin depth is
about 0.27 mm, so current uses the whole of a 0.25 mm wire anyway.

## 1. Bundle the rods

1. Lay the three rods in a triangle (two on the bottom, one nestled on top).
2. Tape them tightly at three or four points along their length, so they
   can't shift.
3. Optionally wrap the whole bundle in one layer of tape for a smoother
   winding surface.

Ferrite is brittle. Handle the rods gently and don't drop them.

## 2. Wind the coil

Wind **about 55 turns** in a **tight single layer at the centre** of the
bundle (it takes up about 15 mm). Leave bare ferrite either side; that's what
concentrates the field, so don't spread the winding along the rods.

1. Tape one end of the wire near the middle of the bundle, leaving a 10 cm
   tail.
2. Wind 55 turns, each touching the last, all in the same direction. If a
   turn crosses over, unwind back to it and redo it.
3. Tape the end and leave another 10 cm tail.
4. Sand about 15 mm of enamel off each tail until the copper shines, then
   tin them with solder.

Each turn around the bundle uses about 55–60 mm of wire, so 55 turns plus
tails needs about 3.5 m.

## Tuning

The coil and capacitors must resonate at exactly 60 kHz:

C = 1 / (4π² × L × f²)

With C1 + C2 = 11.5 nF, the coil needs about 610 µH. 55 turns on this bundle
lands roughly in the 550–650 µH range, so expect to trim.

**With an oscilloscope (best):** probe node B (the coil end fed by the
220 Ω resistor) with the probe ground on GND. Run the carrier only:

```bash
sudo ./time-signal -s JJY60 -c
```

Adjust the trimmer until the waveform is largest and cleanest (a smooth sine
wave). An SDR also works if it genuinely covers 60 kHz (e.g. an SDRplay RSP);
most RTL-SDR dongles don't reach that low.

**Without test equipment:** put a radio-controlled watch or clock 5–10 cm
from the coil, run the carrier, and sweep the trimmer slowly. Stop where the
watch shows the strongest reception or syncs fastest.

**If the trimmer can't reach resonance**, change C2:

| Symptom | Change C2 to | Total |
|---|---|---|
| Resonance too high in frequency | 2.2 nF | ~12.2 nF |
| Resonance too low in frequency | 1 nF | ~11 nF |

Polyester caps are typically ±10 %, so a "10 nF" part can be 9–11 nF. That's
more than the trimmer's ~1 % range covers. On the pHAT, use the spare C3/C4
pads (1206 C0G) or C5 (leaded) instead.

## Placing the antenna

The rods act as a magnetic dipole along their length. Reception is best with
the watch's own antenna **parallel** to the rods, either a little way off one
end or beside the long side. A watch at 90° to the rods may not pick it up.
Keep it away from metal surfaces, monitors and computers.

## Why three rods

Bundling three rods gives about three times the cross-section of one, and
the 180 mm length (length/diameter ≈ 20) raises the effective permeability.
Together they give several times more flux per amp than a single 100 mm AM
rod, which is the biggest single improvement in range.

Further reading: [ferrite rod antenna basics](https://www.electronics-notes.com/articles/antennas-propagation/ferrite-rod-bar-antenna/basics-tutorial.php),
and a [discussion of longer-range transmitters](https://github.com/hzeller/txtempus/issues/8)
on the txtempus project.
