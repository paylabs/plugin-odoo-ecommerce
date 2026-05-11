# -*- coding: utf-8 -*-
"""
Paylabs API Signature Utility

Implements RSA-SHA256 (PKCS#1 v1.5) signature generation and verification
based on the official Paylabs API specification v2.3.

Signature Algorithm:
  1. Minify JSON body (compact separators, no extra whitespace)
  2. hexPayload = sha256(minifiedBody).hexdigest()
  3. stringToSign = f"POST:{endpoint}{path}:{hexPayload}:{timestamp}"
  4. signature = Base64(RSA_PKCS1v15_Sign(SHA256(stringToSign), privateKey))
"""

import hashlib
import base64
import json
import logging

_logger = logging.getLogger(__name__)

try:
    from Crypto.Signature import pkcs1_15
    from Crypto.Hash import SHA256
    from Crypto.PublicKey import RSA
    PYCRYPTODOME_AVAILABLE = True
except ImportError:
    try:
        from Cryptodome.Signature import pkcs1_15
        from Cryptodome.Hash import SHA256
        from Cryptodome.PublicKey import RSA
        PYCRYPTODOME_AVAILABLE = True
    except ImportError:
        PYCRYPTODOME_AVAILABLE = False
        _logger.warning(
            "PyCryptodome/PyCryptodomex is not installed. "
            "Paylabs payment provider will not work. "
            "Install with: pip install pycryptodome"
        )


def _check_pycrypto():
    """Raise ImportError if pycryptodome is not available."""
    if not PYCRYPTODOME_AVAILABLE:
        raise ImportError(
            "PyCryptodome is required for Paylabs payment gateway. "
            "Install with: pip install pycryptodome"
        )


def generate_signature(body_dict, endpoint, path, timestamp, private_key_pem):
    """
    Generates an RSA-SHA256 Digital Signature for Paylabs API requests.
    This signature ensures data integrity and merchant authentication.

    :param body_dict: dict  — request body as Python dict
    :param endpoint:  str   — API endpoint prefix e.g. '/payment/v2.3'
    :param path:      str   — API path e.g. '/qris/create'
    :param timestamp: str   — ISO8601 timestamp e.g. '2024-01-01T12:00:00.000+07:00'
    :param private_key_pem: str — RSA private key in PEM format
    :return: str — Base64-encoded signature
    """
    _check_pycrypto()

    # Step 1: Minify JSON body (compact separators)
    body_str = json.dumps(body_dict, separators=(',', ':'), ensure_ascii=False)
    _logger.info("Paylabs minified body: %s", body_str)

    # Step 2: SHA256 hex digest of minified body
    sha_json = hashlib.sha256(body_str.encode('utf-8')).hexdigest()
    _logger.info("Paylabs body SHA256: %s", sha_json)

    # Step 3: Construct string to sign
    string_to_sign = f"POST:{endpoint}{path}:{sha_json}:{timestamp}"
    _logger.info("Paylabs stringToSign: %s", string_to_sign)

    # Step 4: RSA-SHA256 sign
    private_key = RSA.import_key(private_key_pem)
    h = SHA256.new(string_to_sign.encode('utf-8'))
    signature_bytes = pkcs1_15.new(private_key).sign(h)

    # Step 5: Base64 encode
    return base64.b64encode(signature_bytes).decode('utf-8')


def verify_signature(body_str, path, timestamp, signature_b64, public_key_pem):
    """
    Verifies the Signature from webhooks sent by Paylabs.
    Prevents unauthorized parties from sending fraudulent payment notifications.

    :param body_str:       str — raw request body as string
    :param path:           str — full endpoint path used in webhook
    :param timestamp:      str — X-TIMESTAMP from webhook header
    :param signature_b64:  str — Base64 signature from X-SIGNATURE header
    :param public_key_pem: str — Paylabs RSA public key in PEM format
    :return: bool — True if signature is valid
    """
    _check_pycrypto()

    try:
        binary_signature = base64.b64decode(signature_b64)
        sha_json = hashlib.sha256(body_str.encode('utf-8')).hexdigest()
        string_to_sign = f"POST:{path}:{sha_json}:{timestamp}"

        public_key = RSA.import_key(public_key_pem)
        h = SHA256.new(string_to_sign.encode('utf-8'))
        pkcs1_15.new(public_key).verify(h, binary_signature)
        return True
    except (ValueError, TypeError, Exception) as e:
        _logger.warning("Paylabs webhook signature verification failed: %s", e)
        return False
