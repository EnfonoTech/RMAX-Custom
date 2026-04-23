# Damage PWA Phase 4: Offline Engine (IndexedDB Queue + Service Worker + Sync)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the inspection flow work fully offline. Users can open transfers, save inspections, capture photos, and queue approvals with no network — all actions persist to IndexedDB and sync when connection returns.

**Architecture:** Every write operation (save_item_inspection, approve, reject, photo upload) routes through a write-through queue: the UI updates local IndexedDB immediately, then a background sync engine drains queued operations to the server. Photos are stored as Blobs in IndexedDB until uploaded. A Service Worker caches static assets and provides the PWA install experience.

**Tech Stack:** Same as Phase 3 (no new npm deps). Uses Background Sync API where supported, falls back to `visibilitychange` + `online` event listeners.

**Spec:** `docs/superpowers/specs/2026-04-16-damage-pwa-design.md` (section 6 — Offline Architecture, section 2.2 — Sync Bar)

**Depends on:** Phases 1-3 deployed.

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
│   ├── public/
│   │   └── js/
│   │       └── sw.js                 # NEW — Service Worker (cache + lifecycle)
│   ├── api/
│   │   └── pwa.py                    # NEW — serve SW with proper headers
│   └── hooks.py                      # MODIFY — add website_route_rules for SW
└── frontend/src/
    ├── store/
    │   ├── sync.js                   # NEW — queue state + drain orchestration
    │   └── inspection.js             # MODIFY — write to local before API
    ├── utils/
    │   ├── sync-engine.js            # NEW — drain loop + retry/backoff
    │   ├── photo.js                  # MODIFY — offline-first photo queue
    │   └── online.js                 # NEW — reactive online state composable
    ├── components/
    │   └── SyncBar.vue               # MODIFY — show queue counts + forced sync
    └── main.js                       # MODIFY — register SW + start sync engine
```

---

### Task 1: Service Worker + Registration

**Files:**
- Create: `damage_pwa/public/js/sw.js`
- Create: `damage_pwa/damage_pwa/api/pwa.py`
- Modify: `damage_pwa/damage_pwa/hooks.py`
- Modify: `frontend/src/main.js`

- [ ] **Step 1: Create the Service Worker**

Create `apps/damage_pwa/damage_pwa/public/js/sw.js`:

```javascript
// Damage PWA Service Worker
const SW_VERSION = "v1-2026-04-16";
const STATIC_CACHE = `damage-pwa-static-${SW_VERSION}`;
const ASSET_PREFIX = "/assets/damage_pwa/";
const APP_SCOPE = "/damage-pwa/";

const PRECACHE_URLS = [
  "/assets/damage_pwa/manifest.json",
];

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(PRECACHE_URLS).catch(() => {}))
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k.startsWith("damage-pwa-") && k !== STATIC_CACHE)
          .map((k) => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Only handle same-origin
  if (url.origin !== self.location.origin) return;

  // Never cache POST/PUT/DELETE
  if (req.method !== "GET") return;

  // Static assets: cache-first with network fallback + background update
  if (url.pathname.startsWith(ASSET_PREFIX)) {
    event.respondWith(cacheFirst(req));
    return;
  }

  // SPA entry HTML: network-first, fallback to cached HTML
  if (url.pathname.startsWith(APP_SCOPE)) {
    event.respondWith(networkFirst(req));
    return;
  }

  // API calls: network-first (GET only), no cache on failure for now
  // (write operations are handled by the app's sync queue, not SW)
});

async function cacheFirst(req) {
  const cache = await caches.open(STATIC_CACHE);
  const cached = await cache.match(req);
  if (cached) {
    // Revalidate in background
    fetch(req).then((r) => {
      if (r.ok) cache.put(req, r.clone());
    }).catch(() => {});
    return cached;
  }
  const resp = await fetch(req);
  if (resp.ok) cache.put(req, resp.clone());
  return resp;
}

async function networkFirst(req) {
  const cache = await caches.open(STATIC_CACHE);
  try {
    const resp = await fetch(req);
    if (resp.ok) cache.put(req, resp.clone());
    return resp;
  } catch {
    const cached = await cache.match(req);
    if (cached) return cached;
    throw new Error("Offline and no cached HTML");
  }
}

// Background Sync hook — app triggers via sw.sync.register("sync-damage-pwa")
self.addEventListener("sync", (event) => {
  if (event.tag === "sync-damage-pwa") {
    event.waitUntil(
      self.clients.matchAll({ includeUncontrolled: true }).then((clients) => {
        clients.forEach((c) => c.postMessage({ type: "SYNC_REQUEST" }));
      })
    );
  }
});

// Message-based drain trigger from app
self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") self.skipWaiting();
});
```

- [ ] **Step 2: Create SW-serving endpoint**

Create `apps/damage_pwa/damage_pwa/api/pwa.py`:

```python
import os
import frappe


