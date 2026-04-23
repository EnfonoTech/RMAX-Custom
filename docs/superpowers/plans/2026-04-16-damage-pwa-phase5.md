# Damage PWA Phase 5: Polish + Android TWA Wrapper

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Final polish on the web experience (Settings with Change PIN, error toasts, pull-to-refresh, failed-items error banner) and package the PWA as a sideloadable Android APK via TWA.

**Architecture:** No new architecture. Settings view gains full functionality (Change PIN, Force Sync, Clear Cache, App Info). Global Toast store replaces scattered `alert()` calls. Pull-to-refresh on Dashboard. Android TWA project (Gradle + AndroidBrowserHelper) in a new `android/` directory + Digital Asset Links served from Frappe.

**Spec:** `docs/superpowers/specs/2026-04-16-damage-pwa-design.md` (sections 2.7 Settings, 6.2 Error UX, 7 Android TWA Wrapper)

**Depends on:** Phases 1-4 deployed.

**Server deploy commands:**
```
cd /home/v15/frappe-bench/apps/damage_pwa/frontend && sudo -u v15 yarn build
cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 clear-cache && sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web
```

---

## File Map

```
frappe-bench/apps/damage_pwa/
├── damage_pwa/
│   ├── api/
│   │   └── auth.py                    # MODIFY — add change_pin endpoint
│   └── www/
│       └── .well-known/
│           └── assetlinks.json        # NEW — static DAL file
└── frontend/src/
    ├── store/
    │   └── toast.js                   # NEW — global toast notifications
    ├── components/
    │   ├── Toast.vue                  # NEW — toast renderer
    │   └── ChangePinModal.vue         # NEW — 3-step PIN change modal
    ├── composables/
    │   └── usePullRefresh.js          # NEW — pull-to-refresh gesture
    └── views/
        └── SettingsView.vue           # REWRITE — full settings page

android/                                # NEW — TWA project (gitignored build dirs)
├── build.gradle
├── settings.gradle
├── gradle.properties
├── gradle/wrapper/
│   ├── gradle-wrapper.properties
│   └── gradle-wrapper.jar             # (downloaded by gradlew)
├── gradlew                             # Gradle wrapper script
├── app/
│   ├── build.gradle
│   └── src/main/
│       ├── AndroidManifest.xml
│       ├── java/com/rmax/damage_pwa/
│       │   └── LauncherActivity.kt    # TWA launcher
│       └── res/
│           ├── values/
│           │   ├── colors.xml
│           │   └── strings.xml
│           ├── mipmap-anydpi-v26/
│           │   └── ic_launcher.xml    # Adaptive icon
│           └── mipmap-*/              # Legacy icons (copy from PWA icons)
├── keystore/
│   └── .gitignore                     # Keystore not committed
└── README.md                           # Build instructions
```

---

### Task 1: Toast System (Replace alert())

**Files:**
- Create: `frontend/src/store/toast.js`
- Create: `frontend/src/components/Toast.vue`
- Modify: `frontend/src/App.vue` (mount Toast component)
- Modify: `frontend/src/views/TransferDetailView.vue` (use toast instead of alert)

- [ ] **Step 1: Create toast store**

Create `apps/damage_pwa/frontend/src/store/toast.js`:

```javascript
import { defineStore } from "pinia";

let seq = 0;

export const useToastStore = defineStore("toast", {
  state: () => ({
    toasts: [],  // { id, type: "success" | "error" | "info" | "warn", message, duration }
  }),

  actions: {
    push({ type = "info", message, duration = 3500 }) {
      const id = ++seq;
      this.toasts.push({ id, type, message, duration });
      if (duration > 0) {
        setTimeout(() => this.dismiss(id), duration);
      }
      return id;
    },
    success(message, duration) { return this.push({ type: "success", message, duration }); },
    error(message, duration = 5000) { return this.push({ type: "error", message, duration }); },
    info(message, duration)    { return this.push({ type: "info", message, duration }); },
    warn(message, duration)    { return this.push({ type: "warn", message, duration }); },
    dismiss(id) {
      this.toasts = this.toasts.filter((t) => t.id !== id);
    },
  },
});
```

- [ ] **Step 2: Create Toast.vue**

Create `apps/damage_pwa/frontend/src/components/Toast.vue`:

```vue
<template>
  <div class="toast-stack">
    <transition-group name="toast">
      <div
        v-for="t in toast.toasts"
        :key="t.id"
        class="toast"
        :class="`toast-${t.type}`"
        @click="toast.dismiss(t.id)"
      >
        <span class="icon">
          <svg v-if="t.type === 'success'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          <svg v-else-if="t.type === 'error'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          <svg v-else-if="t.type === 'warn'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="16" x2="12" y2="12"/>
            <line x1="12" y1="8" x2="12.01" y2="8"/>
          </svg>
        </span>
        <span class="msg">{{ t.message }}</span>
      </div>
    </transition-group>
  </div>
</template>

<script setup>
import { useToastStore } from "@/store/toast.js";
const toast = useToastStore();
</script>

<style scoped>
.toast-stack {
  position: fixed;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 300;
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: calc(100% - 32px);
  max-width: 420px;
  pointer-events: none;
}

.toast {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 3px solid var(--text-dim);
  border-radius: var(--radius);
  padding: 10px 14px;
  font-size: 12px;
  letter-spacing: 0.5px;
  color: var(--text);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
  pointer-events: auto;
  cursor: pointer;
}

.toast-success { border-left-color: var(--green); }
.toast-success .icon { color: var(--green); }
.toast-error   { border-left-color: var(--red); }
.toast-error   .icon { color: var(--red); }
.toast-warn    { border-left-color: var(--amber); }
.toast-warn    .icon { color: var(--amber); }
.toast-info    .icon { color: var(--text-dim); }

.icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.msg {
  flex: 1;
  line-height: 1.4;
  word-break: break-word;
}

.toast-enter-active, .toast-leave-active {
  transition: all 0.25s ease;
}
.toast-enter-from, .toast-leave-to {
  opacity: 0;
  transform: translateY(-12px);
}
</style>
```

