# -*- coding: utf-8 -*-
{
    'name': "bsqmgmt1_mrp",
    'version': '1.0',
    'depends': ['mrp', 'mrp_workorder'],
    'author': 'Odoo Inc',
    'maintainer': 'Odoo Inc',
    'category': 'Manufacturing',
    'summary': "My client wants his manufacturing employees to be able to input the weight of the Produced Finished Product (FP) and also of the Components on their Tablet view. This way we can automate the data filling of the manufacturing order, minimizing communication errors between managers and manufacturers.",
    'description': """
Dynamic Finished Product Quantity
=================
- The goal here is to capture the done quantities of the Finished Product with that underlined field (FG) instead of the remaining quantities.
    - The same logic should be applied to the Components Consumed, meaning, the underlined Comp field should reflect the amount of components consumed by this work order.
- This should be enough for us to change automatically the amount of raw materials consumed that was sent into Virtual Locations/My Company:Production and of finished products produced into our WH/Stock, or whatever location the operation type specifies
- Additionally, we would like to link this qty_done with x_studio_end_weight_lbs. So the first one captured on the work order, should also filled the latter with that amount.
    - The same logic should be applied to quantity_done with x_studio_source_weight_lbs.
    - The field x_studio_yields should be the division between both fields (x_studio_end_weight_lbs / x_studio_source_weight_lbs)
""",
    'data': [
        'views/views.xml',
    ]
}