import frappe
from frappe import _

# Rollen-Konstanten (entsprechen den Fixtures in fixtures/role.json)
ADMIN_ROLLEN = ["Vereins Admin", "System Manager"]
ERWEITERTER_ZUGANG = ["Vereins Admin", "System Manager", "Kassenwart", "Vorstand", "Spartenleiter"]
VERGEBBARE_ROLLEN = {"Vereins Admin", "Kassenwart", "Spartenleiter", "Vorstand", "Mitglied", "Blogger"}


def _notify(doctype, action="update", name=None):
    """Echtzeit-Benachrichtigung an alle verbundenen Clients."""
    frappe.publish_realtime("dms_update", {"doctype": doctype, "action": action, "name": name}, room="all")


# ─── Öffentliche Endpunkte (Gäste erlaubt) ───────────────────────────────────

@frappe.whitelist(allow_guest=True)
def get_verein_info():
    """Öffentliche Vereinsinfos für Portal, Impressum und Datenschutz."""
    if not frappe.db.exists("Vereins Konfiguration", "Vereins Konfiguration"):
        return {}
    doc = frappe.get_doc("Vereins Konfiguration")
    return {
        "vereinsname": doc.vereinsname,
        "rechtsform": doc.rechtsform,
        "gruendungsjahr": doc.gruendungsjahr,
        "vereinszweck": doc.vereinszweck,
        "strasse": doc.strasse,
        "hausnummer": doc.hausnummer,
        "plz": doc.plz,
        "ort": doc.ort,
        "bundesland": doc.bundesland,
        "telefon": doc.telefon,
        "email": doc.email,
        "website": doc.website,
        "logo": doc.logo,
        "vereinsmotto": doc.vereinsmotto,
        "willkommenstext": doc.willkommenstext,
        "primaerfarbe": doc.primaerfarbe,
        "sekundaerfarbe": doc.sekundaerfarbe,
        "registernummer": doc.registernummer,
        "amtsgericht": doc.amtsgericht,
        "steuernummer": doc.steuernummer,
        "gemeinnuetzig": doc.gemeinnuetzig,
        "vertretung_vorstand": doc.vertretung_vorstand,
        "impressum_text": doc.impressum_text,
        "datenschutzbeauftragter": doc.datenschutzbeauftragter,
        "datenschutz_email": doc.datenschutz_email,
        "datenschutz_url": doc.datenschutz_url,
        "datenschutz_text": doc.get("datenschutz_text") or "",
        "google_maps_key": (doc.google_maps_key or "") if doc.google_maps_aktiv != 0 else "",
        "google_maps_aktiv": doc.google_maps_aktiv != 0,
    }


def _maps_cache_key():
    import datetime
    return f"maps_geo_{datetime.date.today().strftime('%Y_%m')}"

def _maps_track():
    try:
        k = _maps_cache_key()
        n = int(frappe.cache().get_value(k) or 0)
        frappe.cache().set_value(k, n + 1, expires_in_sec=60 * 60 * 24 * 40)
    except Exception:
        pass

@frappe.whitelist()
def geocode_adresse(query):
    """Adresse über Google Geocoding API suchen (Ergebnisse kommen vom Backend, Key bleibt server-seitig)."""
    if not query:
        return []
    key = frappe.db.get_single_value("Vereins Konfiguration", "google_maps_key")
    if not key:
        return []
    import requests as _req
    try:
        site_url = frappe.utils.get_url()
        r = _req.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"address": query, "key": key, "language": "de", "region": "DE"},
            headers={"Referer": site_url},
            timeout=5,
        )
        data = r.json()
    except Exception:
        return []
    if data.get("status") != "OK":
        return []
    _maps_track()
    results = []
    for item in data.get("results", [])[:5]:
        results.append({
            "formatted_address": item["formatted_address"],
            "lat": item["geometry"]["location"]["lat"],
            "lng": item["geometry"]["location"]["lng"],
        })
    return results


@frappe.whitelist()
def get_maps_nutzung():
    """Monatliche Geocoding-Aufruf-Statistik aus dem Cache."""
    frappe.only_for(ADMIN_ROLLEN)
    import datetime
    heute = datetime.date.today()
    monate = []
    for i in range(3):
        m, y = heute.month - i, heute.year
        while m <= 0:
            m += 12
            y -= 1
        k = f"maps_geo_{y:04d}_{m:02d}"
        monate.append({
            "monat": datetime.date(y, m, 1).strftime("%B %Y"),
            "geocoding": int(frappe.cache().get_value(k) or 0),
        })
    return monate


@frappe.whitelist(allow_guest=True)
def get_mitgliedstypen():
    """Liste aller aktiven Mitgliedstypen für Antrag-Formular."""
    return frappe.get_all(
        "Mitgliedstyp",
        filters={"aktiv": 1},
        fields=["name", "bezeichnung", "beitragsbetrag", "zahlungsintervall",
                "beschreibung", "min_alter", "max_alter", "farbe"],
        order_by="bezeichnung",
    )


@frappe.whitelist(allow_guest=True)
def get_sparten():
    """Alle aktiven Sparten."""
    return frappe.get_all(
        "Sparte",
        filters={"aktiv": 1},
        fields=["name", "name_sparte", "beschreibung", "icon", "farbe",
                "treffpunkt", "bild", "beitrag", "beitrag_intervall", "beitrag_bezeichnung"],
        order_by="name_sparte",
    )


@frappe.whitelist(allow_guest=True)
def get_veranstaltungen(sparte=None, limit=20, offset=0):
    """Öffentliche Veranstaltungen."""
    filters = {"oeffentlich": 1, "status": ["!=", "Abgesagt"]}
    if sparte:
        filters["sparte"] = sparte
    return frappe.get_all(
        "Veranstaltung",
        filters=filters,
        fields=["name", "titel", "kategorie", "datum_von", "datum_bis",
                "uhrzeit_von", "veranstaltungsort", "adresse", "beschreibung",
                "bild", "sparte", "max_teilnehmer", "anmeldung_erforderlich",
                "anmeldeschluss", "kosten_mitglieder", "kosten_gaeste"],
        order_by="datum_von asc",
        limit_page_length=int(limit),
        limit_start=int(offset),
    )


@frappe.whitelist(allow_guest=True)
def submit_mitgliedsantrag(data):
    """Mitgliedsantrag aus dem öffentlichen Formular einreichen."""
    import json
    if isinstance(data, str):
        data = json.loads(data)

    pflichtfelder = ["vorname", "nachname", "strasse", "plz", "ort",
                     "email", "gewuenschter_mitgliedstyp",
                     "datenschutz_akzeptiert", "satzung_akzeptiert",
                     "beitragsordnung_akzeptiert"]
    for f in pflichtfelder:
        if not data.get(f):
            frappe.throw(_(f"Pflichtfeld fehlt: {f}"))

    if not data.get("datenschutz_akzeptiert") or not data.get("satzung_akzeptiert"):
        frappe.throw(_("Bitte akzeptieren Sie Datenschutzerklärung und Satzung."))

    # Nur Felder aus dem öffentlichen Formular übernehmen — Status, Bearbeitungs-
    # und Verknüpfungsfelder dürfen von Gästen nicht gesetzt werden.
    erlaubte_felder = {
        "anrede", "vorname", "nachname", "geburtsdatum", "geschlecht",
        "strasse", "plz", "ort", "telefon", "mobil", "email",
        "gewuenschter_mitgliedstyp", "sparte_wunsch", "sepa_gewuenscht",
        "kontoinhaber", "iban", "bic", "datenschutz_akzeptiert",
        "satzung_akzeptiert", "beitragsordnung_akzeptiert",
    }
    antrag = frappe.new_doc("Mitgliedsantrag")
    for key in erlaubte_felder:
        if key in data:
            setattr(antrag, key, data[key])
    antrag.insert(ignore_permissions=True)
    frappe.db.commit()
    _notify("Mitgliedsantrag", "neu", antrag.name)
    return {"name": antrag.name, "message": "Ihr Antrag wurde erfolgreich eingereicht."}


# ─── Admin-Endpunkte (Frappe-Rollen via frappe.only_for) ─────────────────────

@frappe.whitelist()
def get_dashboard_stats():
    """Admin-Dashboard Statistiken."""
    frappe.only_for(ADMIN_ROLLEN)
    total = frappe.db.count("Mitglied")
    aktiv = frappe.db.count("Mitglied", {"status": "Aktiv"})
    neu_antraege = frappe.db.count("Mitgliedsantrag", {"status": ["in", ["Neu", "In Prüfung"]]})

    naechste_events = frappe.get_all(
        "Veranstaltung",
        filters={"datum_von": [">=", frappe.utils.today()], "status": ["!=", "Abgesagt"]},
        fields=["name", "titel", "datum_von", "uhrzeit_von", "veranstaltungsort"],
        order_by="datum_von asc",
        limit_page_length=5,
    )

    mitglieder_pro_typ = frappe.db.sql("""
        SELECT t.bezeichnung, COUNT(m.name) as anzahl
        FROM `tabMitglied` m
        JOIN `tabMitgliedstyp` t ON m.mitgliedstyp = t.name
        WHERE m.status = 'Aktiv'
        GROUP BY t.bezeichnung
    """, as_dict=True)

    return {
        "total_mitglieder": total,
        "aktive_mitglieder": aktiv,
        "neue_antraege": neu_antraege,
        "naechste_veranstaltungen": naechste_events,
        "mitglieder_pro_typ": mitglieder_pro_typ,
    }


@frappe.whitelist()
def get_mitglieder_liste(search="", status="", mitgliedstyp="", sparte="",
                          limit=50, offset=0):
    """Mitgliederliste für Admin."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    filters = {}
    if status:
        filters["status"] = status
    if mitgliedstyp:
        filters["mitgliedstyp"] = mitgliedstyp

    oder_filter = None
    if search:
        oder_filter = [
            ["vorname", "like", f"%{search}%"],
            ["nachname", "like", f"%{search}%"],
            ["email", "like", f"%{search}%"],
            ["name", "like", f"%{search}%"],
        ]

    mitglieder = frappe.get_all(
        "Mitglied",
        filters=filters,
        or_filters=oder_filter,
        fields=["name", "vorname", "nachname", "mitgliedsnummer", "mitgliedstyp",
                "eintrittsdatum", "status", "email", "ort", "foto"],
        order_by="nachname asc",
        limit_page_length=int(limit),
        limit_start=int(offset),
    )

    total = frappe.db.count("Mitglied", filters=filters)
    return {"items": mitglieder, "total": total}


@frappe.whitelist()
def get_mitglied_detail(name):
    """Vollständiges Mitglied für Admin."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    doc = frappe.get_doc("Mitglied", name)
    rollen = set(frappe.get_roles())
    if rollen.intersection(ADMIN_ROLLEN):
        return doc.as_dict()

    # Vorstand/Spartenleitung sehen nur Stammdaten, Bankdaten nur der Kassenwart
    felder = [
        "name", "mitgliedsnummer", "status", "mitgliedstyp", "eintrittsdatum",
        "anrede", "vorname", "nachname", "geburtsdatum", "geschlecht",
        "strasse", "hausnummer", "plz", "ort", "land", "email", "telefon",
        "mobil", "foto", "sparten",
    ]
    if "Kassenwart" in rollen:
        felder.extend(["bank_name", "iban", "bic", "sepa_mandat", "beitragsrechnungen"])
    return {feld: doc.get(feld) for feld in felder}


@frappe.whitelist()
def annehmen_antrag(name):
    """Mitgliedsantrag annehmen."""
    frappe.only_for(ADMIN_ROLLEN)
    antrag = frappe.get_doc("Mitgliedsantrag", name)
    mitglied_name = antrag.annehmen()
    _notify("Mitgliedsantrag", "update", name)
    _notify("Mitglied", "neu", mitglied_name)
    return {"mitglied": mitglied_name}


@frappe.whitelist()
def ablehnen_antrag(name, grund=""):
    """Mitgliedsantrag ablehnen."""
    frappe.only_for(ADMIN_ROLLEN)
    antrag = frappe.get_doc("Mitgliedsantrag", name)
    antrag.ablehnen(grund)
    _notify("Mitgliedsantrag", "update", name)
    return {"success": True}


@frappe.whitelist()
def update_mitglied(name, data):
    """Admin aktualisiert ein Mitglied."""
    frappe.only_for(ADMIN_ROLLEN)
    import json
    if isinstance(data, str):
        data = json.loads(data)
    erlaubte = [
        "anrede", "vorname", "nachname", "geburtsdatum", "geschlecht",
        "strasse", "plz", "ort", "land", "email", "telefon", "mobil",
        "mitgliedstyp", "status", "eintrittsdatum", "austrittsdatum",
        "iban", "bic", "bank_name", "notizen", "foto",
    ]
    gueltige_status = {"Aktiv", "Passiv", "Gesperrt", "Ausgetreten", "Verstorben"}
    if "status" in data and data["status"] not in gueltige_status:
        frappe.throw(f"Ungültiger Status: {data['status']}")
    doc = frappe.get_doc("Mitglied", name)
    for f in erlaubte:
        if f in data:
            setattr(doc, f, data[f])
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    _notify("Mitglied", "update", name)
    return doc.as_dict()


@frappe.whitelist()
def update_record(doctype, name, data):
    """Generischer Update-Endpoint für Admin."""
    frappe.only_for(ADMIN_ROLLEN)
    import json
    if isinstance(data, str):
        data = json.loads(data)
    erlaubte_doctypes = [
        "Sparte", "Veranstaltung", "Fotoalbum", "Vorstandsmitglied",
        "Versammlungsprotokoll", "Mitgliedstyp", "SEPA Mandat",
        "Vereins Konfiguration",
    ]
    if doctype not in erlaubte_doctypes:
        frappe.throw(f"DocType nicht erlaubt: {doctype}")
    doc = frappe.get_doc(doctype, name)
    skip = {"name", "doctype", "owner", "creation", "modified", "modified_by", "idx"}
    for key, val in data.items():
        if key not in skip and hasattr(doc, key):
            if isinstance(val, list):
                doc.set(key, val)
            else:
                setattr(doc, key, val)
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return doc.as_dict()


@frappe.whitelist()
def delete_record(doctype, name):
    """Generischer Delete-Endpoint für Admin."""
    frappe.only_for(ADMIN_ROLLEN)
    erlaubte_doctypes = [
        "Mitglied", "Sparte", "Veranstaltung", "Fotoalbum", "Vorstandsmitglied",
        "Versammlungsprotokoll", "Mitgliedstyp", "Mitgliedsantrag",
    ]
    if doctype not in erlaubte_doctypes:
        frappe.throw(f"DocType kann nicht gelöscht werden: {doctype}")
    frappe.delete_doc(doctype, name, ignore_permissions=True, force=True)
    frappe.db.commit()
    return "OK"


# ─── Portal-Benutzer & Rollen (Frappe User-Management) ───────────────────────

