from __future__ import annotations

from pathlib import Path
import os
import sys

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from _bootstrap import bootstrap_langgraph_namespace
from _utils import banner, show


def main() -> None:
    bootstrap_langgraph_namespace()

    from langgraph.checkpoint.serde.encrypted import EncryptedSerializer
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    banner("EncryptedSerializer (optional dependency: pycryptodome)")

    # 16/24/32 bytes are valid AES key sizes.
    key = os.environ.get("LANGGRAPH_AES_KEY", "").encode() or b"0123456789abcdef"

    try:
        serde = EncryptedSerializer.from_pycryptodome_aes(
            key=key,
            inner=JsonPlusSerializer(),
        )
    except Exception as e:
        print("Could not create EncryptedSerializer (likely missing pycryptodome).")
        print("Error:", type(e).__name__, str(e).splitlines()[0])
        return

    obj = {"secret": "hello", "n": 123}

    enc, ciphertext = serde.dumps_typed(obj)
    banner("ciphertext")
    show("encoding", enc)
    show("bytes_len", len(ciphertext))
    show("bytes_preview", ciphertext[:32])

    banner("round-trip decrypt")
    decoded = serde.loads_typed((enc, ciphertext))
    show("decoded", decoded)


if __name__ == "__main__":
    main()

