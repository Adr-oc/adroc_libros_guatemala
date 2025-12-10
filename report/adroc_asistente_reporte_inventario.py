# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import time
from .adroc_excel_utils import AdrocExcelReport


class AdrocAsistenteReporteInventario(models.TransientModel):
    _name = 'adroc_libros_guatemala.asistente_reporte_inventario'
    _description = "Asistente para reporte de Inventarios"

    def _default_cuenta(self):
        return self.env['account.account'].search([
            '|', '|',
            ('code', '=like', '1%'),
            ('code', '=like', '2%'),
            ('code', '=like', '3%')
        ]).ids

    cuentas_id = fields.Many2many(
        "account.account",
        relation="adroc_rpt_inv_account_rel",
        string="Inventario",
        required=True,
        default=_default_cuenta)
    folio_inicial = fields.Integer(
        string="Folio Inicial", required=True, default=1)
    fecha_desde = fields.Date(
        string="Fecha Desde", required=True,
        default=lambda self: time.strftime('%Y-%m-01'))
    fecha_hasta = fields.Date(
        string="Fecha Final", required=True,
        default=lambda self: time.strftime('%Y-%m-%d'))
    name = fields.Char('Nombre archivo', size=64)
    archivo = fields.Binary('Archivo')

    def print_report(self):
        data = {
            'ids': [],
            'model': 'adroc_libros_guatemala.asistente_reporte_inventario',
            'form': self.read()[0]
        }
        return self.env.ref(
            'adroc_libros_guatemala.action_adroc_reporte_inventario'
        ).report_action(self, data=data)

    def print_report_excel(self):
        self.ensure_one()

        if not self.cuentas_id:
            raise UserError(_("Debe seleccionar al menos una cuenta."))

        # Preparar datos
        datos = {
            'cuentas_id': self.cuentas_id.ids,
            'fecha_desde': self.fecha_desde,
            'fecha_hasta': self.fecha_hasta,
        }

        reporte_model = self.env['report.adroc_libros_guatemala.adroc_reporte_inventario']
        res = reporte_model.lineas(datos)
        lineas = res['lineas']
        totales = res['totales']

        # Crear Excel
        excel = AdrocExcelReport(
            'LIBRO DE INVENTARIO',
            self.env.company
        )
        sheet = excel.add_worksheet('Libro Inventario')

        # Configurar para impresion
        excel.set_landscape(sheet)

        # Encabezado
        row = excel.write_header(sheet, self.fecha_desde, self.fecha_hasta)
        row += 1

        # Encabezados de tabla
        headers = ['Codigo', 'Cuenta', 'Saldo Inicial', 'Debe', 'Haber', 'Saldo Final']
        col_widths = [15, 40, 15, 15, 15, 15]

        def write_section(section_name, section_lineas, start_row):
            """Escribe una seccion del inventario (Activo, Pasivo, Capital)."""
            row = start_row

            # Titulo de seccion
            sheet.merge_range(row, 0, row, 5, section_name, excel.fmt_seccion)
            row += 1

            # Headers
            row = excel.write_table_headers(sheet, headers, row, col_widths)

            # Datos
            total_saldo_inicial = 0
            total_debe = 0
            total_haber = 0
            total_saldo_final = 0

            for i, linea in enumerate(section_lineas):
                fmts = excel.get_row_formats(i)

                sheet.write(row, 0, linea.get('codigo', ''), fmts['texto'])
                sheet.write(row, 1, linea.get('cuenta', ''), fmts['texto'])
                sheet.write(row, 2, linea.get('saldo_inicial', 0), fmts['numero'])
                sheet.write(row, 3, linea.get('debe', 0), fmts['numero'])
                sheet.write(row, 4, linea.get('haber', 0), fmts['numero'])
                sheet.write(row, 5, linea.get('saldo_final', 0), fmts['numero'])

                total_saldo_inicial += linea.get('saldo_inicial', 0)
                total_debe += linea.get('debe', 0)
                total_haber += linea.get('haber', 0)
                total_saldo_final += linea.get('saldo_final', 0)
                row += 1

            # Subtotales de seccion
            sheet.write(row, 1, f'Total {section_name}', excel.fmt_total_texto)
            sheet.write(row, 2, total_saldo_inicial, excel.fmt_total_numero)
            sheet.write(row, 3, total_debe, excel.fmt_total_numero)
            sheet.write(row, 4, total_haber, excel.fmt_total_numero)
            sheet.write(row, 5, total_saldo_final, excel.fmt_total_numero)
            row += 2

            return row, {
                'saldo_inicial': total_saldo_inicial,
                'debe': total_debe,
                'haber': total_haber,
                'saldo_final': total_saldo_final,
            }

        # Escribir secciones
        totales_generales = {
            'saldo_inicial': 0,
            'debe': 0,
            'haber': 0,
            'saldo_final': 0,
        }

        # ACTIVO
        if lineas.get('activo'):
            row, subtotales = write_section('ACTIVO', lineas['activo'], row)
            for key in totales_generales:
                totales_generales[key] += subtotales[key]

        # PASIVO
        if lineas.get('pasivo'):
            row, subtotales = write_section('PASIVO', lineas['pasivo'], row)
            for key in totales_generales:
                totales_generales[key] += subtotales[key]

        # CAPITAL
        if lineas.get('capital'):
            row, subtotales = write_section('CAPITAL', lineas['capital'], row)
            for key in totales_generales:
                totales_generales[key] += subtotales[key]

        # Totales generales
        row += 1
        sheet.merge_range(row, 0, row, 1, 'TOTALES GENERALES', excel.fmt_total_texto)
        sheet.write(row, 2, totales_generales['saldo_inicial'], excel.fmt_total_numero)
        sheet.write(row, 3, totales_generales['debe'], excel.fmt_total_numero)
        sheet.write(row, 4, totales_generales['haber'], excel.fmt_total_numero)
        sheet.write(row, 5, totales_generales['saldo_final'], excel.fmt_total_numero)

        # Congelar primera fila
        excel.freeze_panes(sheet, 6, 0)

        # Guardar archivo
        datos_excel = excel.close_and_get_data()
        self.write({
            'archivo': datos_excel,
            'name': 'libro_inventario.xlsx'
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'adroc_libros_guatemala.asistente_reporte_inventario',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
