# -*- coding: utf-8 -*-
# ©  2017 Deltatech
# See README.rst file on addons root folder for license details

import base64
import zipfile

try:
    # For Python 3.0 and later
    from io import StringIO
    unicode = str
except ImportError:
    # Fall back to Python 2's
    import StringIO

from io import BytesIO

from .mydbf import base, fields as dbf_fields

import os

from odoo import models, fields, api, _
from odoo.exceptions import UserError, RedirectWarning
import odoo.addons.decimal_precision as dp
import unicodedata

try:
    import html2text
except:
    from odoo.addons.email_template import html2text


class import_saga(models.TransientModel):
    _name = 'import.saga'
    _description = "Import Saga"

    state = fields.Selection([('choose', 'choose'),  # choose period
                              ('result', 'result')], default='choose')  # get the file

    supplier_file = fields.Binary(string='Suppliers File')
    supplier_file_name = fields.Char(string='Suppliers File Name')
    customer_file = fields.Binary(string='Customers File')
    customer_file_name = fields.Char(string='Customers File Name')

    articole_file = fields.Binary(string='Articole File')
    articole_file_name = fields.Char(string='Products File Name')

    ignore_error = fields.Boolean(string='Ignore Errors', default=True)
    result = fields.Html(string="Result Export", readonly=True)

    def unaccent(self, text):

        text = unicode(text.decode('utf-8','ignore').encode("utf-8"))
        text = unicodedata.normalize('NFD', text)
        text = text.encode('ascii', 'ignore')
        text = text.decode("utf-8")
        text = text.replace(chr(13), ' ')
        text = text.replace('\n', ' ')
        return str(text)


    @api.multi
    def do_import(self):
        if self.supplier_file:
            self.import_supplier()
        if self.customer_file:
            self.import_customer()
        if self.articole_file:
            self.import_articole()

    @api.multi
    def import_supplier(self):
        """
        Furnizori
        Nr. crt. Nume câmp Tip Mărime câmp Descriere
        1. COD Character 5 Cod furnizor
        2. DENUMIRE Character 48 Denumire furnizor
        3. COD_FISCAL Character 13 Cod Fiscal, furnizor
        4. ANALITIC Character 16 Cont analitic
        5. ZS Numeric 3 Zile Scadenţă (optional)
        6. ADRESA Character 48 Adresa (optional)
        7. BANCA Character 48 Banca (optional)
        8. CONT_BANCA Character 36 Contul bancar (optional)
        9. FILIALA Character 36 Filiala Banca (optional)
        10. GRUPA Character 16 Grupa de furnizor (optional)
        11. AGENT Character 4 Cod agent (optional)
        12. DEN_AGENT Character 36 Nume agent (optional)
        13. TIP_TERT Character 1 I pt. intracomunitar, E pt. extracomunitari
        14. TARA Character 2 Codul de tara (RO)
        15. TEL Character 20 Numar telefon (optional)
        16. EMAIL Character 100 Email (optional)
        17. IS_TVA Numeric 1 1, dacă este platitor de TVA

        """
        supplier_file = base64.decodestring(self.supplier_file)
        buff = StringIO.StringIO(supplier_file)
        suppliers = base.DBF(buff)
        result_html = ''
        for supplier in suppliers:
            if not supplier['DENUMIRE']:
                continue
            print ("Import", supplier['DENUMIRE'])

            country = self.env['res.country'].search([('code', '=', supplier['TARA'])], limit=1)
            if not country:
                country = self.env.user.company_id.country_id

            vat = supplier['COD_FISCAL']
            cnp = ''
            is_company = True
            if vat:
                for char in vat:
                    if char not in "0123456789":
                        vat = vat.replace(char, '')

            if vat:
                if len(vat) == 13 and supplier['IS_TVA'] != 1:
                    cnp = vat
                    vat = ''
                    is_company = False
                else:
                    vat = country.code + vat

            partner = self.env['res.partner'].search([('ref_supplier', '=', supplier['COD'])], limit=1)
            if not partner and vat:
                partner = self.env['res.partner'].search([('vat', '=', vat)], limit=1)

            if not partner and supplier['DENUMIRE']:
                partner = self.env['res.partner'].search([('name', '=', supplier['DENUMIRE'])], limit=1)

            values = {
                'name': supplier['DENUMIRE'],
                'ref_supplier': supplier['COD'],
                'country_id': country.id,
                'is_company': is_company,
                'supplier': True
            }

            if not partner:
                values['customer'] = False
                partner = self.env['res.partner'].create(values)
            else:
                del values['name']  # se pastreaza numele actualizat din Odoo
                partner.write(values)

            # update vat
            values = {
                'vat': vat,
                'cnp': cnp,
                'vat_subjected': supplier['IS_TVA'] == 1,
            }
            try:
                partner.write(values)
            except Exception as e:
                result_html += '<div>Eroare modificare furnizor %s: %s</div>' % (supplier['DENUMIRE'], str(e))
                if not self.ignore_error:
                    raise

            self.env.cr.commit()
        return

    @api.multi
    def import_customer(self):
        """
        Clienţi
        Nr. crt. Nume câmp Tip Mărime câmp Descriere
        1. COD Character 5 Cod client
        2. DENUMIRE Character 48 Denumire furnizor
        3. COD_FISCAL Character 16 Cod Fiscal, client
        4. REG_COM Character 16 Nr.înregistrare la Registrul Comerţului
        5. ANALITIC Character 16 Cont analitic
        6. ZS Numeric 3 Zile Scadenţă (optional)
        7. DISCOUNT Numeric 5,2 Procent de discount acordat (optional)
        8. ADRESA Character 48 Adresa (optional)
        9. JUDET Character 36 Judeţ (optional)
        10. BANCA Character 36 Banca (optional)
        11. CONT_BANCA Character 36 Contul bancar (optional)
        12. DELEGAT Character 36 Numele şi prenumele delegatului (optional)
        13. BI_SERIE Character 2 Seria actului de identitate a delegatului (op.)
        14. BI_NUMAR Character 8 Număr act identitate, a delegatului (optional)
        15. BI_POL Character 16 Eliberat de... (optional)
        16. MASINA Character 16 Număr maşină delegat (optional)
        17. INF_SUPL Character 100 Informaltii care apar pe factura (optional)
        18. AGENT Character 4 Cod agent (optional)
        19. DEN_AGENT Character 36 Nume agent (optional)
        20. GRUPA Character 16 Grupa de client (optional)
        21. TIP_TERT Character 1 I pt. intracomunitar, E pt. extracomunitari
        22. TARA Character 2 Codul de tara (RO)
        23. TEL Character 20 Numar telefon (optional)
        24. EMAIL Character 100 Email (optional)
        25. IS_TVA Numeric 1 1, dacă este platitor de TVA

        """
        customer_file = base64.decodestring(self.customer_file)
        buff = StringIO.StringIO(customer_file)
        customers = base.DBF(buff)
        result_html = ''
        for customer in customers:
            if not customer['DENUMIRE']:
                continue
            print ("Import", customer['DENUMIRE'])

            country = self.env['res.country'].search([('code', '=', customer['TARA'])], limit=1)
            if not country:
                country = self.env.user.company_id.country_id

            vat = customer['COD_FISCAL']
            cnp = ''
            is_company = True
            if vat:
                for char in vat:
                    if char not in "0123456789":
                        vat = vat.replace(char, '')

            if vat:
                if len(vat) == 13 and customer['IS_TVA'] != 1:
                    cnp = vat
                    vat = ''
                    is_company = False
                else:
                    vat = country.code + vat

            partner = self.env['res.partner'].search([('ref_customer', '=', customer['COD'])], limit=1)
            if not partner and vat:
                partner = self.env['res.partner'].search([('vat', '=', vat)], limit=1)

            if not partner and customer['DENUMIRE']:
                partner = self.env['res.partner'].search([('name', '=', customer['DENUMIRE'])], limit=1)

            state = self.env["res.country.state"].search([('name', '=', customer['JUDET'])], limit=1)

            values = {
                'name': customer['DENUMIRE'],
                'ref_customer': customer['COD'],
                'nrc': customer['REG_COM'],
                'country_id': country.id,
                'is_company': is_company,
                'customer': True,
                'phone': customer['TEL'],
                'email': customer['EMAIL'],
                'state_id': state.id,

            }

            if not partner:
                values['supplier'] = False
                partner = self.env['res.partner'].create(values)
            else:
                del values['name']  # se pastreaza numele actualizat din Odoo
                partner.write(values)

            # update vat
            values = {
                'vat': vat,
                'cnp': cnp,
                'vat_subjected': customer['IS_TVA'] == 1,
            }
            try:
                partner.write(values)
            except Exception as e:
                result_html += '<div>Eroare modificare client %s: %s</div>' % (customer['DENUMIRE'], str(e))
                if not self.ignore_error:
                    raise
            self.env.cr.commit()
        return

    @api.multi
    def import_articole(self):
        """
        Articole
        Nr. crt. Nume câmp Tip Mărime câmp Descriere
        1. COD Character 16 Cod articol
        2. DENUMIRE Character 60 Denumire articol
        3. UM Character 5 Unitate de masura
        4. TVA Numeric 5,2 Procent TVA articol
        5. TIP* Character 2 Cod tip
        6. DEN_TIP Character 36 Denumire tip
        7. PRET_VANZ Numeric 15,4 Pret de vanzare fara TVA (optional)
        8. PRET_V_TVA Numeric 15,4 Pret de vanzare cu TVA (optional)
        9. COD_BARE Character 16 Cod de bare (optional)
        10. CANT_MIN Numeric 14,3 Stoc minim (optional)
        11. GRUPA Character 16 Grupa de articol (optional)

        """

        articole_file = base64.decodestring(self.articole_file)
        buff = StringIO.StringIO(articole_file)
        articole = base.DBF(buff)
        result_html = self.result
        tax = {}
        categorii = {}
        for articol in articole:
            product = self.env['product.product'].search([('default_code', '=', articol['COD'])], limit=1)
            uom = self.env['product.uom'].search([('name', '=', articol['UM'])], limit=1)
            if not uom:
                uom_id = self.env['product.uom'].name_create(articol['UM'])[0]
            else:
                uom_id = uom.id


            if articol['TIP'] not in categorii:
                categ = self.env["product.category"].search([('code_saga', '=', articol['TIP'])], limit=1)
                if not categ:
                    categ = self.env["product.category"].create({'code_saga': articol['TIP'],
                                                                 'name': articol['DEN_TIP']})
                categorii[articol['TIP']] = categ
            else:
                categ = categorii[articol['TIP']]

            CotaTVA = articol['TVA']
            if CotaTVA not in tax:
                sale_tax = self.env['account.tax'].search([('type_tax_use', '=', 'sale'),
                                                           ('amount', '=', CotaTVA)], limit=1)
                purchase_tax = self.env['account.tax'].search([('type_tax_use', '=', 'purchase'),
                                                               ('amount', '=', CotaTVA)], limit=1)
                tax[CotaTVA] = {'sale_tax': sale_tax, 'purchase_tax': purchase_tax}

            else:
                sale_tax = tax[CotaTVA]['sale_tax']
                purchase_tax = tax[CotaTVA]['purchase_tax']


            values = {
                'name': self.unaccent(articol['DENUMIRE']),
                'default_code': articol['COD'],
                'uom_id': uom_id,
                'uom_po_id':uom_id,
                'categ_id': categ.id,
                'list_price': articol['PRET_VANZ'],
                'barcode': articol['COD_BARE'],
                'taxes_id':[(6, False, sale_tax.ids)],
                'supplier_taxes_id':[(6, False, purchase_tax.ids)],
            }
            print (values)
            if not product:
                product = self.env['product.product'].create(values)
            else:
                product.write(values)
            self.env.cr.commit()
        return


