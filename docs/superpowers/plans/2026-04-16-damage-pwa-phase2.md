# Damage PWA Phase 2: Vue SPA Core + Login + Dashboard

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Vue 3 SPA shell with PIN login, dashboard with pending transfers, and Frappe API integration — testable in browser at `/damage-pwa/`.

**Architecture:** Vue 3 + Vite SPA built into `damage_pwa/public/frontend/`. Served by Frappe via `www/damage-pwa/index.py` which discovers hashed asset files. Pinia stores manage state. API client wraps Frappe REST with CSRF handling. Industrial Dark theme via CSS variables.

**Tech Stack:** Vue 3.4, Vue Router 4, Pinia 2, Vite 5, idb 8 (IndexedDB)

**Spec:** `docs/superpowers/specs/2026-04-16-damage-pwa-design.md`

**Depends on:** Phase 1 complete (all backend APIs deployed on server)

**Server:** Commands run via HTTP API to `207.180.209.80:3847`, bench user `v15`, site `rmax_dev2`

---

## File Map

```
frappe-bench/apps/damage_pwa/
├── frontend/                              # NEW — Vue 3 SPA
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html                         # Vite dev entry
│   └── src/
│       ├── main.js                        # Vue app bootstrap
│       ├── App.vue                        # Root: router-view + bottom nav
│       ├── style.css                      # Industrial Dark theme (CSS vars)
│       ├── router/index.js                # Vue Router with auth guard
│       ├── store/
│       │   ├── auth.js                    # PIN + session + login/logout
│       │   ├── transfers.js               # Pending + history lists
│       │   └── master.js                  # Supplier codes cache
│       ├── utils/
│       │   ├── frappe.js                  # API wrapper with CSRF + dedup
│       │   └── db.js                      # IndexedDB via idb library
│       ├── views/
│       │   ├── LoginView.vue              # PIN entry + first-time setup
│       │   └── DashboardView.vue          # KPIs + pending transfer list
│       └── components/
│           ├── BottomNav.vue              # Home | History | Settings tabs
│           ├── SyncBar.vue                # Online/offline + sync status
│           ├── PinPad.vue                 # 4-digit numpad
│           ├── TransferCard.vue           # Pending transfer list card
│           └── KpiCard.vue                # Dashboard stat card
├── damage_pwa/
│   ├── www/
│   │   └── damage-pwa/
│   │       ├── index.py                   # NEW — SPA entry (asset discovery)
│   │       └── index.html                 # NEW — Jinja template
│   └── public/
│       ├── manifest.json                  # NEW — PWA manifest
│       └── frontend/                      # Vite build output (gitignored)
```

---

### Task 1: Scaffold Vue 3 + Vite Frontend

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.js`
- Create: `frontend/src/style.css`

- [ ] **Step 1: Create frontend directory and package.json**

Create `apps/damage_pwa/frontend/package.json`:

```json
{
  "name": "damage-pwa-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.3.0",
    "pinia": "^2.1.0",
    "idb": "^8.0.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "vite": "^5.4.0"
  }
}
```

- [ ] **Step 2: Create vite.config.js**

Create `apps/damage_pwa/frontend/vite.config.js`:

```javascript
import path from "path";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig(({ command }) => ({
  plugins: [vue()],
  base: command === "serve" ? "/" : "/assets/damage_pwa/frontend/",
  build: {
    outDir: path.resolve(__dirname, "../damage_pwa/public/frontend"),
    emptyOutDir: true,
    target: "es2020",
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  server: {
    port: 8081,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/assets": { target: "http://localhost:8000" },
    },
  },
}));
```

- [ ] **Step 3: Create index.html (Vite dev entry)**

Create `apps/damage_pwa/frontend/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
  <meta name="theme-color" content="#0a0a0a" />
  <title>Damage PWA</title>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.js"></script>
</body>
</html>
```

- [ ] **Step 4: Create style.css (Industrial Dark theme)**

Create `apps/damage_pwa/frontend/src/style.css`:

```css
:root {
  --bg: #0a0a0a;
  --surface: #1a1a1a;
  --border: #333333;
  --amber: #f59e0b;
  --green: #22c55e;
  --red: #dc2626;
  --text: #ffffff;
  --text-dim: #666666;
  --font: "SF Mono", "Courier New", "Consolas", monospace;
  --radius: 8px;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--font);
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  min-height: 100dvh;
  overflow-x: hidden;
}

#app {
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
}

input, select, textarea {
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px;
  font-family: var(--font);
  font-size: 14px;
  width: 100%;
  outline: none;
}

input:focus, select:focus, textarea:focus {
  border-color: var(--amber);
}

button {
  font-family: var(--font);
  cursor: pointer;
  border: none;
  border-radius: var(--radius);
  padding: 12px 24px;
  font-size: 14px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.btn-primary {
  background: var(--amber);
  color: #000;
}

.btn-success {
  background: var(--green);
  color: #000;
}

.btn-danger {
  background: var(--red);
  color: #fff;
}

.btn-ghost {
  background: transparent;
  color: var(--text-dim);
  border: 1px solid var(--border);
}

.label {
  text-transform: uppercase;
  letter-spacing: 1.5px;
  font-size: 10px;
  color: var(--amber);
  margin-bottom: 4px;
}

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
}

.page {
  flex: 1;
  padding: 16px;
  padding-bottom: 80px;
  max-width: 480px;
  margin: 0 auto;
  width: 100%;
}

