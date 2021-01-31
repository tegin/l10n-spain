# Copyright 2016 Serv. Tecnol. Avanzados - Pedro M. Baeza
# Copyright 2017 Creu Blanca
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import base64
import logging
from datetime import timedelta

from lxml import etree
from mock import patch
from OpenSSL import crypto

from odoo import exceptions, fields
from odoo.tests import common

try:
    import xmlsig
except (ImportError, IOError) as err:
    logging.info(err)


class CommonTest(common.TransactionCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # We want to avoid testing on the CommonTest class
        if (
            self.test_class == "CommonTest"
            and self.__module__ == "odoo.addons.l10n_es_facturae.tests.common"
        ):
            self.test_tags -= {"at_install"}

    def setUp(self):
        super().setUp()
        self.tax = self.env["account.tax"].create(
            {
                "name": "Test tax",
                "amount_type": "percent",
                "amount": 21,
                "type_tax_use": "sale",
                "facturae_code": "01",
            }
        )

        self.state = self.env["res.country.state"].create(
            {"name": "Ciudad Real", "code": "13", "country_id": self.ref("base.es")}
        )
        self.partner = self.env["res.partner"].create(
            {
                "name": "Cliente de prueba",
                "street": "C/ Ejemplo, 13",
                "zip": "13700",
                "city": "Tomelloso",
                "state_id": self.state.id,
                "country_id": self.ref("base.es"),
                "vat": "ES05680675C",
                "facturae": True,
                "attach_invoice_as_annex": False,
                "organo_gestor": "U00000038",
                "unidad_tramitadora": "U00000038",
                "oficina_contable": "U00000038",
            }
        )
        main_company = self.env.ref("base.main_company")
        main_company.vat = "ESA12345674"
        main_company.partner_id.country_id = self.ref("base.uk")
        self.env["res.currency.rate"].search(
            [("currency_id", "=", main_company.currency_id.id)]
        ).write({"company_id": False})
        bank_obj = self.env["res.partner.bank"]
        self.bank = bank_obj.search(
            [("acc_number", "=", "FR20 1242 1242 1242 1242 1242 124")], limit=1
        )
        if not self.bank:
            self.bank = bank_obj.create(
                {
                    "acc_number": "FR20 1242 1242 1242 1242 1242 124",
                    "partner_id": main_company.partner.id,
                    "bank_id": self.env["res.bank"]
                    .search([("bic", "=", "PSSTFRPPXXX")], limit=1)
                    .id,
                }
            )
        self.payment_method = self.env["account.payment.method"].create(
            {
                "name": "inbound_mandate",
                "code": "inbound_mandate",
                "payment_type": "inbound",
                "bank_account_required": False,
                "active": True,
            }
        )
        payment_methods = self.env["account.payment.method"].search(
            [("payment_type", "=", "inbound")]
        )
        self.journal = self.env["account.journal"].create(
            {
                "name": "Test journal",
                "code": "TEST",
                "type": "bank",
                "company_id": main_company.id,
                "bank_account_id": self.bank.id,
                "inbound_payment_method_ids": [(6, 0, payment_methods.ids)],
            }
        )

        self.sale_journal = self.env["account.journal"].create(
            {
                "name": "Sale journal",
                "code": "SALE_TEST",
                "type": "sale",
                "company_id": main_company.id,
            }
        )
        self.payment_mode = self.env["account.payment.mode"].create(
            {
                "name": "Test payment mode",
                "bank_account_link": "fixed",
                "fixed_journal_id": self.journal.id,
                "payment_method_id": self.env.ref(
                    "payment.account_payment_method_electronic_in"
                ).id,
                "show_bank_account_from_journal": True,
                "facturae_code": "01",
            }
        )

        self.payment_mode_02 = self.env["account.payment.mode"].create(
            {
                "name": "Test payment mode 02",
                "bank_account_link": "fixed",
                "fixed_journal_id": self.journal.id,
                "payment_method_id": self.payment_method.id,
                "show_bank_account_from_journal": True,
                "facturae_code": "02",
            }
        )

        self.account = self.env["account.account"].create(
            {
                "company_id": main_company.id,
                "name": "Facturae Product account",
                "code": "facturae_product",
                "user_type_id": self.env.ref("account.data_account_type_revenue").id,
            }
        )
        self.move = self.env["account.move"].create(
            {
                "partner_id": self.partner.id,
                # "account_id": self.partner.property_account_receivable_id.id,
                "journal_id": self.sale_journal.id,
                "invoice_date": "2016-03-12",
                "payment_mode_id": self.payment_mode.id,
                "type": "out_invoice",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.env.ref(
                                "product.product_delivery_02"
                            ).id,
                            "account_id": self.account.id,
                            "name": "Producto de prueba",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "tax_ids": [(6, 0, self.tax.ids)],
                        },
                    )
                ],
            }
        )
        self.move.refresh()
        self.move_line = self.move.invoice_line_ids

        self.move_02 = self.env["account.move"].create(
            {
                "partner_id": self.partner.id,
                # "account_id": self.partner.property_account_receivable_id.id,
                "journal_id": self.sale_journal.id,
                "invoice_date": "2016-03-12",
                "payment_mode_id": self.payment_mode_02.id,
                "type": "out_invoice",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.env.ref(
                                "product.product_delivery_02"
                            ).id,
                            "account_id": self.account.id,
                            "name": "Producto de prueba",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "tax_ids": [(6, 0, self.tax.ids)],
                        },
                    )
                ],
            }
        )
        self.move_02.refresh()

        self.move_line_02 = self.move_02.invoice_line_ids
        self.partner.vat = "ES05680675C"
        self.partner.is_company = False
        self.partner.firstname = "Cliente"
        self.partner.lastname = "de Prueba"
        self.partner.country_id = self.ref("base.us")
        self.partner.state_id = self.ref("base.state_us_2")
        self.main_company = self.env.ref("base.main_company")
        self.wizard = self.env["create.facturae"].create({})
        self.fe = "http://www.facturae.es/Facturae/2009/v3.2/Facturae"
        self.first_check_amount = ["190.310000", "190.310000", "190.31", "39.97"]
        self.second_check_amount = [
            "190.310000",
            "133.220000",
            "133.22",
            "27.98",
            "57.090000",
        ]

    def test_facturae_generation(self):
        self.move.action_post()
        self.move.name = "2999/99999"
        self.wizard.with_context(
            active_ids=self.move.ids, active_model="account.move"
        ).create_facturae_file()
        generated_facturae = etree.fromstring(base64.b64decode(self.wizard.facturae))
        self.assertEqual(
            generated_facturae.xpath(
                "/fe:Facturae/Parties/SellerParty/TaxIdentification/"
                "TaxIdentificationNumber",
                namespaces={"fe": self.fe},
            )[0].text,
            self.env.ref("base.main_company").vat,
        )
        self.assertEqual(
            generated_facturae.xpath(
                "/fe:Facturae/Invoices/Invoice/InvoiceHeader/InvoiceNumber",
                namespaces={"fe": self.fe},
            )[0].text,
            self.move.name,
        )
        self.assertFalse(
            generated_facturae.xpath(
                "/fe:Facturae/Invoices/Invoice/AdditionalData/"
                "RelatedDocuments/Attachments",
                namespaces={"fe": self.fe},
            ),
        )

    def test_facturae_with_attachments(self):
        self.move.action_post()
        self.move.name = "2999/99999"
        self.partner.attach_invoice_as_annex = True
        with patch(
            "odoo.addons.base.models.ir_actions_report.IrActionsReport.render"
        ) as ptch:
            ptch.return_value = (b"1234", "pdf")
            self.wizard.with_context(
                force_report_rendering=True,
                active_ids=self.move.ids,
                active_model="account.move",
            ).create_facturae_file()
        generated_facturae = etree.fromstring(base64.b64decode(self.wizard.facturae))
        self.assertTrue(
            generated_facturae.xpath(
                "/fe:Facturae/Invoices/Invoice/AdditionalData/" "RelatedDocuments",
                namespaces={"fe": self.fe},
            ),
        )
        self.assertTrue(
            generated_facturae.xpath(
                "/fe:Facturae/Invoices/Invoice/AdditionalData/"
                "RelatedDocuments/Attachment",
                namespaces={"fe": self.fe},
            ),
        )

    def test_bank(self):
        self.bank.bank_id.bic = "CAIXESBB"
        with self.assertRaises(exceptions.ValidationError):
            self.move.validate_facturae_fields()
        with self.assertRaises(exceptions.ValidationError):
            self.move_02.validate_facturae_fields()
        self.bank.bank_id.bic = "CAIXESBBXXX"
        self.bank.acc_number = "1111"
        with self.assertRaises(exceptions.ValidationError):
            self.move.validate_facturae_fields()
        with self.assertRaises(exceptions.ValidationError):
            self.move_02.validate_facturae_fields()
        self.bank.acc_number = "BE96 9988 7766 5544"

    def test_validation_error(self):
        self.main_company.partner_id.country_id = False
        self.move.action_post()
        self.move.name = "2999/99999"
        with self.assertRaises(exceptions.UserError):
            self.env["create.facturae"].with_context(
                active_ids=self.move.ids, active_model="account.move"
            ).create_facturae_file()

    def test_signature(self):
        self.move.action_post()
        self.move.name = "2999/99999"
        pkcs12 = crypto.PKCS12()
        pkey = crypto.PKey()
        pkey.generate_key(crypto.TYPE_RSA, 512)
        x509 = crypto.X509()
        x509.set_pubkey(pkey)
        x509.set_serial_number(0)
        x509.get_subject().CN = "me"
        x509.set_issuer(x509.get_subject())
        x509.gmtime_adj_notBefore(0)
        x509.gmtime_adj_notAfter(10 * 365 * 24 * 60 * 60)
        x509.sign(pkey, "md5")
        pkcs12.set_privatekey(pkey)
        pkcs12.set_certificate(x509)
        self.main_company.facturae_cert = base64.b64encode(
            pkcs12.export(passphrase="password")
        )
        self.main_company.facturae_cert_password = "password"
        self.main_company.partner_id.country_id = self.ref("base.es")
        self.wizard.with_context(
            active_ids=self.move.ids, active_model="account.move"
        ).create_facturae_file()
        generated_facturae = etree.fromstring(base64.b64decode(self.wizard.facturae))
        ns = "http://www.w3.org/2000/09/xmldsig#"
        self.assertEqual(
            len(generated_facturae.xpath("//ds:Signature", namespaces={"ds": ns})), 1
        )

        node = generated_facturae.find(".//ds:Signature", {"ds": ns})
        ctx = xmlsig.SignatureContext()
        certificate = crypto.load_pkcs12(
            base64.b64decode(self.main_company.facturae_cert), "password"
        )
        certificate.set_ca_certificates(None)
        verification_error = False
        error_message = ""
        try:
            ctx.verify(node)
        except Exception as e:
            verification_error = True
            error_message = str(e)
            pass
        self.assertEqual(
            verification_error,
            False,
            "Error found during verification of the signature of "
            + "the move: %s" % error_message,
        )

    def test_refund(self):
        self.move.action_post()
        self.move.name = "2999/99999"
        motive = "Description motive"
        refund = self.env["account.move.reversal"].create(
            {"refund_reason": "01", "reason": motive}
        )
        refund_result = refund.with_context(
            active_ids=self.move.ids, active_model=self.move._name
        ).reverse_moves()
        domain = refund_result.get("domain", False)
        if not domain:
            domain = [("id", "=", refund_result["res_id"])]
        refund_inv = self.env["account.move"].search(domain)
        self.assertIn(motive, refund_inv.ref)
        self.assertEqual(refund_inv.facturae_refund_reason, "01")
        refund_inv.action_post()
        refund_inv.name = "2998/99999"
        self.wizard.with_context(
            active_ids=refund_inv.ids, active_model="account.move"
        ).create_facturae_file()
        with self.assertRaises(exceptions.UserError):
            self.wizard.with_context(
                active_ids=[self.move_02.id, self.move.id], active_model="account.move",
            ).create_facturae_file()

    def test_constrains_01(self):
        move = self.env["account.move"].create(
            {
                "partner_id": self.partner.id,
                # "account_id": self.partner.property_account_receivable_id.id,
                "journal_id": self.journal.id,
                "invoice_date": "2016-03-12",
                "payment_mode_id": self.payment_mode.id,
            }
        )
        line = self.env["account.move.line"].create(
            {
                "product_id": self.env.ref("product.product_delivery_02").id,
                "account_id": self.account.id,
                "move_id": move.id,
                "name": "Producto de prueba",
                "quantity": 1.0,
                "price_unit": 100.0,
                "tax_ids": [(6, 0, self.tax.ids)],
            }
        )
        with self.assertRaises(exceptions.ValidationError):
            line.facturae_start_date = fields.Date.today()

    def test_constrains_02(self):
        move = self.env["account.move"].create(
            {
                "partner_id": self.partner.id,
                # "account_id": self.partner.property_account_receivable_id.id,
                "journal_id": self.journal.id,
                "invoice_date": "2016-03-12",
                "payment_mode_id": self.payment_mode.id,
            }
        )
        line = self.env["account.move.line"].create(
            {
                "product_id": self.env.ref("product.product_delivery_02").id,
                "account_id": self.account.id,
                "move_id": move.id,
                "name": "Producto de prueba",
                "quantity": 1.0,
                "price_unit": 100.0,
                "tax_ids": [(6, 0, self.tax.ids)],
            }
        )
        with self.assertRaises(exceptions.ValidationError):
            line.facturae_end_date = fields.Date.today()

    def test_constrains_03(self):
        move = self.env["account.move"].create(
            {
                "partner_id": self.partner.id,
                # "account_id": self.partner.property_account_receivable_id.id,
                "journal_id": self.journal.id,
                "invoice_date": "2016-03-12",
                "payment_mode_id": self.payment_mode.id,
            }
        )
        line = self.env["account.move.line"].create(
            {
                "product_id": self.env.ref("product.product_delivery_02").id,
                "account_id": self.account.id,
                "move_id": move.id,
                "name": "Producto de prueba",
                "quantity": 1.0,
                "price_unit": 100.0,
                "tax_ids": [(6, 0, self.tax.ids)],
            }
        )
        with self.assertRaises(exceptions.ValidationError):
            line.write(
                {
                    "facturae_end_date": fields.Date.today(),
                    "facturae_start_date": fields.Date.to_string(
                        fields.Date.to_date(fields.Date.today()) + timedelta(days=1)
                    ),
                }
            )

    def test_constrains_04(self):
        move = self.env["account.move"].create(
            {
                "partner_id": self.partner.id,
                # "account_id": self.partner.property_account_receivable_id.id,
                "journal_id": self.journal.id,
                "invoice_date": "2016-03-12",
                "payment_mode_id": self.payment_mode.id,
            }
        )
        with self.assertRaises(exceptions.ValidationError):
            move.facturae_start_date = fields.Date.today()

    def test_constrains_05(self):
        move = self.env["account.move"].create(
            {
                "partner_id": self.partner.id,
                # "account_id": self.partner.property_account_receivable_id.id,
                "journal_id": self.journal.id,
                "invoice_date": "2016-03-12",
                "payment_mode_id": self.payment_mode.id,
            }
        )
        with self.assertRaises(exceptions.ValidationError):
            move.facturae_end_date = fields.Date.today()

    def test_constrains_06(self):
        move = self.env["account.move"].create(
            {
                "partner_id": self.partner.id,
                # "account_id": self.partner.property_account_receivable_id.id,
                "journal_id": self.journal.id,
                "invoice_date": "2016-03-12",
                "payment_mode_id": self.payment_mode.id,
            }
        )
        with self.assertRaises(exceptions.ValidationError):
            move.write(
                {
                    "facturae_end_date": fields.Date.today(),
                    "facturae_start_date": fields.Date.to_string(
                        fields.Date.to_date(fields.Date.today()) + timedelta(days=1)
                    ),
                }
            )

    def test_views(self):
        action = self.move_line.button_edit_facturae_fields()
        item = self.env[action["res_model"]].browse(action["res_id"])
        self.assertEqual(item, self.move_line)

    def _check_amounts(self, move, wo_discount, subtotal, base, tax, discount=0):
        move.action_post()
        move.name = "2999/99999"
        self.wizard.with_context(
            active_ids=move.ids, active_model="account.move"
        ).create_facturae_file()
        facturae_xml = etree.fromstring(base64.b64decode(self.wizard.facturae))
        self.assertEqual(
            facturae_xml.xpath("//InvoiceLine/TotalCost")[0].text, wo_discount,
        )
        self.assertEqual(
            facturae_xml.xpath("//InvoiceLine/GrossAmount")[0].text, subtotal,
        )
        self.assertEqual(
            facturae_xml.xpath("//TaxesOutputs//TaxableBase/TotalAmount")[0].text, base,
        )
        self.assertEqual(
            facturae_xml.xpath("//TaxesOutputs//TaxAmount/TotalAmount")[0].text, tax,
        )
        if discount:
            self.assertEqual(
                facturae_xml.xpath("//InvoiceLine//DiscountAmount")[0].text, discount,
            )

    def test_move_rounding(self):
        self.main_company.tax_calculation_rounding_method = "round_globally"
        dp = self.env.ref("product.decimal_price")
        dp.digits = 4
        # We do this for refreshing the cached value in this env
        self.assertEqual(dp.precision_get(dp.name), 4)
        move = self.env["account.move"].create(
            {
                "partner_id": self.partner.id,
                # "account_id": self.partner.property_account_receivable_id.id,
                "journal_id": self.sale_journal.id,
                "invoice_date": "2016-03-12",
                "payment_mode_id": self.payment_mode.id,
                "type": "out_invoice",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.env.ref(
                                "product.product_delivery_02"
                            ).id,
                            "account_id": self.account.id,
                            "name": "Producto de prueba",
                            "quantity": 1.0,
                            "price_unit": 190.314,
                            "tax_ids": [(6, 0, self.tax.ids)],
                        },
                    )
                ],
            }
        )
        self.assertAlmostEqual(move.invoice_line_ids.price_unit, 190.314, 4)
        self._check_amounts(move, *self.first_check_amount)

    def test_move_rounding_with_discount(self):
        self.main_company.tax_calculation_rounding_method = "round_globally"
        dp = self.env.ref("product.decimal_price")
        dp.digits = 4
        # We do this for refreshing the cached value in this env
        self.assertEqual(dp.precision_get(dp.name), 4)
        move = self.env["account.move"].create(
            {
                "partner_id": self.partner.id,
                # "account_id": self.partner.property_account_receivable_id.id,
                "journal_id": self.sale_journal.id,
                "invoice_date": "2016-03-12",
                "payment_mode_id": self.payment_mode.id,
                "type": "out_invoice",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.env.ref(
                                "product.product_delivery_02"
                            ).id,
                            "account_id": self.account.id,
                            "name": "Producto de prueba",
                            "quantity": 1.0,
                            "price_unit": 190.314,
                            "discount": 30,
                            "tax_ids": [(6, 0, self.tax.ids)],
                        },
                    )
                ],
            }
        )
        self._check_amounts(move, *self.second_check_amount)
