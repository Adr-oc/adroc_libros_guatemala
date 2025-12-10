# -*- encoding: utf-8 -*-

import xlsxwriter
import io
import base64
from datetime import date


class AdrocExcelReport:
    """
    Clase base para generar reportes Excel con formato profesional.
    Proporciona estilos consistentes y métodos reutilizables.
    """

    def __init__(self, titulo_reporte, company):
        self.buffer = io.BytesIO()
        self.workbook = xlsxwriter.Workbook(self.buffer, {'in_memory': True})
        self.titulo_reporte = titulo_reporte
        self.company = company
        self._init_formats()

    def _init_formats(self):
        """Inicializa todos los formatos de celda reutilizables."""
        # Formato para el titulo principal
        self.fmt_titulo = self.workbook.add_format({
            'bold': True,
            'font_size': 14,
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#1a5276',
        })

        # Formato para subtitulos
        self.fmt_subtitulo = self.workbook.add_format({
            'bold': True,
            'font_size': 11,
            'font_color': '#2c3e50',
        })

        # Formato para etiquetas de encabezado de empresa
        self.fmt_etiqueta = self.workbook.add_format({
            'bold': True,
            'font_size': 9,
            'font_color': '#7f8c8d',
        })

        # Formato para valores de encabezado de empresa
        self.fmt_valor = self.workbook.add_format({
            'font_size': 9,
        })

        # Formato para encabezados de tabla
        self.fmt_header = self.workbook.add_format({
            'bold': True,
            'font_size': 10,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#2c3e50',
            'font_color': 'white',
            'border': 1,
            'text_wrap': True,
        })

        # Formato para celdas de datos texto
        self.fmt_texto = self.workbook.add_format({
            'font_size': 9,
            'border': 1,
            'valign': 'vcenter',
        })

        # Formato para celdas de datos numericos
        self.fmt_numero = self.workbook.add_format({
            'font_size': 9,
            'border': 1,
            'valign': 'vcenter',
            'num_format': '#,##0.00',
            'align': 'right',
        })

        # Formato para celdas de datos enteros
        self.fmt_entero = self.workbook.add_format({
            'font_size': 9,
            'border': 1,
            'valign': 'vcenter',
            'num_format': '#,##0',
            'align': 'right',
        })

        # Formato para fechas
        self.fmt_fecha = self.workbook.add_format({
            'font_size': 9,
            'border': 1,
            'valign': 'vcenter',
            'num_format': 'dd/mm/yyyy',
            'align': 'center',
        })

        # Formato para fila de totales
        self.fmt_total_texto = self.workbook.add_format({
            'bold': True,
            'font_size': 10,
            'border': 1,
            'bg_color': '#ecf0f1',
            'valign': 'vcenter',
        })

        self.fmt_total_numero = self.workbook.add_format({
            'bold': True,
            'font_size': 10,
            'border': 1,
            'bg_color': '#ecf0f1',
            'num_format': '#,##0.00',
            'align': 'right',
            'valign': 'vcenter',
        })

        # Formato para filas alternadas (zebra)
        self.fmt_texto_alt = self.workbook.add_format({
            'font_size': 9,
            'border': 1,
            'valign': 'vcenter',
            'bg_color': '#f8f9fa',
        })

        self.fmt_numero_alt = self.workbook.add_format({
            'font_size': 9,
            'border': 1,
            'valign': 'vcenter',
            'num_format': '#,##0.00',
            'align': 'right',
            'bg_color': '#f8f9fa',
        })

        self.fmt_fecha_alt = self.workbook.add_format({
            'font_size': 9,
            'border': 1,
            'valign': 'vcenter',
            'num_format': 'dd/mm/yyyy',
            'align': 'center',
            'bg_color': '#f8f9fa',
        })

        self.fmt_entero_alt = self.workbook.add_format({
            'font_size': 9,
            'border': 1,
            'valign': 'vcenter',
            'num_format': '#,##0',
            'align': 'right',
            'bg_color': '#f8f9fa',
        })

        # Formato para secciones de resumen
        self.fmt_seccion = self.workbook.add_format({
            'bold': True,
            'font_size': 11,
            'bg_color': '#3498db',
            'font_color': 'white',
            'border': 1,
        })

    def add_worksheet(self, name='Reporte'):
        """Crea una hoja nueva y retorna el objeto worksheet."""
        return self.workbook.add_worksheet(name)

    def write_header(self, sheet, fecha_desde, fecha_hasta, start_row=0):
        """
        Escribe el encabezado estandar del reporte con informacion de empresa.
        Retorna la fila donde debe continuar el contenido.
        """
        # Titulo del reporte
        sheet.merge_range(start_row, 0, start_row, 5, self.titulo_reporte, self.fmt_titulo)

        # Informacion de la empresa
        row = start_row + 2
        sheet.write(row, 0, 'NIT:', self.fmt_etiqueta)
        sheet.write(row, 1, self.company.partner_id.vat or '', self.fmt_valor)
        sheet.write(row, 3, 'DOMICILIO FISCAL:', self.fmt_etiqueta)
        sheet.write(row, 4, self.company.partner_id.street or '', self.fmt_valor)

        row += 1
        sheet.write(row, 0, 'NOMBRE:', self.fmt_etiqueta)
        sheet.write(row, 1, self.company.partner_id.name or '', self.fmt_valor)
        sheet.write(row, 3, 'PERIODO:', self.fmt_etiqueta)

        # Formatear fechas
        if isinstance(fecha_desde, date):
            fecha_desde_str = fecha_desde.strftime('%d/%m/%Y')
        else:
            fecha_desde_str = str(fecha_desde)

        if isinstance(fecha_hasta, date):
            fecha_hasta_str = fecha_hasta.strftime('%d/%m/%Y')
        else:
            fecha_hasta_str = str(fecha_hasta)

        sheet.write(row, 4, f'{fecha_desde_str} al {fecha_hasta_str}', self.fmt_valor)

        return row + 2  # Retorna la fila para continuar

    def write_table_headers(self, sheet, headers, row, col_widths=None):
        """
        Escribe los encabezados de una tabla.
        headers: lista de strings con los nombres de columnas
        col_widths: lista opcional de anchos de columna
        """
        for col, header in enumerate(headers):
            sheet.write(row, col, header, self.fmt_header)
            if col_widths and col < len(col_widths):
                sheet.set_column(col, col, col_widths[col])

        return row + 1

    def get_row_formats(self, row_index):
        """
        Retorna los formatos para una fila basado en si es par o impar (efecto zebra).
        """
        if row_index % 2 == 0:
            return {
                'texto': self.fmt_texto,
                'numero': self.fmt_numero,
                'fecha': self.fmt_fecha,
                'entero': self.fmt_entero,
            }
        else:
            return {
                'texto': self.fmt_texto_alt,
                'numero': self.fmt_numero_alt,
                'fecha': self.fmt_fecha_alt,
                'entero': self.fmt_entero_alt,
            }

    def write_totals_row(self, sheet, row, col_start, values, label='TOTALES'):
        """
        Escribe una fila de totales.
        values: diccionario {col_index: valor}
        """
        sheet.write(row, col_start, label, self.fmt_total_texto)
        for col, value in values.items():
            sheet.write(row, col, value, self.fmt_total_numero)

        return row + 1

    def close_and_get_data(self):
        """Cierra el workbook y retorna los datos en base64."""
        self.workbook.close()
        return base64.b64encode(self.buffer.getvalue())

    def freeze_panes(self, sheet, row, col):
        """Congela filas/columnas para scroll."""
        sheet.freeze_panes(row, col)

    def set_landscape(self, sheet):
        """Configura la hoja para impresion horizontal."""
        sheet.set_landscape()
        sheet.set_paper(1)  # Letter
        sheet.fit_to_pages(1, 0)  # Ajustar al ancho de 1 pagina

    def add_autofilter(self, sheet, first_row, first_col, last_row, last_col):
        """Agrega filtros automaticos a un rango."""
        sheet.autofilter(first_row, first_col, last_row, last_col)
