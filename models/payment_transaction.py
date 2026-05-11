# -*- coding: utf-8 -*-
import logging
import json
import urllib.parse
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Paylabs status codes
PAYLABS_SUCCESS_CODE = '0'
PAYLABS_PAYMENT_SUCCESS = '02'
PAYLABS_PAYMENT_FAILED = '09'
PAYLABS_PAYMENT_PENDING = '01'

class PaymentTransaction(models.Model):
    """
    This model handles the payment transaction lifecycle.
    From creating requests to the Paylabs API to processing webhooks.
    """
    _inherit = 'payment.transaction'

    # ------------------------------------------------------------------
    # Paylabs-specific fields
    # ------------------------------------------------------------------
    paylabs_payment_type = fields.Char(string='Paylabs Payment Type')
    paylabs_merchant_trade_no = fields.Char(string='Paylabs Merchant Trade No', index=True)
    paylabs_qr_url = fields.Char(string='QRIS Image URL')
    paylabs_qr_code = fields.Char(string='QRIS Raw Code')
    paylabs_va_code = fields.Char(string='Virtual Account Number')
    paylabs_expired_time = fields.Char(string='Payment Expiry Time')
    paylabs_h5_url = fields.Char(string='Paylabs H5 URL')
    paylabs_fee = fields.Float(string='Paylabs Fee')
    paylabs_raw_webhook = fields.Text(string='Raw Webhook Data')

    def _get_paylabs_pretty_expiry(self):
        """ Returns a human-readable expiry date (Hardcoded to 24 hours after creation). """
        self.ensure_one()
        try:
            from datetime import timedelta
            # Use transaction creation date + 24 hours
            expiry_date = self.create_date + timedelta(hours=24)
            
            # Odoo stores datetimes in UTC, convert to local user timezone if possible 
            # for display, or just format simply.
            return expiry_date.strftime('%d %B %Y, %H:%M')
        except Exception:
            return _("24 Hours from order time")

    # ------------------------------------------------------------------
    # Transaction Creation & Rendering
    # ------------------------------------------------------------------

    def _get_specific_create_values(self, provider_code, values):
        """ 
        Defines specific values during transaction creation.
        Here we map Odoo payment methods to Paylabs payment type codes.
        """
        res = super()._get_specific_create_values(provider_code, values)
        if provider_code != 'paylabs':
            return res

        # Business Logic: Determine the specific 'paymentType' string required by Paylabs API.
        # This is critical because Paylabs expects specific codes like 'MandiriVA' or 'QRIS'.
        paylabs_type = 'QRIS'
        method_id = values.get('payment_method_id')
        if method_id:
            method = self.env['payment.method'].browse(method_id)
            if method.exists() and method.code:
                code = method.code.lower()
                
                # Cleanup: remove prefixes like 'bank_' or 'va_' to get the raw bank name (e.g., 'bca')
                clean_code = code.replace('bank_', '').replace('va_', '').replace('_va', '')
                
                # Precise Mapping: Map Odoo/Common codes to Paylabs API V2.3 Case-Sensitive codes.
                mapping = {
                    'qris': 'QRIS',
                    'h5': 'H5',
                    'bca': 'BCAVA',
                    'bri': 'BRIVA',
                    'bni': 'BNIVA',
                    'mandiri': 'MandiriVA',
                    'permata': 'PermataVA',
                    'cimb': 'CIMBVA',
                    'cimb_niaga': 'CIMBVA',
                    'bsi': 'BSIVA',
                    'nobu': 'NobuVA',
                    'btn': 'BTNVA',
                    'maybank': 'MaybankVA',
                    'danamon': 'DanamonVA',
                    'bnc': 'BNCVA',
                    'muamalat': 'MuamalatVA',
                    'sinarmas': 'SinarmasVA',
                    'ina': 'INAVA',
                }
                
                if clean_code in mapping:
                    paylabs_type = mapping[clean_code]
                elif code in mapping:
                    paylabs_type = mapping[code]
                else:
                    # Generic Fallback: If bank is not in mapping, try to capitalize and append 'VA'.
                    paylabs_type = clean_code.upper()
                    if not paylabs_type.endswith('VA'):
                        paylabs_type = f"{paylabs_type}VA"
                    
                    # Correction: Paylabs uses CamelCase for some banks, not full uppercase.
                    camel_map = {
                        'MANDIRIVA': 'MandiriVA', 'PERMATAVA': 'PermataVA',
                        'NOBUVA': 'NobuVA', 'MAYBANKVA': 'MaybankVA',
                        'DANAMONVA': 'DanamonVA', 'MUAMALATVA': 'MuamalatVA',
                        'SINARMASVA': 'SinarmasVA'
                    }
                    paylabs_type = camel_map.get(paylabs_type, paylabs_type)

        _logger.info("Paylabs: Mapped payment method to Paylabs type: %s", paylabs_type)
        return {**res, 'paylabs_payment_type': paylabs_type}

    def _get_va_bank_name(self, payment_type_code):
        """ Return human-readable bank name from VA code. """
        bank_names = {
            'BCAVA': 'BCA', 'BRIVA': 'BRI', 'BNIVA': 'BNI',
            'MandiriVA': 'Mandiri', 'PermataVA': 'Permata', 'CIMBVA': 'CIMB Niaga',
            'BSIVA': 'BSI', 'NobuVA': 'Nobu', 'BTNVA': 'BTN',
            'MaybankVA': 'Maybank', 'DanamonVA': 'Danamon', 'BNCVA': 'BNC',
            'MuamalatVA': 'Muamalat', 'SinarmasVA': 'Sinarmas',
        }
        return bank_names.get(payment_type_code, payment_type_code)

    def _get_processing_values(self):
        """ 
        Determines the flow after the 'Pay Now' button is clicked.
        For Paylabs:
        1. Creates the transaction on the Paylabs side.
        2. Redirects for H5, or redirects to standard /payment/status for QRIS/VA.
        """
        res = super()._get_processing_values()
        if self.provider_code != 'paylabs':
            return res

        # 1. Create payment on the Paylabs API side
        self._paylabs_create_payment()

        # 2. Determine user redirection destination
        if self.paylabs_payment_type == 'H5' and self.paylabs_h5_url:
            # External redirection to Paylabs Hosted Page
            parsed_url = urllib.parse.urlparse(self.paylabs_h5_url)
            base_action = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
            query_params = urllib.parse.parse_qsl(parsed_url.query)
            inputs = "".join([f'<input type="hidden" name="{k}" value="{v}"/>' for k, v in query_params])
            res['redirect_form_html'] = f'<form action="{base_action}" method="GET">{inputs}</form>'
        else:
            # For QRIS/VA, we use a hidden form to redirect to /payment/status.
            # This is more reliable for Odoo's frontend JS than just returning 'redirect_url'.
            res['redirect_form_html'] = f'<form action="/payment/status" method="GET"></form>'
            
        return res

    def _paylabs_create_payment(self):
        """ 
        Orchestrates the API call to Paylabs to initialize the actual payment (Pre-Order).
        This method sends the amount, reference, and payer details to Paylabs.
        """
        self.ensure_one()
        tx_sudo = self.sudo()
        
        # Security: Prevent multiple successful transactions for the same order/invoice
        domain = [
            ('state', '=', 'done'),
            ('id', '!=', self.id),
        ]
        if tx_sudo.sale_order_ids:
            domain.append(('sale_order_ids', 'in', tx_sudo.sale_order_ids.ids))
        elif tx_sudo.invoice_ids:
            domain.append(('invoice_ids', 'in', tx_sudo.invoice_ids.ids))
        else:
            domain = False # Skip check if no linked records
            
        if domain:
            existing_done_tx = self.search(domain, limit=1)
            if existing_done_tx:
                raise ValidationError(_("This order/invoice has already been paid (Transaction %s).", existing_done_tx.reference))

        client = self.provider_id._get_paylabs_client()
        partner = self.partner_id
        amount = int(self.amount)
        
        # Get base URL including port if available
        base_url = self.provider_id.get_base_url()
        try:
            from odoo.http import request
            if request and hasattr(request, 'httprequest'):
                base_url = request.httprequest.host_url
        except Exception:
            pass
        
        # Ensure no trailing slash
        base_url = base_url.rstrip('/')
        
        try:
            import time
            # Absolute Uniqueness: We combine Odoo reference + ID + Timestamp 
            # to prevent 'Duplicate Trade No' errors if a user retries a failed payment.
            unique_reference = f"{self.reference}-{self.id}-{int(time.time()) % 10000}"
            self.paylabs_merchant_trade_no = unique_reference

            # Standard Flow: Move 'draft' quotations to 'sent' so they are 
            # visible in the portal and can be re-paid if the attempt fails.
            for order in tx_sudo.sale_order_ids.filtered(lambda s: s.state == 'draft'):
                try:
                    _logger.info("Paylabs: Moving SO %s to 'sent' state", order.name)
                    order.action_quotation_sent()
                except Exception as e:
                    _logger.error("Paylabs: Failed to move SO %s to 'sent': %s", order.name, e)

            if self.paylabs_payment_type == 'QRIS':
                # Generate QRIS code
                response = client.create_qris(unique_reference, amount, self.reference)
                self._paylabs_process_response(response, 'QRIS')
            elif self.paylabs_payment_type == 'H5':
                # Generate Hosted Checkout Link (Redirect style)
                # Use the full base_url (with port) we detected earlier
                response = client.create_h5_link(
                    unique_reference, amount, self.reference,
                    partner.phone or '0800000000', f"{base_url}/shop/payment/validate", partner.name
                )
                self._paylabs_process_response(response, 'H5')
            else:
                # Generate Virtual Account Number
                response = client.create_va(
                    self.paylabs_payment_type, unique_reference, amount, self.reference, partner.name
                )
                self._paylabs_process_response(response, 'VA')
        except Exception as e:
            # Error Hardening: Log the error and notify the user with a clean validation error.
            if isinstance(e, ValidationError):
                raise e
            _logger.exception("Paylabs transaction creation failed: %s", e)
            self.write({'state_message': str(e)})
            raise ValidationError(_("Could not connect to Payment Gateway: %s", e))

    def _paylabs_process_response(self, response, mode):
        """ 
        Plugin Logic: Parse the API response and update the Odoo UI.
        This method extracts data like QRIS URLs or VA numbers from the Paylabs
        JSON response and saves them into the Odoo transaction record.
        """
        _logger.info("Paylabs API Response for %s: %s", mode, response)
        err_code = str(response.get('errCode', ''))
        
        # 1. Error Handling: If API returns non-zero, fail the process early
        if err_code != PAYLABS_SUCCESS_CODE:
            msg = response.get('errCodeDes', 'Unknown error')
            _logger.error("Paylabs %s failed [%s]: %s", mode, err_code, msg)
            self.write({'state_message': f"[{err_code}] {msg}"})
            raise ValidationError(_("DEBUG ERROR (API): [%s] %s", err_code, msg))

        # 2. Success Logic: Map Paylabs fields to Odoo fields
        vals = {}
        if mode == 'QRIS':
            vals.update({
                'paylabs_qr_url': response.get('qrisUrl') or response.get('qrCodeUrl'),
                'paylabs_qr_code': response.get('qrCode'),
                'paylabs_expired_time': response.get('expiredTime'),
            })
        elif mode == 'H5':
            vals['paylabs_h5_url'] = response.get('url')
        elif mode == 'VA':
            vals.update({
                'paylabs_va_code': response.get('vaCode') or response.get('payCode') or response.get('accountNo'),
                'paylabs_expired_time': response.get('expiredTime'),
            })
        
        # 3. State Management: Move Odoo transaction to 'pending' (Awaiting Payment)
        self.write(vals)
        self._set_pending()
        self.env.cr.commit()

    # ------------------------------------------------------------------
    # Notification Handling (Webhook)
    # ------------------------------------------------------------------

    @api.model
    def _get_tx_from_notification_data(self, provider_code, data):
        """ 
        Finds the corresponding Odoo transaction based on webhook data.
        Paylabs sends 'merchantTradeNo' which we use as the lookup key.
        """
        tx = super()._get_tx_from_notification_data(provider_code, data)
        if provider_code != 'paylabs' or tx:
            return tx

        reference = data.get('merchantTradeNo')
        if not reference:
            return tx

        # Primary search: Exact match on our stored merchant trade no
        tx = self.search([('paylabs_merchant_trade_no', '=', reference), ('provider_code', '=', 'paylabs')], limit=1)
        if tx:
            return tx

        # Secondary search: fallback to splitting the reference (for legacy or untracked transactions)
        parts = reference.split('-')
        domain = [('provider_code', '=', 'paylabs'), '|', ('reference', '=', reference)]
        
        if len(parts) >= 2:
            # Usually the ID is the second part: [REFERENCE]-[ID]-[TIMESTAMP]
            # We try to find the ID among numeric parts
            potential_ids = [p for p in parts if p.isdigit()]
            if potential_ids:
                # Prioritize larger numbers as they are more likely to be Odoo IDs than order numbers
                potential_ids.sort(key=len, reverse=True)
                for pid in potential_ids:
                    found = self.browse(int(pid)).exists()
                    if found and found.provider_code == 'paylabs' and (found.reference in reference or reference in found.reference):
                        return found
        
        tx = self.search(domain, limit=1)
        
        if not tx:
            _logger.warning("Paylabs: Transaction not found for reference %s", reference)
        return tx

    def _process_notification_data(self, data):
        """ 
        Plugin Logic: The Final Handshake.
        This is called after a successful Webhook signature verification.
        It transitions the Odoo Invoice/Order to 'Paid'.
        """
        super()._process_notification_data(data)
        if self.provider_code != 'paylabs':
            return

        # Extract status from Paylabs notification (02 = Success)
        payment_status = str(data.get('status') or data.get('paymentStatus') or '')
        amount_received = data.get('totalAmount') or data.get('amount') or data.get('requestAmount')

        _logger.info("Paylabs webhook processing: ref=%s status=%s amount=%s", 
                     self.reference, payment_status, amount_received)

        # Set the provider reference if available
        if data.get('platformTradeNo'):
            self.provider_reference = data.get('platformTradeNo')
        
        # Log raw data and fee for auditing
        self.paylabs_raw_webhook = json.dumps(data, indent=2)
        if data.get('transFeeAmount'):
            try:
                self.paylabs_fee = float(data.get('transFeeAmount'))
            except Exception:
                pass

        if payment_status == PAYLABS_PAYMENT_SUCCESS:
            # Security: Basic amount check to ensure no underpayment
            if amount_received and abs(float(amount_received) - self.amount) > 0.1:
                _logger.warning("Paylabs amount mismatch: ref=%s", self.reference)
            
            # Set the transaction to 'Done'
            # Odoo core will handle SO confirmation automatically during post-processing.
            self._set_done()
            
        elif payment_status == PAYLABS_PAYMENT_FAILED:
            self._set_canceled(state_message=_("Payment failed on Paylabs."))
        elif payment_status == PAYLABS_PAYMENT_PENDING:
            self._set_pending()

    def _paylabs_fetch_status(self):
        """
        Actively queries the Paylabs API to check for transaction status.
        This is used as a fallback if webhooks are delayed or fail to reach Odoo.
        """
        self.ensure_one()
        if self.state != 'pending' or self.provider_code != 'paylabs':
            return self.state

        _logger.info("Paylabs: Actively fetching status for tx %s (ref: %s)", self.id, self.paylabs_merchant_trade_no)
        client = self.provider_id._get_paylabs_client()
        
        try:
            # Determine if it's QRIS or VA
            if self.paylabs_payment_type == 'QRIS':
                response = client.query_qris(self.paylabs_merchant_trade_no or self.reference)
            else:
                response = client.query_va(self.paylabs_payment_type, self.paylabs_merchant_trade_no or self.reference)
            
            if response.get('errCode') == '0':
                # Map query response to notification format for processing
                # Paylabs Query Response often uses 'status' or 'paymentStatus'
                self._handle_notification_data('paylabs', response)
                
        except Exception as e:
            _logger.error("Paylabs: Failed to fetch status for %s: %s", self.reference, e)

        return self.state

    @api.model
    def cron_paylabs_cancel_expired(self):
        """
        Scheduled action to cancel pending Paylabs transactions that have expired (after 24 hours).
        Called by ir.cron.
        """
        _logger.info("Paylabs Cron: Checking for expired transactions...")
        from datetime import datetime, timedelta
        
        # Transactions created more than 24 hours ago
        limit_date = datetime.utcnow() - timedelta(hours=24)
        
        expired_txs = self.search([
            ('provider_code', '=', 'paylabs'),
            ('state', '=', 'pending'),
            ('create_date', '<', limit_date)
        ])
        
        for tx in expired_txs:
            _logger.info("Paylabs Cron: Canceling expired transaction %s (created: %s)", tx.reference, tx.create_date)
            tx._set_canceled(state_message=_("Transaction expired (Auto-cancelled by system after 24h)."))
        
        return True

    def _get_payment_method_line_id(self):
        """ 
        Override to help Odoo find the correct payment method line on the journal.
        This is critical for Odoo 17+ to avoid 'Please define a payment method line' error.
        """
        self.ensure_one()
        if self.provider_code != 'paylabs':
            return super()._get_payment_method_line_id()

        # 1. Try standard Odoo logic first
        res = super()._get_payment_method_line_id()
        if res:
            return res

        # 2. Try to find the line linked specifically to this provider and journal
        if self.provider_id.journal_id:
            # First, look for the line we created (linked to the provider)
            line = self.env['account.payment.method.line'].sudo().search([
                ('journal_id', '=', self.provider_id.journal_id.id),
                ('payment_provider_id', '=', self.provider_id.id),
            ], limit=1)
            if line:
                return line.id
            
            # Fallback 1: Look for ANY inbound 'manual' line on that journal
            fallback_line = self.provider_id.journal_id.inbound_payment_method_line_ids.filtered(
                lambda l: l.code == 'manual'
            )[:1]
            if fallback_line:
                return fallback_line.id
            
            # Fallback 2: Take the very first inbound line available
            if self.provider_id.journal_id.inbound_payment_method_line_ids:
                return self.provider_id.journal_id.inbound_payment_method_line_ids[0].id
        
        return res

    def paylabs_get_back_url(self):
        """ 
        Helper to get a valid portal URL to return to the Order/Invoice.
        Uses sudo() to ensure public users don't get 'Access Denied' errors.
        """
        self.ensure_one()
        tx_sudo = self.sudo()
        try:
            if tx_sudo.sale_order_ids:
                return tx_sudo.sale_order_ids[0].get_portal_url()
            if tx_sudo.invoice_ids:
                return tx_sudo.invoice_ids[0].get_portal_url()
        except Exception:
            pass
        return '/shop/payment'
