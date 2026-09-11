import axios from 'axios'

const csrf = () => window.csrf_token || (document.cookie.match(/csrf_token=([^;]+)/) || [])[1] || ''

const client = axios.create({ baseURL: '/api/method/' })

client.interceptors.request.use(cfg => {
  cfg.headers['X-Frappe-CSRF-Token'] = csrf()
  return cfg
})

client.interceptors.response.use(
  r => r.data?.message !== undefined ? r.data.message : r.data,
  err => {
    const data = err.response?.data
    // Frappe _server_messages (JSON-enkodierte Liste)
    if (data?._server_messages) {
      try {
        const msgs = JSON.parse(data._server_messages)
        const first = JSON.parse(msgs[0])
        return Promise.reject(new Error(first.message || first))
      } catch {}
    }
    // Frappe exception (exc)
    if (data?.exc) {
      try {
        const lines = JSON.parse(data.exc)
        const last = Array.isArray(lines) ? lines[lines.length - 1] : lines
        return Promise.reject(new Error(last.split(':').pop().trim() || 'Fehler'))
      } catch {}
    }
    // Direkte message
    if (data?.message) return Promise.reject(new Error(data.message))
    // Fallback
    return Promise.reject(new Error(err.response?.data?.exc_type || err.message || 'Serverfehler'))
  }
)

export const api = {
  call: (method, params = {}) => client.post(method, params),

  // Öffentlich
  getVereinInfo: () => client.post('dms_verein.api.verein.get_verein_info'),
  getMitgliedstypen: () => client.post('dms_verein.api.verein.get_mitgliedstypen'),
  getMitgliedstypenAdmin: () => client.post('dms_verein.api.verein.get_mitgliedstypen_admin'),
  getSparten: () => client.post('dms_verein.api.verein.get_sparten'),
  getVeranstaltungen: (params) => client.post('dms_verein.api.verein.get_veranstaltungen', params),
  submitAntrag: (data) => client.post('dms_verein.api.verein.submit_mitgliedsantrag', { data: JSON.stringify(data) }),

  // Admin
  getDashboardStats: () => client.post('dms_verein.api.verein.get_dashboard_stats'),
  getMitgliederListe: (p) => client.post('dms_verein.api.verein.get_mitglieder_liste', p),
  getMitgliedDetail: (name) => client.post('dms_verein.api.verein.get_mitglied_detail', { name }),
  annehmenAntrag: (name) => client.post('dms_verein.api.verein.annehmen_antrag', { name }),
  ablehnenAntrag: (name, grund) => client.post('dms_verein.api.verein.ablehnen_antrag', { name, grund }),

  // Portal
  getMeinProfil: () => client.post('dms_verein.api.verein.get_mein_profil'),
  updateMeinProfil: (data) => client.post('dms_verein.api.verein.update_mein_profil', { data: JSON.stringify(data) }),

  // Frappe standard
  login: (usr, pwd) => client.post('login', { usr, pwd }),
  logout: () => client.post('logout'),
  getSession: () => client.post('frappe.auth.get_logged_user'),

  // Datei-Upload (Frappe upload_file Endpoint) — gibt direkt die URL zurück
  uploadFile: async (file, doctype = '', docname = '') => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('is_private', '0')
    if (doctype) formData.append('doctype', doctype)
    if (docname) formData.append('docname', docname)
    const result = await client.post('upload_file', formData)
    return result?.file_url || result?.message?.file_url || ''
  },

  // Fotoalbum
  getAlbenListe: () => client.post('dms_verein.api.verein.get_alben_liste'),
  getAlbumDetail: (name) => client.post('dms_verein.api.verein.get_album_detail', { name }),
  addFotoToAlbum: (album_name, datei, titel, datum, aufgenommen_von) => client.post('dms_verein.api.verein.add_foto_to_album', { album_name, datei, titel: titel || '', datum: datum || '', aufgenommen_von: aufgenommen_von || '' }),
  deleteFotoFromAlbum: (album_name, foto_name) => client.post('dms_verein.api.verein.delete_foto_from_album', { album_name, foto_name }),
  setAlbumTitelbild: (album_name, datei) => client.post('dms_verein.api.verein.set_album_titelbild', { album_name, datei }),

  // Mitglied admin
  updateMitglied: (name, data) => client.post('dms_verein.api.verein.update_mitglied', { name, data: JSON.stringify(data) }),

  // Generische Admin-Operationen (mit Berechtigungsprüfung)
  updateRecord: (doctype, name, data) => client.post('dms_verein.api.verein.update_record', { doctype, name, data: JSON.stringify(data) }),
  deleteRecord: (doctype, name) => client.post('dms_verein.api.verein.delete_record', { doctype, name }),

  // Portal-Benutzer & Rollen
  getPortalBenutzerInfo: (mitglied_name) => client.post('dms_verein.api.verein.get_portal_benutzer_info', { mitglied_name }),
  createPortalBenutzer: (mitglied_name, send_welcome = 1) => client.post('dms_verein.api.verein.create_portal_benutzer', { mitglied_name, send_welcome }),
  setMitgliedRollen: (mitglied_name, rollen) => client.post('dms_verein.api.verein.set_mitglied_rollen', { mitglied_name, rollen: JSON.stringify(rollen) }),
  getAvailableRollen: () => client.post('dms_verein.api.verein.get_available_rollen'),

  // Generische Frappe-Operationen
  getDoc: (doctype, name) => client.post('frappe.client.get', { doctype, name }),
  getList: (doctype, opts) => client.post('frappe.client.get_list', { doctype, ...opts }),
  saveDoc: (doc) => client.post('frappe.client.save', { doc }),
  insertDoc: (doc) => client.post('frappe.client.insert', { doc }),
  deleteDoc: (doctype, name) => client.post('frappe.client.delete', { doctype, name }),
}

// Composable-Wrapper für Verwendung in neuen Komponenten (useApi())
export function useApi() { return api }
