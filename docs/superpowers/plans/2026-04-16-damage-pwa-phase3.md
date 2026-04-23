# Damage PWA Phase 3: Transfer Detail + Item Inspection + Photos + History

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fully implement the core inspection flow — users can open a transfer, inspect items one-by-one with photos + supplier code + damage category, and approve/reject the transfer. Also implement History and Slip Detail views.

**Architecture:** New views `TransferDetailView`, `InspectionView`, `SlipDetailView`, `HistoryView` replace Phase 2 stubs. New components `ItemRow`, `ChipSelect`, `PhotoSlot`. New store `inspection.js` manages the current inspection form state. Photos are captured via `<input type="file" capture="environment">`, compressed via Canvas to ≤1MB, uploaded immediately (online only — offline handling deferred to Phase 4).

**Tech Stack:** Vue 3.4, Vue Router 4, Pinia 2 (existing). No new npm deps. Uses Canvas API for photo compression, `uploadFile()` from `utils/frappe.js`.

**Spec:** `docs/superpowers/specs/2026-04-16-damage-pwa-design.md` (sections 2.3, 2.4, 2.5, 2.6, 6.4, 8)

**Depends on:** Phase 1 backend APIs, Phase 2 SPA shell (both deployed).

**Scope boundary:** Online-only. Auto-save-to-IndexedDB + offline queue is Phase 4. This phase uses direct API calls and expects network connectivity.

**Server:** Commands run via HTTP API to `207.180.209.80:3847`, bench user `v15`, site `rmax_dev2`.

```
curl -s -X POST \
  -H "Authorization: Bearer 9c9d7e54d54c30e9f264f202376c04ed4dd4bab9c57eb2b3" \
  -H "Content-Type: application/json" \
  -d '{"command": "..."}' \
  http://207.180.209.80:3847/api/servers/41ef79dc-a2fd-418a-bd88-b5f5173aeaf7/command
```

**After every frontend change:**
```
cd /home/v15/frappe-bench/apps/damage_pwa/frontend && sudo -u v15 yarn build
# Ensure symlink (only needed first time, idempotent):
sudo -u v15 ln -sfn /home/v15/frappe-bench/apps/damage_pwa/damage_pwa/public /home/v15/frappe-bench/sites/assets/damage_pwa
cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 clear-cache && sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web
```

---

## File Map

```
frappe-bench/apps/damage_pwa/frontend/src/
├── store/
│   └── inspection.js                 # NEW — current item form state
├── utils/
│   └── photo.js                      # NEW — compress + upload helper
├── components/
│   ├── ItemRow.vue                   # NEW — transfer detail item row with status
│   ├── ChipSelect.vue                # NEW — damage category chip picker
│   └── PhotoSlot.vue                 # NEW — camera/gallery + preview + delete
└── views/
    ├── TransferDetailView.vue        # REWRITE — items + approve/reject
    ├── InspectionView.vue            # REWRITE — per-item form
    ├── SlipDetailView.vue            # REWRITE — read-only slip
    └── HistoryView.vue               # REWRITE — history list with filter tabs
```

---

### Task 1: Inspection Store + Photo Helper

**Files:**
- Create: `frontend/src/store/inspection.js`
- Create: `frontend/src/utils/photo.js`

- [ ] **Step 1: Create photo.js compression + upload helper**

Create `apps/damage_pwa/frontend/src/utils/photo.js`:

```javascript
import { uploadFile } from "@/utils/frappe.js";

const MAX_DIMENSION = 1280;
const JPEG_QUALITY = 0.7;

/**
 * Compress an image File to JPEG ≤1MB, max 1280px longest side.
 * Returns a Blob.
 */
export async function compressImage(file) {
  const dataUrl = await fileToDataUrl(file);
  const img = await loadImage(dataUrl);

  let { width, height } = img;
  if (width > MAX_DIMENSION || height > MAX_DIMENSION) {
    if (width >= height) {
      height = Math.round((height * MAX_DIMENSION) / width);
      width = MAX_DIMENSION;
    } else {
      width = Math.round((width * MAX_DIMENSION) / height);
      height = MAX_DIMENSION;
    }
  }

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(img, 0, 0, width, height);

  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (!blob) reject(new Error("Compression failed"));
        else resolve(blob);
      },
      "image/jpeg",
      JPEG_QUALITY
    );
  });
}

/**
 * Compress + upload a File to Frappe, return the public file URL.
 */
export async function compressAndUpload(file) {
  const blob = await compressImage(file);
  const compressedFile = new File(
    [blob],
    file.name.replace(/\.[^.]+$/, "") + ".jpg",
    { type: "image/jpeg" }
  );
  return uploadFile(compressedFile);
}

/**
 * Generate a small data URL thumbnail for preview (200px longest side).
 */
export async function makeThumbnail(file) {
  const dataUrl = await fileToDataUrl(file);
  const img = await loadImage(dataUrl);
  let { width, height } = img;
  const target = 200;
  if (width >= height) {
    height = Math.round((height * target) / width);
    width = target;
  } else {
    width = Math.round((width * target) / height);
    height = target;
  }
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  canvas.getContext("2d").drawImage(img, 0, 0, width, height);
  return canvas.toDataURL("image/jpeg", 0.6);
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}
```

- [ ] **Step 2: Create inspection store**

Create `apps/damage_pwa/frontend/src/store/inspection.js`:

```javascript
import { defineStore } from "pinia";
import { call } from "@/utils/frappe.js";

export const useInspectionStore = defineStore("inspection", {
  state: () => ({
    transfer: null,           // Full transfer object
    loading: false,
    saving: false,
    error: null,
    locked: false,
    lockExpiresAt: null,
  }),

  getters: {
    items: (state) => state.transfer?.items || [],
    itemCount: (state) => state.transfer?.items?.length || 0,
    inspectedCount: (state) =>
      (state.transfer?.items || []).filter(
        (i) => i._inspection_status !== "incomplete"
      ).length,
    allInspected(state) {
      return this.itemCount > 0 && this.inspectedCount === this.itemCount;
    },
    progressText(state) {
      return `${this.inspectedCount}/${this.itemCount}`;
    },
  },

  actions: {
    async loadTransfer(name) {
      this.loading = true;
      this.error = null;
      try {
        this.transfer = await call("damage_pwa.api.inspect.get_transfer_detail", { name });
      } catch (e) {
        this.error = e.message;
        throw e;
      } finally {
        this.loading = false;
      }
    },

    async claim(name) {
      try {
        const result = await call("damage_pwa.api.inspect.claim_transfer", { name });
        this.locked = true;
        this.lockExpiresAt = result.expires_at;
        if (this.transfer) {
          this.transfer.modified = result.modified;
        }
        return result;
      } catch (e) {
        this.locked = false;
        throw e;
      }
    },

    findItem(rowName) {
      return this.items.find((i) => i.row_name === rowName);
    },

    async saveItem({ rowName, supplier_code, damage_category, images, image_2, image_3, remarks, status = "complete" }) {
      if (!this.transfer) throw new Error("No transfer loaded");
      this.saving = true;
      try {
        const result = await call("damage_pwa.api.inspect.save_item_inspection", {
          transfer_name: this.transfer.name,
          row_name: rowName,
          supplier_code,
          damage_category,
          images,
          image_2,
          image_3,
          remarks,
          status,
          client_modified: this.transfer.modified,
        });
        // Update local row
        const row = this.findItem(rowName);
        if (row) {
          Object.assign(row, {
            supplier_code,
            damage_category,
            images,
            image_2,
            image_3,
            remarks,
            _inspection_status: result._inspection_status,
          });
        }
        this.transfer.modified = result.modified;
        return result;
      } finally {
        this.saving = false;
      }
    },

    async approve() {
      if (!this.transfer) throw new Error("No transfer loaded");
      return call("damage_pwa.api.inspect.approve_transfer", {
        name: this.transfer.name,
        client_modified: this.transfer.modified,
      });
    },

    async reject(reason) {
      if (!this.transfer) throw new Error("No transfer loaded");
      return call("damage_pwa.api.inspect.reject_transfer", {
        name: this.transfer.name,
        reason,
        client_modified: this.transfer.modified,
      });
    },

    clear() {
      this.transfer = null;
      this.error = null;
      this.locked = false;
      this.lockExpiresAt = null;
    },
  },
});
```

