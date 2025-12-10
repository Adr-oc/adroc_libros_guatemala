# -*- encoding: utf-8 -*-

from odoo import api, models, fields
import logging

_logger = logging.getLogger(__name__)


class AdrocTopProveedores(models.AbstractModel):
    _name = 'report.adroc_libros_guatemala.adroc_reporte_top_proveedores'
    _description = "Reporte top proveedores"

    def lineas(self, datos):
        """
        Obtiene las lineas del reporte de top proveedores.
        Usa parametros SQL seguros para evitar SQL injection.
        """
        proveedor_ids = datos.get('proveedor_id', [])
        if not proveedor_ids:
            return {'lineas': []}

        lineas = []

        # Query segura usando %s para parametros y tuple() para IN clause
        query = """
            SELECT
                COUNT(*) as cant_documentos,
                COALESCE(SUM(am.amount_total), 0) as total,
                rp.id,
                rp.display_name,
                rp.vat
            FROM res_partner rp
            INNER JOIN account_move am ON rp.id = am.partner_id
            WHERE am.move_type = 'in_invoice'
                AND am.state = 'posted'
                AND rp.id IN %s
                AND am.date >= %s
                AND am.date <= %s
            GROUP BY rp.id, rp.display_name, rp.vat
            ORDER BY total DESC NULLS LAST
        """

        # Usar tuple para el IN clause (requerido por psycopg2)
        self.env.cr.execute(query, (
            tuple(proveedor_ids),
            datos['fecha_desde'],
            datos['fecha_hasta']
        ))

        for r in self.env.cr.dictfetchall():
            linea = {
                'display_name': r['display_name'] or '',
                'vat': r['vat'] or '',
                'cant_documentos': r['cant_documentos'] or 0,
                'total_facturas': float(r['total'] or 0)
            }
            lineas.append(linea)

        return {'lineas': lineas}

    @api.model
    def _get_report_values(self, docids, data=None):
        model = self.env.context.get('active_model')

        return {
            'doc_model': model,
            'data': data['form'],
            'lineas': self.lineas,
            'current_company_id': self.env.company,
        }
