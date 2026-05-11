# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.addons.payment.tests.common import PaymentCommon

@tagged('post_install', '-at_install')
class TestPaylabsProvider(PaymentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.paylabs = cls._prepare_provider('paylabs', update_values={
            'paylabs_merchant_id': 'TEST1234',
            'paylabs_private_key': 'DUMMY_KEY',
            'paylabs_public_key': 'DUMMY_PUB',
        })

    def test_paylabs_provider_mode(self):
        """Test the API URL generation based on provider state"""
        self.paylabs.state = 'test'
        self.assertEqual(self.paylabs._paylabs_get_api_url(), 'https://sit-api.paylabs.co.id')
        
        self.paylabs.state = 'enabled'
        self.assertEqual(self.paylabs._paylabs_get_api_url(), 'https://pro-api.paylabs.co.id')

    def test_payment_method_line_deduplication(self):
        """Test if the payment method lines are successfully deduplicated upon provider initialization"""
        # Ensure standard methods like QRIS are linked
        self.paylabs._ensure_paylabs_payment_method_lines()
        
        # Manually triggering the ensure method again shouldn't duplicate lines
        lines_before = len(self.paylabs.payment_method_ids)
        self.paylabs._ensure_paylabs_payment_method_lines()
        lines_after = len(self.paylabs.payment_method_ids)
        
        self.assertEqual(lines_before, lines_after, "Payment methods should be deduplicated")
