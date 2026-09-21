#!/usr/bin/env python3
import hashlib, secrets, sys
if len(sys.argv) != 2: raise SystemExit("Uso: make_password.py SENHA")
salt = secrets.token_bytes(16)
digest = hashlib.pbkdf2_hmac("sha256", sys.argv[1].encode(), salt, 240_000)
print(salt.hex() + "$" + digest.hex())

