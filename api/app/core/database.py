"""
Raven — Database connection
Uses Supabase Python client for RLS-aware queries,
plus raw asyncpg for heavy analytics.
"""

from supabase import create_client, Client
from app.core.config import settings

# Service role client — bypasses RLS, used by backend only
# NEVER expose this key to the frontend
supabase: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_SERVICE_ROLE_KEY,
)

# User-scoped client factory (uses anon key + user JWT for RLS enforcement)
def get_user_client(user_jwt: str) -> Client:
    """Return a Supabase client scoped to the authenticated user."""
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.auth.set_session(user_jwt, "")
    return client

# Alias for import compatibility
engine = supabase