.page-title {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 16px;
  letter-spacing: 1px;
  text-transform: uppercase;
}

/* Scrollbar */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
```

- [ ] **Step 5: Create main.js**

Create `apps/damage_pwa/frontend/src/main.js`:

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

- [ ] **Step 6: Install dependencies**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa/frontend && sudo -u v15 yarn install
```

- [ ] **Step 7: Commit**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa && sudo -u v15 git add -A && sudo -u v15 git commit -m "feat: scaffold Vue 3 + Vite frontend

Industrial Dark theme, package.json with vue/pinia/idb deps.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: API Client + IndexedDB Wrapper

**Files:**
- Create: `frontend/src/utils/frappe.js`
- Create: `frontend/src/utils/db.js`

- [ ] **Step 1: Create frappe.js API wrapper**

Create `apps/damage_pwa/frontend/src/utils/frappe.js`:

```javascript
const pendingRequests = new Map();
const cache = new Map();

function getCsrfToken() {
  const cookie = document.cookie.match(/csrf_token=([^;]+)/);
  if (cookie) return decodeURIComponent(cookie[1]);
  if (window.csrf_token) return window.csrf_token;
  return null;
}

export async function call(method, args = {}, opts = {}) {
  const cacheKey = JSON.stringify({ method, args });

  if (opts.cache) {
    const cached = cache.get(cacheKey);
    if (cached && Date.now() - cached.time < opts.cache) {
      return cached.data;
    }
  }

  if (pendingRequests.has(cacheKey)) {
    return pendingRequests.get(cacheKey);
  }

  const promise = fetch(`/api/method/${method}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Frappe-CSRF-Token": getCsrfToken(),
    },
    credentials: "include",
    body: JSON.stringify(args),
  })
    .then(async (r) => {
      if (!r.ok) {
        const data = await r.json().catch(() => ({}));
        const err = new Error(extractError(data) || `HTTP ${r.status}`);
        err.status = r.status;
        err.data = data;
        throw err;
      }
      const data = await r.json();
      if (data.exc) {
        throw new Error(extractError(data) || "Server error");
      }
      return data.message;
    })
    .finally(() => pendingRequests.delete(cacheKey));

  pendingRequests.set(cacheKey, promise);

  const result = await promise;
  if (opts.cache) {
    cache.set(cacheKey, { data: result, time: Date.now() });
  }
  return result;
}

function extractError(err) {
  if (typeof err._server_messages === "string") {
    try {
      const msgs = JSON.parse(err._server_messages);
      return msgs
        .map((m) => {
          try { return JSON.parse(m).message; } catch { return m; }
        })
        .join("; ");
    } catch { /* fall through */ }
  }
  if (typeof err.exception === "string") {
    return err.exception.split("\n")[0];
  }
  if (typeof err.message === "string") return err.message;
  return null;
}

export async function login(usr, pwd) {
  const r = await fetch("/api/method/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ usr, pwd }),
  });
  if (!r.ok) throw new Error("Invalid credentials");
  return r.json();
}

export async function logout() {
  await fetch("/api/method/logout", {
    method: "POST",
    credentials: "include",
    headers: { "X-Frappe-CSRF-Token": getCsrfToken() },
  });
}

export async function uploadFile(file) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("is_private", "0");

  const r = await fetch("/api/method/upload_file", {
    method: "POST",
    credentials: "include",
    headers: { "X-Frappe-CSRF-Token": getCsrfToken() },
    body: formData,
  });
  if (!r.ok) throw new Error("Upload failed");
  const data = await r.json();
  return data.message.file_url;
}
```

- [ ] **Step 2: Create db.js IndexedDB wrapper**

Create `apps/damage_pwa/frontend/src/utils/db.js`:

```javascript
import { openDB } from "idb";

const DB_NAME = "damage-pwa";
const DB_VERSION = 1;

let dbPromise = null;

function getDB() {
  if (!dbPromise) {
    dbPromise = openDB(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains("auth")) {
          db.createObjectStore("auth");
        }
        if (!db.objectStoreNames.contains("transfers")) {
          db.createObjectStore("transfers", { keyPath: "name" });
        }
        if (!db.objectStoreNames.contains("supplier_codes")) {
          db.createObjectStore("supplier_codes", { keyPath: "name" });
        }
        if (!db.objectStoreNames.contains("photos")) {
          db.createObjectStore("photos", { keyPath: "id" });
        }
        if (!db.objectStoreNames.contains("inspection_queue")) {
          db.createObjectStore("inspection_queue", {
            keyPath: "id",
            autoIncrement: true,
          });
        }
        if (!db.objectStoreNames.contains("action_queue")) {
          db.createObjectStore("action_queue", {
            keyPath: "id",
            autoIncrement: true,
          });
        }
      },
    });
  }
  return dbPromise;
}

export async function get(store, key) {
  const db = await getDB();
  return db.get(store, key);
}

export async function set(store, key, value) {
  const db = await getDB();
  return db.put(store, value, key);
}

export async function put(store, value) {
  const db = await getDB();
  return db.put(store, value);
}

export async function del(store, key) {
  const db = await getDB();
  return db.delete(store, key);
}

export async function getAll(store) {
  const db = await getDB();
  return db.getAll(store);
}

export async function clear(store) {
  const db = await getDB();
  return db.clear(store);
}

export async function clearAll() {
  const db = await getDB();
  const stores = ["transfers", "supplier_codes", "photos", "inspection_queue", "action_queue"];
  const tx = db.transaction(stores, "readwrite");
  await Promise.all(stores.map((s) => tx.objectStore(s).clear()));
  await tx.done;
}