"""
Intrări
Nr. crt. Nume câmp Tip Mărime câmp Descriere
1. NR_NIR Numeric 7 Număr NIR
2. NR_INTRARE Character 16 Numărul documentului de intrare
3. GESTIUNE Character 4 Cod gestiune (optional)
4. DEN_GEST Character 36 Denumirea gestiunii (optional)
5. COD Character 5 Cod furnizor
6. DATA Date - Data documentului de intrare (a facturii)
7. SCADENT Date - Data scadenţei
8. TIP Character 1 "A" - pentru aviz, "T" - taxare inversă...
9. TVAI Numeric 1 1 pentru TVA la incasare
10. COD_ART Character 16 Cod articol (optional)
11. DEN_ART Character 60 Denumire articol
12. UM Character 5 Unitatea de măsură pt.articol (optional)
13. CANTITATE Numeric 14,3 Cantitate
14. DEN_TIP Character 36 Denumirea tipului de articol (optional)
15. TVA_ART Numeric 2 Procentul de TVA
16. VALOARE Numeric 15,2 Valoarea totală, fără TVA
17. TVA Numeric 15,2 TVA total
18. CONT Character 20 Contul corespondent
19. PRET_VANZ Numeric 15,2 Preţul de vânzare, (optional)
20. GRUPA Character 16 Cod de grupa de articol contabil (optional)




"""