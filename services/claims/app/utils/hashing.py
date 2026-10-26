import hashlib
import json

from pydantic import BaseModel


def calculate_request_hash(model: BaseModel) -> str:
    """
    Calculates a SHA-256 hash of a Pydantic model's data.

    To ensure the hash is stable, we:
    1. Convert the model to a dictionary.
    2. Sort the keys alphabetically (canonical JSON).
    3. Encode as UTF-8 and hash using SHA-256.
    """
    # mode="json" renders datetimes/UUIDs as strings; plain model_dump() keeps them as objects json.dumps rejects.
    data = model.model_dump(mode="json")

    # sort_keys=True ensures canonical representation regardless of attribute order
    canonical_json = json.dumps(data, sort_keys=True, separators=(",", ":"))

    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