@frappe.whitelist(allow_guest=True)
def sw():
    """Serve the service worker with Service-Worker-Allowed header set to app scope."""
    sw_path = frappe.get_app_path("damage_pwa", "public", "js", "sw.js")
    with open(sw_path, "r") as f:
        content = f.read()

    frappe.local.response.filename = "sw.js"
    frappe.local.response.filecontent = content.encode("utf-8")
    frappe.local.response.type = "download"
    frappe.local.response.headers["Content-Type"] = "application/javascript"
    frappe.local.response.headers["Service-Worker-Allowed"] = "/damage-pwa/"
    frappe.local.response.headers["Cache-Control"] = "no-cache"
```

- [ ] **Step 3: Add SW header utility**

Read `apps/damage_pwa/damage_pwa/utils.py` on the server. Add to the file (append):

```python
def add_sw_headers(response):
    """Add Service-Worker-Allowed header for SW fetches (idempotent)."""
    try:
        path = frappe.local.request.path
    except Exception:
        return response
    if path and ("/sw" in path or "sw.js" in path):
        response.headers["Service-Worker-Allowed"] = "/damage-pwa/"
    return response
```

The import `import frappe` is likely already there; if not, add it at the top.

- [ ] **Step 4: Update hooks.py**

Read `apps/damage_pwa/damage_pwa/hooks.py` on the server. Add/ensure these lines exist:

```python
# After existing website_route_rules
website_route_rules += [
    {"from_route": "/sw.js", "to_route": "api/method/damage_pwa.api.pwa.sw"},
]

# after_request hook for SW header — merge with existing if any
after_request = ["damage_pwa.utils.add_sw_headers"]
```

If `website_route_rules` is already a list with the SPA rule, append the SW rule to it. If `after_request` already exists, combine into a list.

- [ ] **Step 5: Register SW in main.js**

Read `apps/damage_pwa/frontend/src/main.js` on the server. It should look like:

```javascript
import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import router from "./router/index.js";
import "./style.css";

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.mount("#app");
```

Replace with:

```javascript
import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import router from "./router/index.js";
import "./style.css";

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.mount("#app");

// Register Service Worker
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/sw.js", { scope: "/damage-pwa/" })
      .then((reg) => {
        console.log("[SW] Registered:", reg.scope);
      })
      .catch((err) => {
        console.warn("[SW] Registration failed:", err);
      });
  });

  // Listen for sync requests from SW
  navigator.serviceWorker.addEventListener("message", async (event) => {
    if (event.data?.type === "SYNC_REQUEST") {
      const { useSyncStore } = await import("./store/sync.js");
      useSyncStore().drain();
    }
  });
}
```

- [ ] **Step 6: Build + Deploy**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa/frontend && sudo -u v15 yarn build
cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 clear-cache && sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web
```

- [ ] **Step 7: Verify manually**

- Visit `https://rmax-dev.fateherp.com/sw.js` — should return the JS content with `Content-Type: application/javascript` and `Service-Worker-Allowed: /damage-pwa/`
- Visit `/damage-pwa/`, open DevTools → Application → Service Workers — should show sw.js registered, scope `/damage-pwa/`
- Note: `sync.js` store doesn't exist yet — the sync-message listener will fail silently (dynamic import failure). That's fine; Task 2 creates it.

- [ ] **Step 8: Commit**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa && sudo -u v15 git add -A && sudo -u v15 git commit -m "feat: add Service Worker + registration

SW caches static assets (cache-first) and SPA entry (network-first).
Listens for Background Sync events and messages them to the app.
Served via /sw.js route with Service-Worker-Allowed: /damage-pwa/ header.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Online Composable + Sync Store + Engine

**Files:**
- Create: `frontend/src/utils/online.js`
- Create: `frontend/src/utils/sync-engine.js`
- Create: `frontend/src/store/sync.js`

- [ ] **Step 1: Create online.js composable**

Create `apps/damage_pwa/frontend/src/utils/online.js`:

```javascript
import { ref, onMounted, onUnmounted } from "vue";

const online = ref(typeof navigator !== "undefined" ? navigator.onLine : true);
let listenersAttached = false;

function handleOnline()  { online.value = true; }
function handleOffline() { online.value = false; }

function ensureListeners() {
  if (listenersAttached || typeof window === "undefined") return;
  window.addEventListener("online", handleOnline);
  window.addEventListener("offline", handleOffline);
  listenersAttached = true;
}

export function useOnline() {
  ensureListeners();
  return online;
}

export function isOnline() {
  ensureListeners();
  return online.value;
}
```

- [ ] **Step 2: Create sync-engine.js**

Create `apps/damage_pwa/frontend/src/utils/sync-engine.js`:

