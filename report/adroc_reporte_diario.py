# -*- encoding: utf-8 -*-

from odoo import api, models, fields
import logging


class AdrocReporteDiario(models.AbstractModel):
    _name = 'report.adroc_libros_guatemala.adroc_reporte_diario'
    _description = "Reporte de diarios"

    def retornar_saldo_inicial_todos_anios(self, cuenta, fecha_desde):
        # Use read_group for efficient aggregation on database side
        result = self.env['account.move.line'].read_group(
            domain=[
                ('account_id', '=', cuenta),
                ('date', '<', fecha_desde)
            ],
            fields=['debit', 'credit'],
            groupby=[],
            lazy=False
        )
        if result:
            return result[0]['debit'] - result[0]['credit']
        return 0

    def retornar_saldo_inicial_inicio_anio(self, cuenta, fecha_desde):
        fecha = fields.Date.from_string(fecha_desde)
        # Use read_group for efficient aggregation on database side
        result = self.env['account.move.line'].read_group(
            domain=[
                ('account_id', '=', cuenta),
                ('date', '<', fecha_desde),
                ('date', '>=', fecha.strftime('%Y-1-1'))
            ],
            fields=['debit', 'credit'],
            groupby=[],
            lazy=False
        )
        if result:
            return result[0]['debit'] - result[0]['credit']
        return 0

    def lineas(self, datos):
        totales = {'debe': 0, 'haber': 0, 'saldo_inicial': 0, 'saldo_final': 0}
        polizaCant = 0

        account_ids = [x for x in datos['cuentas_id']]

        if datos['agrupado_por_dia']:
            # Use ORM to avoid database schema issues
            move_lines = self.env['account.move.line'].read_group(
                domain=[
                    ('account_id', 'in', account_ids),
                    ('date', '>=', datos['fecha_desde']),
                    ('date', '<=', datos['fecha_hasta']),
                    ('move_id.state', '=', 'posted')
                ],
                fields=['date', 'account_id', 'debit', 'credit'],
                groupby=['date', 'account_id'],
                orderby='date, account_id',
                lazy=False
            )

            lineas = []
            for r in move_lines:
                account = self.env['account.account'].browse(r['account_id'][0])
                polizaCant += 1
                linea = {
                    'fecha': r['date'],
                    'poliza': polizaCant,
                    'codigo': account.code,
                    'cuenta': account.name,
                    'debe': r['debit'],
                    'haber': r['credit'],
                    'total_debe': r['debit'],
                    'total_haber': r['credit'],
                    'cuentas': [{
                        'codigo': account.code,
                        'cuenta': account.name,
                        'debe': r['debit'],
                        'haber': r['credit']
                    }]
                }
                lineas.append(linea)

            return {'lineas': lineas, 'totales': totales}
        else:
            # Use ORM to avoid database schema issues
            # Group by month (we'll extract the month from date in Python)
            move_lines = self.env['account.move.line'].search([
                ('account_id', 'in', account_ids),
                ('date', '>=', datos['fecha_desde']),
                ('date', '<=', datos['fecha_hasta']),
                ('move_id.state', '=', 'posted')
            ], order='date, journal_id')

            # Group results by month and journal
            grouped_data = {}
            for line in move_lines:
                mes = line.date.strftime('%Y-%m')
                diario = line.journal_id.name
                account = line.account_id

                key = (mes, diario, account.id)
                if key not in grouped_data:
                    grouped_data[key] = {
                        'cuenta_id': account.id,
                        'codigo': account.code,
                        'cuenta': account.name,
                        'balance_inicial': account.include_initial_balance,
                        'mes': mes,
                        'diario': diario,
                        'debe': 0,
                        'haber': 0
                    }
                grouped_data[key]['debe'] += line.debit
                grouped_data[key]['haber'] += line.credit

            resultados_por_mes = {}

            for r in grouped_data.values():
                mes = r['mes']
                diario = r['diario']

                if mes not in resultados_por_mes:
                    resultados_por_mes[mes] = {'diarios': {}, 'totales_mes': {'debe': 0, 'haber': 0}}
                if diario not in resultados_por_mes[mes]['diarios']:
                    resultados_por_mes[mes]['diarios'][diario] = {'cuentas': [], 'totales_diario': {'debe': 0, 'haber': 0}}

                polizaCant += 1
                linea = {
                    'id': r['cuenta_id'],
                    'codigo': r['codigo'],
                    'cuenta': r['cuenta'],
                    'poliza': polizaCant,
                    'descripcion_poliza': 1,
                    'saldo_inicial': 0,
                    'debe': r['debe'],
                    'haber': r['haber'],
                    'saldo_final': 0,
                    'balance_inicial': r['balance_inicial']
                }

                if not linea['balance_inicial']:
                    linea['saldo_inicial'] += self.retornar_saldo_inicial_inicio_anio(linea['id'], datos['fecha_desde'])
                else:
                    linea['saldo_inicial'] += self.retornar_saldo_inicial_todos_anios(linea['id'], datos['fecha_desde'])

                linea['saldo_final'] += linea['saldo_inicial'] + linea['debe'] - linea['haber']

                resultados_por_mes[mes]['diarios'][diario]['totales_diario']['debe'] += linea['debe']
                resultados_por_mes[mes]['diarios'][diario]['totales_diario']['haber'] += linea['haber']
                resultados_por_mes[mes]['diarios'][diario]['cuentas'].append(linea)

                resultados_por_mes[mes]['totales_mes']['debe'] += linea['debe']
                resultados_por_mes[mes]['totales_mes']['haber'] += linea['haber']

                totales['debe'] += linea['debe']
                totales['haber'] += linea['haber']
                totales['saldo_inicial'] += linea['saldo_inicial']
                totales['saldo_final'] += linea['saldo_final']

            return {'resultados_por_mes': resultados_por_mes, 'totales': totales}

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
