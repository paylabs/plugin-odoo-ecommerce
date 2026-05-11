# -*- coding: utf-8 -*-
from . import controllers
from . import models

def post_init_hook(env):
    """Set default values after module installation."""
    
    # 1. Link provider to module_id for website visibility
    module = env['ir.module.module'].search([('name', '=', 'payment_paylabs')], limit=1)
    provider = env['payment.provider'].search([('code', '=', 'paylabs')], limit=1)
    
    # 2. Activate IDR Currency and Link to Provider
    idr_currency = env['res.currency'].search([('name', '=', 'IDR')], limit=1)
    if idr_currency:
        idr_currency.active = True
        if provider:
            vals = {
                'module_id': module.id if module else False,
                'is_published': True,
            }
            if 'supported_currency_ids' in env['payment.provider']._fields:
                vals['supported_currency_ids'] = [(4, idr_currency.id)]
            provider.write(vals)

            # 3. Link and Activate Payment Methods
            supported_codes = [
                'qris', 'h5', 'bca', 'bri', 'bni', 'mandiri', 'permata', 
                'cimb_niaga', 'bsi', 'btn', 'danamon', 'maybank', 'nobu',
                'bnc', 'muamalat', 'sinarmas'
            ]
            methods = env['payment.method'].search([('code', 'in', supported_codes)])
            if methods:
                # Use filtered to pick the best method per code to avoid 'double'
                methods_to_link = env['payment.method']
                for code in supported_codes:
                    methods_for_code = methods.filtered(lambda m: m.code == code)
                    best_method = methods_for_code.filtered(lambda m: 'paylabs' in (m.name or '').lower())
                    if best_method:
                        methods_to_link |= best_method[0]
                    elif methods_for_code:
                        methods_to_link |= methods_for_code[0]
                
                provider.write({'payment_method_ids': [(6, 0, methods_to_link.ids)]})
                methods_to_link.write({'active': True})
                if 'supported_currency_ids' in env['payment.method']._fields:
                    methods_to_link.write({'supported_currency_ids': [(4, idr_currency.id)]})

                # 4. Link Payment Methods to Account Payment Methods (Odoo 17+ requirement)
                manual_inbound = env['account.payment.method'].search([
                    ('code', '=', 'manual'), ('payment_type', '=', 'inbound')
                ], limit=1)
                if not manual_inbound:
                    manual_inbound = env['account.payment.method'].search([
                        ('payment_type', '=', 'inbound')
                    ], limit=1)
                
                if manual_inbound:
                    methods_to_link.write({'primary_payment_method_id': manual_inbound.id})


                    # 5. Create Payment Method Line on Journal
                    # Required so Odoo knows which journal line to use when creating account.payment
                    if provider.journal_id:
                        existing_line = env['account.payment.method.line'].search([
                            ('journal_id', '=', provider.journal_id.id),
                            ('payment_provider_id', '=', provider.id)
                        ], limit=1)
                        if not existing_line:
                            env['account.payment.method.line'].create({
                                'name': 'Paylabs',
                                'payment_method_id': manual_inbound.id,
                                'journal_id': provider.journal_id.id,
                                'payment_provider_id': provider.id,
                            })