```javascript
import { call, uploadFile } from "@/utils/frappe.js";
import * as db from "@/utils/db.js";

const MAX_ATTEMPTS = 5;
const BACKOFF_MS = [0, 5000, 15000, 45000, 120000, 300000];  // Per attempt

function nowMs() { return Date.now(); }

/**
 * Try to upload a single pending photo blob.
 * On success, returns the file URL. On failure, throws.
 */
async function uploadPhoto(photoRec) {
  const file = new File([photoRec.blob], photoRec.filename || "damage.jpg", {
    type: photoRec.blob.type || "image/jpeg",
  });
  return uploadFile(file);
}

/**
 * Drain all pending photos. For each, upload and update referencing
 * inspection_queue entries with the returned file URL. Delete photo on success.
 */
export async function drainPhotos() {
  const photos = await db.getAll("photos");
  const errors = [];
  for (const p of photos) {
    if (p.nextAttemptAt && p.nextAttemptAt > nowMs()) continue;
    try {
      const fileUrl = await uploadPhoto(p);
      // Update any inspection_queue entries referencing this photo
      const queued = await db.getAll("inspection_queue");
      for (const q of queued) {
        let changed = false;
        for (const slot of ["images", "image_2", "image_3"]) {
          if (q[slot] && q[slot].startsWith("photo:") && q[slot] === `photo:${p.id}`) {
            q[slot] = fileUrl;
            changed = true;
          }
        }
        if (changed) await db.put("inspection_queue", q);
      }
      // Delete the blob
      await db.del("photos", p.id);
    } catch (e) {
      p.attempts = (p.attempts || 0) + 1;
      p.lastError = String(e.message || e);
      p.nextAttemptAt = nowMs() + BACKOFF_MS[Math.min(p.attempts, BACKOFF_MS.length - 1)];
      await db.put("photos", p);
      errors.push({ id: p.id, error: p.lastError });
      if (p.attempts >= MAX_ATTEMPTS) {
        // Surface but keep for manual retry
      }
    }
  }
  return { count: photos.length, errors };
}

/**
 * Process inspection queue. Skip items that still reference unresolved
 * photo: placeholders.
 */
export async function drainInspections() {
  const queued = await db.getAll("inspection_queue");
  const errors = [];
  let sent = 0;

  // Sort by createdAt to process oldest first
  queued.sort((a, b) => (a.createdAt || 0) - (b.createdAt || 0));

  for (const q of queued) {
    if (q.nextAttemptAt && q.nextAttemptAt > nowMs()) continue;

    // Skip if any photo slot still unresolved
    const unresolved = ["images", "image_2", "image_3"].some(
      (slot) => q[slot] && String(q[slot]).startsWith("photo:")
    );
    if (unresolved) continue;

    try {
      await call("damage_pwa.api.inspect.save_item_inspection", {
        transfer_name: q.transferName,
        row_name: q.rowName,
        supplier_code: q.supplier_code,
        damage_category: q.damage_category,
        images: q.images,
        image_2: q.image_2,
        image_3: q.image_3,
        remarks: q.remarks,
        status: q.status || "complete",
        client_modified: q.client_modified,
      });
      await db.del("inspection_queue", q.id);
      sent++;
    } catch (e) {
      q.attempts = (q.attempts || 0) + 1;
      q.lastError = String(e.message || e);
      q.nextAttemptAt = nowMs() + BACKOFF_MS[Math.min(q.attempts, BACKOFF_MS.length - 1)];
      await db.put("inspection_queue", q);
      errors.push({ id: q.id, error: q.lastError });
    }
  }
  return { count: queued.length, sent, errors };
}

/**
 * Process approve/reject action queue.
 */
export async function drainActions() {
  const queued = await db.getAll("action_queue");
  const errors = [];
  let sent = 0;

  queued.sort((a, b) => (a.createdAt || 0) - (b.createdAt || 0));

  for (const q of queued) {
    if (q.nextAttemptAt && q.nextAttemptAt > nowMs()) continue;

    // Wait until no inspection_queue entries remain for this transfer
    const remaining = (await db.getAll("inspection_queue")).filter(
      (i) => i.transferName === q.transferName
    );
    if (remaining.length) continue;

    try {
      if (q.action === "approve") {
        await call("damage_pwa.api.inspect.approve_transfer", {
          name: q.transferName,
          client_modified: q.client_modified,
        });
      } else if (q.action === "reject") {
        await call("damage_pwa.api.inspect.reject_transfer", {
          name: q.transferName,
          reason: q.reason,
          client_modified: q.client_modified,
        });
      }
      await db.del("action_queue", q.id);
      sent++;
    } catch (e) {
      q.attempts = (q.attempts || 0) + 1;
      q.lastError = String(e.message || e);
      q.nextAttemptAt = nowMs() + BACKOFF_MS[Math.min(q.attempts, BACKOFF_MS.length - 1)];
      await db.put("action_queue", q);
      errors.push({ id: q.id, error: q.lastError });
    }
  }
  return { count: queued.length, sent, errors };
}

/**
 * Full drain sequence.
 */
export async function drainAll() {
  const photo = await drainPhotos();
  const insp = await drainInspections();
  const action = await drainActions();
  return {
    photos: photo,
    inspections: insp,
    actions: action,
    hasErrors: photo.errors.length > 0 || insp.errors.length > 0 || action.errors.length > 0,
  };
}
```

- [ ] **Step 3: Create sync store**

Create `apps/damage_pwa/frontend/src/store/sync.js`:

```javascript
import { defineStore } from "pinia";
import * as db from "@/utils/db.js";
import { drainAll } from "@/utils/sync-engine.js";
import { isOnline } from "@/utils/online.js";

export const useSyncStore = defineStore("sync", {
  state: () => ({
    pendingPhotos: 0,
    pendingInspections: 0,
    pendingActions: 0,
    draining: false,
    lastSyncAt: null,
    lastError: null,
  }),

  getters: {
    pendingTotal: (state) =>
      state.pendingPhotos + state.pendingInspections + state.pendingActions,
    hasPending(state) {
      return this.pendingTotal > 0;
    },
  },

  actions: {
    async refreshCounts() {
      const [photos, insp, act] = await Promise.all([
        db.getAll("photos"),
        db.getAll("inspection_queue"),
        db.getAll("action_queue"),
      ]);
      this.pendingPhotos = photos.length;
      this.pendingInspections = insp.length;
      this.pendingActions = act.length;
    },

    async drain() {
      if (this.draining) return;
      if (!isOnline()) return;
      this.draining = true;
      this.lastError = null;
      try {
        const result = await drainAll();
        await this.refreshCounts();
        this.lastSyncAt = new Date().toISOString();
        if (result.hasErrors) {
          this.lastError = "Some items failed to sync";
        }
        return result;
      } catch (e) {
        this.lastError = e.message || String(e);
        throw e;
      } finally {
        this.draining = false;
      }
    },

    async requestBackgroundSync() {
      if (!("serviceWorker" in navigator)) return;
      try {
        const reg = await navigator.serviceWorker.ready;
        if ("sync" in reg) {
          await reg.sync.register("sync-damage-pwa");
        }
      } catch {
        // Background Sync not supported — rely on online/foreground triggers
      }
    },

    startWatchers() {
      // Drain on online
      window.addEventListener("online", () => this.drain());
      // Drain on foreground
      document.addEventListener("visibilitychange", () => {
        if (!document.hidden) this.drain();
      });
      // Initial drain + count refresh
      this.refreshCounts();
      this.drain();
      // Periodic poll every 60s as last-resort
      setInterval(() => {
        if (isOnline() && this.hasPending) this.drain();
      }, 60_000);
    },
  },
});
```

- [ ] **Step 4: Start watchers from App.vue**

Read `apps/damage_pwa/frontend/src/App.vue` on the server. It currently has:

```vue
<script setup>
import { onMounted } from "vue";
import { useAuthStore } from "@/store/auth.js";
import BottomNav from "@/components/BottomNav.vue";
import SyncBar from "@/components/SyncBar.vue";

const auth = useAuthStore();

onMounted(() => {
  auth.init();
});
</script>
```

Replace with:

```vue
<script setup>
import { onMounted, watch } from "vue";
import { useAuthStore } from "@/store/auth.js";
import { useSyncStore } from "@/store/sync.js";
import BottomNav from "@/components/BottomNav.vue";
import SyncBar from "@/components/SyncBar.vue";

const auth = useAuthStore();
const sync = useSyncStore();

onMounted(async () => {
  await auth.init();
  if (auth.isAuthenticated) {
    sync.startWatchers();
  }
});

// Start sync watchers after login
watch(() => auth.isAuthenticated, (val) => {
  if (val) sync.startWatchers();
});
</script>
```

- [ ] **Step 5: Build + Deploy**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa/frontend && sudo -u v15 yarn build
cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 clear-cache && sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web
```

- [ ] **Step 6: Commit**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa && sudo -u v15 git add -A && sudo -u v15 git commit -m "feat: add sync engine + sync store + online composable

Sync engine drains photos → inspections → actions with backoff.
Pinia sync store exposes queue counts + drain trigger.
App.vue starts watchers (online/visibility/periodic) on login.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Photo Queue + Placeholder URLs

**Files:**
- Modify: `frontend/src/utils/photo.js`
- Modify: `frontend/src/components/PhotoSlot.vue`

**Pattern:** PhotoSlot now writes compressed blob to IndexedDB `photos` store immediately and emits a `photo:<uuid>` placeholder URL. The inspection store writes this placeholder into the inspection_queue. The sync engine later uploads the blob and rewrites placeholders to real URLs before sending the inspection to the API.

- [ ] **Step 1: Read current photo.js**

Read `apps/damage_pwa/frontend/src/utils/photo.js` on the server. It currently exports `compressImage`, `compressAndUpload`, `makeThumbnail`.

- [ ] **Step 2: Replace photo.js**

Replace the entire contents of `apps/damage_pwa/frontend/src/utils/photo.js` with:

```javascript
import { uploadFile } from "@/utils/frappe.js";
import * as db from "@/utils/db.js";
import { isOnline } from "@/utils/online.js";

const MAX_DIMENSION = 1280;
const JPEG_QUALITY = 0.7;

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
  canvas.getContext("2d").drawImage(img, 0, 0, width, height);

  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => { blob ? resolve(blob) : reject(new Error("Compression failed")); },
      "image/jpeg",
      JPEG_QUALITY
    );
  });
}

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