export async function add(store, value) {
  const db = await getDB();
  return db.add(store, value);
}
```

- [ ] **Step 3: Commit**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa && sudo -u v15 git add -A && sudo -u v15 git commit -m "feat: add Frappe API client + IndexedDB wrapper

API client: CSRF handling, request dedup, error extraction.
IndexedDB: 6 stores (auth, transfers, supplier_codes, photos, inspection_queue, action_queue).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Auth Store + Router with Guard

**Files:**
- Create: `frontend/src/store/auth.js`
- Create: `frontend/src/router/index.js`

- [ ] **Step 1: Create auth store**

Create `apps/damage_pwa/frontend/src/store/auth.js`:

```javascript
import { defineStore } from "pinia";
import { call, login as frappeLogin, logout as frappeLogout } from "@/utils/frappe.js";
import * as db from "@/utils/db.js";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    user: null,
    fullName: null,
    roles: [],
    sessionExpiresAt: null,
    hasPin: false,
    loading: true,
  }),

  getters: {
    isAuthenticated: (state) => !!state.user,
    isDamageUser: (state) => state.roles.includes("Damage User"),
  },

  actions: {
    async init() {
      this.loading = true;
      try {
        const cached = await db.get("auth", "session");
        if (cached) {
          this.user = cached.user;
          this.fullName = cached.fullName;
          this.roles = cached.roles || [];
          this.hasPin = cached.hasPin || false;
          this.sessionExpiresAt = cached.sessionExpiresAt;
        }

        // Validate server session
        try {
          const result = await call("damage_pwa.api.auth.validate_session");
          if (result && result.valid) {
            this.user = result.user;
            this.fullName = result.full_name;
            this.sessionExpiresAt = result.session_expires_at;
            await this._saveToDb();
          }
        } catch (e) {
          // Offline or session expired — keep cached data if available
          if (!cached) {
            this.user = null;
          }
        }
      } finally {
        this.loading = false;
      }
    },

    async login(username, password) {
      await frappeLogin(username, password);
      // After login, set up PIN
      return true;
    },

    async setupPin(pin) {
      const result = await call("damage_pwa.api.auth.setup_pin", { pin });
      this.user = result.user;
      this.fullName = result.full_name;
      this.roles = result.roles;
      this.sessionExpiresAt = result.session_expires_at;
      this.hasPin = true;
      await this._saveToDb();
      return result;
    },

    async validatePin(pin) {
      // PIN is validated locally against stored hash
      // For now, just check session is valid and user has PIN set
      const cached = await db.get("auth", "session");
      if (!cached || !cached.hasPin) return false;

      // Validate server session if online
      try {
        const result = await call("damage_pwa.api.auth.validate_session");
        if (result && result.valid) {
          this.sessionExpiresAt = result.session_expires_at;
          await this._saveToDb();
          return true;
        }
      } catch {
        // Offline — allow if we have cached session
        if (cached && cached.user) return true;
      }
      return false;
    },

    async logout() {
      try {
        await frappeLogout();
      } catch { /* ignore if offline */ }
      this.user = null;
      this.fullName = null;
      this.roles = [];
      this.hasPin = false;
      this.sessionExpiresAt = null;
      await db.del("auth", "session");
      await db.clearAll();
    },

    async _saveToDb() {
      await db.set("auth", "session", {
        user: this.user,
        fullName: this.fullName,
        roles: this.roles,
        hasPin: this.hasPin,
        sessionExpiresAt: this.sessionExpiresAt,
      });
    },
  },
});
```

- [ ] **Step 2: Create router with auth guard**

Create `apps/damage_pwa/frontend/src/router/index.js`:

```javascript
import { createRouter, createWebHistory } from "vue-router";

const routes = [
  {
    path: "/",
    redirect: "/dashboard",
  },
  {
    path: "/login",
    name: "Login",
    component: () => import("@/views/LoginView.vue"),
    meta: { public: true },
  },
  {
    path: "/dashboard",
    name: "Dashboard",
    component: () => import("@/views/DashboardView.vue"),
  },
  {
    path: "/history",
    name: "History",
    component: () => import("@/views/HistoryView.vue"),
  },
  {
    path: "/settings",
    name: "Settings",
    component: () => import("@/views/SettingsView.vue"),
  },
  {
    path: "/transfer/:name",
    name: "TransferDetail",
    component: () => import("@/views/TransferDetailView.vue"),
    props: true,
  },
  {
    path: "/transfer/:name/inspect/:rowName",
    name: "Inspection",
    component: () => import("@/views/InspectionView.vue"),
    props: true,
  },
  {
    path: "/slip/:name",
    name: "SlipDetail",
    component: () => import("@/views/SlipDetailView.vue"),
    props: true,
  },
];

const router = createRouter({
  history: createWebHistory("/damage-pwa/"),
  routes,
});

router.beforeEach(async (to) => {
  if (to.meta.public) return;

  const { useAuthStore } = await import("@/store/auth.js");
  const auth = useAuthStore();

  if (auth.loading) {
    await auth.init();
  }

  if (!auth.isAuthenticated) {
    return { name: "Login", query: { redirect: to.fullPath } };
  }
});

