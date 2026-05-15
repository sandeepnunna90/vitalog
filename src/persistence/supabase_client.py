"""Supabase client factory for the Vitalog persistence layer.

Two client modes:
- Service role (bypasses RLS): migrations, admin ops, seed scripts.
- Anon + patient JWT (RLS enforced): all application code.

Never import supabase.Client directly outside this module.
"""

from __future__ import annotations

import os

from supabase import Client, create_client


def get_service_client() -> Client:
    """Return a service-role Supabase client that bypasses RLS.

    Uses SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables.
    Only use for admin operations — never in the request path.
    """
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


def get_anon_client(patient_jwt: str) -> Client:
    """Return an anon Supabase client with a patient JWT for RLS enforcement.

    Uses SUPABASE_URL and SUPABASE_ANON_KEY environment variables.
    All queries execute as the patient identified by the JWT.
    """
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_ANON_KEY"]
    client: Client = create_client(url, key)
    client.postgrest.auth(patient_jwt)
    return client
