#!/usr/bin/env python3
"""The pedalboard's simulations (plan.md section 11), in ngspice with TI's models.

Usage: ./run.py [A1 A2 ...]   (all of them when none is given)
Needs ngspice and the models from ./get-models.sh, and the netlist from ../gen/check.sh.
Each one prints its numbers and whether it passes, and writes its plots to results/.
"""

import cmath
import math
import os
import subprocess
import sys

import kinet
import svgplot

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
RESULTS = os.path.join(HERE, "results")
AUDIO_MODELS = ["models/opa164x.lib", "models/lm393.lib", "parts.lib"]
POWER_MODELS = ["models/tps61040.lib", "models/tps7a4901.lib", "parts.lib"]  # both define the same d_d1

V12 = 12.05  # the TPS7A4901's output with 909k / 100k (plan 4.4)
ADC_FS_PEAK = 2.1 * math.sqrt(2)  # PCM1863 single-ended full scale, 2.1 Vrms (datasheet 7.5)
ADC_SNR_DB = 106  # PCM1863 single-ended SNR, 0 dB PGA, A-weighted (datasheet 7.5)
ADC_RIN = 20e3  # PCM1863 input impedance per pin (datasheet 7.5)

os.chdir(HERE)
PARTS = kinet.load()
REPORT = []


def say(line=""):
    print(line)
    REPORT.append(line)


def check(name, ok, detail):
    say(f"  {'PASS' if ok else 'FAIL'}  {name}: {detail}")
    return ok


# ngspice's DC solution with TI's op-amp model is erratic: a deck that fails converges after a
# small change of solver settings, at the same operating point (within microvolts). Each run
# tries these in turn; none of them changes the circuit.
SOLVER = ["itl1=1000", "itl1=1000 noopiter", "itl1=1000 abstol=1e-10", "itl1=1000 gmin=1e-13",
          "itl1=1000 gmin=1e-11", "itl1=1000 abstol=1e-10 noopiter"]


def ngspice(name, lines, control, models=AUDIO_MODELS):
    """Run one netlist; control: ngspice commands, which write data with 'wrdata <name>.<n> ...'."""
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, ".spiceinit"), "w") as f:
        f.write("set ngbehavior=psa\nset wr_singlescale\nset wr_vecnames\nset num_threads=4\n")
    for options in SOLVER:
        deck = [f"* {name}"] + [f".include {os.path.join(HERE, m)}" for m in models] + \
            [f".options {options}"] + list(lines) + [".control", *control, "quit", ".endc", ".end"]
        path = os.path.join(OUT, f"{name}.cir")
        with open(path, "w") as f:
            f.write("\n".join(deck) + "\n")
        r = subprocess.run(["ngspice", "-b", f"{name}.cir"], cwd=OUT, capture_output=True, text=True)
        with open(os.path.join(OUT, f"{name}.log"), "w") as f:
            f.write(r.stdout + r.stderr)
        if not any(s in r.stdout + r.stderr for s in ("stepping failed", "Timestep too small")):
            break
    else:
        sys.exit(f"{name}: no DC operating point or the transient stopped, see out/{name}.log")
    if r.returncode or "rror" in r.stderr:
        sys.exit(f"{name}: ngspice failed, see out/{name}.log\n{r.stderr[-2000:]}")


def data(fname):
    """Columns of an ngspice wrdata file, by vector name."""
    with open(os.path.join(OUT, fname)) as f:
        names = f.readline().split()
        cols = [[] for _ in names]
        for line in f:
            for i, v in enumerate(line.split()):
                cols[i].append(float(v))
    return dict(zip(names, cols))


def at(xs, ys, x):
    """Linear interpolation of ys at x (xs ascending)."""
    for i in range(1, len(xs)):
        if xs[i] >= x:
            f = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
            return ys[i - 1] + f * (ys[i] - ys[i - 1])
    return ys[-1]


def a_weight_db(f):
    """IEC 61672 A-weighting in dB."""
    f2 = f * f
    ra = (12194 ** 2 * f2 * f2) / ((f2 + 20.6 ** 2) * math.sqrt((f2 + 107.7 ** 2) * (f2 + 737.9 ** 2)) *
                                    (f2 + 12194 ** 2))
    return 20 * math.log10(ra) + 2.0


def integrate(fs, density, weight=None):
    """RMS from a noise density (V/sqrt(Hz)) over the frequency points (trapezoids)."""
    total = 0.0
    for i in range(1, len(fs)):
        g0 = 10 ** (weight(fs[i - 1]) / 10) if weight else 1
        g1 = 10 ** (weight(fs[i]) / 10) if weight else 1
        total += (density[i - 1] ** 2 * g0 + density[i] ** 2 * g1) / 2 * (fs[i] - fs[i - 1])
    return math.sqrt(total)


