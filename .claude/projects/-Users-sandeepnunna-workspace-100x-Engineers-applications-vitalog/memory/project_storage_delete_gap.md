---
name: Storage file not deleted when document row is deleted
description: Known gap — deleting a document DB row does not clean up the associated file in Supabase Storage bucket
type: project
---

Deleting from the `document` table does not remove the corresponding file from the Supabase Storage `lab_reports` bucket. The two are currently disconnected.

**Why:** The repository layer only issues a Postgres DELETE; there is no corresponding `storage.remove()` call.

**How to apply:** When implementing document deletion (any admin or user-facing delete flow), add a `storage_repo.delete(document_id)` call after the DB delete. Also consider a Supabase database webhook or trigger as an alternative to keep the storage lifecycle coupled to the DB row.
