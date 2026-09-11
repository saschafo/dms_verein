<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <div>
        <h2>Mitglieder</h2>
        <p class="text-slate-500 mt-1">{{ total }} Mitglieder insgesamt</p>
      </div>
      <button @click="showForm = true" class="btn btn-primary">
        <Plus :size="16" /> Neues Mitglied
      </button>
    </div>

    <!-- Filter -->
    <div class="card card-body mb-4 flex flex-col sm:flex-row flex-wrap gap-3">
      <div class="flex-1 min-w-0">
        <div class="relative">
          <Search :size="16" class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input v-model="search" @input="debouncedSearch" class="input pl-9 w-full" placeholder="Name, E-Mail, Mitgliedsnr..." />
        </div>
      </div>
      <div class="flex gap-2">
        <select v-model="filterStatus" @change="loadMitglieder" class="input flex-1 sm:w-36">
          <option value="">Alle Status</option>
          <option>Aktiv</option><option>Passiv</option><option>Gesperrt</option><option>Ausgetreten</option><option>Verstorben</option>
        </select>
        <select v-model="filterTyp" @change="loadMitglieder" class="input flex-1 sm:w-44">
          <option value="">Alle Typen</option>
          <option v-for="t in typen" :key="t.name" :value="t.name">{{ t.bezeichnung }}</option>
        </select>
      </div>
    </div>

    <!-- Mobile/Tablet: Cards (< lg) -->
    <div class="lg:hidden space-y-2">
      <div v-if="loading" class="card card-body text-center py-8"><AppSpinner /></div>
      <div v-else-if="!mitglieder.length" class="card card-body text-center py-8 text-slate-400">Keine Mitglieder gefunden</div>
      <div v-for="m in mitglieder" :key="m.name"
        class="card p-4 flex items-center gap-3 cursor-pointer active:bg-slate-50"
        @click="openDetail(m.name)">
        <div v-if="m.foto" class="w-10 h-10 rounded-full overflow-hidden shrink-0">
          <img :src="m.foto" class="w-full h-full object-cover" />
        </div>
        <div v-else class="w-10 h-10 rounded-full bg-slate-200 flex items-center justify-center text-sm font-bold text-slate-500 shrink-0">
          {{ initials(m) }}
        </div>
        <div class="flex-1 min-w-0">
          <p class="font-medium text-slate-900 truncate">{{ m.vorname }} {{ m.nachname }}</p>
          <p class="text-xs text-slate-500 truncate">{{ m.mitgliedsnummer }} · {{ m.ort }}</p>
        </div>
        <div class="flex flex-col items-end gap-1 shrink-0">
          <StatusBadge :status="m.status" />
          <span class="badge badge-blue text-xs">{{ m.mitgliedstyp }}</span>
        </div>
      </div>
    </div>

    <!-- Desktop: Tabelle (≥ lg) -->
    <div class="hidden lg:block table-wrapper">
      <table class="table">
        <thead>
          <tr><th>Nr.</th><th>Name</th><th>Mitgliedstyp</th><th>Status</th><th>Eintritt</th><th>E-Mail</th><th>Ort</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-if="loading"><td colspan="8" class="text-center py-8"><AppSpinner /></td></tr>
          <tr v-else-if="!mitglieder.length"><td colspan="8" class="text-center py-8 text-slate-400">Keine Mitglieder gefunden</td></tr>
          <tr v-for="m in mitglieder" :key="m.name" class="cursor-pointer" @click="openDetail(m.name)">
            <td class="font-mono text-slate-500 text-xs">{{ m.mitgliedsnummer || m.name }}</td>
            <td>
              <div class="flex items-center gap-3">
                <div v-if="m.foto" class="w-8 h-8 rounded-full overflow-hidden shrink-0">
                  <img :src="m.foto" class="w-full h-full object-cover" />
                </div>
                <div v-else class="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-xs font-bold text-slate-500 shrink-0">
                  {{ initials(m) }}
                </div>
                <span class="font-medium">{{ m.vorname }} {{ m.nachname }}</span>
              </div>
            </td>
            <td><span class="badge badge-blue">{{ m.mitgliedstyp }}</span></td>
            <td><StatusBadge :status="m.status" /></td>
            <td class="text-slate-500 text-sm">{{ formatDate(m.eintrittsdatum) }}</td>
            <td class="text-slate-500 text-sm truncate max-w-32">{{ m.email }}</td>
            <td class="text-slate-500 text-sm">{{ m.ort }}</td>
            <td @click.stop>
              <RouterLink :to="`/admin/mitglieder/${m.name}`" class="btn btn-secondary btn-sm"><Eye :size="14" /></RouterLink>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="total > perPage" class="mt-4 flex items-center justify-between text-sm text-slate-500">
      <span>{{ offset + 1 }}–{{ Math.min(offset + perPage, total) }} von {{ total }}</span>
      <div class="flex gap-2">
        <button :disabled="offset === 0" @click="prev" class="btn btn-secondary btn-sm">
          <ChevronLeft :size="14" />
        </button>
        <button :disabled="offset + perPage >= total" @click="next" class="btn btn-secondary btn-sm">
          <ChevronRight :size="14" />
        </button>
      </div>
    </div>

    <!-- Neues Mitglied Modal -->
    <AppModal :show="showForm" title="Neues Mitglied anlegen" size="lg" @close="showForm = false">
      <MitgliedForm :typen="typen" @saved="onSaved" @cancel="showForm = false" />
    </AppModal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/utils/api'
import AppSpinner from '@/components/ui/AppSpinner.vue'
import AppModal from '@/components/ui/AppModal.vue'
import MitgliedForm from '@/components/MitgliedForm.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { Plus, Search, Eye, ChevronLeft, ChevronRight } from 'lucide-vue-next'
import { useRealtimeRefresh } from '@/composables/useRealtimeRefresh'

const router = useRouter()
const mitglieder = ref([])
const typen = ref([])
const total = ref(0)
const loading = ref(true)
const search = ref('')
const filterStatus = ref('')
const filterTyp = ref('')
const offset = ref(0)
const perPage = 25
const showForm = ref(false)

let searchTimer = null

onMounted(async () => {
  const [, t] = await Promise.all([loadMitglieder(), api.getMitgliedstypenAdmin()])
  typen.value = t || []
})
useRealtimeRefresh(['Mitglied'], () => loadMitglieder())

async function loadMitglieder() {
  loading.value = true
  try {
    const res = await api.getMitgliederListe({
      search: search.value,
      status: filterStatus.value,
      mitgliedstyp: filterTyp.value,
      limit: perPage,
      offset: offset.value,
    })
    mitglieder.value = res.items || []
    total.value = res.total || 0
  } finally {
    loading.value = false
  }
}

function debouncedSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { offset.value = 0; loadMitglieder() }, 350)
}

function prev() { offset.value = Math.max(0, offset.value - perPage); loadMitglieder() }
function next() { offset.value += perPage; loadMitglieder() }
function openDetail(name) { router.push(`/admin/mitglieder/${name}`) }
function initials(m) { return `${m.vorname?.[0] || ''}${m.nachname?.[0] || ''}`.toUpperCase() }
function formatDate(d) { return d ? new Date(d).toLocaleDateString('de-DE') : '—' }
async function onSaved() { showForm.value = false; offset.value = 0; await loadMitglieder() }
</script>
