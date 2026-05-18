-- Make specialist_type and visit_type nullable on the summary table.
-- These columns were added in the initial schema for a design that was
-- removed before implementation (F5 explicitly dropped specialist params).
-- F6 persist() sends no values for these fields; the NOT NULL constraint
-- blocks every SummaryRepository.add() call.

ALTER TABLE summary ALTER COLUMN specialist_type DROP NOT NULL;
ALTER TABLE summary ALTER COLUMN visit_type DROP NOT NULL;
