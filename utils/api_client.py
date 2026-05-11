# -*- coding: utf-8 -*-
"""
Paylabs HTTP API Client

Wraps all Paylabs REST API calls with automatic:
- Timestamp generation (Asia/Jakarta timezone)
- Request ID generation
- RSA-SHA256 signature
- Header injection
- Error handling and logging
"""

import json
import random
import logging
import requests
from datetime import datetime

try:
    import pytz
    PYTZ_AVAILABLE = True
except ImportError:
    PYTZ_AVAILABLE = False

from .signature import generate_signature

_logger = logging.getLogger(__name__)

# -----------------------------------------------------------------
# Paylabs API v2.3 base URLs
# -----------------------------------------------------------------
URL_PRODUCTION = "https://pay.paylabs.co.id/payment/"
URL_SANDBOX = "https://sit-pay.paylabs.co.id/payment/"
URL_SITCH = "https://sitch-pay.paylabs.co.id/payment/"
API_VERSION = "v2.3"
ENDPOINT_PREFIX = "/payment/" + API_VERSION  # used for signature

# -----------------------------------------------------------------
# Payment type codes
# -----------------------------------------------------------------
PAYMENT_TYPES = {
    # QRIS
    'qris': 'QRIS',

    # Virtual Account
    'va_bca': 'BCAVA',
    'va_bri': 'BRIVA',
    'va_bni': 'BNIVA',
    'va_mandiri': 'MandiriVA',
    'va_permata': 'PermataVA',
    'va_cimb': 'CIMBVA',
    'va_bsi': 'BSIVA',
    'va_nobu': 'NobuVA',
    'va_btn': 'BTNVA',
    'va_maybank': 'MaybankVA',
    'va_danamon': 'DanamonVA',
    'va_bnc': 'BNCVA',
    'va_muamalat': 'MuamalatVA',
    'va_sinarmas': 'SinarmasVA',
}

VA_PAYMENT_TYPES = {k: v for k, v in PAYMENT_TYPES.items() if k.startswith('va_')}


def _get_jakarta_timestamp():
    """Return current time as ISO8601 string in Asia/Jakarta timezone."""
    if PYTZ_AVAILABLE:
        jakarta_tz = pytz.timezone('Asia/Jakarta')
        now = datetime.now(jakarta_tz)
    else:
        # Fallback: use UTC+7 offset manually
        from datetime import timezone, timedelta
        tz = timezone(timedelta(hours=7))
        now = datetime.now(tz)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}" + "+07:00"


def _get_request_id():
    """Generates a unique Request ID based on timestamp and random digits."""
    now = datetime.now()
    return now.strftime("%Y%m%d%H%M%S") + str(random.randint(11111, 99999))