/**
 * Online-only: directly upload + return file URL.
 * Kept for places that need immediate URLs (rare).
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
 * Offline-first: compress + persist blob to IndexedDB + return placeholder URL.
 * If online, opportunistically upload immediately and return the real URL.
 * If offline or upload fails, returns a `photo:<uuid>` placeholder.
 * Always stores a thumbnail data URL for immediate preview.
 */
export async function capturePhoto(file) {
  const blob = await compressImage(file);
  const thumb = await makeThumbnail(file);
  const id = genUUID();

  const record = {
    id,
    blob,
    filename: file.name.replace(/\.[^.]+$/, "") + ".jpg",
    thumb,
    createdAt: Date.now(),
    attempts: 0,
  };
  await db.put("photos", record);

  // Try immediate upload if online
  if (isOnline()) {
    try {
      const compressedFile = new File([blob], record.filename, { type: "image/jpeg" });
      const fileUrl = await uploadFile(compressedFile);
      // Success — remove from queue
      await db.del("photos", id);
      return { url: fileUrl, thumb };
    } catch {
      // Fall through to placeholder
    }
  }

  return { url: `photo:${id}`, thumb };
}

/**
 * Resolve a placeholder URL to a thumbnail data URL for preview.
 * If already a real URL, returns it as-is.
 */
export async function resolvePreview(urlOrPlaceholder) {
  if (!urlOrPlaceholder) return null;
  if (!urlOrPlaceholder.startsWith("photo:")) return urlOrPlaceholder;
  const id = urlOrPlaceholder.slice("photo:".length);
  const rec = await db.get("photos", id);
  return rec?.thumb || null;
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

function genUUID() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}
```

- [ ] **Step 3: Update PhotoSlot.vue**

Read `apps/damage_pwa/frontend/src/components/PhotoSlot.vue` on the server. In the `<script setup>` block, find:

```javascript
import { compressAndUpload, makeThumbnail } from "@/utils/photo.js";
```

Replace with:

```javascript
import { capturePhoto, resolvePreview } from "@/utils/photo.js";
import { watch } from "vue";
```

(If `watch` is already imported from "vue" above, just reuse it.)

Find the existing `handleFile` function:

```javascript
async function handleFile(e) {
  const file = e.target.files?.[0];
  e.target.value = "";
  if (!file) return;

  uploading.value = true;
  error.value = "";
  try {
    localThumb.value = await makeThumbnail(file);
    const fileUrl = await compressAndUpload(file);
    emit("update:modelValue", fileUrl);
  } catch (err) {
    error.value = err.message || "Upload failed";
    localThumb.value = null;
  } finally {
    uploading.value = false;
  }
}
```

Replace with:

```javascript
async function handleFile(e) {
  const file = e.target.files?.[0];
  e.target.value = "";
  if (!file) return;

  uploading.value = true;
  error.value = "";
  try {
    const { url, thumb } = await capturePhoto(file);
    localThumb.value = thumb;
    emit("update:modelValue", url);
  } catch (err) {
    error.value = err.message || "Photo failed";
    localThumb.value = null;
  } finally {
    uploading.value = false;
  }
}
```

Also, handle the case where a `photo:<uuid>` placeholder is loaded from an existing save — resolve its thumbnail on mount. Find the `localThumb` declaration:

```javascript
const localThumb = ref(null);
```

After all existing imports and refs in the `<script setup>` block, before the function declarations, add:

```javascript
// Resolve placeholder preview on load / model change
async function syncThumbFromModel() {
  if (!props.modelValue) { localThumb.value = null; return; }
  if (String(props.modelValue).startsWith("photo:")) {
    localThumb.value = await resolvePreview(props.modelValue);
  }
  // If it's a real URL, leave localThumb null — template uses props.modelValue directly
}
watch(() => props.modelValue, syncThumbFromModel, { immediate: true });
```

- [ ] **Step 4: Build + Deploy**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa/frontend && sudo -u v15 yarn build
cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 clear-cache && sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web
```

- [ ] **Step 5: Commit**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa && sudo -u v15 git add -A && sudo -u v15 git commit -m "feat: offline-first photo capture

capturePhoto compresses + stores blob in IndexedDB immediately, returning
a photo:<uuid> placeholder if upload fails or user is offline.
Sync engine uploads blobs later and rewrites placeholders in queue.
PhotoSlot resolves placeholders back to thumbnails on mount.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Queue Writes for Inspection + Actions

**Files:**
- Modify: `frontend/src/store/inspection.js`

**Strategy:** `saveItem`, `approve`, `reject` now enqueue to IndexedDB first AND update the local `transfer.items` cache, then call the API. If the API call fails (network error), the action remains in the queue and will drain later. If the API call succeeds, the queue entry is removed inline.

The key insight: we write to queue FIRST, then try the API. On success we clean up the queue. On failure we leave it.

- [ ] **Step 1: Rewrite inspection.js**

