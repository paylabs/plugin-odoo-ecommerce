# -*- coding: utf-8 -*-
"""
Paylabs Webhook Controller

Handles POST /payment/paylabs/webhook notifications from Paylabs.

Security:
  - Verifies X-SIGNATURE using Paylabs RSA Public Key before processing
  - Returns HTTP 200 only (Paylabs ignores response code but expects JSON)

Paylabs Webhook Body (example):
{
  "merchantId": "010552",
  "requestId": "N01055220260506552000001291778073255473",
  "errCode": "0",
  "paymentType": "QRIS",
  "amount": "10000.00",
  "createTime": "20260506201313",
  "successTime": "20260506201414",
  "merchantTradeNo": "S00061",
  "platformTradeNo": "2026050655200000129",
  "status": "02",
  "paymentMethodInfo": {
    "vaCode": "9999993322716841",
    "payer": "John Wilson"
  },
  "productName": "S00061",
  "transFeeRate": "0.000000",
  "transFeeAmount": "2500.00",
  "totalTransFee": "2500.00",
  "vatFee": "0",
  "requestAmount": "10000.00"
}
"""

import json
import logging
import pprint

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

PAYLABS_WEBHOOK_PATH = '/payment/paylabs/webhook'


class PaylabsController(http.Controller):

    @http.route(
        [PAYLABS_WEBHOOK_PATH],
        type='http',
        auth='none',
        methods=['POST'],
        csrf=False,
        save_session=False,
    )
    def paylabs_webhook(self, **kwargs):
        """
        Receives and processes payment webhook notifications from Paylabs.
        Uses auth='none' to be accessible without login session (critical for server-to-server).
        """
        # 1. Improved Database Context Selection
        db = request.params.get('db')
        import odoo
        from odoo.http import root
        
        if not db:
            # Try to get from session or host-to-db mapping
            db = getattr(request.session, 'db', False)
            if not db and hasattr(root, 'get_db_name'):
                db = root.get_db_name(request.httprequest.host)
            
            # Fallback to first available DB if still not found (common in auth='none')
            if not db:
                dbs = odoo.service.db.list_dbs()
                if dbs:
                    db = dbs[0]

        _logger.info("Paylabs Webhook using Database: %s", db)
        
        if db:
            try:
                # Force environment update with sudo privileges
                request.update_env(user=odoo.SUPERUSER_ID, context={'db': db})
            except Exception as e:
                _logger.error("Paylabs Webhook: Failed to update env for DB %s: %s", db, e)

        # 2. Read raw body and headers
        raw_body = request.httprequest.get_data(as_text=True)
        headers = dict(request.httprequest.headers)
        
        _logger.info("=== PAYLABS WEBHOOK DEBUG START ===")
        _logger.info("Headers: %s", pprint.pformat(headers))
        _logger.info("Raw Body: %s", raw_body)

        # ----------------------------------------------------------------
        # 2. Parse JSON body
        # ----------------------------------------------------------------
        try:
            notification_data = json.loads(raw_body)
        except json.JSONDecodeError as e:
            _logger.error("Paylabs webhook: invalid JSON body: %s", e)
            return request.make_response(
                json.dumps({'errCode': '1', 'errCodeDes': 'Invalid JSON'}),
                headers={'Content-Type': 'application/json'},
            )

        _logger.info("Parsed Data: %s", pprint.pformat(notification_data))

        # ----------------------------------------------------------------
        # 3. Extract key fields
        # ----------------------------------------------------------------
        merchant_trade_no = notification_data.get('merchantTradeNo', '')
        merchant_id = notification_data.get('merchantId', '')
        request_id = notification_data.get('requestId', '')

        if not merchant_trade_no:
            _logger.error("Paylabs webhook: missing merchantTradeNo")
            return self._paylabs_ack(merchant_id, request_id)

        # ----------------------------------------------------------------
        # 4. Verify signature (X-SIGNATURE header)
        # ----------------------------------------------------------------
        # Odoo's request.httprequest.headers is case-insensitive
        x_signature = request.httprequest.headers.get('X-SIGNATURE', '')
        x_timestamp = request.httprequest.headers.get('X-TIMESTAMP', '')

        if x_signature and x_timestamp:
            verified = self._verify_webhook_signature(
                raw_body, x_signature, x_timestamp, notification_data,
                path=request.httprequest.path
            )
            if not verified:
                _logger.warning(
                    "Paylabs webhook: INVALID signature for merchantTradeNo=%s",
                    merchant_trade_no
                )
                return request.make_response(
                    json.dumps({
                        'merchantId': merchant_id,
                        'requestId': request_id,
                        'errCode': '401',
                        'errCodeDes': 'Unauthenticated'
                    }),
                    status=401,
                    headers={'Content-Type': 'application/json'},
                )
            else:
                _logger.info("Paylabs webhook: Signature verified successfully.")
        else:
            _logger.error("Paylabs webhook: Missing X-SIGNATURE or X-TIMESTAMP. Security rejection.")
            return request.make_response(
                json.dumps({
                    'merchantId': merchant_id,
                    'requestId': request_id,
                    'errCode': '400',
                    'errCodeDes': 'Missing Security Headers'
                }),
                status=400,
                headers={'Content-Type': 'application/json'},
            )

        # ----------------------------------------------------------------
        # 5. Process notification using standard Odoo flow
        # ----------------------------------------------------------------
        try:
            _logger.info("Paylabs: Handing over to _handle_notification_data for ref=%s", merchant_trade_no)
            request.env['payment.transaction'].sudo()._handle_notification_data('paylabs', notification_data)
            
            # CRITICAL: Force commit so the status change is immediately visible to the frontend polling
            request.env.cr.commit()
            
            _logger.info("Paylabs: _handle_notification_data completed for ref=%s", merchant_trade_no)
        except Exception as e:
            _logger.exception(
                "Paylabs webhook: error processing notification for ref=%s: %s",
                merchant_trade_no, e
            )

        _logger.info("=== PAYLABS WEBHOOK DEBUG END ===")

        # ----------------------------------------------------------------
        # 6. Always return 200 OK with success response
        # ----------------------------------------------------------------
        return self._paylabs_ack(merchant_id, request_id)

    # ------------------------------------------------------------------
    # Signature verification helper
    # ------------------------------------------------------------------

    def _verify_webhook_signature(self, raw_body, signature, timestamp, notification_data, path=None):
        """
        Verifies the digital signature (X-SIGNATURE) from Paylabs.
        Uses Paylabs Public Key to ensure the request truly originates from them.
        """
        try:
            # Find the Paylabs provider to get the public key
            provider = request.env['payment.provider'].sudo().search(
                [('code', '=', 'paylabs'), ('state', '!=', 'disabled')], limit=1
            )
            if not provider:
                # Try legacy model name for Odoo <=15
                provider = request.env.get('payment.acquirer') and \
                           request.env['payment.acquirer'].sudo().search(
                               [('provider', '=', 'paylabs')], limit=1
                           )

            if not provider or not provider.paylabs_public_key:
                _logger.warning("Paylabs webhook: no public key configured, skipping verification")
                return True  # Skip verification if not configured

            from ..utils.signature import verify_signature
            return verify_signature(
                body_str=raw_body,
                path=path or PAYLABS_WEBHOOK_PATH,
                timestamp=timestamp,
                signature_b64=signature,
                public_key_pem=provider.paylabs_public_key,
            )
        except Exception as e:
            _logger.exception("Paylabs signature verification exception: %s", e)
            return False

    @staticmethod
    def _paylabs_ack(merchant_id='', request_id=''):
        """Return standard 200 OK JSON acknowledgement to Paylabs."""
        data = {
            'errCode': '0',
        }
        if merchant_id:
            data['merchantId'] = merchant_id
        if request_id:
            data['requestId'] = request_id
            
        return request.make_response(
            json.dumps(data),
            headers={'Content-Type': 'application/json;charset=utf-8'},
        )