@frappe.whitelist()
def get_portal_benutzer_info(mitglied_name):
    """Portal-Benutzer-Info für ein Mitglied."""
    frappe.only_for(ADMIN_ROLLEN)
    mitglied = frappe.get_doc("Mitglied", mitglied_name)
    if not mitglied.portal_benutzer or not frappe.db.exists("User", mitglied.portal_benutzer):
        return None
    user = frappe.get_doc("User", mitglied.portal_benutzer)
    return {
        "email": user.email,
        "full_name": user.full_name,
        "enabled": user.enabled,
        "roles": [r.role for r in user.roles],
        "last_login": user.last_login,
    }


@frappe.whitelist()
def create_portal_benutzer(mitglied_name, send_welcome=1):
    """Portal-Benutzer für ein Mitglied erstellen (Frappe User, Typ Website User)."""
    frappe.only_for(ADMIN_ROLLEN)
    mitglied = frappe.get_doc("Mitglied", mitglied_name)
    if mitglied.portal_benutzer and frappe.db.exists("User", mitglied.portal_benutzer):
        return {"status": "exists", "user": mitglied.portal_benutzer}
    if not mitglied.email:
        frappe.throw("Mitglied hat keine E-Mail-Adresse hinterlegt.")
    if frappe.db.exists("User", mitglied.email):
        frappe.db.set_value("Mitglied", mitglied_name, "portal_benutzer", mitglied.email)
        frappe.db.commit()
        return {"status": "linked", "user": mitglied.email}
    user = frappe.new_doc("User")
    user.email = mitglied.email
    user.first_name = mitglied.vorname or ""
    user.last_name = mitglied.nachname or ""
    user.enabled = 1
    user.user_type = "Website User"
    user.send_welcome_email = frappe.utils.cint(send_welcome)
    user.append("roles", {"role": "Mitglied"})
    user.insert(ignore_permissions=True)
    frappe.db.set_value("Mitglied", mitglied_name, "portal_benutzer", mitglied.email)
    frappe.db.commit()
    return {"status": "created", "user": mitglied.email}


@frappe.whitelist()
def set_mitglied_rollen(mitglied_name, rollen):
    """Frappe-Rollen für den Portal-Benutzer eines Mitglieds setzen."""
    frappe.only_for(ADMIN_ROLLEN)
    import json
    if isinstance(rollen, str):
        rollen = json.loads(rollen)
    if not isinstance(rollen, list):
        frappe.throw("Ungültige Rollenliste.")
    mitglied = frappe.get_doc("Mitglied", mitglied_name)
    if not mitglied.portal_benutzer:
        frappe.throw("Kein Portal-Benutzer verknüpft.")
    user = frappe.get_doc("User", mitglied.portal_benutzer)

    # Über diese Schnittstelle werden nur Vereinsrollen verwaltet. Andere Rollen
    # (z. B. System Manager) können weder vergeben noch entzogen werden — sonst
    # könnte sich ein Vereins Admin selbst oder anderen Systemrechte geben.
    vorhandene_fremdrollen = [r.role for r in user.roles if r.role not in VERGEBBARE_ROLLEN]
    unerlaubt = [r for r in rollen if r not in VERGEBBARE_ROLLEN and r not in vorhandene_fremdrollen]
    if unerlaubt:
        frappe.throw(
            f"Diese Rollen dürfen nicht vergeben werden: {', '.join(unerlaubt)}",
            frappe.PermissionError,
        )
    neue_vereinsrollen = [r for r in dict.fromkeys(rollen) if r in VERGEBBARE_ROLLEN]

    user.roles = []
    for rolle in vorhandene_fremdrollen + neue_vereinsrollen:
        user.append("roles", {"role": rolle})
    user.save(ignore_permissions=True)
    frappe.db.commit()
    return "OK"


@frappe.whitelist()
def get_mitgliedstypen_admin():
    """Beitragsklassen (Mitgliedstypen) für Dropdowns — alle inkl. inaktiver."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    return frappe.get_all(
        "Mitgliedstyp",
        fields=["name", "bezeichnung", "beitragsbetrag", "aktiv"],
        order_by="aktiv desc, bezeichnung asc",
        limit_page_length=100,
    )


@frappe.whitelist()
def get_available_rollen():
    """Alle verfügbaren Vereins-Rollen aus Frappe."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    rollen = frappe.get_all(
        "Role",
        filters={"name": ["in", ["Vereins Admin", "Kassenwart", "Spartenleiter", "Vorstand", "Mitglied", "Blogger"]]},
        pluck="name",
        order_by="name",
    )
    return rollen


# ─── Fotoalben ────────────────────────────────────────────────────────────────

def _require_login():
    if frappe.session.user == "Guest":
        frappe.throw(_("Bitte einloggen."), frappe.AuthenticationError)


@frappe.whitelist()
def get_alben_liste():
    """Alle Fotoalben mit Foto-Anzahl — für alle eingeloggten Mitglieder."""
    _require_login()
    return frappe.db.sql("""
        SELECT
            a.name, a.titel, a.datum, a.titelbild,
            a.oeffentlich, a.beschreibung, a.veranstaltung,
            COUNT(f.name) AS foto_count
        FROM `tabFotoalbum` a
        LEFT JOIN `tabFoto` f ON f.parent = a.name AND f.parenttype = 'Fotoalbum'
        GROUP BY a.name
        ORDER BY a.datum DESC
        LIMIT 200
    """, as_dict=True)


@frappe.whitelist()
def get_album_detail(name):
    """Fotoalbum mit allen Fotos laden — für alle eingeloggten Mitglieder."""
    _require_login()
    return frappe.get_doc("Fotoalbum", name).as_dict()


@frappe.whitelist(allow_guest=True)
def get_oeffentliche_alben():
    """Öffentliche Fotoalben mit Fotos — ohne Login zugänglich."""
    return frappe.db.sql("""
        SELECT
            a.name, a.titel, a.datum, a.titelbild, a.beschreibung,
            COUNT(f.name) AS foto_count
        FROM `tabFotoalbum` a
        LEFT JOIN `tabFoto` f ON f.parent = a.name AND f.parenttype = 'Fotoalbum'
        WHERE a.oeffentlich = 1
        GROUP BY a.name
        ORDER BY a.datum DESC
        LIMIT 12
    """, as_dict=True)


@frappe.whitelist(allow_guest=True)
def get_oeffentliches_album(name):
    """Einzelnes öffentliches Album mit Fotos laden."""
    album = frappe.get_doc("Fotoalbum", name)
    if not album.oeffentlich:
        frappe.throw("Dieses Album ist nicht öffentlich.", frappe.PermissionError)
    return album.as_dict()


def _get_current_mitglied():
    """Gibt den Mitglied-Datensatz-Namen des aktuell eingeloggten Users zurück (oder None)."""
    return frappe.db.get_value("Mitglied", {"portal_benutzer": frappe.session.user}, "name")


def _check_album_upload_berechtigung(doc, current_mitglied=None):
    """Prüft ob der aktuelle User Fotos zu diesem Album hinzufügen darf."""
    user_roles = set(frappe.get_roles(frappe.session.user))
    if user_roles & {"System Manager", "Vereins Admin"}:
        return
    berechtigung = doc.upload_berechtigung or "Alle Mitglieder"
    if berechtigung == "Nur Admin":
        frappe.throw("Sie haben keine Berechtigung, Fotos zu diesem Album hinzuzufügen.", frappe.PermissionError)
    if berechtigung == "Spartenleiter" and "Spartenleiter" not in user_roles:
        # Einzelne Mitglieder-Berechtigung prüfen
        if current_mitglied and any(r.mitglied == current_mitglied and r.darf_hochladen for r in doc.mitglied_berechtigungen or []):
            return
        frappe.throw("Nur Spartenleiter dürfen diesem Album Fotos hinzufügen.", frappe.PermissionError)
    if berechtigung == "Ausgewählte Mitglieder":
        if current_mitglied and any(r.mitglied == current_mitglied and r.darf_hochladen for r in doc.mitglied_berechtigungen or []):
            return
        frappe.throw("Sie stehen nicht auf der Liste der berechtigten Mitglieder.", frappe.PermissionError)


def _check_album_loeschen_fremde(doc, current_mitglied=None):
    """Prüft ob der User fremde Fotos löschen darf (eigene sind immer erlaubt)."""
    user_roles = set(frappe.get_roles(frappe.session.user))
    if user_roles & {"System Manager", "Vereins Admin"}:
        return
    # Einzelne Mitglieder-Berechtigung prüfen
    if current_mitglied and any(r.mitglied == current_mitglied and r.darf_loeschen for r in doc.mitglied_berechtigungen or []):
        return
    berechtigung = doc.loeschen_berechtigung or "Nur Admin"
    if berechtigung == "Nur Admin":
        frappe.throw("Nur Administratoren dürfen fremde Fotos löschen.", frappe.PermissionError)
    if berechtigung == "Spartenleiter und Admin" and "Spartenleiter" not in user_roles:
        frappe.throw("Nur Spartenleiter oder Administratoren dürfen fremde Fotos löschen.", frappe.PermissionError)


@frappe.whitelist()
def add_foto_to_album(album_name, datei, titel="", datum="", aufgenommen_von=""):
    """Foto zum Album hinzufügen — Berechtigung gemäß Album-Einstellung."""
    _require_login()
    current_mitglied = _get_current_mitglied()
    doc = frappe.get_doc("Fotoalbum", album_name)
    _check_album_upload_berechtigung(doc, current_mitglied)
    doc.append("fotos", {
        "datei": datei,
        "titel": titel or "",
        "datum": datum or frappe.utils.today(),
        "aufgenommen_von": aufgenommen_von or "",
        "hochgeladen_von": current_mitglied or "",
    })
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return doc.as_dict()


@frappe.whitelist()
def delete_foto_from_album(album_name, foto_name):
    """Foto aus dem Album entfernen. Eigene Fotos kann jeder löschen; fremde nur mit Berechtigung."""
    _require_login()
    current_mitglied = _get_current_mitglied()
    doc = frappe.get_doc("Fotoalbum", album_name)
    foto = next((f for f in doc.fotos if f.name == foto_name), None)
    if not foto:
        frappe.throw("Foto nicht gefunden.")
    # Eigenes Foto → immer erlaubt
    is_own = current_mitglied and foto.hochgeladen_von == current_mitglied
    if not is_own:
        _check_album_loeschen_fremde(doc, current_mitglied)
    doc.fotos = [f for f in doc.fotos if f.name != foto_name]
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return doc.as_dict()


@frappe.whitelist()
def set_album_titelbild(album_name, datei):
    """Titelbild des Albums setzen."""
    frappe.only_for(ADMIN_ROLLEN)
    frappe.db.set_value("Fotoalbum", album_name, "titelbild", datei)
    frappe.db.commit()
    return "OK"


@frappe.whitelist()
def get_album_berechtigung(album_name):
    """Upload- und Lösch-Berechtigung des aktuellen Users für ein Album."""
    _require_login()
    current_mitglied = _get_current_mitglied()
    doc = frappe.get_doc("Fotoalbum", album_name)
    user_roles = set(frappe.get_roles(frappe.session.user))
    is_admin = bool(user_roles & {"System Manager", "Vereins Admin"})
    is_spartenleiter = "Spartenleiter" in user_roles

    # Einzelne Mitglieder-Berechtigungen ermitteln
    mitglied_row = next((r for r in (doc.mitglied_berechtigungen or []) if r.mitglied == current_mitglied), None) if current_mitglied else None

    upload_ok = False
    if is_admin:
        upload_ok = True
    elif (doc.upload_berechtigung or "Alle Mitglieder") == "Alle Mitglieder":
        upload_ok = True
    elif doc.upload_berechtigung == "Spartenleiter" and is_spartenleiter:
        upload_ok = True
    elif mitglied_row and mitglied_row.darf_hochladen:
        upload_ok = True

    loeschen_ok = False
    if is_admin:
        loeschen_ok = True
    elif (doc.loeschen_berechtigung or "Nur Admin") == "Spartenleiter und Admin" and is_spartenleiter:
        loeschen_ok = True
    elif mitglied_row and mitglied_row.darf_loeschen:
        loeschen_ok = True

    return {
        "darf_hochladen": upload_ok,
        "darf_loeschen": loeschen_ok,
        "darf_eigene_loeschen": True,  # eigene Fotos immer löschbar
        "current_mitglied": current_mitglied or "",
        "upload_berechtigung": doc.upload_berechtigung or "Alle Mitglieder",
        "loeschen_berechtigung": doc.loeschen_berechtigung or "Nur Admin",
    }


# ─── Mitglieder-Portal ────────────────────────────────────────────────────────

@frappe.whitelist()
def get_meine_rollen():
    """Eigene Rollen des eingeloggten Benutzers — für Frontend-Berechtigungsprüfung."""
    _require_login()
    return frappe.get_roles(frappe.session.user)


@frappe.whitelist()
def get_mein_profil():
    """Eigenes Profil für Mitglieder-Portal. Jeder eingeloggte Benutzer mit Mitglied-Datensatz."""
    user = frappe.session.user
    mitglied = frappe.db.get_value("Mitglied", {"portal_benutzer": user}, "name")
    if not mitglied:
        frappe.throw(_("Kein Mitglied für diesen Benutzer gefunden."), frappe.PermissionError)
    doc = frappe.get_doc("Mitglied", mitglied)
    return {
        "name": doc.name,
        "vorname": doc.vorname,
        "nachname": doc.nachname,
        "anrede": doc.anrede,
        "geburtsdatum": doc.geburtsdatum,
        "strasse": doc.strasse,
        "plz": doc.plz,
        "ort": doc.ort,
        "telefon": doc.telefon,
        "mobil": doc.mobil,
        "email": doc.email,
        "foto": doc.foto,
        "mitgliedsnummer": doc.mitgliedsnummer,
        "mitgliedstyp": doc.mitgliedstyp,
        "eintrittsdatum": doc.eintrittsdatum,
        "status": doc.status,
        "iban": doc.iban,
        "bic": doc.bic,
        "bank_name": doc.bank_name,
        "beitragsrechnungen": doc.beitragsrechnungen,
        "sparten": doc.sparten,
    }


@frappe.whitelist()
def update_mein_profil(data):
    """Mitglied aktualisiert eigene Kontaktdaten. Jeder eingeloggte Benutzer mit Mitglied-Datensatz."""
    import json
    if isinstance(data, str):
        data = json.loads(data)
    user = frappe.session.user
    mitglied_name = frappe.db.get_value("Mitglied", {"portal_benutzer": user}, "name")
    if not mitglied_name:
        frappe.throw(_("Kein Mitglied gefunden."), frappe.PermissionError)
    erlaubte_felder = ["strasse", "plz", "ort", "telefon", "mobil",
                       "email", "iban", "bic", "bank_name"]
    doc = frappe.get_doc("Mitglied", mitglied_name)
    for f in erlaubte_felder:
        if f in data:
            setattr(doc, f, data[f])
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"success": True}