- [ ] **Step 3: Deploy — push code to server, no build yet (no Vue components touched)**

Run on server:

```bash
cd /home/v15/frappe-bench/apps/damage_pwa && sudo -u v15 git add -A && sudo -u v15 git commit -m "feat: add inspection store + photo compression helper

Pinia inspection store: loadTransfer, claim, saveItem, approve, reject.
Photo helper: Canvas-based compression to JPEG ≤1MB at max 1280px.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: ChipSelect + PhotoSlot + ItemRow Components

**Files:**
- Create: `frontend/src/components/ChipSelect.vue`
- Create: `frontend/src/components/PhotoSlot.vue`
- Create: `frontend/src/components/ItemRow.vue`

- [ ] **Step 1: Create ChipSelect.vue**

Create `apps/damage_pwa/frontend/src/components/ChipSelect.vue`:

```vue
<template>
  <div class="chip-group">
    <button
      v-for="opt in options"
      :key="opt.value"
      type="button"
      class="chip"
      :class="{ selected: modelValue === opt.value }"
      @click="$emit('update:modelValue', opt.value)"
    >
      {{ opt.label }}
    </button>
  </div>
</template>

<script setup>
defineProps({
  modelValue: { type: [String, null], default: null },
  options: { type: Array, required: true },
});
defineEmits(["update:modelValue"]);
</script>

<style scoped>
.chip-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chip {
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 8px 14px;
  font-family: var(--font);
  font-size: 11px;
  letter-spacing: 1px;
  text-transform: uppercase;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.chip.selected {
  background: var(--amber);
  color: #000;
  border-color: var(--amber);
}

.chip:active {
  transform: scale(0.97);
}
</style>
```

- [ ] **Step 2: Create PhotoSlot.vue**

Create `apps/damage_pwa/frontend/src/components/PhotoSlot.vue`:

```vue
<template>
  <div class="photo-slot" :class="{ filled: modelValue, required, uploading }">
    <div v-if="modelValue" class="preview">
      <img :src="previewSrc" alt="Photo" />
      <button class="delete-btn" type="button" @click="handleDelete">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
          <line x1="18" y1="6" x2="6" y2="18"/>
          <line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>
    <div v-else-if="uploading" class="uploading-state">
      <span class="spinner"></span>
      <p class="slot-label">UPLOADING...</p>
    </div>
    <div v-else class="empty-state">
      <p v-if="label" class="slot-label">{{ label }}</p>
      <div class="actions">
        <button type="button" class="capture-btn" @click="triggerCamera">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
            <circle cx="12" cy="13" r="4"/>
          </svg>
          <span>CAMERA</span>
        </button>
        <button type="button" class="capture-btn" @click="triggerGallery">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="18" height="18" rx="2"/>
            <circle cx="8.5" cy="8.5" r="1.5"/>
            <polyline points="21 15 16 10 5 21"/>
          </svg>
          <span>GALLERY</span>
        </button>
      </div>
      <p v-if="error" class="slot-error">{{ error }}</p>
    </div>
    <input
      ref="cameraInput"
      type="file"
      accept="image/*"
      capture="environment"
      style="display:none"
      @change="handleFile"
    />
    <input
      ref="galleryInput"
      type="file"
      accept="image/*"
      style="display:none"
      @change="handleFile"
    />
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import { compressAndUpload, makeThumbnail } from "@/utils/photo.js";

const props = defineProps({
  modelValue: { type: [String, null], default: null },  // File URL
  label: { type: String, default: "" },
  required: { type: Boolean, default: false },
});

const emit = defineEmits(["update:modelValue"]);

const cameraInput = ref(null);
const galleryInput = ref(null);
const uploading = ref(false);
const error = ref("");
const localThumb = ref(null);

const previewSrc = computed(() => localThumb.value || props.modelValue);

function triggerCamera() {
  error.value = "";
  cameraInput.value?.click();
}

function triggerGallery() {
  error.value = "";
  galleryInput.value?.click();
}

async function handleFile(e) {
  const file = e.target.files?.[0];
  e.target.value = "";  // Reset so same file can be reselected
  if (!file) return;

  uploading.value = true;
  error.value = "";
  try {
    // Show thumbnail immediately for UX
    localThumb.value = await makeThumbnail(file);
    // Upload in background
    const fileUrl = await compressAndUpload(file);
    emit("update:modelValue", fileUrl);
  } catch (err) {
    error.value = err.message || "Upload failed";
    localThumb.value = null;
  } finally {
    uploading.value = false;
  }
}

function handleDelete() {
  localThumb.value = null;
  emit("update:modelValue", null);
}
</script>

<style scoped>
.photo-slot {
  aspect-ratio: 1;
  background: var(--surface);
  border: 1px dashed var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.photo-slot.required:not(.filled) {
  border-color: var(--amber);
  border-style: dashed;
}

.photo-slot.filled {
  border-style: solid;
  border-color: var(--border);
}

.preview {
  width: 100%;
  height: 100%;
  position: relative;
}

.preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.delete-btn {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  border: none;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.empty-state, .uploading-state {
  padding: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  text-align: center;
  width: 100%;
}

.slot-label {
  font-size: 9px;
  letter-spacing: 1.5px;
  color: var(--text-dim);
  text-transform: uppercase;
}

.actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
}

.capture-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  background: transparent;
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 8px;
  font-family: var(--font);
  font-size: 10px;
  letter-spacing: 1px;
  font-weight: 600;
  cursor: pointer;
  text-transform: uppercase;
}

.capture-btn:active {
  background: var(--amber);
  color: #000;
  border-color: var(--amber);
}

.slot-error {
  color: var(--red);
  font-size: 9px;
  letter-spacing: 1px;
}

.spinner {
  display: inline-block;
  width: 20px;
  height: 20px;
  border: 2px solid var(--border);
  border-top-color: var(--amber);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }
</style>
```

- [ ] **Step 3: Create ItemRow.vue**

Create `apps/damage_pwa/frontend/src/components/ItemRow.vue`:

```vue
<template>
  <div class="item-row" :class="statusClass" @click="$emit('click')">
    <div class="status-icon">
      <svg v-if="item._inspection_status === 'complete'" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
        <polyline points="20 6 9 17 4 12"/>
      </svg>
      <svg v-else-if="item._inspection_status === 'flagged'" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
        <line x1="12" y1="9" x2="12" y2="13"/>
        <line x1="12" y1="17" x2="12.01" y2="17"/>
      </svg>
      <span v-else class="empty-dot"></span>
    </div>
    <div class="item-body">
      <p class="item-code">{{ item.item_code }}</p>
      <p class="item-name">{{ item.item_name }}</p>
      <p class="meta">{{ item.qty }} {{ item.stock_uom }}<span v-if="item.supplier_code"> · {{ item.supplier_code }}</span></p>
    </div>
    <svg class="chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <polyline points="9 18 15 12 9 6"/>
    </svg>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  item: { type: Object, required: true },
});