def solve(a, b):
    """Gaussian elimination for a small dense system a x = b."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[piv] = m[piv], m[c]
        for r in range(n):
            if r != c:
                f = m[r][c] / m[c][c]
                m[r] = [x - f * y for x, y in zip(m[r], m[c])]
    return [m[i][n] / m[i][i] for i in range(n)]


def harmonics(ts, vs, f0, n=5, periods=4):
    """Amplitudes of the first n harmonics over the last few periods of a transient: a least-squares
    fit of an offset, a drift (the coupling capacitors still settling) and the harmonics together."""
    pts = [(t, v) for t, v in zip(ts, vs) if t > ts[-1] - periods / f0]
    t0 = pts[0][0]

    def basis(t):
        w = 2 * math.pi * f0 * t
        return [1.0, (t - t0) * f0] + [g(k * w) for k in range(1, n + 1) for g in (math.cos, math.sin)]
    rows = [basis(t) for t, _ in pts]
    size = len(rows[0])
    ata = [[sum(r[i] * r[j] for r in rows) for j in range(size)] for i in range(size)]
    atb = [sum(r[i] * v for r, (_, v) in zip(rows, pts)) for i in range(size)]
    x = solve(ata, atb)
    return [math.hypot(x[2 + 2 * k], x[3 + 2 * k]) for k in range(n)]


# --- The guitar input: plan 5.3, the input sheet plus the ADC's input network ----------------

GUITAR = kinet.on_sheet(PARTS, "Guitar input")
# The clip detector (5.4) listens to the stage output through 10 kohm into comparator inputs.
# ngspice finds no DC solution for the stage and the detector together with TI's models, so the
# stage simulations leave it out and A4 drives it from a source.
CLIP_NETS = [kinet.node_name(n) for n in ("CLIP_SENSE", "CLIP_HI", "CLIP_LO", "CLIP_N", "CLIP_HOLD",
                                           "CLIP_BASE", "CLIP_COL", "CLIP_LED_A")]
CLIP = [r for r in GUITAR if r in kinet.touching(PARTS, GUITAR, CLIP_NETS) or PARTS[r].lib == "Comparator:LM393"]
STAGE = [r for r in GUITAR if r not in CLIP]
ADC_NET = kinet.touching(PARTS, kinet.on_sheet(PARTS, "Audio converters and clocks"),
                         ["ADC_DRIVE", "ADC_AC", "ADC_VINL1"])
ADC_NET = [r for r in ADC_NET if not r.startswith("U")]  # the PCM1863 itself is the load below
ADC_LOAD = [f"R_adc ADC_VINL1 adc_bias {ADC_RIN:g}", "V_adcbias adc_bias 0 1.65"]
SUPPLY = [f"V12 P12VA 0 {V12}"]
# Pickup: about 7 kohm and 3 H (plan 11, A1), with a 3 m lead at about 100 pF/m (a typical
# guitar lead; assumed).
PICKUP = ["R_pu src pu1 7k", "L_pu pu1 pu2 3", "C_lead pu2 0 300p"]


def guitar_deck(gain_p, source, extra=(), values=None):
    """The input stage with RV1 at fraction gain_p (0 = least gain); source drives GTR_TIP."""
    lines = kinet.spice(PARTS, STAGE + ADC_NET, pots={"RV1.1": gain_p, "RV1.2": 0.5}, values=values)
    # ngspice's DC solution with TI's model fails for most settings of the gain knob. The feedback
    # carries no DC current (the 100 uF blocks Rg), so 1 MH across it shorts it at DC only:
    # 126 Mohm at 20 Hz, beside at most 33 kohm, changes nothing measured.
    aid = ["L_dcfb ADC_DRIVE GTR_FB 1meg"]
    return lines + aid + SUPPLY + ADC_LOAD + list(source) + list(extra)


def a1():
    say("A1  Guitar input: input impedance, response with a pickup, headroom at least gain")
    ok = True
    # Input impedance at the jack tip.
    ngspice("a1_zin", guitar_deck(0, ["V_t GTR_TIP 0 dc 0 ac 1"]),
            ["ac dec 20 10 100k", "let zin = mag(1 / i(V_t))", "let zph = ph(-1 / i(V_t)) * 180 / pi",
             "wrdata a1_zin.dat zin zph"])
    d = data("a1_zin.dat")
    f, z = d["frequency"], d["zin"]
    z1k = at(f, z, 1e3)
    z20 = at(f, z, 20)
    z20k = at(f, z, 20e3)
    # An R in parallel with a C from the 20 kHz value: C = sqrt(1/z^2 - 1/R^2) / w.
    r_in = at(f, z, 100)
    c_in = math.sqrt(max(1 / z20k ** 2 - 1 / r_in ** 2, 0)) / (2 * math.pi * 20e3)
    say(f"  |Zin| {z20 / 1e3:.0f} k at 20 Hz, {z1k / 1e3:.0f} k at 1 kHz, {z20k / 1e3:.0f} k at 20 kHz:"
        f" about {r_in / 1e3:.0f} k in parallel with {c_in * 1e12:.0f} pF")
    ok &= check("resistive part >= 900 k", r_in >= 900e3, f"{r_in / 1e3:.0f} k")
    # The capacitance adds to the lead's (about 100 pF/m): less than half a metre's worth.
    ok &= check("capacitance under 50 pF (half a metre of lead)", c_in < 50e-12,
                f"{c_in * 1e12:.0f} pF, like {c_in / 100e-12 * 100:.0f} cm more lead")
    svgplot.plot(os.path.join(RESULTS, "a1-input-impedance.svg"), "A1: input impedance at the jack",
                 [("|Zin|", f, [v / 1e3 for v in z])], "Hz", "kohm", xlog=True, ylog=True)

    # Response with a pickup and lead, against the same pickup into an ideal 1 Mohm input; and
    # the same with other values of the RF filter capacitor at the op-amp pin.
    rf_cap = [r for r in STAGE if PARTS[r].lib == "Device:C" and set(PARTS[r].pins.values()) == {"GTR_IN", "0"}][0]
    series = []
    for cval in [PARTS[rf_cap].value] + [v for v in ("100pF", "47pF", "22pF", "10pF")
                                          if v != PARTS[rf_cap].value.split()[0]]:
        name = "a1_resp_" + cval.split()[0]
        ngspice(name, guitar_deck(0, ["V_s src 0 dc 0 ac 1"] + [l.replace("pu2", "GTR_TIP") for l in PICKUP] +
                                  ["V_r rsrc 0 dc 0 ac 1", "R_rpu rsrc rpu1 7k", "L_rpu rpu1 rpu2 3",
                                   "C_rlead rpu2 0 300p", "R_ideal rpu2 0 1meg"], values={rf_cap: cval}),
                ["ac dec 400 10 100k", "let out = vdb(ADC_VINL1)", "let ref = vdb(rpu2)", "let diff = out - ref",
                 f"wrdata {name}.dat out ref diff"])
        d = data(f"{name}.dat")
        f = d["frequency"]
        # The pickup's resonance (its peak) is what the ear hears change: compare its frequency
        # and height with the same pickup and lead into an ideal 1 Mohm input.
        mid_o, mid_r = at(f, d["out"], 200), at(f, d["ref"], 200)
        pk_o = max(zip(d["out"], f))
        pk_r = max(zip(d["ref"], f))
        shift = (pk_o[1] / pk_r[1] - 1) * 100
        height = (pk_o[0] - mid_o) - (pk_r[0] - mid_r)
        rf_corner = 1 / (2 * math.pi * 1e3 * kinet.value(cval))
        line = (f"resonance {pk_o[1] / 1e3:.2f} kHz ({shift:+.1f} %), peak {pk_o[0] - mid_o:+.1f} dB "
                f"({height:+.1f} dB); RF corner with the 1k {rf_corner / 1e6:.1f} MHz")
        if cval == PARTS[rf_cap].value:
            say(f"  ideal 1 Mohm input: resonance {pk_r[1] / 1e3:.2f} kHz, peak {pk_r[0] - mid_r:+.1f} dB")
            say(f"  with {rf_cap} = {cval} (the schematic): {line}")
            series.append(("ideal 1 Mohm input", f, d["ref"]))
        else:
            say(f"  with {rf_cap} = {cval}: {line}")
        series.append((f"this input, {rf_cap} {cval.split()[0]}", f, d["out"]))
    svgplot.plot(os.path.join(RESULTS, "a1-pickup-response.svg"),
                 "A1: pickup (7k + 3 H, 300 pF lead) at the ADC pin, least gain",
                 series, "Hz", "dB", xlog=True, ylim=(-30, 15))

    # Headroom: a 2 V peak, 1 kHz input at the least gain.
    ngspice("a1_tran", guitar_deck(0, ["V_s src 0 sin(0 2 1k)", "R_src src GTR_TIP 7k"]),
            ["tran 2u 30m 0 2u", "wrdata a1_tran.dat v(ADC_DRIVE) v(ADC_VINL1)"])
    d = data("a1_tran.dat")
    t, v = d["time"], d["v(ADC_DRIVE)"]
    h = harmonics(t, v, 1e3)
    thd = math.sqrt(sum(x * x for x in h[1:])) / h[0]
    tail = [x for tt, x in zip(t, v) if tt > 20e-3]
    ok &= check("2 V peak at least gain, no clipping", thd < 1e-3 and max(tail) < V12 - 0.5 and min(tail) > 0.5,
                f"output {min(tail):.2f}..{max(tail):.2f} V, THD {thd * 100:.4f} %")
    return ok


# Alps' 15A (log) taper, read from the RK09L catalog's chart: rotation from terminal 1 to 3 (%),
# output across terminals 1-2 (%). Two straight stretches, not a smooth log curve.
ALPS_15A = [(0, 0.5), (5, 0.7), (10, 1), (20, 2), (23, 2.5), (30, 6), (40, 11.5), (50, 16), (60, 21),
            (64, 24), (68, 28), (72, 36), (76, 48), (80, 61), (84, 74), (88, 85), (90, 90), (93, 96),
            (96, 99.5), (100, 100)]


def pot_taper(kind, x):
    """Fraction of the track between terminal 1 and the wiper at rotation x (0..1, clockwise).
    'B' linear; 'A' Alps 15A (log); 'C' reverse log (15A mirrored)."""
    if kind == "B":
        return x
    if kind == "C":
        return 1 - pot_taper("A", 1 - x)
    return at([r / 100 for r, _ in ALPS_15A], [o / 100 for _, o in ALPS_15A], x)


def gain_curve(rv1=None):
    ps = [i / 50 for i in range(51)]
    gains = []
    for i, p in enumerate(ps):
        name = f"a2_{i}"
        ngspice(name, guitar_deck(p, ["V_s GTR_TIP 0 dc 0 ac 1"], values={"RV1": rv1} if rv1 else None),
                ["ac lin 1 1k 1k", f"let g = vdb(ADC_DRIVE)", f"wrdata {name}.dat g"])
        gains.append(data(f"{name}.dat")["g"][0])
    return ps, gains


def a2():
    say("A2  Gain over the knob's rotation")
    ps, gains = gain_curve()
    ok = check("range 0 to about +24 dB", abs(gains[0]) < 0.3 and 22 <= gains[-1] <= 26,
               f"{gains[0]:+.1f} dB .. {gains[-1]:+.1f} dB")
    series, steps = [], {}
    for kind in ("B", "A", "C"):
        xs = [i / 100 for i in range(101)]
        gs = [at(ps, gains, pot_taper(kind, x)) for x in xs]
        series.append((f"{kind} taper", [x * 300 for x in xs], gs))
        # dB per 10 % of rotation: the largest step against the average
        d = [gs[i + 10] - gs[i] for i in range(0, 91, 10)]
        steps[kind] = (max(d), (gs[-1] - gs[0]) / 10)
        say(f"  {kind} taper: dB per 30 degrees of rotation " + " ".join(f"{x:.1f}" for x in d))
    best = min(steps, key=lambda k: steps[k][0] / steps[k][1])
    say(f"  smoothest: {best} taper (largest step {steps[best][0]:.1f} dB against an average {steps[best][1]:.1f} dB)")
    svgplot.plot(os.path.join(RESULTS, "a2-gain-taper.svg"), "A2: gain over the knob (300 degree rotation)",
                 series, "rotation, degrees", "gain, dB")
    return ok


def a3():
    say("A3  Noise at full gain with a 10 kohm source")
    ngspice("a3", guitar_deck(1, ["V_s src 0 dc 0 ac 1", "R_s src GTR_TIP 10k"]),
            ["noise v(ADC_VINL1) V_s dec 20 20 20k", "setplot noise1",
             "wrdata a3.dat onoise_spectrum inoise_spectrum"])
    d = data("a3.dat")
    f = d["frequency"]
    total = integrate(f, d["onoise_spectrum"], a_weight_db)
    # The 10 kohm source's own noise, through the same gain (onoise / inoise is the gain).
    e_src = math.sqrt(4 * 1.380649e-23 * 300.15 * 10e3)
    source = integrate(f, [e_src * o / i for o, i in zip(d["onoise_spectrum"], d["inoise_spectrum"])], a_weight_db)
    stage = math.sqrt(max(total ** 2 - source ** 2, 0))
    adc = 2.1 / 10 ** (ADC_SNR_DB / 20)
    say(f"  A-weighted at the ADC pin: source {source * 1e6:.1f} uV, the stage's own {stage * 1e6:.1f} uV, "
        f"ADC floor {adc * 1e6:.1f} uV (2.1 Vrms / {ADC_SNR_DB} dB)")
    with_stage = math.sqrt(total ** 2 + adc ** 2)
    without = math.sqrt(source ** 2 + adc ** 2)
    nf = 20 * math.log10(with_stage / without)
    # The source alone is already above the ADC's floor at this gain, so no stage could stay under
    # it; what matters is how much the stage adds to the noise you would get anyway.
    ok = check("the stage adds under 3 dB to source + ADC noise at full gain", nf < 3,
               f"{nf:.1f} dB ({with_stage * 1e6:.1f} against {without * 1e6:.1f} uV)")
    svgplot.plot(os.path.join(RESULTS, "a3-noise.svg"), "A3: noise density at the ADC pin, full gain, 10 kohm source",
                 [("total", f, [x * 1e9 for x in d["onoise_spectrum"]]),
                  ("10 kohm source alone", f, [e_src * o / i * 1e9 for o, i in
                                               zip(d["onoise_spectrum"], d["inoise_spectrum"])])],
                 "Hz", "nV/sqrt(Hz)", xlog=True, ylog=True)
    return ok


def a5():
    say("A5  Into the ADC: the 10 uF, 100 ohm, 10 nF network and the PCM1863's 20 kohm input")
    ok = True
    for p, label in ((0, "least"), (1, "full")):
        ngspice(f"a5_{p}", guitar_deck(p, ["V_s GTR_TIP 0 dc 0 ac 1"]),
                ["ac dec 40 1 1meg", "let g = vdb(ADC_VINL1) - vdb(ADC_DRIVE)", "let s = vdb(ADC_VINL1)",
                 f"wrdata a5_{p}.dat g s"])
        d = data(f"a5_{p}.dat")
        f = d["frequency"]
        ref = at(f, d["g"], 1e3)
        lo, hi = at(f, d["g"], 20) - ref, at(f, d["g"], 20e3) - ref
        ok &= check(f"network flat 20 Hz-20 kHz ({label} gain)", abs(lo) < 0.1 and abs(hi) < 0.1,
                    f"{lo:+.3f} dB at 20 Hz, {hi:+.3f} dB at 20 kHz")
        if p == 1:
            svgplot.plot(os.path.join(RESULTS, "a5-adc-network.svg"), "A5: op-amp output to ADC pin",
                         [("network", f, d["g"])], "Hz", "dB", xlog=True, ylim=(-6, 1))
    # Stability: a small step at full gain, looking for ringing at the op-amp output.
    ngspice("a5_step", guitar_deck(1, ["V_s GTR_TIP 0 pulse(0 10m 1m 1u 1u 1m 2m)"]),
            ["tran 20n 1.1m 0.95m 20n", "wrdata a5_step.dat v(ADC_DRIVE)"])
    d = data("a5_step.dat")
    t, v = d["time"], d["v(ADC_DRIVE)"]
    base = at(t, v, 0.99e-3)
    final = at(t, v, 1.09e-3)
    peak = max(v)
    over = (peak - final) / (final - base) * 100
    ok &= check("no ringing driving the network (step at full gain)", over < 10, f"overshoot {over:.1f} %")
    return ok


VREF = V12 * 100 / 240  # the 140k / 100k divider


def clip_deck(source, values=None):
    """The clip detector (5.4), its input ADC_DRIVE driven by the test bench."""
    return kinet.spice(PARTS, CLIP, values=values) + SUPPLY + list(source)


def led_current(d):
    return [(c - a) / 4.7e3 for c, a in zip(d["v(CLIP_COL)"], d["v(CLIP_LED_A)"])]


def clip_burst(name, cycles, amp, values=None):
    """1 kHz at 2 V peak, then `cycles` cycles at amp, then 2 V again: the LED current over time."""
    start = 10e-3
    src = [f"B_d ADC_DRIVE 0 V = {VREF:.4f} + (2 + {amp - 2:.4f} * (u(time - {start}) - "
           f"u(time - {start + cycles * 1e-3:.6f}))) * sin(6.283185e3 * time)"]
    ngspice(name, clip_deck(src, values), ["tran 5u 400m 0 5u", f"wrdata {name}.dat v(CLIP_COL) v(CLIP_LED_A) v(CLIP_HOLD)"])
    d = data(f"{name}.dat")
    t, i = d["time"], led_current(d)
    lit = [tt for tt, ii in zip(t, i) if ii > 0.5e-3]
    peak = max(i)
    hold = (lit[-1] - start - cycles * 1e-3) if lit else 0
    return t, i, peak, hold


def a4():
    say("A4  Clip LED: thresholds and how long a peak keeps it lit")
    ok = True
    ngspice("a4_dc", clip_deck(["V_d ADC_DRIVE 0 5"]), ["dc V_d 0 12 2m", "wrdata a4_dc.dat v(CLIP_N) v(CLIP_COL) v(CLIP_LED_A)"])
    d = data("a4_dc.dat")
    v, n = d["v-sweep"], d["v(CLIP_N)"]
    lows = [x for x, y in zip(v, n) if y < V12 / 2]
    lo_t = max(x for x in lows if x < VREF)
    hi_t = min(x for x in lows if x > VREF)
    say(f"  VREF {VREF:.2f} V; LED on below {lo_t:.3f} V and above {hi_t:.3f} V")
    ok &= check("thresholds VREF +/- 2.6 V +/- 0.1 V", abs(hi_t - VREF - 2.6) <= 0.1 and abs(VREF - lo_t - 2.6) <= 0.1,
                f"+{hi_t - VREF:.3f} / -{VREF - lo_t:.3f} V")
    say(f"  ADC full scale {ADC_FS_PEAK:.2f} V peak: the LED comes on "
        f"{20 * math.log10(ADC_FS_PEAK / (hi_t - VREF)):.1f} dB below it")
    # One cycle 0.5 dB over the threshold, and ten.
    amp = (hi_t - VREF) * 10 ** (0.5 / 20)
    series = []
    for cycles in (1, 10):
        t, i, peak, hold = clip_burst(f"a4_burst{cycles}", cycles, amp)
        say(f"  {cycles} cycle(s) at 1 kHz, 0.5 dB over: LED peak {peak * 1e3:.2f} mA, over 0.5 mA for {hold * 1e3:.0f} ms after")
        series.append((f"{cycles} cycle(s)", [x * 1e3 for x in t], [x * 1e3 for x in i]))
        if cycles == 1:
            ok &= check("a single 1 kHz peak 0.5 dB over lights it for 50-200 ms", 50e-3 <= hold <= 200e-3,
                        f"{hold * 1e3:.0f} ms, {peak * 1e3:.2f} mA")
            idle = max(x for tt, x in zip(t, i) if tt < 9e-3)
            ok &= check("off while the signal stays under the threshold", idle < 20e-6, f"{idle * 1e6:.2f} uA")
    svgplot.plot(os.path.join(RESULTS, "a4-clip-led.svg"), "A4: clip LED current after a 1 kHz peak 0.5 dB over",
                 series, "ms", "mA")
    return ok


# --- Outputs: plan 5.5 and 5.6, from the DAC's output pins --------------------------------

OUTPUTS = [r for r in kinet.on_sheet(PARTS, "Outputs") if r != "U12" and not
           set(PARTS[r].pins.values()) & {"P5V", "HP_CPP", "HP_CPN", "HP_CPVSS", "HP_SD"}]
DAC_NET = [r for r in kinet.touching(PARTS, kinet.on_sheet(PARTS, "Audio converters and clocks"),
                                     ["DAC_OUTL_RAW", "DAC_OUTR_RAW"]) if not r.startswith("U")]
# The 5 V reference: the divider and its capacitors (guitar sheet).
VREF_NET = [r for r in GUITAR if set(PARTS[r].pins.values()) <= {"VREF_5V", "P12VA", "0"} and r[0] in "RC"]
# The TPA6130A2 has no SPICE model. Its inputs are each half of its differential input
# impedance, to an internal point at AC ground; 37 kohm is the least, at its highest gains
# (datasheet 9.2.2.1).
TPA_RIN = 37e3
TPA_INPUTS = [f"R_tpa{n} HP_{s} 0 {TPA_RIN / 2:g}" for n, s in enumerate(("LINM", "LINP", "RINM", "RINP"))]


def outputs_deck(main, phones, source, extra=(), values=None):
    """main / phones: the knobs' fraction of the track from ground to the wiper (1 = full)."""
    pots = {"RV2.1": main, "RV2.2": main, "RV3.1": phones, "RV3.2": phones}
    return kinet.spice(PARTS, OUTPUTS + DAC_NET + VREF_NET, pots=pots, values=values) + \
        TPA_INPUTS + list(source) + list(extra)


