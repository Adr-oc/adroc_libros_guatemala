# -*- encoding: utf-8 -*-

{
    'name': 'ADROC - Libros de Guatemala',
    'version': '19.0.1.0.0',
    'category': 'Localization',
    'summary': 'Reportes requeridos por la SAT para Guatemala',
    'description': """
        Libros contables requeridos por la SAT para llevar una contabilidad en Guatemala.

        Incluye:
        - Libro de Banco
        - Libro de Compras
        - Libro de Ventas
        - Libro Diario
        - Libro Mayor General
        - Libro de Inventario
        - Reporte de Partida
        - Reporte Top Proveedores
    """,
    'author': 'ADROC',
    'license': 'LGPL-3',
    'depends': ['account', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/report.xml',
        'views/reporte_banco.xml',
        'views/reporte_compras.xml',
        'views/reporte_ventas.xml',
        'views/reporte_diario.xml',
        'views/reporte_mayor.xml',
        'views/reporte_inventario.xml',
        'views/reporte_partida.xml',
        'views/reporte_top_proveedores.xml',
    ],
    'auto_install': False,
    'installable': True,
}
