
from odoo import api, fields, models, exceptions, _


class L10nEsAeatMod190Report(models.Model):

    _description = 'AEAT 190 report'
    _inherit = 'l10n.es.aeat.report.tax.mapping'
    _name = 'l10n.es.aeat.mod190.report'
    _aeat_number = '190'
    _period_quarterly = False
    _period_monthly = False
    _period_yearly = True

    casilla_01 = fields.Integer(string="[01] Recipients", readonly=True)
    casilla_02 = fields.Float(string="[02] Amount of perceptions")
    casilla_03 = fields.Float(string="[03] Amount of retentions")
    partner_record_ids = fields.One2many(
        comodel_name='l10n.es.aeat.mod190.report.line',
        inverse_name='report_id', string='Partner records', ondelete='cascade')
    registro_manual = fields.Boolean(string='Manual records', default=False)
    calculado = fields.Boolean(string='Calculated', default=False)

    @api.multi
    def _check_report_lines(self):
        """Checks if all the fields of all the report lines
        (partner records) are filled """
        for item in self:
            for partner_record in item.partner_record_ids:
                if not partner_record.partner_record_ok:
                    raise exceptions.UserError(
                        _("All partner records fields (country, VAT number) "
                          "must be filled."))

    @api.multi
    def button_confirm(self):
        for report in self:
            valid = True
            if self.casilla_01 != len(report.partner_record_ids):
                valid = False

            percepciones = 0.0
            retenciones = 0.0
            for line in report.partner_record_ids:
                percepciones += \
                    line.percepciones_dinerarias + \
                    line.percepciones_en_especie + \
                    line.percepciones_dinerarias_incap + \
                    line.percepciones_en_especie_incap

                retenciones += \
                    line.retenciones_dinerarias + \
                    line.retenciones_dinerarias_incap

            if self.casilla_02 != percepciones:
                valid = False

            if self.casilla_03 != retenciones:
                valid = False

            if not valid:
                raise exceptions.UserError(
                    _("You have to recalculate the report before confirm it."))
        self._check_report_lines()
        return super(L10nEsAeatMod190Report, self).button_confirm()

    @api.multi
    def calculate(self):
        res = super(L10nEsAeatMod190Report, self).calculate()
        for report in self:
            if not report.registro_manual:
                report.partner_record_ids.unlink()
            tax_lines = report.tax_line_ids.filtered(
                lambda x: x.field_number in (
                    11, 12, 13, 14, 15, 16) and x.res_id == report.id)
            tax_line_vals = {}
            for tax_line in tax_lines:
                for line in tax_line.move_line_ids:
                    rp = line.partner_id
                    if line.aeat_perception_key_id:
                        key_id = line.aeat_perception_key_id
                        subkey_id = line.aeat_perception_subkey_id
                    else:
                        key_id = rp.aeat_perception_key_id
                        subkey_id = rp.aeat_perception_subkey_id
                    check_existance = False
                    if rp.id not in tax_line_vals:
                        tax_line_vals[rp.id] = {}
                    if key_id.id not in tax_line_vals[rp.id]:
                        tax_line_vals[rp.id][key_id.id] = {}
                    if subkey_id.id not in tax_line_vals[rp.id][key_id.id]:
                        tax_line_vals[rp.id][key_id.id][subkey_id.id] = {}
                        check_existance = True
                    if check_existance:
                        partner_record_id = False
                        for rpr_id in report.partner_record_ids:
                            if (
                                rpr_id.partner_id == rp and
                                key_id == rpr_id.aeat_perception_key_id and
                                subkey_id == rpr_id.aeat_perception_subkey_id
                            ):
                                partner_record_id = rpr_id.id
                                break
                        if not partner_record_id:
                            if not rp.aeat_perception_key_id:
                                raise exceptions.UserError(
                                    _("The perception key of the partner, %s. "
                                        "Must be filled." % rp.name))
                            tax_line_vals[rp.id][key_id.id][
                                subkey_id.id
                            ] = report._get_line_mod190_vals(
                                rp, key_id, subkey_id)
                        else:
                            tax_line_vals[rp.id][key_id.id][subkey_id.id] = False
                    if report.registro_manual:
                        continue
                    if tax_line_vals[rp.id][key_id.id][subkey_id.id]:
                        values = tax_line_vals[rp.id][key_id.id][subkey_id.id]
                        pd = 0.0
                        if (
                            tax_line.field_number in (11, 15) and
                            tax_line.res_id == report.id
                        ):
                            pd += line.debit - line.credit
                        rd = 0.0
                        if (
                            tax_line.field_number in (12, 16) and
                            tax_line.res_id == report.id
                        ):
                            rd += line.credit - line.debit
                        pde = 0.0
                        if (
                            tax_line.field_number == 13 and
                            tax_line.res_id == report.id
                        ):
                            pde += line.debit - line.credit
                        rde = 0.0
                        if (
                            tax_line.field_number == 13 and
                            tax_line.res_id == report.id
                        ):
                            rde += line.credit - line.debit
                        if not rp.disability or rp.disability == '0':
                            values['percepciones_dinerarias'] += pd
                            values['retenciones_dinerarias'] += rd
                            values['percepciones_en_especie'] += pde - rde
                            values['ingresos_a_cuenta_efectuados'] += pde
                            values['ingresos_a_cuenta_repercutidos'] += rde
                        else:
                            values['percepciones_dinerarias_incap'] += pd
                            values['retenciones_dinerarias_incap'] += rd
                            values[
                                'percepciones_en_especie_incap'] += pde - rde
                            values['ingresos_a_cuenta_efectuados_incap'] += pde
                            values[
                                'ingresos_a_cuenta_repercutidos_incap'] += rde

            line_obj = self.env['l10n.es.aeat.mod190.report.line']
            registros = 0
            for partner_id in tax_line_vals:
                for key_id in tax_line_vals[partner_id]:
                    for subkey_id in tax_line_vals[partner_id][key_id]:
                        values = tax_line_vals[partner_id][key_id][subkey_id]
                        registros += 1
                        if values:
                            line_obj.create(values)
            report._compute_amount(registros)
            report.calculado = True
        return res

    def _compute_amount(self, registros):
        percepciones = 0.0
        retenciones = 0.0
        if self.registro_manual:
            registros = 0
            for line in self.partner_record_ids:
                registros += 1
                percepciones += \
                    line.percepciones_dinerarias + \
                    line.percepciones_en_especie + \
                    line.percepciones_dinerarias_incap + \
                    line.percepciones_en_especie_incap
                retenciones += \
                    line.retenciones_dinerarias + \
                    line.retenciones_dinerarias_incap
        else:
            percepciones = 0.0
            retenciones = 0.0
            tax_lines = self.tax_line_ids.search(
                [('field_number', 'in', (11, 13, 15)),
                 ('model', '=', 'l10n.es.aeat.mod190.report'),
                 ('res_id', '=', self.id)])
            for t in tax_lines:
                for m in t.move_line_ids:
                    percepciones += m.debit - m.credit

            tax_lines = self.tax_line_ids.search(
                [('field_number', 'in', (12, 14, 16)),
                 ('model', '=', 'l10n.es.aeat.mod190.report'),
                 ('res_id', '=', self.id)])
            for t in tax_lines:
                for m in t.move_line_ids:
                    retenciones += m.credit - m.debit
        self.casilla_01 = registros
        self.casilla_02 = percepciones
        self.casilla_03 = retenciones

    def _get_line_mod190_vals(self, rp, key_id, subkey_id):
        codigo_provincia = self.SPANISH_STATES.get(
            rp.state_id.code, False)
        if not codigo_provincia:
            exceptions.UserError(
                _('The state is not defined in the partner, %s') % rp.name)
        vals = {
            'report_id': self.id,
            'partner_id': rp.id,
            'partner_vat': rp.vat,
            'aeat_perception_key_id': key_id.id,
            'aeat_perception_subkey_id': subkey_id.id,
            'codigo_provincia': codigo_provincia,
            'ceuta_melilla': rp.ceuta_melilla,
            'partner_record_ok': True,
            'percepciones_dinerarias': 0,
            'retenciones_dinerarias': 0,
            'percepciones_en_especie': 0,
            'ingresos_a_cuenta_efectuados': 0,
            'ingresos_a_cuenta_repercutidos': 0,
            'percepciones_dinerarias_incap': 0,
            'retenciones_dinerarias_incap': 0,
            'percepciones_en_especie_incap': 0,
            'ingresos_a_cuenta_efectuados_incap': 0,
            'ingresos_a_cuenta_repercutidos_incap': 0,
        }
        if key_id.additional_data_required + subkey_id.additional_data_required >= 2:
            vals.update({
                'birth_year': rp.birth_year,
                'disability': rp.disability,
                'geographical_mobility': rp.geographical_mobility,
                'legal_representative_vat': rp.legal_representative_vat,
                'family_situation': rp.family_situation,
                'spouse_vat': rp.spouse_vat,
                'relation_kind': rp.relation_kind,
                'descendants_less_3_years': rp.descendants_less_3_years,
                'descendants_less_3_years_integer':
                    rp.descendants_less_3_years_integer,
                'descendants': rp.descendants,
                'descendants_integer': rp.descendants_integer,
                'calculation_rule_first_childs_1': rp.calculation_rule_first_childs_1,
                'calculation_rule_first_childs_2': rp.calculation_rule_first_childs_2,
                'calculation_rule_first_childs_3': rp.calculation_rule_first_childs_3,
                'descendants_disability_33': rp.descendants_disability_33,
                'descendants_disability_33_integer':
                    rp.descendants_disability_33_integer,
                'descendants_disability': rp.descendants_disability,
                'descendants_disability_integer':
                    rp.descendants_disability_integer,
                'descendants_disability_66': rp.descendants_disability_66,
                'descendants_disability_66_integer':
                    rp.descendants_disability_66_integer,
                'ancestors': rp.ancestors,
                'ancestors_integer': rp.ancestors_integer,
                'ancestors_older_75': rp.ancestors_older_75,
                'ancestors_older_75_integer': rp.ancestors_older_75_integer,
                'ancestors_disability_33': rp.ancestors_disability_33,
                'ancestors_disability_33_integer':
                    rp.ancestors_disability_33_integer,
                'ancestors_disability': rp.ancestors_disability,
                'ancestors_disability_integer':
                    rp.ancestors_disability_integer,
                'ancestors_disability_66': rp.ancestors_disability_66,
                'ancestors_disability_66_integer':
                    rp.ancestors_disability_66_integer,
            })
        return vals