def a6():
    say("A6  Main outputs: response into 10 kohm and 600 ohm, power-on and power-off thumps")
    ok = True
    series = []
    for load in (10e3, 600):
        name = f"a6_ac_{load:g}"
        ngspice(name, outputs_deck(0.9999, 0.5, ["V_dac DAC_OUTL_RAW 0 dc 0 ac 1", "V_dacr DAC_OUTR_RAW 0 0",
                                                 f"R_load MAIN_L_TIP MAIN_L_RING {load:g}"] + SUPPLY),
                ["ac dec 40 2 100k", "let g = vdb(MAIN_L_TIP, MAIN_L_RING)", f"wrdata {name}.dat g"])
        d = data(f"{name}.dat")
        f, g = d["frequency"], d["g"]
        g1k = at(f, g, 1e3)
        lo, hi = at(f, g, 20) - g1k, at(f, g, 20e3) - g1k
        corner = next(x for x, y in zip(f, g) if y > g1k - 3)
        ok &= check(f"into {load:g} ohm: flat 20 Hz-20 kHz within 0.5 dB", abs(lo) <= 0.5 and abs(hi) <= 0.5,
                    f"{g1k:+.2f} dB at 1 kHz; {lo:+.2f} dB at 20 Hz, {hi:+.2f} dB at 20 kHz; -3 dB at {corner:.1f} Hz")
        series.append((f"{load:g} ohm load", f, g))
    svgplot.plot(os.path.join(RESULTS, "a6-main-response.svg"), "A6: DAC pin to main output (tip to ring), full volume",
                 series, "Hz", "dB", xlog=True, ylim=(-8, 1))

    # Thumps: the 12 V rail rising over 5 ms at power-on; falling over 20 ms when the power is cut.
    # VREF follows through its 140k / 100k divider and 47 uF. TI's model can't start from a dead
    # rail (it stops below about 0.4 V), so power-on starts at 4.5 V, the OPA1642's least supply,
    # with VREF still at 0 V: it takes seconds to rise, so nothing is lost.
    for case, rail, length in (("on", "pwl(0 4.5 0.1 4.5 0.105 12.05)", 12), ("off", "pwl(0 12.05 0.1 12.05 0.12 0)", 3)):
        name = f"a6_{case}"
        src = [f"V12 P12VA 0 {rail}", "V_dac DAC_OUTL_RAW 0 0", "V_dacr DAC_OUTR_RAW 0 0",
               "R_load MAIN_L_TIP MAIN_L_RING 10k"] + ([".ic v(VREF_5V)=0"] if case == "on" else [])
        ngspice(name, outputs_deck(0.5, 0.5, src),
                [f"tran 100u {length} 0 1m", f"wrdata {name}.dat v(MAIN_L_TIP,MAIN_L_RING) v(VREF_5V)"])
        d = data(f"{name}.dat")
        t, v = d["time"], d["v(MAIN_L_TIP,MAIN_L_RING)"]
        pk = max(v, key=abs)
        tp = t[v.index(pk)]
        say(f"  power-{case}: largest output {pk:+.2f} V at {tp:.2f} s (into 10 kohm)")
        svgplot.plot(os.path.join(RESULTS, f"a6-thump-{case}.svg"), f"A6: main output at power-{case} (10 kohm load)",
                     [("output, V", t, v)], "s", "V")
    return ok


