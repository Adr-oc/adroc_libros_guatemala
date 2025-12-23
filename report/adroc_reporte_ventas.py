# -*- encoding: utf-8 -*-

from odoo import api, models
from odoo.exceptions import UserError
import logging


class AdrocReporteVentas(models.AbstractModel):
    _name = 'report.adroc_libros_guatemala.adroc_reporte_ventas'
    _description = "Reporte de ventas"

    def lineas(self, datos):
        totales = {}

        totales['num_facturas'] = 0
        totales['compra'] = {'exento': 0, 'neto': 0, 'iva': 0, 'total': 0}
        totales['servicio'] = {'exento': 0, 'neto': 0, 'iva': 0, 'total': 0}
        totales['importacion'] = {'exento': 0, 'neto': 0, 'iva': 0, 'total': 0}
        totales['combustible'] = {'exento': 0, 'neto': 0, 'iva': 0, 'total': 0}

        journal_ids = [x for x in datos['diarios_id']]
        facturas = self.env['account.move'].search([
            ('state', 'in', ['posted', 'cancel']),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
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
            if f.move_type != 'out_invoice':
                tipo = 'NC'
            if hasattr(f, 'nota_debito') and f.nota_debito:
                tipo = 'ND'

            linea = {
                'estado': f.state,
                'tipo': tipo,
                'fecha': f.invoice_date,
                'serie': serie,
                'numero': numero,
                'cliente': f.partner_id.name,
                'nit': f.partner_id.vat,
                'compra': 0,
                'compra_exento': 0,
                'servicio': 0,
                'servicio_exento': 0,
                'combustible': 0,
                'combustible_exento': 0,
                'importacion': 0,
                'importacion_exento': 0,
                'base': 0,
                'iva': 0,
                'total': 0
            }

            # Si está anulada (pero tiene serie y número), agregar con valores en cero
            if f.state == 'cancel':
                lineas.append(linea)
                continue

            for l in f.invoice_line_ids:
                precio = (l.price_unit * (1-(l.discount or 0.0)/100.0)) * tipo_cambio
                if tipo == 'NC':
                    precio = precio * -1

                tipo_linea = f.tipo_gasto if hasattr(f, 'tipo_gasto') and f.tipo_gasto else 'mixto'
                if tipo_linea == 'mixto':
                    if l.product_id.type != 'service':
                        tipo_linea = 'compra'
                    else:
                        tipo_linea = 'servicio'

                r = l.tax_ids.compute_all(precio, currency=f.currency_id, quantity=l.quantity, product=l.product_id, partner=f.partner_id)

                linea['base'] += r['total_excluded']
                totales[tipo_linea]['total'] += r['total_excluded']
                if len(l.tax_ids) > 0:
                    linea[tipo_linea] += r['total_excluded']
                    totales[tipo_linea]['neto'] += r['total_excluded']
                    for i in r['taxes']:
                        if i['id'] == datos['impuesto_id'][0]:
                            linea['iva'] += i['amount']
                            totales[tipo_linea]['iva'] += i['amount']
                            totales[tipo_linea]['total'] += i['amount']
                        elif i['amount'] > 0:
                            linea[tipo_linea+'_exento'] += i['amount']
                            totales[tipo_linea]['exento'] += i['amount']
                else:
                    linea[tipo_linea+'_exento'] += r['total_excluded']
                    totales[tipo_linea]['exento'] += r['total_excluded']

                linea['total'] += precio * l.quantity

            lineas.append(linea)

        lineas = sorted(lineas, key=lambda i: str(i['fecha']) + str(i['numero']))

        if datos['resumido']:
            lineas_resumidas = {}
            for l in lineas:
                llave = l['tipo']+str(l['fecha'])
                if llave not in lineas_resumidas:
                    lineas_resumidas[llave] = dict(l)
                    lineas_resumidas[llave]['estado'] = 'open'
                    lineas_resumidas[llave]['cliente'] = 'Varios'
                    lineas_resumidas[llave]['nit'] = 'Varios'
                    lineas_resumidas[llave]['facturas'] = [l['numero']]
                else:
                    lineas_resumidas[llave]['compra'] += l['compra']
                    lineas_resumidas[llave]['compra_exento'] += l['compra_exento']
                    lineas_resumidas[llave]['servicio'] += l['servicio']
                    lineas_resumidas[llave]['servicio_exento'] += l['servicio_exento']
                    lineas_resumidas[llave]['combustible'] += l['combustible']
                    lineas_resumidas[llave]['combustible_exento'] += l['combustible_exento']
                    lineas_resumidas[llave]['importacion'] += l['importacion']
                    lineas_resumidas[llave]['importacion_exento'] += l['importacion_exento']
                    lineas_resumidas[llave]['base'] += l['base']
                    lineas_resumidas[llave]['iva'] += l['iva']
                    lineas_resumidas[llave]['total'] += l['total']
                    lineas_resumidas[llave]['facturas'].append(l['numero'])

            for l in lineas_resumidas.values():
                facturas = sorted(l['facturas'])
                l['numero'] = str(l['facturas'][0]) + ' al ' + str(l['facturas'][-1])

            lineas = sorted(lineas_resumidas.values(), key=lambda l: l['tipo']+str(l['fecha']))

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
            'direccion_diario': diario.direccion.street if hasattr(diario, 'direccion') and diario.direccion else '',
            'current_company_id': self.env.company,
        }