defineEmits(["click"]);

const statusClass = computed(() => {
  return `status-${props.item._inspection_status || "incomplete"}`;
});
</script>

<style scoped>
.item-row {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 3px solid var(--border);
  border-radius: var(--radius);
  padding: 12px;
  cursor: pointer;
  transition: border-color 0.15s;
}

.item-row.status-complete { border-left-color: var(--green); }
.item-row.status-flagged  { border-left-color: var(--amber); }
.item-row.status-incomplete { border-left-color: var(--text-dim); }

.item-row:active {
  background: #222;
}

.status-icon {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.status-complete .status-icon { color: var(--green); background: rgba(34, 197, 94, 0.15); }
.status-flagged  .status-icon { color: var(--amber); background: rgba(245, 158, 11, 0.15); }
.status-incomplete .status-icon .empty-dot {
  width: 10px;
  height: 10px;
  border: 1.5px solid var(--text-dim);
  border-radius: 50%;
}

.item-body {
  flex: 1;
  min-width: 0;
}

.item-code {
  font-weight: 700;
  font-size: 13px;
  letter-spacing: 0.5px;
}

.item-name {
  font-size: 12px;
  color: var(--text-dim);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.meta {
  font-size: 11px;
  color: var(--text-dim);
  margin-top: 4px;
}

.chevron {
  color: var(--text-dim);
  flex-shrink: 0;
}
</style>
```

- [ ] **Step 4: Commit**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa && sudo -u v15 git add -A && sudo -u v15 git commit -m "feat: add ChipSelect, PhotoSlot, ItemRow components

ChipSelect: pill-select for damage category.
PhotoSlot: camera/gallery + client-side compression + delete.
ItemRow: transfer item card with inspection status indicator.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Transfer Detail View

**Files:**
- Modify: `frontend/src/views/TransferDetailView.vue` (rewrite from stub)

- [ ] **Step 1: Rewrite TransferDetailView.vue**

Replace the entire contents of `apps/damage_pwa/frontend/src/views/TransferDetailView.vue` with:

```vue
<template>
  <div class="page">
    <div class="back-row">
      <button class="back-btn" @click="$router.push('/dashboard')">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="19" y1="12" x2="5" y2="12"/>
          <polyline points="12 19 5 12 12 5"/>
        </svg>
        BACK
      </button>
      <div class="progress-pill">{{ store.progressText }}</div>
    </div>

    <div v-if="store.loading" class="loading">
      <span class="spinner"></span> LOADING...
    </div>

    <div v-else-if="store.error" class="empty">
      <p class="error-text">{{ store.error }}</p>
      <button class="btn-ghost" @click="load">RETRY</button>
    </div>

    <template v-else-if="store.transfer">
      <h2 class="page-title">{{ store.transfer.name }}</h2>

      <div class="info-card">
        <div class="info-row">
          <span class="label">FROM</span>
          <span>{{ shortWh(store.transfer.branch_warehouse) }}</span>
        </div>
        <div class="info-row">
          <span class="label">TO</span>
          <span>{{ shortWh(store.transfer.damage_warehouse) }}</span>
        </div>
        <div class="info-row">
          <span class="label">DATE</span>
          <span>{{ store.transfer.transaction_date }}</span>
        </div>
        <div v-if="store.transfer.damage_slips?.length" class="info-row">
          <span class="label">SLIPS</span>
          <span>{{ store.transfer.damage_slips.length }}</span>
        </div>
      </div>

      <div v-if="isLockedByOther" class="lock-warning">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="3" y="11" width="18" height="11" rx="2"/>
          <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
        </svg>
        LOCKED BY {{ store.transfer.locked_by }}
      </div>

      <div v-if="claimError" class="lock-warning">{{ claimError }}</div>

      <p class="section-label">ITEMS ({{ store.itemCount }})</p>

      <div class="item-list">
        <ItemRow
          v-for="item in store.items"
          :key="item.row_name"
          :item="item"
          @click="openItem(item)"
        />
      </div>

      <div v-if="store.transfer.damage_slips?.length" class="slips-section">
        <p class="section-label">LINKED DAMAGE SLIPS</p>
        <div class="slip-list">
          <div
            v-for="slip in store.transfer.damage_slips"
            :key="slip.damage_slip"
            class="slip-item"
            @click="$router.push(`/slip/${slip.damage_slip}`)"
          >
            <div>
              <p class="slip-name">{{ slip.damage_slip }}</p>
              <p class="slip-meta">{{ slip.slip_date }} · {{ slip.total_items }} items</p>
            </div>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="9 18 15 12 9 6"/>
            </svg>
          </div>
        </div>
      </div>

      <div class="actions-bar">
        <button
          class="btn-danger full"
          :disabled="isLockedByOther || store.saving"
          @click="promptReject"
        >
          REJECT
        </button>
        <button
          class="btn-success full"
          :disabled="!store.allInspected || isLockedByOther || store.saving"
          @click="confirmApprove"
        >
          APPROVE
        </button>
      </div>

      <p v-if="!store.allInspected" class="approve-hint">
        {{ store.itemCount - store.inspectedCount }} items still pending inspection
      </p>
    </template>

    <!-- Reject modal -->
    <div v-if="showRejectModal" class="modal-backdrop" @click.self="showRejectModal = false">
      <div class="modal">
        <p class="modal-title">REJECT TRANSFER</p>
        <p class="modal-hint">Provide a reason — this returns the transfer to the Branch User for rework.</p>
        <textarea v-model="rejectReason" rows="3" placeholder="Reason..."></textarea>
        <p v-if="actionError" class="error-text">{{ actionError }}</p>
        <div class="modal-actions">
          <button class="btn-ghost full" @click="showRejectModal = false">CANCEL</button>
          <button class="btn-danger full" :disabled="!rejectReason.trim() || submitting" @click="handleReject">
            {{ submitting ? "REJECTING..." : "REJECT" }}
          </button>
        </div>
      </div>
    </div>

    <!-- Approve confirmation -->
    <div v-if="showApproveModal" class="modal-backdrop" @click.self="showApproveModal = false">
      <div class="modal">
        <p class="modal-title">APPROVE TRANSFER?</p>
        <p class="modal-hint">This creates a Stock Entry moving items to the damage warehouse. This cannot be undone.</p>
        <p v-if="actionError" class="error-text">{{ actionError }}</p>
        <div class="modal-actions">
          <button class="btn-ghost full" @click="showApproveModal = false">CANCEL</button>
          <button class="btn-success full" :disabled="submitting" @click="handleApprove">
            {{ submitting ? "APPROVING..." : "CONFIRM" }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useInspectionStore } from "@/store/inspection.js";
import { useAuthStore } from "@/store/auth.js";
import { useMasterStore } from "@/store/master.js";
import ItemRow from "@/components/ItemRow.vue";

const props = defineProps({
  name: { type: String, required: true },
});

const router = useRouter();
const store = useInspectionStore();
const auth = useAuthStore();
const master = useMasterStore();

const claimError = ref("");
const showRejectModal = ref(false);
const showApproveModal = ref(false);
const rejectReason = ref("");
const actionError = ref("");
const submitting = ref(false);

const isLockedByOther = computed(() => {
  const lockedBy = store.transfer?.locked_by;
  return !!lockedBy && lockedBy !== auth.user;
});

onMounted(load);

async function load() {
  await store.loadTransfer(props.name);
  // Ensure supplier codes are cached for the inspection view
  if (!master.supplierCodes.length) {
    master.fetchSupplierCodes();
  }
  // Claim lock if available and state is Pending Inspection
  if (store.transfer?.workflow_state === "Pending Inspection" && !isLockedByOther.value) {
    try {
      await store.claim(props.name);
    } catch (e) {
      claimError.value = e.message;
    }
  }
}

function openItem(item) {
  if (isLockedByOther.value) return;
  router.push(`/transfer/${props.name}/inspect/${item.row_name}`);
}

function promptReject() {
  actionError.value = "";
  rejectReason.value = "";
  showRejectModal.value = true;
}

function confirmApprove() {
  actionError.value = "";
  showApproveModal.value = true;
}

async function handleReject() {
  submitting.value = true;
  actionError.value = "";
  try {
    await store.reject(rejectReason.value.trim());
    showRejectModal.value = false;
    router.replace("/dashboard");
  } catch (e) {
    actionError.value = e.message;
  } finally {
    submitting.value = false;
  }
}

async function handleApprove() {
  submitting.value = true;
  actionError.value = "";
  try {
    const result = await store.approve();
    showApproveModal.value = false;
    if (result.warnings?.length) {
      alert("Approved with warnings:\n" + result.warnings.join("\n"));
    }
    router.replace("/dashboard");
  } catch (e) {
    actionError.value = e.message;
  } finally {
    submitting.value = false;
  }
}

function shortWh(name) {
  if (!name) return "—";
  return name.replace(/ - CNC$/, "").replace(/^Warehouse /, "");
}
</script>

<style scoped>
.back-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: transparent;
  color: var(--text-dim);
  border: none;
  padding: 0;
  font-family: var(--font);
  font-size: 11px;
  letter-spacing: 1.5px;
  cursor: pointer;
  font-weight: 600;
}

.progress-pill {
  background: var(--surface);
  border: 1px solid var(--amber);
  color: var(--amber);
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 1px;
}

.info-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 16px;
  margin-bottom: 16px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  font-size: 13px;
}

