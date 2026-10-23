"""SPICE lines for parts of the KiCad schematic, read from its netlist.

The simulations take their parts, values and connections from ../kicad/out/pedalboard.net
(made by ../gen/check.sh), so they test the circuit as drawn. Each simulation picks parts by
sheet and reference; connectors and jacks are left out, and the test bench drives their nets.
"""

import re

NETLIST = "../kicad/out/pedalboard.net"

SUFFIX = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "k": 1e3, "K": 1e3,
          "M": 1e6, "G": 1e9, "R": 1, "": 1}


def value(text):
    """'4.7k' -> 4700, '100nF C0G' -> 1e-7, '2R2' -> 2.2, '0R' -> 0, '10uF 25V' -> 1e-5."""
    m = re.match(r"(\d+(?:\.\d+)?)([fpnuµmkKMGR]?)(\d*)", text.split()[0])
    if not m:
        raise ValueError(f"no value in {text!r}")
    num = m.group(1) + ("." + m.group(3) if m.group(3) else "")
    return float(num) * SUFFIX[m.group(2)]


def parse(text):
    """S-expression to nested lists of strings."""
    tokens = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', text)
    stack = [[]]
    for tok in tokens:
        if tok == "(":
            stack.append([])
        elif tok == ")":
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(tok[1:-1] if tok.startswith('"') else tok)
    return stack[0][0]


def kids(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]


def kid(node, key):
    found = kids(node, key)
    return found[0] if found else None


class Part:
    def __init__(self, ref, value, lib, sheet, fields):
        self.ref, self.value, self.lib, self.sheet, self.fields = ref, value, lib, sheet, fields
        self.pins = {}  # pin number -> SPICE node

    def __repr__(self):
        return f"{self.ref} {self.lib} {self.value} {self.pins}"


def node_name(net):
    if net == "GND":
        return "0"
    if net.startswith("unconnected-"):
        return "nc_" + re.sub(r"\W", "_", net[len("unconnected-"):]).strip("_")
    name = net.rsplit("/", 1)[-1]  # local labels: the sheet path goes (names are unique on this board)
    return re.sub(r"[^\w+.-]", "_", name).replace("+", "P").replace(".", "_")


def load(path=NETLIST):
    root = parse(open(path, encoding="utf-8").read())
    parts = {}
    for comp in kids(kid(root, "components"), "comp"):
        ref = kid(comp, "ref")[1]
        lib = kid(comp, "libsource")
        props = {kid(p, "name")[1]: kid(p, "value")[1] for p in kids(comp, "property")}
        fields = {f[1][1]: f[2] if len(f) > 2 else "" for f in kids(kid(comp, "fields") or [], "field")}
        parts[ref] = Part(ref, kid(comp, "value")[1], f"{kid(lib, 'lib')[1]}:{kid(lib, 'part')[1]}",
                          props.get("Sheetname", ""), fields)
    for net in kids(kid(root, "nets"), "net"):
        name = node_name(kid(net, "name")[1])
        for n in kids(net, "node"):
            parts[kid(n, "ref")[1]].pins[kid(n, "pin")[1]] = name
    return parts


# Pots: the test bench gives each one a fraction p = R(pin 1 to wiper) / R; a dual pot's second
# gang uses pins 4, 5, 6 the same way.
def pot(ref, ends, total, p):
    a, w, b = ends
    p = min(max(p, 1e-4), 1 - 1e-4)
    return [f"{ref}_a {a} {w} {total * p:.6g}", f"{ref}_b {w} {b} {total * (1 - p):.6g}"]


# Dual op-amps and comparators on the standard pinout: (+, -, out) per unit, supply 8 and 4.
DUAL_UNITS = (("A", "3", "2", "1"), ("B", "5", "6", "7"))

# ngspice and TI's models: what each KiCad symbol becomes.
DEVICES = {
    "Amplifier_Operational:OPA2134": "OPA164x",  # placed as the OPA1642, which has the same pinout
    "Comparator:LM393": "LM2903B",  # TI's LM393 PSpice model (SLCJ016) is its LM2903B/LM393B model
}