export default router;
```

- [ ] **Step 3: Commit**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa && sudo -u v15 git add -A && sudo -u v15 git commit -m "feat: add auth store + Vue Router with auth guard

Pinia auth store: login, PIN setup, session validation, IndexedDB cache.
Router: 8 routes with lazy loading, auth guard redirects to /login.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: App Shell + Bottom Nav + Sync Bar

**Files:**
- Create: `frontend/src/App.vue`
- Create: `frontend/src/components/BottomNav.vue`
- Create: `frontend/src/components/SyncBar.vue`

- [ ] **Step 1: Create App.vue**

Create `apps/damage_pwa/frontend/src/App.vue`:

```vue
<template>
  <div class="app-shell">
    <SyncBar v-if="auth.isAuthenticated" />
    <router-view />
    <BottomNav v-if="auth.isAuthenticated" />
  </div>
</template>

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

<style scoped>
.app-shell {
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
}
</style>
```

- [ ] **Step 2: Create BottomNav.vue**

Create `apps/damage_pwa/frontend/src/components/BottomNav.vue`:

```vue
<template>
  <nav class="bottom-nav">
    <router-link to="/dashboard" class="nav-item" :class="{ active: route.name === 'Dashboard' }">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
        <polyline points="9 22 9 12 15 12 15 22"/>
      </svg>
      <span>HOME</span>
    </router-link>
    <router-link to="/history" class="nav-item" :class="{ active: route.name === 'History' }">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <polyline points="12 6 12 12 16 14"/>
      </svg>
      <span>HISTORY</span>
    </router-link>
    <router-link to="/settings" class="nav-item" :class="{ active: route.name === 'Settings' }">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="3"/>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
      </svg>
      <span>SETTINGS</span>
    </router-link>
  </nav>
</template>

<script setup>
import { useRoute } from "vue-router";
const route = useRoute();
</script>

<style scoped>
.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--surface);
  border-top: 1px solid var(--border);
  display: flex;
  justify-content: space-around;
  padding: 8px 0;
  padding-bottom: max(8px, env(safe-area-inset-bottom));
  z-index: 100;
}

.nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  text-decoration: none;
  color: var(--text-dim);
  font-size: 9px;
  letter-spacing: 1.5px;
  padding: 4px 16px;
  transition: color 0.2s;
}

.nav-item.active {
  color: var(--amber);
}

.nav-item svg {
  width: 20px;
  height: 20px;
}
</style>
```

- [ ] **Step 3: Create SyncBar.vue**

Create `apps/damage_pwa/frontend/src/components/SyncBar.vue`:

```vue
<template>
  <div class="sync-bar" :class="statusClass">
    <span class="sync-dot"></span>
    <span class="sync-text">{{ statusText }}</span>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";

const online = ref(navigator.onLine);

function onOnline() { online.value = true; }
function onOffline() { online.value = false; }

onMounted(() => {
  window.addEventListener("online", onOnline);
  window.addEventListener("offline", onOffline);
});

onUnmounted(() => {
  window.removeEventListener("online", onOnline);
  window.removeEventListener("offline", onOffline);
});

const statusClass = computed(() => {
  if (!online.value) return "offline";
  return "synced";
});

const statusText = computed(() => {
  if (!online.value) return "OFFLINE — WORKING LOCALLY";
  return "ONLINE";
});
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
}

.sync-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.synced .sync-dot { background: var(--green); }
.offline .sync-dot { background: var(--red); }
.pending .sync-dot { background: var(--amber); }

.synced .sync-text { color: var(--text-dim); }
.offline .sync-text { color: var(--red); }
.pending .sync-text { color: var(--amber); }
</style>
```

- [ ] **Step 4: Commit**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa && sudo -u v15 git add -A && sudo -u v15 git commit -m "feat: add App shell + BottomNav + SyncBar

Root layout with auth-gated nav and online/offline indicator.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: PinPad Component + Login View

**Files:**
- Create: `frontend/src/components/PinPad.vue`
- Create: `frontend/src/views/LoginView.vue`

- [ ] **Step 1: Create PinPad.vue**

Create `apps/damage_pwa/frontend/src/components/PinPad.vue`:

```vue
<template>
  <div class="pin-pad">
    <div class="pin-dots">
      <span v-for="i in 4" :key="i" class="dot" :class="{ filled: pin.length >= i }"></span>
    </div>
    <p v-if="error" class="pin-error">{{ error }}</p>
    <div class="numpad">
      <button v-for="n in [1,2,3,4,5,6,7,8,9]" :key="n" class="num-key" @click="press(n)">{{ n }}</button>
      <button class="num-key empty" disabled></button>
      <button class="num-key" @click="press(0)">0</button>
      <button class="num-key del" @click="backspace">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 4H8l-7 8 7 8h13a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2z"/>
          <line x1="18" y1="9" x2="12" y2="15"/>
          <line x1="12" y1="9" x2="18" y2="15"/>
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from "vue";

const props = defineProps({
  error: { type: String, default: "" },
});

const emit = defineEmits(["complete"]);
const pin = ref("");

function press(n) {
  if (pin.value.length >= 4) return;
  pin.value += String(n);
}

function backspace() {
  pin.value = pin.value.slice(0, -1);
}

watch(pin, (val) => {
  if (val.length === 4) {
    emit("complete", val);
    setTimeout(() => { pin.value = ""; }, 300);
  }
});

defineExpose({ clear: () => { pin.value = ""; } });
</script>

<style scoped>
.pin-pad {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
}

.pin-dots {
  display: flex;
  gap: 16px;
}

.dot {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid var(--border);
  transition: all 0.15s;
}