- [ ] **Step 3: Mount Toast in App.vue**

Read `apps/damage_pwa/frontend/src/App.vue` on the server. Currently has `<SyncBar>` + `<router-view>` + `<BottomNav>`.

In the `<template>`, add `<Toast />` as the last child before `</div>`. In the `<script setup>`, add:

```javascript
import Toast from "@/components/Toast.vue";
```

Result should look like:

```vue
<template>
  <div class="app-shell">
    <SyncBar v-if="auth.isAuthenticated" />
    <router-view />
    <BottomNav v-if="auth.isAuthenticated" />
    <Toast />
  </div>
</template>

<script setup>
import { onMounted, watch } from "vue";
import { useAuthStore } from "@/store/auth.js";
import { useSyncStore } from "@/store/sync.js";
import BottomNav from "@/components/BottomNav.vue";
import SyncBar from "@/components/SyncBar.vue";
import Toast from "@/components/Toast.vue";

// ... rest unchanged
</script>
```

- [ ] **Step 4: Replace alert() in TransferDetailView.vue**

Read `apps/damage_pwa/frontend/src/views/TransferDetailView.vue`. Find:

```javascript
    if (result.warnings?.length) {
      alert("Approved with warnings:\n" + result.warnings.join("\n"));
    }
```

Replace with:

```javascript
    if (result.warnings?.length) {
      toast.warn("Approved with warnings: " + result.warnings.join(", "), 6000);
    } else if (result.queued) {
      toast.info("Approval queued — will sync when online");
    } else {
      toast.success("Transfer approved");
    }
```

At the top of `<script setup>` add the import + setup:

```javascript
import { useToastStore } from "@/store/toast.js";
// ... existing imports ...
const toast = useToastStore();
```

Also replace the catch blocks that currently set `actionError.value = e.message` to also emit toasts. Find the `handleReject` function; after the catch, the error is already shown in the modal, but add a toast for the success path — find:

```javascript
async function handleReject() {
  submitting.value = true;
  actionError.value = "";
  try {
    await store.reject(rejectReason.value.trim());
    showRejectModal.value = false;
    router.replace("/dashboard");
```

Add a toast emit between `showRejectModal.value = false` and `router.replace`:

```javascript
    toast.success(result?.queued ? "Rejection queued — will sync when online" : "Transfer rejected");
```

And change `await store.reject(...)` to `const result = await store.reject(...)`.

Similarly in `handleApprove`, change `await store.approve()` to `const result = await store.approve()` (already done above).

- [ ] **Step 5: Build + Deploy**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa/frontend && sudo -u v15 yarn build
cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 clear-cache && sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web
```

- [ ] **Step 6: Commit**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa && sudo -u v15 git add -A && sudo -u v15 git commit -m "feat: global toast system + replace alert()

Pinia toast store with push/success/error/warn/info methods.
Toast.vue renders stack of dismissible toasts with color-coded left border.
TransferDetailView uses toasts for approve/reject feedback.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Change PIN Backend + Modal

**Files:**
- Modify: `damage_pwa/damage_pwa/api/auth.py`
- Create: `frontend/src/components/ChangePinModal.vue`

- [ ] **Step 1: Add change_pin endpoint**

Read `apps/damage_pwa/damage_pwa/api/auth.py` on the server. It currently has `setup_pin` and `validate_session`. Append a new endpoint to the file:

```python
@frappe.whitelist()
def change_pin(current_pin, new_pin):
    """Change the user's PIN. Requires current PIN for verification."""
    assert_damage_user()

    if not current_pin or not new_pin:
        frappe.throw(_("Current and new PIN required"))

    if not (isinstance(new_pin, str) and new_pin.isdigit() and 4 <= len(new_pin) <= 6):
        frappe.throw(_("PIN must be 4-6 digits"))

    user = frappe.session.user

    # Fetch existing record
    pin_name = frappe.db.get_value("Damage PWA Pin", {"user": user}, "name")
    if not pin_name:
        frappe.throw(_("No PIN set — use setup_pin first"))

    doc = frappe.get_doc("Damage PWA Pin", pin_name)

    # Verify current PIN using bcrypt
    import bcrypt
    if not bcrypt.checkpw(current_pin.encode("utf-8"), doc.pin_hash.encode("utf-8")):
        frappe.throw(_("Current PIN is incorrect"), frappe.AuthenticationError)

    # Hash and store new PIN
    new_hash = bcrypt.hashpw(new_pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    doc.pin_hash = new_hash
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True}
```

Make sure `assert_damage_user` is imported. If the file's top looks like `from damage_pwa.utils import assert_damage_user`, it's already good. If `from frappe import _` isn't imported, add it.

- [ ] **Step 2: Create ChangePinModal.vue**

Create `apps/damage_pwa/frontend/src/components/ChangePinModal.vue`:

```vue
<template>
  <div v-if="open" class="modal-backdrop" @click.self="close">
    <div class="modal">
      <p class="modal-title">CHANGE PIN</p>
      <p class="modal-hint">{{ hint }}</p>
      <PinPad :key="step" :error="error" @complete="handleComplete" />
      <button class="btn-ghost full" @click="close">CANCEL</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import PinPad from "@/components/PinPad.vue";
