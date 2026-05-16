# Cost Notes — AWS Textract

## Textract free tier

AWS Textract's Analyze Document API (FeatureTypes: FORMS + TABLES) includes a free tier of **1,000 pages/month** for the first 3 months, then $0.015/page for forms analysis and $0.015/page for tables analysis.

## Capstone usage estimate

The capstone demo uses approximately 10 documents (Hero longitudinal dataset H1 + a handful of synthetic lab reports from C1). Each document is a single-page or short PDF. Total page volume is well under 100 pages — negligible cost, covered by the free tier.

## Production projection (out of capstone scope)

At scale (e.g., 10,000 uploads/month with average 2 pages each = 20,000 pages):
- Forms analysis: 20,000 × $0.015 = $300/month
- Tables analysis: 20,000 × $0.015 = $300/month
- Total: ~$600/month — acceptable for early product; revisit when volume exceeds free tier.
