<!-- run-facts -->

- **status: `success`**
- extraction mode: `agent`; paragraphs kept 141/141; characters 166815
- stage seconds: prepare 0.211, build 0.05, finalize 0.009
- validation checks failed: none
<!-- end run-facts -->
# Knowledge graph report — case `demo-perovskite-2papers`

- nodes: **35** (verified 35)
- edges: **34** (verified 34)
- rejected evidence items: 0

## Sources

- `P1` (primary): Engineering Larger Grains in MAPbI3 Solar Cells via Covalent Organic Framework (COF)-Assisted Crystallization: High-Performance Devices with Superior Stability Under Prolonged Illumination — DOI 10.3390/polym18202535
- `P2` (secondary): Resolving carrier kinetics in perovskite through deep-learning-assisted photoluminescence analysis — DOI 10.1038/s41467-026-77052-8

## Node types

```
{"material": 10, "metric": 9, "method": 8, "conclusion": 4, "other": 2, "task": 1, "model": 1}
```

## Edge types

```
{"uses": 9, "reports": 9, "measures": 5, "improves": 4, "supports": 3, "compares": 1, "evaluated_on": 1, "other": 1, "outperforms": 1}
```

## Entities

| id | label | type | sources | evidence |
|---|---|---|---|---|
| N0001 | perovskite solar cells | task | P1, P2 | 2 |
| N0002 | power conversion efficiency | metric | P1, P2 | 2 |
| N0003 | stability | metric | P1, P2 | 2 |
| N0004 | MAPbI3 | material | P1 | 2 |
| N0005 | time-resolved photoluminescence | method | P2 | 2 |
| N0006 | rate-equation models | method | P2 | 1 |
| N0007 | Bayesian inference | method | P2 | 1 |
| N0008 | carrier kinetics | other | P2 | 1 |
| N0009 | photoluminescence quantum yield | metric | P2 | 1 |
| N0010 | PLQY provides an orthogonal constraint against parameter non-uniqueness | conclusion | P2 | 1 |
| N0011 | TrPL alone is insufficient to determine carrier kinetics | conclusion | P2 | 1 |
| N0012 | coefficient of determination | metric | P2 | 1 |
| N0013 | covalent organic frameworks | material | P1 | 1 |
| N0014 | deep learning framework | method | P2 | 1 |
| N0015 | perovskite absorber | material | P1, P2 | 2 |
| N0016 | bimolecular recombination coefficient | metric | P2 | 1 |
| N0017 | non-radiative recombination | other | P1, P2 | 2 |
| N0018 | spin-coating | method | P1 | 1 |
| N0019 | mesoscopic device architecture | model | P1 | 1 |
| N0020 | Spiro-OMeTAD | material | P1, P2 | 2 |
| N0021 | Cs0.05FA0.90MA0.05PbI2.85Br0.15 | material | P2 | 1 |
| N0022 | FA0.9MA0.1PbI2.85Br0.15 | material | P2 | 1 |
| N0023 | trap density | metric | P2 | 1 |
| N0024 | passivation | method | P1, P2 | 2 |
| N0025 | photoluminescence spectroscopy | method | P1 | 1 |
| N0026 | Boc-PDA-COF | material | P1 | 1 |
| N0027 | Tp-COF | material | P1 | 1 |
| N0028 | DMTH-COF | material | P1 | 2 |
| N0029 | PCE retention after 500 h | metric | P1 | 1 |
| N0030 | efficiencies from different studies are not directly comparable | conclusion | P1 | 1 |
| N0031 | triazine-based COF additive | material | P1 | 1 |
| N0032 | fill factor | metric | P1 | 1 |
| N0033 | open-circuit voltage | metric | P1 | 1 |
| N0034 | bulk additive engineering | method | P1 | 1 |
| N0035 | COFs act as crystallization regulators and defect passivators | conclusion | P1 | 1 |

## Relations

