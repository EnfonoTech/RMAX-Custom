# Damage PWA → Capacitor Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Each task's steps use checkbox (`- [ ]`) syntax for tracking.

**Date:** 2026-04-17
**Goal:** Replace the Trusted Web Activity (TWA) wrapper with a Capacitor-based native Android app. Same Vue 3 SPA, new shell. Eliminate all Chrome-profile-state issues that broke the current TWA.

---

## Why This Migration

The current TWA approach (Android app that opens Chrome Custom Tabs to `https://rmax-dev.fateherp.com/damage-pwa/`) failed in production for three connected reasons:

1. **Shared Chrome state** — TWA uses the user's regular Chrome profile. Chrome's cache, cookies, Service Worker registry, and HSTS state can corrupt under heavy iteration (or just naturally over time). When corrupted, every TWA user on that device is stuck with "This site can't be reached" and the only fix is Android Settings → Apps → Chrome → Clear Data.

2. **Fragile offline** — Our hand-rolled Service Worker precaches by fetching `/damage-pwa/` and parsing asset URLs from the HTML at install time. Any hiccup during that window (DNS flake, server restart, airplane mode) and the SW registers with an empty cache. Offline never works on that device until it's reset.

3. **Chrome version lottery** — Warehouse phones run whatever Chrome version shipped when the device was factory-reset. Some of these have broken `storage.persist()`, broken Background Sync, or different Cache Storage eviction heuristics.

Capacitor fixes all three: the WebView is bundled with the app, storage is isolated per-app, and no Chrome profile state can corrupt it.

## Reusing What We Have

- **100% of the Vue 3 SPA** — every view, store, component, utility survives
- **Industrial blue theme + all CSS** — survives
- **Backend APIs** — survive unchanged
- **Keystore** — reuse `damage-pwa.keystore` so updates install over v0.6.x cleanly

What we're replacing:
- Android TWA project (`/Users/sayanthns/Documents/RMAX/damage-pwa-android/`) → Capacitor project (`/Users/sayanthns/Documents/RMAX/damage-pwa-capacitor/`)
- Our `sw.js` → `@capacitor/filesystem` + `@capacitor/preferences` for offline storage (no Service Worker in the native app)
- `navigator.onLine` → `@capacitor/network`
- `<input type="file">` camera → `@capacitor/camera` (optional, with web fallback)
- Cookie-based session → Frappe API key/secret auth stored in `@capacitor/preferences`

## Architecture After Migration

```
┌─────────────────────────────────────────────────┐
│  Android Device                                 │
│  ┌───────────────────────────────────────────┐  │
│  │  RMAX WH (Capacitor app)                  │  │
│  │  ┌─────────────────────────────────────┐  │  │
│  │  │  WebView                            │  │  │
│  │  │  (serves local bundled SPA)         │  │  │
│  │  │  - file:///android_asset/public/... │  │  │
│  │  │  - Vue + Pinia + IndexedDB          │  │  │
│  │  └─────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────────────────┐  │  │
│  │  │  Capacitor Bridge                   │  │  │
│  │  │  - Camera, Filesystem, Network,     │  │  │
│  │  │    Preferences, App, SplashScreen   │  │  │
│  │  └─────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────┘  │
│                        │                         │
│                        │ HTTPS (API only)        │
│                        ▼                         │
└─────────────────────────────────────────────────┘
                         │
            ┌────────────┴────────────┐
            │  Frappe (existing)      │
            │  /api/method/...        │
            └─────────────────────────┘
```

Key change: the SPA is **bundled with the app** (local assets, never fetched over HTTP). Only the API calls go to the server. This eliminates the entire class of "site can't be reached" errors on cold launch.

---

## File Map

```
/Users/sayanthns/Documents/RMAX/damage-pwa-capacitor/       # NEW — Capacitor project
├── package.json                # Capacitor deps
├── capacitor.config.ts         # App ID, WebView config, plugins
├── index.html                  # WebView entry (links to bundled SPA)
├── src/                        # Vue SPA — COPIED from apps/damage_pwa/frontend/src
│   ├── main.js                 # Bootstrap with Capacitor-aware adapters
│   ├── App.vue                 # Reused as-is
│   ├── router/index.js         # Reused as-is
│   ├── store/                  # Reused; auth.js uses API keys instead of cookies
│   ├── views/                  # Reused as-is
│   ├── components/             # Reused as-is
│   ├── utils/
│   │   ├── frappe.js           # MODIFIED — uses Authorization: token header + API base URL const
│   │   ├── db.js               # MODIFIED — Capacitor Preferences/Filesystem adapters
│   │   ├── online.js           # MODIFIED — uses @capacitor/network
│   │   ├── photo.js            # MODIFIED — uses @capacitor/camera with web fallback
│   │   └── platform.js         # NEW — feature detection helpers
├── vite.config.js              # Build to `www/` for Capacitor
├── android/                    # Generated by `npx cap add android`
│   ├── app/
│   │   ├── build.gradle        # applicationId com.rmax.damage_pwa (match TWA)
│   │   └── src/main/
│   │       ├── AndroidManifest.xml
│   │       ├── assets/         # SPA bundle lands here after sync
│   │       └── res/            # Icons from existing PWA assets
│   └── keystore/
│       └── damage-pwa.keystore # COPIED from TWA project
└── README.md                   # Build + distribute instructions

# Server side — MINIMAL changes
/home/v15/frappe-bench/apps/damage_pwa/damage_pwa/api/auth.py
  + login_with_pin()            # NEW — accepts email + PIN, returns api_key + api_secret
```

