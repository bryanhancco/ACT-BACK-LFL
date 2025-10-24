import os
import logging
from supabase import create_client, Client
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

def _strip_quotes(value: str | None) -> str | None:
	if value is None:
		return None
	v = value.strip()
	# Remove surrounding single or double quotes if present
	if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
		return v[1:-1]
	return v

try:
	raw_url = os.environ.get('SUPABASE_URL')
	raw_key = os.environ.get('SUPABASE_API_KEY')

	url: str = _strip_quotes(raw_url) or ''
	key: str = _strip_quotes(raw_key) or ''

	if not url or not key:
		logging.error('SUPABASE_URL or SUPABASE_API_KEY is not set. Check .env')
		raise RuntimeError('Database configuration missing')

	# create_client will raise if url is malformed; let the exception propagate with a clear message
	supabase: Client = create_client(url, key)
except Exception as e:
	logging.exception('Failed to initialize Supabase client: %s', e)
	# Re-raise so the application fails fast with a clear error
	raise