"""OT-2 protocol: dispense the 96-reaction Co-Ni-Cu BDC ternary gradient into 2 mL GC vials.

Scope: liquid handling only. The 90 mM working solutions are prepared by hand (see plate_plan_96wells.xlsx), and capping, oven heating at 120 °C and characterisation are done by hand after this run.

Order of addition: DMF top-up -> Co -> Ni -> Cu -> BDC last, so every reaction starts within the BDC step rather than hours apart.
Dispensing is contact-free (from just inside the vial top), so one tip per reagent per pipette is reused unless NEW_TIP_EVERY_TRANSFER is True.

Sample IDs A1-H12 are the well IDs in plate_plan_96wells.xlsx. Each GC-vial rack holds one metal:ligand ratio (24 samples):
  rack 1 (slot 1) = 1:1 (samples A1-B12), rack 2 (slot 2) = 1:2 (C1-D12), rack 3 (slot 3) = 1:3 (E1-F12), rack 4 (slot 4) = 1:4 (G1-H12)
  within a rack: first sample row 1-6 -> rack row A, 7-12 -> row B; second sample row 1-6 -> row C, 7-12 -> row D.
"""
import math

from opentrons import protocol_api

metadata = {
    "protocolName": "Co-Ni-Cu BDC ternary gradient - 96 GC vials",
    "author": "Aritra Roy",
    "description": "Dispenses Co, Ni, Cu acetate and BDC working solutions (90 mM in DMF) plus DMF top-up into 96 x 2 mL GC vials, 300 uL per vial.",
}
requirements = {"robotType": "OT-2", "apiLevel": "2.27"}

# ---------------- Settings ----------------
# PLACEHOLDER: replace with the HTEL labware definition for the 2 mL GC-vial rack (24 positions, rows A-D x columns 1-6).
# The Opentrons 24-tube rack below is only a stand-in so the protocol simulates.
VIAL_RACK = "opentrons_24_tuberack_nest_2ml_screwcap"
VIAL_RACK_SLOTS = ["1", "2", "3", "4"]
RESERVOIR = "axygen_12_reservoir_12000ul"  # HTEL custom labware (Opentrons_Example_Files.zip)
RESERVOIR_SLOT = "5"
TIP_SLOTS = ["6", "7", "8", "9", "11"]  # slot 10 holds the permanently installed Heater-Shaker (not used here)

NEW_TIP_EVERY_TRANSFER = False  # True = fresh tip for every transfer (420 tips, 5 racks)
PAUSE_BEFORE_BDC = True  # lets you check the vials before the reactions are started
DISPENSE_DEPTH_MM = 5  # dispense this far below the vial top, above the liquid
ASPIRATE_HEIGHT_MM = 2  # above reservoir bottom (HTEL guidance: >1 mm safety margin; no meniscus tracking)
P20_MAX_UL = 20  # volumes up to this use the P20, larger ones the P300
DEAD_VOL_UL = 1500  # left unused in each trough (8 x 71 mm trough holds ~1.1 mL below the 2 mm aspirate height)

# Reservoir wells and the volume (uL) you load into each - match the "Make up to" volumes in the workbook.
SOURCES = {
    "DMF": [("A1", 6500), ("A2", 6500)],
    "Co": [("A4", 4000)],
    "Ni": [("A6", 4000)],
    "Cu": [("A8", 4000)],
    "BDC": [("A10", 10000), ("A12", 10000)],
}
ORDER = ["DMF", "Co", "Ni", "Cu", "BDC"]

