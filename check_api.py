"""Check the same schema-constrained chat interface used for judging."""
from urllib.error import HTTPError

from extractor import completion

if __name__ == "__main__":
    schema = {"type": "object", "properties": {"status": {"enum": ["ok"]}},
              "required": ["status"], "additionalProperties": False}
    try:
        print(completion("Zwróć status ok.", "Sprawdzenie usługi.", schema)["status"])
    except HTTPError as err:
        raise SystemExit(f"API check failed (HTTP {err.code}). Check the endpoint, model and API key in .env.") from None
    except OSError:
        raise SystemExit("Cannot reach the model API. Check KIO_LLM_BASE_URL in .env or start the local model server.") from None