# ─── Sparten-Baukasten ────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def get_sparte_detail(name):
    """Öffentliche Sparten-Detailseite inkl. aller Sektionen."""
    doc = frappe.get_doc("Sparte", name)
    if not doc.aktiv:
        frappe.throw(_("Diese Sparte ist nicht aktiv."), frappe.DoesNotExistError)

    # Spartenleiter-Info holen
    leiter_info = None
    if doc.spartenleiter:
        m = frappe.get_doc("Mitglied", doc.spartenleiter)
        leiter_info = {
            "name": doc.spartenleiter,
            "vorname": m.vorname,
            "nachname": m.nachname,
            "email": doc.email or m.email,
            "telefon": doc.telefon or m.telefon,
            "foto": m.foto,
        }

    # Nächste Veranstaltungen dieser Sparte
    events = frappe.get_all(
        "Veranstaltung",
        filters={"sparte": name, "oeffentlich": 1,
                 "datum_von": [">=", frappe.utils.today()],
                 "status": ["!=", "Abgesagt"]},
        fields=["name", "titel", "datum_von", "uhrzeit_von",
                "veranstaltungsort", "bild"],
        order_by="datum_von asc",
        limit_page_length=5,
    )

    sektionen = []
    for s in doc.sektionen:
        sektion = s.as_dict()
        # Galerie-Bilder als JSON parsen
        if sektion.get("galerie_bilder"):
            import json as _json
            try:
                sektion["galerie_bilder_parsed"] = _json.loads(sektion["galerie_bilder"])
            except Exception:
                sektion["galerie_bilder_parsed"] = []
        sektionen.append(sektion)

    return {
        "name": doc.name,
        "name_sparte": doc.name_sparte,
        "beschreibung": doc.beschreibung,
        "icon": doc.icon,
        "farbe": doc.farbe,
        "bild": doc.bild,
        "email": doc.email,
        "telefon": doc.telefon,
        "treffpunkt": doc.treffpunkt,
        "gruendungsjahr": doc.gruendungsjahr,
        "beitrag": doc.beitrag,
        "beitrag_intervall": doc.beitrag_intervall,
        "beitrag_bezeichnung": doc.beitrag_bezeichnung,
        "spartenleiter": leiter_info,
        "anzahl_mitglieder": len(doc.mitglieder),
        "veranstaltungen": events,
        "sektionen": sektionen,
    }


@frappe.whitelist()
def save_sparte_sektionen(name, sektionen):
    """Sektionen einer Sparte speichern (Admin / Spartenleiter)."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    import json
    if isinstance(sektionen, str):
        sektionen = json.loads(sektionen)

    doc = frappe.get_doc("Sparte", name)
    doc.sektionen = []
    for idx, s in enumerate(sektionen):
        doc.append("sektionen", {
            "typ": s.get("typ", "Text"),
            "titel": s.get("titel", ""),
            "untertitel": s.get("untertitel", ""),
            "text": s.get("text", ""),
            "bild": s.get("bild", ""),
            "bild_ausrichtung": s.get("bild_ausrichtung", "Rechts"),
            "cta_text": s.get("cta_text", ""),
            "cta_link": s.get("cta_link", ""),
            "hintergrund": s.get("hintergrund", "Weiß"),
            "galerie_bilder": s.get("galerie_bilder", ""),
            "html_inhalt": s.get("html_inhalt", ""),
        })
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return doc.as_dict()


@frappe.whitelist()
def get_sparte_mitglieder(sparte_name):
    """Mitgliederliste einer Sparte für Admin-Verwaltung."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    doc = frappe.get_doc("Sparte", sparte_name)
    result = []
    for m in doc.mitglieder:
        info = frappe.db.get_value(
            "Mitglied", m.mitglied,
            ["vorname", "nachname", "mitgliedsnummer", "foto"], as_dict=True
        ) or {}
        result.append({
            "row_name": m.name,
            "mitglied": m.mitglied,
            "vorname": info.get("vorname", ""),
            "nachname": info.get("nachname", ""),
            "mitgliedsnummer": info.get("mitgliedsnummer", ""),
            "foto": info.get("foto", ""),
            "funktion": m.funktion or "",
            "von": str(m.von) if m.von else "",
            "aktiv": int(m.aktiv or 0),
        })
    return result


@frappe.whitelist()
def set_sparte_mitglieder(sparte_name, mitglieder):
    """Spartenmitglieder speichern + Spartenleiter-Rollen automatisch vergeben."""
    frappe.only_for(ADMIN_ROLLEN)
    import json as _json
    if isinstance(mitglieder, str):
        mitglieder = _json.loads(mitglieder)

    doc = frappe.get_doc("Sparte", sparte_name)
    doc.mitglieder = []
    for m in mitglieder:
        doc.append("mitglieder", {
            "mitglied": m["mitglied"],
            "funktion": m.get("funktion", ""),
            "von": m.get("von") or None,
            "aktiv": int(m.get("aktiv", 1)),
        })

    # spartenleiter + stellvertreter Felder aus funktion ableiten
    leiter = [m for m in mitglieder if m.get("funktion") == "Spartenleiter"]
    stv = [m for m in mitglieder if m.get("funktion") == "Stv. Spartenleiter"]
    doc.spartenleiter = leiter[0]["mitglied"] if leiter else None
    doc.stellvertreter = stv[0]["mitglied"] if stv else None

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    # Frappe-Rolle "Spartenleiter" mit allen Sparten synchronisieren
    _sync_spartenleiter_rollen()
    return "OK"


def _sync_spartenleiter_rollen():
    """'Spartenleiter' Frappe-Rolle anhand aller Spartenmitglied-Einträge vergeben/entziehen."""
    leiter_rows = frappe.db.sql("""
        SELECT DISTINCT sm.mitglied
        FROM `tabSpartenmitglied` sm
        WHERE sm.funktion IN ('Spartenleiter', 'Stv. Spartenleiter')
          AND sm.aktiv = 1
    """, as_dict=True)
    leiter_mitglieder = {r.mitglied for r in leiter_rows}

    # Portal-Benutzer für Spartenleiter-Mitglieder ermitteln
    soll_users = set()
    for mitglied_name in leiter_mitglieder:
        portal_user = frappe.db.get_value("Mitglied", mitglied_name, "portal_benutzer")
        if portal_user:
            soll_users.add(portal_user)

    # Aktuelle Träger der Spartenleiter-Rolle
    ist_users = {r.parent for r in frappe.db.sql(
        "SELECT DISTINCT parent FROM `tabHas Role` WHERE role='Spartenleiter' AND parenttype='User'",
        as_dict=True,
    )}

    # Neu hinzufügen
    for user in soll_users - ist_users:
        try:
            u = frappe.get_doc("User", user)
            if not any(r.role == "Spartenleiter" for r in u.roles):
                u.append("roles", {"role": "Spartenleiter"})
                u.save(ignore_permissions=True)
        except Exception:
            pass

    # Entziehen (nur wenn der User kein Soll mehr hat)
    for user in ist_users - soll_users:
        try:
            u = frappe.get_doc("User", user)
            u.roles = [r for r in u.roles if r.role != "Spartenleiter"]
            u.save(ignore_permissions=True)
        except Exception:
            pass

    frappe.db.commit()


# ─── Blog ─────────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def get_blog_liste(kategorie="", limit=12, offset=0):
    """Öffentliche Blog-Beitragsliste."""
    filters = {"status": "Veröffentlicht"}
    if kategorie:
        filters["kategorie"] = kategorie
    beitraege = frappe.get_all(
        "Blog Beitrag",
        filters=filters,
        fields=["name", "titel", "slug", "zusammenfassung", "beitragsbild",
                "autor", "veroeffentlicht_am", "kategorie"],
        order_by="veroeffentlicht_am desc",
        limit_page_length=int(limit),
        limit_start=int(offset),
    )
    # Autorname auflösen
    for b in beitraege:
        if b.get("autor"):
            fn = frappe.db.get_value("User", b["autor"], ["first_name", "last_name"])
            if fn:
                b["autor_name"] = " ".join(filter(None, [fn[0], fn[1]])) or b["autor"]
        if b.get("kategorie"):
            b["kategorie_bezeichnung"] = frappe.db.get_value(
                "Blog Kategorie", b["kategorie"], "bezeichnung") or b["kategorie"]
    total = frappe.db.count("Blog Beitrag", filters)
    return {"items": beitraege, "total": total}


@frappe.whitelist(allow_guest=True)
def get_blog_beitrag(slug):
    """Einzelnen Blog-Beitrag nach Slug oder Name."""
    name = frappe.db.get_value("Blog Beitrag", {"slug": slug, "status": "Veröffentlicht"}, "name")
    if not name:
        # Fallback: slug ist evtl. direkt der Dokumentname
        name = frappe.db.get_value("Blog Beitrag", {"name": slug, "status": "Veröffentlicht"}, "name")
    if not name:
        frappe.throw(_("Beitrag nicht gefunden."), frappe.DoesNotExistError)
    doc = frappe.get_doc("Blog Beitrag", name)
    autor_name = doc.autor
    if doc.autor:
        fn = frappe.db.get_value("User", doc.autor, ["first_name", "last_name"])
        if fn:
            autor_name = " ".join(filter(None, [fn[0], fn[1]])) or doc.autor
    kategorie_bezeichnung = ""
    if doc.kategorie:
        kategorie_bezeichnung = frappe.db.get_value("Blog Kategorie", doc.kategorie, "bezeichnung") or doc.kategorie
    sektionen = [
        {
            "typ": s.typ, "hintergrund": s.hintergrund or "Weiß",
            "titel": s.titel or "", "text": s.text or "",
            "bild": s.bild or "", "bildunterschrift": s.bildunterschrift or "",
            "bild_ausrichtung": s.bild_ausrichtung or "Rechts",
            "bilder": s.bilder or "", "video_url": s.video_url or "",
            "zitat_autor": s.zitat_autor or "", "info_typ": s.info_typ or "Info",
            "autoplay": s.autoplay, "html_inhalt": s.html_inhalt or "",
        }
        for s in (doc.sektionen or [])
    ]
    return {
        "name": doc.name,
        "titel": doc.titel,
        "slug": doc.slug,
        "inhalt": doc.inhalt,
        "zusammenfassung": doc.zusammenfassung,
        "beitragsbild": doc.beitragsbild,
        "autor": doc.autor,
        "autor_name": autor_name,
        "veroeffentlicht_am": doc.veroeffentlicht_am,
        "kategorie": doc.kategorie,
        "kategorie_bezeichnung": kategorie_bezeichnung,
        "sektionen": sektionen,
    }


@frappe.whitelist(allow_guest=True)
def get_blog_kategorien():
    """Alle Blog-Kategorien."""
    return frappe.get_all(
        "Blog Kategorie",
        fields=["name", "bezeichnung", "slug", "beschreibung", "bild"],
        order_by="bezeichnung",
    )


@frappe.whitelist()
def get_blog_liste_admin(limit=50, offset=0):
    """Admin-Blog-Liste (alle Status)."""
    frappe.only_for(ADMIN_ROLLEN + ["Blogger"])
    user = frappe.session.user
    rollen = frappe.get_roles(user)
    filters = {}
    # Blogger sehen nur eigene Beiträge
    if "Blogger" in rollen and not any(r in rollen for r in ADMIN_ROLLEN):
        filters["autor"] = user
    beitraege = frappe.get_all(
        "Blog Beitrag",
        filters=filters,
        fields=["name", "titel", "slug", "status", "autor",
                "veroeffentlicht_am", "kategorie", "beitragsbild"],
        order_by="modified desc",
        limit_page_length=int(limit),
        limit_start=int(offset),
    )
    for b in beitraege:
        if b.get("kategorie"):
            b["kategorie_bezeichnung"] = frappe.db.get_value(
                "Blog Kategorie", b["kategorie"], "bezeichnung") or b["kategorie"]
        else:
            b["kategorie_bezeichnung"] = ""
    return {"items": beitraege, "total": frappe.db.count("Blog Beitrag", filters)}


@frappe.whitelist()
def save_blog_beitrag(data):
    """Blog-Beitrag anlegen oder speichern."""
    frappe.only_for(ADMIN_ROLLEN + ["Blogger"])
    import json
    if isinstance(data, str):
        data = json.loads(data)
    erlaubte = ["titel", "slug", "inhalt", "zusammenfassung", "beitragsbild",
                "kategorie", "status", "veroeffentlicht_am"]
    name = data.get("name")
    if name:
        doc = frappe.get_doc("Blog Beitrag", name)
        rollen = frappe.get_roles(frappe.session.user)
        if "Blogger" in rollen and not any(r in rollen for r in ADMIN_ROLLEN):
            if doc.autor != frappe.session.user:
                frappe.throw(_("Keine Berechtigung, diesen Beitrag zu bearbeiten."),
                             frappe.PermissionError)
    else:
        doc = frappe.new_doc("Blog Beitrag")
        doc.autor = frappe.session.user
    for f in erlaubte:
        if f in data:
            setattr(doc, f, data[f])
    if data.get("status") == "Veröffentlicht" and not doc.veroeffentlicht_am:
        doc.veroeffentlicht_am = frappe.utils.today()
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return doc.as_dict()


@frappe.whitelist()
def get_blog_beitrag_admin(name):
    """Einzelnen Blog-Beitrag für den Baukasten laden (inkl. Sektionen)."""
    frappe.only_for(ADMIN_ROLLEN + ["Blogger"])
    doc = frappe.get_doc("Blog Beitrag", name)
    rollen = frappe.get_roles(frappe.session.user)
    if "Blogger" in rollen and not any(r in rollen for r in ADMIN_ROLLEN):
        if doc.autor != frappe.session.user:
            frappe.throw(_("Keine Berechtigung."), frappe.PermissionError)
    sektionen = [
        {
            "typ": s.typ, "hintergrund": s.hintergrund or "Weiß",
            "titel": s.titel or "", "text": s.text or "",
            "bild": s.bild or "", "bildunterschrift": s.bildunterschrift or "",
            "bild_ausrichtung": s.bild_ausrichtung or "Rechts",
            "bilder": s.bilder or "", "video_url": s.video_url or "",
            "zitat_autor": s.zitat_autor or "", "info_typ": s.info_typ or "Info",
            "autoplay": s.autoplay, "html_inhalt": s.html_inhalt or "",
        }
        for s in (doc.sektionen or [])
    ]
    return {
        "name": doc.name,
        "titel": doc.titel,
        "slug": doc.slug,
        "status": doc.status,
        "sektionen": sektionen,
    }