# Per-sample volumes (uL) from plate_plan_96wells.xlsx, columns A and F-J. Paste new values here if the workbook changes.
VOLUMES_CSV = """
Sample,Co,Ni,Cu,BDC,DMF
A1,30,30,0,60,180
A2,40,20,0,60,180
A3,20,40,0,60,180
A4,30,0,30,60,180
A5,40,0,20,60,180
A6,20,0,40,60,180
A7,0,30,30,60,180
A8,0,40,20,60,180
A9,0,20,40,60,180
A10,20,20,20,60,180
A11,20,20,20,60,180
A12,20,20,20,60,180
B1,30,15,15,60,180
B2,15,30,15,60,180
B3,15,15,30,60,180
B4,24,24,12,60,180
B5,24,12,24,60,180
B6,12,24,24,60,180
B7,30,20,10,60,180
B8,30,10,20,60,180
B9,20,30,10,60,180
B10,20,10,30,60,180
B11,10,30,20,60,180
B12,10,20,30,60,180
C1,30,30,0,120,120
C2,40,20,0,120,120
C3,20,40,0,120,120
C4,30,0,30,120,120
C5,40,0,20,120,120
C6,20,0,40,120,120
C7,0,30,30,120,120
C8,0,40,20,120,120
C9,0,20,40,120,120
C10,20,20,20,120,120
C11,20,20,20,120,120
C12,20,20,20,120,120
D1,30,15,15,120,120
D2,15,30,15,120,120
D3,15,15,30,120,120
D4,24,24,12,120,120
D5,24,12,24,120,120
D6,12,24,24,120,120
D7,30,20,10,120,120
D8,30,10,20,120,120
D9,20,30,10,120,120
D10,20,10,30,120,120
D11,10,30,20,120,120
D12,10,20,30,120,120
E1,30,30,0,180,60
E2,40,20,0,180,60
E3,20,40,0,180,60
E4,30,0,30,180,60
E5,40,0,20,180,60
E6,20,0,40,180,60
E7,0,30,30,180,60
E8,0,40,20,180,60
E9,0,20,40,180,60
E10,20,20,20,180,60
E11,20,20,20,180,60
E12,20,20,20,180,60
F1,30,15,15,180,60
F2,15,30,15,180,60
F3,15,15,30,180,60
F4,24,24,12,180,60
F5,24,12,24,180,60
F6,12,24,24,180,60
F7,30,20,10,180,60
F8,30,10,20,180,60
F9,20,30,10,180,60
F10,20,10,30,180,60
F11,10,30,20,180,60
F12,10,20,30,180,60
G1,30,30,0,240,0
G2,40,20,0,240,0
G3,20,40,0,240,0
G4,30,0,30,240,0
G5,40,0,20,240,0
G6,20,0,40,240,0
G7,0,30,30,240,0
G8,0,40,20,240,0
G9,0,20,40,240,0
G10,20,20,20,240,0
G11,20,20,20,240,0
G12,20,20,20,240,0
H1,30,15,15,240,0
H2,15,30,15,240,0
H3,15,15,30,240,0
H4,24,24,12,240,0
H5,24,12,24,240,0
H6,12,24,24,240,0
H7,30,20,10,240,0
H8,30,10,20,240,0
H9,20,30,10,240,0
H10,20,10,30,240,0
H11,10,30,20,240,0
H12,10,20,30,240,0
"""
# ------------------------------------------


def parse_volumes():
    lines = VOLUMES_CSV.strip().splitlines()
    header = lines[0].split(",")
    rows = []
    for ln in lines[1:]:
        parts = ln.split(",")
        rows.append({"Sample": parts[0], **{h: float(v) for h, v in zip(header[1:], parts[1:])}})
    return rows


def vial_position(sample):
    """Map sample ID (A1-H12) to (rack index, rack well) - see module docstring."""
    r, c = "ABCDEFGH".index(sample[0]), int(sample[1:]) - 1
    return r // 2, f"{'ABCD'[(r % 2) * 2 + c // 6]}{c % 6 + 1}"


class Source:
    """Reservoir well(s) for one reagent; moves to the next well when the current one reaches its dead volume."""

    def __init__(self, name, wells):
        self.name, self.wells, self.i = name, wells, 0  # wells: list of [well, remaining_uL]

    def take(self, vol):
        while self.wells[self.i][1] - vol < DEAD_VOL_UL:
            self.i += 1
            if self.i == len(self.wells):
                raise RuntimeError(f"Not enough {self.name} loaded in the reservoir")
        self.wells[self.i][1] -= vol
        return self.wells[self.i][0]