| id | source → target | type | condition | evidence |
|---|---|---|---|---|
| E0001 | N0028 → N0034 | uses | MAPbI3 precursor solution, single solution-processing step | 1 |
| E0002 | N0035 → N0004 | supports | three COFs as bulk additives in MAPbI3 films | 1 |
| E0003 | N0013 → N0024 | supports | COF functional groups passivate defects | 1 |
| E0004 | N0028 → N0002 | reports | MAPbI3, mesoscopic, 0.50 cm2, champion 20.78% vs pristine 14.7% | 1 |
| E0005 | N0028 → N0033 | reports | Voc 1.183 V; pristine 1.142 V | 1 |
| E0006 | N0028 → N0032 | reports | FF 76.46%, below 79.4% and 81.2% of prior additive studies | 1 |
| E0007 | N0028 → N0029 | improves | 500 h aging; normalized retention ~0.50 vs ~0.20 pristine | 1 |
| E0008 | N0028 → N0017 | improves | film PL intensity, bulk | 1 |
| E0009 | N0028 → N0031 | compares | PCE 20.78% vs 20.04% in MAPbI3; margin small | 1 |
| E0010 | N0026 → N0002 | reports | MAPbI3, champion 18.88% | 1 |
| E0011 | N0027 → N0002 | reports | MAPbI3, champion 15.88% | 1 |
| E0012 | N0004 → N0018 | uses | two-step spin-coating on m-TiO2/FTO | 1 |
| E0013 | N0019 → N0020 | uses | HTL in FTO/c-TiO2/m-TiO2/perovskite/Spiro-OMeTAD/Au | 1 |
| E0014 | N0002 → N0019 | evaluated_on | 0.50 cm2 active area, AM1.5G | 1 |
| E0015 | N0025 → N0017 | measures | steady-state PL, 532 nm excitation | 1 |
| E0016 | N0029 → N0003 | measures | 500 h degradation tracking | 1 |
| E0017 | N0030 → N0002 | other | methodological caution | 1 |
| E0018 | N0014 → N0005 | uses | TrPL decay profiles as input | 1 |
| E0019 | N0014 → N0009 | uses | excitation-dependent PLQY as orthogonal constraint | 1 |
| E0020 | N0014 → N0012 | reports | six kinetic parameters, all R2 > 0.9, simulated pool | 1 |
| E0021 | N0014 → N0023 | measures | NT among six extracted parameters | 1 |
| E0022 | N0014 → N0008 | measures | extracts six kinetic parameters from TrPL+PLQY | 1 |
| E0023 | N0009 → N0010 | supports | simulation + experiment | 1 |
| E0024 | N0011 → N0005 | reports | non-unique solutions when TrPL is the only input | 1 |
| E0025 | N0010 → N0008 | improves | alleviates parameter non-uniqueness | 1 |
| E0026 | N0014 → N0007 | outperforms | computational cost of inversion | 1 |
| E0027 | N0022 → N0018 | uses | deposited films; passivation layer spin-coated | 1 |
| E0028 | N0022 → N0020 | uses | HTL in device stack | 1 |
| E0029 | N0022 → N0002 | reports | 15 devices, box/distribution plot only (no single value in text) | 1 |
| E0030 | N0021 → N0002 | reports | part of 15-device PCE comparison | 1 |
| E0031 | N0008 → N0017 | measures | γhc and γAug describe nonradiative pathways | 1 |
| E0032 | N0006 → N0008 | uses | mechanistic description of recombination | 1 |
| E0033 | N0007 → N0008 | uses | invert kinetic behaviour | 1 |
| E0034 | N0024 → N0002 | improves | passivated FAMA/CsFAMA films (P2); COF bulk passivation (P1) | 1 |

## Merge decisions

