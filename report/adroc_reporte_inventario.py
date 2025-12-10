# -*- encoding: utf-8 -*-

from odoo import api, models, fields
import time
import datetime
import logging

_logger = logging.getLogger(__name__)


class AdrocReporteInventario(models.AbstractModel):
    _name = 'report.adroc_libros_guatemala.adroc_reporte_inventario'
    _description = "Reporte de inventario"

    def retornar_saldo_inicial_todos_anios(self, cuenta, fecha_desde, fecha_hasta):
        saldo_inicial = 0
        self.env.cr.execute(
            'select a.id, a.code as codigo, a.name as cuenta, sum(l.debit) as debe, sum(l.credit) as haber '
            'from account_move_line l join account_account a on(l.account_id = a.id)'
            'where a.id = %s and l.date < %s group by a.id, a.code, a.name,l.debit,l.credit',
            (cuenta, fecha_hasta)
        )
        for m in self.env.cr.dictfetchall():
            saldo_inicial += m['debe'] - m['haber']
        return saldo_inicial

    def retornar_saldo_inicial_inicio_anio(self, cuenta, fecha_desde, fecha_hasta):
        saldo_inicial = 0
        self.env.cr.execute(
            'select a.id, a.code as codigo, a.name as cuenta, sum(l.debit) as debe, sum(l.credit) as haber '
            'from account_move_line l join account_account a on(l.account_id = a.id)'
            'where a.id = %s and l.date < %s and l.date >= %s group by a.id, a.code, a.name,l.debit,l.credit',
            (cuenta, fecha_hasta, fecha_desde)
        )
        for m in self.env.cr.dictfetchall():
            saldo_inicial += m['debe'] - m['haber']
        return saldo_inicial

    def lineas(self, datos):
        totales = {}
        lineas_resumidas = {}
        lineas = {
            'activo': [], 'total_activo': 0,
            'pasivo': [], 'total_pasivo': 0,
            'capital': [], 'total_capital': 0,
        }
        agrupado = {'activo': [], 'pasivo': [], 'capital': []}
        totales['debe'] = 0
        totales['haber'] = 0
        totales['saldo_inicial'] = 0
        totales['saldo_final'] = 0
        account_ids = [x for x in datos['cuentas_id']]
        movimientos = self.env['account.move.line'].search([
            ('account_id', 'in', account_ids),
            ('date', '<=', datos['fecha_hasta']),
            ('date', '>=', datos['fecha_desde'])])

        accounts_str = ','.join([str(x) for x in datos['cuentas_id']])
        self.env.cr.execute(
            'select a.id, a.code as codigo, a.name as cuenta,a.internal_group as tipo_cuenta,'
            'a.include_initial_balance as balance_inicial, sum(l.debit) as debe, sum(l.credit) as haber '
            'from account_move_line l join account_account a on(l.account_id = a.id)'
            'where a.id in (' + accounts_str + ') and l.date >= %s and l.date <= %s '
            'group by a.id, a.code, a.name,a.internal_group,a.include_initial_balance ORDER BY a.code',
            (datos['fecha_desde'], datos['fecha_hasta'])
        )

        for r in self.env.cr.dictfetchall():
            totales['debe'] += r['debe']
            totales['haber'] += r['haber']
            linea = {
                'id': r['id'],
                'codigo': r['codigo'],
                'cuenta': r['cuenta'],
                'saldo_inicial': 0,
                'debe': r['debe'],
                'haber': r['haber'],
                'saldo_final': 0,
                'balance_inicial': r['balance_inicial']
            }
            if r['tipo_cuenta'] == 'asset':
                lineas['activo'].append(linea)
            elif r['tipo_cuenta'] == 'liability':
                lineas['pasivo'].append(linea)
            elif r['tipo_cuenta'] == 'equity':
                lineas['capital'].append(linea)

        for l in lineas['activo']:
            if not l['balance_inicial']:
                l['saldo_inicial'] += self.retornar_saldo_inicial_inicio_anio(l['id'], datos['fecha_desde'], datos['fecha_hasta'])
                l['saldo_final'] += l['saldo_inicial'] + l['debe'] - l['haber']
                totales['saldo_inicial'] += l['saldo_inicial']
                totales['saldo_final'] += l['saldo_final']
            else:
                l['saldo_inicial'] += self.retornar_saldo_inicial_todos_anios(l['id'], datos['fecha_desde'], datos['fecha_hasta'])
                l['saldo_final'] += l['saldo_inicial'] + l['debe'] - l['haber']
                totales['saldo_inicial'] += l['saldo_inicial']
                totales['saldo_final'] += l['saldo_final']

        for l in lineas['pasivo']:
            if not l['balance_inicial']:
                l['saldo_inicial'] += self.retornar_saldo_inicial_inicio_anio(l['id'], datos['fecha_desde'], datos['fecha_hasta'])
                l['saldo_final'] += l['saldo_inicial'] + l['debe'] - l['haber']
                totales['saldo_inicial'] += l['saldo_inicial']
                totales['saldo_final'] += l['saldo_final']
            else:
                l['saldo_inicial'] += self.retornar_saldo_inicial_todos_anios(l['id'], datos['fecha_desde'], datos['fecha_hasta'])
                l['saldo_final'] += l['saldo_inicial'] + l['debe'] - l['haber']
                totales['saldo_inicial'] += l['saldo_inicial']
                totales['saldo_final'] += l['saldo_final']

        for l in lineas['capital']:
            if not l['balance_inicial']:
                l['saldo_inicial'] += self.retornar_saldo_inicial_inicio_anio(l['id'], datos['fecha_desde'], datos['fecha_hasta'])
                l['saldo_final'] += l['saldo_inicial'] + l['debe'] - l['haber']
                totales['saldo_inicial'] += l['saldo_inicial']
                totales['saldo_final'] += l['saldo_final']
            else:
                l['saldo_inicial'] += self.retornar_saldo_inicial_todos_anios(l['id'], datos['fecha_desde'], datos['fecha_hasta'])
                l['saldo_final'] += l['saldo_inicial'] + l['debe'] - l['haber']
                totales['saldo_inicial'] += l['saldo_inicial']
                totales['saldo_final'] += l['saldo_final']

        return {'lineas': lineas, 'totales': totales}

    @api.model
    def _get_report_values(self, docids, data=None):
        model = self.env.context.get('active_model')
        docs = self.env[model].browse(self.env.context.get('active_ids', []))

        diario = self.env['account.move.line'].browse(data['form']['cuentas_id'][0])

        return {
            'doc_ids': self.ids,
            'doc_model': model,
            'data': data['form'],
            'docs': docs,
            'lineas': self.lineas,
            'current_company_id': self.env.company,
        }