class L10nEsAeatMod190ReportLine(models.Model):
    _name = 'l10n.es.aeat.mod190.report.line'
    _description = "Line for AEAT report Mod 190"
    _inherit = 'l10n.es.mod190.additional.data.mixin'

    @api.depends('partner_vat', 'birth_year',
                 'codigo_provincia', 'aeat_perception_key_id', 'partner_id')
    def _compute_partner_record_ok(self):
        """Comprobamos que los campos estén introducidos dependiendo de las
           claves y las subclaves."""

        for record in self:
            record.partner_record_ok = bool(
                record.partner_vat and record.codigo_provincia and
                record.aeat_perception_key_id and record
            )

    report_id = fields.Many2one(
        comodel_name='l10n.es.aeat.mod190.report',
        string='AEAT 190 Report ID', ondelete="cascade")
    partner_record_ok = fields.Boolean(
        compute="_compute_partner_record_ok", string='Partner Record OK',
        help='Checked if partner record is OK')
    partner_id = fields.Many2one(
        comodel_name='res.partner', string='Partner', required=True)
    partner_vat = fields.Char(string='VAT', size=15)
    legal_representative_vat = fields.Char(
        oldname="representante_legal_vat",
        string="L. R. VAT", size=9)
    accrual_exercise = fields.Char(
        oldname="ejercicio_devengo",
        string='year', size=4)
    ceuta_melilla = fields.Char(
        string='Ceuta or Melilla', size=1)

    # Percepciones y Retenciones

    percepciones_dinerarias = fields.Float(
        string='Monetary perceptions')
    retenciones_dinerarias = fields.Float(
        string='Money withholdings')
    percepciones_en_especie = fields.Float(
        string='Valuation')
    ingresos_a_cuenta_efectuados = fields.Float(
        string='Income paid on account')
    ingresos_a_cuenta_repercutidos = fields.Float(
        string='Income paid into account')
    percepciones_dinerarias_incap = fields.Float(
        string='Monetary perceptions derived from incapacity for work')
    retenciones_dinerarias_incap = fields.Float(
        string='Monetary withholdings derived from incapacity for work')
    percepciones_en_especie_incap = fields.Float(
        string='Perceptions in kind arising from incapacity for work')
    ingresos_a_cuenta_efectuados_incap = fields.Float(
        string='Income on account in kind made as a result of incapacity '
               'for work')
    ingresos_a_cuenta_repercutidos_incap = fields.Float(
        string='Income to account in kind, repercussions derived from '
               'incapacity for work')

    codigo_provincia = fields.Char(
        string="State ISO code", size=2,
        help='''''')

    reduccion_aplicable = fields.Float(string='Applicable reduction')
    gastos_deducibles = fields.Float(string='Deductible expenses')
    pensiones_compensatorias = fields.Float(string='Compensatory pensions')
    anualidades_por_alimentos = fields.Float(string='Annuities for food')
    prestamos_vh = fields.Selection(
        selection=[
            ('0', "0 - Si en ningún momento del ejercicio ha resultado de "
                  "aplicación la reducción del tipo de retención."),
            ('1', '1 - Si en algún momento del ejercicio ha resultado de '
                  'aplicación la reducción del tipo de retención.')],
        string='Comunicación préstamos vivienda habitual')

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if self.partner_id:
            partner = self.partner_id
            if not partner.state_id:
                exceptions.UserError(
                    _('State not defined on %s') % partner.display_name)

            self.codigo_provincia = self.report_id.SPANISH_STATES.get(
                partner.state_id.code, "98")

            self.partner_vat = partner.vat
            # Cargamos valores establecidos en el tercero.
            self.aeat_perception_key_id = partner.aeat_perception_key_id
            self.aeat_perception_subkey_id = partner.aeat_perception_subkey_id
            self.birth_year = partner.birth_year
            self.disability = partner.disability
            self.ceuta_melilla = partner.ceuta_melilla
            self.geographical_mobility = partner.geographical_mobility
            self.legal_representative_vat = partner.legal_representative_vat
            self.family_situation = partner.family_situation
            self.spouse_vat = partner.spouse_vat
            self.relation_kind = partner.relation_kind
            self.descendants_less_3_years = partner.descendants_less_3_years
            self.descendants_less_3_years_integer = \
                partner.descendants_less_3_years_integer
            self.descendants = partner.descendants
            self.descendants_integer = \
                partner.descendants_integer
            self.calculation_rule_first_childs_1 = partner.calculation_rule_first_childs_1
            self.calculation_rule_first_childs_2 = partner.calculation_rule_first_childs_2
            self.calculation_rule_first_childs_3 = partner.calculation_rule_first_childs_3
            self.descendants_disability_33 = \
                partner.descendants_disability_33
            self.descendants_disability_33_integer = \
                partner.descendants_disability_33_integer
            self.descendants_disability = \
                partner.descendants_disability
            self.descendants_disability_integer = \
                partner.descendants_disability_integer
            self.descendants_disability_66 = \
                partner.descendants_disability_66
            self.descendants_disability_66_integer = \
                partner.descendants_disability_66_integer
            self.ancestors = partner.ancestors
            self.ancestors_integer = partner.ancestors_integer
            self.ascendientes_m75 = partner.ancestors_older_75
            self.ancestors_older_75_integer = partner.ancestors_older_75_integer

            self.ancestors_disability_33 = \
                partner.ancestors_disability_33
            self.ancestors_disability_33_integer = \
                partner.ancestors_disability_33_integer
            self.ancestors_disability = \
                partner.ancestors_disability
            self.ancestors_disability = \
                partner.ancestors_disability_integer
            self.ancestors_disability_66 = \
                partner.ancestors_disability_66
            self.ancestors_disability_66_integer = \
                partner.ancestors_disability_66_integer

            if self.aeat_perception_key_id:
                self.aeat_perception_subkey_id = False
                return {'domain': {'aeat_perception_subkey_id': [
                    ('aeat_perception_key_id', '=', self.aeat_perception_key_id.id)]}}
            else:
                return {'domain': {'aeat_perception_subkey_id': []}}
        else:
            self.partner_vat = False
            self.codigo_provincia = False
