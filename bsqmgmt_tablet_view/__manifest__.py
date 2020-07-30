# -*- coding: utf-8 -*-
{
    'name': "BSQMGMT Tablet View Customization",

    'summary': """View Weight Customization""",

    'description': """
        [2217789]
        """,

    'author': 'Odoo',
    'website': 'https://www.odoo.com/',

    'category': 'Custom Development',
    'version': '1.0',
    'license': 'OEEL-1',

    # any module necessary for this one to work correctly
    'depends': ['mrp', 'mrp_workorder'],

    # always loaded
    'data': [
        'views/mrp_production_views.xml',
        'views/mrp_workorder_views.xml',
        # 'views/product_views.xml'
    ],
    # only loaded in demonstration mode
    'demo': [],
    'application': False,
}
