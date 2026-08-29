from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    hs_code = fields.Char(
        'HS 编码',
        help='海关商品编码（Harmonized System Code），用于装箱单/报关单草单自动带出。')