.info-row:last-child { border-bottom: none; }

.info-row .label {
  color: var(--amber);
  font-size: 10px;
  letter-spacing: 1.5px;
}

.lock-warning {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(220, 38, 38, 0.1);
  border: 1px solid var(--red);
  color: var(--red);
  padding: 10px 12px;
  border-radius: var(--radius);
  margin-bottom: 16px;
  font-size: 11px;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  font-weight: 600;
}

.section-label {
  font-size: 10px;
  letter-spacing: 2px;
  color: var(--amber);
  text-transform: uppercase;
  margin-bottom: 8px;
}

.item-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 20px;
}

.slips-section {
  margin-bottom: 80px;
}

.slip-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.slip-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 10px 14px;
  cursor: pointer;
}

.slip-item:active { background: #222; }
.slip-name { font-size: 13px; font-weight: 600; }
.slip-meta { font-size: 11px; color: var(--text-dim); margin-top: 2px; }

.actions-bar {
  position: fixed;
  bottom: 60px;
  left: 0;
  right: 0;
  display: flex;
  gap: 8px;
  padding: 8px 16px;
  background: var(--bg);
  border-top: 1px solid var(--border);
  z-index: 90;
  padding-bottom: max(8px, env(safe-area-inset-bottom));
}

.actions-bar .full {
  flex: 1;
  height: 44px;
  font-size: 13px;
}

.actions-bar button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.approve-hint {
  position: fixed;
  bottom: 118px;
  left: 16px;
  right: 16px;
  text-align: center;
  color: var(--text-dim);
  font-size: 10px;
  letter-spacing: 1px;
  z-index: 89;
  text-transform: uppercase;
}

.loading, .empty {
  text-align: center;
  color: var(--text-dim);
  padding: 48px 0;
  font-size: 12px;
  letter-spacing: 1.5px;
  text-transform: uppercase;
}

.empty button { margin-top: 12px; }

.error-text {
  color: var(--red);
  font-size: 11px;
  letter-spacing: 1px;
  text-transform: uppercase;
}

.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid var(--border);
  border-top-color: var(--amber);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  vertical-align: middle;
  margin-right: 8px;
}

@keyframes spin { to { transform: rotate(360deg); } }

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.8);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  z-index: 200;
}

.modal {
  background: var(--surface);
  border-top: 1px solid var(--border);
  border-radius: 16px 16px 0 0;
  padding: 20px 16px;
  width: 100%;
  max-width: 480px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: max(20px, env(safe-area-inset-bottom));
}

.modal-title {
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 2px;
}

.modal-hint {
  font-size: 12px;
  color: var(--text-dim);
}

.modal textarea {
  resize: none;
}

.modal-actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}

.modal-actions .full {
  flex: 1;
  height: 44px;
}
</style>
```

- [ ] **Step 2: Build frontend**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa/frontend && sudo -u v15 yarn build
```

Expected: Build completes without errors. New hashed asset files appear in `damage_pwa/public/frontend/assets/`.

- [ ] **Step 3: Deploy**

```bash
sudo -u v15 ln -sfn /home/v15/frappe-bench/apps/damage_pwa/damage_pwa/public /home/v15/frappe-bench/sites/assets/damage_pwa && cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 clear-cache && sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web
```

- [ ] **Step 4: Verify manually**