@frappe.whitelist()
def save_blog_sektionen(beitrag_name, sektionen):
    """Baukasten-Sektionen eines Blog-Beitrags speichern."""
    frappe.only_for(ADMIN_ROLLEN + ["Blogger"])
    import json
    if isinstance(sektionen, str):
        sektionen = json.loads(sektionen)
    doc = frappe.get_doc("Blog Beitrag", beitrag_name)
    rollen = frappe.get_roles(frappe.session.user)
    if "Blogger" in rollen and not any(r in rollen for r in ADMIN_ROLLEN):
        if doc.autor != frappe.session.user:
            frappe.throw(_("Keine Berechtigung."), frappe.PermissionError)
    erlaubte_felder = ["typ", "hintergrund", "titel", "text", "bild", "bildunterschrift",
                       "bild_ausrichtung", "bilder", "video_url", "zitat_autor", "info_typ",
                       "autoplay", "html_inhalt"]
    neue_sektionen = []
    for s in sektionen:
        row = {f: s.get(f, "") for f in erlaubte_felder}
        neue_sektionen.append(row)
    doc.set("sektionen", neue_sektionen)
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return "OK"


@frappe.whitelist()
def get_meine_blog_beitraege():
    """Alle Blog-Beiträge des eingeloggten Bloggers."""
    frappe.only_for(ADMIN_ROLLEN + ["Blogger"])
    user = frappe.session.user
    rollen = frappe.get_roles(user)
    filters = {} if any(r in rollen for r in ADMIN_ROLLEN) else {"autor": user}
    beitraege = frappe.get_all(
        "Blog Beitrag",
        filters=filters,
        fields=["name", "titel", "slug", "status", "veroeffentlicht_am",
                "kategorie", "beitragsbild", "autor"],
        order_by="modified desc",
    )
    return beitraege


@frappe.whitelist()
def delete_blog_beitrag(name):
    """Blog-Beitrag löschen."""
    frappe.only_for(ADMIN_ROLLEN)
    frappe.delete_doc("Blog Beitrag", name, ignore_permissions=True, force=True)
    frappe.db.commit()
    return "OK"


@frappe.whitelist()
def save_blog_kategorie(data):
    """Blog-Kategorie anlegen oder speichern."""
    frappe.only_for(ADMIN_ROLLEN)
    import json
    if isinstance(data, str):
        data = json.loads(data)
    name = data.get("name")
    if name:
        doc = frappe.get_doc("Blog Kategorie", name)
    else:
        doc = frappe.new_doc("Blog Kategorie")
    for f in ["bezeichnung", "slug", "beschreibung", "bild"]:
        if f in data:
            setattr(doc, f, data[f])
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return doc.as_dict()


# ─── Beitragsklassen & Rechnungen ────────────────────────────────────────────

@frappe.whitelist()
def get_beitragsklassen():
    """Alle Mitgliedstypen als Beitragsklassen (mit Beitragsdetails)."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    return frappe.get_all(
        "Mitgliedstyp",
        fields=["name", "bezeichnung", "beitragsbetrag", "zahlungsintervall",
                "min_alter", "max_alter", "aktiv", "farbe", "stimmberechtigt",
                "beschreibung", "ist_standardklasse"],
        order_by="bezeichnung",
    )


@frappe.whitelist()
def save_beitragsklasse(data):
    """Mitgliedstyp/Beitragsklasse speichern."""
    frappe.only_for(ADMIN_ROLLEN)
    import json
    if isinstance(data, str):
        data = json.loads(data)
    name = data.get("name")
    if name:
        doc = frappe.get_doc("Mitgliedstyp", name)
    else:
        doc = frappe.new_doc("Mitgliedstyp")
    for f in ["bezeichnung", "beitragsbetrag", "zahlungsintervall",
              "min_alter", "max_alter", "aktiv", "farbe", "stimmberechtigt",
              "beschreibung", "ist_standardklasse"]:
        if f in data:
            setattr(doc, f, data[f])
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return doc.as_dict()


@frappe.whitelist()
def delete_beitragsklasse(name):
    """Mitgliedstyp löschen (nur wenn keine Mitglieder zugewiesen)."""
    frappe.only_for(ADMIN_ROLLEN)
    count = frappe.db.count("Mitglied", {"mitgliedstyp": name})
    if count > 0:
        frappe.throw(f"Diese Beitragsklasse ist bei {count} Mitglied(ern) zugewiesen und kann nicht gelöscht werden.")
    frappe.delete_doc("Mitgliedstyp", name, ignore_permissions=True, force=True)
    frappe.db.commit()
    return "OK"


@frappe.whitelist()
def auto_beitragsklasse_zuweisen():
    """Weist aktiven Mitgliedern automatisch die passende Beitragsklasse anhand des Alters zu.
    Klassen mit Altersregel werden zuerst geprüft; wer nicht passt, bekommt die Standardklasse."""
    frappe.only_for(ADMIN_ROLLEN)
    klassen = frappe.get_all(
        "Mitgliedstyp",
        filters={"aktiv": 1},
        fields=["name", "bezeichnung", "min_alter", "max_alter", "ist_standardklasse"],
        order_by="min_alter",
    )
    altersklassen = [k for k in klassen if (k.min_alter or 0) > 0 or (k.max_alter or 0) > 0]
    standardklasse = next((k for k in klassen if k.ist_standardklasse), None)

    if not altersklassen and not standardklasse:
        return {
            "geaendert": 0,
            "info": "Keine Altersregeln und keine Standardklasse konfiguriert. "
                    "Setze Mindestalter/Höchstalter oder markiere eine Klasse als Standardklasse.",
        }

    today = frappe.utils.today()
    mitglieder = frappe.get_all(
        "Mitglied",
        filters={"status": "Aktiv"},
        fields=["name", "geburtsdatum", "mitgliedstyp"],
    )
    geaendert = 0
    kein_geburtsdatum = 0
    kein_match = 0
    details = []

    for m in mitglieder:
        if not m.geburtsdatum:
            kein_geburtsdatum += 1
            continue
        alter = frappe.utils.date_diff(today, str(m.geburtsdatum)) // 365
        neue_klasse = None

        for k in altersklassen:
            min_a = k.min_alter or 0
            max_a = k.max_alter or 999
            if min_a <= alter <= max_a:
                neue_klasse = k.name
                break

        # Kein Treffer bei Altersregeln → Standardklasse
        if not neue_klasse and standardklasse:
            neue_klasse = standardklasse.name

        if not neue_klasse:
            kein_match += 1
            continue

        if neue_klasse != m.mitgliedstyp:
            frappe.db.set_value("Mitglied", m.name, "mitgliedstyp", neue_klasse)
            details.append({"mitglied": m.name, "neu": neue_klasse})
            geaendert += 1

    frappe.db.commit()

    regeln_info = [f"{k.bezeichnung} ({k.min_alter or 0}–{k.max_alter or '∞'} J.)" for k in altersklassen]
    if standardklasse:
        regeln_info.append(f"{standardklasse.bezeichnung} (Standardklasse/Fallback)")

    return {
        "geaendert": geaendert,
        "kein_geburtsdatum": kein_geburtsdatum,
        "kein_match": kein_match,
        "gesamt": len(mitglieder),
        "altersklassen": regeln_info,
        "details": details,
    }


@frappe.whitelist()
def generiere_beitragsrechnungen(jahr):
    """Generiert für alle aktiven Mitglieder eine Beitragsrechnung für das Jahr."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    jahr = int(jahr)
    mitglieder = frappe.get_all(
        "Mitglied",
        filters={"status": "Aktiv"},
        fields=["name", "mitgliedsnummer", "mitgliedstyp"],
    )
    erstellt = 0
    uebersprungen = 0
    for m in mitglieder:
        if not m.mitgliedstyp:
            uebersprungen += 1
            continue
        # Prüfen ob schon eine Rechnung für dieses Jahr existiert
        existing = frappe.db.exists(
            "Beitragsrechnung",
            {"parent": m.name, "parentfield": "beitragsrechnungen", "jahr": jahr}
        )
        if existing:
            uebersprungen += 1
            continue
        typdoc = frappe.get_doc("Mitgliedstyp", m.mitgliedstyp)
        betrag = typdoc.beitragsbetrag or 0
        if betrag <= 0:
            uebersprungen += 1
            continue
        # Rechnungsnummer: VEREIN-JAHR-MITGLIEDSNR-001
        lfd = frappe.db.count(
            "Beitragsrechnung",
            {"parent": m.name, "parentfield": "beitragsrechnungen", "jahr": jahr}
        ) + 1
        rnr = f"BR-{jahr}-{m.mitgliedsnummer or m.name}-{lfd:03d}"
        mitglied_doc = frappe.get_doc("Mitglied", m.name)
        mitglied_doc.append("beitragsrechnungen", {
            "rechnungsnummer": rnr,
            "jahr": jahr,
            "mitgliedstyp": m.mitgliedstyp,
            "betrag": betrag,
            "faelligkeit": f"{jahr}-01-31",
            "status": "Offen",
            "zahlungsart": "SEPA Lastschrift" if mitglied_doc.iban else "Überweisung",
        })
        mitglied_doc.save(ignore_permissions=True)
        erstellt += 1
    frappe.db.commit()
    _notify("Rechnung", "neu")
    return {"erstellt": erstellt, "uebersprungen": uebersprungen}


@frappe.whitelist()
def get_alle_rechnungen(jahr="", status="", search="", limit=100, offset=0):
    """Alle Beitragsrechnungen aller Mitglieder."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    filters = [
        ["Beitragsrechnung", "parenttype", "=", "Mitglied"],
        ["Beitragsrechnung", "parentfield", "=", "beitragsrechnungen"],
    ]
    if jahr:
        filters.append(["Beitragsrechnung", "jahr", "=", int(jahr)])
    if status:
        filters.append(["Beitragsrechnung", "status", "=", status])
    rows = frappe.get_all(
        "Beitragsrechnung",
        filters=filters,
        fields=["name", "parent", "rechnungsnummer", "jahr", "mitgliedstyp",
                "betrag", "faelligkeit", "status", "zahlungsdatum", "zahlungsart"],
        order_by="faelligkeit desc, parent asc",
        limit_page_length=int(limit),
        limit_start=int(offset),
    )
    # Mitgliedsnamen dazu holen
    for r in rows:
        m = frappe.db.get_value("Mitglied", r.parent, ["vorname", "nachname", "mitgliedsnummer"], as_dict=True)
        if m:
            r["mitglied_name"] = f"{m.vorname} {m.nachname}"
            r["mitgliedsnummer"] = m.mitgliedsnummer or m.name
    # Summen
    total = frappe.db.count("Beitragsrechnung", filters)
    offen = frappe.db.count("Beitragsrechnung", filters + [["Beitragsrechnung", "status", "=", "Offen"]])
    return {"rows": rows, "total": total, "offen": offen}


@frappe.whitelist()
def update_rechnung_status(parent, row_name, status, zahlungsdatum=""):
    """Status einer Beitragsrechnung setzen (z.B. 'Bezahlt')."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    update = {"status": status}
    if zahlungsdatum:
        update["zahlungsdatum"] = zahlungsdatum
    elif status == "Bezahlt" and not zahlungsdatum:
        update["zahlungsdatum"] = frappe.utils.today()
    frappe.db.set_value("Beitragsrechnung", row_name, update)
    frappe.db.commit()
    _notify("Rechnung", "update", row_name)
    return "OK"


@frappe.whitelist()
def get_rechnung_html(parent, row_name):
    """Liefert druckbares HTML für eine Beitragsrechnung."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    r = frappe.get_doc("Beitragsrechnung", row_name)
    mitglied = frappe.get_doc("Mitglied", parent)
    verein = frappe.get_doc("Vereins Konfiguration", "Vereins Konfiguration") if frappe.db.exists("Vereins Konfiguration", "Vereins Konfiguration") else None

    def fmt_eur(val):
        return f"{float(val or 0):.2f} €".replace(".", ",")

    def fmt_date(d):
        if not d:
            return "—"
        import datetime
        if isinstance(d, str):
            d = datetime.date.fromisoformat(d)
        return d.strftime("%d.%m.%Y")

    vname = verein.vereinsname if verein else "Verein"
    vstrasse = verein.strasse if verein else ""
    vort = f"{verein.plz} {verein.ort}" if verein else ""
    viban = verein.iban if (verein and hasattr(verein, "iban")) else ""

    html = f"""<!DOCTYPE html>
