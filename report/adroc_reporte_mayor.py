# -*- encoding: utf-8 -*-

from odoo import api, models, fields
import logging
from datetime import datetime


class AdrocReporteMayor(models.AbstractModel):
    _name = 'report.adroc_libros_guatemala.adroc_reporte_mayor'
    _description = "Reporte de mayor"

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

        accounts_str = ','.join([str(x) for x in datos['cuentas_id']])
        if datos['agrupado_por_dia']:
            self.env.cr.execute(
                'select l.move_name, l.name as descripcion, a.id, a.code as codigo, a.name as cuenta, '
                'l.date as fecha, a.include_initial_balance as balance_inicial, sum(l.debit) as debe, '
                'sum(l.credit) as haber, l.journal_id '
                'from account_move_line l join account_account a on(l.account_id = a.id) '
                'where a.id in (' + accounts_str + ') and l.date >= %s and l.date <= %s '
                'group by l.move_name, l.name, a.id, a.code, a.name, l.date, a.include_initial_balance, l.journal_id '
                'ORDER BY a.code, l.date',
                (datos['fecha_desde'], datos['fecha_hasta'])
            )

            poliza = 0
            for r in self.env.cr.dictfetchall():
                totales['debe'] += r['debe']
                totales['haber'] += r['haber']
                poliza += 1
                linea = {
                    'id': r['id'],
                    'fecha': r['fecha'],
                    'poliza': poliza,
                    'codigo': r['codigo'],
                    'cuenta': r['cuenta'],
                    'descripcion': r['descripcion'],
                    'move_name': r['move_name'],
                    'journal_id': self.env['account.journal'].browse(r['journal_id']).name,
                    'saldo_inicial': 0,
                    'debe': r['debe'],
                    'haber': r['haber'],
                    'saldo_final': 0,
                    'balance_inicial': r['balance_inicial']
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
            self.env.cr.execute(
                'select a.id, a.code as codigo, a.name as cuenta, a.include_initial_balance as balance_inicial, '
                'sum(l.debit) as debe, sum(l.credit) as haber '
                'from account_move_line l join account_account a on(l.account_id = a.id)'
                'where a.id in (' + accounts_str + ') and l.date >= %s and l.date <= %s '
                'group by a.id, a.code, a.name,a.include_initial_balance, l.date ORDER BY a.code, l.date',
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