Visit `https://rmax-dev.fateherp.com/damage-pwa/` → login as sabith@gmail.com → tap the pending transfer card. Expected:
- Transfer detail loads with info card (FROM/TO/DATE)
- Items list shows with incomplete status dots
- Progress pill shows "0/N"
- Approve button is disabled
- Reject button is enabled

- [ ] **Step 5: Commit**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa && sudo -u v15 git add -A && sudo -u v15 git commit -m "feat: implement Transfer Detail view

Shows items with inspection status, linked slips, approve/reject actions.
Auto-claims lock on mount. Reject requires reason modal.
Approve requires all items inspected + confirmation modal.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Item Inspection View

**Files:**
- Modify: `frontend/src/views/InspectionView.vue` (rewrite from stub)

**Damage categories** (from spec section 2.4) — hardcoded list:
- `Glass or Body Broken`
- `Flickering`
- `Driver Damage`
- `Sensor Damage`
- `LED Damage`
- `Other`

- [ ] **Step 1: Rewrite InspectionView.vue**

Replace the entire contents of `apps/damage_pwa/frontend/src/views/InspectionView.vue` with:

```vue
<template>
  <div class="page">
    <div class="back-row">
      <button class="back-btn" @click="goBack">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="19" y1="12" x2="5" y2="12"/>
          <polyline points="12 19 5 12 12 5"/>
        </svg>
        BACK
      </button>
      <span class="item-counter">{{ store.transfer?.name }} · {{ itemIndex + 1 }} / {{ store.itemCount }}</span>
    </div>

    <div v-if="store.loading || !item" class="loading">
      <span class="spinner"></span> LOADING...
    </div>

    <template v-else>
      <div class="item-card">
        <p class="item-code">{{ item.item_code }}</p>
        <p class="item-name">{{ item.item_name }}</p>
        <p class="item-qty">{{ item.qty }} {{ item.stock_uom }}</p>
      </div>

      <div class="field-block">
        <label class="field-label">SUPPLIER CODE <span class="required">*</span></label>
        <select v-model="form.supplier_code">
          <option :value="null">-- Select --</option>
          <option v-for="sc in master.supplierCodes" :key="sc.name" :value="sc.name">
            {{ sc.supplier_code_name || sc.name }}
          </option>
        </select>
      </div>

      <div class="field-block">
        <label class="field-label">DAMAGE CATEGORY <span class="required">*</span></label>
        <ChipSelect v-model="form.damage_category" :options="CATEGORIES" />
      </div>

      <div class="field-block">
        <label class="field-label">PHOTOS <span class="required">*</span></label>
        <div class="photo-grid">
          <PhotoSlot v-model="form.images" label="REQUIRED" :required="true" />
          <PhotoSlot v-model="form.image_2" label="OPTIONAL" />
          <PhotoSlot v-model="form.image_3" label="OPTIONAL" />
        </div>
      </div>

      <div class="field-block">
        <label class="field-label">REMARKS</label>
        <textarea v-model="form.remarks" rows="3" placeholder="Optional notes..."></textarea>
      </div>

      <div class="flag-row">
        <label class="flag-check">
          <input type="checkbox" v-model="form.flagged" />
          <span>FLAG FOR REVIEW</span>
        </label>
        <p class="flag-hint">Mark as flagged if you are uncertain about the supplier or category. Flagged items don't block approval but show a warning.</p>
      </div>

      <p v-if="saveError" class="error-text">{{ saveError }}</p>

      <div class="actions-bar">
        <button class="btn-ghost full" :disabled="isFirst || saving" @click="savePrev">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:4px; vertical-align:middle">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
          PREV
        </button>
        <button class="btn-primary full" :disabled="!canSave || saving" @click="saveAndContinue">
          {{ saving ? "SAVING..." : (isLast ? "SAVE & DONE" : "SAVE & NEXT") }}
          <svg v-if="!isLast" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-left:4px; vertical-align:middle">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
        </button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { useInspectionStore } from "@/store/inspection.js";
import { useMasterStore } from "@/store/master.js";
import ChipSelect from "@/components/ChipSelect.vue";
import PhotoSlot from "@/components/PhotoSlot.vue";

const CATEGORIES = [
  { value: "Glass or Body Broken", label: "Glass / Body" },
  { value: "Flickering", label: "Flickering" },
  { value: "Driver Damage", label: "Driver" },
  { value: "Sensor Damage", label: "Sensor" },
  { value: "LED Damage", label: "LED" },
  { value: "Other", label: "Other" },
];

const props = defineProps({
  name: { type: String, required: true },
  rowName: { type: String, required: true },
});

const router = useRouter();
const store = useInspectionStore();
const master = useMasterStore();

const saving = ref(false);
const saveError = ref("");

const form = ref({
  supplier_code: null,
  damage_category: null,
  images: null,
  image_2: null,
  image_3: null,
  remarks: "",
  flagged: false,
});

const item = computed(() => store.findItem(props.rowName));

const itemIndex = computed(() =>
  store.items.findIndex((i) => i.row_name === props.rowName)
);

const isFirst = computed(() => itemIndex.value <= 0);
const isLast = computed(() => itemIndex.value === store.itemCount - 1);

const canSave = computed(() => {
  return !!form.value.supplier_code
    && !!form.value.damage_category
    && !!form.value.images;
});

onMounted(async () => {
  // If no transfer loaded or different one, load it
  if (!store.transfer || store.transfer.name !== props.name) {
    await store.loadTransfer(props.name);
  }
  if (!master.supplierCodes.length) {
    await master.fetchSupplierCodes();
  }
  hydrateForm();
});

// Rehydrate form when rowName changes (PREV/NEXT navigation)
watch(() => props.rowName, hydrateForm);

function hydrateForm() {
  saveError.value = "";
  const row = item.value;
  if (!row) return;
  form.value = {
    supplier_code: row.supplier_code || null,
    damage_category: row.damage_category || null,
    images: row.images || null,
    image_2: row.image_2 || null,
    image_3: row.image_3 || null,
    remarks: row.remarks || "",
    flagged: row._inspection_status === "flagged",
  };
}

async function save() {
  saveError.value = "";
  saving.value = true;
  try {
    await store.saveItem({
      rowName: props.rowName,
      supplier_code: form.value.supplier_code,
      damage_category: form.value.damage_category,
      images: form.value.images,
      image_2: form.value.image_2,
      image_3: form.value.image_3,
      remarks: form.value.remarks || null,
      status: form.value.flagged ? "flagged" : "complete",
    });
    return true;
  } catch (e) {
    saveError.value = e.message;
    return false;
  } finally {
    saving.value = false;
  }
}

async function saveAndContinue() {
  const ok = await save();
  if (!ok) return;
  if (isLast.value) {
    router.replace(`/transfer/${props.name}`);
  } else {
    const next = store.items[itemIndex.value + 1];
    router.replace(`/transfer/${props.name}/inspect/${next.row_name}`);
  }
}

async function savePrev() {
  if (isFirst.value) return;
  // Save current if anything filled, else just navigate
  if (canSave.value) {
    const ok = await save();
    if (!ok) return;
  }
  const prev = store.items[itemIndex.value - 1];
  router.replace(`/transfer/${props.name}/inspect/${prev.row_name}`);
}

function goBack() {
  router.push(`/transfer/${props.name}`);
}
</script>

<style scoped>
.back-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: transparent;
  color: var(--text-dim);
  border: none;
  padding: 0;
  font-family: var(--font);
  font-size: 11px;
  letter-spacing: 1.5px;
  cursor: pointer;
  font-weight: 600;
}

.item-counter {
  font-size: 11px;
  color: var(--text-dim);
  letter-spacing: 1px;
}

.item-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 3px solid var(--amber);
  border-radius: var(--radius);
  padding: 14px 16px;
  margin-bottom: 20px;
}

.item-code {
  font-weight: 700;
  font-size: 15px;
  letter-spacing: 0.5px;
}

.item-name {
  font-size: 13px;
  color: var(--text-dim);
  margin-top: 4px;
}

.item-qty {
  font-size: 12px;
  color: var(--amber);
  margin-top: 6px;
  letter-spacing: 1px;
}

.field-block {
  margin-bottom: 20px;
}

.field-label {
  display: block;
  font-size: 10px;
  letter-spacing: 2px;
  color: var(--amber);
  text-transform: uppercase;
  margin-bottom: 8px;
  font-weight: 600;
}

.required { color: var(--red); }

.photo-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.flag-row {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 14px;
  margin-bottom: 20px;
}

.flag-check {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  letter-spacing: 1.5px;
  font-weight: 600;
  cursor: pointer;
}

.flag-check input {
  width: 18px;
  height: 18px;
  accent-color: var(--amber);
}

.flag-hint {
  font-size: 11px;
  color: var(--text-dim);
  margin-top: 6px;
  line-height: 1.4;
}

.error-text {
  color: var(--red);
  font-size: 11px;
  letter-spacing: 1px;
  text-transform: uppercase;
  margin-bottom: 12px;
}

.actions-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.actions-bar .full {
  flex: 1;
  height: 48px;
  font-size: 13px;
}

.actions-bar button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.loading {
  text-align: center;
  color: var(--text-dim);
  padding: 48px 0;
  font-size: 12px;
  letter-spacing: 1.5px;
  text-transform: uppercase;
}

.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid var(--border);
  border-top-color: var(--amber);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  vertical-align: middle;
  margin-right: 8px;
}

@keyframes spin { to { transform: rotate(360deg); } }
</style>
```