<html lang="de">
<head><meta charset="UTF-8"><style>
  body {{font-family:Arial,sans-serif;font-size:12px;color:#222;margin:40px}}
  .header {{display:flex;justify-content:space-between;margin-bottom:30px}}
  .title {{font-size:22px;font-weight:bold;margin:20px 0 8px}}
  table {{width:100%;border-collapse:collapse;margin:15px 0}}
  th {{background:#f1f5f9;text-align:left;padding:8px 10px;border-bottom:2px solid #cbd5e1}}
  td {{padding:8px 10px;border-bottom:1px solid #e2e8f0}}
  .total {{font-weight:bold;font-size:14px}}
  .footer {{margin-top:40px;font-size:11px;color:#666;border-top:1px solid #e2e8f0;padding-top:15px}}
  @media print {{body{{margin:20px}} .no-print{{display:none}}}}
</style></head>
<body>
<div class="header">
  <div><strong>{vname}</strong><br>{vstrasse}<br>{vort}</div>
  <div style="text-align:right"><strong>Beitragsrechnung</strong><br>Nr.: {r.rechnungsnummer or r.name}<br>Datum: {fmt_date(frappe.utils.today())}</div>
</div>
<hr>
<p><strong>An:</strong><br>
{mitglied.vorname} {mitglied.nachname}<br>
{mitglied.strasse or ''}<br>
{mitglied.plz or ''} {mitglied.ort or ''}</p>
<div class="title">Beitragsrechnung {r.jahr}</div>
<table>
  <thead><tr><th>Beschreibung</th><th>Zeitraum</th><th style="text-align:right">Betrag</th></tr></thead>
  <tbody>
    <tr>
      <td>Mitgliedsbeitrag ({r.mitgliedstyp or 'Standard'})</td>
      <td>01.01.{r.jahr} – 31.12.{r.jahr}</td>
      <td style="text-align:right">{fmt_eur(r.betrag)}</td>
    </tr>
  </tbody>
  <tfoot>
    <tr class="total">
      <td colspan="2">Gesamtbetrag</td>
      <td style="text-align:right">{fmt_eur(r.betrag)}</td>
    </tr>
  </tfoot>
</table>
<p><strong>Fälligkeitsdatum:</strong> {fmt_date(r.faelligkeit)}<br>
<strong>Zahlungsart:</strong> {r.zahlungsart or 'Überweisung'}</p>
{"<p><strong>Bankverbindung:</strong><br>Kreditinstitut: " + (verein.bank_name if (verein and hasattr(verein,'bank_name')) else '') + "<br>IBAN: " + viban + "</p>" if viban else ""}
<p>Bitte überweisen Sie den Betrag bis zum {fmt_date(r.faelligkeit)} auf unser Vereinskonto.</p>
<div class="footer">Mitgliedsnummer: {mitglied.mitgliedsnummer or mitglied.name or '—'} | Status: {r.status}</div>
</body></html>"""
    return html


# ─── SEPA Portal ──────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_mein_sepa_mandat():
    """Aktives SEPA-Mandat des eingeloggten Mitglieds."""
    _require_login()
    mitglied_name = frappe.db.get_value("Mitglied", {"portal_benutzer": frappe.session.user}, "name")
    if not mitglied_name:
        return None
    rows = frappe.db.sql("""
        SELECT name, mandatsreferenz, status, kontoinhaber, iban,
               bic, bank_name, erteilungsdatum, art, anzahl_einzuege
        FROM `tabSEPA Mandat`
        WHERE mitglied = %s
          AND status = 'Aktiv'
          AND iban IS NOT NULL
          AND iban != ''
        LIMIT 1
    """, (mitglied_name,), as_dict=True)
    return dict(rows[0]) if rows else None


@frappe.whitelist()
def create_mein_sepa_mandat(iban, kontoinhaber, bank_name="", bic=""):
    """SEPA-Lastschriftmandat für das eigene Mitglied anlegen."""
    _require_login()
    mitglied_name = frappe.db.get_value("Mitglied", {"portal_benutzer": frappe.session.user}, "name")
    if not mitglied_name:
        frappe.throw("Kein verknüpftes Mitglied gefunden.")
    existing = frappe.db.get_value("SEPA Mandat", {"mitglied": mitglied_name, "status": "Aktiv"}, "name")
    if existing:
        frappe.throw("Sie haben bereits ein aktives Lastschriftmandat.")
    verein = frappe.db.get_value("Vereins Konfiguration", "Vereins Konfiguration",
                                  ["sepa_mandatsreferenz_prefix"], as_dict=True)
    prefix = (verein.sepa_mandatsreferenz_prefix or "MANDAT") if verein else "MANDAT"
    today = frappe.utils.today()
    ref = f"{prefix}-{mitglied_name}-{today}".replace(" ", "")[:35]
    iban_clean = iban.replace(" ", "").upper()
    bic_clean = bic.replace(" ", "").upper() if bic else ""
    # Bankdaten auch im Mitglied aktualisieren
    frappe.db.set_value("Mitglied", mitglied_name,
                        {"iban": iban_clean, "bic": bic_clean, "bank_name": bank_name})
    doc = frappe.get_doc({
        "doctype": "SEPA Mandat",
        "mandatsreferenz": ref,
        "status": "Aktiv",
        "mitglied": mitglied_name,
        "kontoinhaber": kontoinhaber,
        "iban": iban_clean,
        "bic": bic_clean,
        "bank_name": bank_name,
        "erteilungsdatum": today,
        "art": "CORE (Basis)",
        "anzahl_einzuege": 0,
    })
    doc.flags.ignore_permissions = True
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    frappe.publish_realtime("sepa_mandat_update", {"action": "neu", "mandat": doc.name}, room="all")
    return {"name": doc.name, "mandatsreferenz": ref}


@frappe.whitelist()
def widerruf_mein_sepa_mandat():
    """Eigenes SEPA-Mandat widerrufen."""
    _require_login()
    mitglied_name = frappe.db.get_value("Mitglied", {"portal_benutzer": frappe.session.user}, "name")
    if not mitglied_name:
        frappe.throw("Kein verknüpftes Mitglied gefunden.")
    mandat_name = frappe.db.get_value("SEPA Mandat", {"mitglied": mitglied_name, "status": "Aktiv"}, "name")
    if not mandat_name:
        frappe.throw("Kein aktives Mandat gefunden.")
    doc = frappe.get_doc("SEPA Mandat", mandat_name)
    doc.status = "Widerrufen"
    doc.widerrufen_am = frappe.utils.today()
    doc.widerrufsgrund = "Widerruf durch Mitglied über das Portal"
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    frappe.publish_realtime("sepa_mandat_update", {"action": "widerruf", "mandat": mandat_name}, room="all")
    return "OK"


# ─── Veranstaltungs-Anmeldung ─────────────────────────────────────────────────

@frappe.whitelist()
def anmelden_veranstaltung(veranstaltung_name):
    """Aktuell eingeloggtes Mitglied für eine Veranstaltung anmelden."""
    user = frappe.session.user
    mitglied_name = frappe.db.get_value("Mitglied", {"portal_benutzer": user}, "name")
    if not mitglied_name:
        frappe.throw("Kein verknüpftes Mitglied gefunden.")
    ev = frappe.get_doc("Veranstaltung", veranstaltung_name)
    # Bereits angemeldet?
    for a in ev.anmeldungen:
        if a.mitglied == mitglied_name and a.status != "Abgesagt":
            frappe.throw("Du bist bereits angemeldet.")
    # Kapazität prüfen
    aktive = [a for a in ev.anmeldungen if a.status in ("Angemeldet", "Anwesend")]
    if ev.max_teilnehmer and len(aktive) >= ev.max_teilnehmer:
        status = "Warteliste"
    else:
        status = "Angemeldet"
    ev.append("anmeldungen", {
        "mitglied": mitglied_name,
        "anmeldedatum": frappe.utils.now(),
        "status": status,
    })
    ev.save(ignore_permissions=True)
    frappe.db.commit()
    _notify("Veranstaltung", "update", veranstaltung_name)
    return {"status": status}


@frappe.whitelist()
def abmelden_veranstaltung(veranstaltung_name):
    """Aktuell eingeloggtes Mitglied von Veranstaltung abmelden."""
    user = frappe.session.user
    mitglied_name = frappe.db.get_value("Mitglied", {"portal_benutzer": user}, "name")
    if not mitglied_name:
        frappe.throw("Kein verknüpftes Mitglied gefunden.")
    # Direkt per DB suchen statt über get_doc (vermeidet Caching-Probleme)
    row_name = frappe.db.get_value(
        "Veranstaltungsanmeldung",
        {"parent": veranstaltung_name, "mitglied": mitglied_name,
         "status": ["!=", "Abgesagt"], "parenttype": "Veranstaltung"},
        "name",
    )
    if not row_name:
        frappe.throw("Keine aktive Anmeldung gefunden.")
    frappe.db.set_value("Veranstaltungsanmeldung", row_name, "status", "Abgesagt")
    frappe.db.commit()
    _notify("Veranstaltung", "update", veranstaltung_name)
    return "OK"


@frappe.whitelist()
def get_meine_anmeldungen():
    """Alle Veranstaltungsanmeldungen des eingeloggten Mitglieds."""
    user = frappe.session.user
    mitglied_name = frappe.db.get_value("Mitglied", {"portal_benutzer": user}, "name")
    if not mitglied_name:
        return []
    rows = frappe.get_all(
        "Veranstaltungsanmeldung",
        filters={"mitglied": mitglied_name, "parenttype": "Veranstaltung",
                 "status": ["!=", "Abgesagt"]},
        fields=["name", "parent", "status", "anmeldedatum"],
    )
    result = []
    for r in rows:
        ev = frappe.db.get_value("Veranstaltung", r.parent,
            ["titel", "datum_von", "uhrzeit_von", "veranstaltungsort", "status", "bild"], as_dict=True)
        if ev and ev.status != "Abgesagt":
            result.append({
                "name": r.name,
                "veranstaltung": r.parent,
                "anmeldung_status": r.status,   # Anmeldungs-Status (Angemeldet/Warteliste)
                "anmeldedatum": str(r.anmeldedatum) if r.anmeldedatum else "",
                "titel": ev.titel,
                "datum_von": str(ev.datum_von) if ev.datum_von else "",
                "uhrzeit_von": ev.uhrzeit_von or "",
                "veranstaltungsort": ev.veranstaltungsort or "",
                "bild": ev.bild or "",
            })
    return sorted(result, key=lambda x: x.get("datum_von") or "")


@frappe.whitelist()
def get_veranstaltung_anmeldungen(veranstaltung_name):
    """Teilnehmerliste einer Veranstaltung (Admin)."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    rows = frappe.get_all(
        "Veranstaltungsanmeldung",
        filters={"parent": veranstaltung_name, "parentfield": "anmeldungen"},
        fields=["name", "mitglied", "name_gast", "status", "anmeldedatum", "anmerkung"],
        order_by="anmeldedatum",
    )
    for r in rows:
        if r.mitglied:
            m = frappe.db.get_value("Mitglied", r.mitglied,
                ["vorname", "nachname", "email", "mitgliedsnummer"], as_dict=True)
            if m:
                r["vollname"] = f"{m.vorname} {m.nachname}"
                r["email"] = m.email
                r["mitgliedsnummer"] = m.mitgliedsnummer or m.name
        else:
            r["vollname"] = r.name_gast or "Gast"
    return rows


@frappe.whitelist()
def update_anmeldung_status(row_name, status):
    """Status einer Veranstaltungsanmeldung ändern (Admin)."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    frappe.db.set_value("Veranstaltungsanmeldung", row_name, "status", status)
    frappe.db.commit()
    _notify("Veranstaltung", "update")
    return "OK"


# ─── Massen-E-Mail ────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_email_gruppen():
    """Verfügbare Empfängergruppen für Massen-E-Mail."""
    frappe.only_for(ADMIN_ROLLEN)
    typen = frappe.get_all("Mitgliedstyp", filters={"aktiv": 1},
                           fields=["name", "bezeichnung"], order_by="bezeichnung")
    sparten = frappe.get_all("Sparte", filters={"aktiv": 1},
                             fields=["name", "name_sparte"], order_by="name_sparte")
    return {
        "standard": [
            {"key": "alle", "label": "Alle aktiven Mitglieder"},
            {"key": "mit_email", "label": "Alle Mitglieder mit E-Mail"},
            {"key": "mit_portal", "label": "Mitglieder mit Portal-Zugang"},
        ],
        "mitgliedstypen": [{"key": f"typ:{t.name}", "label": t.bezeichnung} for t in typen],
        "sparten": [{"key": f"sparte:{s.name}", "label": s.name_sparte} for s in sparten],
    }


@frappe.whitelist()
def get_email_empfaenger_vorschau(gruppe):
    """Zeigt wie viele Empfänger eine Gruppe hat."""
    frappe.only_for(ADMIN_ROLLEN)
    emails = _get_emails_fuer_gruppe(gruppe)
    return {"anzahl": len(emails), "vorschau": emails[:5]}


@frappe.whitelist()
def send_massen_email(gruppe, betreff, inhalt, test_empfaenger=""):
    """Sendet Massen-E-Mail an eine Mitgliedergruppe mit Template-Variablen."""
    frappe.only_for(ADMIN_ROLLEN)
    verein = frappe.db.get_value("Vereins Konfiguration", "Vereins Konfiguration",
                                  "vereinsname") if frappe.db.exists("Vereins Konfiguration", "Vereins Konfiguration") else "Verein"

    def render(text, kontext):
        try:
            return frappe.render_template(text, kontext)
        except Exception:
            return text

    if test_empfaenger:
        mitglieder = _get_mitglieder_fuer_gruppe(gruppe)
        zeilen = ""
        for m in mitglieder[:30]:
            kontext = {
                "vorname": m.get("vorname") or "",
                "nachname": m.get("nachname") or "",
                "vollname": f'{m.get("vorname") or ""} {m.get("nachname") or ""}'.strip(),
                "mitgliedsnummer": m.get("name") or m.get("mitgliedsnummer") or "",
                "email": m.get("email") or "",
                "verein": verein,
            }
            zeilen += f"""<tr style="border-bottom:1px solid #e2e8f0">
              <td style="padding:6px 10px;font-size:12px;color:#64748b;white-space:nowrap">{kontext['mitgliedsnummer']}</td>
              <td style="padding:6px 10px;font-size:12px;font-weight:600;white-space:nowrap">{kontext['vollname']}</td>
              <td style="padding:6px 10px;font-size:12px;color:#64748b;white-space:nowrap">{m.get('email','')}</td>
              <td style="padding:6px 10px;font-size:12px"><b>Betreff:</b> {render(betreff, kontext)}<br>
                <div style="margin-top:4px;padding:6px 8px;background:#f8fafc;border-radius:4px;border:1px solid #e2e8f0">{render(inhalt, kontext)}</div>
              </td></tr>"""
        mehr = f'<p style="color:#94a3b8;font-size:12px;padding:8px 10px">… und {len(mitglieder)-30} weitere Empfänger</p>' if len(mitglieder) > 30 else ""
        vorschau_html = f"""<div style="font-family:sans-serif;max-width:960px">
          <h2 style="color:#1e293b;margin-bottom:4px">Vorschau Massen-E-Mail</h2>
          <p style="color:#64748b;margin-top:0">Gruppe: <b>{gruppe}</b> &bull; {len(mitglieder)} Empfänger</p>
          <table style="width:100%;border-collapse:collapse;border:1px solid #e2e8f0">
            <thead><tr style="background:#f1f5f9">
              <th style="padding:8px 10px;text-align:left;font-size:12px;color:#64748b">Nr.</th>
              <th style="padding:8px 10px;text-align:left;font-size:12px;color:#64748b">Name</th>
              <th style="padding:8px 10px;text-align:left;font-size:12px;color:#64748b">E-Mail</th>
              <th style="padding:8px 10px;text-align:left;font-size:12px;color:#64748b">Personalisierter Inhalt</th>
            </tr></thead>
            <tbody>{zeilen}</tbody>
          </table>{mehr}</div>"""
        frappe.sendmail(
            recipients=[test_empfaenger],
            subject=f"[VORSCHAU] {betreff} ({len(mitglieder)} Empfänger)",
            message=vorschau_html,
            delayed=False,
        )
        return {"gesendet": 0, "test": True, "anzahl": len(mitglieder)}

    mitglieder = _get_mitglieder_fuer_gruppe(gruppe)
    if not mitglieder:
        frappe.throw("Keine E-Mail-Adressen in dieser Gruppe gefunden.")

    for m in mitglieder:
        try:
            kontext = {
                "vorname": m.get("vorname") or "",
                "nachname": m.get("nachname") or "",
                "vollname": f'{m.get("vorname") or ""} {m.get("nachname") or ""}'.strip(),
                "mitgliedsnummer": m.get("name") or m.get("mitgliedsnummer") or "",
                "email": m.get("email") or "",
                "verein": verein,
            }
            frappe.sendmail(
                recipients=[m["email"]],
                subject=render(betreff, kontext),
                message=render(inhalt, kontext),
                sender_full_name=verein,
                delayed=True,
            )
        except Exception:
            pass
    frappe.db.commit()
    return {"gesendet": len(mitglieder)}


def _get_mitglieder_fuer_gruppe(gruppe):
    """Hilfsfunktion: Mitgliedsdaten (inkl. E-Mail) für eine Empfängergruppe."""
    felder = ["name", "vorname", "nachname", "email", "mitgliedsnummer"]
    filters = {"status": "Aktiv"}
    if gruppe == "alle" or gruppe == "mit_email":
        pass
    elif gruppe == "mit_portal":
        filters["portal_aktiv"] = 1
    elif gruppe.startswith("typ:"):
        filters["mitgliedstyp"] = gruppe[4:]
    elif gruppe.startswith("sparte:"):
        sparte_name = gruppe[7:]
        mitglied_names = frappe.db.sql(
            "SELECT DISTINCT parent FROM `tabSpartenmitglied` WHERE sparte=%s",
            sparte_name, as_list=True
        )
        rows = frappe.get_all("Mitglied",
            filters={"name": ["in", [r[0] for r in mitglied_names]], "status": "Aktiv"},
            fields=felder)
        return [r for r in rows if r.get("email")]
    rows = frappe.get_all("Mitglied", filters=filters, fields=felder)
    return [r for r in rows if r.get("email")]

def _get_emails_fuer_gruppe(gruppe):
    return [m["email"] for m in _get_mitglieder_fuer_gruppe(gruppe)]


# ─── E-Mail Konfiguration ─────────────────────────────────────────────────────

@frappe.whitelist()
def get_email_konfiguration():
    """Aktuelle ausgehende E-Mail-Einstellungen lesen."""
    frappe.only_for(ADMIN_ROLLEN)
    acc = frappe.db.get_value(
        "Email Account",
        {"enable_outgoing": 1, "default_outgoing": 1},
        ["name", "email_id", "smtp_server", "smtp_port",
         "use_tls", "use_ssl", "login_id", "enable_outgoing", "default_outgoing"],
        as_dict=True,
    )
    if not acc:
        # Ersten ausgehenden nehmen
        acc = frappe.db.get_value(
            "Email Account",
            {"enable_outgoing": 1},
            ["name", "email_id", "smtp_server", "smtp_port",
             "use_tls", "use_ssl", "login_id", "enable_outgoing", "default_outgoing"],
            as_dict=True,
        )
    return acc or {}


@frappe.whitelist()
def save_email_konfiguration(data):
    """SMTP-Einstellungen speichern / Email Account anlegen oder aktualisieren."""
    frappe.only_for(ADMIN_ROLLEN)
    import json
    if isinstance(data, str):
        data = json.loads(data)

    email_id = data.get("email_id", "").strip()
    if not email_id:
        frappe.throw("E-Mail-Adresse darf nicht leer sein.")

    # Bestehendes Konto suchen (nach Name oder email_id)
    existing_name = data.get("name") or frappe.db.get_value("Email Account", {"email_id": email_id}, "name")

    if existing_name and frappe.db.exists("Email Account", existing_name):
        doc = frappe.get_doc("Email Account", existing_name)
    else:
        doc = frappe.new_doc("Email Account")
        doc.email_account_name = data.get("email_account_name") or email_id.split("@")[0]

    doc.email_id         = email_id
    doc.service          = ""
    doc.smtp_server      = data.get("smtp_server", "").strip()
    doc.smtp_port        = int(data.get("smtp_port") or 587)
    doc.use_tls          = 1 if data.get("use_tls") else 0
    doc.use_ssl          = 1 if data.get("use_ssl") else 0
    doc.login_id         = data.get("login_id") or email_id
    doc.enable_outgoing  = 1
    doc.default_outgoing = 1
    doc.enable_incoming  = 0
    doc.notify_if_unreachable = 0

    # Passwort nur setzen wenn übermittelt
    pw = data.get("password", "").strip()
    if pw:
        doc.password = pw

    doc.flags.ignore_permissions = True
    doc.flags.ignore_validate = True
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"name": doc.name, "ok": True}


@frappe.whitelist()
def test_email_senden(empfaenger):
    """Test-E-Mail senden um SMTP zu prüfen."""
    frappe.only_for(ADMIN_ROLLEN)
    empfaenger = empfaenger.strip()
    if not empfaenger:
        frappe.throw("Empfänger-E-Mail fehlt.")
    frappe.sendmail(
        recipients=[empfaenger],
        subject="Test-E-Mail von der Vereinsverwaltung",
        message="""<p>Diese Test-E-Mail bestätigt, dass der E-Mail-Versand korrekt konfiguriert ist.</p>
<p>Wenn du diese Nachricht erhältst, funktioniert der E-Mail-Versand.</p>""",
        delayed=False,
    )
    return {"ok": True}


# ─── Portal-Benutzer Verwaltung ───────────────────────────────────────────────

@frappe.whitelist()
def toggle_portal_benutzer(mitglied_name):
    """Portal-Benutzer aktivieren oder deaktivieren."""
    frappe.only_for(ADMIN_ROLLEN)
    mitglied = frappe.get_doc("Mitglied", mitglied_name)
    if not mitglied.portal_benutzer:
        frappe.throw("Diesem Mitglied ist kein Portal-Benutzer zugeordnet.")
    user = frappe.get_doc("User", mitglied.portal_benutzer)
    user.enabled = 0 if user.enabled else 1
    user.flags.ignore_permissions = True
    user.save(ignore_permissions=True)
    frappe.db.commit()
    return {"enabled": user.enabled}


@frappe.whitelist()
def reset_portal_passwort(mitglied_name):
    """Passwort-Reset-E-Mail für den Portal-Benutzer senden."""
    frappe.only_for(ADMIN_ROLLEN)
    mitglied = frappe.get_doc("Mitglied", mitglied_name)
    if not mitglied.portal_benutzer:
        frappe.throw("Diesem Mitglied ist kein Portal-Benutzer zugeordnet.")
    email = mitglied.portal_benutzer
    # Frappe built-in reset
    from frappe.utils.password import update_password
    from frappe.core.doctype.user.user import reset_password
    reset_password(email)
    return {"ok": True, "email": email}


@frappe.whitelist()
def set_portal_passwort(mitglied_name, neues_passwort):
    """Passwort für den Portal-Benutzer direkt setzen."""
    frappe.only_for(ADMIN_ROLLEN)
    if len(neues_passwort) < 6:
        frappe.throw("Das Passwort muss mindestens 6 Zeichen lang sein.")
    mitglied = frappe.get_doc("Mitglied", mitglied_name)
    if not mitglied.portal_benutzer:
        frappe.throw("Diesem Mitglied ist kein Portal-Benutzer zugeordnet.")
    from frappe.utils.password import update_password
    update_password(mitglied.portal_benutzer, neues_passwort)
    frappe.db.commit()
    return {"ok": True}


# ─── Rechnungen: Löschen ─────────────────────────────────────────────────────

@frappe.whitelist()
def delete_rechnung(parent, row_name):
    """Einzelne Beitragsrechnung (Child-Row) löschen."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    doc = frappe.get_doc("Mitglied", parent)
    doc.beitragsrechnungen = [r for r in doc.beitragsrechnungen if r.name != row_name]
    doc.flags.ignore_permissions = True
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return "OK"


# ─── SEPA Mandate ────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_sepa_mandate(status="", search=""):
    """Alle SEPA-Mandate auflisten."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    filters = {}
    if status:
        filters["status"] = status
    rows = frappe.get_all(
        "SEPA Mandat",
        filters=filters,
        fields=["name", "mandatsreferenz", "status", "mitglied",
                "kontoinhaber", "iban", "bic", "bank_name",
                "erteilungsdatum", "art", "letzter_einzug", "anzahl_einzuege",
                "widerrufen_am"],
        order_by="erteilungsdatum desc",
        limit_page_length=500,
    )
    # Mitgliedsnamen ergänzen + optional filtern
    result = []
    for r in rows:
        m = frappe.db.get_value("Mitglied", r.mitglied, ["vorname", "nachname", "mitgliedsnummer"], as_dict=True)
        r["mitglied_name"] = f"{m.vorname} {m.nachname}" if m else r.mitglied
        r["mitgliedsnummer"] = (m.mitgliedsnummer if m else None) or r.mitglied
        if search:
            s = search.lower()
            if s not in r["mitglied_name"].lower() and s not in (r.mandatsreferenz or "").lower():
                continue
        result.append(r)
    return result


@frappe.whitelist()
def create_sepa_mandat(mitglied, iban, bic, bank_name, kontoinhaber, erteilungsdatum, art="CORE (Basis)"):
    """Neues SEPA-Mandat anlegen."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    # Vorhandenes aktives Mandat prüfen
    existing = frappe.db.get_value("SEPA Mandat", {"mitglied": mitglied, "status": "Aktiv"}, "name")
    if existing:
        frappe.throw(f"Für dieses Mitglied existiert bereits ein aktives Mandat ({existing}).")
    # Mandatsreferenz generieren
    verein = frappe.db.get_value("Vereins Konfiguration", "Vereins Konfiguration",
                                  ["sepa_mandatsreferenz_prefix"], as_dict=True)
    prefix = (verein.sepa_mandatsreferenz_prefix or "MANDAT") if verein else "MANDAT"
    # Eindeutige Referenz: PREFIX-MITGLIED-DATUM
    ref = f"{prefix}-{mitglied}-{erteilungsdatum}".replace(" ", "")[:35]
    doc = frappe.get_doc({
        "doctype": "SEPA Mandat",
        "mandatsreferenz": ref,
        "status": "Aktiv",
        "mitglied": mitglied,
        "kontoinhaber": kontoinhaber,
        "iban": iban.replace(" ", "").upper(),
        "bic": bic.replace(" ", "").upper(),
        "bank_name": bank_name,
        "erteilungsdatum": erteilungsdatum,
        "art": art,
        "anzahl_einzuege": 0,
    })
    doc.flags.ignore_permissions = True
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    frappe.publish_realtime("sepa_mandat_update", {"action": "neu", "mandat": doc.name}, room="all")
    return {"name": doc.name, "mandatsreferenz": ref}


@frappe.whitelist()
def widerruf_sepa_mandat(mandat_name, grund=""):
    """SEPA-Mandat widerrufen."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    doc = frappe.get_doc("SEPA Mandat", mandat_name)
    doc.status = "Widerrufen"
    doc.widerrufen_am = frappe.utils.today()
    doc.widerrufsgrund = grund
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    frappe.publish_realtime("sepa_mandat_update", {"action": "widerruf", "mandat": mandat_name}, room="all")
    return "OK"


@frappe.whitelist()
def get_mitglieder_ohne_mandat():
    """Aktive Mitglieder mit IBAN aber ohne aktives SEPA-Mandat."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    alle = frappe.get_all(
        "Mitglied",
        filters={"status": "Aktiv"},
        fields=["name", "vorname", "nachname", "mitgliedsnummer", "iban", "bic", "bank_name"],
    )
    result = []
    for m in alle:
        if not m.iban:
            continue
        hat_mandat = frappe.db.exists("SEPA Mandat", {"mitglied": m.name, "status": "Aktiv"})
        if not hat_mandat:
            result.append({
                "name": m.name,
                "mitglied_name": f"{m.vorname} {m.nachname}",
                "mitgliedsnummer": m.mitgliedsnummer or m.name,
                "iban": m.iban,
                "bic": m.bic or "",
                "bank_name": m.bank_name or "",
            })
    return result


# ─── SEPA XML Generierung (pain.008.003.02) ──────────────────────────────────

@frappe.whitelist()
def generate_sepa_xml(einzugsdatum, jahr=""):
    """SEPA-Lastschrift XML (pain.008.003.02) für alle offenen SEPA-Rechnungen generieren."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    import xml.etree.ElementTree as ET
    from datetime import datetime

    verein = frappe.get_doc("Vereins Konfiguration", "Vereins Konfiguration")
    glaeubiger_id = verein.sepa_glaeubiger_id or ""
    if not glaeubiger_id:
        frappe.throw("Bitte zuerst die SEPA Gläubiger-ID in der Konfiguration hinterlegen.")
    if not verein.iban:
        frappe.throw("Bitte zuerst die Vereins-IBAN in der Konfiguration hinterlegen.")

    # Offene SEPA-Rechnungen laden
    filters = [
        ["Beitragsrechnung", "status", "=", "Offen"],
        ["Beitragsrechnung", "zahlungsart", "=", "SEPA Lastschrift"],
        ["Beitragsrechnung", "parenttype", "=", "Mitglied"],
    ]
    if jahr:
        filters.append(["Beitragsrechnung", "jahr", "=", int(jahr)])

    rechnungen = frappe.get_all(
        "Beitragsrechnung",
        filters=filters,
        fields=["name", "parent", "rechnungsnummer", "betrag", "jahr"],
    )
    if not rechnungen:
        frappe.throw("Keine offenen SEPA-Rechnungen gefunden.")

    # Mandate laden + Transaktionen aufbauen
    frst_txs = []  # Ersteinzug (noch nie eingezogen)
    rcur_txs = []  # Wiederholend

    for r in rechnungen:
        mandat = frappe.db.get_value(
            "SEPA Mandat", {"mitglied": r.parent, "status": "Aktiv"},
            ["name", "mandatsreferenz", "erteilungsdatum", "iban", "bic",
             "kontoinhaber", "anzahl_einzuege", "art"],
            as_dict=True,
        )
        if not mandat:
            continue  # Kein aktives Mandat → überspringen

        iban_clean = (mandat.iban or "").replace(" ", "").upper()
        bic_clean  = (mandat.bic or "NOTPROVIDED").replace(" ", "").upper()
        end_to_end = (r.rechnungsnummer or r.name)[:35]
        verwendung  = f"Mitgliedsbeitrag {r.jahr} {verein.vereinsname}"[:140]

        tx = {
            "end_to_end":    end_to_end,
            "betrag":        float(r.betrag or 0),
            "mandat_ref":    mandat.mandatsreferenz[:35],
            "mandat_datum":  str(mandat.erteilungsdatum),
            "debtor_name":   (mandat.kontoinhaber or r.parent)[:70],
            "debtor_iban":   iban_clean,
            "debtor_bic":    bic_clean,
            "verwendung":    verwendung,
            "mandat_name":   mandat.name,
            "rechnung_name": r.name,
            "rechnung_parent": r.parent,
            "lcl_instrm":    (mandat.art or "CORE (Basis)").split()[0],
        }
        if (mandat.anzahl_einzuege or 0) == 0:
            frst_txs.append(tx)
        else:
            rcur_txs.append(tx)

    if not frst_txs and not rcur_txs:
        frappe.throw("Keine Rechnungen mit aktivem SEPA-Mandat gefunden.")

    now_str = datetime.now().strftime("%Y%m%d%H%M%S")
    msg_id  = f"SEPA-{now_str}"
    total_count = len(frst_txs) + len(rcur_txs)
    total_sum   = sum(t["betrag"] for t in frst_txs + rcur_txs)

    NS = "urn:iso:std:iso:20022:tech:xsd:pain.008.003.02"
    ET.register_namespace("", NS)

    def sub(parent, tag, text=None):
        el = ET.SubElement(parent, f"{{{NS}}}{tag}")
        if text is not None:
            el.text = str(text)
        return el

    root = ET.Element(f"{{{NS}}}Document")
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    cdi = sub(root, "CstmrDrctDbtInitn")

    # GrpHdr
    grp = sub(cdi, "GrpHdr")
    sub(grp, "MsgId", msg_id)
    sub(grp, "CreDtTm", datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
    sub(grp, "NbOfTxs", total_count)
    sub(grp, "CtrlSum", f"{total_sum:.2f}")
    initg = sub(grp, "InitgPty")
    sub(initg, "Nm", verein.vereinsname[:70])

    def build_pmt_inf(txs, seq_type, pmt_id):
        if not txs:
            return
        pmt_sum = sum(t["betrag"] for t in txs)
        pmt = sub(cdi, "PmtInf")
        sub(pmt, "PmtInfId", pmt_id)
        sub(pmt, "PmtMtd", "DD")
        sub(pmt, "NbOfTxs", len(txs))
        sub(pmt, "CtrlSum", f"{pmt_sum:.2f}")
        tp = sub(pmt, "PmtTpInf")
        sub(sub(tp, "SvcLvl"), "Cd", "SEPA")
        sub(sub(tp, "LclInstrm"), "Cd", txs[0].get("lcl_instrm", "CORE"))
        sub(tp, "SeqTp", seq_type)
        sub(pmt, "ReqdColltnDt", einzugsdatum)
        sub(sub(pmt, "Cdtr"), "Nm", verein.vereinsname[:70])
        cdtr_acct = sub(pmt, "CdtrAcct")
        sub(sub(cdtr_acct, "Id"), "IBAN", verein.iban.replace(" ", "").upper())
        cdtr_agt = sub(pmt, "CdtrAgt")
        sub(sub(cdtr_agt, "FinInstnId"), "BIC",
            (verein.bic or "NOTPROVIDED").replace(" ", "").upper())
        sub(pmt, "ChrgBr", "SLEV")
        # Gläubiger-ID
        scheme = sub(sub(sub(sub(pmt, "CdtrSchmeId"), "Id"), "PrvtId"), "Othr")
        sub(scheme, "Id", glaeubiger_id)
        sub(sub(scheme, "SchmeNm"), "Prtry", "SEPA")

        for tx in txs:
            ddi = sub(pmt, "DrctDbtTxInf")
            sub(sub(ddi, "PmtId"), "EndToEndId", tx["end_to_end"])
            amt = sub(ddi, "InstdAmt", f"{tx['betrag']:.2f}")
            amt.set("Ccy", "EUR")
            mnd = sub(sub(ddi, "DrctDbtTx"), "MndtRltdInf")
            sub(mnd, "MndtId", tx["mandat_ref"])
            sub(mnd, "DtOfSgntr", tx["mandat_datum"])
            sub(mnd, "AmdmntInd", "false")
            # DbtrAgt
            agt = ET.SubElement(ddi, f"{{{NS}}}DbtrAgt")
            fi  = ET.SubElement(agt, f"{{{NS}}}FinInstnId")
            ET.SubElement(fi, f"{{{NS}}}BIC").text = tx["debtor_bic"]
            # Dbtr
            dbtr = ET.SubElement(ddi, f"{{{NS}}}Dbtr")
            ET.SubElement(dbtr, f"{{{NS}}}Nm").text = tx["debtor_name"]
            # DbtrAcct
            dacct = ET.SubElement(ddi, f"{{{NS}}}DbtrAcct")
            ET.SubElement(ET.SubElement(dacct, f"{{{NS}}}Id"), f"{{{NS}}}IBAN").text = tx["debtor_iban"]
            # RmtInf
            rmt = ET.SubElement(ddi, f"{{{NS}}}RmtInf")
            ET.SubElement(rmt, f"{{{NS}}}Ustrd").text = tx["verwendung"]

    build_pmt_inf(frst_txs, "FRST", f"PMT-FRST-{now_str}")
    build_pmt_inf(rcur_txs, "RCUR", f"PMT-RCUR-{now_str}")

    xml_bytes = ET.tostring(root, encoding="unicode", xml_declaration=False)
    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_bytes

    return {
        "xml": xml_str,
        "dateiname": f"SEPA-Lastschrift-{einzugsdatum}.xml",
        "anzahl": total_count,
        "summe": total_sum,
        "frst": len(frst_txs),
        "rcur": len(rcur_txs),
        "mandate_ids": [t["mandat_name"] for t in frst_txs + rcur_txs],
        "rechnungen": [{"name": t["rechnung_name"], "parent": t["rechnung_parent"]} for t in frst_txs + rcur_txs],
    }


@frappe.whitelist()
def get_sepa_vorschau(jahr=""):
    """Vorschau: wie viele SEPA-Rechnungen würden eingezogen werden."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    filters = [
        ["Beitragsrechnung", "status", "=", "Offen"],
        ["Beitragsrechnung", "zahlungsart", "=", "SEPA Lastschrift"],
        ["Beitragsrechnung", "parenttype", "=", "Mitglied"],
    ]
    if jahr:
        filters.append(["Beitragsrechnung", "jahr", "=", int(jahr)])
    rows = frappe.get_all(
        "Beitragsrechnung",
        filters=filters,
        fields=["name", "parent", "betrag", "jahr"],
    )
    anzahl = 0; summe = 0.0; frst = 0; rcur = 0
    for r in rows:
        mandat = frappe.db.get_value(
            "SEPA Mandat", {"mitglied": r.parent, "status": "Aktiv"},
            ["anzahl_einzuege"], as_dict=True,
        )
        if not mandat:
            continue
        anzahl += 1
        summe += float(r.betrag or 0)
        if (mandat.anzahl_einzuege or 0) == 0:
            frst += 1
        else:
            rcur += 1
    return {"anzahl": anzahl, "summe": summe, "frst": frst, "rcur": rcur}


@frappe.whitelist()
def get_mitglieder_liste_einfach():
    """Aktive Mitglieder als einfache Liste für Dropdowns."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    rows = frappe.get_all(
        "Mitglied",
        filters={"status": "Aktiv"},
        fields=["name", "vorname", "nachname", "mitgliedsnummer"],
        order_by="nachname asc",
    )
    return [{"value": r.name, "label": f"{r.nachname}, {r.vorname} (Nr. {r.mitgliedsnummer or r.name})"} for r in rows]


@frappe.whitelist()
def sepa_einzug_bestaetigen(mandat_ids, rechnung_infos):
    """Nach erfolgreichem Einzug: Mandate aktualisieren + Rechnungen als bezahlt markieren."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    import json
    if isinstance(mandat_ids, str):
        mandat_ids = json.loads(mandat_ids)
    if isinstance(rechnung_infos, str):
        rechnung_infos = json.loads(rechnung_infos)

    heute = frappe.utils.today()
    for mid in mandat_ids:
        doc = frappe.get_doc("SEPA Mandat", mid)
        doc.letzter_einzug = heute
        doc.anzahl_einzuege = (doc.anzahl_einzuege or 0) + 1
        doc.flags.ignore_permissions = True
        doc.save(ignore_permissions=True)

    for r in rechnung_infos:
        frappe.db.set_value("Beitragsrechnung", r["name"], {
            "status": "Bezahlt",
            "zahlungsdatum": heute,
        })

    frappe.db.commit()
    return {"ok": True, "aktualisiert": len(mandat_ids)}


# ─── Abstimmungen ─────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_abstimmungen_admin():
    """Alle Abstimmungen für Admin-Übersicht."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    import json
    rows = frappe.get_all(
        "Abstimmung",
        fields=["name", "titel", "beschreibung", "status", "datum_von", "datum_bis",
                "sparte", "nur_stimmberechtigt", "anonym", "fragen_json"],
        order_by="datum_von desc",
        limit_page_length=200,
    )
    for r in rows:
        r["teilnehmer"] = frappe.db.count("Abstimmungsstimme", {"abstimmung": r.name})
        r["fragen"] = json.loads(r.fragen_json or "[]")
        sparte_title = frappe.db.get_value("Sparte", r.sparte, "name_sparte") if r.sparte else None
        r["sparte_label"] = sparte_title or "Alle Mitglieder"
    return rows


@frappe.whitelist()
def save_abstimmung(data):
    """Abstimmung erstellen oder aktualisieren."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    import json
    if isinstance(data, str):
        data = json.loads(data)

    name = data.get("name")
    fragen = data.get("fragen", [])
    fragen_json = json.dumps(fragen, ensure_ascii=False)

    if name and frappe.db.exists("Abstimmung", name):
        doc = frappe.get_doc("Abstimmung", name)
        doc.titel = data.get("titel", doc.titel)
        doc.beschreibung = data.get("beschreibung", "")
        doc.datum_von = data.get("datum_von")
        doc.datum_bis = data.get("datum_bis")
        doc.sparte = data.get("sparte") or None
        doc.nur_stimmberechtigt = int(data.get("nur_stimmberechtigt", 1))
        doc.anonym = int(data.get("anonym", 1))
        doc.status = data.get("status", doc.status)
        doc.fragen_json = fragen_json
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.get_doc({
            "doctype": "Abstimmung",
            "titel": data.get("titel"),
            "beschreibung": data.get("beschreibung", ""),
            "datum_von": data.get("datum_von"),
            "datum_bis": data.get("datum_bis"),
            "sparte": data.get("sparte") or None,
            "nur_stimmberechtigt": int(data.get("nur_stimmberechtigt", 1)),
            "anonym": int(data.get("anonym", 1)),
            "status": data.get("status", "Entwurf"),
            "fragen_json": fragen_json,
        })
        doc.insert(ignore_permissions=True)

    frappe.db.commit()
    _notify("Abstimmung", "update", doc.name)
    return {"name": doc.name}


@frappe.whitelist()
def delete_abstimmung(name):
    """Abstimmung und alle Stimmen löschen."""
    frappe.only_for(ADMIN_ROLLEN)
    frappe.db.delete("Abstimmungsstimme", {"abstimmung": name})
    frappe.delete_doc("Abstimmung", name, ignore_permissions=True)
    frappe.db.commit()
    _notify("Abstimmung", "delete", name)
    return "OK"


@frappe.whitelist()
def get_abstimmung_ergebnis(name):
    """Ergebnis einer Abstimmung inkl. Charts-Daten."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    import json
    doc = frappe.get_doc("Abstimmung", name)
    fragen = json.loads(doc.fragen_json or "[]")
    stimmen_docs = frappe.get_all(
        "Abstimmungsstimme",
        filters={"abstimmung": name},
        fields=["mitglied", "stimmen_json", "abstimmungsdatum"],
    )
    total = len(stimmen_docs)

    ergebnis = []
    for fi, frage in enumerate(fragen):
        optionen = frage.get("optionen", [])
        zaehler = [0] * len(optionen)
        for sd in stimmen_docs:
            try:
                stimmen = json.loads(sd.stimmen_json or "{}")
                gewaehlt = stimmen.get(str(fi), [])
                if isinstance(gewaehlt, int):
                    gewaehlt = [gewaehlt]
                for oi in gewaehlt:
                    if 0 <= oi < len(zaehler):
                        zaehler[oi] += 1
            except Exception:
                pass
        ergebnis.append({
            "frage": frage.get("frage"),
            "typ": frage.get("typ"),
            "optionen": [
                {
                    "text": opt,
                    "count": zaehler[i],
                    "prozent": round(zaehler[i] / total * 100, 1) if total else 0,
                }
                for i, opt in enumerate(optionen)
            ],
        })

    teilnehmer_liste = []
    if not doc.anonym:
        for sd in stimmen_docs:
            m = frappe.db.get_value("Mitglied", sd.mitglied, ["vorname", "nachname"], as_dict=True)
            teilnehmer_liste.append({
                "mitglied": sd.mitglied,
                "name": f"{m.vorname} {m.nachname}" if m else sd.mitglied,
                "datum": sd.abstimmungsdatum,
            })

    # Wahlberechtigt
    wahlberechtigt = _get_wahlberechtigte(doc)
    return {
        "name": doc.name,
        "titel": doc.titel,
        "status": doc.status,
        "anonym": doc.anonym,
        "total": total,
        "wahlberechtigt": len(wahlberechtigt),
        "beteiligung": round(total / len(wahlberechtigt) * 100, 1) if wahlberechtigt else 0,
        "ergebnis": ergebnis,
        "teilnehmer": teilnehmer_liste,
    }


def _get_wahlberechtigte(doc):
    """Alle Mitglieder die an dieser Abstimmung teilnehmen dürfen."""
    filters = {"status": "Aktiv"}
    if doc.nur_stimmberechtigt:
        stimmber_typen = frappe.get_all(
            "Mitgliedstyp", filters={"stimmberechtigt": 1}, pluck="name"
        )
        if not stimmber_typen:
            return []
        filters["mitgliedstyp"] = ["in", stimmber_typen]
    alle = frappe.get_all("Mitglied", filters=filters, pluck="name")
    if doc.sparte:
        sparte_doc = frappe.get_doc("Sparte", doc.sparte)
        sparte_mitglieder = {m.mitglied for m in sparte_doc.mitglieder if m.aktiv}
        return [m for m in alle if m in sparte_mitglieder]
    return alle


@frappe.whitelist()
def get_meine_abstimmungen():
    """Aktive und kürzlich beendete Abstimmungen für das eingeloggte Mitglied."""
    _require_login()
    import json
    mitglied_name = frappe.db.get_value("Mitglied", {"portal_benutzer": frappe.session.user}, "name")
    if not mitglied_name:
        return []

    heute = frappe.utils.today()
    rows = frappe.get_all(
        "Abstimmung",
        filters={"status": ["in", ["Aktiv", "Beendet"]], "datum_von": ["<=", heute]},
        fields=["name", "titel", "beschreibung", "status", "datum_von", "datum_bis",
                "sparte", "nur_stimmberechtigt", "anonym", "fragen_json"],
        order_by="datum_bis desc",
        limit_page_length=50,
    )

    mitglied = frappe.get_doc("Mitglied", mitglied_name)
    mitgliedstyp = frappe.get_doc("Mitgliedstyp", mitglied.mitgliedstyp) if mitglied.mitgliedstyp else None
    stimmberechtigt = bool(mitgliedstyp and mitgliedstyp.stimmberechtigt)

    result = []
    for r in rows:
        # Sparten-Filter
        if r.sparte:
            sparte_doc = frappe.get_doc("Sparte", r.sparte)
            in_sparte = any(m.mitglied == mitglied_name and m.aktiv for m in sparte_doc.mitglieder)
            if not in_sparte:
                continue
        # Stimmberechtigungs-Filter
        if r.nur_stimmberechtigt and not stimmberechtigt:
            continue

        bereits_abgestimmt = frappe.db.exists(
            "Abstimmungsstimme", {"abstimmung": r.name, "mitglied": mitglied_name}
        )
        r["bereits_abgestimmt"] = bool(bereits_abgestimmt)
        r["fragen"] = json.loads(r.fragen_json or "[]")
        r["sparte_label"] = frappe.db.get_value("Sparte", r.sparte, "name_sparte") if r.sparte else "Alle Mitglieder"
        r["stimmberechtigt"] = stimmberechtigt

        # Ergebnis nur zeigen wenn beendet oder bereits abgestimmt
        if r.status == "Beendet" or r["bereits_abgestimmt"]:
            r["ergebnis"] = _berechne_ergebnis(r.name, r["fragen"])
        else:
            r["ergebnis"] = None

        result.append(r)
    return result


def _berechne_ergebnis(abstimmung_name, fragen):
    import json
    stimmen_docs = frappe.get_all(
        "Abstimmungsstimme",
        filters={"abstimmung": abstimmung_name},
        fields=["stimmen_json"],
    )
    total = len(stimmen_docs)
    ergebnis = []
    for fi, frage in enumerate(fragen):
        optionen = frage.get("optionen", [])
        zaehler = [0] * len(optionen)
        for sd in stimmen_docs:
            try:
                stimmen = json.loads(sd.stimmen_json or "{}")
                gewaehlt = stimmen.get(str(fi), [])
                if isinstance(gewaehlt, int):
                    gewaehlt = [gewaehlt]
                for oi in gewaehlt:
                    if 0 <= oi < len(zaehler):
                        zaehler[oi] += 1
            except Exception:
                pass
        ergebnis.append({
            "frage": frage.get("frage"),
            "typ": frage.get("typ"),
            "total": total,
            "optionen": [
                {"text": opt, "count": zaehler[i], "prozent": round(zaehler[i] / total * 100, 1) if total else 0}
                for i, opt in enumerate(optionen)
            ],
        })
    return ergebnis


@frappe.whitelist()
def abstimmen(abstimmung_name, stimmen_json):
    """Stimme abgeben."""
    _require_login()
    import json
    mitglied_name = frappe.db.get_value("Mitglied", {"portal_benutzer": frappe.session.user}, "name")
    if not mitglied_name:
        frappe.throw("Kein verknüpftes Mitglied gefunden.")

    doc = frappe.get_doc("Abstimmung", abstimmung_name)
    heute = frappe.utils.getdate()
    if doc.status != "Aktiv" or not (frappe.utils.getdate(doc.datum_von) <= heute <= frappe.utils.getdate(doc.datum_bis)):
        frappe.throw("Diese Abstimmung ist nicht aktiv.")
    if frappe.db.exists("Abstimmungsstimme", {"abstimmung": abstimmung_name, "mitglied": mitglied_name}):
        frappe.throw("Du hast bereits abgestimmt.")

    # Berechtigung prüfen
    wahlberechtigt = _get_wahlberechtigte(doc)
    if mitglied_name not in wahlberechtigt:
        frappe.throw("Du bist für diese Abstimmung nicht stimmberechtigt.")

    stimmen = stimmen_json if isinstance(stimmen_json, str) else json.dumps(stimmen_json)
    stimme = frappe.get_doc({
        "doctype": "Abstimmungsstimme",
        "abstimmung": abstimmung_name,
        "mitglied": mitglied_name,
        "abstimmungsdatum": frappe.utils.now(),
        "stimmen_json": stimmen,
    })
    stimme.flags.ignore_permissions = True
    stimme.insert(ignore_permissions=True)
    frappe.db.commit()
    _notify("Abstimmung", "update", abstimmung_name)

    fragen = json.loads(doc.fragen_json or "[]")
    return {"ok": True, "ergebnis": _berechne_ergebnis(abstimmung_name, fragen)}


@frappe.whitelist()
def get_vorstand_liste():
    """Alle Vorstandsmitglieder mit aufgelöstem Mitgliedsnamen."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    rows = frappe.get_all(
        "Vorstandsmitglied",
        fields=["name", "mitglied", "position", "amtsperiode_von", "amtsperiode_bis",
                "aktiv", "email_dienstlich", "telefon_dienstlich"],
        order_by="aktiv desc, amtsperiode_von asc",
        limit_page_length=100,
    )
    mitglied_namen = {}
    ids = list({r.mitglied for r in rows if r.mitglied})
    if ids:
        for m in frappe.get_all("Mitglied", filters=[["name", "in", ids]],
                                fields=["name", "vorname", "nachname"]):
            mitglied_namen[m.name] = f"{m.nachname}, {m.vorname}"
    for r in rows:
        r["mitglied_name"] = mitglied_namen.get(r.mitglied, r.mitglied)
    return rows


# ─── Sparten Terminkalender ──────────────────────────────────────────────────

def _expand_termine(rows, bis=None):
    """Expandiert Wiederholungsregeln zu konkreten Termindaten (max. 1 Jahr voraus)."""
    import datetime
    today = datetime.date.today()
    max_bis = today + datetime.timedelta(days=365)
    if bis:
        try:
            max_bis = min(max_bis, datetime.date.fromisoformat(str(bis)))
        except Exception:
            pass

    WOCHENTAGE = {"Montag": 0, "Dienstag": 1, "Mittwoch": 2, "Donnerstag": 3,
                  "Freitag": 4, "Samstag": 5, "Sonntag": 6}

    result = []
    for r in rows:
        if not r.get("aktiv"):
            continue
        try:
            start = datetime.date.fromisoformat(str(r["datum"]))
        except Exception:
            continue

        regel = r.get("wiederholung") or "Keine"
        wdh_bis_raw = r.get("wiederholung_bis")
        wdh_bis = max_bis
        if wdh_bis_raw:
            try:
                wdh_bis = min(wdh_bis, datetime.date.fromisoformat(str(wdh_bis_raw)))
            except Exception:
                pass

        def _termin(d):
            return {**r, "datum": d.isoformat(), "ist_wiederholung": d != start}

        if regel == "Keine":
            if start >= today:
                result.append(_termin(start))
            continue

        if regel == "Wöchentlich":
            # Wenn ein Wochentag angegeben ist, nimm diesen; sonst Wochentag des Startdatums
            wt_name = r.get("wiederholung_wochentag") or ""
            ziel_wt = WOCHENTAGE.get(wt_name, start.weekday())
            # Nächstes Vorkommen ab heute
            d = today + datetime.timedelta(days=(ziel_wt - today.weekday()) % 7)
            if d < start:
                d += datetime.timedelta(weeks=1)
            while d <= wdh_bis:
                result.append(_termin(d))
                d += datetime.timedelta(weeks=1)
            continue

        if regel == "Zweiwöchentlich":
            wt_name = r.get("wiederholung_wochentag") or ""
            ziel_wt = WOCHENTAGE.get(wt_name, start.weekday())
            d = today + datetime.timedelta(days=(ziel_wt - today.weekday()) % 7)
            if d < start:
                d += datetime.timedelta(weeks=2)
            # Phase angleichen an Startdatum
            diff_weeks = (d - start).days // 7
            if diff_weeks % 2 != 0:
                d += datetime.timedelta(weeks=1)
            while d <= wdh_bis:
                result.append(_termin(d))
                d += datetime.timedelta(weeks=2)
            continue

        if regel == "Monatlich (selber Tag)":
            d = start
            while d <= wdh_bis:
                if d >= today:
                    result.append(_termin(d))
                # Nächsten Monat
                m = d.month + 1
                y = d.year + (1 if m > 12 else 0)
                m = m if m <= 12 else 1
                import calendar
                last_day = calendar.monthrange(y, m)[1]
                d = d.replace(year=y, month=m, day=min(d.day, last_day))
            continue

        # Monatlich (N. Wochentag) — z.B. "Monatlich (2. Wochentag)" → 2. Donnerstag
        import re
        m_nth = re.match(r"Monatlich \((\d)\. Wochentag\)", regel)
        if m_nth:
            n = int(m_nth.group(1))
            wt_name = r.get("wiederholung_wochentag") or ""
            ziel_wt = WOCHENTAGE.get(wt_name, start.weekday())
            check_date = today.replace(day=1)
            while check_date <= wdh_bis:
                # Finde n-ten Wochentag im Monat
                first_wd = check_date.weekday()
                delta = (ziel_wt - first_wd) % 7
                d = check_date + datetime.timedelta(days=delta + 7 * (n - 1))
                if d.month == check_date.month and d >= today and d <= wdh_bis:
                    result.append(_termin(d))
                # Nächster Monat
                m2 = check_date.month + 1
                y2 = check_date.year + (1 if m2 > 12 else 0)
                m2 = m2 if m2 <= 12 else 1
                check_date = check_date.replace(year=y2, month=m2, day=1)
            continue

    result.sort(key=lambda x: x["datum"])
    return result


@frappe.whitelist()
def get_sparten_termine(sparte_name, limit=60):
    """Kommende Termine einer Sparte (expandiert mit Wiederholungen) — für Mitglieder."""
    _require_login()
    rows = frappe.get_all(
        "Sparten Termin",
        filters={"sparte": sparte_name, "aktiv": 1},
        fields=["name", "titel", "datum", "uhrzeit_von", "uhrzeit_bis",
                "treffpunkt", "beschreibung", "wiederholung",
                "wiederholung_wochentag", "wiederholung_bis", "aktiv"],
        order_by="datum asc",
        limit_page_length=200,
    )
    expanded = _expand_termine([dict(r) for r in rows])
    return expanded[:int(limit)]


@frappe.whitelist()
def get_sparten_termine_admin(sparte_name):
    """Alle Terminvorlagen einer Sparte für den Admin (nicht expandiert)."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    rows = frappe.get_all(
        "Sparten Termin",
        filters={"sparte": sparte_name},
        fields=["name", "titel", "datum", "uhrzeit_von", "uhrzeit_bis",
                "treffpunkt", "beschreibung", "wiederholung",
                "wiederholung_wochentag", "wiederholung_bis", "aktiv"],
        order_by="datum asc",
        limit_page_length=200,
    )
    return [dict(r) for r in rows]


@frappe.whitelist()
def create_sparten_termin(sparte_name, titel, datum, uhrzeit_von="", uhrzeit_bis="",
                          treffpunkt="", beschreibung="", wiederholung="Keine",
                          wiederholung_wochentag="", wiederholung_bis=""):
    """Termin für eine Sparte anlegen — Spartenleiter oder Admin."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    # Spartenleiter darf nur für seine eigene Sparte anlegen
    user_roles = set(frappe.get_roles(frappe.session.user))
    if not (user_roles & {"System Manager", "Vereins Admin", "Kassenwart", "Vorstand"}):
        # Prüfen ob User Spartenleiter dieser Sparte ist
        mitglied_name = frappe.db.get_value("Mitglied", {"portal_benutzer": frappe.session.user}, "name")
        if mitglied_name:
            ist_leiter = frappe.db.exists("Spartenmitglied", {
                "parent": sparte_name,
                "mitglied": mitglied_name,
                "funktion": ["in", ["Spartenleiter", "Stv. Spartenleiter"]],
                "aktiv": 1,
            })
            if not ist_leiter:
                frappe.throw("Sie sind kein Spartenleiter dieser Sparte.", frappe.PermissionError)

    doc = frappe.get_doc({
        "doctype": "Sparten Termin",
        "sparte": sparte_name,
        "titel": titel,
        "datum": datum,
        "uhrzeit_von": uhrzeit_von or None,
        "uhrzeit_bis": uhrzeit_bis or None,
        "treffpunkt": treffpunkt or "",
        "beschreibung": beschreibung or "",
        "wiederholung": wiederholung or "Keine",
        "wiederholung_wochentag": wiederholung_wochentag or "",
        "wiederholung_bis": wiederholung_bis or None,
        "aktiv": 1,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.as_dict()


@frappe.whitelist()
def update_sparten_termin(name, titel, datum, uhrzeit_von="", uhrzeit_bis="",
                          treffpunkt="", beschreibung="", wiederholung="Keine",
                          wiederholung_wochentag="", wiederholung_bis="", aktiv=1):
    """Termin aktualisieren — Spartenleiter oder Admin."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    doc = frappe.get_doc("Sparten Termin", name)
    doc.titel = titel
    doc.datum = datum
    doc.uhrzeit_von = uhrzeit_von or None
    doc.uhrzeit_bis = uhrzeit_bis or None
    doc.treffpunkt = treffpunkt or ""
    doc.beschreibung = beschreibung or ""
    doc.wiederholung = wiederholung or "Keine"
    doc.wiederholung_wochentag = wiederholung_wochentag or ""
    doc.wiederholung_bis = wiederholung_bis or None
    doc.aktiv = int(aktiv)
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return doc.as_dict()


@frappe.whitelist()
def delete_sparten_termin(name):
    """Termin löschen — Spartenleiter oder Admin."""
    frappe.only_for(ERWEITERTER_ZUGANG)
    frappe.delete_doc("Sparten Termin", name, ignore_permissions=True, force=True)
    frappe.db.commit()
    return "OK"


@frappe.whitelist(allow_guest=False)
def get_site_name():
    """Return Frappe site name for socket.io namespace resolution."""
    return {'sitename': frappe.local.site}


@frappe.whitelist(allow_guest=True)
def produkt_kontakt(vorname='', nachname='', verein='', email='', telefon='', mitglieder='', nachricht=''):
    """Kontaktanfrage von der Produktseite — sendet E-Mail an kontakt@industrie-4-0.org."""
    if not vorname or not nachname or not email:
        frappe.throw('Bitte Vorname, Nachname und E-Mail angeben.')

    body = f"""
<p>Neue Demo-Anfrage über die DMS-Verein Produktseite:</p>
<table style="border-collapse:collapse;width:100%;max-width:500px">
  <tr><td style="padding:6px 12px;color:#64748b;font-size:13px;width:140px">Name</td>
      <td style="padding:6px 12px;font-weight:600">{frappe.utils.escape_html(vorname)} {frappe.utils.escape_html(nachname)}</td></tr>
  <tr style="background:#f8fafc"><td style="padding:6px 12px;color:#64748b;font-size:13px">E-Mail</td>
      <td style="padding:6px 12px"><a href="mailto:{frappe.utils.escape_html(email)}">{frappe.utils.escape_html(email)}</a></td></tr>
  <tr><td style="padding:6px 12px;color:#64748b;font-size:13px">Verein</td>
      <td style="padding:6px 12px">{frappe.utils.escape_html(verein) or '—'}</td></tr>
  <tr style="background:#f8fafc"><td style="padding:6px 12px;color:#64748b;font-size:13px">Telefon</td>
      <td style="padding:6px 12px">{frappe.utils.escape_html(telefon) or '—'}</td></tr>
  <tr><td style="padding:6px 12px;color:#64748b;font-size:13px">Mitglieder</td>
      <td style="padding:6px 12px">{frappe.utils.escape_html(mitglieder) or '—'}</td></tr>
  <tr style="background:#f8fafc"><td style="padding:6px 12px;color:#64748b;font-size:13px;vertical-align:top">Nachricht</td>
      <td style="padding:6px 12px;white-space:pre-wrap">{frappe.utils.escape_html(nachricht) or '—'}</td></tr>
</table>
"""
    frappe.sendmail(
        recipients=['kontakt@industrie-4-0.org'],
        subject=f'Demo-Anfrage DMS Verein – {vorname} {nachname}',
        message=body,
        now=True,
    )
    return {'success': True}