---

## Task 1 — Scaffold Capacitor Project

**Files:**
- Create: `/Users/sayanthns/Documents/RMAX/damage-pwa-capacitor/package.json`
- Create: `/Users/sayanthns/Documents/RMAX/damage-pwa-capacitor/capacitor.config.ts`
- Create: `/Users/sayanthns/Documents/RMAX/damage-pwa-capacitor/vite.config.js`

**Steps:**

- [ ] **Step 1: Init project + install Capacitor**

  ```bash
  mkdir -p /Users/sayanthns/Documents/RMAX/damage-pwa-capacitor
  cd /Users/sayanthns/Documents/RMAX/damage-pwa-capacitor

  npm init -y
  npm install vue@^3.4 vue-router@^4.3 pinia@^2.1 idb@^8.0
  npm install --save-dev vite@^5.4 @vitejs/plugin-vue@^5.0

  npm install @capacitor/core@^6 @capacitor/cli@^6
  npm install @capacitor/android@^6
  npm install @capacitor/camera @capacitor/filesystem @capacitor/preferences \
               @capacitor/network @capacitor/app @capacitor/splash-screen \
               @capacitor/status-bar
  ```

- [ ] **Step 2: Write `capacitor.config.ts`**

  ```typescript
  import type { CapacitorConfig } from '@capacitor/cli';

  const config: CapacitorConfig = {
    appId: 'com.rmax.damage_pwa',
    appName: 'RMAX WH',
    webDir: 'www',
    server: {
      // Use bundled assets in production; only API calls go to the server.
      androidScheme: 'https',
      cleartext: false,
    },
    plugins: {
      SplashScreen: {
        launchShowDuration: 500,
        backgroundColor: '#dd2023',
        androidSplashResourceName: 'splash',
        showSpinner: false,
      },
      StatusBar: {
        backgroundColor: '#dd2023',
        style: 'LIGHT',
      },
    },
  };

  export default config;
  ```

- [ ] **Step 3: Write `vite.config.js` (build to `www/` not `dist/`)**

  ```javascript
  import path from 'path';
  import { defineConfig } from 'vite';
  import vue from '@vitejs/plugin-vue';

  export default defineConfig({
    plugins: [vue()],
    base: './',  // RELATIVE paths — critical for Capacitor's local file:// WebView
    build: {
      outDir: 'www',
      emptyOutDir: true,
      target: 'es2020',
    },
    resolve: {
      alias: { '@': path.resolve(__dirname, 'src') },
    },
    server: {
      port: 5173,
    },
  });
  ```

- [ ] **Step 4: Verify scaffold**

  ```bash
  npx cap --help  # sanity check
  ```

---

## Task 2 — Copy and Adapt Vue SPA

**Files:**
- Copy from: `/home/v15/frappe-bench/apps/damage_pwa/frontend/src/` (on the server; use git clone or rsync)
- Copy to: `/Users/sayanthns/Documents/RMAX/damage-pwa-capacitor/src/`

**Steps:**

- [ ] **Step 1: Pull the latest Vue SPA source from the server locally**

  ```bash
  cd /Users/sayanthns/Documents/RMAX
  git clone https://github.com/EnfonoTech/damage-pwa.git damage-pwa-src
  cd damage-pwa-src
  git checkout develop
  ```

  Copy the `frontend/src/` tree into the Capacitor project:

  ```bash
  cp -r /Users/sayanthns/Documents/RMAX/damage-pwa-src/frontend/src \
        /Users/sayanthns/Documents/RMAX/damage-pwa-capacitor/
  cp /Users/sayanthns/Documents/RMAX/damage-pwa-src/frontend/index.html \
     /Users/sayanthns/Documents/RMAX/damage-pwa-capacitor/
  ```

