# -*- encoding: utf-8 -*-

import json
from odoo import models, fields, api
from odoo.exceptions import UserError
import logging


class AdrocReporteCompras(models.AbstractModel):
    _name = 'report.adroc_libros_guatemala.adroc_reporte_compras'
    _description = "Reporte de compras"

    def lineas(self, datos):
        totales = {}

        totales['num_facturas'] = 0
        totales['compra'] = {'exento': 0, 'neto': 0, 'iva': 0, 'total': 0, 'isr': 0}
        totales['servicio'] = {'exento': 0, 'neto': 0, 'iva': 0, 'total': 0, 'isr': 0}
        totales['combustible'] = {'exento': 0, 'neto': 0, 'iva': 0, 'idp': 0, 'total': 0, 'isr': 0}
        totales['importacion'] = {'exento': 0, 'neto': 0, 'iva': 0, 'total': 0, 'isr': 0}
        totales['pequeno'] = {'exento': 0, 'neto': 0, 'iva': 0, 'total': 0, 'isr': 0}

        journal_ids = [x for x in datos['diarios_id']]
        # Incluir facturas posted y cancel (para mostrar anuladas con invoice_series/invoice_number)
        facturas = self.env['account.move'].search([
            ('state', 'in', ['posted', 'cancel']),
            ('move_type', 'in', ['in_invoice', 'in_refund']),
            ('journal_id', 'in', journal_ids),
            ('invoice_date', '<=', datos['fecha_hasta']),
            ('invoice_date', '>=', datos['fecha_desde']),
        ])

        lineas = []
        for f in facturas:
            # Obtener invoice_series e invoice_number
            serie = f.invoice_series if hasattr(f, 'invoice_series') and f.invoice_series else ''
            numero = f.invoice_number if hasattr(f, 'invoice_number') and f.invoice_number else ''

            # Si está anulada y NO tiene invoice_series e invoice_number, no incluir
            if f.state == 'cancel' and (not serie or not numero):
                continue

            etiquetas = [tag.name for tag in f.etiqueta_ids] if hasattr(f, 'etiqueta_ids') else []

            totales['num_facturas'] += 1

            # Obtener tasa de cambio para quetzalizacion
            tasa_cambio = 1
            if f.currency_id.id == 2:  # USD
                # Buscar tasa de cambio de la fecha exacta
                tasa_cambio_rec = self.env['res.currency.rate'].search(
                    [('currency_id', '=', 2), ('name', '=', f.invoice_date)], limit=1)

                if not tasa_cambio_rec:
                    # Si no existe, buscar la última tasa de cambio registrada
                    tasa_cambio_rec = self.env['res.currency.rate'].search(
                        [('currency_id', '=', 2), ('name', '<=', f.invoice_date)],
                        order='name desc', limit=1)

                if not tasa_cambio_rec:
                    # Si aún no hay ninguna, buscar cualquier tasa registrada
                    tasa_cambio_rec = self.env['res.currency.rate'].search(
                        [('currency_id', '=', 2)], order='name desc', limit=1)

                tasa_cambio = tasa_cambio_rec.inverse_company_rate if tasa_cambio_rec else 1

            tipo = 'FACT'
            if f.move_type != 'in_invoice':
                tipo = 'NC'
            if hasattr(f, 'nota_debito') and f.nota_debito:
                tipo = 'ND'
            if f.partner_id.pequenio_contribuyente if hasattr(f.partner_id, 'pequenio_contribuyente') else False:
                tipo += ' PEQ'

            nit = f.partner_id.vat if f.partner_id.vat else ''

            linea = {
                'estado': f.state,
                'tipo': tipo,
                'fecha': f.invoice_date,
                'serie': serie,
                'numero': numero,
                'proveedor': f.partner_id.name,
                'nit': nit,
                'compra': 0,
                'compra_exento': 0,
                'servicio': 0,
                'servicio_exento': 0,
                'combustible': 0,
                'combustible_exento': 0,
                'importacion': 0,
                'importacion_exento': 0,
                'pequeno': 0,
                'pequeno_exento': 0,
                'base': 0,
                'iva': 0,
                'isr': 0,
                'total': 0
            }

            # Si está anulada (pero tiene serie y número), agregar con valores en cero
            if f.state == 'cancel':
                lineas.append(linea)
                continue

            filtered_lines = list(filter(lambda line: 'Compras' in etiquetas or
                                         'Servicios' in etiquetas or
                                         'Combustible' in etiquetas or
                                         'Importaciones' in etiquetas or
                                         'Pequenos contribuyentes' in etiquetas,
                                         f.invoice_line_ids))

            # Calcular impuestos UNA SOLA VEZ por factura
            all_lines = self.env['account.move.line'].search([('move_id', '=', f.id)])
            taxes = self.env['account.tax'].search([('name', '!=', False)])
            taxes_name = [tax.name for tax in taxes]

            total_iva_factura = 0
            total_isr_factura = 0

            for i in all_lines:
                i_name = str(i.name)
                is_valid_name = len(i_name) > 0
                if is_valid_name and i_name in taxes_name:
                    if 'ISR' in i_name:
                        # ISR: sumar el valor absoluto
                        total_isr_factura += abs(i.credit) if abs(i.credit) > 0 else abs(i.debit)
                    elif 'IVA' in i_name:
                        # IVA: considerar el signo según tipo de documento
                        tax_amount = -(i.credit) if f.move_type != 'in_invoice' else (i.debit)
                        total_iva_factura += tax_amount

            amount_json = json.loads(json.dumps(f.tax_totals))
            for l in filtered_lines:
                tipo_linea = 'Servicios'
                if 'Compras' in etiquetas:
                    tipo_linea = 'compra'
                elif 'Servicios' in etiquetas:
                    tipo_linea = 'servicio'
                elif 'Combustible' in etiquetas:
                    tipo_linea = 'combustible'
                elif 'Importaciones' in etiquetas:
                    tipo_linea = 'importacion'
                elif 'Pequenos contribuyentes' in etiquetas:
                    tipo_linea = 'pequeno'

                price_subtotal = -(l.price_subtotal) if f.move_type != 'in_invoice' else (l.price_subtotal)
                # Aplicar quetzalizacion
                price_subtotal = price_subtotal * tasa_cambio

                linea['base'] += price_subtotal

                if len(l.tax_ids) > 0:
                    linea[tipo_linea] += price_subtotal
                else:
                    linea[tipo_linea + '_exento'] += price_subtotal

            # Asignar impuestos calculados (una vez por factura, no por línea)
            linea['iva'] = total_iva_factura
            linea['isr'] = total_isr_factura

            # Calcular total desde las líneas contables
            # Los valores debit/credit ya están en quetzales
            total = 0
            for i in all_lines:
                total += i.debit

            # Para notas de crédito, invertir el signo
            if tipo == 'NCCQ' or tipo == 'NC':
                linea['total'] = total * -1
            else:
                linea['total'] = total

            lineas.append(linea)

        # Sumar los totales despues de procesar las lineas, incluyendo el ISR
        for linea in lineas:
            for tipo_linea in ['compra', 'servicio', 'combustible', 'importacion', 'pequeno']:
                if linea[tipo_linea] or linea[tipo_linea + '_exento']:
                    totales[tipo_linea]['neto'] += linea[tipo_linea]
                    totales[tipo_linea]['exento'] += linea[tipo_linea + '_exento']
                    totales[tipo_linea]['iva'] += linea['iva']
                    totales[tipo_linea]['total'] += linea['total']
                    totales[tipo_linea]['isr'] += abs(linea['isr'])

        lineas = sorted(lineas, key=lambda i: str(i['fecha']) + str(i['numero']))
        return {'lineas': lineas, 'totales': totales}

    @api.model
    def _get_report_values(self, docids, data=None):
        model = self.env.context.get('active_model')
        docs = self.env[model].browse(self.env.context.get('active_ids', []))

        if len(data['form']['diarios_id']) == 0:
            raise UserError("Por favor ingrese al menos un diario.")

        diario = self.env['account.journal'].browse(data['form']['diarios_id'][0])

        return {
            'doc_ids': self.ids,
            'doc_model': model,
            'data': data['form'],
            'docs': docs,
            'lineas': self.lineas,
            'direccion': diario.direccion.street if hasattr(diario, 'direccion') and diario.direccion else '',
            'current_company_id': self.env.company,
        }
