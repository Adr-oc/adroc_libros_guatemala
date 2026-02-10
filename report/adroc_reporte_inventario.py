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
        # Use read_group for efficient aggregation on database side
        result = self.env['account.move.line'].read_group(
            domain=[
                ('account_id', '=', cuenta),
                ('date', '<', fecha_hasta)
            ],
            fields=['debit', 'credit'],
            groupby=[],
            lazy=False
        )
        if result:
            return result[0]['debit'] - result[0]['credit']
        return 0

    def retornar_saldo_inicial_inicio_anio(self, cuenta, fecha_desde, fecha_hasta):
        # Use read_group for efficient aggregation on database side
        result = self.env['account.move.line'].read_group(
            domain=[
                ('account_id', '=', cuenta),
                ('date', '<', fecha_hasta),
                ('date', '>=', fecha_desde)
            ],
            fields=['debit', 'credit'],
            groupby=[],
            lazy=False
        )
        if result:
            return result[0]['debit'] - result[0]['credit']
        return 0

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

        # Use ORM to avoid database schema issues
        move_lines = self.env['account.move.line'].read_group(
            domain=[
                ('account_id', 'in', account_ids),
                ('date', '>=', datos['fecha_desde']),
                ('date', '<=', datos['fecha_hasta'])
            ],
            fields=['account_id', 'debit', 'credit'],
            groupby=['account_id'],
            orderby='account_id',
            lazy=False
        )

        for r in move_lines:
            account = self.env['account.account'].browse(r['account_id'][0])
            totales['debe'] += r['debit']
            totales['haber'] += r['credit']
            linea = {
                'id': account.id,
                'codigo': account.code,
                'cuenta': account.name,
                'saldo_inicial': 0,
                'debe': r['debit'],
                'haber': r['credit'],
                'saldo_final': 0,
                'balance_inicial': account.include_initial_balance
            }
            if account.internal_group == 'asset':
                lineas['activo'].append(linea)
            elif account.internal_group == 'liability':
                lineas['pasivo'].append(linea)
            elif account.internal_group == 'equity':
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
