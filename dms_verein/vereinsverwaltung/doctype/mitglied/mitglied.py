import frappe
from frappe.model.document import Document


class Mitglied(Document):
    def before_save(self):
        self.vollstaendiger_name = f"{self.vorname} {self.nachname}"

    def validate(self):
        if not self.portal_benutzer:
            return
        existing = frappe.db.exists(
            "Mitglied",
            {"portal_benutzer": self.portal_benutzer, "name": ["!=", self.name]},
        )
        if existing:
            frappe.throw("Der Portal-Benutzer ist bereits mit einem anderen Mitglied verknüpft.")

    def after_insert(self):
        self._add_mitgliedschaft_eintrag()

    def _add_mitgliedschaft_eintrag(self):
        if not self.mitgliedschaften:
            self.append("mitgliedschaften", {
                "mitgliedstyp": self.mitgliedstyp,
                "von": self.eintrittsdatum,
                "status": "Aktiv",
            })
            self.save(ignore_permissions=True)