Read the current `apps/damage_pwa/frontend/src/store/inspection.js` on the server to confirm the shape.

Replace the entire contents of `apps/damage_pwa/frontend/src/store/inspection.js` with:

```javascript
import { defineStore } from "pinia";
import { call } from "@/utils/frappe.js";
import * as db from "@/utils/db.js";
import { isOnline } from "@/utils/online.js";
import { useSyncStore } from "@/store/sync.js";

export const useInspectionStore = defineStore("inspection", {
  state: () => ({
    transfer: null,
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
        // Try network first
        if (isOnline()) {
          try {
            this.transfer = await call("damage_pwa.api.inspect.get_transfer_detail", { name });
            await db.put("transfers", this.transfer);
            await this._applyLocalQueue(name);
            return;
          } catch (e) {
            // Fall back to cache
            this.error = `Using cached data: ${e.message}`;
          }
        }
        const cached = await db.get("transfers", name);
        if (cached) {
          this.transfer = cached;
          await this._applyLocalQueue(name);
        } else {
          throw new Error("No cached data and offline");
        }
      } catch (e) {
        this.error = e.message;
        throw e;
      } finally {
        this.loading = false;
      }
    },

    /**
     * Apply any pending inspection_queue entries to the in-memory transfer items
     * so the UI shows unsent changes immediately.
     */
    async _applyLocalQueue(transferName) {
      if (!this.transfer) return;
      const queued = (await db.getAll("inspection_queue")).filter(
        (q) => q.transferName === transferName
      );
      for (const q of queued) {
        const row = this.transfer.items.find((i) => i.row_name === q.rowName);
        if (row) {
          Object.assign(row, {
            supplier_code: q.supplier_code,
            damage_category: q.damage_category,
            images: q.images,
            image_2: q.image_2,
            image_3: q.image_3,
            remarks: q.remarks,
            _inspection_status: determineStatus(q),
          });
        }
      }
    },

    async claim(name) {
      // Claim requires network — fall through silently offline
      if (!isOnline()) {
        this.locked = true;  // optimistic
        return { locked: true, offline: true };
      }
      try {
        const result = await call("damage_pwa.api.inspect.claim_transfer", { name });
        this.locked = true;
        this.lockExpiresAt = result.expires_at;
        if (this.transfer) this.transfer.modified = result.modified;
        return result;
      } catch (e) {
        this.locked = false;
        throw e;
      }
    },

    findItem(rowName) {
      return this.items.find((i) => i.row_name === rowName);
    },

    /**
     * Save item inspection — writes to queue + local state immediately,
     * then attempts API call. On API success, queue entry is removed.
     */
    async saveItem({ rowName, supplier_code, damage_category, images, image_2, image_3, remarks, status = "complete" }) {
      if (!this.transfer) throw new Error("No transfer loaded");
      this.saving = true;
      const sync = useSyncStore();

      // Update local state immediately
      const row = this.findItem(rowName);
      if (row) {
        Object.assign(row, {
          supplier_code,
          damage_category,
          images,
          image_2,
          image_3,
          remarks,
          _inspection_status: determineStatus({ supplier_code, damage_category, images, status }),
        });
      }
      await db.put("transfers", this.transfer);

      const queueEntry = {
        transferName: this.transfer.name,
        rowName,
        supplier_code,
        damage_category,
        images,
        image_2,
        image_3,
        remarks,
        status,
        client_modified: this.transfer.modified,
        createdAt: Date.now(),
        attempts: 0,
      };

      // Enqueue
      const queueId = await db.add("inspection_queue", queueEntry);
      await sync.refreshCounts();

      // Try API if online and no photo placeholders
      const hasPlaceholder = [images, image_2, image_3].some(
        (u) => u && String(u).startsWith("photo:")
      );

      if (isOnline() && !hasPlaceholder) {
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
          this.transfer.modified = result.modified;
          await db.put("transfers", this.transfer);
          await db.del("inspection_queue", queueId);
          await sync.refreshCounts();
          this.saving = false;
          return result;
        } catch (e) {
          // Leave in queue; background sync will retry
          this.saving = false;
          // If it's a concurrency conflict, surface it
          if (String(e.message || "").includes("modified by someone else")) {
            throw e;
          }
          // Otherwise treat as queued for later
          return { queued: true };
        }
      }

      // Queued for later (offline or has placeholder photos)
      this.saving = false;
      // Trigger background sync in case we come online soon
      sync.requestBackgroundSync();
      return { queued: true };
    },

    async approve() {
      if (!this.transfer) throw new Error("No transfer loaded");
      const sync = useSyncStore();

      // If there are pending inspection_queue entries for this transfer, queue the approve
      const pending = (await db.getAll("inspection_queue")).filter(
        (q) => q.transferName === this.transfer.name
      );

      if (pending.length > 0 || !isOnline()) {
        await db.add("action_queue", {
          transferName: this.transfer.name,
          action: "approve",
          client_modified: this.transfer.modified,
          createdAt: Date.now(),
          attempts: 0,
        });
        await sync.refreshCounts();
        sync.requestBackgroundSync();
        return { queued: true };
      }

      // Direct call
      return call("damage_pwa.api.inspect.approve_transfer", {
        name: this.transfer.name,
        client_modified: this.transfer.modified,
      });
    },

    async reject(reason) {
      if (!this.transfer) throw new Error("No transfer loaded");
      const sync = useSyncStore();

      if (!isOnline()) {
        await db.add("action_queue", {
          transferName: this.transfer.name,
          action: "reject",
          reason,
          client_modified: this.transfer.modified,
          createdAt: Date.now(),
          attempts: 0,
        });
        await sync.refreshCounts();
        sync.requestBackgroundSync();
        return { queued: true };
      }

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

function determineStatus({ supplier_code, damage_category, images, status }) {
  if (status === "flagged") return "flagged";
  if (supplier_code && damage_category && images) return "complete";
  return "incomplete";
}
```