import { call } from "@/utils/frappe.js";
import { useToastStore } from "@/store/toast.js";

const props = defineProps({
  open: { type: Boolean, default: false },
});
const emit = defineEmits(["close"]);

const toast = useToastStore();

const step = ref("current");  // "current" | "new" | "confirm"
const currentPin = ref("");
const newPin = ref("");
const error = ref("");

const hint = computed(() => {
  if (step.value === "current") return "Enter your current PIN";
  if (step.value === "new") return "Enter a new 4-digit PIN";
  if (step.value === "confirm") return "Confirm new PIN";
  return "";
});

watch(() => props.open, (val) => {
  if (val) {
    step.value = "current";
    currentPin.value = "";
    newPin.value = "";
    error.value = "";
  }
});

async function handleComplete(pin) {
  error.value = "";
  if (step.value === "current") {
    currentPin.value = pin;
    step.value = "new";
    return;
  }
  if (step.value === "new") {
    newPin.value = pin;
    step.value = "confirm";
    return;
  }
  if (step.value === "confirm") {
    if (pin !== newPin.value) {
      error.value = "PINs don't match";
      step.value = "new";
      newPin.value = "";
      return;
    }
    try {
      await call("damage_pwa.api.auth.change_pin", {
        current_pin: currentPin.value,
        new_pin: newPin.value,
      });
      toast.success("PIN changed successfully");
      close();
    } catch (e) {
      if (String(e.message || "").toLowerCase().includes("incorrect")) {
        error.value = "Current PIN is incorrect";
        step.value = "current";
        currentPin.value = "";
      } else {
        error.value = e.message || "Failed to change PIN";
      }
    }
  }
}

function close() {
  emit("close");
}
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
  padding: 16px;
}

.modal {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px 16px;
  width: 100%;
  max-width: 400px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}

.modal-title {
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 2px;
}

.modal-hint {
  font-size: 12px;
  color: var(--text-dim);
  letter-spacing: 0.5px;
}

.full { width: 100%; height: 44px; }
</style>
```

- [ ] **Step 3: Commit (no build needed yet, rolled into Task 3)**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa && sudo -u v15 git add -A && sudo -u v15 git commit -m "feat: add change_pin API + ChangePinModal

Server endpoint verifies current PIN with bcrypt, rehashes new PIN.
Modal steps through: current PIN → new PIN → confirm.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Full Settings View

**Files:**
- Modify: `frontend/src/views/SettingsView.vue` (rewrite)

- [ ] **Step 1: Replace SettingsView.vue**

Replace the entire contents of `apps/damage_pwa/frontend/src/views/SettingsView.vue` with:

```vue
<template>
  <div class="page">
    <h2 class="page-title">SETTINGS</h2>

    <div class="section">
      <p class="label">ACCOUNT</p>
      <div class="card">
        <div class="info-row"><span class="k">USER</span><span>{{ auth.fullName || auth.user }}</span></div>
        <div class="info-row"><span class="k">EMAIL</span><span>{{ auth.user }}</span></div>
      </div>
      <button class="btn-ghost full" @click="showChangePin = true">CHANGE PIN</button>
    </div>

    <div class="section">
      <p class="label">SYNC</p>
      <div class="card">
        <div class="info-row"><span class="k">LAST SYNC</span><span>{{ lastSyncText }}</span></div>
        <div class="info-row"><span class="k">PENDING</span><span>{{ sync.pendingTotal }}</span></div>
        <div v-if="sync.pendingPhotos" class="info-row"><span class="k">PHOTOS</span><span>{{ sync.pendingPhotos }}</span></div>
        <div v-if="sync.pendingInspections" class="info-row"><span class="k">INSPECTIONS</span><span>{{ sync.pendingInspections }}</span></div>
        <div v-if="sync.pendingActions" class="info-row"><span class="k">APPROVALS</span><span>{{ sync.pendingActions }}</span></div>
      </div>
      <button
        class="btn-primary full"
        :disabled="sync.draining || !online"
        @click="forceSync"
      >
        {{ sync.draining ? "SYNCING..." : "FORCE SYNC" }}
      </button>
    </div>

    <div class="section">
      <p class="label">STORAGE</p>
      <div class="card">
        <div class="info-row"><span class="k">USAGE</span><span>{{ storageText }}</span></div>
      </div>
      <button class="btn-ghost full" @click="confirmClearCache">CLEAR CACHE</button>
    </div>

    <div class="section">
      <p class="label">APP INFO</p>
      <div class="card">
        <div class="info-row"><span class="k">VERSION</span><span>{{ version }}</span></div>
        <div class="info-row"><span class="k">SERVER</span><span>{{ serverHost }}</span></div>
      </div>
    </div>

    <button class="btn-danger full" @click="handleLogout">LOGOUT</button>

    <ChangePinModal :open="showChangePin" @close="showChangePin = false" />

    <!-- Clear cache confirmation -->
    <div v-if="showClearConfirm" class="modal-backdrop" @click.self="showClearConfirm = false">
      <div class="modal">
        <p class="modal-title">CLEAR CACHE?</p>
        <p class="modal-hint">This removes all cached transfers, supplier codes, and queued photos. Unsent changes will be lost. Continue?</p>
        <div class="modal-actions">
          <button class="btn-ghost full" @click="showClearConfirm = false">CANCEL</button>
          <button class="btn-danger full" @click="handleClearCache">CLEAR</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/store/auth.js";
