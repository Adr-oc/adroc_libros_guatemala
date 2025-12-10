# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import time
from .adroc_excel_utils import AdrocExcelReport


class AdrocAsistenteReporteBanco(models.TransientModel):
    _name = 'adroc_libros_guatemala.asistente_reporte_banco'
    _description = "Asistente para reporte de bancos"

    def _default_cuenta(self):
        if len(self.env.context.get('active_ids', [])) > 0:
            return self.env.context.get('active_ids')[0]
        else:
            return None

    cuenta_bancaria_id = fields.Many2one(
        "account.account", string="Cuenta", required=True, default=_default_cuenta)
    folio_inicial = fields.Integer(
        string="Folio Inicial", required=True, default=1)
    fecha_desde = fields.Date(
        string="Fecha Inicial", required=True,
        default=lambda self: time.strftime("%Y-%m-01"))
    fecha_hasta = fields.Date(
        string="Fecha Final", required=True,
        default=lambda self: time.strftime("%Y-%m-%d"))
    name = fields.Char('Nombre archivo', size=64)
    archivo = fields.Binary('Archivo')

    def print_report(self):
        data = {
            'ids': [],
            'model': 'adroc_libros_guatemala.asistente_reporte_banco',
            'form': self.read()[0]
        }
        return self.env.ref(
            'adroc_libros_guatemala.action_adroc_reporte_banco'
        ).report_action(self, data=data)

    def print_report_excel(self):
        self.ensure_one()

        # Preparar datos para el reporte
        datos = {
            'cuenta_bancaria_id': [self.cuenta_bancaria_id.id],
            'fecha_desde': self.fecha_desde,
            'fecha_hasta': self.fecha_hasta,
        }

        reporte_model = self.env['report.adroc_libros_guatemala.adroc_reporte_banco']
        res = reporte_model.lineas(datos)
        lineas = res['lineas']
        totales = res['totales']
        balance_inicial = reporte_model.balance_inicial(datos)

        # Crear Excel
        excel = AdrocExcelReport(
            'LIBRO DE BANCO',
            self.cuenta_bancaria_id.company_id or self.env.company
        )
        sheet = excel.add_worksheet('Libro de Banco')

        # Configurar para impresion
        excel.set_landscape(sheet)

        # Encabezado
        row = excel.write_header(
            sheet, self.fecha_desde, self.fecha_hasta)

        # Info de la cuenta
        sheet.write(row, 0, 'CUENTA:', excel.fmt_etiqueta)
        sheet.write(row, 1, f'{self.cuenta_bancaria_id.code} - {self.cuenta_bancaria_id.name}',
                    excel.fmt_valor)

        # Moneda
        moneda = self.cuenta_bancaria_id.currency_id or self.env.company.currency_id
        sheet.write(row, 3, 'MONEDA:', excel.fmt_etiqueta)
        sheet.write(row, 4, moneda.name, excel.fmt_valor)

        row += 2

        # Balance inicial
        saldo_inicial = balance_inicial.get('balance_moneda') or balance_inicial.get('balance', 0)
        sheet.write(row, 0, 'SALDO INICIAL:', excel.fmt_subtitulo)
        sheet.write(row, 1, saldo_inicial, excel.fmt_numero)

        row += 2

        # Encabezados de tabla
        headers = ['Fecha', 'Documento', 'Tercero', 'Concepto', 'Debe', 'Haber', 'Saldo']
        col_widths = [12, 15, 25, 35, 15, 15, 15]
        row = excel.write_table_headers(sheet, headers, row, col_widths)

        # Congelar encabezados
        excel.freeze_panes(sheet, row, 0)
        header_row = row - 1

        # Datos
        for i, linea in enumerate(lineas):
            fmts = excel.get_row_formats(i)

            sheet.write(row, 0, linea['fecha'], fmts['fecha'])
            sheet.write(row, 1, linea['documento'], fmts['texto'])
            sheet.write(row, 2, linea['nombre'], fmts['texto'])
            sheet.write(row, 3, linea['concepto'], fmts['texto'])
            sheet.write(row, 4, linea['debito'], fmts['numero'])
            sheet.write(row, 5, linea['credito'], fmts['numero'])
            sheet.write(row, 6, linea['balance'], fmts['numero'])
            row += 1

        # Agregar filtros
        if lineas:
            excel.add_autofilter(sheet, header_row, 0, row - 1, 6)

        # Totales
        row += 1
        excel.write_totals_row(sheet, row, 3, {
            4: totales['debito'],
            5: totales['credito'],
            6: totales['balance'],
        })

        # Guardar archivo
        datos_excel = excel.close_and_get_data()
        self.write({
            'archivo': datos_excel,
            'name': f'libro_banco_{self.cuenta_bancaria_id.code}.xlsx'
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'adroc_libros_guatemala.asistente_reporte_banco',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