- [ ] **Step 2: Build + Deploy**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa/frontend && sudo -u v15 yarn build
cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 clear-cache && sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web
```

- [ ] **Step 3: Commit**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa && sudo -u v15 git add -A && sudo -u v15 git commit -m "feat: offline-first inspection writes

saveItem enqueues to IndexedDB first, then tries API if online.
Photos with photo:<uuid> placeholders stay queued until photo uploaded.
approve/reject queue if pending inspections exist or offline.
loadTransfer applies local queue overlay so UI shows unsent changes.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Sync Bar with Queue Counts

**Files:**
- Modify: `frontend/src/components/SyncBar.vue`

- [ ] **Step 1: Replace SyncBar.vue**

Replace the entire contents of `apps/damage_pwa/frontend/src/components/SyncBar.vue` with:

```vue
<template>
  <div class="sync-bar" :class="statusClass" @click="handleClick">
    <span class="sync-dot"></span>
    <span class="sync-text">{{ statusText }}</span>
    <span v-if="sync.draining" class="spinner-sm"></span>
  </div>
</template>

<script setup>
import { computed, onMounted } from "vue";
import { useOnline } from "@/utils/online.js";
import { useSyncStore } from "@/store/sync.js";

const online = useOnline();
const sync = useSyncStore();

onMounted(() => sync.refreshCounts());

const statusClass = computed(() => {
  if (!online.value) return "offline";
  if (sync.hasPending) return "pending";
  if (sync.lastError) return "error";
  return "synced";
});

const statusText = computed(() => {
  if (!online.value) {
    if (sync.hasPending) return `OFFLINE — ${sync.pendingTotal} PENDING`;
    return "OFFLINE — WORKING LOCALLY";
  }
  if (sync.draining) return `SYNCING ${sync.pendingTotal}...`;
  if (sync.hasPending) return `${sync.pendingTotal} CHANGES PENDING · TAP TO SYNC`;
  if (sync.lastError) return `SYNC ERROR — TAP TO RETRY`;
  if (sync.lastSyncAt) return `SYNCED ${relativeTime(sync.lastSyncAt)}`;
  return "ONLINE";
});

function relativeTime(iso) {
  const then = new Date(iso).getTime();
  const diff = Math.floor((Date.now() - then) / 1000);
  if (diff < 60) return "JUST NOW";
  if (diff < 3600) return `${Math.floor(diff / 60)} MIN AGO`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} H AGO`;
  return new Date(iso).toLocaleDateString();
}

function handleClick() {
  if (online.value && (sync.hasPending || sync.lastError)) {
    sync.drain();
  }
}
</script>

<style scoped>
.sync-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  font-size: 10px;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  border-bottom: 1px solid var(--border);
  cursor: default;
  font-weight: 600;
}

.sync-bar.pending, .sync-bar.error { cursor: pointer; }

.sync-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.synced  .sync-dot { background: var(--green); }
.offline .sync-dot { background: var(--red); }
.pending .sync-dot { background: var(--amber); animation: pulse 1.2s infinite; }
.error   .sync-dot { background: var(--red); }

.synced  .sync-text { color: var(--text-dim); }
.offline .sync-text { color: var(--red); }
.pending .sync-text { color: var(--amber); }
.error   .sync-text { color: var(--red); }

.spinner-sm {
  display: inline-block;
  width: 10px;
  height: 10px;
  border: 1.5px solid var(--border);
  border-top-color: var(--amber);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-left: auto;
}

@keyframes spin { to { transform: rotate(360deg); } }
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
</style>
```

