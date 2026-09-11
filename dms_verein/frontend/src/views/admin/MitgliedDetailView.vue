<template>
  <div v-if="loading"><AppSpinner full-page /></div>

  <div v-else-if="mitglied" class="pb-8">
    <!-- Header -->
    <div class="flex items-start gap-4 mb-6">
      <button @click="router.back()" class="btn btn-secondary btn-sm mt-1"><ArrowLeft :size="14" /></button>
      <div class="flex items-center gap-4 flex-1 flex-wrap">
        <div class="w-16 h-16 rounded-xl bg-primary-100 flex items-center justify-center text-2xl font-bold text-primary-600 shrink-0">
          {{ initials }}
        </div>
        <div>
          <h2>{{ mitglied.vorname }} {{ mitglied.nachname }}</h2>
          <p class="text-slate-500 mt-0.5">{{ mitglied.name }} · {{ mitglied.mitgliedstyp }}</p>
        </div>
        <div class="ml-auto flex flex-wrap gap-2 items-center">
          <StatusBadge :status="mitglied.status" />

          <!-- Portal-Zugang Status im Header -->
          <template v-if="!loadingPortal">
            <button v-if="!portalUser?.email && mitglied.email" @click="quickCreatePortal"
              :disabled="creatingUser"
              class="btn btn-secondary border-dashed border-amber-400 text-amber-700 hover:bg-amber-50 flex items-center gap-1.5 text-sm">
              <UserPlus :size="15" />
              {{ creatingUser ? 'Erstelle...' : 'Portal-Zugang anlegen' }}
            </button>
            <span v-else-if="!portalUser && !mitglied.email"
              class="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded-lg px-2 py-1">
              Keine E-Mail → kein Portal-Zugang
            </span>
            <span v-else-if="portalUser?.email && portalUser.enabled"
              class="flex items-center gap-1 text-xs text-green-700 bg-green-50 border border-green-200 rounded-lg px-2 py-1">
              <CircleCheck :size="13" /> Portal-Zugang aktiv
            </span>
            <span v-else-if="portalUser?.email && !portalUser.enabled"
              class="flex items-center gap-1 text-xs text-slate-600 bg-slate-100 border border-slate-200 rounded-lg px-2 py-1">
              Portal-Zugang deaktiviert
            </span>
          </template>

          <template v-if="!editMode">
            <button @click="startEdit" class="btn btn-secondary"><Pencil :size="16" /> Bearbeiten</button>
            <button @click="confirmDelete" class="btn btn-danger"><Trash2 :size="16" /></button>
          </template>
          <template v-else>
            <button @click="cancelEdit" class="btn btn-secondary">Abbrechen</button>
            <button @click="saveEdit" :disabled="saving" class="btn btn-primary"><Save :size="16" /> {{ saving ? 'Speichert...' : 'Speichern' }}</button>
          </template>
        </div>
      </div>
    </div>

    <AppAlert v-if="saveError" type="error" :message="saveError" class="mb-4" />
    <AppAlert v-if="saveSuccess" type="success" message="Änderungen gespeichert." class="mb-4" />

    <!-- Tabs -->
    <div class="flex gap-1 border-b border-slate-200 mb-6 overflow-x-auto">
      <button v-for="tab in tabs" :key="tab.id" @click="activeTab = tab.id"
        :class="['px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap',
                 activeTab === tab.id ? 'border-primary-600 text-primary-700' : 'border-transparent text-slate-500 hover:text-slate-800']">
        {{ tab.label }}
      </button>
    </div>

    <!-- Tab: Stammdaten -->
    <div v-show="activeTab === 'stamm'">
      <!-- VIEW MODE -->
      <div v-if="!editMode" class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div class="card">
          <div class="card-header"><h3 class="text-base font-semibold">Persönliche Daten</h3></div>
          <div class="card-body space-y-3">
            <InfoRow label="Anrede" :value="mitglied.anrede" />
            <InfoRow label="Vorname" :value="mitglied.vorname" />
            <InfoRow label="Nachname" :value="mitglied.nachname" />
            <InfoRow label="Geburtsdatum" :value="formatDate(mitglied.geburtsdatum)" />
            <InfoRow label="Geschlecht" :value="mitglied.geschlecht" />
          </div>
        </div>
        <div class="card">
          <div class="card-header"><h3 class="text-base font-semibold">Adresse & Kontakt</h3></div>
          <div class="card-body space-y-3">
            <InfoRow label="Straße" :value="mitglied.strasse" />
            <InfoRow label="PLZ / Ort" :value="`${mitglied.plz || ''} ${mitglied.ort || ''}`" />
            <InfoRow label="Land" :value="mitglied.land" />
            <InfoRow label="E-Mail" :value="mitglied.email" />
            <InfoRow label="Telefon" :value="mitglied.telefon" />
            <InfoRow label="Mobil" :value="mitglied.mobil" />
          </div>
        </div>
        <div class="card">
          <div class="card-header"><h3 class="text-base font-semibold">Mitgliedschaft</h3></div>
          <div class="card-body space-y-3">
            <InfoRow label="Mitgliedstyp" :value="mitglied.mitgliedstyp" />
            <InfoRow label="Status" :value="mitglied.status" />
            <InfoRow label="Eintrittsdatum" :value="formatDate(mitglied.eintrittsdatum)" />
            <InfoRow label="Austrittsdatum" :value="formatDate(mitglied.austrittsdatum)" />
          </div>
        </div>
        <div v-if="mitglied.notizen" class="card">
          <div class="card-header"><h3 class="text-base font-semibold">Notizen</h3></div>
          <div class="card-body text-sm text-slate-600 whitespace-pre-wrap">{{ mitglied.notizen }}</div>
        </div>
      </div>

      <!-- EDIT MODE -->
      <div v-else class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div class="card">
          <div class="card-header"><h3 class="text-base font-semibold">Persönliche Daten</h3></div>
          <div class="card-body space-y-3">
            <div class="form-group">
              <label class="label">Anrede</label>
              <select v-model="editData.anrede" class="input">
                <option value="">—</option><option>Herr</option><option>Frau</option><option>Divers</option>
              </select>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div class="form-group"><label class="label">Vorname *</label><input v-model="editData.vorname" class="input" required /></div>
              <div class="form-group"><label class="label">Nachname *</label><input v-model="editData.nachname" class="input" required /></div>
            </div>
            <div class="form-group"><label class="label">Geburtsdatum</label><input v-model="editData.geburtsdatum" type="date" class="input" /></div>
            <div class="form-group">
              <label class="label">Geschlecht</label>
              <select v-model="editData.geschlecht" class="input">
                <option value="">—</option><option>Männlich</option><option>Weiblich</option><option>Divers</option>
              </select>
            </div>
          </div>
        </div>
        <div class="card">
          <div class="card-header"><h3 class="text-base font-semibold">Adresse & Kontakt</h3></div>
          <div class="card-body space-y-3">
            <div class="form-group"><label class="label">Straße</label><input v-model="editData.strasse" class="input" /></div>
            <div class="grid grid-cols-3 gap-3">
              <div class="form-group"><label class="label">PLZ</label><input v-model="editData.plz" class="input" /></div>
              <div class="form-group col-span-2"><label class="label">Ort</label><input v-model="editData.ort" class="input" /></div>
            </div>
            <div class="form-group"><label class="label">Land</label><input v-model="editData.land" class="input" /></div>
            <div class="form-group"><label class="label">E-Mail</label><input v-model="editData.email" type="email" class="input" /></div>
            <div class="grid grid-cols-2 gap-3">
              <div class="form-group"><label class="label">Telefon</label><input v-model="editData.telefon" class="input" /></div>
              <div class="form-group"><label class="label">Mobil</label><input v-model="editData.mobil" class="input" /></div>
            </div>
          </div>
        </div>
        <div class="card">
          <div class="card-header"><h3 class="text-base font-semibold">Mitgliedschaft</h3></div>
          <div class="card-body space-y-3">
            <div class="form-group">
              <label class="label">Mitgliedstyp</label>
              <select v-model="editData.mitgliedstyp" class="input">
                <option value="">– Kein Typ –</option>
                <option v-for="t in mitgliedstypen" :key="t.name" :value="t.name">
                  {{ t.bezeichnung || t.name }}{{ t.aktiv ? '' : ' (inaktiv)' }}
                </option>
              </select>
            </div>
            <div class="form-group">
              <label class="label">Status</label>
              <select v-model="editData.status" class="input">
                <option>Aktiv</option><option>Passiv</option><option>Gesperrt</option><option>Ausgetreten</option><option>Verstorben</option>
              </select>
            </div>
            <div class="form-group"><label class="label">Eintrittsdatum</label><input v-model="editData.eintrittsdatum" type="date" class="input" /></div>
            <div class="form-group"><label class="label">Austrittsdatum</label><input v-model="editData.austrittsdatum" type="date" class="input" /></div>
          </div>
        </div>
        <div class="card">
          <div class="card-header"><h3 class="text-base font-semibold">Notizen</h3></div>
          <div class="card-body">
            <textarea v-model="editData.notizen" class="input h-32 resize-none" placeholder="Interne Notizen..."></textarea>
          </div>
        </div>
      </div>
    </div>

    <!-- Tab: Mitgliedschaft -->
    <div v-show="activeTab === 'mitgliedschaft'">
      <div class="card">
        <div class="card-header"><h3 class="text-base font-semibold">Mitgliedschaftshistorie</h3></div>
        <div class="table-wrapper">
          <table class="table">
            <thead><tr><th>Typ</th><th>Von</th><th>Bis</th><th>Status</th></tr></thead>
            <tbody>
              <tr v-if="!mitglied.mitgliedschaften?.length"><td colspan="4" class="text-center py-6 text-slate-400">Keine Einträge</td></tr>
              <tr v-for="m in mitglied.mitgliedschaften" :key="m.name">
                <td>{{ m.mitgliedstyp }}</td>
                <td>{{ formatDate(m.von) }}</td>
                <td>{{ m.bis ? formatDate(m.bis) : 'aktuell' }}</td>
                <td><StatusBadge :status="m.status" /></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Tab: Finanzen -->
    <div v-show="activeTab === 'finanzen'">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <!-- VIEW MODE -->
        <template v-if="!editMode">
          <div class="card card-body">
            <h3 class="text-base font-semibold mb-3">Bankverbindung</h3>
            <div class="space-y-3">
              <InfoRow label="Kreditinstitut" :value="mitglied.bank_name" />
              <InfoRow label="IBAN" :value="mitglied.iban ? mitglied.iban.replace(/(.{4})/g, '$1 ').trim() : '—'" mono />
              <InfoRow label="BIC" :value="mitglied.bic" />
            </div>
          </div>
          <div class="card card-body">
            <h3 class="text-base font-semibold mb-3">SEPA Lastschrift</h3>
            <InfoRow label="Mandat" :value="mitglied.sepa_mandat" />
          </div>
        </template>
        <!-- EDIT MODE -->
        <template v-else>
          <div class="card">
            <div class="card-header"><h3 class="text-base font-semibold">Bankverbindung bearbeiten</h3></div>
            <div class="card-body space-y-3">
              <div class="form-group"><label class="label">Bank / Kreditinstitut</label><input v-model="editData.bank_name" class="input" /></div>
              <div class="form-group"><label class="label">IBAN</label><input v-model="editData.iban" class="input font-mono" placeholder="DE..." /></div>
              <div class="form-group"><label class="label">BIC</label><input v-model="editData.bic" class="input font-mono" /></div>
            </div>
          </div>
        </template>
      </div>
      <div class="card">
        <div class="card-header"><h3 class="text-base font-semibold">Beitragsrechnungen</h3></div>
        <div class="table-wrapper">
          <table class="table">
            <thead><tr><th>Jahr</th><th>Typ</th><th>Betrag</th><th>Fälligkeit</th><th>Status</th><th></th></tr></thead>
            <tbody>
              <tr v-if="!mitglied.beitragsrechnungen?.length"><td colspan="6" class="text-center text-slate-400 py-6">Keine Rechnungen</td></tr>
              <tr v-for="r in mitglied.beitragsrechnungen" :key="r.name">
                <td>{{ r.jahr }}</td>
                <td>{{ r.mitgliedstyp }}</td>
                <td class="font-medium">{{ formatCurrency(r.betrag) }}</td>
                <td>{{ formatDate(r.faelligkeit) }}</td>
                <td><StatusBadge :status="r.status" /></td>
                <td class="text-right">
                  <button @click="confirmDeleteRechnung(r)"
                    class="text-slate-300 hover:text-red-500 transition-colors p-1 rounded"
                    title="Rechnung löschen">
                    <Trash2 :size="14" />
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Tab: Rollen & Zugang -->
    <div v-show="activeTab === 'zugang'">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div class="card">
          <div class="card-header flex items-center justify-between">
            <h3 class="text-base font-semibold">Portal-Zugang</h3>
            <span v-if="portalUser?.email" :class="['badge', portalUser.enabled ? 'badge-green' : 'badge-red']">
              {{ portalUser.enabled ? 'Aktiv' : 'Deaktiviert' }}
            </span>
          </div>
          <div class="card-body space-y-4">

            <!-- Kein Zugang vorhanden -->
            <template v-if="!portalUser?.email">
              <div class="flex items-start gap-3 p-3 bg-amber-50 border border-amber-200 rounded-xl text-sm text-amber-800">
                <UserX :size="16" class="shrink-0 mt-0.5 text-amber-500" />
                <div>Kein Portal-Zugang vorhanden. Erstelle einen Zugang damit sich das Mitglied im Portal anmelden kann.</div>
              </div>
              <div v-if="!mitglied.email" class="text-sm text-red-600 bg-red-50 rounded-lg p-3">
                Keine E-Mail-Adresse hinterlegt — bitte zuerst unter Stammdaten eintragen.
              </div>
              <template v-else>
                <div class="text-sm text-slate-600">E-Mail: <strong>{{ mitglied.email }}</strong></div>
                <label class="flex items-center gap-2 text-sm cursor-pointer">
                  <input v-model="sendWelcomeEmail" type="checkbox" class="w-4 h-4" />
                  Willkommens-E-Mail mit Login-Link senden
                </label>
                <button @click="createPortalAccount" :disabled="creatingUser" class="btn btn-primary">
                  <UserPlus :size="15" /> {{ creatingUser ? 'Erstelle...' : 'Portal-Zugang anlegen' }}
                </button>
              </template>
            </template>

            <!-- Zugang vorhanden -->
            <template v-else>
              <!-- Benutzerinfo -->
              <div class="flex items-center gap-3 p-3 bg-slate-50 rounded-xl border border-slate-200">
                <div class="w-10 h-10 rounded-full flex items-center justify-center font-bold text-white text-sm shrink-0"
                     :style="{ backgroundColor: verein.info?.primaerfarbe || '#2563eb' }">
                  {{ (portalUser.full_name || portalUser.email)?.[0]?.toUpperCase() }}
                </div>
                <div class="flex-1 min-w-0">
                  <p class="font-medium text-sm truncate">{{ portalUser.full_name || portalUser.email }}</p>
                  <p class="text-xs text-slate-500 truncate">{{ portalUser.email }}</p>
                  <p class="text-xs text-slate-400 mt-0.5">
                    Letzter Login: {{ portalUser.last_login ? new Date(portalUser.last_login).toLocaleString('de-DE') : 'Noch nie' }}
                  </p>
                </div>
              </div>

              <!-- Aktionen -->
              <div class="grid grid-cols-1 gap-2">
                <!-- Aktivieren / Deaktivieren -->
                <button @click="toggleUser" :disabled="userActionRunning"
                  :class="['btn w-full justify-start gap-2', portalUser.enabled ? 'btn-secondary text-red-600 hover:bg-red-50 hover:border-red-200' : 'btn-secondary text-green-600 hover:bg-green-50 hover:border-green-200']">
                  <component :is="portalUser.enabled ? UserX : CircleCheck" :size="15" />
                  {{ portalUser.enabled ? 'Zugang deaktivieren' : 'Zugang aktivieren' }}
                </button>

                <!-- Passwort-Reset per E-Mail -->
                <button @click="sendPasswordReset" :disabled="userActionRunning"
                  class="btn btn-secondary w-full justify-start gap-2">
                  <Mail :size="15" /> Passwort-Reset-E-Mail senden
                </button>

                <!-- Passwort direkt setzen -->
                <div class="border border-slate-200 rounded-xl p-3 space-y-2">
                  <p class="text-xs font-medium text-slate-600">Neues Passwort direkt setzen:</p>
                  <div class="flex gap-2">
                    <div class="relative flex-1">
                      <input v-model="neuesPasswort" :type="showNewPw ? 'text' : 'password'"
                        class="input pr-8 text-sm" placeholder="Mind. 6 Zeichen" />
                      <button type="button" @click="showNewPw = !showNewPw"
                        class="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                        <Eye v-if="!showNewPw" :size="13" />
                        <EyeOff v-else :size="13" />
                      </button>
                    </div>
                    <button @click="setPassword" :disabled="!neuesPasswort || userActionRunning"
                      class="btn btn-secondary shrink-0 text-sm">
                      Setzen
                    </button>
                  </div>
                </div>

                <!-- Willkommens-Mail erneut senden -->
                <button @click="resendWelcome" :disabled="userActionRunning"
                  class="btn btn-secondary w-full justify-start gap-2 text-sm">
                  <Send :size="14" /> Willkommens-E-Mail erneut senden
                </button>
              </div>
            </template>

            <AppAlert v-if="portalMsg" :type="portalMsg.type" :message="portalMsg.text" class="mt-2" />
          </div>
        </div>

        <div class="card card-body" v-if="portalUser?.email">
          <h3 class="text-base font-semibold mb-4">Rollen & Berechtigungen</h3>
          <p class="text-sm text-slate-500 mb-4">Legt fest, welche Bereiche dieser Benutzer im System sehen und verwalten darf.</p>
          <div class="space-y-2 mb-4">
            <label v-for="rolle in availableRollen" :key="rolle" class="flex items-start gap-3 p-2.5 rounded-lg hover:bg-slate-50 cursor-pointer">
              <input type="checkbox" :value="rolle" v-model="selectedRollen" class="w-4 h-4 mt-0.5 shrink-0" />
              <div>
                <p class="text-sm font-medium">{{ rolle }}</p>
                <p class="text-xs text-slate-400">{{ rollenBeschreibung[rolle] || '' }}</p>
              </div>
            </label>
          </div>
          <button @click="saveRollen" :disabled="savingRollen" class="btn btn-primary btn-sm">
            {{ savingRollen ? 'Speichert...' : 'Rollen speichern' }}
          </button>
          <AppAlert v-if="rollenMsg" :type="rollenMsg.type" :message="rollenMsg.text" class="mt-3" />
        </div>
      </div>
    </div>
  </div>

  <!-- Rechnung löschen Modal -->
  <AppModal :show="showDeleteRechnung" title="Rechnung löschen?" size="sm" @close="showDeleteRechnung = false">
    <p class="text-sm text-slate-600">
      Beitragsrechnung <strong>{{ deleteRechnungTarget?.jahr }}</strong>
      ({{ formatCurrency(deleteRechnungTarget?.betrag) }}) wirklich löschen?
    </p>
    <template #footer>
      <button @click="showDeleteRechnung = false" class="btn btn-secondary">Abbrechen</button>
      <button @click="doDeleteRechnung" :disabled="deletingRechnung" class="btn btn-danger">
        {{ deletingRechnung ? 'Löscht…' : 'Löschen' }}
      </button>
    </template>
  </AppModal>

  <!-- Delete Confirm Modal -->
  <AppModal :show="showDeleteConfirm" title="Mitglied löschen?" @close="showDeleteConfirm = false">
    <p class="text-sm text-slate-600">Soll das Mitglied <strong>{{ mitglied?.vorname }} {{ mitglied?.nachname }}</strong> ({{ mitglied?.name }}) wirklich gelöscht werden? Diese Aktion kann nicht rückgängig gemacht werden.</p>
    <template #footer>
      <button @click="showDeleteConfirm = false" class="btn btn-secondary">Abbrechen</button>
      <button @click="deleteMitglied" :disabled="deleting" class="btn btn-danger">{{ deleting ? 'Löscht...' : 'Endgültig löschen' }}</button>
    </template>
  </AppModal>
