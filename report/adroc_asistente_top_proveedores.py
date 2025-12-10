# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import time
from .adroc_excel_utils import AdrocExcelReport


class AdrocAsistenteTopProveedores(models.TransientModel):
    _name = 'adroc_libros_guatemala.asistente_top_proveedores'
    _description = "Asistente para reporte de Proveedores"

    def _default_proveedor(self):
        """Obtiene proveedores que tienen facturas de compra."""
        # Usar ORM en lugar de SQL directo para mejor rendimiento y seguridad
        facturas = self.env['account.move'].search([
            ('move_type', '=', 'in_invoice'),
            ('state', '=', 'posted'),
        ])
        partner_ids = facturas.mapped('partner_id').ids
        return [(6, 0, partner_ids)] if partner_ids else False

    proveedor_id = fields.Many2many(
        "res.partner",
        relation="adroc_rpt_top_prov_partner_rel",
        string="Proveedores",
        required=True,
        default=_default_proveedor)
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
            'model': 'adroc_libros_guatemala.asistente_top_proveedores',
            'form': self.read()[0]
        }
        return self.env.ref(
            'adroc_libros_guatemala.action_adroc_top_proveedores'
        ).report_action(self, data=data)

    def print_report_excel(self):
        self.ensure_one()

        if not self.proveedor_id:
            raise UserError(_("Debe seleccionar al menos un proveedor."))

        # Preparar datos
        datos = {
            'proveedor_id': self.proveedor_id.ids,
            'fecha_desde': self.fecha_desde,
            'fecha_hasta': self.fecha_hasta,
        }

        reporte_model = self.env['report.adroc_libros_guatemala.adroc_reporte_top_proveedores']
        res = reporte_model.lineas(datos)
        lineas = res['lineas']

        # Crear Excel
        excel = AdrocExcelReport(
            'RESUMEN DE PROVEEDORES Y TOTAL DE DOCUMENTOS',
            self.env.company
        )
        sheet = excel.add_worksheet('Top Proveedores')

        # Configurar para impresion
        excel.set_landscape(sheet)

        # Encabezado
        row = excel.write_header(sheet, self.fecha_desde, self.fecha_hasta)
        row += 1

        # Encabezados de tabla
        headers = ['No.', 'NIT', 'Proveedor', 'No. Documentos', 'Total Facturado']
        col_widths = [8, 15, 45, 15, 18]
        row = excel.write_table_headers(sheet, headers, row, col_widths)

        # Congelar encabezados
        excel.freeze_panes(sheet, row, 0)
        header_row = row - 1

        # Datos
        total_documentos = 0
        total_facturado = 0.0

        for i, linea in enumerate(lineas):
            fmts = excel.get_row_formats(i)

            sheet.write(row, 0, i + 1, fmts['entero'])
            sheet.write(row, 1, linea.get('vat', ''), fmts['texto'])
            sheet.write(row, 2, linea.get('display_name', ''), fmts['texto'])
            sheet.write(row, 3, linea.get('cant_documentos', 0), fmts['entero'])
            sheet.write(row, 4, linea.get('total_facturas', 0), fmts['numero'])

            total_documentos += linea.get('cant_documentos', 0)
            total_facturado += linea.get('total_facturas', 0)
            row += 1

        # Agregar filtros
        if lineas:
            excel.add_autofilter(sheet, header_row, 0, row - 1, 4)

        # Totales
        row += 1
        sheet.write(row, 2, 'TOTALES', excel.fmt_total_texto)
        sheet.write(row, 3, total_documentos, excel.fmt_total_numero)
        sheet.write(row, 4, total_facturado, excel.fmt_total_numero)

        # Resumen adicional
        row += 3
        sheet.write(row, 0, 'RESUMEN', excel.fmt_seccion)
        sheet.merge_range(row, 0, row, 2, 'RESUMEN', excel.fmt_seccion)

        row += 1
        sheet.write(row, 0, 'Cantidad de proveedores:', excel.fmt_etiqueta)
        sheet.write(row, 1, len(lineas), excel.fmt_valor)

        row += 1
        sheet.write(row, 0, 'Total documentos:', excel.fmt_etiqueta)
        sheet.write(row, 1, total_documentos, excel.fmt_valor)

        row += 1
        sheet.write(row, 0, 'Total facturado:', excel.fmt_etiqueta)
        sheet.write(row, 1, total_facturado, excel.fmt_numero)

        # Guardar archivo
        datos_excel = excel.close_and_get_data()
        self.write({
            'archivo': datos_excel,
            'name': 'top_proveedores.xlsx'
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'adroc_libros_guatemala.asistente_top_proveedores',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
