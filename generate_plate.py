"""Generate the 96-well Co-Ni-Cu BDC plate design, per-well dispense volumes and stock-solution preparation sheet.

Outputs (written next to this script):
  plate_design_96wells.csv           - metal ratios, metal:ligand ratios and nominal concentrations per well
  plate_dispense_volumes_96wells.csv - plate design + uL of each working solution, DMF top-up, per-well amounts
  stock_solution_preparation.csv     - mass to weigh for each concentrated stock and how to dilute it to the working solution
"""
import csv
import itertools
import math
from pathlib import Path

OUT = Path(__file__).parent
METALS = ["Co", "Ni", "Cu"]

# Plate / dispensing parameters
WORKING_CONC_mM = 90.0  # all metal and BDC working solutions dispensed by the robot
WELL_VOL_uL = 300.0  # 200 uL UV-Vis aliquot + LRMS sample + losses
METAL_VOL_uL = WELL_VOL_uL / 5  # total metal per well; the 1:4 well then needs exactly WELL_VOL_uL
LIGAND_RATIOS = [1, 2, 3, 4]
OVERAGE = 1.10  # extra working solution on top of plate use + reservoir dead volume
RESERVOIR_DEAD_mL = 1.5  # left in each Axygen 12-well reservoir trough at the 2 mm aspirate height
RESERVOIR_WELLS = {"Co": 1, "Ni": 1, "Cu": 1, "BDC": 2, "DMF": 2}  # troughs per solution (see ot2_protocol.py SOURCES)

# Reagents from final_application/Reagents and suppliers.xlsx
REAGENTS = {
    "Co": dict(name="Cobalt(II) acetate tetrahydrate", formula="Co(CH3COO)2.4H2O", mw=249.08, sigma="403024", stock_mM=450.0, stock_mL=5.0),
    "Ni": dict(name="Nickel(II) acetate tetrahydrate", formula="Ni(CH3COO)2.4H2O", mw=248.84, sigma="244066", stock_mM=450.0, stock_mL=5.0),
    "Cu": dict(name="Copper(II) acetate monohydrate", formula="Cu(CH3COO)2.H2O", mw=199.65, sigma="217557", stock_mM=450.0, stock_mL=5.0),
    "BDC": dict(name="1,4-Benzenedicarboxylic acid (terephthalic acid)", formula="C6H4(COOH)2", mw=166.13, sigma="185361", stock_mM=180.0, stock_mL=25.0),
}
PURITY = 1.0  # fraction; replace with the certificate-of-analysis value to correct the weighed mass


def compositions():
    """24 metal compositions (Co:Ni:Cu), each containing at least two metals."""
    comps = []
    for a, b in [(0, 1), (0, 2), (1, 2)]:
        for ra, rb in [(1, 1), (2, 1), (1, 2)]:
            r = [0, 0, 0]
            r[a], r[b] = ra, rb
            comps.append(("Binary", tuple(r), ""))
    comps += [("Ternary", (1, 1, 1), f"Centre point replicate {i}") for i in (1, 2, 3)]
    comps += [("Ternary", p, "") for p in [(2, 1, 1), (1, 2, 1), (1, 1, 2)]]
    comps += [("Ternary", p, "") for p in [(2, 2, 1), (2, 1, 2), (1, 2, 2)]]
    comps += [("Ternary", p, "") for p in sorted(set(itertools.permutations((3, 2, 1))), reverse=True)]
    assert len(comps) * len(LIGAND_RATIOS) == 96
    return comps