def run(protocol: protocol_api.ProtocolContext):
    samples = parse_volumes()
    assert len(samples) == 96

    # Check volumes and tip counts before touching anything
    for name in ORDER:
        need = sum(s[name] for s in samples)
        usable = sum(v - DEAD_VOL_UL for _, v in SOURCES[name])
        if need > usable:
            raise ValueError(f"{name}: need {need:.0f} uL but only {usable:.0f} uL usable in the reservoir")
    if NEW_TIP_EVERY_TRANSFER:
        n20 = sum(1 for s in samples for k in ORDER if 0 < s[k] <= P20_MAX_UL)
        n300 = sum(1 for s in samples for k in ORDER if s[k] > P20_MAX_UL)
    else:
        n20 = sum(1 for k in ORDER if any(0 < s[k] <= P20_MAX_UL for s in samples))
        n300 = sum(1 for k in ORDER if any(s[k] > P20_MAX_UL for s in samples))
    racks20, racks300 = math.ceil(n20 / 96), math.ceil(n300 / 96)
    if racks20 + racks300 > len(TIP_SLOTS):
        raise ValueError(f"Needs {racks20} P20 + {racks300} P300 tip racks but only {len(TIP_SLOTS)} tip slots")

    tips20 = [protocol.load_labware("opentrons_96_tiprack_20ul", s) for s in TIP_SLOTS[:racks20]]
    tips300 = [protocol.load_labware("opentrons_96_tiprack_300ul", s) for s in TIP_SLOTS[racks20:racks20 + racks300]]
    p20 = protocol.load_instrument("p20_single_gen2", "left", tip_racks=tips20)
    p300 = protocol.load_instrument("p300_single_gen2", "right", tip_racks=tips300)

    racks = [protocol.load_labware(VIAL_RACK, s, label=f"GC vials, M:L 1:{i + 1}") for i, s in enumerate(VIAL_RACK_SLOTS)]
    reservoir = protocol.load_labware(RESERVOIR, RESERVOIR_SLOT, label="90 mM working solutions + DMF")
    sources = {k: Source(k, [[reservoir[w], v] for w, v in wells]) for k, wells in SOURCES.items()}
    colours = {"DMF": "#9EC5E8", "Co": "#E377C2", "Ni": "#2CA02C", "Cu": "#1F77B4", "BDC": "#FFBF00"}
    for k, wells in SOURCES.items():
        liquid = protocol.define_liquid(k, description="DMF" if k == "DMF" else f"{k} 90 mM in DMF", display_color=colours[k])
        for w, v in wells:
            reservoir[w].load_liquid(liquid, v)

    def add(name):
        protocol.comment(f"--- Adding {name} ---")
        for s in samples:
            vol = s[name]
            if vol <= 0:
                continue
            pip = p20 if vol <= P20_MAX_UL else p300
            if not pip.has_tip:
                pip.pick_up_tip()
            rack_i, pos = vial_position(s["Sample"])
            vial = racks[rack_i][pos]
            pip.aspirate(vol, sources[name].take(vol).bottom(ASPIRATE_HEIGHT_MM))
            pip.dispense(vol, vial.top(-DISPENSE_DEPTH_MM))
            pip.blow_out(vial.top(-DISPENSE_DEPTH_MM))
            if NEW_TIP_EVERY_TRANSFER:
                pip.drop_tip()
        for pip in (p20, p300):
            if pip.has_tip:
                pip.drop_tip()

    for name in ORDER:
        if name == "BDC" and PAUSE_BEFORE_BDC:
            protocol.pause("Metals and DMF dispensed. Check the vials, then resume to add BDC (this starts the reactions).")
        add(name)
    protocol.comment("Done. Cap the vials and transfer to the 120 °C oven.")
