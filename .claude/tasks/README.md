# Vitalog — Capstone Backlog

**Source docs:** `docs/Vitalog_PRD_v2.md`, `docs/Vitalog_architecture.md`, `docs/vitalog_roadmap.md`
**Scope:** Capstone only (architecture §11, roadmap §4). v1+ items are deferred and not tracked here.
**Timeline:** 10 days, solo.
**Total:** 33 stories · 144 points · 8 epics

Status legend: ⬜ pending · 🟡 in progress · ✅ done · ⏸ blocked

## Story index

### Epic A — Foundation (13 pts)
| ID | Title | Pts | Status | Depends on |
|---|---|---|---|---|
| [A1](A1_repo_scaffolding.md) | Repo scaffolding & dev tooling | 3 | ✅ | — |
| [A2](A2_reference_data_seed.md) | Reference data seed | 5 | ✅ | A1 |
| [A3](A3_persistence_layer.md) | Persistence layer (Supabase + repos) | 5 | ✅ | A1 |

### Epic B — AI Gateway + Guardrails (21 pts)
| ID | Title | Pts | Status | Depends on |
|---|---|---|---|---|
| [B1](B1_ai_gateway_core.md) | AI Gateway core | 5 | ✅ | A1 |
| [B2](B2_guardrails_layer1_2.md) | Layer 1 + Layer 2 guardrails | 3 | ✅ | B1 |
| [B3](B3_guardrails_layer3_deterministic.md) | Layer 3 deterministic validators | 3 | ✅ | B1 |
| [B4](B4_citation_verifier_mode_a.md) | Mode A citation verifier (structured) | 5 | ⬜ | B1, A3 |
| [B5](B5_citation_verifier_mode_b.md) | Mode B citation verifier (parse-and-match) | 5 | ⬜ | B1, A3 |

### Epic C — Eval Corpus & Harness (20 pts)
| ID | Title | Pts | Status | Depends on |
|---|---|---|---|---|
| [C1](C1_synthetic_data_generator.md) | Synthetic data generator | 5 | ⬜ | A2 |
| [C2](C2_eval_corpus_assembly.md) | Eval corpus assembly (~18 docs) | 3 | ⬜ | C1 |
| [C3](C3_extraction_accuracy_harness.md) | Extraction accuracy harness | 3 | ⬜ | C2 |
| [C4](C4_adversarial_prompt_suite.md) | Adversarial prompt suite | 3 | ⬜ | B3 |
| [C5](C5_confidence_band_calibration.md) | Confidence band calibration | 6 | ⬜ | C3, D6 |

### Epic D — Ingestion (27 pts)
| ID | Title | Pts | Status | Depends on |
|---|---|---|---|---|
| [D1](D1_upload_validation_probes.md) | Upload + validation + pre-LLM probes | 3 | ✅ | A3 |
| [D2](D2_document_classifier.md) | Document classifier (3 categories) | 5 | ✅ | B1, B2 |
| [D3](D3_classification_gated_storage.md) | Classification-gated raw doc storage | 3 | ✅ | D1, D2, A3 |
| [D4](D4_textract_primary_path.md) | AWS Textract primary path | 5 | ✅ | D1 |
| [D5](D5_vision_llm_fallback.md) | Vision-LLM fallback | 3 | ⬜ | D4, B1 |
| [D6](D6_structurer_composite_confidence.md) | Structurer + composite confidence + 3-band routing | 8 | ⬜ | D4, D5, B1, B3 |

### Epic E — Normalization (14 pts)
| ID | Title | Pts | Status | Depends on |
|---|---|---|---|---|
| [E1](E1_normalization_tier1_alias.md) | Tier 1 LOINC-aware alias lookup | 3 | ⬜ | A2, A3 |
| [E2](E2_pending_taxonomy_queue.md) | Tier 4 pending taxonomy queue + admin CLI | 5 | ⬜ | E1, A3 |
| [E3](E3_unit_conversion_range_validation.md) | Unit conversion + range validation | 3 | ⬜ | A2, E1 |
| [E4](E4_duplicate_detection.md) | Duplicate detection | 3 | ⬜ | E1, E3 |

