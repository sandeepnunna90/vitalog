-- Vitalog A3: Audit log append-only hash chain
-- Each inserted row computes prev_hash, payload_hash, and chain_hash via pgcrypto.
-- The trigger fires BEFORE INSERT so the computed values land in the same row.

CREATE OR REPLACE FUNCTION audit_log_chain_fn()
RETURNS TRIGGER AS $$
DECLARE
  prev_chain_hash TEXT;
BEGIN
  -- Fetch the most recent chain_hash; use sha256('') for the first row
  SELECT chain_hash INTO prev_chain_hash
  FROM audit_log
  ORDER BY log_id DESC
  LIMIT 1;

  IF prev_chain_hash IS NULL THEN
    prev_chain_hash := encode(digest('', 'sha256'), 'hex');
  END IF;

  NEW.payload_hash := encode(digest(NEW.payload::text, 'sha256'), 'hex');
  NEW.prev_hash    := prev_chain_hash;
  NEW.chain_hash   := encode(digest(prev_chain_hash || NEW.payload_hash, 'sha256'), 'hex');

  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER audit_log_chain_trigger
  BEFORE INSERT ON audit_log
  FOR EACH ROW EXECUTE FUNCTION audit_log_chain_fn();