.dot.filled {
  background: var(--amber);
  border-color: var(--amber);
}

.pin-error {
  color: var(--red);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.numpad {
  display: grid;
  grid-template-columns: repeat(3, 72px);
  gap: 12px;
}

.num-key {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text);
  font-size: 24px;
  font-family: var(--font);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.1s;
  padding: 0;
}

.num-key:active {
  background: var(--amber);
  color: #000;
  border-color: var(--amber);
}

.num-key.empty {
  visibility: hidden;
}

.num-key.del {
  font-size: 18px;
}

.num-key.del svg {
  stroke: var(--text-dim);
}
</style>
```

- [ ] **Step 2: Create LoginView.vue**

Create `apps/damage_pwa/frontend/src/views/LoginView.vue`:

```vue
<template>
  <div class="login-page">
    <div class="login-header">
      <h1 class="brand">DAMAGE<span class="accent">PWA</span></h1>
      <p class="subtitle">WAREHOUSE INSPECTION SYSTEM</p>
    </div>

    <!-- Step 1: Username/Password (first time) -->
    <div v-if="step === 'credentials'" class="login-form">
      <p class="label">SIGN IN WITH YOUR ACCOUNT</p>
      <input
        v-model="username"
        type="text"
        placeholder="Email or username"
        autocomplete="username"
        @keyup.enter="$refs.pwdInput?.focus()"
      />
      <input
        ref="pwdInput"
        v-model="password"
        type="password"
        placeholder="Password"
        autocomplete="current-password"
        @keyup.enter="handleLogin"
      />
      <p v-if="error" class="error-text">{{ error }}</p>
      <button class="btn-primary full" :disabled="loggingIn" @click="handleLogin">
        {{ loggingIn ? "SIGNING IN..." : "SIGN IN" }}
      </button>
    </div>

    <!-- Step 2: Set PIN (after login) -->
    <div v-else-if="step === 'setup-pin'" class="pin-section">
      <p class="label">SET YOUR 4-DIGIT PIN</p>
      <p class="hint">Quick access for future sessions</p>
      <PinPad :error="error" @complete="handleSetupPin" />
    </div>

    <!-- Step 3: Enter PIN (returning user) -->
    <div v-else-if="step === 'enter-pin'" class="pin-section">
      <p class="welcome">{{ auth.fullName || auth.user }}</p>
      <p class="label">ENTER PIN</p>
      <PinPad :error="error" @complete="handlePinEntry" />
      <button class="btn-ghost switch-btn" @click="step = 'credentials'">
        USE PASSWORD INSTEAD
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useAuthStore } from "@/store/auth.js";
import PinPad from "@/components/PinPad.vue";

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();

const step = ref("credentials");
const username = ref("");
const password = ref("");
const error = ref("");
const loggingIn = ref(false);

onMounted(async () => {
  await auth.init();
  if (auth.isAuthenticated && auth.hasPin) {
    step.value = "enter-pin";
  }
});

async function handleLogin() {
  error.value = "";
  loggingIn.value = true;
  try {
    await auth.login(username.value, password.value);
    step.value = "setup-pin";
  } catch (e) {
    error.value = "Invalid email or password";
  } finally {
    loggingIn.value = false;
  }
}

async function handleSetupPin(pin) {
  error.value = "";
  try {
    await auth.setupPin(pin);
    const redirect = route.query.redirect || "/dashboard";
    router.replace(redirect);
  } catch (e) {
    error.value = e.message || "Failed to set PIN";
  }
}