import { useSyncStore } from "@/store/sync.js";
import { useToastStore } from "@/store/toast.js";
import { useOnline } from "@/utils/online.js";
import * as db from "@/utils/db.js";
import ChangePinModal from "@/components/ChangePinModal.vue";

const router = useRouter();
const auth = useAuthStore();
const sync = useSyncStore();
const toast = useToastStore();
const online = useOnline();

const showChangePin = ref(false);
const showClearConfirm = ref(false);

const version = "0.5.0 · phase-5";
const serverHost = window.location.host;

const storageBytes = ref(0);

const storageText = computed(() => {
  const b = storageBytes.value;
  if (!b) return "—";
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(1)} MB`;
});

const lastSyncText = computed(() => {
  if (!sync.lastSyncAt) return "NEVER";
  return relativeTime(sync.lastSyncAt);
});

onMounted(async () => {
  sync.refreshCounts();
  if (navigator.storage?.estimate) {
    try {
      const est = await navigator.storage.estimate();
      storageBytes.value = est.usage || 0;
    } catch { /* ignore */ }
  }
});

async function forceSync() {
  const result = await sync.drain();
  if (result?.hasErrors) {
    toast.error("Some items failed to sync — check queues");
  } else if (sync.pendingTotal === 0) {
    toast.success("All synced");
  }
}

function confirmClearCache() {
  showClearConfirm.value = true;
}

async function handleClearCache() {
  showClearConfirm.value = false;
  await db.clearAll();
  await sync.refreshCounts();
  toast.success("Cache cleared");
}

async function handleLogout() {
  await auth.logout();
  router.replace("/login");
}

function relativeTime(iso) {
  const then = new Date(iso).getTime();
  const diff = Math.floor((Date.now() - then) / 1000);
  if (diff < 60) return "JUST NOW";
  if (diff < 3600) return `${Math.floor(diff / 60)} MIN AGO`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} H AGO`;
  return new Date(iso).toLocaleDateString();
}
</script>

<style scoped>
.section {
  margin-bottom: 20px;
}

.label {
  font-size: 10px;
  letter-spacing: 2px;
  color: var(--amber);
  text-transform: uppercase;
  margin-bottom: 8px;
  font-weight: 600;
}

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 16px;
  margin-bottom: 8px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  font-size: 12px;
}

.info-row:last-child { border-bottom: none; }

.info-row .k {
  color: var(--text-dim);
  font-size: 10px;
  letter-spacing: 1.5px;
}

.full {
  width: 100%;
  height: 44px;
}

button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

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
  padding-bottom: max(20px, env(safe-area-inset-bottom));
}

.modal-title {
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 2px;
  margin-bottom: 8px;
}

.modal-hint {
  font-size: 12px;
  color: var(--text-dim);
  line-height: 1.5;
  margin-bottom: 16px;
}

.modal-actions {
  display: flex;
  gap: 8px;
}

.modal-actions .full {
  flex: 1;
}
</style>
```

- [ ] **Step 2: Build + Deploy**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa/frontend && sudo -u v15 yarn build
cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 clear-cache && sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web
```

- [ ] **Step 3: Verify manually**

- Tap SETTINGS in bottom nav
- Expected: Account card with user info, Sync card with counts + Force Sync button, Storage card + Clear Cache, App Info, Logout
- Tap CHANGE PIN → 3-step modal, fills PinPad correctly, success toast on change
- Tap FORCE SYNC (when online) → spinner → "All synced" toast
- Tap CLEAR CACHE → confirmation modal → confirms → toast

- [ ] **Step 4: Commit**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa && sudo -u v15 git add -A && sudo -u v15 git commit -m "feat: full Settings view

Account (CHANGE PIN), Sync (counts + FORCE SYNC), Storage (usage + CLEAR CACHE),
App Info, Logout. Uses storage.estimate() for usage display.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Pull-to-Refresh on Dashboard

**Files:**
- Create: `frontend/src/composables/usePullRefresh.js`
- Modify: `frontend/src/views/DashboardView.vue`

- [ ] **Step 1: Create usePullRefresh composable**

Create `apps/damage_pwa/frontend/src/composables/usePullRefresh.js`:

```javascript
import { ref, onMounted, onBeforeUnmount } from "vue";

const TRIGGER_DISTANCE = 70;   // px below start before fire
const MAX_DISTANCE = 120;       // max visual stretch

/**
 * Adds pull-to-refresh gesture handling to the window/document.
 * Only activates when scrollTop is 0 and user drags down.
 *
 * @param {() => Promise<void>} onRefresh callback
 */
export function usePullRefresh(onRefresh) {
  const pulling = ref(false);
  const distance = ref(0);
  const refreshing = ref(false);

  let startY = 0;
  let currentY = 0;
  let active = false;

  function onTouchStart(e) {
    if (refreshing.value) return;
    if ((document.scrollingElement || document.documentElement).scrollTop > 0) return;
    startY = e.touches[0].clientY;
    active = true;
  }

  function onTouchMove(e) {
    if (!active) return;
    currentY = e.touches[0].clientY;
    const diff = currentY - startY;
    if (diff < 0) { active = false; pulling.value = false; return; }
    // Prevent default to block native overscroll
    e.preventDefault();
    distance.value = Math.min(MAX_DISTANCE, diff * 0.5);
    pulling.value = distance.value > 0;
  }

  async function onTouchEnd() {
    if (!active) return;
    active = false;
    if (distance.value >= TRIGGER_DISTANCE && !refreshing.value) {
      refreshing.value = true;
      try {
        await onRefresh();
      } catch { /* swallow — caller can toast */ }
      refreshing.value = false;
    }
    distance.value = 0;
    pulling.value = false;
  }

  onMounted(() => {
    document.addEventListener("touchstart", onTouchStart, { passive: true });
    document.addEventListener("touchmove", onTouchMove, { passive: false });
    document.addEventListener("touchend", onTouchEnd, { passive: true });
  });

  onBeforeUnmount(() => {
    document.removeEventListener("touchstart", onTouchStart);
    document.removeEventListener("touchmove", onTouchMove);
    document.removeEventListener("touchend", onTouchEnd);
  });

  return { pulling, distance, refreshing };
}
```

- [ ] **Step 2: Wire up in DashboardView.vue**

Read `apps/damage_pwa/frontend/src/views/DashboardView.vue`. In the `<script setup>`, add import:

```javascript
import { usePullRefresh } from "@/composables/usePullRefresh.js";
```

Add hook at the bottom of the setup block, after `onMounted`:

```javascript
const { pulling, distance, refreshing } = usePullRefresh(async () => {
  await Promise.all([
    store.fetchPending(),
    store.fetchKpis(),
  ]);
});
```

In the `<template>`, insert a pull indicator at the top of the `.page` div (as the first child, before `.dash-header`):

```html
    <div
      v-show="pulling || refreshing"
      class="pull-indicator"
      :style="{ height: `${Math.max(distance, refreshing ? 40 : 0)}px` }"
    >
      <span class="spinner" :class="{ spinning: refreshing }"></span>
      <span class="pull-text">{{ refreshing ? 'REFRESHING...' : (distance >= 70 ? 'RELEASE TO REFRESH' : 'PULL TO REFRESH') }}</span>
    </div>
```

Add CSS at the end of `<style scoped>`:

```css
.pull-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  overflow: hidden;
  transition: height 0.1s;
  color: var(--text-dim);
  font-size: 10px;
  letter-spacing: 1.5px;
  text-transform: uppercase;
}

.pull-indicator .spinner {
  width: 14px;
  height: 14px;
  border: 2px solid var(--border);
  border-top-color: var(--amber);
  border-radius: 50%;
}

.pull-indicator .spinner.spinning {
  animation: spin 0.8s linear infinite;
}
```

(The `@keyframes spin` already exists in the file.)

- [ ] **Step 3: Build + Deploy**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa/frontend && sudo -u v15 yarn build
cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 clear-cache && sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web
```

- [ ] **Step 4: Verify manually**

On mobile (or Chrome mobile emulation):
- Scroll to top of Dashboard
- Drag finger down → pull indicator appears
- At ≥70px threshold → "RELEASE TO REFRESH"
- Release → spinner spins → data refetches → spinner disappears

- [ ] **Step 5: Commit**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa && sudo -u v15 git add -A && sudo -u v15 git commit -m "feat: pull-to-refresh on Dashboard

usePullRefresh composable handles touchstart/move/end,
activates only when scrollTop is 0 and user drags down.
70px trigger threshold, 120px max stretch.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Digital Asset Links + TWA Project Scaffold

**Files:**
- Create: `damage_pwa/damage_pwa/www/.well-known/assetlinks.json` (empty for now — populated after signing)
- Create: `damage_pwa/damage_pwa/www/.well-known/__init__.py` (empty, just marks directory as Python package)
- Create: `android/` directory structure (local only — not on server)

**Note:** The APK build happens locally on macOS, not on the server. The server only needs to serve `assetlinks.json` once we have a signing fingerprint.

- [ ] **Step 1: Create assetlinks placeholder on server**

On the server, create the `.well-known` directory and a placeholder file. This reserves the URL — the content will be updated in Step 8 after generating the signing keystore.

```bash
sudo -u v15 mkdir -p /home/v15/frappe-bench/apps/damage_pwa/damage_pwa/www/.well-known
sudo -u v15 tee /home/v15/frappe-bench/apps/damage_pwa/damage_pwa/www/.well-known/assetlinks.json > /dev/null <<'JSONEOF'
[]
JSONEOF
sudo -u v15 touch /home/v15/frappe-bench/apps/damage_pwa/damage_pwa/www/.well-known/__init__.py
```

Deploy:

```bash
cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 clear-cache && sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web
```

Verify: `curl -s https://rmax-dev.fateherp.com/.well-known/assetlinks.json` returns `[]`.

