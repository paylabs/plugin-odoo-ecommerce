# -*- coding: utf-8 -*-
import json
import base64
from datetime import datetime, timezone
from odoo.tests import tagged
from odoo.tests.common import BaseCase
from ..utils.signature import generate_signature, verify_signature

# Generate a dummy RSA key pair for testing
try:
    from Crypto.PublicKey import RSA
    RSA_KEY = RSA.generate(2048)
    PRIVATE_KEY_PEM = RSA_KEY.export_key().decode('utf-8')
    PUBLIC_KEY_PEM = RSA_KEY.publickey().export_key().decode('utf-8')
except ImportError:
    PRIVATE_KEY_PEM = "---"
    PUBLIC_KEY_PEM = "---"

@tagged('post_install', '-at_install')
class TestPaylabsSignature(BaseCase):

    def setUp(self):
        super().setUp()
        self.body_dict = {"merchantId": "123", "amount": 1000}
        self.endpoint = "/payment"
        self.path = "/test"
        # Use current time to pass timestamp tolerance check
        self.timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+00:00")

    def test_signature_generation_and_verification(self):
        """Test if a generated signature is correctly verified"""
        if PRIVATE_KEY_PEM == "---":
            self.skipTest("pycryptodome not installed")
            
        signature = generate_signature(
            self.body_dict, self.endpoint, self.path, self.timestamp, PRIVATE_KEY_PEM
        )
        self.assertTrue(signature, "Signature should not be empty")

        body_str = json.dumps(self.body_dict, separators=(',', ':'), ensure_ascii=False)
        is_valid = verify_signature(
            body_str, self.endpoint + self.path, self.timestamp, signature, PUBLIC_KEY_PEM
        )
        self.assertTrue(is_valid, "Valid signature should be verified successfully")

    def test_invalid_signature_rejection(self):
        """Test if an invalid signature is rejected"""
        if PRIVATE_KEY_PEM == "---":
            self.skipTest("pycryptodome not installed")

        body_str = json.dumps(self.body_dict, separators=(',', ':'), ensure_ascii=False)
        invalid_sig = base64.b64encode(b"invalid_signature_data").decode('utf-8')
        
        is_valid = verify_signature(
            body_str, self.endpoint + self.path, self.timestamp, invalid_sig, PUBLIC_KEY_PEM
        )
        self.assertFalse(is_valid, "Invalid signature should be rejected")

    def test_timestamp_tolerance_rejection(self):
        """Test if an expired timestamp is rejected (Replay Attack Prevention)"""
        if PRIVATE_KEY_PEM == "---":
            self.skipTest("pycryptodome not installed")
            
        # Timestamp from 10 minutes ago
        old_timestamp = "2020-01-01T12:00:00.000+00:00"
        
        signature = generate_signature(
            self.body_dict, self.endpoint, self.path, old_timestamp, PRIVATE_KEY_PEM
        )
        
        body_str = json.dumps(self.body_dict, separators=(',', ':'), ensure_ascii=False)
        is_valid = verify_signature(
            body_str, self.endpoint + self.path, old_timestamp, signature, PUBLIC_KEY_PEM
        )
        self.assertFalse(is_valid, "Signature with old timestamp should be rejected")
