# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import time
from .adroc_excel_utils import AdrocExcelReport


class AdrocAsistenteReporteCompras(models.TransientModel):
    _name = 'adroc_libros_guatemala.asistente_reporte_compras'
    _description = "Asistente para reporte de compras"

    def _default_diarios(self):
        return self.env['account.journal'].search([('type', '=', 'purchase')]).ids

    def _default_impuesto(self):
        impuesto = self.env['account.tax'].search(
            [('name', '=', 'IVA por Cobrar'), ('company_id', '=', self.env.company.id)], limit=1)
        return impuesto.id if impuesto else False

    diarios_id = fields.Many2many(
        "account.journal", relation="adroc_rpt_compras_journal_rel",
        string="Diarios", required=True, default=_default_diarios)
    impuesto_id = fields.Many2one(
        "account.tax", string="Impuesto", required=True, default=_default_impuesto)
    folio_inicial = fields.Integer(
        string="Folio Inicial", required=True, default=1)
    fecha_desde = fields.Date(
        string="Fecha Inicial", required=True,
        default=lambda self: time.strftime('%Y-%m-01'))
    fecha_hasta = fields.Date(
        string="Fecha Final", required=True,
        default=lambda self: time.strftime('%Y-%m-%d'))
    name = fields.Char('Nombre archivo', size=64)
    archivo = fields.Binary('Archivo')

    def print_report(self):
        data = {
            'ids': [],
            'model': 'adroc_libros_guatemala.asistente_reporte_compras',
            'form': self.read()[0]
        }
        return self.env.ref(
            'adroc_libros_guatemala.action_adroc_reporte_compras'
        ).with_context(landscape=True).report_action(self, data=data)

    def print_report_excel(self):
        self.ensure_one()

        if not self.diarios_id:
            raise UserError(_("Debe seleccionar al menos un diario."))

        # Preparar datos
        datos = {
            'fecha_hasta': self.fecha_hasta,
            'fecha_desde': self.fecha_desde,
            'impuesto_id': [self.impuesto_id.id, self.impuesto_id.name],
            'diarios_id': self.diarios_id.ids,
        }

        reporte_model = self.env['report.adroc_libros_guatemala.adroc_reporte_compras']
        res = reporte_model.lineas(datos)
        lineas = res['lineas']
        totales = res['totales']

        # Crear Excel con formato profesional
        company = self.diarios_id[0].company_id or self.env.company
        excel = AdrocExcelReport('LIBRO DE COMPRAS Y SERVICIOS', company)
        sheet = excel.add_worksheet('Libro de Compras')

        # Configurar para impresion horizontal
        excel.set_landscape(sheet)

        # Encabezado del reporte
        row = excel.write_header(sheet, self.fecha_desde, self.fecha_hasta)
        row += 1

        # Encabezados de la tabla
        headers = [
            'Tipo', 'Fecha', 'Serie', 'Numero', 'Proveedor', 'NIT',
            'Compras', 'Compras Exento', 'Servicios', 'Servicios Exento',
            'Combustible', 'IDP', 'Importaciones', 'Peq. Contribuyentes',
            'IVA', 'ISR', 'Total'
        ]
        col_widths = [8, 11, 10, 12, 30, 15, 12, 12, 12, 12, 12, 10, 12, 12, 12, 12, 14]
        row = excel.write_table_headers(sheet, headers, row, col_widths)

        # Congelar encabezados
        excel.freeze_panes(sheet, row, 0)
        header_row = row - 1

        # Datos de las lineas
        for i, linea in enumerate(lineas):
            fmts = excel.get_row_formats(i)

            sheet.write(row, 0, linea['tipo'], fmts['texto'])
            sheet.write(row, 1, linea['fecha'], fmts['fecha'])
            sheet.write(row, 2, linea['serie'], fmts['texto'])
            sheet.write(row, 3, linea['numero'], fmts['texto'])
            sheet.write(row, 4, linea['proveedor'], fmts['texto'])
            sheet.write(row, 5, linea['nit'], fmts['texto'])
            sheet.write(row, 6, linea['compra'], fmts['numero'])
            sheet.write(row, 7, linea['compra_exento'], fmts['numero'])
            sheet.write(row, 8, linea['servicio'], fmts['numero'])
            sheet.write(row, 9, linea['servicio_exento'], fmts['numero'])
            sheet.write(row, 10, linea['combustible'], fmts['numero'])
            sheet.write(row, 11, linea['combustible_exento'], fmts['numero'])
            sheet.write(row, 12, linea['importacion'] + linea['importacion_exento'], fmts['numero'])
            sheet.write(row, 13, linea['pequeno'] + linea['pequeno_exento'], fmts['numero'])
            sheet.write(row, 14, linea['iva'], fmts['numero'])
            sheet.write(row, 15, linea['isr'], fmts['numero'])
            sheet.write(row, 16, linea['total'], fmts['numero'])
            row += 1

        # Agregar filtros
        if lineas:
            excel.add_autofilter(sheet, header_row, 0, row - 1, 16)

        # Fila de totales
        row += 1
        sheet.write(row, 5, 'TOTALES', excel.fmt_total_texto)
        sheet.write(row, 6, totales['compra']['neto'], excel.fmt_total_numero)
        sheet.write(row, 7, totales['compra']['exento'], excel.fmt_total_numero)
        sheet.write(row, 8, totales['servicio']['neto'], excel.fmt_total_numero)
        sheet.write(row, 9, totales['servicio']['exento'], excel.fmt_total_numero)
        sheet.write(row, 10, totales['combustible']['neto'], excel.fmt_total_numero)
        sheet.write(row, 11, totales['combustible']['exento'], excel.fmt_total_numero)
        sheet.write(row, 12, totales['importacion']['neto'] + totales['importacion']['exento'], excel.fmt_total_numero)
        sheet.write(row, 13, totales['pequeno']['neto'] + totales['pequeno']['exento'], excel.fmt_total_numero)

        total_iva = (totales['compra']['iva'] + totales['servicio']['iva'] +
                     totales['combustible']['iva'] + totales['importacion']['iva'] +
                     totales['pequeno']['iva'])
        total_isr = (totales['compra']['isr'] + totales['servicio']['isr'] +
                     totales['combustible']['isr'] + totales['importacion']['isr'] +
                     totales['pequeno']['isr'])
        total_general = (totales['compra']['total'] + totales['servicio']['total'] +
                         totales['combustible']['total'] + totales['importacion']['total'] +
                         totales['pequeno']['total'])

        sheet.write(row, 14, total_iva, excel.fmt_total_numero)
        sheet.write(row, 15, total_isr, excel.fmt_total_numero)
        sheet.write(row, 16, total_general, excel.fmt_total_numero)

        # Resumen
        row += 3
        sheet.merge_range(row, 0, row, 2, 'RESUMEN', excel.fmt_seccion)
        row += 1
        sheet.write(row, 0, 'Cantidad de facturas:', excel.fmt_etiqueta)
        sheet.write(row, 1, totales['num_facturas'], excel.fmt_valor)
        row += 1
        sheet.write(row, 0, 'Total credito fiscal:', excel.fmt_etiqueta)
        sheet.write(row, 1, total_iva, excel.fmt_numero)

        # Resumen por tipo
        row += 2
        resumen_headers = ['', 'Tipo', 'Exento', 'Neto', 'IVA', 'ISR', 'Total']
        row = excel.write_table_headers(sheet, resumen_headers, row)

        tipos_resumen = [
            ('COMPRAS', totales['compra']),
            ('SERVICIOS', totales['servicio']),
            ('COMBUSTIBLES', totales['combustible']),
            ('IMPORTACIONES', totales['importacion']),
            ('PEQ. CONTRIBUYENTES', totales['pequeno']),
        ]

        for i, (nombre, vals) in enumerate(tipos_resumen):
            fmts = excel.get_row_formats(i)
            sheet.write(row, 1, nombre, fmts['texto'])
            sheet.write(row, 2, vals['exento'], fmts['numero'])
            sheet.write(row, 3, vals['neto'], fmts['numero'])
            sheet.write(row, 4, vals['iva'], fmts['numero'])
            sheet.write(row, 5, vals['isr'], fmts['numero'])
            sheet.write(row, 6, vals['total'], fmts['numero'])
            row += 1

        # Totales del resumen
        total_exento = sum(t[1]['exento'] for t in tipos_resumen)
        total_neto = sum(t[1]['neto'] for t in tipos_resumen)

        sheet.write(row, 1, 'TOTALES', excel.fmt_total_texto)
        sheet.write(row, 2, total_exento, excel.fmt_total_numero)
        sheet.write(row, 3, total_neto, excel.fmt_total_numero)
        sheet.write(row, 4, total_iva, excel.fmt_total_numero)
        sheet.write(row, 5, total_isr, excel.fmt_total_numero)
        sheet.write(row, 6, total_general, excel.fmt_total_numero)

        # Guardar archivo
        datos_excel = excel.close_and_get_data()
        self.write({
            'archivo': datos_excel,
            'name': 'libro_de_compras.xlsx'
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'adroc_libros_guatemala.asistente_reporte_compras',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