- [ ] **Step 2: Build**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa/frontend && sudo -u v15 yarn build
```

- [ ] **Step 3: Deploy**

```bash
cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 clear-cache && sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web
```

- [ ] **Step 4: Verify manually**

From Transfer Detail, tap an item. Expected:
- Item Inspection view loads with item code, name, qty
- Supplier Code dropdown populates
- 6 damage category chips render
- 3 photo slots (first marked REQUIRED)
- Save & Next is disabled until all required fields filled
- Camera button opens device camera (on mobile)
- Save & Next persists data and navigates to next item
- After last item, returns to Transfer Detail

- [ ] **Step 5: Commit**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa && sudo -u v15 git add -A && sudo -u v15 git commit -m "feat: implement Item Inspection view

Supplier code dropdown, damage category chip select, 3 photo slots,
remarks, flag-for-review checkbox. PREV/NEXT navigation.
Save blocked until supplier_code + category + required photo set.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Slip Detail View

**Files:**
- Modify: `frontend/src/views/SlipDetailView.vue` (rewrite from stub)

- [ ] **Step 1: Rewrite SlipDetailView.vue**

Replace the entire contents of `apps/damage_pwa/frontend/src/views/SlipDetailView.vue` with:

```vue
<template>
  <div class="page">
    <div class="back-row">
      <button class="back-btn" @click="$router.back()">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="19" y1="12" x2="5" y2="12"/>
          <polyline points="12 19 5 12 12 5"/>
        </svg>
        BACK
      </button>
    </div>

    <div v-if="loading" class="loading">
      <span class="spinner"></span> LOADING...
    </div>

    <div v-else-if="error" class="empty">
      <p class="error-text">{{ error }}</p>
      <button class="btn-ghost" @click="load">RETRY</button>
    </div>

    <template v-else-if="slip">
      <h2 class="page-title">{{ slip.name }}</h2>

      <div class="info-card">
        <div class="info-row"><span class="label">DATE</span><span>{{ slip.date }}</span></div>
        <div class="info-row"><span class="label">FROM</span><span>{{ shortWh(slip.branch_warehouse) }}</span></div>
        <div class="info-row"><span class="label">TO</span><span>{{ shortWh(slip.damage_warehouse) }}</span></div>
        <div v-if="slip.customer" class="info-row"><span class="label">CUSTOMER</span><span>{{ slip.customer }}</span></div>
        <div v-if="slip.damage_category" class="info-row"><span class="label">CATEGORY</span><span>{{ slip.damage_category }}</span></div>
        <div class="info-row"><span class="label">STATUS</span><span>{{ slip.status }}</span></div>
      </div>

      <div v-if="slip.remarks" class="remarks-card">
        <p class="section-label">REMARKS</p>
        <p class="remarks-text">{{ slip.remarks }}</p>
      </div>

      <p class="section-label">ITEMS ({{ slip.items?.length || 0 }})</p>

      <div class="item-list">
        <div v-for="(item, i) in slip.items" :key="i" class="item">
          <p class="item-code">{{ item.item_code }}</p>
          <p class="item-name">{{ item.item_name }}</p>
          <p class="item-qty">{{ item.qty }} {{ item.stock_uom }}</p>
          <p v-if="item.description" class="item-desc">{{ item.description }}</p>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { call } from "@/utils/frappe.js";

const props = defineProps({
  name: { type: String, required: true },
});

const slip = ref(null);
const loading = ref(false);
const error = ref("");

onMounted(load);

async function load() {
  loading.value = true;
  error.value = "";
  try {
    slip.value = await call("damage_pwa.api.inspect.get_slip_detail", { name: props.name });
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

function shortWh(name) {
  if (!name) return "—";
  return name.replace(/ - CNC$/, "").replace(/^Warehouse /, "");
}
</script>

<style scoped>
.back-row { margin-bottom: 12px; }

.back-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: transparent;
  color: var(--text-dim);
  border: none;
  padding: 0;
  font-family: var(--font);
  font-size: 11px;
  letter-spacing: 1.5px;
  cursor: pointer;
  font-weight: 600;
}

.info-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 16px;
  margin-bottom: 16px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  font-size: 13px;
}

.info-row:last-child { border-bottom: none; }

.info-row .label {
  color: var(--amber);
  font-size: 10px;
  letter-spacing: 1.5px;
}

.remarks-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 16px;
  margin-bottom: 16px;
}