### Epic F — Intelligence (30 pts)
| ID | Title | Pts | Status | Depends on |
|---|---|---|---|---|
| [F1](F1_trend_engine.md) | Trend Engine (deterministic) | 3 | ⬜ | A3, E1 |
| [F2](F2_observation_generator.md) | Observation Generator (Mode B) | 5 | ⬜ | B1, B3, B5, F1 |
| [F3](F3_nlq_handler.md) | NLQ Handler | 5 | ⬜ | B1, B3, B5, A3 |
| [F4](F4_context_cards.md) | Context cards | 3 | ⬜ | A2, F1 |
| [F5](F5_summary_generator_cardiology.md) | Summary Generator (cardiology, Mode A) | 8 | ⬜ | B1, B2, B3, B4, A3, A2 |
| [F6](F6_annotation_and_export.md) | Annotation + export (PDF/MD/JSON) | 6 | ⬜ | F5, A3 |

### Epic G — Top Layer (11 pts)
| ID | Title | Pts | Status | Depends on |
|---|---|---|---|---|
| [G1](G1_mcp_server_six_tools.md) | MCP server + 6 tools wired | 8 | ⬜ | D, E, F complete |
| [G2](G2_patient_profile_mark.md) | Patient profile (Mark hardcoded) | 3 | ⬜ | A3 |

### Epic H — Demo (8 pts)


| ID | Title | Pts | Status | Depends on |
|---|---|---|---|---|
| [H1](H1_hero_longitudinal_dataset.md) | Hero longitudinal dataset (HbA1c × 9 × 3 labs) | 3 | ⬜ | C1, A2 |
| [H2](H2_demo_polish_and_rehearsal.md) | Demo polish + rehearsal | 5 | ⬜ | All |

## Suggested 10-day loading

| Day | Stories | Pts |
|---|---|---|
| 1 | A1, A2, A3 | 13 |
| 2 | B1, B2, C1 | 13 |
| 3 | B3, D1, D2 | 11 |
| 4 | D3, D4, C2 | 11 |
| 5 | D5, D6 | 11 |
| 6 | E1, E2, E3, E4 | 14 |
| 7 | B4, B5, C3, C5 | 19 |
| 8 | F1, F2, F3, F4, G2 | 19 |
| 9 | F5, F6, G1 | 22 |
| 10 | C4, H1, H2 | 11 |

Days 7 and 9 are the heaviest. If reality bites, the smallest relief valve is moving F4 (context cards) and F6's markdown/JSON formats out of the demo critical path — PDF is the only format the demo actually shows.

## Capstone scope cross-walk

Every item in architecture §11 (capstone scope) and roadmap §4 (Scope-in) maps to at least one story above. Use this as a coverage check:

- **Ingestion** (Textract, structurer, vision fallback, 3-category classification, conservative bias, composite confidence + bands, week-2 calibration) → A1, B1, B2, B3, C5, D1–D6
- **Normalization** (Tier 1 + Tier 4, ~30 biomarkers, UCUM, dedup) → A2, E1–E4
- **Persistence** (Supabase, repos, classification-gated storage, reference data) → A2, A3, D3
- **Intelligence** (Trend Engine, Observation Generator, NLQ, Summary Generator cardiology, hero data) → F1–F6, H1
- **AI Gateway + guardrails** (chokepoint, prompt registry, L1+L2+L3, Mode A + Mode B, eval logging) → B1–B5
- **Eval suite** (ground truth, accuracy, adversarial, factuality) → C1–C5
- **Top Layer** (MCP server + 6 tools, Claude Desktop) → G1
- **Patient profile** (Mark hardcoded) → G2
- **Demo + writeup** → H1, H2

## Workflow notes

Per `applications/CLAUDE.md`:
- Update each story's `Notes / changelog` section as work progresses.
- Update this README's `Status` column when starting/completing a story.
- Plans must be approved before implementing (already done at the backlog level; per-story plan modes are not required for stories whose ACs are unambiguous).