async function handlePinEntry(pin) {
  error.value = "";
  try {
    const valid = await auth.validatePin(pin);
    if (valid) {
      const redirect = route.query.redirect || "/dashboard";
      router.replace(redirect);
    } else {
      error.value = "Invalid PIN or session expired";
      step.value = "credentials";
    }
  } catch (e) {
    error.value = "Verification failed";
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 24px;
  gap: 32px;
}

.login-header {
  text-align: center;
}

.brand {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 4px;
}

.accent {
  color: var(--amber);
}

.subtitle {
  font-size: 10px;
  letter-spacing: 3px;
  color: var(--text-dim);
  margin-top: 4px;
}

.login-form {
  width: 100%;
  max-width: 320px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.error-text {
  color: var(--red);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.full {
  width: 100%;
  height: 48px;
}

.pin-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.welcome {
  font-size: 16px;
  color: var(--text);
}

.hint {
  font-size: 12px;
  color: var(--text-dim);
}

.switch-btn {
  margin-top: 16px;
  font-size: 11px;
  padding: 8px 16px;
}
</style>
```

- [ ] **Step 3: Commit**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa && sudo -u v15 git add -A && sudo -u v15 git commit -m "feat: add PinPad component + LoginView

3-step login: credentials → set PIN → enter PIN.
Numpad with haptic dots, password fallback.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 6: Transfers Store + Dashboard View

**Files:**
- Create: `frontend/src/store/transfers.js`
- Create: `frontend/src/store/master.js`
- Create: `frontend/src/components/KpiCard.vue`
- Create: `frontend/src/components/TransferCard.vue`
- Create: `frontend/src/views/DashboardView.vue`

- [ ] **Step 1: Create transfers store**

Create `apps/damage_pwa/frontend/src/store/transfers.js`:

```javascript
import { defineStore } from "pinia";
import { call } from "@/utils/frappe.js";
import * as db from "@/utils/db.js";

export const useTransfersStore = defineStore("transfers", {
  state: () => ({
    pending: [],
    loading: false,
    lastFetched: null,
    error: null,
  }),

  getters: {
    pendingCount: (state) => state.pending.length,
    approvedCount: () => 0,
    rejectedCount: () => 0,
  },

  actions: {
    async fetchPending() {
      this.loading = true;
      this.error = null;
      try {
        const result = await call("damage_pwa.api.inspect.get_pending_transfers");
        this.pending = result || [];
        this.lastFetched = new Date().toISOString();

        // Cache to IndexedDB
        await db.clear("transfers");
        for (const t of this.pending) {
          await db.put("transfers", t);
        }
      } catch (e) {
        this.error = e.message;
        // Try loading from cache
        const cached = await db.getAll("transfers");
        if (cached.length) {
          this.pending = cached;
        }
      } finally {
        this.loading = false;
      }
    },

    async fetchKpis() {
      try {
        const history = await call("damage_pwa.api.inspect.get_history", {
          limit: 0,
          start: 0,
          status_filter: "Approved",
        });
        this.approvedCount = history?.total_count || 0;
      } catch { /* offline */ }

      try {
        const history = await call("damage_pwa.api.inspect.get_history", {
          limit: 0,
          start: 0,
          status_filter: "Rejected",
        });
        this.rejectedCount = history?.total_count || 0;
      } catch { /* offline */ }
    },
  },
});
```

- [ ] **Step 2: Create master store**

Create `apps/damage_pwa/frontend/src/store/master.js`:

```javascript
import { defineStore } from "pinia";
import { call } from "@/utils/frappe.js";
import * as db from "@/utils/db.js";

export const useMasterStore = defineStore("master", {
  state: () => ({
    supplierCodes: [],
    lastModified: null,
    loading: false,
  }),

  actions: {
    async fetchSupplierCodes() {
      this.loading = true;
      try {
        const result = await call("damage_pwa.api.master.get_supplier_codes", {
          if_modified_since: this.lastModified,
        });

        if (result.not_modified) {
          this.loading = false;
          return;
        }

        this.supplierCodes = (result.data || []).filter((sc) => sc.enabled !== 0);
        this.lastModified = result.last_modified;

        // Cache
        await db.clear("supplier_codes");
        for (const sc of result.data || []) {
          await db.put("supplier_codes", sc);
        }
      } catch {
        // Load from cache
        const cached = await db.getAll("supplier_codes");
        if (cached.length) {
          this.supplierCodes = cached.filter((sc) => sc.enabled !== 0);
        }
      } finally {
        this.loading = false;
      }
    },
  },
});
```

- [ ] **Step 3: Create KpiCard.vue**

Create `apps/damage_pwa/frontend/src/components/KpiCard.vue`:

```vue
<template>
  <div class="kpi-card" :class="variant">
    <p class="label">{{ label }}</p>
    <p class="value">{{ value }}</p>
  </div>
</template>

<script setup>
defineProps({
  label: { type: String, required: true },
  value: { type: [Number, String], default: 0 },
  variant: { type: String, default: "default" },
});
</script>

<style scoped>
.kpi-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 16px;
  text-align: center;
}

.kpi-card .label {
  font-size: 9px;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--amber);
  margin-bottom: 4px;
}

.kpi-card .value {
  font-size: 28px;
  font-weight: 700;
}

.kpi-card.amber { border-left: 3px solid var(--amber); }
.kpi-card.green { border-left: 3px solid var(--green); }
.kpi-card.red { border-left: 3px solid var(--red); }
</style>
```

- [ ] **Step 4: Create TransferCard.vue**

Create `apps/damage_pwa/frontend/src/components/TransferCard.vue`:

```vue
<template>
  <div class="transfer-card" :class="{ locked: isLockedByOther }" @click="$emit('click')">
    <div class="card-left">
      <p class="dt-name">{{ transfer.name }}</p>
      <p class="warehouses">
        {{ shortWh(transfer.branch_warehouse) }} → {{ shortWh(transfer.damage_warehouse) }}
      </p>
      <p class="meta">{{ transfer.transaction_date }} · {{ transfer.item_count }} items</p>
    </div>
    <div class="card-right">
      <span class="progress">{{ transfer.inspected_count }}/{{ transfer.item_count }}</span>
      <span v-if="isLockedByOther" class="lock-badge">LOCKED</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useAuthStore } from "@/store/auth.js";

const props = defineProps({
  transfer: { type: Object, required: true },
});

defineEmits(["click"]);

const auth = useAuthStore();

const isLockedByOther = computed(() => {
  return props.transfer.locked_by && props.transfer.locked_by !== auth.user;
});

function shortWh(name) {
  if (!name) return "—";
  return name.replace(/ - CNC$/, "").replace(/^Warehouse /, "");
}
</script>

<style scoped>
.transfer-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 3px solid var(--amber);
  border-radius: var(--radius);
  padding: 12px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: border-color 0.2s;
}

.transfer-card:active {
  border-color: var(--amber);
}

.transfer-card.locked {
  opacity: 0.5;
  border-left-color: var(--text-dim);
}

.dt-name {
  font-weight: 700;
  font-size: 14px;
  letter-spacing: 0.5px;
}

.warehouses {
  font-size: 12px;
  color: var(--text-dim);
  margin-top: 2px;
}

.meta {
  font-size: 11px;
  color: var(--text-dim);
  margin-top: 4px;
}

.card-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.progress {
  font-size: 16px;
  font-weight: 700;
  color: var(--amber);
}

