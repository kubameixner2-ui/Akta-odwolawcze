"""Check the same schema-constrained chat interface used for judging."""
from extractor import completion

if __name__ == "__main__":
    schema = {"type": "object", "properties": {"status": {"enum": ["ok"]}},
              "required": ["status"], "additionalProperties": False}
    print(completion("Zwróć status ok.", "Sprawdzenie usługi.", schema)["status"])
