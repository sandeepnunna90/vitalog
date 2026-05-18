# Clinical Guideline Citations — Biomarker Groupings

Reference document for `reference_data/biomarker_groups.json`.
Each entry maps a condition to the authoritative guideline that backs the biomarker list.

---

## Type 2 Diabetes (T2D)
**Guideline:** ADA Standards of Care in Diabetes — 2026
**Organization:** American Diabetes Association
**Published:** January 2026, *Diabetes Care* Vol 49, Supplement 1
- [Section 2: Diagnosis](https://pmc.ncbi.nlm.nih.gov/articles/PMC12690183/)
- [Section 4: Comprehensive Evaluation](https://pmc.ncbi.nlm.nih.gov/articles/PMC12690184/)
- [Section 6: Glycemic Goals](https://pmc.ncbi.nlm.nih.gov/articles/PMC12690178/)
- [Section 10: Cardiovascular Disease](https://pmc.ncbi.nlm.nih.gov/articles/PMC12690187/)
- [Section 11: Chronic Kidney Disease](https://diabetesjournals.org/care/article/49/Supplement_1/S246/163914/11-Chronic-Kidney-Disease-and-Risk-Management)

---

## Type 1 Diabetes (T1D)
**Guideline:** ADA Standards of Care in Diabetes — 2026 (same document as T2D)
**Organization:** American Diabetes Association

---

## Hypertension (HTN)
**Guideline:** 2025 AHA/ACC/Multisociety Guideline for the Prevention, Detection, Evaluation and Management of High Blood Pressure in Adults
**Organization:** ACC / AHA + 11 additional societies
**Published:** 2025, *Circulation* and *Hypertension*
- [Full Guideline — Circulation](https://www.ahajournals.org/doi/10.1161/HYP.0000000000000249)
- [2025 Updates Summary — PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12995957/)

---

## Cardiovascular Disease (CVD)
**Primary guideline:** ACC/AHA/Multisociety 2026 Guideline on the Management of Dyslipidemia
**Organization:** ACC / AHA + multispecialty
**Published:** March 2026, *Circulation* / *JACC*
- [Full Guideline — Circulation](https://www.ahajournals.org/doi/10.1161/CIR.0000000000001423)
- [NLA Summary](https://www.lipid.org/nla/2026-accahamultisociety-dyslipidemia-guideline-released)
- [ACC Press Release](https://www.acc.org/about-acc/press-releases/2026/03/13/18/01/accaha-issue-updated-guideline-for-managing-lipids-cholesterol)

**Supporting guideline:** ACC/AHA 2019 Guideline on Primary Prevention of CVD
- [Full Guideline — Circulation](https://www.ahajournals.org/doi/10.1161/cir.0000000000000678)

**Supporting statement:** ACC 2025 Scientific Statement on Inflammation and ASCVD (backs hsCRP monitoring)
- [ACC Article](https://www.acc.org/latest-in-cardiology/articles/2025/12/01/01/prioritizing-health-hscrp)

---

## Chronic Kidney Disease (CKD)
**Primary guideline:** KDIGO 2024 Clinical Practice Guideline for the Evaluation and Management of CKD
**Organization:** Kidney Disease: Improving Global Outcomes (KDIGO)
**Published:** 2024, *Kidney International* (Supplement)
- [Full PDF](https://kdigo.org/wp-content/uploads/2024/03/KDIGO-2024-CKD-Guideline.pdf)
- [Executive Summary PDF](https://kdigo.org/wp-content/uploads/2017/02/KDIGO-2024-CKD-Guideline-Executive-Summary.pdf)
- [PMC Commentary](https://pmc.ncbi.nlm.nih.gov/articles/PMC12158546/)

**Anemia guideline:** KDIGO 2026 Clinical Practice Guideline for the Management of Anemia in CKD
- [Full PDF](https://kdigo.org/wp-content/uploads/2026/01/KDIGO-2026-Anemia-in-CKD-Guideline.pdf)

---

## Hypothyroidism
**Guideline:** AACE/ATA Clinical Practice Guidelines for Hypothyroidism in Adults, 2012
**Organization:** American Association of Clinical Endocrinologists + American Thyroid Association
**Published:** 2012, *Endocrine Practice* and *Thyroid*
- [Guideline Central Summary](https://www.guidelinecentral.com/guideline/6855/)

*Note: No updated AACE/ATA guideline specific to hypothyroidism in adults exists as of May 2026. This remains the primary reference.*

---

## Prediabetes
**Guideline:** ADA Standards of Care in Diabetes — 2026, Section 2 (Diagnosis) + Section 3 (Prevention)
**Organization:** American Diabetes Association
- Same URLs as T2D above.

---

## Dyslipidemia
**Guideline:** ACC/AHA/Multisociety 2026 Guideline on the Management of Dyslipidemia
- Same URLs as CVD above.

---

## Metabolic Syndrome
**Primary statement:** AHA/NHLBI Diagnosis and Management of the Metabolic Syndrome (Scientific Statement), 2005
**Organization:** American Heart Association + National Heart, Lung, and Blood Institute
**Published:** 2005, *Circulation*
- [2005 Statement — Circulation](https://www.ahajournals.org/doi/10.1161/circulationaha.105.169404)

**Harmonization update:** AHA/IDF/NHLBI Joint Statement: Harmonizing the Metabolic Syndrome, 2009
- [2009 Statement — Circulation](https://www.ahajournals.org/doi/10.1161/circulationaha.109.192644)

---

## Biomarkers NOT supported by guidelines

| Condition | Biomarker | Status |
|---|---|---|
| Hypothyroidism | Total cholesterol, LDL, triglycerides | ❌ Explicitly NOT recommended for hypothyroidism monitoring (AACE/ATA 2012 says lipids must not be used to diagnose hypothyroidism; no monitoring recommendation exists) |
| CVD / Dyslipidemia | ALT, AST | ❌ Explicitly NOT recommended for routine monitoring in 2026 dyslipidemia guideline — symptom-driven only |
| Metabolic Syndrome | Total cholesterol, LDL | ❌ Not in the 5-component diagnostic criteria (only triglycerides and HDL are) |
| CKD | BUN | ⚠️ Clinically used but not formally mandated by KDIGO 2024 |
| CKD | Sodium | ⚠️ In expected-value tables but no explicit monitoring frequency recommendation |
| T2D | Sodium | ⚠️ Not listed in ADA 2026 T2D monitoring recommendations |
| Metabolic Syndrome | hsCRP | ⚠️ Optional / emerging factor — not required monitoring |
