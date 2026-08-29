{
    'name': 'Export Doc Tracker / 出口交单追踪与单证',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': '销售订单交单阶段追踪 + 装箱单/商业发票/报关草单/唛头生成',
    'description': """
在销售订单上追踪出口交单流程（交单方式、交单阶段状态条、交单日期、单据清单勾选），
并提供四种外贸单证的 PDF 生成：装箱单、商业发票、报关单草单、唛头。
""",
    'author': 'WorkBuddy',
    'website': 'https://www.workbuddy.cn',
    'depends': ['sale', 'sale_stock', 'stock', 'account'],
    'data': [
        'security/export_doc_security.xml',
        'views/sale_order_views.xml',
        'views/export_doc_wizard_views.xml',
        'reports/commercial_invoice.xml',
        'reports/packing_list.xml',
        'reports/customs_draft.xml',
        'reports/shipping_mark.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
