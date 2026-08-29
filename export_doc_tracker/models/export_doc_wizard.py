from odoo import models, fields, api


class ExportDocFillWizard(models.TransientModel):
    _name = 'export.doc.fill.wizard'
    _description = '填制装箱单 / 报关草单'

    sale_order_id = fields.Many2one('sale.order', string='销售订单', required=True)

    # ===== 报关草单 表头信息 =====
    incoterm_id = fields.Many2one('account.incoterms', 'Incoterm')
    customs_trans_mode = fields.Char('运输方式')
    customs_trade_mode = fields.Char('监管方式')
    customs_dest_country = fields.Char('运抵国(地区)')
    customs_port = fields.Char('指运港')
    customs_contract_no = fields.Char('合同协议号')
    customs_package_type = fields.Char('包装种类')

    # ===== 报关草单 标准草单表头字段 =====
    customs_prelim_no = fields.Char('预录入编号')
    customs_no = fields.Char('海关编号')
    customs_export_port = fields.Char('出口口岸')
    customs_filing_no = fields.Char('备案号')
    customs_export_date = fields.Date('出口日期')
    customs_declaration_date = fields.Date('申报日期')
    customs_consignor = fields.Char('经营单位/发货单位')
    customs_conveyance = fields.Char('运输工具名称')
    customs_bl_no = fields.Char('提运单号')
    customs_levy_nature = fields.Char('征免性质')
    customs_settlement = fields.Char('结汇方式')
    customs_license_no = fields.Char('许可证号')
    customs_domestic_source = fields.Char('境内货源地')
    customs_approval_no = fields.Char('批准文号')
    customs_freight = fields.Char('运费')
    customs_insurance = fields.Char('保费')
    customs_extras = fields.Char('杂费')
    customs_container_no = fields.Char('集装箱号')
    customs_attached_docs = fields.Char('随附单据')
    customs_manufacturer = fields.Char('生产厂家')
    customs_marks_remark = fields.Text('标记唛码及备注')

    # ===== 装箱单 箱级数据（手填，优先于自动估算）=====
    pl_total_packages = fields.Integer('总件数')
    pl_gross_weight = fields.Float('总毛重 (KGS)')
    pl_net_weight = fields.Float('总净重 (KGS)')
    pl_volume = fields.Float('总体积 (CBM)')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        so_id = self.env.context.get('active_id')
        if so_id:
            so = self.env['sale.order'].browse(so_id)
            if so.exists():
                res.update({
                    'sale_order_id': so.id,
                    'incoterm_id': so.incoterm_id.id,
                    'customs_trans_mode': so.customs_trans_mode,
                    'customs_trade_mode': so.customs_trade_mode,
                    'customs_dest_country': so.customs_dest_country,
                    'customs_port': so.customs_port,
                    'customs_contract_no': so.customs_contract_no,
                    'customs_package_type': so.customs_package_type,
                    'customs_prelim_no': so.customs_prelim_no,
                    'customs_no': so.customs_no,
                    'customs_export_port': so.customs_export_port,
                    'customs_filing_no': so.customs_filing_no,
                    'customs_export_date': so.customs_export_date,
                    'customs_declaration_date': so.customs_declaration_date,
                    'customs_consignor': so.customs_consignor,
                    'customs_conveyance': so.customs_conveyance,
                    'customs_bl_no': so.customs_bl_no,
                    'customs_levy_nature': so.customs_levy_nature,
                    'customs_settlement': so.customs_settlement,
                    'customs_license_no': so.customs_license_no,
                    'customs_domestic_source': so.customs_domestic_source,
                    'customs_approval_no': so.customs_approval_no,
                    'customs_freight': so.customs_freight,
                    'customs_insurance': so.customs_insurance,
                    'customs_extras': so.customs_extras,
                    'customs_container_no': so.customs_container_no,
                    'customs_attached_docs': so.customs_attached_docs,
                    'customs_manufacturer': so.customs_manufacturer,
                    'customs_marks_remark': so.customs_marks_remark,
                    'pl_total_packages': so.pl_total_packages,
                    'pl_gross_weight': so.pl_gross_weight,
                    'pl_net_weight': so.pl_net_weight,
                    'pl_volume': so.pl_volume,
                })
        return res

    def _save_to_so(self):
        self.sale_order_id.write({
            'incoterm_id': self.incoterm_id.id,
            'customs_trans_mode': self.customs_trans_mode,
            'customs_trade_mode': self.customs_trade_mode,
            'customs_dest_country': self.customs_dest_country,
            'customs_port': self.customs_port,
            'customs_contract_no': self.customs_contract_no,
            'customs_package_type': self.customs_package_type,
            'customs_prelim_no': self.customs_prelim_no,
            'customs_no': self.customs_no,
            'customs_export_port': self.customs_export_port,
            'customs_filing_no': self.customs_filing_no,
            'customs_export_date': self.customs_export_date,
            'customs_declaration_date': self.customs_declaration_date,
            'customs_consignor': self.customs_consignor,
            'customs_conveyance': self.customs_conveyance,
            'customs_bl_no': self.customs_bl_no,
            'customs_levy_nature': self.customs_levy_nature,
            'customs_settlement': self.customs_settlement,
            'customs_license_no': self.customs_license_no,
            'customs_domestic_source': self.customs_domestic_source,
            'customs_approval_no': self.customs_approval_no,
            'customs_freight': self.customs_freight,
            'customs_insurance': self.customs_insurance,
            'customs_extras': self.customs_extras,
            'customs_container_no': self.customs_container_no,
            'customs_attached_docs': self.customs_attached_docs,
            'customs_manufacturer': self.customs_manufacturer,
            'customs_marks_remark': self.customs_marks_remark,
            'pl_total_packages': self.pl_total_packages,
            'pl_gross_weight': self.pl_gross_weight,
            'pl_net_weight': self.pl_net_weight,
            'pl_volume': self.pl_volume,
        })

    def action_preview_packing(self):
        self._save_to_so()
        return self.env.ref('export_doc_tracker.action_report_packing_list').report_action(self.sale_order_id)

    def action_preview_customs(self):
        self._save_to_so()
        return self.env.ref('export_doc_tracker.action_report_customs_draft').report_action(self.sale_order_id)
