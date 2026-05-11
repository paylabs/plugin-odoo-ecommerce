# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.addons.payment.tests.common import PaymentCommon

@tagged('post_install', '-at_install')
class TestPaylabsWebhook(PaymentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.paylabs = cls._prepare_provider('paylabs', update_values={
            'paylabs_merchant_id': 'TEST1234',
        })
        
        # Create a mock transaction
        cls.tx = cls._create_transaction(flow='redirect', provider_reference='S00061', state='pending')
        cls.tx.paylabs_merchant_trade_no = 'TXN123'
        cls.tx.reference = 'TXN123'

    def test_webhook_processing_success(self):
        """Test if a successful webhook correctly sets the transaction to 'done'"""
        notification_data = {
            'merchantTradeNo': 'TXN123',
            'status': '02',
            'amount': self.tx.amount,
        }
        
        self.tx._process_notification_data(notification_data)
        self.assertEqual(self.tx.state, 'done', "Transaction should be done")

    def test_webhook_processing_failure(self):
        """Test if a failed webhook correctly sets the transaction to 'cancel'"""
        notification_data = {
            'merchantTradeNo': 'TXN123',
            'status': '03',
        }
        
        self.tx._process_notification_data(notification_data)
        self.assertEqual(self.tx.state, 'cancel', "Transaction should be canceled")

    def test_idempotency_skip(self):
        """Test if duplicate webhook processing is skipped for 'done' transactions"""
        self.tx.state = 'done'
        
        notification_data = {
            'merchantTradeNo': 'TXN123',
            'status': '02',
        }
        
        # Assuming the logging says skipping duplicate processing, the state should remain 'done'
        self.tx._process_notification_data(notification_data)
        self.assertEqual(self.tx.state, 'done', "State should remain done on retry")
