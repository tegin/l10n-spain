# Copyright 2020 Creu Blanca
# @author: Enric Tobella
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.addons.component.core import Component


class EDIBackendOutputComponentMixin(Component):
    _name = "edi.output.l10n_es_facturae"
    # TODO: Change inheritance
    # _inherit = "edi.component.output.mixin"

    def generate(self, exchange_record):
        # TODO: When changing the inheratance, remove from function and do:
        # exchange_record = self.exchange_record
        return exchange_record.record.get_facturae()[0]
