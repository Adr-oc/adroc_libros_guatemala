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
            ('date', '<=', datos['fecha_hasta']),
            ('date', '>=', datos['fecha_desde']),
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

            tipo_cambio = 1
            if f.currency_id.id != f.company_id.currency_id.id:
                total = 0
                for l in f.line_ids:
                    if l.account_id.reconcile:
                        total += l.debit - l.credit
                if f.amount_total != 0:
                    tipo_cambio = abs(total / f.amount_total)

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
                'fecha': f.date,
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

            amount_json = json.loads(json.dumps(f.tax_totals))
            for l in filtered_lines:
                cantidad = (l.quantity)
                precio = (l.price_unit * (1 - (l.discount or 0.0) / 100.0)) * tipo_cambio
                if tipo == 'NCCQ' or tipo == 'NC':
                    precio = precio * -1

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

                r = self.env['account.move.line'].search([('move_id', '=', l.move_id.id)])
                taxes = self.env['account.tax'].search([('name', '!=', False)])
                price_subtotal = -(l.price_subtotal) if f.move_type != 'in_invoice' else (l.price_subtotal)
                if f.currency_id.id == 2:
                    tasa_cambio_rec = self.env['res.currency.rate'].search(
                        [('currency_id', '=', 2), ('name', '=', f.invoice_date)])
                    tasa_cambio = tasa_cambio_rec.inverse_company_rate if tasa_cambio_rec else 1
                    price_subtotal = price_subtotal * tasa_cambio

                linea['base'] += price_subtotal
                impuestos_extras = 0
                taxes_name = []
                for tax in taxes:
                    taxes_name.append(tax.name)
                if len(l.tax_ids) > 0:
                    linea[tipo_linea] += price_subtotal
                    for i in r:
                        i_name = str(i.name)
                        tax = -(i.credit) if f.move_type != 'in_invoice' else (i.debit)
                        is_valid_name = True if len(i_name) > 0 else False
                        if 'ISR' in i_name and i_name in taxes_name and is_valid_name:
                            linea_isr = abs(i.credit) if abs(i.credit) > 0 else abs(i.debit)
                            linea['isr'] = linea_isr

                        if 'IVA' in i_name and i_name in taxes_name and is_valid_name:
                            linea['iva'] = tax

                        elif i_name in taxes_name and is_valid_name:
                            linea[tipo_linea + '_exento'] += tax

                        if 'tasa municipal' in i_name.lower():
                            impuestos_extras += tax
                else:
                    linea[tipo_linea + '_exento'] = price_subtotal

            amount_untaxed = 0
            total_tax_amount = 0
            total_isr = 0
            for subtotal_group in amount_json["groups_by_subtotal"].values():
                for tax_group in subtotal_group:
                    if 'ISR' in tax_group['tax_group_name']:
                        total_isr += -(tax_group["tax_group_amount"]) if f.move_type != 'in_invoice' else (
                            tax_group["tax_group_amount"])

                    if 'ISR' not in tax_group['tax_group_name']:
                        total_tax_amount += -(tax_group["tax_group_amount"]) if f.move_type != 'in_invoice' else (
                            tax_group["tax_group_amount"])

            amount_untaxed = -amount_json['amount_untaxed'] if f.move_type != 'in_invoice' else (
                amount_json["amount_untaxed"])
            if f.currency_id.id == 2:
                tasa_cambio_rec = self.env['res.currency.rate'].search(
                    [('currency_id', '=', 2), ('name', '=', f.invoice_date)])
                tasa_cambio = tasa_cambio_rec.inverse_company_rate if tasa_cambio_rec else 1
                amount_untaxed = amount_untaxed * tasa_cambio
                total_tax_amount = total_tax_amount * tasa_cambio
                total_isr = total_isr * tasa_cambio

            r = self.env['account.move.line'].search([('move_id', '=', f.id)])
            total = 0
            for i in r:
                total += i.debit

            linea['total'] = total
            if tipo == 'NCCQ' or tipo == 'NC':
                linea['total'] = total * -1
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
