# Copyright 2020 Creu Blanca
# @author: Enric Tobella
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json

from zeep import helpers

from odoo import _
from odoo.exceptions import UserError

from odoo.addons.component.core import Component


class EdiWebServiceReceiveFaceL10nEsFacturaeFaceUpdate(Component):
    _name = "edi.webservice.receive.face.l10n_es_facturae_face_update"
    _usage = "edi.webservice.receive.face.l10n_es_facturae_face_update"
    _inherit = "edi.component.receive.mixin"

    def receive(self):
        invoice = self.exchange_record.record
        response = self.backend.webservice_backend_id.call(
            "consult_invoice",
            invoice.company_id.facturae_cert,
            invoice.company_id.facturae_cert_password,
            self.exchange_record.parent_id.external_identifier,
        )
        if response.resultado.codigo != "0":
            raise UserError(
                _("Connection with FACe returned error %s - %s")
                % (response.resultado.codigo, response.resultado.descripcion)
            )
        return json.dumps(helpers.serialize_object(response.factura))
