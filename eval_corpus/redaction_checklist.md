# HIPAA Safe Harbor Redaction Checklist

This checklist documents the 18 Safe Harbor identifiers removed from each
document in `eval_corpus/redacted_real/`. Each item must be verified before
the redacted PDF is committed to the repo.

## Per-document checklist

For each `redacted_real/*.pdf`, confirm the following are absent or replaced
with `REDACTED`:

| # | Identifier | Verified |
|---|---|---|
| 1 | Patient name (first, last, middle initial) | ☐ |
| 2 | Geographic data smaller than state (street, city, zip, county) | ☐ |
| 3 | All date elements except year (month, day, full dates — e.g. DOB, collection date) | ☐ |
| 4 | Phone numbers | ☐ |
| 5 | Fax numbers | ☐ |
| 6 | Email addresses | ☐ |
| 7 | Social Security number | ☐ |
| 8 | Medical record number (MRN) | ☐ |
| 9 | Health plan beneficiary number | ☐ |
| 10 | Account number | ☐ |
| 11 | Certificate or license number | ☐ |
| 12 | Vehicle identifier or serial number | ☐ |
| 13 | Device identifier or serial number | ☐ |
| 14 | Web URL | ☐ |
| 15 | IP address | ☐ |
| 16 | Biometric identifier (fingerprint, voice print) | ☐ |
| 17 | Full-face photograph or comparable image | ☐ |
| 18 | Any other unique identifying number or code | ☐ |

## Lab-report-specific items (also redact)

- Ordering physician name and NPI
- Referring provider name
- Accession / specimen ID number
- Lab client account number
- Patient portal username or QR code

## Redaction log

| Filename | Redacted by | Date | Terms redacted | Notes |
|---|---|---|---|---|
| _(fill in after redacting each document)_ | | | | |

## How to run redaction

```bash
python scripts/redact_real.py \
    --input /path/to/original.pdf \
    --output eval_corpus/redacted_real/report_NNN.pdf \
    --terms "Your Name" "Your DOB" "Your MRN" "Dr. Physician" "555-0100" "AccessionXXX"
```

Run with `--dry-run` first to count matches before writing.
After redaction, open the output PDF and visually confirm all black boxes are correct.
