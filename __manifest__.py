# -*- coding: utf-8 -*-
{
    'name': 'Payment Provider: Paylabs',
    'version': '1.0.0',
    'category': 'Accounting/Payment',
    'sequence': 350,
    'summary': 'Payment gateway integration with Paylabs (QRIS, Virtual Account)',
    'description': """
Paylabs Payment Gateway Integration
=====================================
Supports:
- QRIS (QR Code Indonesian Standard)
- Virtual Account: BCA, BRI, BNI, Mandiri, Permata, CIMB, BSI, Nobu, BTN, Maybank, Danamon, BNC, Muamalat, Sinarmas

Based on Paylabs API v2.3
Docs: https://docs.paylabs.co.id
    """,
    'author': 'Paylabs',
    'website': 'https://paylabs.co.id',
    'license': 'LGPL-3',
    'depends': ['payment', 'account', 'sale', 'website'],
    'data': [
        'security/ir.model.access.csv',
        'views/payment_provider_views.xml',
        'views/payment_paylabs_templates.xml',
        'views/account_move_views.xml',
        'views/sale_order_views.xml',
        'views/sale_portal_templates.xml',
        'data/ir_cron_data.xml',
        'data/payment_method_data.xml',
        'data/payment_provider_data.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'payment_paylabs/static/src/css/payment_paylabs.css',
            'payment_paylabs/static/src/js/payment_form.js',
        ],
    },
    'images': ['static/description/icon.png'],
    'installable': True,
    'auto_install': False,
    'application': False,
    'post_init_hook': 'post_init_hook',
}