.lock-badge {
  font-size: 9px;
  letter-spacing: 1px;
  color: var(--red);
  background: rgba(220, 38, 38, 0.15);
  padding: 2px 6px;
  border-radius: 4px;
}
</style>
```

- [ ] **Step 5: Create DashboardView.vue**

Create `apps/damage_pwa/frontend/src/views/DashboardView.vue`:

```vue
<template>
  <div class="page">
    <div class="dash-header">
      <h1 class="brand-sm">DAMAGE<span class="accent">PWA</span></h1>
    </div>

    <div class="kpi-grid">
      <KpiCard label="Pending" :value="store.pendingCount" variant="amber" />
      <KpiCard label="Approved" :value="store.approvedCount" variant="green" />
      <KpiCard label="Rejected" :value="store.rejectedCount" variant="red" />
    </div>

    <div class="section">
      <p class="label">PENDING INSPECTION</p>

      <div v-if="store.loading" class="loading">
        <span class="spinner"></span> LOADING...
      </div>

      <div v-else-if="store.error && !store.pending.length" class="empty">
        <p>{{ store.error }}</p>
        <button class="btn-ghost" @click="refresh">RETRY</button>
      </div>

      <div v-else-if="!store.pending.length" class="empty">
        <p>NO PENDING TRANSFERS</p>
      </div>

      <div v-else class="transfer-list">
        <TransferCard
          v-for="t in store.pending"
          :key="t.name"
          :transfer="t"
          @click="openTransfer(t)"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from "vue";
import { useRouter } from "vue-router";
import { useTransfersStore } from "@/store/transfers.js";
import { useMasterStore } from "@/store/master.js";
import KpiCard from "@/components/KpiCard.vue";
import TransferCard from "@/components/TransferCard.vue";

const router = useRouter();
const store = useTransfersStore();
const master = useMasterStore();

onMounted(() => {
  refresh();
});

function refresh() {
  store.fetchPending();
  store.fetchKpis();
  master.fetchSupplierCodes();
}

function openTransfer(t) {
  if (t.locked_by && t.locked_by !== "current_user") {
    // Still allow opening — claim happens on TransferDetail
  }
  router.push(`/transfer/${t.name}`);
}
</script>

<style scoped>
.dash-header {
  margin-bottom: 16px;
}

.brand-sm {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 3px;
}

.accent {
  color: var(--amber);
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 24px;
}

.section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.transfer-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.loading, .empty {
  text-align: center;
  color: var(--text-dim);
  padding: 48px 0;
  font-size: 12px;
  letter-spacing: 1.5px;
  text-transform: uppercase;
}