def a7():
    say("A7  Headphones: the knob's taper with the amplifier's input as its load, and the bass corner")
    ok = True
    xs = [i / 20 for i in range(1, 21)]
    loaded = []
    for i, x in enumerate(xs):
        p = pot_taper("A", x)
        name = f"a7_{i}"
        ngspice(name, outputs_deck(0.5, p, ["V_dac DAC_OUTL_RAW 0 dc 0 ac 1", "V_dacr DAC_OUTR_RAW 0 0"] + SUPPLY),
                ["ac lin 1 1k 1k", "let g = vdb(HP_LINM, HP_LINP)", f"wrdata {name}.dat g"])
        loaded.append(data(f"{name}.dat")["g"][0])
    # The same knob unloaded: 10k above the pot and nothing on the wiper.
    ideal = [20 * math.log10(10e3 * pot_taper("A", x) / 20e3) for x in xs]
    for x, gl, gi in zip(xs, loaded, ideal):
        if x in (0.25, 0.5, 0.75, 1.0):
            say(f"  rotation {x * 100:.0f} %: {gl:+.1f} dB at the amp's input (unloaded pot {gi:+.1f} dB)")
    ok &= check("taper keeps its shape under the amp's load (within 3 dB of unloaded)",
                max(abs(a - b) for a, b in zip(loaded, ideal)) <= 3,
                f"largest difference {max(abs(a - b) for a, b in zip(loaded, ideal)):.1f} dB")
    svgplot.plot(os.path.join(RESULTS, "a7-phones-taper.svg"), "A7: headphone knob, DAC to amplifier input",
                 [("with the amp's 37 kohm input", [x * 300 for x in xs], loaded),
                  ("unloaded pot", [x * 300 for x in xs], ideal)], "rotation, degrees", "dB")
    ngspice("a7_ac", outputs_deck(0.5, 0.9999, ["V_dac DAC_OUTL_RAW 0 dc 0 ac 1", "V_dacr DAC_OUTR_RAW 0 0"] + SUPPLY),
            ["ac dec 40 2 100k", "let g = vdb(HP_LINM, HP_LINP)", "wrdata a7_ac.dat g"])
    d = data("a7_ac.dat")
    f, g = d["frequency"], d["g"]
    g1k = at(f, g, 1e3)
    corner = next(x for x, y in zip(f, g) if y > g1k - 3)
    ok &= check("bass corner below 20 Hz at the amp's lowest input impedance", corner < 20,
                f"-3 dB at {corner:.1f} Hz, {at(f, g, 20) - g1k:+.2f} dB at 20 Hz")
    # Peak at the amp's inputs with the DAC at full scale, against their -2.5 V limit (datasheet).
    peak = math.sqrt(2) * 2.1 * 10 ** (max(loaded) / 20)
    ok &= check("DAC full scale stays inside the amp's input limit", peak < 2.5, f"{peak:.2f} V peak")
    return ok


