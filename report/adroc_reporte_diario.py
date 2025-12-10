# -*- encoding: utf-8 -*-

from odoo import api, models, fields
import logging


class AdrocReporteDiario(models.AbstractModel):
    _name = 'report.adroc_libros_guatemala.adroc_reporte_diario'
    _description = "Reporte de diarios"

    def retornar_saldo_inicial_todos_anios(self, cuenta, fecha_desde):
        saldo_inicial = 0
        self.env.cr.execute(
            'select a.id, a.code as codigo, a.name as cuenta, sum(l.debit) as debe, sum(l.credit) as haber '
            'from account_move_line l join account_account a on(l.account_id = a.id)'
            'where a.id = %s and l.date < %s group by a.id, a.code, a.name,l.debit,l.credit',
            (cuenta, fecha_desde)
        )
        for m in self.env.cr.dictfetchall():
            saldo_inicial += m['debe'] - m['haber']
        return saldo_inicial

    def retornar_saldo_inicial_inicio_anio(self, cuenta, fecha_desde):
        saldo_inicial = 0
        fecha = fields.Date.from_string(fecha_desde)
        self.env.cr.execute(
            'select a.id, a.code as codigo, a.name as cuenta, sum(l.debit) as debe, sum(l.credit) as haber '
            'from account_move_line l join account_account a on(l.account_id = a.id)'
            'where a.id = %s and l.date < %s and l.date >= %s group by a.id, a.code, a.name,l.debit,l.credit',
            (cuenta, fecha_desde, fecha.strftime('%Y-1-1'))
        )
        for m in self.env.cr.dictfetchall():
            saldo_inicial += m['debe'] - m['haber']
        return saldo_inicial

    def lineas(self, datos):
        totales = {'debe': 0, 'haber': 0, 'saldo_inicial': 0, 'saldo_final': 0}
        polizaCant = 0

        account_ids = [x for x in datos['cuentas_id']]
        accounts_str = ','.join([str(x) for x in datos['cuentas_id']])

        if datos['agrupado_por_dia']:
            self.env.cr.execute('''
                SELECT
                    l.date AS fecha,
                    a.id AS cuenta_id,
                    a.code AS codigo,
                    a.name AS cuenta,
                    SUM(l.debit) AS debe,
                    SUM(l.credit) AS haber
                FROM
                    account_move_line l
                JOIN
                    account_account a ON (l.account_id = a.id)
                JOIN
                    account_move m ON (l.move_id = m.id)
                WHERE
                    a.id IN (%s)
                    AND l.date >= %%s
                    AND l.date <= %%s
                    AND m.state = 'posted'
                GROUP BY
                    l.date, a.id, a.code, a.name
                ORDER BY
                    l.date, a.code
            ''' % accounts_str, (datos['fecha_desde'], datos['fecha_hasta']))

            lineas = []
            for r in self.env.cr.dictfetchall():
                polizaCant += 1
                linea = {
                    'fecha': r['fecha'],
                    'poliza': polizaCant,
                    'codigo': r['codigo'],
                    'cuenta': r['cuenta'],
                    'debe': r['debe'],
                    'haber': r['haber'],
                    'total_debe': r['debe'],
                    'total_haber': r['haber'],
                    'cuentas': [{
                        'codigo': r['codigo'],
                        'cuenta': r['cuenta'],
                        'debe': r['debe'],
                        'haber': r['haber']
                    }]
                }
                lineas.append(linea)

            return {'lineas': lineas, 'totales': totales}
        else:
            self.env.cr.execute('''
                SELECT
                    a.id AS cuenta_id,
                    a.code AS codigo,
                    a.name AS cuenta,
                    a.include_initial_balance AS balance_inicial,
                    TO_CHAR(l.date, 'YYYY-MM') AS mes,
                    j.name AS diario,
                    SUM(l.debit) AS debe,
                    SUM(l.credit) AS haber
                FROM
                    account_move_line l
                JOIN
                    account_account a ON (l.account_id = a.id)
                JOIN
                    account_journal j ON (l.journal_id = j.id)
                JOIN
                    account_move m ON (l.move_id = m.id)
                WHERE
                    a.id IN (%s)
                    AND l.date >= %%s
                    AND l.date <= %%s
                    AND m.state = 'posted'
                GROUP BY
                    a.id, a.code, a.name, a.include_initial_balance,
                    TO_CHAR(l.date, 'YYYY-MM'), j.name
                ORDER BY
                    TO_CHAR(l.date, 'YYYY-MM'), j.name, a.code
            ''' % accounts_str, (datos['fecha_desde'], datos['fecha_hasta']))

            resultados_por_mes = {}

            for r in self.env.cr.dictfetchall():
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
