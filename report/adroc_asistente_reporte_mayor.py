# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import time
import xlsxwriter
import base64
import io
import logging


class AdrocAsistenteReporteMayor(models.TransientModel):
    _name = 'adroc_libros_guatemala.asistente_reporte_mayor'
    _description = "Asistente para reporte de Mayor"

    def _default_cuenta(self):
        if len(self.env.context.get('active_ids', [])) > 0:
            return self.env.context.get('active_ids')
        else:
            return self.env['account.account'].search([]).ids

    cuentas_id = fields.Many2many("account.account", relation="adroc_rpt_mayor_account_rel",
        string="Cuentas", required=True, default=_default_cuenta)
    folio_inicial = fields.Integer(string="Folio Inicial", required=True, default=1)
    agrupado_por_dia = fields.Boolean(string="Agrupado por dia", default=True)
    agrupado_por_diario = fields.Boolean(string="Agrupado por diario", default=True)
    fecha_desde = fields.Date(string="Fecha Inicial", required=True, default=lambda self: time.strftime('%Y-%m-01'))
    fecha_hasta = fields.Date(string="Fecha Final", required=True, default=lambda self: time.strftime('%Y-%m-%d'))
    name = fields.Char('Nombre archivo', size=32)
    archivo = fields.Binary('Archivo')

    def print_report(self):
        data = {
            'ids': [],
            'model': 'adroc_libros_guatemala.asistente_reporte_mayor',
            'form': self.read()[0]
        }
        return self.env.ref('adroc_libros_guatemala.action_adroc_reporte_mayor').report_action(self, data=data)

    def print_report_excel(self):
        for w in self:
            dict = {}
            dict['fecha_hasta'] = w['fecha_hasta']
            dict['fecha_desde'] = w['fecha_desde']
            dict['agrupado_por_dia'] = w['agrupado_por_dia']
            dict['agrupado_por_diario'] = w['agrupado_por_diario']
            dict['cuentas_id'] = [x.id for x in w.cuentas_id]
            res = self.env['report.adroc_libros_guatemala.adroc_reporte_mayor'].lineas(dict)

            f = io.BytesIO()
            libro = xlsxwriter.Workbook(f)
            hoja = libro.add_worksheet('Reporte')
            formato_fecha = libro.add_format({'num_format': 'dd/mm/yy'})

            hoja.write(0, 0, 'LIBRO MAYOR')
            hoja.write(2, 0, 'NUMERO DE IDENTIFICACION TRIBUTARIA')
            # In Odoo 19, company_id changed to company_ids
            company = w.cuentas_id[0].company_ids[0] if w.cuentas_id[0].company_ids else self.env.company
            hoja.write(2, 1, company.partner_id.vat)
            hoja.write(3, 0, 'NOMBRE COMERCIAL')
            hoja.write(3, 1, company.partner_id.name)
            hoja.write(2, 3, 'DOMICILIO FISCAL')
            hoja.write(2, 4, company.partner_id.street)
            hoja.write(3, 3, 'REGISTRO DEL')
            hoja.write(3, 4, w.fecha_desde, formato_fecha)
            hoja.write(3, 5, 'AL')
            hoja.write(3, 6, w.fecha_hasta, formato_fecha)

            y = 5
            if w['agrupado_por_dia']:
                lineas = res['lineas']

                hoja.write(y, 0, 'Codigo')
                hoja.write(y, 1, 'Cuenta')
                hoja.write(y, 2, 'fecha')
                hoja.write(y, 3, 'Saldo Inicial')
                hoja.write(y, 4, 'Debe')
                hoja.write(y, 5, 'Haber')
                hoja.write(y, 6, 'Saldo Final')

                for cuenta in lineas:
                    y += 1
                    hoja.write(y, 0, cuenta['codigo'])
                    hoja.write(y, 1, cuenta['cuenta'])
                    hoja.write(y, 3, cuenta['saldo_inicial'])
                    hoja.write(y, 4, cuenta['total_debe'])
                    hoja.write(y, 5, cuenta['total_haber'])
                    hoja.write(y, 6, cuenta['saldo_final'])
                    for fechas in cuenta['fechas']:
                        y += 1
                        hoja.write(y, 2, fechas['fecha'])
                        hoja.write(y, 4, fechas['debe'])
                        hoja.write(y, 5, fechas['haber'])
                    y += 1
            else:
                lineas = res['lineas']
                totales = res['totales']

                hoja.write(y, 0, 'Codigo')
                hoja.write(y, 1, 'Cuenta')
                hoja.write(y, 2, 'Saldo Inicial')
                hoja.write(y, 3, 'Debe')
                hoja.write(y, 4, 'Haber')
                hoja.write(y, 5, 'Saldo Final')

                for linea in lineas:
                    y += 1
                    hoja.write(y, 0, linea['codigo'])
                    hoja.write(y, 1, linea['cuenta'])
                    hoja.write(y, 2, linea['saldo_inicial'])
                    hoja.write(y, 3, linea['debe'])
                    hoja.write(y, 4, linea['haber'])
                    hoja.write(y, 5, linea['saldo_final'])

                y += 1
                hoja.write(y, 1, 'Totales')
                hoja.write(y, 3, totales['debe'])
                hoja.write(y, 4, totales['haber'])

            libro.close()
            datos = base64.b64encode(f.getvalue())
            self.write({'archivo': datos, 'name': 'libro_mayor.xlsx'})

        return {
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'adroc_libros_guatemala.asistente_reporte_mayor',
            'res_id': self.id,
            'view_id': False,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }
