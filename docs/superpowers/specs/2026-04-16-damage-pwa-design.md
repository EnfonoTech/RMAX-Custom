# Damage PWA — Design Specification

**Date:** 2026-04-16
**Status:** Draft
**App Name:** `damage_pwa`
**Stack:** Vue 3 + Vite + Pinia + PWA (Service Worker + IndexedDB)
**Target:** Separate Frappe app, served at `/damage-pwa/` on the same site
**Android:** TWA wrapper generating sideloadable APK

---

## 1. Purpose

A mobile-first PWA for the Damage User role to perform warehouse inspections on Damage Transfers. The user inspects damaged items, assigns supplier codes, photographs damage, and approves/rejects transfers — all with full offline capability for unreliable warehouse WiFi.

### Users
- **Primary:** Damage User (sabith@gmail.com is the test user)
- **Device:** Android phone/tablet in warehouse
- **Environment:** Low-light warehouse, potentially gloved hands, spotty WiFi

### Non-Goals
- Creating Damage Slips (Branch User does this in Frappe desk)
- Creating Damage Transfers (Branch/Stock User does this in Frappe desk)
- Write-off functionality (Admin does this in Frappe desk)

---

## 2. Screens

### 2.1 PIN Login
- **First time:** Username + password form → validates against Frappe login API → prompt to set 4-digit PIN
- **Subsequent:** Numpad with 4 PIN dots → validates against hashed PIN in IndexedDB
- **Offline:** PIN validates locally against cached hash. API calls queue until online.
- **Session expiry:** App stores `session_expires_at` from `setup_pin`. Proactively prompts re-auth before expiry.

### 2.2 Dashboard
- **Top bar:** App logo + sync status indicator (green dot = synced, amber = pending, red = offline)
- **Sync bar:** "SYNCED 2 MIN AGO" / "3 CHANGES PENDING" / "OFFLINE — WORKING LOCALLY"
- **KPI cards:** Pending | Approved | Rejected counts
- **Transfer list:** Pending Inspection transfers, sorted newest first. Each card shows: DT name, source → damage warehouse, item count, date. Amber left border = pending. Greyed out = locked by another inspector.
- **Pull to refresh:** Re-fetches from server when online
- **Bottom nav:** Home | History | Settings

### 2.3 Transfer Detail
- **Header:** Back arrow + DT name + item progress (e.g., "3/8 inspected")
- **Info card:** Branch warehouse → Damage warehouse, transaction date, linked slips count
- **Item list:** Each item shows: item_code, item_name, qty, inspection status (checkmark if done, empty if pending)
- **Tap item → opens Item Inspection screen**
- **Linked Slips section:** Collapsible, read-only list of Damage Slips
- **Action buttons (bottom):** Approve (green) + Reject (red) — enabled only when ALL items are inspected. Disabled if any item missing supplier_code, category, or photo.
- **Claim lock:** Acquired automatically when opening transfer. Shows "Locked by you" indicator. Expires after 30 min.

### 2.4 Item Inspection
- **Header:** Back + "DT-00045 / Item 1 of 8"
- **Item info card:** item_code, item_name, qty, UOM (read-only)
- **Supplier Code:** Dropdown picker from cached Supplier Code list (required)
- **Damage Category:** Chip-select, single choice (required). Options: Glass or Body Broken, Flickering, Driver Damage, Sensor Damage, LED Damage, Other
- **Photos (1-3):** 
  - Slot 1 (required), Slots 2-3 (optional)
  - Each slot: Camera button (rear camera via `capture="environment"`) or Gallery button
  - Thumbnail preview with delete (X) button
  - Client-side compression to max 1MB via Canvas API before storing
- **Remarks:** Multi-line text input (optional)
- **Navigation:** "← PREV" + "SAVE & NEXT →" buttons
- **Auto-save:** Saves to IndexedDB on field change (not just on button tap)

### 2.5 Completed History
- **Tab filter:** All | Approved | Rejected
- **List:** DT name, warehouses, date, status badge, item count
- **Tap → opens read-only Transfer Detail (no edit, no action buttons)**
- **Pagination:** Infinite scroll, loads 20 at a time

### 2.6 Damage Slip Viewer
- **Accessed from:** Transfer Detail → Linked Slips section → tap a slip
- **Read-only:** DS name, date, branch warehouse, damage warehouse, customer, category, remarks
- **Item table:** item_code, item_name, qty, UOM

### 2.7 Settings
- **Change PIN:** Enter current PIN → enter new PIN → confirm
- **Sync status:** Last sync time, items in queue, force sync button
- **Clear cache:** Clears IndexedDB (except auth). Requires re-sync.
- **App info:** Version, logged-in user, server URL
- **Logout:** Clears all local data, returns to first-time login

---

## 3. Visual Design

### Theme: Industrial Dark
- **Background:** `#0a0a0a` (near-black)
- **Surface:** `#1a1a1a` (cards, inputs)
- **Border:** `#333333`
- **Primary accent:** `#f59e0b` (amber) — labels, active states, branding
- **Success:** `#22c55e` (green) — approved, synced
- **Danger:** `#dc2626` (red) — rejected, errors, delete
- **Text primary:** `#ffffff`
- **Text secondary:** `#666666`
- **Typography:** Monospace (`SF Mono`, `Courier New`, monospace fallback)
- **Labels:** All-caps, letter-spacing 1-2px, 10-11px, amber color
- **Cards:** 8px border-radius, 1px solid #333 border
- **Status indicators:** Left border 3px solid (amber=pending, green=approved, red=rejected)
- **Buttons:** Large touch targets (48px+ height), amber fill for primary actions
- **Damage category:** Chip/pill select (amber fill = selected, dark + border = unselected)

---

## 4. Architecture

### 4.1 Project Structure

```
frappe-bench/apps/damage_pwa/
├── frontend/                          # Vue 3 SPA
│   ├── src/
│   │   ├── main.js                    # App bootstrap
│   │   ├── App.vue                    # Root: router-view + sync manager
│   │   ├── router/index.js            # Vue Router with PIN guard
│   │   ├── store/
│   │   │   ├── auth.js                # PIN + session management
│   │   │   ├── transfers.js           # Transfer list + detail
│   │   │   ├── inspection.js          # Current inspection state
│   │   │   ├── sync.js                # Offline queue + sync engine
│   │   │   └── master.js              # Supplier codes cache
│   │   ├── views/
│   │   │   ├── LoginView.vue          # PIN entry + first-time setup
│   │   │   ├── DashboardView.vue      # KPIs + pending list
│   │   │   ├── TransferDetailView.vue # Items + approve/reject
│   │   │   ├── InspectionView.vue     # Per-item inspection form
│   │   │   ├── HistoryView.vue        # Completed transfers
│   │   │   ├── SlipDetailView.vue     # Read-only Damage Slip
│   │   │   └── SettingsView.vue       # PIN, cache, logout
│   │   ├── components/
│   │   │   ├── SyncBar.vue            # Connection + sync status
│   │   │   ├── BottomNav.vue          # Home / History / Settings
│   │   │   ├── TransferCard.vue       # List item card
│   │   │   ├── ItemRow.vue            # Item with inspection status
│   │   │   ├── ChipSelect.vue         # Damage category picker
│   │   │   ├── PhotoSlot.vue          # Camera/gallery + preview
│   │   │   ├── PinPad.vue             # Numpad input
│   │   │   └── KpiCard.vue            # Dashboard stat card
│   │   ├── utils/
│   │   │   ├── frappe.js              # API wrapper with CSRF + dedup
│   │   │   ├── db.js                  # IndexedDB wrapper (idb library)
│   │   │   ├── sync-engine.js         # Queue processor + conflict resolution
│   │   │   ├── photo.js               # Camera, gallery, compression
│   │   │   └── pin.js                 # PIN hashing + validation
│   │   └── composables/
│   │       ├── useOnline.js           # Reactive online/offline state
│   │       └── usePullRefresh.js      # Pull-to-refresh gesture
│   ├── vite.config.js
│   └── package.json
├── damage_pwa/
│   ├── hooks.py                       # App config, routes, after_request
│   ├── api/
│   │   ├── auth.py                    # setup_pin, validate_session
│   │   ├── inspect.py                 # CRUD + workflow for inspections
│   │   └── master.py                  # Supplier codes
│   ├── www/damage-pwa/
│   │   ├── index.py                   # SPA entry (asset discovery)
│   │   └── index.html                 # HTML template with Vue mount
│   ├── public/
│   │   ├── manifest.json              # PWA manifest
│   │   ├── js/sw.js                   # Service worker (static file)
│   │   ├── icons/                     # PWA icons (192, 512)
│   │   └── frontend/                  # Built Vue assets (Vite output)
│   └── damage_pwa/
│       └── doctype/
│           └── damage_pwa_pin/        # Stores hashed PINs per user
├── android/                           # TWA wrapper project
│   ├── app/
│   │   ├── build.gradle               # SDK 34, TWA dependencies
│   │   └── src/main/
│   │       ├── AndroidManifest.xml     # LauncherActivity → /damage-pwa/
│   │       └── res/                    # Icons, colors, strings
│   ├── build.gradle                   # Root Gradle config
│   ├── gradle/                        # Gradle wrapper
│   └── keystore/                      # Signing keystore (gitignored)
└── pyproject.toml
```