</template>

<script setup>
import { ref, computed, onMounted, watch, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/utils/api'
import { useVereinStore } from '@/stores/verein'
import { useAuthStore } from '@/stores/auth'
import AppSpinner from '@/components/ui/AppSpinner.vue'
import AppModal from '@/components/ui/AppModal.vue'
import AppAlert from '@/components/ui/AppAlert.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { ArrowLeft, Pencil, Save, Trash2, UserPlus, CircleCheck, UserX, Mail, Send, Eye, EyeOff } from 'lucide-vue-next'

const auth = useAuthStore()
const isAdmin = computed(() => auth.isAdmin)

// Render-Funktion statt String-Template (Template-Compiler nicht im Vite-Build)
const InfoRow = {
  props: ['label', 'value', 'mono'],
  setup(props) {
    return () => h('div', { class: 'flex justify-between gap-4 text-sm py-0.5' }, [
      h('span', { class: 'text-slate-500 shrink-0' }, props.label),
      h('span', { class: 'font-medium text-right break-all' + (props.mono ? ' font-mono' : '') },
        props.value || '—'),
    ])
  },
}

const route = useRoute()
const router = useRouter()
const verein = useVereinStore()
const mitglied = ref(null)
const loading = ref(true)
const editMode = ref(false)
const editData = ref({})
const saving = ref(false)
const saveError = ref('')
const saveSuccess = ref(false)
const activeTab = ref('stamm')
const mitgliedstypen = ref([])

// Delete
const showDeleteConfirm = ref(false)
const deleting = ref(false)
const showDeleteRechnung = ref(false)
const deleteRechnungTarget = ref(null)
const deletingRechnung = ref(false)

// Portal user
const portalUser = ref(null)
const loadingPortal = ref(false)
const creatingUser = ref(false)
const sendWelcomeEmail = ref(true)
const portalMsg = ref(null)
const userActionRunning = ref(false)
const neuesPasswort = ref('')
const showNewPw = ref(false)

// Roles
const availableRollen = ref([])
const selectedRollen = ref([])
const savingRollen = ref(false)
const rollenMsg = ref(null)

const rollenBeschreibung = {
  'Vereins Admin': 'Voller Zugriff auf alle Verwaltungsfunktionen',
  'Kassenwart': 'Zugriff auf Finanzen, Beiträge und SEPA-Export',
  'Spartenleiter': 'Verwaltung der eigenen Sparte und deren Mitglieder',
  'Vorstand': 'Lesezugriff auf alle Vereinsdaten',
  'Mitglied': 'Zugriff auf das Mitglieder-Portal (Self-Service)',
}

const tabs = computed(() => [
  { id: 'stamm', label: 'Stammdaten' },
  { id: 'mitgliedschaft', label: 'Mitgliedschaft' },
  { id: 'finanzen', label: 'Finanzen' },
  ...(auth.isAdmin ? [{ id: 'zugang', label: 'Rollen & Zugang' }] : []),
])

const initials = computed(() => {
  if (!mitglied.value) return ''
  return `${mitglied.value.vorname?.[0] || ''}${mitglied.value.nachname?.[0] || ''}`.toUpperCase()
})

onMounted(async () => {
  try {
    [mitglied.value, mitgliedstypen.value, availableRollen.value] = await Promise.all([
      api.getMitgliedDetail(route.params.id),
      api.getMitgliedstypenAdmin().catch(() => []),
      api.getAvailableRollen().catch(() => []),
    ])
    // Portal-Status nur für Admins laden
    if (auth.isAdmin) {
      loadingPortal.value = true
      portalUser.value = await api.getPortalBenutzerInfo(mitglied.value.name).catch(() => null)
      if (portalUser.value?.email) selectedRollen.value = [...(portalUser.value.roles || [])]
    }
  } finally {
    loading.value = false
    loadingPortal.value = false
  }
})

watch(activeTab, async (tab) => {
  if (tab === 'zugang' && mitglied.value && !loadingPortal.value) {
    loadingPortal.value = true
    try {
      portalUser.value = await api.getPortalBenutzerInfo(mitglied.value.name)
      if (portalUser.value?.email) selectedRollen.value = [...(portalUser.value.roles || [])]
    } finally { loadingPortal.value = false }
  }
})

function startEdit() {
  const m = mitglied.value
  editData.value = {
    anrede: m.anrede || '', vorname: m.vorname || '', nachname: m.nachname || '',
    geburtsdatum: m.geburtsdatum || '', geschlecht: m.geschlecht || '',
    strasse: m.strasse || '', plz: m.plz || '', ort: m.ort || '', land: m.land || '',
    email: m.email || '', telefon: m.telefon || '', mobil: m.mobil || '',
    mitgliedstyp: m.mitgliedstyp || '', status: m.status || 'Aktiv',
    eintrittsdatum: m.eintrittsdatum || '', austrittsdatum: m.austrittsdatum || '',
    iban: m.iban || '', bic: m.bic || '', bank_name: m.bank_name || '',
    notizen: m.notizen || '',
  }
  editMode.value = true
  saveError.value = ''
  saveSuccess.value = false
}

function cancelEdit() { editMode.value = false }

async function saveEdit() {
  saving.value = true; saveError.value = ''; saveSuccess.value = false
  try {
    const updated = await api.updateMitglied(mitglied.value.name, editData.value)
    mitglied.value = { ...mitglied.value, ...updated }
    editMode.value = false
    saveSuccess.value = true
    setTimeout(() => saveSuccess.value = false, 3000)
  } catch (e) { saveError.value = e.message }
  finally { saving.value = false }
}

function confirmDelete() { showDeleteConfirm.value = true }

function confirmDeleteRechnung(r) {
  deleteRechnungTarget.value = r
  showDeleteRechnung.value = true
}

async function doDeleteRechnung() {
  deletingRechnung.value = true
  try {
    await api.call('dms_verein.api.verein.delete_rechnung', {
      parent: mitglied.value.name,
      row_name: deleteRechnungTarget.value.name,
    })
    mitglied.value.beitragsrechnungen = mitglied.value.beitragsrechnungen.filter(
      r => r.name !== deleteRechnungTarget.value.name
    )
    showDeleteRechnung.value = false
  } catch (e) { saveError.value = e.message }
  finally { deletingRechnung.value = false }
}

async function deleteMitglied() {
  deleting.value = true
  try {
    await api.deleteRecord('Mitglied', mitglied.value.name)
    router.push('/admin/mitglieder')
  } catch (e) { alert('Fehler beim Löschen: ' + e.message) }
  finally { deleting.value = false }
}

async function quickCreatePortal() {
  creatingUser.value = true
  try {
    await api.createPortalBenutzer(mitglied.value.name, 1)
    portalUser.value = await api.getPortalBenutzerInfo(mitglied.value.name)
    if (portalUser.value?.email) selectedRollen.value = [...(portalUser.value.roles || [])]
    portalMsg.value = { type: 'success', text: 'Portal-Zugang erstellt. Willkommens-E-Mail wurde gesendet.' }
    activeTab.value = 'zugang'
  } catch (e) { portalMsg.value = { type: 'error', text: e.message } }
  finally { creatingUser.value = false }
}

async function createPortalAccount() {
  creatingUser.value = true; portalMsg.value = null
  try {
    const res = await api.createPortalBenutzer(mitglied.value.name, sendWelcomeEmail.value ? 1 : 0)
    portalUser.value = await api.getPortalBenutzerInfo(mitglied.value.name)
    if (portalUser.value?.email) selectedRollen.value = [...(portalUser.value.roles || [])]
    const msgs = { created: 'Portal-Konto erstellt. Willkommens-E-Mail wurde gesendet.', linked: 'Vorhandenes Konto verknüpft.', exists: 'Konto war bereits verknüpft.' }
    portalMsg.value = { type: 'success', text: msgs[res?.status] || 'Konto eingerichtet.' }
  } catch (e) { portalMsg.value = { type: 'error', text: e.message } }
  finally { creatingUser.value = false }
}

async function toggleUser() {
  userActionRunning.value = true; portalMsg.value = null
  try {
    const r = await api.call('dms_verein.api.verein.toggle_portal_benutzer', { mitglied_name: mitglied.value.name })
    portalUser.value = { ...portalUser.value, enabled: r.enabled }
    portalMsg.value = { type: 'success', text: r.enabled ? 'Zugang aktiviert.' : 'Zugang deaktiviert.' }
  } catch (e) { portalMsg.value = { type: 'error', text: e.message } }
  finally { userActionRunning.value = false }
}

async function sendPasswordReset() {
  userActionRunning.value = true; portalMsg.value = null
  try {
    const r = await api.call('dms_verein.api.verein.reset_portal_passwort', { mitglied_name: mitglied.value.name })
    portalMsg.value = { type: 'success', text: `Passwort-Reset-E-Mail an ${r.email} gesendet.` }
  } catch (e) { portalMsg.value = { type: 'error', text: e.message } }
  finally { userActionRunning.value = false }
}

async function setPassword() {
  if (!neuesPasswort.value) return
  userActionRunning.value = true; portalMsg.value = null
  try {
    await api.call('dms_verein.api.verein.set_portal_passwort', { mitglied_name: mitglied.value.name, neues_passwort: neuesPasswort.value })
    portalMsg.value = { type: 'success', text: 'Passwort erfolgreich gesetzt.' }
    neuesPasswort.value = ''
    showNewPw.value = false
  } catch (e) { portalMsg.value = { type: 'error', text: e.message } }
  finally { userActionRunning.value = false }
}

async function resendWelcome() {
  userActionRunning.value = true; portalMsg.value = null
  try {
    await api.call('dms_verein.api.verein.reset_portal_passwort', { mitglied_name: mitglied.value.name })
    portalMsg.value = { type: 'success', text: 'Willkommens-E-Mail gesendet.' }
  } catch (e) { portalMsg.value = { type: 'error', text: e.message } }
  finally { userActionRunning.value = false }
}

async function saveRollen() {
  savingRollen.value = true; rollenMsg.value = null
  try {
    await api.setMitgliedRollen(mitglied.value.name, selectedRollen.value)
    rollenMsg.value = { type: 'success', text: 'Rollen gespeichert.' }
    setTimeout(() => rollenMsg.value = null, 3000)
  } catch (e) { rollenMsg.value = { type: 'error', text: e.message } }
  finally { savingRollen.value = false }
}

const formatDate = (d) => d ? new Date(d).toLocaleDateString('de-DE') : '—'
const formatCurrency = (v) => v ? `${Number(v).toFixed(2)} €` : '0,00 €'
</script>