# --- Power: plan 4.4, the 15 V boost and the 12 V regulator --------------------------------

BOOST_NETS = ["BOOST_SW", "BOOST_FB", "P15V", "15V_FILT", "LDO12_NR", "LDO12_FB", "12VA_REG"]
POWER = [r for r in kinet.touching(PARTS, kinet.on_sheet(PARTS, "Power"), BOOST_NETS)]
POWER += [r for r in kinet.on_sheet(PARTS, "Power") if r not in POWER and PARTS[r].lib == "Device:C"
          and set(PARTS[r].pins.values()) == {"P5V", "0"} and PARTS[r].value.startswith("4.7u")]  # boost input
# Every decoupling capacitor on the 12 V rail, from the other sheets.
RAIL12 = [r for r in PARTS if set(PARTS[r].pins.values()) == {"P12VA", "0"} and PARTS[r].lib == "Device:C"]


def audio_ripple_at_adc(t, idx, vs, transfer, dt=200e-9):
    """RMS at the ADC pin of a rail's 20 Hz-20 kHz content (transfer: the rail-to-ADC response)."""
    t0, n = t[idx[0]], int((t[idx[-1]] - t[idx[0]]) / dt)
    x, j = [], idx[0]
    for k in range(n):  # resample evenly
        tt = t0 + k * dt
        while t[j + 1] < tt:
            j += 1
        x.append(vs[j] + (vs[j + 1] - vs[j]) * (tt - t[j]) / (t[j + 1] - t[j]))
    ts = [k * dt for k in range(n)]
    tm, vm = sum(ts) / n, sum(x) / n
    slope = sum((a - tm) * (b - vm) for a, b in zip(ts, x)) / sum((a - tm) ** 2 for a in ts)
    xw = [(b - vm - slope * (a - tm)) * (0.5 - 0.5 * math.cos(2 * math.pi * i / (n - 1)))
          for i, (a, b) in enumerate(zip(ts, x))]
    total = 0.0
    for k in range(1, int(20e3 * n * dt) + 1):
        f = k / (n * dt)
        w = 2 * math.pi * f * dt
        amp = 2 * abs(sum(v * cmath.exp(-1j * w * i) for i, v in enumerate(xw))) / (n * 0.5)
        total += (amp / math.sqrt(2) * 10 ** (at(transfer["frequency"], transfer["g"], f) / 20)) ** 2
    return math.sqrt(total)