### 4.2 Frappe App Config (hooks.py)

```python
app_name = "damage_pwa"
app_title = "Damage PWA"

website_route_rules = [
    {"from_route": "/damage-pwa/<path:app_path>", "to_route": "damage-pwa"}
]

after_request = ["damage_pwa.utils.add_sw_headers"]
```

No `app_include_js` — this is a standalone SPA, not injected into Frappe desk.

### 4.3 Custom DocType: Damage PWA Pin

Stores hashed PINs server-side for verification:

| Field | Type | Notes |
|-------|------|-------|
| `user` | Link (User) | Primary, unique |
| `pin_hash` | Password | bcrypt hash of PIN |
| `created_at` | Datetime | When PIN was set |

Permissions: System Manager only (API handles access).

---

## 5. API Specification

All endpoints require Damage User role. Each validates via `_assert_damage_user()` utility.

### 5.1 Auth

**`damage_pwa.api.auth.setup_pin`**
- **Args:** `pin` (string, 4-6 digits)
- **Requires:** Already logged in via Frappe session
- **Action:** Hash PIN with bcrypt, store in Damage PWA Pin DocType
- **Returns:** `{ user, full_name, roles, session_expires_at, supplier_codes_modified }`
- **Notes:** Called after standard Frappe login. PIN is a convenience layer, not a replacement for Frappe auth.

**`damage_pwa.api.auth.validate_session`**
- **Returns:** `{ valid: true, user, session_expires_at }` or 403

### 5.2 Inspection

**`damage_pwa.api.inspect.get_pending_transfers`**
- **Returns:** List of Damage Transfers where workflow_state="Pending Inspection"
- **Each includes:** name, transaction_date, company, branch_warehouse, damage_warehouse, items (full list with inspection status), locked_by, locked_at
- **Sort:** name DESC (newest first)

**`damage_pwa.api.inspect.get_transfer_detail`**
- **Args:** `name` (DT name)
- **Returns:** Full DT with items + linked Damage Slips + lock status
- **Notes:** Items include current inspection data (supplier_code, category, images, remarks)

**`damage_pwa.api.inspect.claim_transfer`**
- **Args:** `name` (DT name)
- **Action:** Sets `_damage_pwa_locked_by` = current user, `_damage_pwa_locked_at` = now
- **Validation:** Fails if locked by another user within last 30 min
- **Returns:** `{ locked: true, expires_at }`

**`damage_pwa.api.inspect.save_inspection`**
- **Args:** `name` (DT name), `items` (list of `{ row_name, supplier_code, damage_category, images, image_2, image_3, remarks }`) — `row_name` is the child table row's `name` field (e.g., "abc123"), NOT the item_name
- **Validation:** Validates lock ownership. All items must belong to the DT.
- **Action:** Bulk updates all items in a single transaction with savepoint. Rolls back entirely on any failure.
- **Returns:** `{ success: true, updated_count }`
- **Photo contract:** `images`, `image_2`, `image_3` are file URLs (already uploaded via `upload_file`). The PWA uploads photos first, then calls this with URLs.

**`damage_pwa.api.inspect.approve_transfer`**
- **Args:** `name` (DT name)
- **Validation:** All items must have supplier_code + damage_category + at least 1 image. Lock must be held by current user.
- **Action:** `apply_workflow(doc, "Approve")` → triggers existing `on_submit` → Stock Entry creation
- **Returns:** `{ success: true, stock_entry }`

**`damage_pwa.api.inspect.reject_transfer`**
- **Args:** `name` (DT name), `reason` (optional string)
- **Action:** `apply_workflow(doc, "Reject")`
- **Returns:** `{ success: true }`

**`damage_pwa.api.inspect.get_history`**
- **Args:** `limit` (default 20), `start` (default 0), `status_filter` (optional: "Approved"/"Rejected"/"Written Off")
- **Returns:** `{ data: [...], total_count }` — DTs with workflow_state in (Approved, Rejected, Written Off)

**`damage_pwa.api.inspect.get_slip_detail`**
- **Args:** `name` (DS name)
- **Returns:** Full Damage Slip with items (read-only)

### 5.3 Master Data

**`damage_pwa.api.master.get_supplier_codes`**
- **Returns:** `{ data: [{ name, supplier_code_name, supplier, enabled }], last_modified }` — all enabled Supplier Codes
- **Cache:** PWA stores `last_modified` and sends it as `if_modified_since` on next fetch. API returns 304 if unchanged.

---

## 6. Offline Architecture

### 6.1 IndexedDB Stores

| Store | Key | Content | TTL |
|-------|-----|---------|-----|
| `auth` | `"session"` | Hashed PIN, user info, session_expires_at | Until logout |
| `transfers` | DT name | Full transfer data + items | Refreshed on each sync |
| `supplier_codes` | SC name | Supplier Code records | Refreshed when last_modified changes |
| `photos` | UUID | Compressed image blob + metadata (transfer, item, slot) | Until uploaded + confirmed |
| `inspection_queue` | Auto-increment | `{ transfer, items: [...], timestamp }` | Until synced |
| `action_queue` | Auto-increment | `{ transfer, action: "approve"/"reject", reason?, timestamp }` | Until synced |

### 6.2 Sync Engine

**Trigger:** Online event, app foreground, pull-to-refresh, manual sync button.

**Process order (sequential, not parallel):**
1. Validate session — if expired, prompt re-auth, halt sync
2. Upload photos from `photos` store → get file URLs → update `inspection_queue` entries with URLs
3. Process `inspection_queue` → call `save_inspection` per transfer → on success, delete from queue
4. Process `action_queue` → call `approve_transfer`/`reject_transfer` → on success, delete from queue
5. Fetch fresh data → `get_pending_transfers`, `get_supplier_codes` (conditional) → update IndexedDB
6. Update dashboard KPIs

**Conflict resolution:** Server wins.
- If `save_inspection` returns 409 (transfer already approved/rejected by someone else): discard queued inspection, show notification
- If `approve_transfer` returns error (already transitioned): discard queued action, show notification
- If `claim_transfer` returns locked by another: show "Locked by {user}" in UI, prevent editing

**Retry:** Failed syncs retry with exponential backoff (5s, 15s, 45s, max 5 min). Network errors queue indefinitely until connectivity returns.

### 6.3 Service Worker

**Strategy:** Network-first for API calls, cache-first for static assets.

- Static assets (JS, CSS, icons, manifest): Cached on install, served from cache. Updated on new SW version.
- API calls: Try network first. On failure, return cached response if available (for GET endpoints). POST/PUT never served from SW cache.
- Photos: Not cached by SW — managed by IndexedDB directly.

### 6.4 Photo Handling

1. User taps Camera → `<input type="file" accept="image/*" capture="environment">` opens rear camera
2. User taps Gallery → `<input type="file" accept="image/*">` opens file picker
3. Selected file → Canvas API resize to max 1280px longest side, JPEG quality 0.7, target ≤1MB
4. Compressed blob → stored in IndexedDB `photos` store with UUID + metadata
5. Thumbnail generated (200px) for UI preview
6. On sync: blob → `FormData` → `upload_file` API → returns file URL
7. File URL stored in inspection_queue item's `images`/`image_2`/`image_3` field
8. After successful `save_inspection`, photo blob deleted from IndexedDB

---

## 7. Android TWA Wrapper

### 7.1 Prerequisites (macOS setup)

```bash
# Install Android command-line tools
brew install --cask android-commandlinetools

# Accept licenses + install SDK
sdkmanager --sdk_root=$HOME/android-sdk "platform-tools" "platforms;android-34" "build-tools;34.0.0"
export ANDROID_HOME=$HOME/android-sdk
export PATH=$PATH:$ANDROID_HOME/platform-tools:$ANDROID_HOME/build-tools/34.0.0

# Install JDK 17 (required by Gradle)
brew install openjdk@17
export JAVA_HOME=$(/usr/libexec/java_home -v 17)
```

### 7.2 TWA Project Structure

Minimal Android project (~5 files):
- `build.gradle` (root): Gradle plugin configuration
- `app/build.gradle`: SDK 34, `androidx.browser:browser:1.8.0`, `com.google.androidbrowserhelper:androidbrowserhelper:2.5.0`
- `AndroidManifest.xml`: `LauncherActivity` from androidbrowserhelper, intent filter for `/damage-pwa/`
- `res/values/strings.xml`: App name, site URL, theme color
- `res/mipmap-*/`: App icons (from PWA icons)

### 7.3 Digital Asset Links

For full-screen TWA (no URL bar), the server must serve:

```
GET /.well-known/assetlinks.json
```

Content:
```json
[{
  "relation": ["delegate_permission/common.handle_all_urls"],
  "target": {
    "namespace": "android_app",
    "package_name": "com.rmax.damage_pwa",
    "sha256_cert_fingerprints": ["<SHA-256 of signing key>"]
  }
}]
```

This is served as a static file via Frappe's `www/.well-known/` directory in the `damage_pwa` app.

### 7.4 Build APK

```bash
cd android/
./gradlew assembleRelease
# Output: app/build/outputs/apk/release/app-release.apk
# Rename to damage-pwa.apk for distribution
```

**Keystore generation:**
```bash
keytool -genkey -v -keystore keystore/damage-pwa.keystore \
  -alias damage-pwa -keyalg RSA -keysize 2048 -validity 10000
```

The keystore is `.gitignored`. Store it securely — losing it means you can't update the APK.

---

## 8. Security

- All API endpoints validate `"Damage User" in frappe.get_roles()` as first line
- PIN hash: bcrypt with salt, stored server-side in Damage PWA Pin DocType and client-side in IndexedDB
- IndexedDB data is device-local, cleared on logout
- Photos compressed client-side, uploaded via Frappe's standard file upload (respects file permissions)
- CSRF token: extracted from cookie, included in all API calls
- Session cookies: `credentials: "include"` on all fetch calls, `SameSite=Lax`
- Lock mechanism prevents concurrent edits to same transfer
- No sensitive data (passwords, tokens) stored in localStorage — IndexedDB only

---

## 9. Dependencies

### Frontend (package.json)
```
vue: ^3.4
vue-router: ^4.3
pinia: ^2.1
idb: ^8.0          # IndexedDB wrapper
@vite-pwa/vite: ^0.20  # Vite PWA plugin (manifest + SW registration)
```

### Backend (pyproject.toml)
```
frappe: >=15.0.0   # Framework dependency
bcrypt: >=4.0.0    # PIN hashing
```

### Android
```
androidx.browser:browser:1.8.0
com.google.androidbrowserhelper:androidbrowserhelper:2.5.0
Gradle 8.x, JDK 17, SDK 34
```

---

## 10. Deployment

### First-time setup on server
```bash
cd ~/frappe-bench
bench get-app https://github.com/EnfonoTech/damage-pwa.git
bench --site rmax_dev2 install-app damage_pwa
bench --site rmax_dev2 migrate
cd apps/damage_pwa/frontend && yarn && yarn build
bench build --app damage_pwa  # For hooks CSS/JS if any
sudo supervisorctl restart all
```

### Subsequent deploys
```bash
cd ~/frappe-bench/apps/damage_pwa && git pull upstream main
cd frontend && yarn build
cd ~/frappe-bench
bench --site rmax_dev2 migrate  # If schema changes
bench --site rmax_dev2 clear-cache
sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web
```

### APK distribution
Build locally → share `damage-pwa.apk` via file transfer / cloud storage → sideload on warehouse devices (enable "Install from unknown sources").
