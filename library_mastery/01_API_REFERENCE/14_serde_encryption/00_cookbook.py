from __future__ import annotations

from pathlib import Path
import os
import sys

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


def recipe_jsonplus_roundtrip() -> None:
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    banner("JsonPlusSerializer: round-trip")
    serde = JsonPlusSerializer(pickle_fallback=False)
    obj = {"user": {"id": "u1"}, "nums": [1, 2, 3], "ok": True}
    enc, blob = serde.dumps_typed(obj)
    show("encoding", enc)
    show("bytes_len", len(blob))
    show("decoded", serde.loads_typed((enc, blob)))


def recipe_encrypted_serializer_optional() -> None:
    from langgraph.checkpoint.serde.encrypted import EncryptedSerializer
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    banner("EncryptedSerializer: optional (pycryptodome)")

    key = os.environ.get("LANGGRAPH_AES_KEY", "").encode() or b"0123456789abcdef"
    try:
        serde = EncryptedSerializer.from_pycryptodome_aes(
            key=key,
            inner=JsonPlusSerializer(pickle_fallback=False),
        )
    except Exception as e:
        print("Encrypted serializer unavailable (missing dependency or invalid key).")
        print("Error:", type(e).__name__, str(e).splitlines()[0])
        return

    obj = {"secret": "hello", "n": 123}
    enc, blob = serde.dumps_typed(obj)
    show("ciphertext_len", len(blob))
    show("decoded", serde.loads_typed((enc, blob)))


def main() -> None:
    bootstrap_langgraph_namespace()
    recipe_jsonplus_roundtrip()
    recipe_encrypted_serializer_optional()


if __name__ == "__main__":
    main()

