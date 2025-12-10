# -*- encoding: utf-8 -*-

from odoo import api, models
import logging


class AdrocReportePartida(models.AbstractModel):
    _name = 'report.adroc_libros_guatemala.adroc_reporte_partida'
    _description = "Reporte de partida"

    @api.model
    def _get_report_values(self, docids, data=None):
        return self.get_report_values(docids, data)

    @api.model
    def get_report_values(self, docids, data=None):
        model = 'account.move'
        docs = self.env[model].browse(docids)

        return {
            'doc_ids': docids,
            'doc_model': model,
            'docs': docs,
            'current_company_id': self.env.company,
        }