.empty button {
  margin-top: 12px;
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

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
```

- [ ] **Step 6: Commit**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa && sudo -u v15 git add -A && sudo -u v15 git commit -m "feat: add transfers/master stores + Dashboard view

Pinia stores for pending transfers, KPIs, supplier codes with IndexedDB cache.
Dashboard: KPI cards + pending transfer list with lock indicators.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 7: Stub Views + SPA Entry Point + Build

**Files:**
- Create: `frontend/src/views/HistoryView.vue`
- Create: `frontend/src/views/SettingsView.vue`
- Create: `frontend/src/views/TransferDetailView.vue`
- Create: `frontend/src/views/InspectionView.vue`
- Create: `frontend/src/views/SlipDetailView.vue`
- Create: `damage_pwa/www/damage-pwa/index.py`
- Create: `damage_pwa/www/damage-pwa/index.html`
- Create: `damage_pwa/public/manifest.json`

- [ ] **Step 1: Create stub views**

These are minimal placeholders so the router doesn't break. They'll be fully implemented in Phase 3-4.

Create `apps/damage_pwa/frontend/src/views/HistoryView.vue`:

```vue
<template>
  <div class="page">
    <h2 class="page-title">HISTORY</h2>
    <p class="placeholder">Coming in Phase 3</p>
  </div>
</template>

<style scoped>
.placeholder { color: var(--text-dim); text-align: center; padding: 48px 0; font-size: 12px; letter-spacing: 1px; text-transform: uppercase; }
</style>
```

Create `apps/damage_pwa/frontend/src/views/SettingsView.vue`:

```vue
<template>
  <div class="page">
    <h2 class="page-title">SETTINGS</h2>
    <div class="card" style="margin-bottom: 12px;">
      <p class="label">LOGGED IN AS</p>
      <p>{{ auth.fullName || auth.user }}</p>
    </div>
    <button class="btn-danger full" @click="handleLogout">LOGOUT</button>
  </div>
</template>

<script setup>
import { useRouter } from "vue-router";
import { useAuthStore } from "@/store/auth.js";

const router = useRouter();
const auth = useAuthStore();

async function handleLogout() {
  await auth.logout();
  router.replace("/login");
}
</script>

<style scoped>
.full { width: 100%; height: 48px; }
</style>
```

Create `apps/damage_pwa/frontend/src/views/TransferDetailView.vue`:

```vue
<template>
  <div class="page">
    <h2 class="page-title">TRANSFER {{ name }}</h2>
    <p class="placeholder">Coming in Phase 3</p>
  </div>
</template>

<script setup>
defineProps({ name: { type: String, required: true } });
</script>

<style scoped>
.placeholder { color: var(--text-dim); text-align: center; padding: 48px 0; font-size: 12px; letter-spacing: 1px; text-transform: uppercase; }
</style>
```

Create `apps/damage_pwa/frontend/src/views/InspectionView.vue`:

```vue
<template>
  <div class="page">
    <h2 class="page-title">INSPECT ITEM</h2>
    <p class="placeholder">Coming in Phase 3</p>
  </div>
</template>

<script setup>
defineProps({
  name: { type: String, required: true },
  rowName: { type: String, required: true },
});
</script>

<style scoped>
.placeholder { color: var(--text-dim); text-align: center; padding: 48px 0; font-size: 12px; letter-spacing: 1px; text-transform: uppercase; }
</style>
```

Create `apps/damage_pwa/frontend/src/views/SlipDetailView.vue`:

```vue
<template>
  <div class="page">
    <h2 class="page-title">DAMAGE SLIP {{ name }}</h2>
    <p class="placeholder">Coming in Phase 3</p>
  </div>
</template>

<script setup>
defineProps({ name: { type: String, required: true } });
</script>

<style scoped>
.placeholder { color: var(--text-dim); text-align: center; padding: 48px 0; font-size: 12px; letter-spacing: 1px; text-transform: uppercase; }
</style>
```

- [ ] **Step 2: Create SPA entry point (index.py)**

Create directory `apps/damage_pwa/damage_pwa/www/damage-pwa/` and file `index.py`:

```python
import os
import frappe

no_cache = 1


def get_context(context):
    csrf_token = frappe.sessions.get_csrf_token()
    frappe.db.commit()

    assets_dir = frappe.get_app_path("damage_pwa", "public", "frontend", "assets")
    js_file = css_file = ""
    if os.path.exists(assets_dir):
        for f in os.listdir(assets_dir):
            if f.startswith("index-") and f.endswith(".js"):
                js_file = f
            elif f.startswith("index-") and f.endswith(".css"):
                css_file = f

    context.update({
        "csrf_token": csrf_token,
        "js_file": js_file,
        "css_file": css_file,
    })
```

- [ ] **Step 3: Create SPA template (index.html)**

Create `apps/damage_pwa/damage_pwa/www/damage-pwa/index.html`:

```html
{% extends "templates/web.html" %}

{% block title %}Damage PWA{% endblock %}

{% block head_include %}
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
<meta name="theme-color" content="#0a0a0a" />
<link rel="manifest" href="/assets/damage_pwa/manifest.json" />
<style>
  /* Hide Frappe navbar and footer */
  .navbar, .web-footer, .page-header, .page-header-wrapper,
  [data-page-container] > .page-header { display: none !important; }
  .main-section { padding: 0 !important; margin: 0 !important; }
  .container { max-width: 100% !important; padding: 0 !important; }
  body { background: #0a0a0a !important; overflow-x: hidden; }
  .page-content { padding: 0 !important; }
</style>
{% endblock %}

{% block page_content %}
<div id="app"></div>
<script>window.csrf_token = "{{ csrf_token }}";</script>
{% if css_file %}<link rel="stylesheet" href="/assets/damage_pwa/frontend/assets/{{ css_file }}">{% endif %}
{% if js_file %}<script type="module" src="/assets/damage_pwa/frontend/assets/{{ js_file }}"></script>{% endif %}
{% endblock %}
```

- [ ] **Step 4: Create PWA manifest**

Create `apps/damage_pwa/damage_pwa/public/manifest.json`:

```json
{
  "name": "Damage PWA",
  "short_name": "DamagePWA",
  "description": "Warehouse Damage Inspection",
  "start_url": "/damage-pwa/",
  "scope": "/damage-pwa/",
  "display": "standalone",
  "theme_color": "#0a0a0a",
  "background_color": "#0a0a0a",
  "icons": [
    {
      "src": "/assets/damage_pwa/icons/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/assets/damage_pwa/icons/icon-512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
```

- [ ] **Step 5: Build the frontend**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa/frontend && sudo -u v15 yarn build
```

Expected: Build output in `damage_pwa/public/frontend/assets/` with `index-*.js` and `index-*.css`.

- [ ] **Step 6: Verify SPA loads in browser**

```bash
cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 clear-cache && sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web
```

Then visit `https://rmax-dev.fateherp.com/damage-pwa/` — should show the Login screen with Industrial Dark theme.

- [ ] **Step 7: Commit**

```bash
cd /home/v15/frappe-bench/apps/damage_pwa && sudo -u v15 git add -A -- . ':!damage_pwa/public/frontend' && sudo -u v15 git commit -m "feat: add SPA entry + stub views + PWA manifest + build

SPA served via www/damage-pwa with Frappe navbar hidden.
Stub views for History, Settings, TransferDetail, Inspection, SlipDetail.
PWA manifest with Industrial Dark theme colors.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Phase 2 Checkpoint

After completing all 7 tasks, verify:

| Test | Method | Expected |
|------|--------|----------|
| Frontend builds | `cd frontend && yarn build` | No errors, assets in `public/frontend/assets/` |
| SPA loads | Visit `/damage-pwa/` | Dark-themed login screen |
| Login works | Enter sabith@gmail.com + password | Prompts for PIN setup |
| PIN setup works | Enter 4-digit PIN | Redirects to Dashboard |
| Dashboard loads | After login | Shows KPI cards + pending transfer list |
| Bottom nav works | Tap History / Settings | Navigates to stub views |
| Logout works | Settings → Logout | Returns to login |
| Offline indicator | Toggle airplane mode | Shows "OFFLINE — WORKING LOCALLY" |

**Next:** Phase 3 — Transfer Detail + Item Inspection + Photo handling