- [ ] **Step 2: Scaffold Android project locally**

On the local machine (not the server), in the Damage PWA's working directory — we'll create this in a new local folder since it's not on the server. For context we'll use `/Users/sayanthns/Documents/RMAX/damage-pwa-android/`.

Create `/Users/sayanthns/Documents/RMAX/damage-pwa-android/build.gradle`:

```gradle
buildscript {
    ext.kotlin_version = '1.9.22'
    repositories {
        google()
        mavenCentral()
    }
    dependencies {
        classpath 'com.android.tools.build:gradle:8.3.0'
        classpath "org.jetbrains.kotlin:kotlin-gradle-plugin:$kotlin_version"
    }
}

allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

task clean(type: Delete) {
    delete rootProject.buildDir
}
```

Create `settings.gradle`:

```gradle
rootProject.name = 'DamagePWA'
include ':app'
```

Create `gradle.properties`:

```properties
org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
android.useAndroidX=true
android.enableJetifier=false
kotlin.code.style=official
```

Create `gradle/wrapper/gradle-wrapper.properties`:

```properties
distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\://services.gradle.org/distributions/gradle-8.6-bin.zip
networkTimeout=10000
validateDistributionUrl=true
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
```

Create `app/build.gradle`:

```gradle
apply plugin: 'com.android.application'
apply plugin: 'kotlin-android'

android {
    namespace 'com.rmax.damage_pwa'
    compileSdk 34

    defaultConfig {
        applicationId 'com.rmax.damage_pwa'
        minSdk 21
        targetSdk 34
        versionCode 1
        versionName '0.5.0'

        manifestPlaceholders = [
            hostName: 'rmax-dev.fateherp.com',
            defaultUrl: 'https://rmax-dev.fateherp.com/damage-pwa/',
            launcherName: 'Damage PWA',
            assetStatements: '[{ "relation": ["delegate_permission/common.handle_all_urls"], "target": {"namespace": "web", "site": "https://rmax-dev.fateherp.com"}}]'
        ]
    }

    signingConfigs {
        release {
            storeFile file('../keystore/damage-pwa.keystore')
            storePassword System.getenv('KEYSTORE_PASSWORD') ?: 'changeit'
            keyAlias System.getenv('KEY_ALIAS') ?: 'damage-pwa'
            keyPassword System.getenv('KEY_PASSWORD') ?: 'changeit'
        }
    }

    buildTypes {
        release {
            minifyEnabled false
            signingConfig signingConfigs.release
        }
        debug {
            applicationIdSuffix '.debug'
            versionNameSuffix '-debug'
        }
    }

    compileOptions {
        sourceCompatibility JavaVersion.VERSION_17
        targetCompatibility JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = '17'
    }
}

dependencies {
    implementation 'androidx.browser:browser:1.8.0'
    implementation 'com.google.androidbrowserhelper:androidbrowserhelper:2.5.0'
}
```

Create `app/src/main/AndroidManifest.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <uses-permission android:name="android.permission.INTERNET"/>

    <application
        android:allowBackup="false"
        android:label="${launcherName}"
        android:icon="@mipmap/ic_launcher"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:supportsRtl="true"
        android:theme="@android:style/Theme.Translucent.NoTitleBar">

        <meta-data
            android:name="asset_statements"
            android:resource="@string/asset_statements"/>

        <activity
            android:name="com.google.androidbrowserhelper.trusted.LauncherActivity"
            android:alwaysRetainTaskState="true"
            android:label="${launcherName}"
            android:exported="true">

            <meta-data
                android:name="android.support.customtabs.trusted.DEFAULT_URL"
                android:value="${defaultUrl}"/>

            <meta-data
                android:name="android.support.customtabs.trusted.STATUS_BAR_COLOR"
                android:resource="@color/colorPrimary"/>

            <meta-data
                android:name="android.support.customtabs.trusted.NAVIGATION_BAR_COLOR"
                android:resource="@color/navigationColor"/>

            <meta-data
                android:name="android.support.customtabs.trusted.SCREEN_ORIENTATION"
                android:value="portrait"/>

            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>

            <intent-filter android:autoVerify="true">
                <action android:name="android.intent.action.VIEW"/>
                <category android:name="android.intent.category.DEFAULT"/>
                <category android:name="android.intent.category.BROWSABLE"/>
                <data
                    android:scheme="https"
                    android:host="${hostName}"
                    android:path="/damage-pwa/"/>
            </intent-filter>

        </activity>

    </application>

</manifest>
```

Create `app/src/main/res/values/colors.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="colorPrimary">#0a0a0a</color>
    <color name="navigationColor">#0a0a0a</color>
</resources>
```

Create `app/src/main/res/values/strings.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">Damage PWA</string>
    <string name="asset_statements">
        [{ \"relation\": [\"delegate_permission/common.handle_all_urls\"],
           \"target\": {\"namespace\": \"web\", \"site\": \"https://rmax-dev.fateherp.com\"}}]
    </string>
</resources>
```