.remarks-text {
  font-size: 12px;
  color: var(--text);
  margin-top: 6px;
  line-height: 1.5;
  white-space: pre-wrap;
}

.section-label {
  font-size: 10px;
  letter-spacing: 2px;
  color: var(--amber);
  text-transform: uppercase;
  margin-bottom: 8px;
  font-weight: 600;
}

.item-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 16px;
}

.item {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 10px 14px;
}

.item-code { font-weight: 700; font-size: 13px; letter-spacing: 0.5px; }
.item-name { font-size: 12px; color: var(--text-dim); margin-top: 2px; }
.item-qty { font-size: 11px; color: var(--amber); margin-top: 4px; letter-spacing: 1px; }
.item-desc { font-size: 11px; color: var(--text-dim); margin-top: 4px; font-style: italic; }

.loading, .empty {
  text-align: center;
  color: var(--text-dim);
  padding: 48px 0;
  font-size: 12px;
  letter-spacing: 1.5px;
  text-transform: uppercase;
}

.empty button { margin-top: 12px; }

.error-text {
  color: var(--red);
  font-size: 11px;
  letter-spacing: 1px;
  text-transform: uppercase;
}

.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid var(--border);
  border-top-color: var(--amber);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  vertical-align: middle;
  margin-right: 8px;
}

@keyframes spin { to { transform: rotate(360deg); } }
</style>
```

- [ ] **Step 2: Commit (no build needed yet — bundled with History)**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa && sudo -u v15 git add -A && sudo -u v15 git commit -m "feat: implement Slip Detail view

Read-only Damage Slip viewer accessed from Transfer Detail.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 6: History View

**Files:**
- Modify: `frontend/src/views/HistoryView.vue` (rewrite from stub)

- [ ] **Step 1: Rewrite HistoryView.vue**

Replace the entire contents of `apps/damage_pwa/frontend/src/views/HistoryView.vue` with:

```vue
<template>
  <div class="page">
    <h2 class="page-title">HISTORY</h2>

    <div class="tabs">
      <button
        v-for="tab in TABS"
        :key="tab.value"
        class="tab"
        :class="{ active: activeTab === tab.value }"
        @click="setTab(tab.value)"
      >
        {{ tab.label }}
      </button>
    </div>

    <div v-if="loading && !items.length" class="loading">
      <span class="spinner"></span> LOADING...
    </div>

    <div v-else-if="error && !items.length" class="empty">
      <p class="error-text">{{ error }}</p>
      <button class="btn-ghost" @click="reload">RETRY</button>
    </div>

    <div v-else-if="!items.length" class="empty">
      <p>NO RECORDS</p>
    </div>

    <div v-else class="history-list" @scroll="onScroll" ref="listRef">
      <div
        v-for="t in items"
        :key="t.name"
        class="history-item"
        :class="`status-${t.workflow_state.toLowerCase().replace(/ /g, '-')}`"
        @click="open(t)"
      >
        <div class="left">
          <p class="dt-name">{{ t.name }}</p>
          <p class="meta">{{ shortWh(t.branch_warehouse) }} → {{ shortWh(t.damage_warehouse) }}</p>
          <p class="meta-small">{{ t.transaction_date }} · {{ t.item_count }} items</p>
        </div>
        <span class="badge" :class="badgeClass(t.workflow_state)">{{ t.workflow_state }}</span>
      </div>

      <div v-if="loading" class="loading-more">
        <span class="spinner-sm"></span> LOADING MORE...
      </div>

      <div v-if="!hasMore && items.length" class="end-marker">
        · END OF RESULTS ·
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { call } from "@/utils/frappe.js";

const TABS = [
  { value: "all", label: "ALL" },
  { value: "Approved", label: "APPROVED" },
  { value: "Rejected", label: "REJECTED" },
];

const PAGE_SIZE = 20;

const router = useRouter();
const listRef = ref(null);
const activeTab = ref("all");
const items = ref([]);
const loading = ref(false);
const error = ref("");
const start = ref(0);
const totalCount = ref(0);
const hasMore = ref(true);

onMounted(() => reload());

function setTab(tab) {
  if (activeTab.value === tab) return;
  activeTab.value = tab;
  reload();
}

async function reload() {
  items.value = [];
  start.value = 0;
  hasMore.value = true;
  await loadPage();
}

async function loadPage() {
  if (loading.value || !hasMore.value) return;
  loading.value = true;
  error.value = "";
  try {
    const args = { limit: PAGE_SIZE, start: start.value };
    if (activeTab.value !== "all") args.status_filter = activeTab.value;
    const result = await call("damage_pwa.api.inspect.get_history", args);
    items.value.push(...(result.data || []));
    totalCount.value = result.total_count || 0;
    start.value += result.data?.length || 0;
    hasMore.value = items.value.length < totalCount.value;
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

function onScroll(e) {
  const el = e.target;
  if (el.scrollHeight - el.scrollTop - el.clientHeight < 200) {
    loadPage();
  }
}

function open(t) {
  // Completed transfers open in read-only transfer detail
  router.push(`/transfer/${t.name}`);
}

function shortWh(name) {
  if (!name) return "—";
  return name.replace(/ - CNC$/, "").replace(/^Warehouse /, "");
}

function badgeClass(state) {
  if (state === "Approved") return "badge-green";
  if (state === "Rejected") return "badge-red";
  if (state === "Written Off") return "badge-dim";
  return "";
}
</script>

<style scoped>
.tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--border);
}

.tab {
  background: transparent;
  color: var(--text-dim);
  border: none;
  border-bottom: 2px solid transparent;
  padding: 10px 14px;
  font-family: var(--font);
  font-size: 11px;
  letter-spacing: 1.5px;
  font-weight: 600;
  cursor: pointer;
  text-transform: uppercase;
  border-radius: 0;
}

.tab.active {
  color: var(--amber);
  border-bottom-color: var(--amber);
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: calc(100dvh - 220px);
  overflow-y: auto;
}

.history-item {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 14px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  cursor: pointer;
}

.history-item.status-approved { border-left: 3px solid var(--green); }
.history-item.status-rejected { border-left: 3px solid var(--red); }
.history-item.status-written-off { border-left: 3px solid var(--text-dim); }

.history-item:active { background: #222; }

.left { flex: 1; min-width: 0; }

.dt-name { font-weight: 700; font-size: 14px; letter-spacing: 0.5px; }
.meta { font-size: 12px; color: var(--text-dim); margin-top: 4px; }
.meta-small { font-size: 11px; color: var(--text-dim); margin-top: 2px; }

.badge {
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 9px;
  letter-spacing: 1.5px;
  font-weight: 700;
  text-transform: uppercase;
  flex-shrink: 0;
}

.badge-green { background: rgba(34, 197, 94, 0.15); color: var(--green); }
.badge-red   { background: rgba(220, 38, 38, 0.15); color: var(--red); }
.badge-dim   { background: rgba(102, 102, 102, 0.15); color: var(--text-dim); }

.loading, .empty, .loading-more, .end-marker {
  text-align: center;
  color: var(--text-dim);
  font-size: 11px;
  letter-spacing: 1.5px;
  text-transform: uppercase;
}

.loading, .empty { padding: 48px 0; }
.loading-more { padding: 16px 0; }
.end-marker { padding: 16px 0; opacity: 0.5; }
.empty button { margin-top: 12px; }

.error-text { color: var(--red); }

.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid var(--border);
  border-top-color: var(--amber);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  vertical-align: middle;
  margin-right: 8px;
}

