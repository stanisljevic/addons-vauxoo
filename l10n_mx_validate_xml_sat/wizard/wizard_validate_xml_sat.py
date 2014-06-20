# -*- encoding: utf-8 -*-
###########################################################################
#    Module Writen to OpenERP, Open Source Management Solution
#
#    Copyright (c) 2014 Vauxoo - http://www.vauxoo.com/
#    All Rights Reserved.
#    info Vauxoo (info@vauxoo.com)
############################################################################
#    Coded by: Luis Torres (luis_t@vauxoo.com)
############################################################################
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from openerp.osv import osv, fields
from tools.translate import _
import decimal_precision as dp
import base64
from suds.client import Client
try:
    import xmltodict
except:
    _logger.error('Execute "sudo pip install xmltodict" to use l10n_mx_facturae_report module.')
    
class wizard_validate_uuid_sat(osv.osv_memory):
    _name = 'wizard.validate.uuid.sat'
    
    def default_get(self, cr, uid, fields, context=None):
        res = super(wizard_validate_uuid_sat, self).default_get(cr, uid, fields, context=context)
        ir_att_obj = self.pool.get('ir.attachment.facturae.mx')
        attachments = ir_att_obj.search(cr, uid, [('id_source', 'in', context['active_ids'])], context=context)
        list_xml = []
        for att in ir_att_obj.browse(cr, uid, attachments, context):
            if att.file_xml_sign:
                data_xml = base64.decodestring(att.file_xml_sign.datas)
                dict_data = dict(xmltodict.parse(data_xml).get('cfdi:Comprobante', {}))
                complemento = dict_data.get('cfdi:Complemento', {})
                emitter = dict_data.get('cfdi:Emisor', {})
                receiver = dict_data.get('cfdi:Receptor', {})
                list_xml.append([0, False, {
                    'name': att.file_xml_sign.name,
                    'amount': float(dict_data.get('@total', 0.0)), 
                    'number': dict_data.get('@folio', ''), 
                    'type': dict_data.get('@tipoDeComprobante', ''), 
                    'uuid': complemento.get('tfd:TimbreFiscalDigital', {}).get('@UUID', ''), 
                    'date_time': dict_data.get('@fecha', ''), 
                    'file_xml': att.file_xml_sign.id,
                    'vat_emitter': emitter.get('@rfc', ''), 
                    'vat_receiver': receiver.get('@rfc', ''), }])
        res.update({'xml_ids': list_xml})
        return res
    
    _columns = {
        'name': fields.char('Wizard name', readonly=True, size=64),
        'xml_ids': fields.many2many('xml.to.validate.line', 'wizard_xml_to_validate', 'wizard_id',
            'xml_id', 'XMLs to validate', help='XMLs to validate the uuid in the SAT'),
    }
    
    def check_uuid_dat(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        data = self.browse(cr, uid, ids[0], context=context)
        for xml in data.xml_ids:
            url = 'https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc?wsdl'
            client = Client(url)
            result = client.service.Consulta(""""?re=%s&rr=%s&tt=%s&id=%s""" % (xml.vat_emitter\
                or '', xml.vat_receiver or '', xml.amount or 0.0, xml.uuid or ''))
            result = result and result['Estado'] or ''
            xml.write({'result': result})
        return {
            'name':_("Validate Invoice UUID SAT"),
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
            'res_model': 'wizard.validate.uuid.sat',
            'res_id': ids[0],
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'domain': '[]',
            'context': context,
        }
    
class xml_to_validate_line(osv.osv_memory):
    _name = 'xml.to.validate.line'
    
    def fields_view_get(self, cr, uid, view_id=None, view_type=False, context=None, toolbar=False, submenu=False):
        if context is None:
            context = {}
        res = super(xml_to_validate_line, self).fields_view_get(cr, uid, view_id=view_id,
            view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
        if context.get('active_ids'):
            att_obj = self.pool.get('ir.attachment')
            attachment_ids = att_obj.search(cr, uid, [('res_id', 'in', context.get('active_ids'))], context=context)
            att_dom = []
            for att in att_obj.browse(cr, uid, attachment_ids, context=context):
                if '.xml' in att.name:
                    att_dom.append(att.id)
            for field in res['fields']:
                if field == 'file_xml':
                    res['fields'][field]['domain'] = [('id', 'in', att_dom)]
        return res
    
    _columns = {
        'name': fields.char('XML name', readonly=True, size=64),
        'file_xml': fields.many2one('ir.attachment', 'File XML', help='File to validate UUID',),
        'amount': fields.float('Amount', digits_compute=dp.get_precision('Account'),
            readonly=True, help='Amount to the XML'),
        'number': fields.char('Number', readonly=True, help='Number of XML'),
        'type': fields.char('Type', readonly=True, help='Type of document that generated the XML'),
        'uuid': fields.char('UUID', readonly=True, help='UUID of XML'),
        'date_time': fields.datetime('DateTime', readonly=True, help='DateTime in that was '\
            'generated the XML'),
        'result': fields.char('Result', readonly=True, help='Result of the validation'),
        'vat_emitter': fields.char('Vat Emitter', help='Vat of emitter'),
        'vat_receiver': fields.char('Vat Receiver', help='Vat of receiver'),
        'state_invoice': fields.char('State Invoice', help='State of invoice that was generated the XML'),
    }

    def onchange_xml_id(self, cr, uid, ids, xml_id, context=None):
        result = {'value': {}}
        if xml_id:
            att_obj = self.pool.get('ir.attachment')
            att_brw = att_obj.browse(cr, uid, xml_id, context=context)
            data_xml = base64.decodestring(att_brw.datas or '')
            dict_data = dict(xmltodict.parse(data_xml).get('cfdi:Comprobante', {}))
            #~ print 'dict_data', dict_data
            complemento = dict_data.get('cfdi:Complemento', {})
            emitter = dict_data.get('cfdi:Emisor', {})
            receiver = dict_data.get('cfdi:Receptor', {})
            result['value'].update({
                'name': att_brw.name or '',
                'amount': float(dict_data.get('@total', 0.0)), 
                'number': dict_data.get('@folio', ''), 
                'type': dict_data.get('@tipoDeComprobante', ''), 
                'uuid': complemento.get('tfd:TimbreFiscalDigital', {}).get('@UUID', ''), 
                'vat_emitter': emitter.get('@rfc', ''), 
                'vat_receiver': receiver.get('@rfc', ''), 
                })
        print 'result', result
        return result
