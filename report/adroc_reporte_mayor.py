# -*- encoding: utf-8 -*-

from odoo import api, models, fields
import logging
from datetime import datetime


class AdrocReporteMayor(models.AbstractModel):
    _name = 'report.adroc_libros_guatemala.adroc_reporte_mayor'
    _description = "Reporte de mayor"

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
        totales = {}
        lineas_resumidas = {}
        lineas = []
        totales['debe'] = 0
        totales['haber'] = 0
        totales['saldo_inicial'] = 0
        totales['saldo_final'] = 0

        account_ids = [x for x in datos['cuentas_id']]
        accounts = self.env['account.account'].browse(account_ids)

        movimientos = self.env['account.move.line'].search([
            ('account_id', 'in', account_ids),
            ('date', '<=', datos['fecha_hasta']),
            ('date', '>=', datos['fecha_desde'])])

        if datos['agrupado_por_dia']:
            # Use ORM to avoid database schema issues
            # Get all move lines for the period grouped by date
            move_lines = self.env['account.move.line'].read_group(
                domain=[
                    ('account_id', 'in', account_ids),
                    ('date', '>=', datos['fecha_desde']),
                    ('date', '<=', datos['fecha_hasta'])
                ],
                fields=['move_name', 'name', 'account_id', 'date', 'debit', 'credit', 'journal_id'],
                groupby=['account_id', 'date', 'move_name', 'name', 'journal_id'],
                orderby='account_id, date',
                lazy=False
            )

            poliza = 0
            for r in move_lines:
                account = self.env['account.account'].browse(r['account_id'][0])
                totales['debe'] += r['debit']
                totales['haber'] += r['credit']
                poliza += 1
                linea = {
                    'id': account.id,
                    'fecha': r['date'],
                    'poliza': poliza,
                    'codigo': account.code,
                    'cuenta': account.name,
                    'descripcion': r['name'],
                    'move_name': r['move_name'],
                    'journal_id': self.env['account.journal'].browse(r['journal_id'][0]).name,
                    'saldo_inicial': 0,
                    'debe': r['debit'],
                    'haber': r['credit'],
                    'saldo_final': 0,
                    'balance_inicial': account.include_initial_balance
                }
                lineas.append(linea)

            cuentas_agrupadas = {}
            llave = 'codigo'
            for l in lineas:
                if l[llave] not in cuentas_agrupadas:
                    cuentas_agrupadas[l[llave]] = {
                        'codigo': l[llave],
                        'cuenta': l['cuenta'],
                        'saldo_inicial': 0,
                        'saldo_final': 0,
                        'fechas': [],
                        'total_debe': 0,
                        'total_haber': 0,
                        'diarios': {}
                    }

                    if not l['balance_inicial']:
                        cuentas_agrupadas[l[llave]]['saldo_inicial'] = self.retornar_saldo_inicial_inicio_anio(l['id'], datos['fecha_desde'])
                    else:
                        cuentas_agrupadas[l[llave]]['saldo_inicial'] = saldo = self.retornar_saldo_inicial_todos_anios(l['id'], datos['fecha_desde'])
                cuentas_agrupadas[l[llave]]['fechas'].append(l)

            for cuenta in cuentas_agrupadas.values():
                for fecha in cuenta['fechas']:
                    cuenta['total_debe'] += fecha['debe']
                    cuenta['total_haber'] += fecha['haber']
                cuenta['saldo_final'] += cuenta['saldo_inicial'] + cuenta['total_debe'] - cuenta['total_haber']
                lineas.append(cuenta)

            lineas = cuentas_agrupadas.values()

        if datos['agrupado_por_diario']:
            lineas_resumidas = {}
            for linea in lineas:
                diarios = {}
                for l in linea['fechas']:
                    diario_id = l['journal_id']
                    fecha = l['fecha']

                    if isinstance(fecha, str):
                        fecha = datetime.strptime(fecha, '%Y-%m-%d').date()

                    meses = {
                        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
                        5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
                        9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
                    }
                    mes = meses[fecha.month]

                    if diario_id not in diarios:
                        diarios[diario_id] = {}

                    if mes not in diarios[diario_id]:
                        diarios[diario_id][mes] = {
                            'debe': 0,
                            'haber': 0,
                            'descripcion': diario_id,
                            'mes': mes,
                        }

                    diarios[diario_id][mes]['debe'] += float(l['debe']) if l['debe'] else 0
                    diarios[diario_id][mes]['haber'] += float(l['haber']) if l['haber'] else 0

                lineas_resumidas[linea['codigo']] = {
                    'codigo': linea['codigo'],
                    'cuenta': linea['cuenta'],
                    'saldo_inicial': linea['saldo_inicial'],
                    'saldo_final': linea['saldo_final'],
                    'diarios': diarios,
                    'total_debe': linea['total_debe'],
                    'total_haber': linea['total_haber'],
                }

            lineas = list(lineas_resumidas.values())

        else:
            # Use ORM to avoid database schema issues
            move_lines = self.env['account.move.line'].read_group(
                domain=[
                    ('account_id', 'in', account_ids),
                    ('date', '>=', datos['fecha_desde']),
                    ('date', '<=', datos['fecha_hasta'])
                ],
                fields=['account_id', 'debit', 'credit'],
                groupby=['account_id', 'date'],
                orderby='account_id, date',
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
                lineas.append(linea)

            for l in lineas:
                if not l['balance_inicial']:
                    l['saldo_inicial'] += self.retornar_saldo_inicial_inicio_anio(l['id'], datos['fecha_desde'])
                    l['saldo_final'] += l['saldo_inicial'] + l['debe'] - l['haber']
                    totales['saldo_inicial'] += l['saldo_inicial']
                    totales['saldo_final'] += l['saldo_final']
                else:
                    l['saldo_inicial'] += self.retornar_saldo_inicial_todos_anios(l['id'], datos['fecha_desde'])
                    l['saldo_final'] += l['saldo_inicial'] + l['debe'] - l['haber']
                    totales['saldo_inicial'] += l['saldo_inicial']
                    totales['saldo_final'] += l['saldo_final']

        # Ensure all accounts are included, even if they have no movements
        for account in accounts:
            if account.code not in [linea['codigo'] for linea in lineas]:
                saldo_inicial = self.retornar_saldo_inicial_todos_anios(account.id, datos['fecha_desde'])
                lineas.append({
                    'codigo': account.code,
                    'cuenta': account.name,
                    'saldo_inicial': saldo_inicial,
                    'debe': 0,
                    'haber': 0,
                    'saldo_final': saldo_inicial,
                    'fechas': [],
                    'total_debe': 0,
                    'total_haber': 0,
                    'diarios': {}
                })

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
