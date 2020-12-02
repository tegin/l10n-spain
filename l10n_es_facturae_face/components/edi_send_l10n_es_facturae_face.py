# Copyright 2020 Creu Blanca
# @author: Enric Tobella
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.addons.component.core import Component


class EdiOutputSendL10nEsFacturaeFace(Component):
    _name = "edi.output.send.l10n_es_facturae.l10n_es_facturae_face_output"
    _usage = "edi.webservice.send.face.l10n_es_facturae"
    _inherit = "edi.component.send.mixin"

    def _get_extra_attachment(self):
        return []

    def send(self):
        invoice = self.exchange_record.record
        response = self.backend.webservice_backend_id.call(
            "send",
            invoice.company_id.facturae_cert,
            invoice.company_id.facturae_cert_password,
            self.exchange_record._get_file_content(),
            self.exchange_record.exchange_filename,
            invoice.company_id.face_email,
            self._get_extra_attachment(),
        )
        self.exchange_record.write(
            {"external_identifier": response.factura.numeroRegistro}
        )