def spice(parts, refs, pots=None, values=None, skip_units=()):
    """SPICE lines for the parts named in refs. pots: {ref or ref.gang: fraction};
    values: {ref: value} to try another value than the schematic's."""
    pots = pots or {}
    lines = []
    for ref in refs:
        p = parts[ref]
        if values and ref in values:
            p = Part(ref, values[ref], p.lib, p.sheet, p.fields)
            p.pins = parts[ref].pins
        pin = p.pins.get
        lib = p.lib
        if lib in ("Device:R",):
            v = value(p.value)
            lines.append(f"{ref} {pin('1')} {pin('2')} {max(v, 1e-3):.6g}")  # 0R links: 1 mohm
        elif lib in ("Device:C", "Device:C_Polarized"):
            lines.append(f"{ref} {pin('1')} {pin('2')} {value(p.value):.6g}")
        elif lib == "Device:L":
            # with a winding resistance typical of a 10 uH 1210 part (the part is chosen at layout)
            lines += [f"{ref} {pin('1')} {ref}_dcr {value(p.value):.6g}", f"R{ref}_dcr {ref}_dcr {pin('2')} 0.3"]
        elif lib == "Device:FerriteBead":
            lines.append(f"X{ref} {pin('1')} {pin('2')} BEAD PARAMS: Z100={value(p.value):.6g}")
        elif lib == "Device:Polyfuse":
            lines.append(f"R{ref} {pin('1')} {pin('2')} 0.05")
        elif lib == "Device:R_Potentiometer":
            lines += pot(ref, (pin("1"), pin("2"), pin("3")), value(p.value), pots[ref])
        elif lib == "Device:R_Potentiometer_Dual_Separate":
            lines += pot(ref + "_1", (pin("1"), pin("2"), pin("3")), value(p.value), pots[ref + ".1"])
            lines += pot(ref + "_2", (pin("4"), pin("5"), pin("6")), value(p.value), pots[ref + ".2"])
        elif lib in DEVICES:
            for unit, plus, minus, out in DUAL_UNITS:
                if unit in skip_units or pin(out) is None:
                    continue
                lines.append(f"X{ref}{unit} {pin(plus)} {pin(minus)} {pin('8')} {pin('4')} {pin(out)} {DEVICES[lib]}")
                if lib == "Amplifier_Operational:OPA2134":
                    # TI's OPA164x model finds no DC operating point with its output unloaded:
                    # 10 kohm through 1 kH loads it at DC only (125 kohm at 20 Hz, behind an
                    # output impedance of milliohms), so it changes nothing that is measured.
                    lines += [f"L{ref}{unit}_dc {pin(out)} {ref}{unit}_dc 1k", f"R{ref}{unit}_dc {ref}{unit}_dc 0 10k"]
        elif lib == "Diode:BAV99":  # pin 1 anode 1, pin 2 cathode 2, pin 3 the junction (Nexperia)
            lines += [f"{ref}a {pin('1')} {pin('3')} BAV99", f"{ref}b {pin('3')} {pin('2')} BAV99"]
        elif lib == "Diode:MBR0530":  # pin 1 cathode, pin 2 anode
            lines.append(f"{ref} {pin('2')} {pin('1')} MBR0530")
        elif lib == "Device:LED":  # pin 1 cathode, pin 2 anode
            lines.append(f"{ref} {pin('2')} {pin('1')} LED_RED")
        elif lib == "Transistor_BJT:BC857":  # pin 1 base, 2 emitter, 3 collector
            lines.append(f"{ref} {pin('3')} {pin('1')} {pin('2')} BC857")
        elif lib == "Regulator_Switching:TPS61040DBV":  # 1 SW, 2 GND, 3 FB, 4 EN, 5 VIN
            lines.append(f"X{ref} {pin('4')} {pin('3')} {pin('1')} {pin('5')} {pin('2')} TPS61040_TRANS")
        elif lib == "pedalboard:TPS7A4901DGN":  # TI model pins: PwPd EN FB IN NC NR DNC OUT GND
            lines.append(f"X{ref} {pin('9')} {pin('5')} {pin('2')} {pin('8')} {pin('3')} {pin('6')} {pin('7')} "
                         f"{pin('1')} {pin('4')} TPS7A4901_TRANS")
        else:
            raise ValueError(f"{ref}: no SPICE model for {lib}")
    return lines


def on_sheet(parts, sheet, prefixes=("R", "C", "L", "U", "D", "Q", "RV", "FB")):
    """References on one sheet that a simulation can use (no connectors, jacks or test points)."""
    def key(r):
        m = re.match(r"([A-Z]+)(\d+)", r)
        return m.group(1), int(m.group(2))
    return sorted((r for r, p in parts.items() if p.sheet == sheet and key(r)[0] in prefixes), key=key)


def touching(parts, refs, nets):
    """The refs that have a pin on any of the nets."""
    return [r for r in refs if set(parts[r].pins.values()) & set(nets)]
