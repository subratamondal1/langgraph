# Section 14 — Serialization & Encryption (`langgraph.checkpoint.serde.*`)

This folder is a runnable companion to **Section 14** of `library_mastery/01_API_REFERENCE.md`.

Goal: understand how checkpoint/cache payloads become bytes (and how to harden it):
- `JsonPlusSerializer` is the default serde for many adapters
- `EncryptedSerializer` wraps another serializer to encrypt its bytes
- security matters: permissive “revival” or pickle fallback can be dangerous with untrusted data

## Files

- `00_cookbook.py`
  - production-first serde patterns: safe JsonPlus defaults + optional encryption wrapper

- `jsonplus_roundtrip.py`
  - round-trips a Python object through `JsonPlusSerializer`
  - prints byte length + decoded value so you can debug exactly what’s being persisted

- `encrypted_serializer_roundtrip.py`
  - tries to round-trip with `EncryptedSerializer.from_pycryptodome_aes`
  - if `pycryptodome` isn’t installed, prints a message and exits cleanly

## Run

```bash
./.venv/bin/python library_mastery/01_API_REFERENCE/14_serde_encryption/jsonplus_roundtrip.py
```
