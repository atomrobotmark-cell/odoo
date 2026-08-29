import random
import base64
from odoo import models, fields, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # ===== 交单阶段追踪 =====
    doc_submit_method = fields.Selection([
        ('lc', 'L/C 信用证'),
        ('tt', 'T/T 电汇'),
        ('dp', 'D/P 付款交单'),
        ('da', 'D/A 承兑交单'),
        ('other', '其他'),
    ], string='交单方式', default='tt', tracking=True, copy=False)

    doc_submit_stage = fields.Selection([
        ('none', '未开始'),
        ('preparing', '单据准备中'),
        ('ready', '待交单'),
        ('submitted', '已交单'),
    ], string='交单阶段', default='none', tracking=True, copy=False)

    doc_submit_date = fields.Date(string='交单日期', tracking=True, copy=False)
    doc_submit_note = fields.Text(string='交单备注', copy=False)

    # ===== 单据清单（勾选） =====
    doc_commercial_invoice = fields.Boolean('商业发票', default=True)
    doc_packing_list = fields.Boolean('装箱单', default=True)
    doc_bill_of_lading = fields.Boolean('提单 B/L')
    doc_cert_origin = fields.Boolean('产地证')
    doc_insurance = fields.Boolean('保险单')
    doc_customs_draft = fields.Boolean('报关单草单', default=True)
    doc_shipping_mark = fields.Boolean('唛头', default=True)

    # ===== 唛头 =====
    shipping_mark = fields.Text(
        '唛头内容',
        help='直接输入唛头文字（支持换行）；留空则按默认模板自动生成。')
    shipping_mark_project = fields.Char(
        '项目代号',
        help='唛头主题用的项目代号，打印唛头前填写（输出时提供）。')
    shipping_mark_code = fields.Char(
        '唛头随机编号', compute='_compute_shipping_mark_code', store=True,
        readonly=False,
        help='系统自动生成的 6 位编号，与项目代号、国家组合成唛头主题。')
    invoice_no = fields.Char(
        '发票号', compute='_compute_invoice_no', store=False,
        help='由本销售订单关联的商业发票自动带出。')

    # ===== 报关草单补充信息 =====
    incoterm_id = fields.Many2one('account.incoterms', 'Incoterm',
                                   help='国际贸易术语（如 CIF、FOB），用于商业发票与报关草单。')
    customs_trans_mode = fields.Char('运输方式', default='海运')
    customs_trade_mode = fields.Char('监管方式', default='一般贸易')
    customs_dest_country = fields.Char('运抵国(地区)')
    customs_port = fields.Char('指运港')
    customs_contract_no = fields.Char('合同协议号')
    customs_package_type = fields.Char('包装种类', default='纸箱')

    # ===== 报关草单 标准草单表头字段 =====
    customs_prelim_no = fields.Char('预录入编号')
    customs_no = fields.Char('海关编号')
    customs_export_port = fields.Char('出口口岸')
    customs_filing_no = fields.Char('备案号')
    customs_export_date = fields.Date('出口日期')
    customs_declaration_date = fields.Date('申报日期')
    customs_consignor = fields.Char(
        '经营单位/发货单位',
        help='报关草单「经营单位」「发货单位」栏；按本单实际填，默认留空时取公司名。')
    customs_conveyance = fields.Char('运输工具名称')
    customs_bl_no = fields.Char('提运单号')
    customs_levy_nature = fields.Char('征免性质')
    customs_settlement = fields.Char('结汇方式', default='T/T')
    customs_license_no = fields.Char('许可证号')
    customs_domestic_source = fields.Char('境内货源地', default='无锡其他')
    customs_approval_no = fields.Char('批准文号')
    customs_freight = fields.Char('运费', help='如 USD 500 / 率值，按报关格式填写')
    customs_insurance = fields.Char('保费')
    customs_extras = fields.Char('杂费')
    customs_container_no = fields.Char('集装箱号')
    customs_attached_docs = fields.Char('随附单据')
    customs_manufacturer = fields.Char('生产厂家')
    customs_marks_remark = fields.Text('标记唛码及备注')

    # ===== 装箱单 箱级数据（手填，优先于按产品重量自动估算）=====
    pl_total_packages = fields.Integer(
        '总件数', help='装箱单用：总包装件数；留空则按订单行数估算。')
    pl_gross_weight = fields.Float(
        '总毛重 (KGS)', help='装箱单用：总毛重；留空则按产品重量自动估算。')
    pl_net_weight = fields.Float(
        '总净重 (KGS)', help='装箱单用：总净重；留空则按产品重量自动估算。')
    pl_volume = fields.Float(
        '总体积 (CBM)', help='装箱单用：总体积；留空则按产品体积自动估算。')

    @api.depends('name')
    def _compute_shipping_mark_code(self):
        for o in self:
            if not o.shipping_mark_code:
                o.shipping_mark_code = ''.join(
                    random.choice('0123456789') for _ in range(6))

    @api.depends('invoice_ids')
    def _compute_invoice_no(self):
        for o in self:
            out = o.invoice_ids.filtered(
                lambda m: m.move_type == 'out_invoice')
            o.invoice_no = ' / '.join(out.mapped('name')) if out else ''

    def action_doc_submit(self):
        """一键标记已交单并记录当天日期。"""
        self.write({
            'doc_submit_stage': 'submitted',
            'doc_submit_date': fields.Date.context_today(self),
        })

    def action_open_fill_wizard(self):
        """从销售订单打开「填制装箱单 / 报关草单」向导页。"""
        return {
            'name': '填制装箱单 / 报关草单',
            'type': 'ir.actions.act_window',
            'res_model': 'export.doc.fill.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
                'active_id': self.id,
            },
        }

    # ===== 报表预览（新标签页打开 HTML，不直接下载）=====
    def _preview_report(self, report_name):
        """在新标签页打开报表的 HTML 渲染版（预览，不下载）。"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/report/html/{report_name}/{self.id}',
            'target': 'new',
        }

    def action_preview_invoice(self):
        return self._preview_report('export_doc_tracker.report_commercial_invoice')

    def action_preview_packing(self):
        return self._preview_report('export_doc_tracker.report_packing_list')

    def action_preview_customs(self):
        return self._preview_report('export_doc_tracker.report_customs_draft')

    def action_preview_mark(self):
        return self._preview_report('export_doc_tracker.report_shipping_mark')

    # ===== 一键邮件发送（预填撰写窗 + 4 份 PDF 附件）=====
    def action_send_docs(self):
        """生成 4 份单证 PDF 作为附件，打开已预填收件人/正文的邮件撰写窗。"""
        self.ensure_one()
        specs = [
            ('export_doc_tracker.action_report_commercial_invoice', 'Commercial Invoice'),
            ('export_doc_tracker.action_report_packing_list', 'Packing List'),
            ('export_doc_tracker.action_report_customs_draft', 'Customs Draft'),
            ('export_doc_tracker.action_report_shipping_mark', 'Shipping Mark'),
        ]
        att_ids = []
        for xmlid, label in specs:
            pdf, _ = self.env['ir.actions.report']._render_qweb_pdf(
                xmlid, res_ids=[self.id])
            att = self.env['ir.attachment'].create({
                'name': f'{label} - {self.name}.pdf',
                'type': 'binary',
                'datas': base64.b64encode(pdf),
                'res_model': 'sale.order',
                'res_id': self.id,
                'mimetype': 'application/pdf',
            })
            att_ids.append(att.id)

        partner_ids = self.partner_id.ids
        partner_email = self.partner_id.email
        subject = f'Export Documents - {self.name} ({self.partner_id.name or ""})'
        body = ('<p>Dear %s,</p>'
                '<p>Please find attached the export documents for your order <strong>%s</strong>.</p>'
                '<p>Best regards,<br/>%s</p>') % (
            (self.partner_id.name or ''), self.name, (self.env.company.name or ''))
        ctx = {
            'default_model': 'sale.order',
            'default_res_id': self.id,
            'default_partner_ids': [(6, 0, partner_ids)],
            'default_attachment_ids': [(6, 0, att_ids)],
            'default_use_template': False,
            'default_composition_mode': 'comment',
            'default_subject': subject,
            'default_body': body,
        }
        if not partner_email:
            ctx['default_body'] = ('<p><b>[提醒] 当前客户(%s)未填写邮箱，请手动添加收件人后再发送。</b></p>'
                                   % (self.partner_id.name or '未知')) + body
        return {
            'type': 'ir.actions.act_window',
            'name': '发送出口单证',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'target': 'new',
            'context': ctx,
        }