- [ ] **Step 2: Build + Deploy**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa/frontend && sudo -u v15 yarn build
cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 clear-cache && sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web
```

- [ ] **Step 3: Verify manually**

- Open the app online → bar shows "SYNCED JUST NOW" (or "ONLINE")
- Toggle DevTools to offline → bar turns red "OFFLINE — WORKING LOCALLY"
- Save an inspection while offline → bar shows "OFFLINE — 1 PENDING"
- Go back online → bar shows "1 CHANGES PENDING · TAP TO SYNC" → tap → "SYNCING 1..." → "SYNCED JUST NOW"

- [ ] **Step 4: Commit**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa && sudo -u v15 git add -A && sudo -u v15 git commit -m "feat: sync bar shows queue counts + tap-to-sync

Amber pulsing dot when pending, red when offline or error.
Tap while online to force drain. Shows relative last-sync time.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 6: PWA Icons + Manifest Polish

**Files:**
- Create: `damage_pwa/public/icons/icon-192.png`
- Create: `damage_pwa/public/icons/icon-512.png`
- Modify: `damage_pwa/public/manifest.json`

We need PWA icons for Add-to-Home-Screen. Generate simple solid-color icons with the "DPWA" text on them using ImageMagick on the server (already installed on most Frappe hosts — fall back to a Python pillow script if not).

- [ ] **Step 1: Generate icons**

Run on the server:

```bash
sudo -u v15 mkdir -p /home/v15/frappe-bench/apps/damage_pwa/damage_pwa/public/icons
cd /home/v15/frappe-bench/apps/damage_pwa/damage_pwa/public/icons

# Try ImageMagick first
if command -v convert >/dev/null 2>&1; then
  sudo -u v15 convert -size 512x512 xc:'#0a0a0a' \
    -fill '#f59e0b' -gravity center \
    -font 'DejaVu-Sans-Bold' -pointsize 120 \
    -annotate 0 'DPWA' icon-512.png
  sudo -u v15 convert icon-512.png -resize 192x192 icon-192.png
else
  # Fallback: Python + Pillow
  sudo -u v15 python3 <<'PYEOF'
from PIL import Image, ImageDraw, ImageFont
for size in (512, 192):
    img = Image.new("RGB", (size, size), "#0a0a0a")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size // 4)
    except Exception:
        font = ImageFont.load_default()
    text = "DPWA"
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - w) / 2, (size - h) / 2 - bbox[1]), text, fill="#f59e0b", font=font)
    img.save(f"icon-{size}.png")
PYEOF
fi

ls -la /home/v15/frappe-bench/apps/damage_pwa/damage_pwa/public/icons/
```

Expected: Two files `icon-192.png` and `icon-512.png` exist.

- [ ] **Step 2: Update manifest.json**

Read `apps/damage_pwa/damage_pwa/public/manifest.json`. Replace with:

```json
{
  "name": "Damage PWA",
  "short_name": "DamagePWA",
  "description": "Warehouse Damage Inspection",
  "start_url": "/damage-pwa/",
  "scope": "/damage-pwa/",
  "display": "standalone",
  "orientation": "portrait",
  "theme_color": "#0a0a0a",
  "background_color": "#0a0a0a",
  "categories": ["productivity", "business"],
  "icons": [
    {
      "src": "/assets/damage_pwa/icons/icon-192.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any maskable"
    },
    {
      "src": "/assets/damage_pwa/icons/icon-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any maskable"
    }
  ]
}
```

- [ ] **Step 3: Re-symlink assets (in case it's stale)**

```bash
sudo -u v15 ln -sfn /home/v15/frappe-bench/apps/damage_pwa/damage_pwa/public /home/v15/frappe-bench/sites/assets/damage_pwa
```

- [ ] **Step 4: Deploy**

No yarn build needed — icons and manifest are static assets under `public/`. Just:

```bash
cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 clear-cache && sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web
```

- [ ] **Step 5: Verify**

- `https://rmax-dev.fateherp.com/assets/damage_pwa/icons/icon-192.png` — returns a 192x192 PNG
- `https://rmax-dev.fateherp.com/assets/damage_pwa/manifest.json` — returns the manifest
- In Chrome DevTools → Application → Manifest, should show all fields and render both icons

- [ ] **Step 6: Commit**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa && sudo -u v15 git add -A && sudo -u v15 git commit -m "feat: PWA icons + polished manifest

192px + 512px icons with 'DPWA' text on Industrial Dark background.
Manifest adds orientation, categories, maskable purpose.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Phase 4 Checkpoint

After completing all 6 tasks, verify:

| Test | Method | Expected |
|------|--------|----------|
| SW registers | DevTools → Application → SW | sw.js registered, scope `/damage-pwa/` |
| Static cache | Reload page with SW active | Assets served from SW cache (check Network tab "from ServiceWorker") |
| Offline page load | DevTools offline → reload | SPA loads from cache; login works if session cached |
| Offline save | Save inspection offline | No error; item shows updated locally; sync bar "1 PENDING" |
| Photo offline | Take photo offline | Thumbnail shows; photo queued |
| Come online | Toggle online | Sync bar turns amber, drains automatically, turns green |
| Tap to sync | Hit pending state online | Tap sync bar → drains immediately |
| Offline approve | Queue approve offline | `action_queue` has entry; syncs after inspections complete |
| PWA install | Chrome menu → "Install Damage PWA" | Install prompt works; app opens standalone |
| Icons display | Install prompt / Home screen | Amber DPWA icon visible |

**Next:** Phase 5 — Polish (Settings/Change PIN, error toasts, pull-to-refresh) + Android TWA wrapper