def a8():
    say("A8  The 15 V boost and the 12 V regulator: switching frequency and the ripple left on 12 V")
    ok = True
    # How much of a ripple on the 12 V rail reaches the ADC pin through the guitar stage at full
    # gain (op-amp PSRR, the VREF divider, the clamp diode), from TI's op-amp model.
    deck = [l for l in guitar_deck(1, ["V_s GTR_TIP 0 0"]) if not l.startswith("V12 ")]
    ngspice("a8_psrr", deck + [f"V12 P12VA 0 dc {V12} ac 1"],
            ["ac dec 20 10 2meg", "let g = vdb(ADC_VINL1)", "wrdata a8_psrr.dat g"])
    psrr = data("a8_psrr.dat")
    adc_floor = 2.1 / 10 ** (ADC_SNR_DB / 20)
    for load_ma in (10, 30):
        name = f"a8_{load_ma}"
        r_load = V12 / (load_ma * 1e-3)
        # The 12 V regulator's soft start (10 nF on NR/SS) takes tens of milliseconds, too long to
        # simulate at switching speed: start the rails at their working voltages instead.
        deck = kinet.spice(PARTS, POWER + RAIL12) + [
            "V5 P5V 0 5", "V_en PWR_EN 0 3.27", f"R_load P12VA 0 {r_load:.1f}",
            f".ic v(P15V)=15 v(15V_FILT)=15 v(12VA_REG)={V12} v(P12VA)={V12} v(LDO12_NR)=1.194 "
            "v(LDO12_FB)=1.194 v(BOOST_FB)=1.233"]
        ngspice(name, deck, ["tran 20n 6m 0 50n", f"wrdata {name}.dat v(BOOST_SW) v(P15V) v(15V_FILT) v(P12VA)"],
                models=POWER_MODELS)
        d = data(f"{name}.dat")
        t = d["time"]
        tail = [i for i, x in enumerate(t) if x > 4e-3]
        # Switching pulses: the switch held on (its node within 0.5 V of ground) for 300 ns or more.
        # Between pulses the node rings with the inductor, through ground, so crossings can't be
        # counted. (TI's model has no clamp diode at SW, so the ring reaches -11 V; the chip's own
        # diode stops it near -0.7 V.)
        ons, start = [], None
        for i in tail:
            if abs(d["v(BOOST_SW)"][i]) < 0.5:
                start = t[i] if start is None else start
            else:
                if start is not None and t[i] - start >= 300e-9:
                    ons.append(start)
                start = None
        f_sw = len(ons) / (t[tail[-1]] - t[tail[0]])
        longest = max(b - a for a, b in zip(ons, ons[1:]))

        def pp(key):
            """Peak-to-peak after taking out the mean and the slow drift (soft start still settling)."""
            ts = [t[i] for i in tail]
            vs = [d[key][i] for i in tail]
            tm, vm = sum(ts) / len(ts), sum(vs) / len(vs)
            slope = sum((a - tm) * (b - vm) for a, b in zip(ts, vs)) / sum((a - tm) ** 2 for a in ts)
            res = [b - vm - slope * (a - tm) for a, b in zip(ts, vs)]
            return max(res) - min(res), vm
        r15, v15 = pp("v(P15V)")
        rf, vf = pp("v(15V_FILT)")
        r12, v12 = pp("v(P12VA)")
        say(f"  {load_ma} mA on 12 V: boost {v15:.2f} V, {f_sw / 1e3:.0f} kHz on average (longest gap "
            f"{longest * 1e6:.0f} us), ripple {r15 * 1e3:.0f} mV p-p; after the filter {rf * 1e3:.1f} mV; "
            f"12 V rail {v12:.2f} V, ripple {r12 * 1e6:.1f} uV p-p")
        # At light load the boost switches in bursts, which puts part of its ripple in the audio
        # band. That part, through the guitar stage to the ADC pin: a spectrum of the 12 V rail
        # (2 ms, Hann window, drift taken out) weighted by the rail-to-ADC transfer.
        audio = audio_ripple_at_adc(t, tail, d["v(P12VA)"], psrr)
        ok &= check(f"{load_ma} mA: audio-band ripple at the ADC pin below the ADC's floor", audio < adc_floor,
                    f"{audio * 1e9:.0f} nVrms against {adc_floor * 1e6:.1f} uVrms")
        ok &= check(f"{load_ma} mA: 12 V within 1 %", abs(v12 - V12) < 0.12, f"{v12:.3f} V")
        # The rest, all taken at the average switching frequency, through the stage to the ADC pin.
        g = 10 ** (at(psrr["frequency"], psrr["g"], f_sw) / 20)
        at_adc = r12 / (2 * math.sqrt(2)) * g
        ok &= check(f"{load_ma} mA: switching ripple at the ADC pin below the ADC's floor", at_adc < adc_floor,
                    f"{at_adc * 1e9:.1f} nVrms (rail to ADC pin {20 * math.log10(g):.0f} dB at "
                    f"{f_sw / 1e3:.0f} kHz) against {adc_floor * 1e6:.1f} uVrms")
        if load_ma == 10:
            ts = [t[i] * 1e3 for i in tail]
            svgplot.plot(os.path.join(RESULTS, "a8-rails.svg"), "A8: 15 V and 12 V rails, 10 mA load (last 2 ms)",
                         [("15 V boost, mV from mean", ts, [(d["v(P15V)"][i] - v15) * 1e3 for i in tail]),
                          ("12 V rail, mV from mean", ts, [(d["v(P12VA)"][i] - v12) * 1e3 for i in tail])],
                         "ms", "mV")
    return ok


SIMS = {"A1": a1, "A2": a2, "A3": a3, "A4": a4, "A5": a5, "A6": a6, "A7": a7, "A8": a8}


def main():
    os.makedirs(RESULTS, exist_ok=True)
    names = [a.upper() for a in sys.argv[1:]] or list(SIMS)
    results = {n: SIMS[n]() for n in names}
    say()
    say("Summary: " + ", ".join(f"{n} {'pass' if ok else 'FAIL'}" for n, ok in results.items()))
    with open(os.path.join(OUT, "report.txt"), "w") as f:
        f.write("\n".join(REPORT) + "\n")


if __name__ == "__main__":
    main()
