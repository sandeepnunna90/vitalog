-- H5: Add auth_user_id and api_key to patient table for MCP OAuth 2.0.
-- auth_user_id links to Supabase Auth users (Google OAuth).
-- api_key is the bearer token issued to mcp-remote after login.
-- Apply this migration BEFORE deploying H5 to avoid 500 errors on /sse connections.

ALTER TABLE patient ADD COLUMN IF NOT EXISTS auth_user_id text UNIQUE;
ALTER TABLE patient ADD COLUMN IF NOT EXISTS api_key uuid UNIQUE DEFAULT gen_random_uuid();
