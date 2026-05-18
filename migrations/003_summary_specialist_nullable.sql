-- Drop specialist_type and visit_type columns from the summary table.
-- These columns were added in the initial schema for a design that was
-- removed before implementation (F5 explicitly dropped specialist params).
-- The Python SummaryRow/SummaryCreate models have no such fields; dropping
-- the columns keeps the schema in sync.

ALTER TABLE summary DROP COLUMN IF EXISTS specialist_type;
ALTER TABLE summary DROP COLUMN IF EXISTS visit_type;