| surfaces | decision | basis |
|---|---|---|
| Spiro-OMeTAD / spiro-OMeTAD | merged | same chemical species (2,2',7,7'-tetrakis[N,N-di(4-methoxyphenyl)amino]-9,9'-spirobifluorene) used as hole-transport layer in both papers; name differs only in capitalisation; surfaces share one canonical key, so the graph holds one node |
| power conversion efficiency / PCE | merged | explicit abbreviation defined in both texts; surfaces share one canonical key, so the graph holds one node |
| time-resolved photoluminescence / TrPL | merged | explicit abbreviation in P2; surfaces share one canonical key, so the graph holds one node |
| covalent organic frameworks / COFs | merged | explicit abbreviation in P1; surfaces share one canonical key, so the graph holds one node |
| covalent organic frameworks / DMTH-COF | kept_separate | generic framework class vs one specific framework; merging would erase the distinction |
| perovskite absorber / MAPbI3 | kept_separate | MAPbI3 is one specific composition; the generic absorber term also covers P2 compositions |
| perovskite absorber / FA0.9MA0.1PbI2.85Br0.15 | kept_separate | different absorber composition and deposition; not the same physical sample as P1 |
| MAPbI3 / FA0.9MA0.1PbI2.85Br0.15 | kept_separate | different chemical compositions (MA-only vs FA/MA/Cs mixed-cation, I/Br mixed-halide) |
| non-radiative recombination / nonradiative recombination | merged | same concept, hyphenation variant; surfaces share one canonical key, so the graph holds one node |

## Conflicts

- `non_comparable_efficiency`: {"kind": "non_comparable_efficiency", "detail": "P1 reports champion PCE 20.78% for a MAPbI3 mesoscopic device (0.50 cm2); P2 reports only a 15-device PCE distribution for FAMA/CsFAMA films (0.14 cm2 active area). P1 itself states that efficiencies should not be compared across studies that differ in absorber, architecture and area. The two PCE values are therefore recorded per source and NOT ranked.", "items": ["P1/d0070", "P1/d0063", "P2/Par31"]}
- `sample_identity_conflict`: {"kind": "sample_identity_conflict", "detail": "The generic term \"perovskite\" denotes MAPbI3 in P1 and FA0.9MA0.1PbI2.85Br0.15 / Cs0.05FA0.90MA0.05PbI2.85Br0.15 in P2; treated as distinct samples, never as one material instance.", "items": ["P1/d0002", "P2/Par24"]}
- `metric_semantics_conflict`: {"kind": "metric_semantics_conflict", "detail": "P2 \"R2 > 0.9\" is the coefficient of determination of the DL model on simulated kinetic parameters, not a device performance metric; it must not be compared with P1 device PCE/Voc/FF.", "items": ["P2/Par8", "P1/d0063"]}
- `method_term_conflict`: {"kind": "method_term_conflict", "detail": "\"passivation\" in P1 denotes bulk COF additive defect passivation inside the MAPbI3 film; in P2 it denotes a surface passivation solution spin-coated on cooled films. Same word, different procedure.", "items": ["P1/d0072", "P2/Par68"]}

## Uncertainty

- `value_not_reported_in_text` : P2 device PCE is presented only as a box/distribution plot (15 devices); no single numeric PCE is stated in the body text, so no PCE node value was extracted for P2.
- `value_not_reported_in_text` : P1 aging conditions (illumination, humidity, encapsulation) for the 500 h retention are not specified in the cited paragraph; only retention fractions were extracted.
- `undetermined_relation` : No paper compares its devices against the other paper; no cross-paper outperforms relation is asserted.
- `cross_paper_generic_term` perovskite solar cells: surface appears in ['P1', 'P2']; merged as a shared concept, NOT as one physical sample/model instance
- `cross_paper_generic_term` power conversion efficiency: surface appears in ['P1', 'P2']; merged as a shared concept, NOT as one physical sample/model instance
- `cross_paper_generic_term` stability: surface appears in ['P1', 'P2']; merged as a shared concept, NOT as one physical sample/model instance
- `cross_paper_generic_term` perovskite absorber: surface appears in ['P1', 'P2']; merged as a shared concept, NOT as one physical sample/model instance
- `cross_paper_generic_term` non-radiative recombination: surface appears in ['P1', 'P2']; merged as a shared concept, NOT as one physical sample/model instance
- `cross_paper_generic_term` Spiro-OMeTAD: surface appears in ['P1', 'P2']; merged as a shared concept, NOT as one physical sample/model instance
- `cross_paper_generic_term` passivation: surface appears in ['P1', 'P2']; merged as a shared concept, NOT as one physical sample/model instance

## Queries

### Q1 — entity (answered)
```json
{"qid": "Q1", "type": "entity", "name": "Spiro-OMeTAD", "purpose": "cross-paper shared hole-transport material and its neighbourhood"}
```
nodes: ['N0020'], edges: ['E0013', 'E0028'], evidence: 2
> [P1/d0021] The resulting mesoscopic PSCs with the architecture FTO/c-TiO2/m-TiO2/perovskite/Spiro-OMeTAD/Au were fabricated.
> [P2/Par69] The hole transport layer (HTL) solution was prepared by mixing 0.090 g spiro-OMeTAD, 36 µL tBP, 23 µL of Li-TFSI solution (520 mg/mL in acetonitrile) with 1 mL CB in the argon glove box.

### Q2 — relation_search (answered)
```json
{"qid": "Q2", "type": "relation_search", "relation": "outperforms", "purpose": "which items are claimed to outperform others, and under what condition"}
```
nodes: ['N0014', 'N0007'], edges: ['E0026'], evidence: 1
> [P2/Par6] In contrast, deep learning (DL) provides a more computationally economical and efficient data-driven approach.

### Q3 — cross_paper (answered)
```json
{"qid": "Q3", "type": "cross_paper", "purpose": "shared vs source-exclusive entities and recorded conflicts"}
```
nodes: ['N0001', 'N0002', 'N0003', 'N0015', 'N0017', 'N0020', 'N0024', 'N0004', 'N0013', 'N0018', 'N0019', 'N0025', 'N0026', 'N0027', 'N0028', 'N0029', 'N0030', 'N0031', 'N0032', 'N0033', 'N0034', 'N0035', 'N0005', 'N0006', 'N0007', 'N0008', 'N0009', 'N0010', 'N0011', 'N0012', 'N0014', 'N0016', 'N0021', 'N0022', 'N0023'], edges: [], evidence: 0

### Q4 — evidence_trace (answered)
```json
{"qid": "Q4", "type": "evidence_trace", "id": "E0004", "purpose": "trace the DMTH-COF PCE claim back to the original passage"}
```
nodes: [], edges: ['E0004'], evidence: 1
> [P1/d0063] The increase in PCE is even more significant, with a rise from 14.7% for pristine to 20.78% for the DMTH-COF device, resulting in a 41.36% increase.

### Q5 — metric_compare (answered)
```json
{"qid": "Q5", "type": "metric_compare", "name": "power conversion efficiency", "purpose": "per-source PCE values without cross-paper aggregation"}
```
nodes: ['N0028', 'N0002', 'N0026', 'N0027', 'N0019', 'N0022', 'N0021', 'N0024'], edges: ['E0004', 'E0010', 'E0011', 'E0014', 'E0029', 'E0030', 'E0034'], evidence: 7
> [P1/d0063] The increase in PCE is even more significant, with a rise from 14.7% for pristine to 20.78% for the DMTH-COF device, resulting in a 41.36% increase.
> [P1/d0056] The Tp-modified device reaches 15.88% PCE, Boc-PDA-COF-modified devices reach 18.88%, and the DMTH-based device achieves the highest performance with Voc = 1.183 V, Jsc = 22.98 mA cm−2, FF = 76.46%, and PCE = 20.78%.
> [P1/d0056] The Tp-modified device reaches 15.88% PCE, Boc-PDA-COF-modified devices reach 18.88%, and the DMTH-based device achieves the highest performance with Voc = 1.183 V, Jsc = 22.98 mA cm−2, FF = 76.46%, and PCE = 20.78%.
> [P1/d0021] The resulting mesoscopic PSCs with the architecture FTO/c-TiO2/m-TiO2/perovskite/Spiro-OMeTAD/Au were fabricated.
> [P2/Par31] d Power conversion efficiency (PCE) box and distribution plots of 15 devices.

### Q6 — path (answered)
```json
{"qid": "Q6", "type": "path", "from": "DMTH-COF", "to": "stability", "max_hops": 3, "purpose": "how the COF additive connects to stability"}
```
nodes: ['N0028', 'N0029', 'N0003'], edges: ['E0007', 'E0016'], evidence: 2
> [P1/d0069] After 500 h, the normalized PCE retention values were approximately 0.20 for pristine MAPbI3, 0.50 for DMTH-COF, 0.41 for Boc-PDA-COF, and 0.30 for Tp-COF.
> [P1/d0069] The stability trends across pristine, Tp-, Boc-PDA-, and DMTH-doped devices mirror the way each COF modifies crystallization, defect chemistry, and surface wettability.