class PaylabsApiClient:
    """
    HTTP client for Paylabs Payment Gateway API v2.3.

    Usage::

        client = PaylabsApiClient(
            merchant_id='YOUR_MID',
            private_key='-----BEGIN RSA PRIVATE KEY-----\\n...',
            mode='sandbox',  # or 'production'
        )
        result = client.create_qris(
            merchant_trade_no='ORDER001',
            amount=50000,
            product_name='Pembayaran Pesanan #001',
            notify_url='https://your.domain.com/payment/paylabs/webhook',
        )
    """

    def __init__(self, merchant_id, private_key, mode='sandbox', notify_url=None):
        """
        Initializes the Paylabs API Client.
        :param merchant_id: Merchant ID from Paylabs.
        :param private_key: RSA Private Key for signing.
        :param mode: 'sandbox' (testing) or 'production' (live).
        :param notify_url: Default URL to receive webhook notifications.
        """
        self.merchant_id = merchant_id
        self.private_key = private_key
        self.mode = mode
        self.default_notify_url = notify_url

        if mode == 'production':
            self.base_url = URL_PRODUCTION + API_VERSION
        elif mode == 'sitch':
            self.base_url = URL_SITCH + API_VERSION
        else:
            self.base_url = URL_SANDBOX + API_VERSION

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_headers(self, body_dict, path, timestamp=None, request_id=None):
        """
        Constructs the HTTP headers required by Paylabs, including Digital Signature.
        """
        timestamp = timestamp or _get_jakarta_timestamp()
        request_id = request_id or _get_request_id()

        signature = generate_signature(
            body_dict=body_dict,
            endpoint=ENDPOINT_PREFIX,
            path=path,
            timestamp=timestamp,
            private_key_pem=self.private_key,
        )
        return {
            'X-TIMESTAMP': timestamp,
            'X-SIGNATURE': signature,
            'X-PARTNER-ID': self.merchant_id,
            'X-REQUEST-ID': request_id,
            'Content-Type': 'application/json;charset=utf-8',
        }

    def _post(self, path, body_dict, max_retries=2):
        """
        Executes a POST request to the Paylabs API with error handling, logging, and retry mechanism.
        """
        # Ensure requestId in body matches X-REQUEST-ID in header
        # Idempotency Support: If we retry, we use the SAME requestId
        request_id = body_dict.get('requestId')
        if not request_id:
            request_id = _get_request_id()
            body_dict['requestId'] = request_id

        url = self.base_url + path
        payload = json.dumps(body_dict, separators=(',', ':'), ensure_ascii=False)

        _logger.info("Paylabs API POST %s | requestId=%s", url, request_id)
        _logger.debug("Paylabs request body: %s", payload)

        import time

        for attempt in range(max_retries + 1):
            try:
                # We regenerate the timestamp and signature for each attempt to prevent expiry
                timestamp = _get_jakarta_timestamp()
                headers = self._build_headers(body_dict, path, timestamp, request_id)

                _logger.info("Paylabs API: Sending request to %s (Attempt %d/%d)...", url, attempt + 1, max_retries + 1)
                
                start_time = time.time()
                response = requests.post(url, headers=headers, data=payload, timeout=20)
                latency = time.time() - start_time
                
                _logger.info("Paylabs API [%s]: Received response [%s] in %.2f seconds", request_id, response.status_code, latency)
                _logger.debug("Paylabs response body [%s]: %s", request_id, response.text)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.Timeout:
                _logger.warning("Paylabs API timeout [%s]: %s (Attempt %d/%d)", request_id, url, attempt + 1, max_retries + 1)
                if attempt == max_retries:
                    _logger.error("Paylabs API timeout [%s] after %d retries.", request_id, max_retries)
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s
            except requests.exceptions.RequestException as e:
                _logger.error("Paylabs API error [%s]: %s | %s", request_id, url, e)
                if hasattr(e, 'response') and e.response is not None:
                    _logger.error("Paylabs API error response: %s", e.response.text)
                    # Don't retry on client errors (4xx) except 429 Too Many Requests
                    if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                        raise
                
                if attempt == max_retries:
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff

    def _base_body(self, merchant_trade_no, request_id=None):
        """Return base request body fields."""
        return {
            'merchantId': self.merchant_id,
            'merchantTradeNo': merchant_trade_no,
            'requestId': request_id or _get_request_id(),
        }

    # ------------------------------------------------------------------
    # QRIS API
    # ------------------------------------------------------------------

    def create_qris(self, merchant_trade_no, amount, product_name,
                    notify_url=None, store_id=None):
        """
        Create QRIS payment.

        :param merchant_trade_no: str — unique order/trade number
        :param amount:            int/float — payment amount in IDR
        :param product_name:      str — product/order description
        :param notify_url:        str — webhook URL for payment notification
        :param store_id:          str — store/outlet ID (optional)
        :return: dict — Paylabs API response
          {
            'errCode': '0',             # '0' = success
            'errCodeDes': 'success',
            'merchantId': '...',
            'merchantTradeNo': '...',
            'requestId': '...',
            'totalAmount': 50000,
            'qrisUrl': 'https://...',   # QR code image URL
            'qrCode': 'QRCODE_STRING',  # raw QR string (for display)
            'expiredTime': '...',        # QR expiry time
            'paymentType': 'QRIS',
          }
        """
        path = "/qris/create"
        body = self._base_body(merchant_trade_no)
        body.update({
            'paymentType': 'QRIS',
            'amount': int(amount),
            'productName': product_name,
        })
        if notify_url or self.default_notify_url:
            body['notifyUrl'] = notify_url or self.default_notify_url
        if store_id:
            body['storeId'] = str(store_id)

        return self._post(path, body)

    def query_qris(self, merchant_trade_no):
        """Query QRIS transaction status."""
        path = "/qris/query"
        body = self._base_body(merchant_trade_no)
        body['paymentType'] = 'QRIS'
        return self._post(path, body)

    # ------------------------------------------------------------------
    # Virtual Account API
    # ------------------------------------------------------------------

    def create_h5_link(self, merchant_trade_no, amount, product_name, phone_number, redirect_url, payer_name=None, notify_url=None):
        """
        Create H5 Payment Link (Hosted Checkout).
        """
        path = "/h5/createLink"
        body = self._base_body(merchant_trade_no)
        body.update({
            'amount': int(amount),
            'productName': product_name,
            'phoneNumber': phone_number,
            'redirectUrl': redirect_url,
        })
        if payer_name:
            body['payer'] = payer_name
        if notify_url or self.default_notify_url:
            body['notifyUrl'] = notify_url or self.default_notify_url

        return self._post(path, body)

    def create_va(self, payment_type, merchant_trade_no, amount, product_name,
                  payer, notify_url=None, store_id=None):
        """
        Create Virtual Account payment.

        :param payment_type:      str — VA type code e.g. 'BCAVA', 'BRIVA', 'BSIVA'
        :param merchant_trade_no: str — unique order number
        :param amount:            int — payment amount in IDR
        :param product_name:      str — product description
        :param payer:             str — payer name
        :param notify_url:        str — webhook URL
        :param store_id:          str — store/outlet ID (optional)
        :return: dict — Paylabs API response
          {
            'errCode': '0',
            'merchantTradeNo': '...',
            'totalAmount': 50000,
            'vaCode': '88888XXXXXXX',    # Virtual Account number
            'expiredTime': '...',
            'paymentType': 'BCAVA',
          }
        """
        path = "/va/create"
        body = self._base_body(merchant_trade_no)
        body.update({
            'paymentType': payment_type,
            'amount': int(amount),
            'productName': product_name,
            'payer': payer,
        })
        if notify_url or self.default_notify_url:
            body['notifyUrl'] = notify_url or self.default_notify_url
        if store_id:
            body['storeId'] = str(store_id)

        return self._post(path, body)

    def query_va(self, payment_type, merchant_trade_no):
        """Query Virtual Account transaction status."""
        path = "/va/query"
        body = self._base_body(merchant_trade_no)
        body['paymentType'] = payment_type
        return self._post(path, body)

    # ------------------------------------------------------------------
    # Transaction status helper (used for polling)
    # ------------------------------------------------------------------

    def query_transaction(self, payment_method, merchant_trade_no, payment_type=None):
        """
        Generic query for any payment type.

        :param payment_method: str — 'qris' or 'va'
        :param merchant_trade_no: str
        :param payment_type: str — required for VA (e.g. 'BCAVA')
        """
        if payment_method == 'qris':
            return self.query_qris(merchant_trade_no)
        elif payment_method == 'va':
            return self.query_va(payment_type, merchant_trade_no)
        else:
            raise ValueError(f"Unknown payment method: {payment_method}")