def write_csv(name, rows):
    with open(OUT / name, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    comps = compositions()
    design, dispense = [], []
    totals = {k: 0.0 for k in METALS + ["BDC", "DMF"]}

    for li, L in enumerate(LIGAND_RATIOS):
        for i, (typ, r, note) in enumerate(comps):
            row = "ABCDEFGH"[li * 2 + i // 12]
            x = [v / sum(r) for v in r]
            d = {
                "Well": f"{row}{i % 12 + 1}", "Plate_Row": row, "Plate_Column": i % 12 + 1,
                "Composition_ID": f"C{i + 1:02d}", "Composition_Type": typ,
                "Metals_Present": "-".join(m for m, v in zip(METALS, r) if v),
                **{f"{m}_Ratio": v for m, v in zip(METALS, r)},
                "Total_Metal_Ratio": 1, "Ligand_Ratio": L,
                **{f"{m}_Mole_Fraction": f"{v:.4f}" for m, v in zip(METALS, x)},
                **{f"{m}_Conc_mM": f"{WORKING_CONC_mM * v:.2f}" for m, v in zip(METALS, x)},
                "Total_Metal_Conc_mM": f"{WORKING_CONC_mM:.2f}",
                "BDC_Ligand_Conc_mM": f"{WORKING_CONC_mM * L:.2f}",
            }
            design.append({**d, "Notes": note})

            vol = {m: METAL_VOL_uL * v for m, v in zip(METALS, x)}
            vol["BDC"] = METAL_VOL_uL * L
            vol["DMF"] = WELL_VOL_uL - sum(vol.values())
            for k in totals:
                totals[k] += vol[k]
            umol = {k: WORKING_CONC_mM * vol[k] / 1000 for k in METALS + ["BDC"]}
            dispense.append({
                **d,
                "Working_Soln_Conc_mM": f"{WORKING_CONC_mM:.2f}",
                **{f"{k}_Working_Soln_Vol_uL": f"{vol[k]:.2f}" for k in METALS + ["BDC"]},
                "DMF_Topup_Vol_uL": f"{vol['DMF']:.2f}", "Total_Well_Vol_uL": f"{WELL_VOL_uL:.2f}",
                **{f"{k}_Amount_umol": f"{umol[k]:.3f}" for k in METALS + ["BDC"]},
                **{f"{k}_Reagent_Mass_Equiv_mg": f"{umol[k] * REAGENTS[k]['mw'] / 1000:.3f}" for k in METALS + ["BDC"]},
                **{f"{k}_Final_Conc_mM": f"{WORKING_CONC_mM * vol[k] / WELL_VOL_uL:.2f}" for k in METALS + ["BDC"]},
                "Notes": note,
            })

    stocks = []
    dilution_dmf_mL = 0.0
    for k, g in REAGENTS.items():
        need_mL = totals[k] / 1000
        work_mL = math.ceil((need_mL + RESERVOIR_DEAD_mL * RESERVOIR_WELLS[k]) * OVERAGE)  # whole mL
        aliquot_mL = work_mL * WORKING_CONC_mM / g["stock_mM"]
        dilution_dmf_mL += work_mL - aliquot_mL
        mass_mg = g["stock_mM"] * g["stock_mL"] * g["mw"] / 1000 / PURITY
        stocks.append({
            "Step": "1 - Concentrated stock", "Component": k, "Reagent": g["name"], "Formula": g["formula"],
            "Sigma_Product_No": g["sigma"], "MW_g_per_mol": f"{g['mw']:.2f}", "Purity_Fraction": f"{PURITY:.2f}",
            "Solvent": "DMF", "Target_Conc_mM": f"{g['stock_mM']:.2f}", "Final_Volume_mL": f"{g['stock_mL']:.2f}",
            "Mass_to_Weigh_mg": f"{mass_mg:.1f}", "Source_Solution": "Solid reagent",
            "Volume_of_Source_mL": "", "DMF_to_Add_mL": "", "Dilution_Factor": "",
            "Plate_Requirement_mL": "",
            "Instructions": f"Weigh {mass_mg:.1f} mg into a {g['stock_mL']:g} mL volumetric flask, dissolve in DMF and make up to the mark",
        })
        stocks.append({
            "Step": "2 - Working solution", "Component": k, "Reagent": g["name"], "Formula": g["formula"],
            "Sigma_Product_No": g["sigma"], "MW_g_per_mol": f"{g['mw']:.2f}", "Purity_Fraction": "",
            "Solvent": "DMF", "Target_Conc_mM": f"{WORKING_CONC_mM:.2f}", "Final_Volume_mL": f"{work_mL:.2f}",
            "Mass_to_Weigh_mg": "", "Source_Solution": f"{g['stock_mM']:g} mM {k} stock",
            "Volume_of_Source_mL": f"{aliquot_mL:.2f}", "DMF_to_Add_mL": f"{work_mL - aliquot_mL:.2f}",
            "Dilution_Factor": f"{g['stock_mM'] / WORKING_CONC_mM:g}", "Plate_Requirement_mL": f"{need_mL:.2f}",
            "Instructions": f"Pipette {aliquot_mL:.2f} mL of the {g['stock_mM']:g} mM stock and make up to {work_mL:g} mL with DMF (C1V1 = C2V2)",
        })
    dmf_mL = totals["DMF"] / 1000
    stocks.append({
        **{k: "" for k in stocks[0]},
        "Step": "3 - Solvent", "Component": "DMF", "Reagent": "N,N-Dimethylformamide", "Sigma_Product_No": "227056",
        "Final_Volume_mL": f"{math.ceil((dmf_mL + RESERVOIR_DEAD_mL * RESERVOIR_WELLS['DMF']) * OVERAGE):.2f}", "Plate_Requirement_mL": f"{dmf_mL:.2f}",
        "Instructions": f"Plate top-up reservoir; a further {dilution_dmf_mL:.2f} mL DMF is used in step 2 plus the step 1 make-up volumes",
    })

    write_csv("plate_design_96wells.csv", design)
    write_csv("plate_dispense_volumes_96wells.csv", dispense)
    write_csv("stock_solution_preparation.csv", stocks)


if __name__ == "__main__":
    main()