- [ ] **Step 2: Create `src/utils/platform.js`**

  Feature-detection helpers used by all adapters. Detect Capacitor, then fall back to web.

  ```javascript
  export const isNative = () => {
    try {
      return !!window.Capacitor && window.Capacitor.isNativePlatform?.();
    } catch { return false; }
  };

  export const API_BASE = 'https://rmax-dev.fateherp.com';
  ```

- [ ] **Step 3: Rewrite `src/utils/frappe.js`**

  Remove cookie-based auth; use `Authorization: token <key>:<secret>` with the API base URL from `platform.js`. Keep timeouts. Drop CSRF handling entirely (API keys don't need CSRF).

  Key changes:
  - `import { API_BASE } from './platform.js'` at top
  - `fetch(\`${API_BASE}/api/method/${method}\`, ...)` instead of relative URL
  - Read API credentials from the new `preferences` adapter (`getApiKey()`, `getApiSecret()`)
  - Headers: `Authorization: token ${key}:${secret}` (NOT cookies)
  - Remove `getCsrfToken()`, `refreshCsrfToken()`, all CSRF retry logic
  - Keep `fetchWithTimeout`, `stripHtml`, `extractError`, `uploadFile`
  - Expose a new `setCredentials({apiKey, apiSecret})` that writes to preferences

- [ ] **Step 4: Rewrite `src/utils/db.js`**

  IndexedDB is flaky on some WebViews. Replace with a dual-backend:
  - `@capacitor/preferences` for small structured records (auth, queue metadata)
  - `@capacitor/filesystem` for photo blobs (write to `DATA` directory)

  Export the same interface we use today (`get`, `put`, `getAll`, `del`, `clear`, `clearAll`, `add`, `set`) so stores don't need any changes. Under the hood, decide backend based on store name:
  - `auth`, `supplier_codes`, `transfers` → Preferences (JSON-serialized, keyed by `store:key`)
  - `inspection_queue`, `action_queue` → Preferences (array serialized under `inspection_queue`, auto-incrementing id in memory)
  - `photos` → Preferences for metadata + Filesystem for blob file paths

  On web, fall through to the existing IndexedDB implementation (so the same code runs in `npm run dev` browser mode).

- [ ] **Step 5: Rewrite `src/utils/online.js`**

  Use `@capacitor/network` when native, `navigator.onLine` + `online`/`offline` events on web.

  ```javascript
  import { ref, onMounted } from 'vue';
  import { Network } from '@capacitor/network';
  import { isNative } from './platform.js';

  const online = ref(true);
  let initialized = false;

  async function initOnce() {
    if (initialized) return;
    initialized = true;
    if (isNative()) {
      const status = await Network.getStatus();
      online.value = status.connected;
      Network.addListener('networkStatusChange', (s) => online.value = s.connected);
    } else {
      online.value = navigator.onLine;
      window.addEventListener('online', () => online.value = true);
      window.addEventListener('offline', () => online.value = false);
    }
  }

  export function useOnline() { initOnce(); return online; }
  export function isOnline() { initOnce(); return online.value; }
  ```

- [ ] **Step 6: Rewrite `src/utils/photo.js`**

  Use `@capacitor/camera` for native capture (gives us native UI, proper permissions, file URIs pointing to `DATA` storage). Fall back to `<input type="file">` on web.

  The existing `capturePhoto()` signature stays — returns `{ url: "photo:<id>", thumb: "data:image/jpeg;base64..." }` — but instead of storing a Blob in IDB, we store the file URI returned by Camera and a small thumbnail data URL in Preferences.

  Sync engine's `drainPhotos` needs a small change: read file from Filesystem + wrap in FormData instead of reading blob from IDB.

- [ ] **Step 7: Rewrite `src/store/auth.js`**

  Login flow becomes:
  1. User enters email + password → server returns session cookie AND generates API key/secret (see Task 4)
  2. User sets 4-digit PIN → PIN hash stored in Preferences
  3. API key/secret also stored in Preferences
  4. All subsequent API calls use token auth; cookie can expire harmlessly

  Remove all the cookie/CSRF-based session revalidation logic — API tokens don't expire the same way. Add an `authenticate()` on boot that calls a lightweight `auth.ping` endpoint with the stored token to validate credentials.

- [ ] **Step 8: Adapt `main.js`**

  Remove all Service Worker registration code. Add Capacitor-specific bootstrap:
  ```javascript
  import { SplashScreen } from '@capacitor/splash-screen';
  import { StatusBar } from '@capacitor/status-bar';
  import { isNative } from './utils/platform.js';

  if (isNative()) {
    StatusBar.setBackgroundColor({ color: '#dd2023' });
    SplashScreen.hide();
  }
  ```

---

## Task 3 — Server-side API key authentication

**Files:**
- Modify: `/home/v15/frappe-bench/apps/damage_pwa/damage_pwa/api/auth.py`

**Steps:**

- [ ] **Step 1: Add `login_with_pin` endpoint**

  Accepts `email` + `pin`. Validates PIN against stored hash. On success, generates (or reuses) a Frappe API key/secret for that user and returns them.

  ```python
  @frappe.whitelist(allow_guest=True, methods=["POST"])
  def login_with_pin(email, pin):
      """Validate PIN and return API credentials for token-based auth."""
      if not email or not pin:
          frappe.throw(_("Email and PIN required"))

      user = frappe.db.get_value("User", {"email": email}, "name")
      if not user:
          frappe.throw(_("Invalid credentials"), frappe.AuthenticationError)

      pin_name = frappe.db.get_value("Damage PWA Pin", {"user": user}, "name")
      if not pin_name:
          frappe.throw(_("No PIN set — login with password first"))

      doc = frappe.get_doc("Damage PWA Pin", pin_name)
      import bcrypt
      if not bcrypt.checkpw(pin.encode("utf-8"), doc.pin_hash.encode("utf-8")):
          frappe.throw(_("Invalid credentials"), frappe.AuthenticationError)

      # Check Damage User role
      user_doc = frappe.get_doc("User", user)
      if "Damage User" not in [r.role for r in user_doc.roles]:
          frappe.throw(_("Not authorized"), frappe.PermissionError)

      # Generate or return existing API credentials
      api_secret = frappe.generate_hash(length=15)
      user_doc.api_key = user_doc.api_key or frappe.generate_hash(length=15)
      user_doc.api_secret = api_secret
      user_doc.flags.ignore_permissions = True
      user_doc.save(ignore_permissions=True)
      frappe.db.commit()

      return {
          "user": user,
          "full_name": user_doc.full_name,
          "api_key": user_doc.api_key,
          "api_secret": api_secret,
          "roles": [r.role for r in user_doc.roles],
      }
  ```

- [ ] **Step 2: Add `ping` endpoint for boot-time token validation**

  ```python
  @frappe.whitelist()
  def ping():
      assert_damage_user()
      return {
          "user": frappe.session.user,
          "timestamp": str(frappe.utils.now_datetime()),
      }
  ```

- [ ] **Step 3: Deploy + commit**

  ```bash
  curl -X POST ... # base64 the file, deploy as we've been doing
  cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 clear-cache
  sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web
  cd /home/v15/frappe-bench/apps/damage_pwa && sudo -u v15 git add -A
  sudo -u v15 git commit -m "feat: add login_with_pin + ping endpoints for Capacitor token auth"
  ```

---

## Task 4 — Add Android Platform

**Files:**
- Generated: `/Users/sayanthns/Documents/RMAX/damage-pwa-capacitor/android/` (whole tree)
- Modify: `android/app/build.gradle` (signing config)
- Copy: `damage-pwa.keystore` from existing TWA project

**Steps:**

- [ ] **Step 1: Initial build + add Android**

  ```bash
  cd /Users/sayanthns/Documents/RMAX/damage-pwa-capacitor
  npm run build               # builds `www/`
  npx cap add android         # generates android/ project
  npx cap sync android        # copies www/ to android/app/src/main/assets/public/
  ```

- [ ] **Step 2: Copy keystore**

  ```bash
  mkdir -p android/keystore
  cp /Users/sayanthns/Documents/RMAX/damage-pwa-android/keystore/damage-pwa.keystore \
     android/keystore/
  ```

- [ ] **Step 3: Configure signing in `android/app/build.gradle`**

  Add to the `android { ... }` block:
  ```gradle
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
  }
  ```

- [ ] **Step 4: Set applicationId to match existing TWA**

  In `android/app/build.gradle` `defaultConfig`, confirm `applicationId 'com.rmax.damage_pwa'` and bump `versionCode` to 10, `versionName` to '1.0.0'.

- [ ] **Step 5: Configure icons**

  Copy the 512×512 RMAX logo into `android/app/src/main/res/mipmap-xxxhdpi/ic_launcher.png` and downscale for each density. Or use Android Studio's Image Asset Studio.

- [ ] **Step 6: Sanity build**

  ```bash
  cd android
  ./gradlew assembleDebug 2>&1 | tail -10
  # Expect: BUILD SUCCESSFUL
  ```

---

## Task 5 — Build, Sign, Install, Test

**Steps:**

- [ ] **Step 1: Production build**

  ```bash
  cd /Users/sayanthns/Documents/RMAX/damage-pwa-capacitor
  npm run build
  npx cap sync android
  cd android
  KEYSTORE_PASSWORD=changeit KEY_PASSWORD=changeit ./gradlew assembleRelease
  cp app/build/outputs/apk/release/app-release.apk ../rmax-wh-v1.0.0.apk
  ```

- [ ] **Step 2: Verify signature matches old TWA**

  ```bash
  $ANDROID_HOME/build-tools/34.0.0/apksigner verify --print-certs rmax-wh-v1.0.0.apk | grep SHA-256
  # Must match: 5eaf79664158924cef80f927e8ff3335b9b568366795bf452760476218ab5d5a
  ```

  If fingerprint matches, this APK installs as an UPGRADE over v0.6.0 on the test phone. Otherwise it'll force an uninstall first.

- [ ] **Step 3: Sideload + test**

  Transfer APK to phone (AirDrop to self / Drive / USB). Install. Expect:
  - First launch: splash screen for ~500ms, then login screen (no previous credentials carry over from TWA — user logs in once more)
  - Email + password → "SET PIN" screen → PIN entered → Dashboard with pending transfers
  - Settings → confirm version reads "1.0.0 · build 10 · Capacitor"
  - Open a transfer → inspect an item → take a photo with Camera → save & next
  - Approve the transfer
  - Turn wifi OFF → relaunch app → should open straight to Dashboard with cached data
  - Turn wifi ON → settings → force sync → see queue drain

- [ ] **Step 4: If Chromium WebView fails camera permissions**

  Add to `android/app/src/main/AndroidManifest.xml` under `<manifest>`:
  ```xml
  <uses-permission android:name="android.permission.CAMERA"/>
  <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" android:maxSdkVersion="32"/>
  <uses-permission android:name="android.permission.READ_MEDIA_IMAGES"/>
  ```

  Rebuild + retest.

---

## Task 6 — Documentation + Rollout

**Files:**
- Create: `/Users/sayanthns/Documents/RMAX/damage-pwa-capacitor/README.md`
- Update: Existing TWA project README with "DEPRECATED — migrated to Capacitor"

**Steps:**

- [ ] **Step 1: Write Capacitor README**

  Include:
  - Setup: JDK 17, Android SDK 34, Node 20
  - Build: `npm run build && npx cap sync android && cd android && ./gradlew assembleRelease`
  - Signing: env vars for keystore password
  - Update flow: bump `versionCode` + `versionName`, rebuild, distribute APK
  - How to reset app state on device (Settings → Apps → RMAX WH → Clear Data)
  - Known differences from TWA: API key auth instead of cookies, native camera instead of web input, Preferences+Filesystem instead of IndexedDB

- [ ] **Step 2: User migration note**

  When distributing v1.0.0 Capacitor APK:
  - Install over v0.6.0 TWA → APK upgrade works because same signing cert
  - User sees login screen once (old TWA session doesn't transfer — intentional, clean slate)
  - Users who had unsynced queue in the TWA lose those queued items (announce in advance; drain them online first)

- [ ] **Step 3: Deprecate TWA directory**

  ```bash
  cd /Users/sayanthns/Documents/RMAX/damage-pwa-android
  echo "DEPRECATED — migrated to Capacitor at ../damage-pwa-capacitor/" > DEPRECATED.md
  git add DEPRECATED.md && git commit -m "deprecate: replaced by Capacitor project"
  ```

- [ ] **Step 4: Production rollout checklist**

  - [ ] All Damage Users drain their queue online BEFORE installing v1.0.0
  - [ ] v1.0.0 APK tested end-to-end on the test phone (online + offline + camera + sync)
  - [ ] APK uploaded to Drive/Slack channel
  - [ ] Message sent to all users with install instructions
  - [ ] One user installs + confirms login works
  - [ ] Rest of team installs
  - [ ] Monitor `Damage PWA Pin` DocType + recent Error Logs for 48 hours

---

## Checkpoint — After Task 5

At this point, the v1.0.0 Capacitor APK should work end-to-end on the test phone:
- Cold online launch: login → PIN → Dashboard
- Cold offline launch (with warm cache): straight to Dashboard
- Photo capture via native camera
- Queue + sync via Preferences + Filesystem
- No "This site can't be reached" possible because the SPA is bundled, not fetched

If anything regresses compared to the TWA, fix before Task 6 (rollout).

---

## Rollback Plan

If v1.0.0 hits a blocker on rollout:
- Keep the TWA build in user's hands — they install v0.6.0 again over the broken v1.0.0 (same cert → works)
- Old server state (cookies, CSRF, SW) still supported by the Vue SPA at `/damage-pwa/`
- Both apps coexist on the server until Capacitor is stable

---

## Estimated Effort

- Task 1 (scaffold): 45 min
- Task 2 (adapt SPA): 90 min — the bulk of the work
- Task 3 (server auth endpoint): 30 min
- Task 4 (Android platform): 30 min
- Task 5 (build + test): 60 min
- Task 6 (docs + rollout): 30 min

**Total: ~4.5 hours focused work in one session.**

---
---

# Platform Extension — ERPNext-PWA-Offline Framework

**Added:** 2026-04-17
**Intent:** Ship Damage PWA as the first consumer of a **reusable offline-first framework** for ERPNext PWAs. After this migration, any future PWA (Van Sales refactor, warehouse scanner, delivery app, etc.) starts with offline + auth + sync working in minutes, not weeks.

**Key insight from reviewing Van Sales PWA:** it uses React, Damage uses Vue. The framework must be **view-layer-agnostic** — pure JS modules that either framework can import.

## Shift in Approach (applies retroactively to Tasks 1–2)

Instead of one monolithic Capacitor project, the directory structure is:

```
/Users/sayanthns/Documents/RMAX/
├── erpnext-pwa-core/           # NEW — framework-agnostic vanilla JS + Capacitor template
│   └── (see Task 7)
├── damage-pwa-capacitor/       # FIRST CONSUMER — Vue, imports erpnext-pwa-core
└── van-sales-pwa-capacitor/    # FUTURE — React, imports erpnext-pwa-core
```

And on the Frappe server:

```
/home/v15/frappe-bench/apps/
├── frappe_pwa_core/            # NEW Frappe app — shared PIN + auth primitives
├── damage_pwa/                 # Becomes a thin consumer: workflows + views only
└── fateh_pwa/                  # (Van Sales) future consumer
```

## Execution Order (revised)

| Phase | Scope | Timing |
|---|---|---|
| Phase 1: Monolithic Capacitor | Execute Tasks 1-5 of this plan AS WRITTEN, putting all core modules inside `damage-pwa-capacitor/src/utils/` | NEXT SESSION |
| Phase 2: Test + stabilize | Tasks 6 rollout. Get real users on v1.0.0. Verify offline works on actual warehouse devices for 1-2 weeks | WEEK 2 |
| Phase 3: Extract framework | Task 7-9 below. Pull the proven-in-production modules out of `damage-pwa-capacitor/` into `erpnext-pwa-core/`. Refactor damage-pwa to import from it | WEEK 3 |
| Phase 4: Second consumer | Scaffold Van Sales v2 using the framework — proves reusability | WEEK 4+ |

**Why monolithic first:** Premature abstraction is the enemy. We don't know what's truly generic until we've built one real consumer and are about to build a second. Ship Damage PWA monolithically, stabilize, then extract.

---

## Task 7 — Extract `erpnext-pwa-core` package (Phase 3)

**Prerequisite:** Damage PWA v1.0.0 has been running in production on warehouse phones for at least 1 week without offline-related bugs.

### 7.1 — Scaffold the core package

- [ ] Create `/Users/sayanthns/Documents/RMAX/erpnext-pwa-core/`
- [ ] `npm init` with `"name": "@enfono/erpnext-pwa-core"`, private (or publish to a private registry)
- [ ] Directory layout:

```
erpnext-pwa-core/
├── src/
│   ├── api/
│   │   ├── client.js           # Generic API wrapper with timeout + token auth
│   │   └── errors.js           # stripHtml, extractError, friendly error mapping
│   ├── auth/
│   │   ├── pin.js              # PIN pad logic, hash validation
│   │   └── session.js          # API key/secret storage, authenticate(), logout()
│   ├── storage/
│   │   ├── index.js            # Unified API: get/put/getAll/del/clear
│   │   ├── adapters/
│   │   │   ├── capacitor.js    # Preferences + Filesystem
│   │   │   └── web.js          # IndexedDB (for PWA mode)
│   │   └── plainify.js         # toPlain() from our earlier Vue-reactive fix
│   ├── sync/
│   │   ├── engine.js           # drainAll, bounded parallel pool, backoff
│   │   ├── config.js           # Queue config schema, unrecoverable patterns
│   │   └── retry.js            # Backoff, MAX_ATTEMPTS, isUnrecoverable
│   ├── offline/
│   │   └── network.js          # useOnline, isOnline, native + web
│   ├── capture/
│   │   ├── camera.js           # capturePhoto, compress, thumb, native + web
│   │   └── compress.js         # Canvas-based JPEG compression
│   ├── platform/
│   │   └── index.js            # isNative, API_BASE constant
│   └── index.js                # Public re-exports
├── capacitor-template/         # Starter capacitor.config.ts + android/ shell
├── docs/
│   ├── architecture.md         # "How offline works"
│   ├── building-a-pwa.md       # Step-by-step "build your first ERPNext PWA"
│   ├── sync-config.md          # Declarative sync queue schema
│   └── plugin-catalog.md       # Which Capacitor plugins + why
└── README.md
```

### 7.2 — Generic sync engine with declarative config

Current `sync-engine.js` hard-codes `"damage_pwa.api.inspect.save_item_inspection"`. New schema:

```typescript
// sync-config.js (per consumer)
export default {
  queues: [
    {
      name: 'inspection_queue',          // IDB/Preferences store name
      apiMethod: 'damage_pwa.api.inspect.save_item_inspection',
      toArgs: (q) => ({ transfer_name: q.transferName, row_name: q.rowName, ... }),
      hasPhotoPlaceholders: (q) => ['images', 'image_2', 'image_3']
        .some((s) => q[s]?.startsWith('photo:')),
      concurrency: 3,
    },
    {
      name: 'action_queue',
      apiMethod: (q) => q.action === 'approve'
        ? 'damage_pwa.api.inspect.approve_transfer'
        : 'damage_pwa.api.inspect.reject_transfer',
      toArgs: (q) => ({ name: q.transferName, reason: q.reason, ... }),
      concurrency: 1,
      dependsOn: 'inspection_queue',       // Wait until this queue is empty
    },
  ],
  photos: {
    storeName: 'photos',
    uploadMethod: 'upload_file',
    concurrency: 4,
  },
  unrecoverableErrors: [
    /not in pending inspection/i,
    /row .* not found/i,
    /do not hold the lock/i,
    /locked by/i,
    /already submitted/i,
    // consumer can append their own
  ],
};
```

The engine reads this config and drives the drain loop generically. Damage PWA and Van Sales both import `runSync(config)`.

### 7.3 — Shared server-side Frappe app

Create `/home/v15/frappe-bench/apps/frappe_pwa_core/`:

```
frappe_pwa_core/
├── frappe_pwa_core/
│   ├── api/
│   │   └── auth.py             # login_with_pin, setup_pin, change_pin, validate_session, ping
│   ├── doctype/
│   │   └── pwa_pin/            # Generic (not "Damage PWA Pin"); linked to User
│   ├── utils.py                # assert_role(role_name), add_pwa_headers()
│   └── hooks.py                # Minimal
├── pyproject.toml
└── README.md
```

Damage PWA's `damage_pwa/api/auth.py` becomes a thin shim: `from frappe_pwa_core.api.auth import login_with_pin, setup_pin` and passes the `Damage User` role name as an arg. Van Sales does the same with `Sales User` or whatever role gates it.

Migration of existing `Damage PWA Pin` → `PWA Pin` DocType:
```python
# In frappe_pwa_core install hook
def after_install():
    frappe.db.sql("""
      INSERT INTO `tabPWA Pin` (name, user, pin_hash, created_at, owner, creation, modified, modified_by)
      SELECT name, user, pin_hash, created_at, owner, creation, modified, modified_by
      FROM `tabDamage PWA Pin`
      ON DUPLICATE KEY UPDATE pin_hash = VALUES(pin_hash)
    """)
```

### 7.4 — Consumer refactor

Modify `damage-pwa-capacitor/` to import from `erpnext-pwa-core`:

```javascript
// Before (monolithic):
import { call } from './utils/frappe.js';
import { capturePhoto } from './utils/photo.js';

// After (framework):
import { apiCall, capturePhoto, runSync, setupAuth } from '@enfono/erpnext-pwa-core';
import syncConfig from './sync-config.js';

// Boot:
setupAuth({ apiBase: 'https://rmax-dev.fateherp.com', role: 'Damage User' });
runSync(syncConfig);
```

Consumer is now ~200 lines of configuration + view-layer code. The 2,000+ lines of offline/sync/storage/camera plumbing move to the framework.

### 7.5 — Commit + publish

- [ ] Framework repo: `github.com/EnfonoTech/erpnext-pwa-core` (new)
- [ ] Published to private npm or via git URL in package.json
- [ ] damage-pwa-capacitor updated to depend on it
- [ ] Version tagged v0.1.0

---

## Task 8 — Scaffolder CLI (Phase 3)

Generate a new ERPNext PWA in minutes.

### 8.1 — `npx create-erpnext-pwa`

Published to npm (or run via `npx github:EnfonoTech/erpnext-pwa-core/create`).

```bash
npx create-erpnext-pwa warehouse-scanner --template vue --role "Stock User"

# Prompts:
# - App name (kebab-case)
# - Display name (e.g. "Warehouse Scanner")
# - Frappe app name for backend (e.g. "warehouse_scanner")
# - Role gate (e.g. "Stock User")
# - UI framework: Vue | React
# - Theme color (hex)

# Output:
#   ./warehouse-scanner/
#   ├── package.json       (with @enfono/erpnext-pwa-core dep)
#   ├── capacitor.config.ts
#   ├── src/               (Vue or React starter)
#   │   ├── main.js
#   │   ├── router/
#   │   ├── views/         (Login, Dashboard placeholders)
#   │   ├── sync-config.js (commented skeleton)
#   │   └── api-config.js  (API base URL, role name)
#   ├── android/           (configured with Capacitor)
#   └── server/
#       └── warehouse_scanner/  (Frappe app skeleton, imports frappe_pwa_core)
```

First run: `npm install && npm run dev` → working login screen on localhost against the real Frappe server. Consumer adds business logic from there.

### 8.2 — Built-in migrations

CLI has a `migrate` subcommand for known architectural shifts:
```bash
npx create-erpnext-pwa migrate --to 0.2.0  # from 0.1 framework to 0.2
```

So future framework bumps don't require manual refactoring of every consumer.

---

## Task 9 — Reference docs + the playbook (Phase 3)

Write the "how to build an ERPNext PWA with offline" guide. Publishable to `rmax-docs.vercel.app` or a new microsite.

- [ ] `docs/architecture.md` — the big picture. What runs where. Why Capacitor, why API keys, why declarative sync
- [ ] `docs/building-a-pwa.md` — step-by-step tutorial building a "Customer Visit Tracker" app from scratch using the CLI
- [ ] `docs/sync-config.md` — the declarative queue schema, examples for common patterns (GET list + cache, POST with optimistic update, file upload, multi-step action)
- [ ] `docs/plugin-catalog.md` — which Capacitor plugins the framework ships with, when to add more, security implications
- [ ] `docs/deployment.md` — signing, distribution, Play Store vs sideload, update flow

---

## Task 10 — Van Sales PWA v2 rebuilt on framework (Phase 4+)

**Deferred** — out of scope for next session. Listed here so the roadmap is visible.

The React-based Van Sales PWA (currently no offline) gets rewritten to:
1. Import `@enfono/erpnext-pwa-core`
2. Use `frappe_pwa_core` for server auth
3. Configure its own `sync-config.js` for Sales Invoice / Payment / Customer queues
4. Keep its own view components (React)
5. Reuse the Android shell template

If the framework was extracted well, Van Sales v2 offline works in ~1 week of work instead of months.

This is the forcing function that proves the framework is actually reusable. If extracting Van Sales reveals leaks or poorly-factored abstractions in the core, we fix them and bump to v0.2.0.

---

## Strategic Notes

**Why NOT start framework-first:**
- We don't yet know which patterns will survive contact with reality
- Extracting from a working consumer is far more reliable than designing in a vacuum
- The Vue↔React divide only becomes clear when you actually have both

**Why frame this as a platform NOW:**
- Sets the architectural direction so phase 1 modules are written as exports (not deep integrations)
- Damage PWA's `utils/` directory should look and feel like a library from day one — same file names, same module boundaries as what'll later move to `erpnext-pwa-core/src/`
- No large refactor needed during extraction; just a physical move + `package.json` updates

**What gets written differently in Phase 1 because of Phase 3 intent:**
- `src/utils/sync-engine.js` should already accept a config parameter (even if initially hard-coded by the caller to Damage PWA's queues) — don't bake the API method names into the engine
- `src/utils/frappe.js` should export `createClient({ apiBase, credentials })` — not a module-level singleton tied to one server
- `src/utils/db.js` should export an adapter factory — don't hard-code the 6 store names; accept them as input
- `src/store/auth.js` should accept a `role` config — don't hard-code `"Damage User"`

These small shifts turn "rewrite during extraction" into "cut + paste during extraction."

---

## Revised Estimated Effort

**Phase 1 (Tasks 1-5):** ~5 hours — same as original, with minor write-for-extraction adjustments
**Phase 2 (Task 6 rollout):** 1 week observation
**Phase 3 (Tasks 7-9):** ~8 hours focused work — extract + scaffold + docs
**Phase 4 (Task 10 Van Sales v2):** ~1 week engineering — separate milestone

Framework reaches v1.0 after Van Sales proves reusability. Every subsequent ERPNext PWA is a 1-2 week project instead of a 3-month project.
