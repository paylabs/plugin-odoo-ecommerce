# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    """
    This model extends payment.provider to integrate Paylabs.
    It stores API credentials and payment method configurations.
    """
    # 1. Identification: Add 'paylabs' as a valid payment provider code in Odoo's core selection.
    # ondelete='set default' ensures that if the module is uninstalled, existing records don't break.
    code = fields.Selection(
        selection_add=[('paylabs', 'Paylabs')],
        ondelete={'paylabs': 'set default'},
    )

    # 2. Credentials: Store RSA keys and Merchant ID securely.
    # groups='base.group_system' ensures only administrators can see these sensitive keys.
    paylabs_merchant_id = fields.Char(
        string='Merchant ID (X-PARTNER-ID)',
        help='The unique Partner ID assigned to you by Paylabs.',
        required_if_provider='paylabs',
        groups='base.group_system',
    )
    paylabs_private_key = fields.Text(
        string='RSA Private Key (Merchant)',
        help='Your RSA Private Key used to sign outgoing requests. Keep this secret!',
        required_if_provider='paylabs',
        groups='base.group_system',
    )
    paylabs_public_key = fields.Text(
        string='RSA Public Key (Paylabs)',
        help='Paylabs RSA Public Key used to verify signatures in incoming webhooks.',
        required_if_provider='paylabs',
        groups='base.group_system',
    )
    
    paylabs_notify_url = fields.Char(
        string='Webhook Notify URL',
        help='The endpoint where Paylabs will send payment status updates.',
    )

    # 3. Compatibility & Legacy: Store these to avoid XML errors even if not used in logic.
    paylabs_enable_qris = fields.Boolean(string='Enable QRIS', default=True)
    paylabs_va_banks = fields.Char(string='VA Banks', help='Comma separated VA bank codes.')

    # ------------------------------------------------------------------
    # Helper Methods
    # ------------------------------------------------------------------

    def _get_paylabs_api_mode(self):
        """ Determines whether to use sandbox or production based on provider state. """
        self.ensure_one()
        return 'production' if self.state == 'enabled' else 'sandbox'

    @api.model_create_multi
    def create(self, vals_list):
        """ Override create to ensure payment method lines on initial creation. """
        providers = super().create(vals_list)
        for provider in providers:
            if provider.code == 'paylabs' and provider.journal_id:
                provider._ensure_paylabs_payment_method_lines()
        return providers

    def write(self, vals):
        """ 
        Override write to automatically create payment method lines on the journal.
        This is a CRITICAL fix for Odoo 17/18 which requires a payment method line 
        on the journal for every payment method supported by the provider.
        """
        res = super().write(vals)
        # Prevent infinite recursion when _ensure_paylabs_payment_method_lines calls write
        if not self.env.context.get('skip_paylabs_ensure_methods'):
            if 'journal_id' in vals or 'payment_method_ids' in vals or 'state' in vals:
                self._ensure_paylabs_payment_method_lines()
        return res

    def _ensure_paylabs_payment_method_lines(self):
        """
        Ensures that the provider's journal has the necessary payment method lines
        AND ensures that the payment methods themselves are active and correctly linked.
        This version is ULTRA-AGGRESSIVE to fix existing duplicate data:
        1. Strips 'Paylabs - ' prefix from all linked payment methods.
        2. Ensures ONLY ONE method per code is active and linked.
        3. Deactivates any other methods with the same code to prevent duplication.
        """
        for provider in self.filtered(lambda p: p.code == 'paylabs'):
            # 1. Identify all codes we support
            supported_codes = [
                'qris', 'h5', 'bca', 'bri', 'bni', 'mandiri', 'permata', 
                'cimb_niaga', 'bsi', 'btn', 'danamon', 'maybank', 'nobu',
                'bnc', 'muamalat', 'sinarmas'
            ]
            
            # 2. Find all methods that might conflict
            all_methods = self.env['payment.method'].sudo().search([
                '|', ('code', 'in', supported_codes), ('name', 'ilike', 'Paylabs')
            ])
            
            methods_to_link = self.env['payment.method']
            methods_to_deactivate = self.env['payment.method']
            
            for code in supported_codes:
                methods_for_code = all_methods.filtered(lambda m: m.code == code)
                if not methods_for_code:
                    continue
                
                # Selection logic:
                # a. Prefer the record with our XML ID (payment_paylabs.payment_method_paylabs_...)
                # b. Otherwise prefer one already linked to this provider
                # c. Otherwise take the one with the shortest name (likely standard)
                our_method = methods_for_code.filtered(lambda m: 'payment_paylabs' in (m.get_external_id().get(m.id) or ''))
                if our_method:
                    best = our_method[0]
                else:
                    linked = methods_for_code.filtered(lambda m: provider.id in m.provider_ids.ids)
                    if linked:
                        best = linked[0]
                    else:
                        best = sorted(methods_for_code, key=lambda m: len(m.name or ''))[0]
                
                methods_to_link |= best
                # All other methods for this code should be DEACTIVATED and UNLINKED
                others = methods_for_code - best
                methods_to_deactivate |= others

            # 3. Data Cleanup & Deduplication
            for method in all_methods:
                # Cleanup names for EVERYTHING we found
                if method.name and (method.name.startswith('Paylabs - ') or method.name.startswith('Paylabs ')):
                    new_name = method.name.replace('Paylabs - ', '').replace('Paylabs ', '')
                    if method.name != new_name:
                        method.write({'name': new_name})
                
                # If it's in our deactivate list, make sure it's inactive and unlinked
                if method in methods_to_deactivate:
                    method.write({'active': False})
                    if provider.id in method.provider_ids.ids:
                        method.write({'provider_ids': [(3, provider.id)]})

            # 4. Update provider.payment_method_ids
            # Ensure ONLY the 'best' methods are linked. 
            # (6, 0, ids) is the safest way to reset the list to exactly what we want.
            provider.sudo().with_context(skip_paylabs_ensure_methods=True).write({
                'payment_method_ids': [(6, 0, methods_to_link.ids)]
            })
            
            # Force flush
            provider.flush_recordset(['state', 'payment_method_ids'])

            # 5. Prepare activation values
            manual_inbound = self.env['account.payment.method'].sudo().search([
                ('code', '=', 'manual'), ('payment_type', '=', 'inbound')
            ], limit=1)
            if not manual_inbound:
                manual_inbound = self.env['account.payment.method'].sudo().search([
                    ('payment_type', '=', 'inbound')
                ], order='id asc', limit=1)

            idr_currency = self.env['res.currency'].sudo().search([('name', '=', 'IDR')], limit=1)
            indonesia_country = self.env['res.country'].sudo().search([('code', '=', 'ID')], limit=1)

            if provider.state in ['test', 'enabled']:
                # Activate our chosen methods and restrict them to IDR/Indonesia
                method_vals = {
                    'active': True,
                    'primary_payment_method_id': manual_inbound.id if manual_inbound else False
                }
                if idr_currency:
                    method_vals['supported_currency_ids'] = [(6, 0, idr_currency.ids)]
                if indonesia_country:
                    method_vals['supported_country_ids'] = [(6, 0, indonesia_country.ids)]
                
                methods_to_link.write(method_vals)

            # 6. Ensure Journal Lines (for Odoo 17/18 accounting)
            if not provider.journal_id:
                continue

            if manual_inbound:
                # Remove ALL existing Paylabs journal lines for this journal to start fresh
                # This is the cleanest way to fix messed up names.
                existing_lines = self.env['account.payment.method.line'].sudo().search([
                    ('journal_id', '=', provider.journal_id.id),
                    ('payment_provider_id', '=', provider.id),
                ])
                existing_lines.unlink()

                for method in methods_to_link:
                    # Naming for Journal Lines: Keep 'Paylabs' prefix for internal clarity
                    line_name = f"Paylabs {method.name}"
                    self.env['account.payment.method.line'].sudo().create({
                        'name': line_name,
                        'payment_method_id': manual_inbound.id,
                        'journal_id': provider.journal_id.id,
                        'payment_provider_id': provider.id,
                    })




        
    def _get_paylabs_notify_url(self):
        """ 
        Computes the target URL for Paylabs webhooks.
        The URL must be accessible to Paylabs' servers. 
        It appends the database name (?db=...) to ensure the notification 
        reaches the correct Odoo instance in multi-tenant setups.
        """
        self.ensure_one()
        # If a manual override is provided in the configuration, use it.
        if self.paylabs_notify_url:
            return self.paylabs_notify_url
        
        # Determine the base URL from the request or system parameters.
        try:
            from odoo.http import request
            base_url = request.httprequest.host_url.rstrip('/')
        except Exception:
            # Fallback to the web.base.url system parameter if no request context exists.
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url').rstrip('/')
            
        url = f"{base_url}/payment/paylabs/webhook"
        
        # Multi-database support: ensure Paylabs knows which DB to notify.
        if self.env.cr.dbname:
            connector = '&' if '?' in url else '?'
            url = f"{url}{connector}db={self.env.cr.dbname}"
            
        return url

    def _get_paylabs_client(self):
        """ 
        Instantiates the PaylabsApiClient helper.
        This client handles all the heavy lifting of RSA signing and HTTP requests.
        """
        self.ensure_one()
        from ..utils.api_client import PaylabsApiClient
        return PaylabsApiClient(
            merchant_id=(self.paylabs_merchant_id or '').strip(),
            private_key=(self.paylabs_private_key or '').strip(),
            mode=self._get_paylabs_api_mode(),
            notify_url=self._get_paylabs_notify_url(),
        )

    def _get_supported_currencies(self):
        """ 
        Plugin Logic: Paylabs only operates in IDR.
        This override ensures that Paylabs will NOT be visible on the checkout page
        if the customer's current currency is anything other than Rupiah.
        """
        supported_currencies = super()._get_supported_currencies()
        if self.code == 'paylabs':
            return self.env['res.currency'].search([('name', '=', 'IDR')])
        return supported_currencies

    def _compute_feature_support_fields(self):
        super()._compute_feature_support_fields()
        for provider in self.filtered(lambda p: p.code == 'paylabs'):
            if hasattr(provider, 'support_authorization'):
                provider.support_authorization = False
            if hasattr(provider, 'support_tokenization'):
                provider.support_tokenization = False
            if hasattr(provider, 'support_refund'):
                provider.support_refund = 'none'
            if hasattr(provider, 'support_manual_capture'):
                provider.support_manual_capture = False

    @api.constrains('paylabs_merchant_id', 'paylabs_private_key')
    def _check_paylabs_credentials(self):
        for provider in self.filtered(lambda p: p.code == 'paylabs'):
            if not provider.paylabs_merchant_id or not provider.paylabs_private_key:
                from odoo.exceptions import ValidationError
                raise ValidationError(_("Paylabs credentials are required."))