Create `app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/colorPrimary"/>
    <foreground android:drawable="@mipmap/ic_launcher_foreground"/>
</adaptive-icon>
```

Create `app/src/main/res/mipmap-anydpi-v26/ic_launcher_round.xml` (same content).

For the foreground icon, copy the 512px PWA icon from the server to `app/src/main/res/mipmap-xxxhdpi/ic_launcher_foreground.png` (432x432 pixel density for adaptive). If adaptive icons are too complex, use legacy icons across all densities: copy the PWA 192px icon to each of `mipmap-mdpi/ic_launcher.png`, `mipmap-hdpi/ic_launcher.png`, `mipmap-xhdpi/ic_launcher.png`, `mipmap-xxhdpi/ic_launcher.png`, `mipmap-xxxhdpi/ic_launcher.png`.

Create `app/src/main/java/com/rmax/damage_pwa/.gitkeep` (no custom activity needed — we use the library's `LauncherActivity`).

Create `keystore/.gitignore`:

```
*.keystore
*.jks
```

Create `README.md`:

```markdown
# Damage PWA Android TWA

Sideloadable Android APK wrapping the Damage PWA via Trusted Web Activity.

## Prerequisites (macOS)

```bash
brew install --cask android-commandlinetools
brew install openjdk@17

export JAVA_HOME=$(/usr/libexec/java_home -v 17)
export ANDROID_HOME=$HOME/Library/Android/sdk
mkdir -p $ANDROID_HOME
sdkmanager --sdk_root=$ANDROID_HOME "platform-tools" "platforms;android-34" "build-tools;34.0.0"
```

## One-time: Generate Keystore

```bash
mkdir -p keystore
keytool -genkey -v \
  -keystore keystore/damage-pwa.keystore \
  -alias damage-pwa \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -storepass changeit -keypass changeit \
  -dname "CN=RMAX, O=RMAX, L=Jeddah, S=Saudi Arabia, C=SA"
```

**IMPORTANT:** Back up this keystore immediately. Losing it means you cannot update the APK.

## Get SHA-256 Fingerprint (for assetlinks.json)

```bash
keytool -list -v -keystore keystore/damage-pwa.keystore -alias damage-pwa -storepass changeit | grep SHA256
```

Copy the fingerprint value, then update the server's
`apps/damage_pwa/damage_pwa/www/.well-known/assetlinks.json`:

```json
[{
  "relation": ["delegate_permission/common.handle_all_urls"],
  "target": {
    "namespace": "android_app",
    "package_name": "com.rmax.damage_pwa",
    "sha256_cert_fingerprints": ["<fingerprint>"]
  }
}]
```

## Build

```bash
# Debug
./gradlew assembleDebug
# Output: app/build/outputs/apk/debug/app-debug.apk

# Release (requires keystore)
KEYSTORE_PASSWORD=changeit KEY_PASSWORD=changeit ./gradlew assembleRelease
# Output: app/build/outputs/apk/release/app-release.apk
```

## Install

```bash
adb install -r app/build/outputs/apk/release/app-release.apk
```

Or share the APK file directly; users enable "Install from unknown sources" on their device.
```

Create `.gitignore` at the android root:

```
.gradle/
build/
app/build/
local.properties
*.iml
.idea/
keystore/*.keystore
keystore/*.jks
```

Also create gradlew wrapper. Use:

```bash
cd /Users/sayanthns/Documents/RMAX/damage-pwa-android
# Download gradle-wrapper.jar if missing
mkdir -p gradle/wrapper
curl -L -o gradle/wrapper/gradle-wrapper.jar \
  https://raw.githubusercontent.com/gradle/gradle/v8.6.0/gradle/wrapper/gradle-wrapper.jar
# Create gradlew script
cat > gradlew <<'SH'
#!/usr/bin/env sh
DIR="$(cd "$(dirname "$0")" && pwd)"
java -jar "$DIR/gradle/wrapper/gradle-wrapper.jar" "$@"
SH
chmod +x gradlew
```

Note: This minimal gradlew is a simplification; a full wrapper also parses `gradle-wrapper.properties` to fetch the distribution. For a proper wrapper, once you have gradle installed locally via brew (`brew install gradle`), run `gradle wrapper --gradle-version 8.6` in the android dir to generate a correct `gradlew` and `gradlew.bat`.

- [ ] **Step 3: Commit Android project (to RMAX-Custom repo)**

The Android project lives outside the damage_pwa Frappe app. Add to the RMAX-Custom repo:

```bash
# Inside /Users/sayanthns/Documents/RMAX-Custom (if the user wants to keep it with their main docs)
# OR a standalone repo — user's choice.
# For now, commit android/ to the damage_pwa repo's separate branch or sibling dir.
```

For this plan, we'll simply document that `/Users/sayanthns/Documents/RMAX/damage-pwa-android/` exists and is a standalone project. User can initialize its own git repo if they want:

```bash
cd /Users/sayanthns/Documents/RMAX/damage-pwa-android
git init
git add -A
git commit -m "chore: scaffold TWA wrapper for Damage PWA

AndroidManifest with LauncherActivity, Gradle config targeting SDK 34,
adaptive launcher icons, assetlinks meta-data pointing to
https://rmax-dev.fateherp.com.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 6: Build APK + Populate assetlinks.json

**Files:**
- Modify: `damage_pwa/damage_pwa/www/.well-known/assetlinks.json` (final content)

- [ ] **Step 1: Generate keystore locally**

```bash
cd /Users/sayanthns/Documents/RMAX/damage-pwa-android
mkdir -p keystore
keytool -genkey -v \
  -keystore keystore/damage-pwa.keystore \
  -alias damage-pwa \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -storepass changeit -keypass changeit \
  -dname "CN=RMAX, O=RMAX, L=Jeddah, S=Saudi Arabia, C=SA"
```

**BACK UP THIS KEYSTORE TO A SAFE LOCATION (password manager, 1Password, etc.).**

- [ ] **Step 2: Get fingerprint**

```bash
keytool -list -v -keystore keystore/damage-pwa.keystore -alias damage-pwa -storepass changeit | grep -A1 "SHA256" | head -2
```

Copy the SHA256 fingerprint (format: `AA:BB:CC:...`).

- [ ] **Step 3: Update assetlinks.json on server**

Replace the placeholder with the real content. Let `FINGERPRINT` be the value from Step 2:

```bash
FINGERPRINT="<paste here>"
sudo -u v15 tee /home/v15/frappe-bench/apps/damage_pwa/damage_pwa/www/.well-known/assetlinks.json > /dev/null <<JSONEOF
[{
  "relation": ["delegate_permission/common.handle_all_urls"],
  "target": {
    "namespace": "android_app",
    "package_name": "com.rmax.damage_pwa",
    "sha256_cert_fingerprints": ["$FINGERPRINT"]
  }
}]
JSONEOF
cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 clear-cache && sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web
```

Verify: `curl -s https://rmax-dev.fateherp.com/.well-known/assetlinks.json` returns the JSON with fingerprint.

- [ ] **Step 4: Build debug APK first**

```bash
cd /Users/sayanthns/Documents/RMAX/damage-pwa-android
./gradlew assembleDebug
# Look for: BUILD SUCCESSFUL
# Output at: app/build/outputs/apk/debug/app-debug.apk
```

- [ ] **Step 5: Install on test device**

Plug in Android device with USB debugging enabled, or use an emulator:

```bash
adb devices
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Launch the app. Expected: opens full-screen (no URL bar) directly to the Damage PWA login. If the URL bar appears, check DevTools (chrome://inspect) for DAL validation errors — usually means fingerprint mismatch.

- [ ] **Step 6: Build release APK**

```bash
KEYSTORE_PASSWORD=changeit KEY_PASSWORD=changeit ./gradlew assembleRelease
# Output: app/build/outputs/apk/release/app-release.apk
```

- [ ] **Step 7: Rename + distribute**

```bash
cp app/build/outputs/apk/release/app-release.apk damage-pwa-v0.5.0.apk
```

Share the file via:
- Google Drive / Dropbox link
- Internal Slack channel
- Direct file transfer

Users enable "Install from unknown sources" (Settings → Security → Unknown sources, or per-app permission on Android 8+) and open the APK.

- [ ] **Step 8: Commit server-side assetlinks update**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa && sudo -u v15 git add -A && sudo -u v15 git commit -m "chore: finalize assetlinks.json with TWA signing fingerprint

Links rmax-dev.fateherp.com to com.rmax.damage_pwa via SHA-256 cert.
Required for Trusted Web Activity to run full-screen (no URL bar).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Phase 5 Checkpoint

After completing all 6 tasks, verify:

### Web polish
| Test | Method | Expected |
|------|--------|----------|
| Toast success | Approve a transfer | Green-bordered toast "Transfer approved" |
| Toast error | Trigger an API error | Red-bordered toast with message |
| Toast warn | Approve with flagged items | Amber toast "Approved with warnings: ..." |
| Change PIN flow | Settings → CHANGE PIN → enter wrong current | Returns to first step with "Current PIN is incorrect" |
| Change PIN success | Enter correct current → new → confirm | Success toast, modal closes |
| Force sync | Settings → FORCE SYNC | Spinner → "All synced" toast |
| Clear cache | Settings → CLEAR CACHE → confirm | Cache cleared, sync counts zero |
| Storage estimate | Settings view | Shows "X.X MB" under Storage |
| Pull-to-refresh | Dashboard → drag down | Pull indicator appears, releases triggers refetch |

### Android TWA
| Test | Method | Expected |
|------|--------|----------|
| Keystore generated | `ls keystore/damage-pwa.keystore` | File exists |
| Fingerprint retrieved | keytool output | SHA256 AA:BB:CC:... |
| assetlinks.json valid | `curl https://rmax-dev.fateherp.com/.well-known/assetlinks.json` | JSON with fingerprint |
| Debug APK builds | `./gradlew assembleDebug` | BUILD SUCCESSFUL |
| APK installs | `adb install -r ...` | Success |
| App opens full-screen | Launch on device | No URL bar, direct to PWA login |
| Release APK builds | `./gradlew assembleRelease` | BUILD SUCCESSFUL |
| APK signed | `jarsigner -verify app-release.apk` | "jar verified" |

**End state:** All 5 phases complete. The Damage PWA is:
- Web: installable, offline-capable, full inspection workflow with photos
- Android: sideloadable as APK, full-screen TWA experience
- Server: API + workflow integration complete, lock + concurrency + audit trail working
