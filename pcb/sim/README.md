# Pedalboard simulations

Circuit simulations of the pedalboard's analog parts and its 12 V supply, run in
[ngspice](https://ngspice.sourceforge.io/) with Texas Instruments' own SPICE models. They test
the schematic as drawn: `kinet.py` reads the parts, values and connections from the KiCad
netlist, so a change on the schematic shows up here on the next run.

## Running them

```sh
../gen/check.sh       # the netlist, ../kicad/out/pedalboard.net
./get-models.sh       # TI's models into models/ (not in git: they are TI's)
./run.py              # all of them; or ./run.py A1 A4 ...
```

Each simulation prints its numbers and PASS or FAIL. The plots go to `results/`. ngspice's
working files go to `out/`.
You need ngspice (version 44 was used) and Python 3. No Python packages are needed.

| File | What it is |
|---|---|
| `run.py` | The simulations A1–A8 and their pass marks |
| `kinet.py` | KiCad netlist to SPICE: which model each symbol becomes, and the pin order |
| `parts.lib` | Generic models for the BAV99, BC857, LED, MBR0530 and ferrite beads (Nexperia's site refuses scripted downloads) |
| `get-models.sh` | Downloads TI's models: OPA164x (sbom627), LM393 (slcj016), TPS61040 (slvmda8), TPS7A4901 (sbvm528) |
| `svgplot.py` | Draws the plots |

## Results (2026-10-23)

| # | What | Result |
|---|---|---|
| A1 | Guitar input | 910 kΩ in parallel with 29 pF. The pickup's resonance moves 4.5 %, as it would with 29 cm more lead. 2 V peak at the least gain: 0.0001 % THD |
| A2 | Gain knob | 0 to +24.2 dB. A log (A) taper gives 1–3 dB per 30° of rotation; a linear pot would put 10 dB in the first 30° |
| A3 | Noise at full gain, 10 kΩ source | The stage adds 1.4 dB to the noise of the source and the ADC together |
| A4 | Clip LED | Lights at VREF +2.62 / −2.60 V, 1.1 dB under the ADC's full scale. One 1 kHz cycle 0.5 dB over: 2 mA for 98 ms. Off below the threshold |
| A5 | Into the ADC | Flat within 0.07 dB from 20 Hz to 20 kHz. 0.1 % overshoot on a step, so no ringing |
| A6 | Main outputs | Flat into 10 kΩ and 600 Ω (−3 dB at 2 Hz and 4.5 Hz). Power-on: a slow 0.4 V swell. **Power-off: a −4.8 V thump** (see below) |
| A7 | Headphones | The knob keeps its shape within 2.7 dB under the amplifier's 37 kΩ input. Bass −3 dB at 15 Hz. A full-scale DAC signal is 1.09 V peak at the amplifier's inputs (limit 2.5 V) |
| A8 | 15 V boost, 12 V regulator | 12.04 V at 10 and 30 mA. At 10 mA the boost switches in bursts (157 kHz on average, gaps up to 47 µs), which leaves a few µV of 4–10 kHz ripple on 12 V: 93 nV at the ADC pin, 40 dB under its floor. At 30 mA it switches steadily at 373 kHz |

### What the simulations changed on the schematic

- **C43, RF filter at the op-amp input: 100 pF → 22 pF.** With 100 pF the input had 107 pF,
  as much as a metre of extra guitar lead, and the pickup's resonance fell 14 %. 22 pF still
  filters above 7 MHz with the 1 kΩ in front of it. The OPA1642 rejects RF itself: 53 dB at
  400 MHz and 87–97 dB at the Wi-Fi bands (datasheet table 1).
- **Clip LED hold: 2.2 µF / 47 kΩ / 100 kΩ → 100 nF / 2.2 MΩ / 1 MΩ.** With 2.2 µF a single
  short peak didn't light the LED at all (0.01 mA); ten cycles were needed.
- **Clip comparator: LM393 → LM393B.** The 2.2 MΩ recharge needs the B version's low output
  leakage: 50 nA at most at 36 V. The plain LM393 allows 1 µA over temperature, enough to make
  the LED glow.
- **Main output capacitors: 10 µF → 47 µF.** Into a 600 Ω load, 10 µF was −3 dB at 20 Hz.
- **Gain knob: 50 kΩ log (A) taper,** as drawn.

### The power-off thump (A6)

When the power lead is pulled while the board is running, the 12 V rail falls, and the output
buffers fall with it from their 5 V bias to 0 V. The 47 µF output capacitors pass that step to
the jacks: −4.8 V into 10 kΩ, fading over about a second. Speakers that are still on will thump.
After `shutdown` the Pi keeps the board powered, so the thump happens whenever the lead is pulled
with the board still powered.

**Decision (2026-10-23): accepted for now.** Turn the speakers off or down before pulling the
lead. If it ever needs fixing, a muting relay is the usual way: its normally-closed contacts
ground the outputs while it has no power. It would need a small detector, so that it releases
before the 12 V rail falls, and a simulation of its own.

### How far to trust these

- The op-amp, comparator and both regulators are TI's models. `get-models.sh` fixes two things
  so ngspice reads them as PSpice does:
  - TI's "noiseless" resistors needed ngspice's own `noisy=0`. Without it, ngspice gave the
    OPA1642 65 nV/√Hz of noise; with it, 5.0 nV/√Hz, against the datasheet's 5.1.
  - A typo in the TPS61040 file.
- ngspice struggles to find DC operating points with TI's op-amp model. `run.py` works around
  this without changing what is measured:
  - each op-amp output gets a 10 kΩ load through a 1 kH inductor, a load at DC only;
  - the gain stage's feedback is shorted at DC through 1 MH;
  - when one solver setting fails, the next is tried.
  `kinet.py` and `run.py` say where and why.
- The clip detector and the gain stage are simulated separately: ngspice finds no DC solution
  for the two together. A4 drives the detector from a source standing in for the stage's output.
- The TPA6130A2 has no SPICE model. Its inputs are modelled as half its lowest differential
  input impedance (37 kΩ, datasheet 9.2.2.1) to ground.
- The guitar lead (300 pF) and the 10 µH inductor's resistance (0.3 Ω) are typical values, not
  measured ones.
- A8 starts the rails at their working voltages: the 12 V regulator's soft start takes tens of
  milliseconds, which at switching speed took over 8 minutes to simulate. Between pulses, the
  boost's switch node rings down to −11 V in TI's model, which has no clamp diode on that pin;
  the real chip's diode stops it near −0.7 V. So A8 finds pulses by the switch being held on,
  not by edges.