.spinner-sm {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid var(--border);
  border-top-color: var(--amber);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  vertical-align: middle;
  margin-right: 6px;
}

@keyframes spin { to { transform: rotate(360deg); } }
</style>
```

- [ ] **Step 2: Build**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa/frontend && sudo -u v15 yarn build
```

- [ ] **Step 3: Deploy**

```bash
cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 clear-cache && sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web
```

- [ ] **Step 4: Verify manually**

- Tap HISTORY tab in bottom nav
- Expected: List of completed transfers with status badges
- Tab switch: ALL / APPROVED / REJECTED filters correctly
- Scroll: infinite scroll loads more if >20 records
- Tap item: opens Transfer Detail (read-only since workflow_state isn't Pending)

- [ ] **Step 5: Commit**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa && sudo -u v15 git add -A && sudo -u v15 git commit -m "feat: implement History view

Tabs: ALL / APPROVED / REJECTED.
Infinite scroll pagination (20 per page).
Status badges on each row.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 7: Read-Only Transfer Detail for Completed Transfers

**Context:** Step 5 in Task 6 revealed that tapping a completed transfer from History opens the same `TransferDetailView`. That view currently always tries to claim a lock and shows approve/reject buttons. We need it to degrade to read-only when `workflow_state !== "Pending Inspection"`.

**Files:**
- Modify: `frontend/src/views/TransferDetailView.vue`

- [ ] **Step 1: Read the file**

Read the current state of `frontend/src/views/TransferDetailView.vue` (from Task 3).

- [ ] **Step 2: Make it conditional on workflow_state**

In `apps/damage_pwa/frontend/src/views/TransferDetailView.vue`:

**Change the computed `isLockedByOther`** section: add a new computed after it:

```javascript
const isReadOnly = computed(() =>
  store.transfer?.workflow_state !== "Pending Inspection"
);
```

Replace `isLockedByOther` in templates/scripts with `isReadOnly || isLockedByOther` wherever we disable editing (specifically `openItem`, approve/reject button disabled).

**Guard the claim() call in `load()`** — it already checks `workflow_state === "Pending Inspection"`, so this is already correct.

**Conditionally render the `actions-bar`** — wrap it in `v-if="!isReadOnly"`:

Find:
```html
      <div class="actions-bar">
```

Replace with:
```html
      <div v-if="!isReadOnly" class="actions-bar">
```

And find:
```html
      <p v-if="!store.allInspected" class="approve-hint">
```

Replace with:
```html
      <p v-if="!isReadOnly && !store.allInspected" class="approve-hint">
```

**Add a status badge for completed transfers** — insert after the `info-card` div, before the `lock-warning` block:

```html
      <div v-if="isReadOnly" class="status-banner" :class="statusBannerClass">
        {{ store.transfer.workflow_state.toUpperCase() }}
      </div>
```

**Update `openItem`** to block editing in read-only:

Find:
```javascript
function openItem(item) {
  if (isLockedByOther.value) return;
  router.push(`/transfer/${props.name}/inspect/${item.row_name}`);
}
```

Replace with:
```javascript
function openItem(item) {
  if (isReadOnly.value || isLockedByOther.value) return;
  router.push(`/transfer/${props.name}/inspect/${item.row_name}`);
}
```

**Add the `statusBannerClass` computed** — add after `isReadOnly`:

```javascript
const statusBannerClass = computed(() => {
  const s = store.transfer?.workflow_state;
  if (s === "Approved") return "banner-green";
  if (s === "Rejected") return "banner-red";
  return "banner-dim";
});
```

**Add CSS** — append to the `<style scoped>` block (before the closing `</style>`):

```css
.status-banner {
  padding: 10px 14px;
  border-radius: var(--radius);
  margin-bottom: 16px;
  font-size: 12px;
  letter-spacing: 2px;
  font-weight: 700;
  text-align: center;
}

.banner-green { background: rgba(34, 197, 94, 0.15); color: var(--green); border: 1px solid var(--green); }
.banner-red   { background: rgba(220, 38, 38, 0.15); color: var(--red); border: 1px solid var(--red); }
.banner-dim   { background: rgba(102, 102, 102, 0.15); color: var(--text-dim); border: 1px solid var(--text-dim); }
```

- [ ] **Step 3: Build**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa/frontend && sudo -u v15 yarn build
```

- [ ] **Step 4: Deploy**

```bash
cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 clear-cache && sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web
```

- [ ] **Step 5: Verify manually**

- From History, tap an Approved transfer. Expected: status banner shows "APPROVED", no approve/reject bar, tapping items does nothing (or stays on page).
- From Dashboard, tap a Pending transfer. Expected: full editable mode as before.

- [ ] **Step 6: Commit**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa && sudo -u v15 git add -A && sudo -u v15 git commit -m "feat: read-only Transfer Detail for completed transfers

Hides approve/reject bar and blocks item editing when workflow_state != Pending Inspection.
Shows colored status banner (green=Approved, red=Rejected).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Phase 3 Checkpoint

After completing all 7 tasks, verify:

| Test | Method | Expected |
|------|--------|----------|
| Transfer Detail loads | Dashboard → tap pending DT | Shows items, info card, slips, actions bar |
| Auto-claim works | Open pending DT | No "Locked by" warning (claim succeeds) |
| Inspection form | Tap an item | Supplier code dropdown, 6 category chips, 3 photo slots |
| Photo capture | Tap CAMERA in slot 1 | Device camera opens (mobile); Gallery opens file picker |
| Photo upload | After picking | Thumbnail appears, compression completes, URL saved |
| Save & Next | Fill all required + save | Moves to next item, updates parent progress |
| Flag for review | Check flag + save | Item shows amber border on Transfer Detail |
| Approve disabled | Any item incomplete | APPROVE button grayed out with hint message |
| Approve succeeds | All items complete → confirm | Redirects to dashboard, DT gone from pending |
| Reject requires reason | Empty reason modal | REJECT button disabled until text entered |
| Reject succeeds | Reason filled → confirm | Redirects to dashboard |
| Slip Detail | Tap linked slip | Read-only slip with items list |
| History ALL tab | Bottom nav → HISTORY | List of completed transfers with status badges |
| History filter | Tap APPROVED tab | List filters to approved only |
| Infinite scroll | Scroll history to bottom | Loads next page or shows "END OF RESULTS" |
| Read-only detail | History → tap approved DT | Status banner, no action bar, item taps disabled |

**Next:** Phase 4 — Offline Engine (IndexedDB sync queue, Service Worker, photo queue, background sync)
