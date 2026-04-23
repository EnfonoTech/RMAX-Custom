# Damage PWA Phase 1: Frappe App Scaffold + Backend APIs

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the `damage_pwa` Frappe app with all backend API endpoints, testable via curl/Postman before any frontend work begins.

**Architecture:** Separate Frappe v15 app (`damage_pwa`) installed alongside `rmax_custom` on the same site. Exposes whitelisted Python APIs under `damage_pwa.api.*`. Creates one custom DocType (`Damage PWA Pin`) and adds custom fields to existing `Damage Transfer` and `Damage Transfer Item` DocTypes via fixtures.

**Tech Stack:** Frappe v15, Python 3.10+, bcrypt, MariaDB

**Spec:** `docs/superpowers/specs/2026-04-16-damage-pwa-design.md`

**Checkpoint:** After this phase, every API endpoint can be tested via curl. No frontend code yet.

---

## File Map

```
frappe-bench/apps/damage_pwa/
├── pyproject.toml
├── damage_pwa/
│   ├── __init__.py
│   ├── hooks.py
│   ├── modules.txt
│   ├── patches.txt
│   ├── utils.py                           # SW headers + shared helpers
│   ├── api/
│   │   ├── __init__.py
│   │   ├── auth.py                        # setup_pin, validate_session
│   │   ├── inspect.py                     # All inspection CRUD + workflow
│   │   └── master.py                      # Supplier codes
│   ├── damage_pwa/
│   │   ├── __init__.py
│   │   └── doctype/
│   │       └── damage_pwa_pin/
│   │           ├── __init__.py
│   │           ├── damage_pwa_pin.json     # DocType definition
│   │           ├── damage_pwa_pin.py       # Controller
│   │           └── test_damage_pwa_pin.py  # Tests
│   ├── fixtures/
│   │   └── custom_field.json              # Custom fields for DT + DT Item
│   ├── www/
│   │   └── damage-pwa/
│   │       ├── index.py                   # SPA entry (Phase 2)
│   │       └── index.html                 # SPA template (Phase 2)
│   └── public/
│       └── manifest.json                  # PWA manifest (Phase 2)
└── frontend/                              # Vue SPA (Phase 2)
```

---

### Task 1: Scaffold the Frappe App

**Files:**
- Create: `damage_pwa/pyproject.toml`
- Create: `damage_pwa/damage_pwa/__init__.py`
- Create: `damage_pwa/damage_pwa/hooks.py`
- Create: `damage_pwa/damage_pwa/modules.txt`
- Create: `damage_pwa/damage_pwa/patches.txt`

- [ ] **Step 1: Create app via bench**

Run from the server (or locally if you have a bench):

```bash
cd ~/frappe-bench
bench new-app damage_pwa
```

Answer the prompts:
- App Title: `Damage PWA`
- App Description: `Mobile PWA for Damage Inspection Workflow`
- App Publisher: `Enfono`
- App Email: `ramees@enfono.com`
- App License: `mit`

- [ ] **Step 2: Install app on site**

```bash
bench --site rmax_dev2 install-app damage_pwa
```

Expected: "Installing damage_pwa... Success"

- [ ] **Step 3: Configure hooks.py**

Replace the generated `damage_pwa/damage_pwa/hooks.py` with:

```python
app_name = "damage_pwa"
app_title = "Damage PWA"
app_publisher = "Enfono"
app_description = "Mobile PWA for Damage Inspection Workflow"
app_email = "ramees@enfono.com"
app_license = "mit"

# SPA route catch-all
website_route_rules = [
    {"from_route": "/damage-pwa/<path:app_path>", "to_route": "damage-pwa"}
]

# Service worker headers
after_request = ["damage_pwa.utils.add_sw_headers"]

# Custom fields on Damage Transfer (from rmax_custom)
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            [
                "name",
                "in",
                [
                    # Damage Transfer — lock fields
                    "Damage Transfer-_damage_pwa_locked_by",
                    "Damage Transfer-_damage_pwa_locked_at",
                    "Damage Transfer-_rejection_reason",

                    # Damage Transfer Item — audit fields
                    "Damage Transfer Item-_inspected_by",
                    "Damage Transfer Item-_inspected_at",
                    "Damage Transfer Item-_inspection_status",
                ]
            ]
        ]
    }
]
```

- [ ] **Step 4: Create utils.py**

Create `damage_pwa/damage_pwa/utils.py`:

```python
import frappe


def add_sw_headers(response):
    """Add Service-Worker-Allowed header for SW requests."""
    if hasattr(frappe.local, "request"):
        path = frappe.local.request.path or ""
        if "/assets/damage_pwa/" in path and path.endswith("sw.js"):
            response.headers["Service-Worker-Allowed"] = "/damage-pwa/"
    return response


def assert_damage_user():
    """Validate current user has Damage User role. Call as first line in every API."""
    if "Damage User" not in frappe.get_roles():
        frappe.throw("Not permitted", frappe.PermissionError)
```

- [ ] **Step 5: Create empty API package**

Create `damage_pwa/damage_pwa/api/__init__.py`:

```python
```

(Empty file — just makes it a package)

- [ ] **Step 6: Commit scaffold**

```bash
cd ~/frappe-bench/apps/damage_pwa
git init
git add -A
git commit -m "feat: scaffold damage_pwa Frappe app

Frappe v15 app for Damage Inspection PWA.
Hooks: SPA route catch-all, SW headers, custom field fixtures.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Create Damage PWA Pin DocType

**Files:**
- Create: `damage_pwa/damage_pwa/damage_pwa/doctype/damage_pwa_pin/__init__.py`
- Create: `damage_pwa/damage_pwa/damage_pwa/doctype/damage_pwa_pin/damage_pwa_pin.json`
- Create: `damage_pwa/damage_pwa/damage_pwa/doctype/damage_pwa_pin/damage_pwa_pin.py`
- Create: `damage_pwa/damage_pwa/damage_pwa/doctype/damage_pwa_pin/test_damage_pwa_pin.py`

- [ ] **Step 1: Create DocType JSON**

Create `damage_pwa/damage_pwa/damage_pwa/doctype/damage_pwa_pin/damage_pwa_pin.json`:

```json
{
    "actions": [],
    "autoname": "field:user",
    "creation": "2026-04-16 00:00:00.000000",
    "doctype": "DocType",
    "engine": "InnoDB",
    "field_order": [
        "user",
        "pin_hash",
        "created_at"
    ],
    "fields": [
        {
            "fieldname": "user",
            "fieldtype": "Link",
            "label": "User",
            "options": "User",
            "reqd": 1,
            "unique": 1,
            "in_list_view": 1
        },
        {
            "fieldname": "pin_hash",
            "fieldtype": "Password",
            "label": "PIN Hash",
            "reqd": 1,
            "hidden": 1
        },
        {
            "fieldname": "created_at",
            "fieldtype": "Datetime",
            "label": "Created At",
            "read_only": 1
        }
    ],
    "index_web_pages_for_search": 0,
    "is_submittable": 0,
    "links": [],
    "modified": "2026-04-16 00:00:00.000000",
    "module": "Damage Pwa",
    "name": "Damage PWA Pin",
    "naming_rule": "By fieldname",
    "owner": "Administrator",
    "permissions": [
        {
            "create": 1,
            "delete": 1,
            "read": 1,
            "role": "System Manager",
            "write": 1
        }
    ],
    "sort_field": "modified",
    "sort_order": "DESC",
    "states": []
}
```

- [ ] **Step 2: Create controller**

Create `damage_pwa/damage_pwa/damage_pwa/doctype/damage_pwa_pin/damage_pwa_pin.py`:

```python
import frappe
from frappe.model.document import Document


class DamagePWAPin(Document):
    pass
```

- [ ] **Step 3: Create __init__.py and test file**

Create `damage_pwa/damage_pwa/damage_pwa/doctype/damage_pwa_pin/__init__.py` (empty).

Create `damage_pwa/damage_pwa/damage_pwa/doctype/damage_pwa_pin/test_damage_pwa_pin.py`:

```python
from frappe.tests.utils import FrappeTestCase


class TestDamagePWAPin(FrappeTestCase):
    pass
```

- [ ] **Step 4: Create modules.txt**

Ensure `damage_pwa/damage_pwa/modules.txt` contains:

```
Damage Pwa
```

- [ ] **Step 5: Run migrate to create table**

```bash
bench --site rmax_dev2 migrate
```

Expected: No errors. Table `tabDamage PWA Pin` created.

- [ ] **Step 6: Verify DocType exists**

```bash
bench --site rmax_dev2 console
```

In console:
```python
frappe.get_meta("Damage PWA Pin").fields
```

Expected: Returns 3 fields (user, pin_hash, created_at).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: add Damage PWA Pin DocType

Stores bcrypt-hashed PINs per user for mobile auth.
System Manager permissions only — API handles access.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Create Custom Fields (Fixtures)

**Files:**
- Create: `damage_pwa/damage_pwa/fixtures/custom_field.json`

These add lock/audit fields to the existing Damage Transfer and Damage Transfer Item DocTypes (from `rmax_custom`).

- [ ] **Step 1: Create fixture JSON**

Create `damage_pwa/damage_pwa/fixtures/custom_field.json`:

```json
[
    {
        "doctype": "Custom Field",
        "dt": "Damage Transfer",
        "fieldname": "_damage_pwa_locked_by",
        "fieldtype": "Data",
        "label": "Locked By (PWA)",
        "read_only": 1,
        "hidden": 1,
        "no_copy": 1
    },
    {
        "doctype": "Custom Field",
        "dt": "Damage Transfer",
        "fieldname": "_damage_pwa_locked_at",
        "fieldtype": "Datetime",
        "label": "Locked At (PWA)",
        "read_only": 1,
        "hidden": 1,
        "no_copy": 1
    },
    {
        "doctype": "Custom Field",
        "dt": "Damage Transfer",
        "fieldname": "_rejection_reason",
        "fieldtype": "Small Text",
        "label": "Rejection Reason",
        "read_only": 1,
        "hidden": 0
    },
    {
        "doctype": "Custom Field",
        "dt": "Damage Transfer Item",
        "fieldname": "_inspected_by",
        "fieldtype": "Link",
        "label": "Inspected By",
        "options": "User",
        "read_only": 1,
        "hidden": 1,
        "no_copy": 1
    },
    {
        "doctype": "Custom Field",
        "dt": "Damage Transfer Item",
        "fieldname": "_inspected_at",
        "fieldtype": "Datetime",
        "label": "Inspected At",
        "read_only": 1,
        "hidden": 1,
        "no_copy": 1
    },
    {
        "doctype": "Custom Field",
        "dt": "Damage Transfer Item",
        "fieldname": "_inspection_status",
        "fieldtype": "Select",
        "label": "Inspection Status",
        "options": "\nincomplete\ncomplete\nflagged",
        "default": "incomplete",
        "read_only": 1,
        "in_list_view": 0,
        "no_copy": 1
    }
]
```

- [ ] **Step 2: Run migrate to install fixtures**

```bash
bench --site rmax_dev2 migrate
```

Expected: Custom fields created on Damage Transfer and Damage Transfer Item.

- [ ] **Step 3: Verify custom fields exist**

```bash
bench --site rmax_dev2 console
```

```python
dt_meta = frappe.get_meta("Damage Transfer")
print([f.fieldname for f in dt_meta.fields if f.fieldname.startswith("_")])
# Expected: ['_damage_pwa_locked_by', '_damage_pwa_locked_at', '_rejection_reason']

dti_meta = frappe.get_meta("Damage Transfer Item")
print([f.fieldname for f in dti_meta.fields if f.fieldname.startswith("_")])
# Expected: ['_inspected_by', '_inspected_at', '_inspection_status']
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: add custom fields for lock + audit trail

Adds to Damage Transfer: _damage_pwa_locked_by, _damage_pwa_locked_at, _rejection_reason
Adds to Damage Transfer Item: _inspected_by, _inspected_at, _inspection_status

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Auth API (setup_pin + validate_session)

**Files:**
- Create: `damage_pwa/damage_pwa/api/auth.py`

- [ ] **Step 1: Install bcrypt**

```bash
cd ~/frappe-bench
./env/bin/pip install bcrypt
```

- [ ] **Step 2: Write auth.py**

Create `damage_pwa/damage_pwa/api/auth.py`:

```python
import frappe
from frappe import _
from frappe.utils import now_datetime, get_datetime, cint
from damage_pwa.utils import assert_damage_user

try:
    import bcrypt
except ImportError:
    bcrypt = None


@frappe.whitelist()
def setup_pin(pin):
    """Set or update PIN for current user. Requires active Frappe session."""
    assert_damage_user()

    if not pin or not str(pin).isdigit() or len(str(pin)) < 4 or len(str(pin)) > 6:
        frappe.throw(_("PIN must be 4-6 digits"))

    if not bcrypt:
        frappe.throw(_("bcrypt not installed on server"))

    pin_hash = bcrypt.hashpw(str(pin).encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    existing = frappe.db.exists("Damage PWA Pin", {"user": frappe.session.user})
    if existing:
        doc = frappe.get_doc("Damage PWA Pin", existing)
        doc.pin_hash = pin_hash
        doc.created_at = now_datetime()
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.get_doc({
            "doctype": "Damage PWA Pin",
            "user": frappe.session.user,
            "pin_hash": pin_hash,
            "created_at": now_datetime(),
        })
        doc.insert(ignore_permissions=True)

    frappe.db.commit()

    # Session expiry: Frappe default is 6 hours for "Remember Me", else browser session
    session_expiry_hrs = cint(frappe.conf.get("session_expiry", 6))
    session_expires_at = get_datetime(now_datetime())
    from datetime import timedelta
    session_expires_at = session_expires_at + timedelta(hours=session_expiry_hrs)

    # Get supplier codes last_modified for initial cache
    sc_modified = frappe.db.sql(
        "SELECT MAX(modified) FROM `tabSupplier Code`"
    )
    sc_last_modified = str(sc_modified[0][0]) if sc_modified and sc_modified[0][0] else None

    return {
        "user": frappe.session.user,
        "full_name": frappe.db.get_value("User", frappe.session.user, "full_name"),
        "roles": frappe.get_roles(),
        "session_expires_at": str(session_expires_at),
        "supplier_codes_modified": sc_last_modified,
    }


@frappe.whitelist()
def validate_session():
    """Check if current Frappe session is still valid."""
    assert_damage_user()

    session_expiry_hrs = cint(frappe.conf.get("session_expiry", 6))
    from datetime import timedelta
    session_expires_at = get_datetime(now_datetime()) + timedelta(hours=session_expiry_hrs)

    return {
        "valid": True,
        "user": frappe.session.user,
        "full_name": frappe.db.get_value("User", frappe.session.user, "full_name"),
        "session_expires_at": str(session_expires_at),
    }
```

- [ ] **Step 3: Test setup_pin via curl**

First, get a session cookie by logging in as the Damage User:

```bash
# Login
curl -s -c cookies.txt -X POST \
  'https://rmax-dev.fateherp.com/api/method/login' \
  -H 'Content-Type: application/json' \
  -d '{"usr": "sabith@gmail.com", "pwd": "<password>"}'

# Setup PIN
curl -s -b cookies.txt -X POST \
  'https://rmax-dev.fateherp.com/api/method/damage_pwa.api.auth.setup_pin' \
  -H 'Content-Type: application/json' \
  -H 'X-Frappe-CSRF-Token: <token_from_login_response>' \
  -d '{"pin": "1234"}'
```

Expected: `{"message": {"user": "sabith@gmail.com", "full_name": "...", "roles": [...], "session_expires_at": "...", "supplier_codes_modified": "..."}}`

- [ ] **Step 4: Test validate_session via curl**

```bash
curl -s -b cookies.txt -X POST \
  'https://rmax-dev.fateherp.com/api/method/damage_pwa.api.auth.validate_session' \
  -H 'Content-Type: application/json' \
  -H 'X-Frappe-CSRF-Token: <token>'
```

Expected: `{"message": {"valid": true, "user": "sabith@gmail.com", ...}}`

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: add auth API — setup_pin + validate_session

PIN stored as bcrypt hash in Damage PWA Pin DocType.
Returns session_expires_at for proactive re-auth.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Master Data API (get_supplier_codes)

**Files:**
- Create: `damage_pwa/damage_pwa/api/master.py`

- [ ] **Step 1: Write master.py**

Create `damage_pwa/damage_pwa/api/master.py`:

```python
import frappe
from damage_pwa.utils import assert_damage_user


@frappe.whitelist()
def get_supplier_codes(if_modified_since=None):
    """Return all Supplier Codes with conditional cache support.

    Args:
        if_modified_since: ISO datetime string. If provided and data hasn't changed,
                          returns 304-equivalent empty response.

    Returns:
        dict with: data (list), last_modified (str), deleted (list of names)
    """
    assert_damage_user()

    last_modified_result = frappe.db.sql(
        "SELECT MAX(modified) FROM `tabSupplier Code`"
    )
    last_modified = str(last_modified_result[0][0]) if last_modified_result and last_modified_result[0][0] else None

    # Conditional cache: if nothing changed, return minimal response
    if if_modified_since and last_modified and last_modified <= if_modified_since:
        return {"not_modified": True}

    # Fetch all supplier codes (including disabled, so PWA can remove them from cache)
    data = frappe.get_all(
        "Supplier Code",
        fields=["name", "supplier_code_name", "supplier", "enabled", "modified"],
        order_by="supplier_code_name asc",
    )

    # Find deleted records since if_modified_since (if provided)
    deleted = []
    if if_modified_since:
        deleted_records = frappe.get_all(
            "Deleted Document",
            filters={
                "deleted_doctype": "Supplier Code",
                "creation": [">", if_modified_since],
            },
            fields=["deleted_name"],
        )
        deleted = [d.deleted_name for d in deleted_records]

    return {
        "data": data,
        "last_modified": last_modified,
        "deleted": deleted,
    }
```

- [ ] **Step 2: Test via curl**

```bash
curl -s -b cookies.txt -X POST \
  'https://rmax-dev.fateherp.com/api/method/damage_pwa.api.master.get_supplier_codes' \
  -H 'Content-Type: application/json' \
  -H 'X-Frappe-CSRF-Token: <token>'
```

Expected: `{"message": {"data": [{"name": "Clear Desk", ...}, ...], "last_modified": "2026-...", "deleted": []}}`

- [ ] **Step 3: Test conditional cache**

```bash
# Use the last_modified from previous response
curl -s -b cookies.txt -X POST \
  'https://rmax-dev.fateherp.com/api/method/damage_pwa.api.master.get_supplier_codes' \
  -H 'Content-Type: application/json' \
  -H 'X-Frappe-CSRF-Token: <token>' \
  -d '{"if_modified_since": "2026-04-16 12:00:00"}'
```

Expected: `{"message": {"not_modified": true}}` (if nothing changed since that time)

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: add master data API — get_supplier_codes

Conditional cache via if_modified_since. Returns disabled records
and deleted names so PWA can sync removals.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 6: Inspection API — Read Endpoints

**Files:**
- Create: `damage_pwa/damage_pwa/api/inspect.py`

- [ ] **Step 1: Write read endpoints in inspect.py**

Create `damage_pwa/damage_pwa/api/inspect.py`:

```python
import json
import frappe
from frappe import _
from frappe.utils import now_datetime, get_datetime, cint
from damage_pwa.utils import assert_damage_user

LOCK_TIMEOUT_MINUTES = 30


def _is_lock_active(doc):
    """Check if a transfer's lock is still active."""
    if not doc.get("_damage_pwa_locked_by") or not doc.get("_damage_pwa_locked_at"):
        return False
    locked_at = get_datetime(doc._damage_pwa_locked_at)
    now = get_datetime(now_datetime())
    return (now - locked_at).total_seconds() < LOCK_TIMEOUT_MINUTES * 60


def _get_item_inspection_status(item):
    """Determine inspection status for a single item row."""
    has_supplier = bool(item.get("supplier_code"))
    has_category = bool(item.get("damage_category"))
    has_photo = bool(item.get("images"))

    if has_supplier and has_category and has_photo:
        return item.get("_inspection_status") or "complete"
    return "incomplete"


def _serialize_transfer(dt_name, include_slips=False):
    """Serialize a Damage Transfer for API response."""
    doc = frappe.get_doc("Damage Transfer", dt_name)

    items = []
    for item in doc.items:
        items.append({
            "row_name": item.name,
            "item_code": item.item_code,
            "item_name": item.item_name,
            "qty": item.qty,
            "stock_uom": item.stock_uom,
            "damage_category": item.damage_category,
            "supplier_code": item.supplier_code,
            "images": item.images,
            "image_2": item.image_2,
            "image_3": item.image_3,
            "remarks": item.remarks,
            "damage_slip": item.damage_slip,
            "_inspected_by": item.get("_inspected_by"),
            "_inspected_at": str(item.get("_inspected_at")) if item.get("_inspected_at") else None,
            "_inspection_status": _get_item_inspection_status(item),
        })

    result = {
        "name": doc.name,
        "transaction_date": str(doc.transaction_date),
        "company": doc.company,
        "branch_warehouse": doc.branch_warehouse,
        "damage_warehouse": doc.damage_warehouse,
        "workflow_state": doc.workflow_state,
        "docstatus": doc.docstatus,
        "modified": str(doc.modified),
        "owner": doc.owner,
        "items": items,
        "item_count": len(items),
        "inspected_count": sum(1 for i in items if i["_inspection_status"] != "incomplete"),
        "locked_by": doc.get("_damage_pwa_locked_by") if _is_lock_active(doc) else None,
        "locked_at": str(doc.get("_damage_pwa_locked_at")) if _is_lock_active(doc) else None,
    }

    if include_slips:
        slips = []
        for slip_row in (doc.damage_slips or []):
            slips.append({
                "damage_slip": slip_row.damage_slip,
                "slip_date": str(slip_row.slip_date) if slip_row.slip_date else None,
                "damage_category": slip_row.damage_category,
                "total_items": slip_row.total_items,
            })
        result["damage_slips"] = slips

    return result


@frappe.whitelist()
def get_pending_transfers():
    """Get all Damage Transfers in Pending Inspection state."""
    assert_damage_user()

    transfers = frappe.get_all(
        "Damage Transfer",
        filters={"workflow_state": "Pending Inspection"},
        fields=["name"],
        order_by="name desc",
    )

    result = []
    for t in transfers:
        result.append(_serialize_transfer(t.name))

    return result


@frappe.whitelist()
def get_transfer_detail(name):
    """Get full Damage Transfer with items and linked slips."""
    assert_damage_user()

    if not frappe.db.exists("Damage Transfer", name):
        frappe.throw(_("Transfer {0} not found").format(name), frappe.DoesNotExistError)

    return _serialize_transfer(name, include_slips=True)


@frappe.whitelist()
def get_history(limit=20, start=0, status_filter=None):
    """Get completed Damage Transfers (approved/rejected/written off)."""
    assert_damage_user()

    limit = cint(limit) or 20
    start = cint(start) or 0

    filters = {
        "workflow_state": ["in", ["Approved", "Rejected", "Written Off"]],
    }
    if status_filter and status_filter in ("Approved", "Rejected", "Written Off"):
        filters["workflow_state"] = status_filter

    total_count = frappe.db.count("Damage Transfer", filters=filters)

    transfers = frappe.get_all(
        "Damage Transfer",
        filters=filters,
        fields=["name", "transaction_date", "company", "branch_warehouse",
                "damage_warehouse", "workflow_state", "owner", "modified"],
        order_by="name desc",
        start=start,
        page_length=limit,
    )

    # Add item counts without fetching full items
    for t in transfers:
        t["item_count"] = frappe.db.count(
            "Damage Transfer Item", filters={"parent": t["name"]}
        )
        t["transaction_date"] = str(t["transaction_date"])
        t["modified"] = str(t["modified"])

    return {
        "data": transfers,
        "total_count": total_count,
    }


@frappe.whitelist()
def get_slip_detail(name):
    """Get a Damage Slip with items (read-only)."""
    assert_damage_user()

    if not frappe.db.exists("Damage Slip", name):
        frappe.throw(_("Damage Slip {0} not found").format(name), frappe.DoesNotExistError)

    doc = frappe.get_doc("Damage Slip", name)
    items = []
    for item in doc.items:
        items.append({
            "item_code": item.item_code,
            "item_name": item.item_name,
            "qty": item.qty,
            "stock_uom": item.stock_uom,
            "description": item.description,
        })

    return {
        "name": doc.name,
        "date": str(doc.date),
        "company": doc.company,
        "branch_warehouse": doc.branch_warehouse,
        "damage_warehouse": doc.damage_warehouse,
        "customer": doc.customer,
        "damage_category": doc.damage_category,
        "remarks": doc.remarks,
        "status": doc.status,
        "items": items,
    }
```

- [ ] **Step 2: Test get_pending_transfers**

```bash
curl -s -b cookies.txt -X POST \
  'https://rmax-dev.fateherp.com/api/method/damage_pwa.api.inspect.get_pending_transfers' \
  -H 'Content-Type: application/json' \
  -H 'X-Frappe-CSRF-Token: <token>'
```

Expected: `{"message": [{"name": "DT-00045", "items": [...], ...}, ...]}`

- [ ] **Step 3: Test get_history**

```bash
curl -s -b cookies.txt -X POST \
  'https://rmax-dev.fateherp.com/api/method/damage_pwa.api.inspect.get_history' \
  -H 'Content-Type: application/json' \
  -H 'X-Frappe-CSRF-Token: <token>' \
  -d '{"limit": 5, "start": 0}'
```

Expected: `{"message": {"data": [...], "total_count": N}}`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: add inspection read APIs

get_pending_transfers, get_transfer_detail, get_history, get_slip_detail.
Full item serialization with inspection status tracking.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 7: Inspection API — Write Endpoints (claim, save, approve, reject)

**Files:**
- Modify: `damage_pwa/damage_pwa/api/inspect.py`

- [ ] **Step 1: Add claim_transfer to inspect.py**

Append to `damage_pwa/damage_pwa/api/inspect.py`:

```python
@frappe.whitelist()
def claim_transfer(name):
    """Lock a Damage Transfer for inspection by current user."""
    assert_damage_user()

    doc = frappe.get_doc("Damage Transfer", name)

    if doc.workflow_state != "Pending Inspection":
        frappe.throw(_("Transfer {0} is not pending inspection").format(name))

    # Check if locked by another user
    if _is_lock_active(doc) and doc._damage_pwa_locked_by != frappe.session.user:
        frappe.throw(
            _("Locked by {0} until {1}").format(
                doc._damage_pwa_locked_by,
                str(get_datetime(doc._damage_pwa_locked_at)
                    + __import__("datetime").timedelta(minutes=LOCK_TIMEOUT_MINUTES)),
            ),
            frappe.ValidationError,
        )

    doc._damage_pwa_locked_by = frappe.session.user
    doc._damage_pwa_locked_at = now_datetime()
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    from datetime import timedelta
    expires_at = get_datetime(now_datetime()) + timedelta(minutes=LOCK_TIMEOUT_MINUTES)

    return {
        "locked": True,
        "expires_at": str(expires_at),
        "modified": str(doc.modified),
    }


@frappe.whitelist()
def save_item_inspection(transfer_name, row_name, supplier_code=None,
                         damage_category=None, images=None, image_2=None,
                         image_3=None, remarks=None, status="complete",
                         client_modified=None):
    """Save inspection data for a single item row."""
    assert_damage_user()

    doc = frappe.get_doc("Damage Transfer", transfer_name)

    if doc.workflow_state != "Pending Inspection":
        frappe.throw(_("Transfer is not in Pending Inspection state"))

    # Validate lock
    if not _is_lock_active(doc) or doc._damage_pwa_locked_by != frappe.session.user:
        frappe.throw(_("You do not hold the lock on this transfer"))

    # Concurrency check
    if client_modified:
        if str(doc.modified) > client_modified:
            frappe.throw(
                _("Transfer was modified by someone else. Please refresh."),
                frappe.ValidationError,
            )

    # Find the item row
    target_row = None
    for item in doc.items:
        if item.name == row_name:
            target_row = item
            break

    if not target_row:
        frappe.throw(_("Item row {0} not found in transfer {1}").format(row_name, transfer_name))

    # Update fields
    if supplier_code is not None:
        target_row.supplier_code = supplier_code
    if damage_category is not None:
        target_row.damage_category = damage_category
    if images is not None:
        target_row.images = images
    if image_2 is not None:
        target_row.image_2 = image_2
    if image_3 is not None:
        target_row.image_3 = image_3
    if remarks is not None:
        target_row.remarks = remarks

    # Set audit fields
    target_row._inspected_by = frappe.session.user
    target_row._inspected_at = now_datetime()

    # Determine inspection status
    if status == "flagged":
        target_row._inspection_status = "flagged"
    elif target_row.supplier_code and target_row.damage_category and target_row.images:
        target_row._inspection_status = "complete"
    else:
        target_row._inspection_status = "incomplete"

    # Refresh lock timer
    doc._damage_pwa_locked_at = now_datetime()
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "success": True,
        "modified": str(doc.modified),
        "_inspection_status": target_row._inspection_status,
    }


@frappe.whitelist()
def save_inspection(name, items, client_modified=None):
    """Bulk save inspection data for multiple items. Resilient — continues on per-item failure."""
    assert_damage_user()

    items_list = json.loads(items) if isinstance(items, str) else items

    updated = []
    failed = []

    for item_data in items_list:
        try:
            result = save_item_inspection(
                transfer_name=name,
                row_name=item_data["row_name"],
                supplier_code=item_data.get("supplier_code"),
                damage_category=item_data.get("damage_category"),
                images=item_data.get("images"),
                image_2=item_data.get("image_2"),
                image_3=item_data.get("image_3"),
                remarks=item_data.get("remarks"),
                status=item_data.get("status", "complete"),
                client_modified=client_modified,
            )
            updated.append(item_data["row_name"])
            # Update client_modified for next iteration (doc.modified changes after each save)
            client_modified = result.get("modified")
        except Exception as e:
            failed.append({
                "row_name": item_data["row_name"],
                "error": str(e),
            })

    return {
        "success": len(failed) == 0,
        "updated": updated,
        "failed": failed,
    }


@frappe.whitelist()
def approve_transfer(name, client_modified=None):
    """Approve a Damage Transfer — triggers workflow transition + Stock Entry creation."""
    assert_damage_user()

    doc = frappe.get_doc("Damage Transfer", name)

    if doc.workflow_state != "Pending Inspection":
        frappe.throw(_("Transfer is not in Pending Inspection state"))

    # Validate lock
    if not _is_lock_active(doc) or doc._damage_pwa_locked_by != frappe.session.user:
        frappe.throw(_("You do not hold the lock on this transfer"))

    # Concurrency check
    if client_modified and str(doc.modified) > client_modified:
        frappe.throw(
            _("Transfer was modified by someone else. Please refresh."),
            frappe.ValidationError,
        )

    # Check all items — only "incomplete" blocks approval
    warnings = []
    incomplete_items = []
    flagged_items = []

    for item in doc.items:
        status = _get_item_inspection_status(item)
        if status == "incomplete":
            incomplete_items.append(item.item_code)
        elif status == "flagged" or item.get("_inspection_status") == "flagged":
            flagged_items.append(item.item_code)

    if incomplete_items:
        frappe.throw(
            _("Cannot approve — {0} items incomplete: {1}").format(
                len(incomplete_items), ", ".join(incomplete_items)
            )
        )

    if flagged_items:
        warnings.append("{0} items flagged: {1}".format(len(flagged_items), ", ".join(flagged_items)))

    # Idempotency: if already approved (e.g., duplicate request), return success
    if doc.workflow_state == "Approved" and doc.transfer_entry_created:
        return {
            "success": True,
            "stock_entry": doc.stock_entry_transfer,
            "warnings": warnings,
            "already_approved": True,
        }

    # Apply workflow transition — this triggers on_submit → Stock Entry creation
    from frappe.model.workflow import apply_workflow
    apply_workflow(doc, "Approve")

    # Reload to get stock_entry_transfer set by on_submit
    doc.reload()

    return {
        "success": True,
        "stock_entry": doc.stock_entry_transfer,
        "warnings": warnings,
    }


@frappe.whitelist()
def reject_transfer(name, reason=None, client_modified=None):
    """Reject a Damage Transfer — sends back to Branch User for rework."""
    assert_damage_user()

    doc = frappe.get_doc("Damage Transfer", name)

    if doc.workflow_state != "Pending Inspection":
        frappe.throw(_("Transfer is not in Pending Inspection state"))

    # Concurrency check
    if client_modified and str(doc.modified) > client_modified:
        frappe.throw(
            _("Transfer was modified by someone else. Please refresh."),
            frappe.ValidationError,
        )

    # Store rejection reason
    if reason:
        doc._rejection_reason = reason
        doc.save(ignore_permissions=True)
        # Also add as comment for visibility in Frappe desk
        doc.add_comment("Comment", _("Rejected via PWA: {0}").format(reason))

    from frappe.model.workflow import apply_workflow
    apply_workflow(doc, "Reject")

    return {"success": True}
```

- [ ] **Step 2: Test claim_transfer**

```bash
curl -s -b cookies.txt -X POST \
  'https://rmax-dev.fateherp.com/api/method/damage_pwa.api.inspect.claim_transfer' \
  -H 'Content-Type: application/json' \
  -H 'X-Frappe-CSRF-Token: <token>' \
  -d '{"name": "DT-00045"}'
```

Expected: `{"message": {"locked": true, "expires_at": "2026-...", "modified": "..."}}`

- [ ] **Step 3: Test save_item_inspection**

```bash
# Use a real row_name from get_transfer_detail response
curl -s -b cookies.txt -X POST \
  'https://rmax-dev.fateherp.com/api/method/damage_pwa.api.inspect.save_item_inspection' \
  -H 'Content-Type: application/json' \
  -H 'X-Frappe-CSRF-Token: <token>' \
  -d '{
    "transfer_name": "DT-00045",
    "row_name": "<actual_row_name>",
    "supplier_code": "Clear Desk",
    "damage_category": "Glass or Body Broken",
    "remarks": "Corner cracked",
    "status": "complete"
  }'
```

Expected: `{"message": {"success": true, "modified": "...", "_inspection_status": "complete"}}`

Note: `images` not sent yet (no photo uploaded) — status will be "incomplete" without it. That's correct.

- [ ] **Step 4: Test approve_transfer (expected to fail — items incomplete)**

```bash
curl -s -b cookies.txt -X POST \
  'https://rmax-dev.fateherp.com/api/method/damage_pwa.api.inspect.approve_transfer' \
  -H 'Content-Type: application/json' \
  -H 'X-Frappe-CSRF-Token: <token>' \
  -d '{"name": "DT-00045"}'
```

Expected: Error — "Cannot approve — N items incomplete: ..."

- [ ] **Step 5: Test reject_transfer**

```bash
curl -s -b cookies.txt -X POST \
  'https://rmax-dev.fateherp.com/api/method/damage_pwa.api.inspect.reject_transfer' \
  -H 'Content-Type: application/json' \
  -H 'X-Frappe-CSRF-Token: <token>' \
  -d '{"name": "DT-00045", "reason": "Missing items — need recount"}'
```

Expected: `{"message": {"success": true}}`

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: add inspection write APIs

claim_transfer: 30min soft lock with concurrency check
save_item_inspection: per-item save with audit trail
save_inspection: bulk save with per-item resilience
approve_transfer: flexible approval (flagged OK, incomplete blocks)
reject_transfer: with reason, stored as comment + field

All endpoints validate lock + client_modified for concurrency.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 8: Push to GitHub + Deploy to Server

**Files:** None — deployment only.

- [ ] **Step 1: Create GitHub repo**

```bash
gh repo create EnfonoTech/damage-pwa --private --description "Damage Inspection PWA for RMAX"
```

- [ ] **Step 2: Push to GitHub**

```bash
cd ~/frappe-bench/apps/damage_pwa
git remote add origin https://github.com/EnfonoTech/damage-pwa.git
git push -u origin main
```

- [ ] **Step 3: Deploy to server**

On the RMAX server (5.189.131.148):

```bash
cd /home/v15/frappe-bench
bench get-app https://github.com/EnfonoTech/damage-pwa.git
bench --site rmax_dev2 install-app damage_pwa
bench --site rmax_dev2 migrate
sudo supervisorctl restart all
```

- [ ] **Step 4: Run API smoke tests on server**

Repeat the curl tests from Tasks 4-7 against the live server URL to verify all endpoints work.

- [ ] **Step 5: Verify custom fields on server**

```bash
bench --site rmax_dev2 console
```

```python
dt_meta = frappe.get_meta("Damage Transfer")
print([f.fieldname for f in dt_meta.fields if f.fieldname.startswith("_")])
```

Expected: Lock and audit fields present.

---

## Phase 1 Checkpoint

After completing all 8 tasks, verify:

| Test | Method | Expected |
|------|--------|----------|
| App installed | `bench --site rmax_dev2 list-apps` | `damage_pwa` in list |
| Damage PWA Pin table | `bench console` → `frappe.get_meta("Damage PWA Pin")` | 3 fields |
| Custom fields on DT | `bench console` → check meta | 6 custom fields |
| `setup_pin` | curl POST | Returns user + session_expires_at |
| `validate_session` | curl POST | Returns valid: true |
| `get_supplier_codes` | curl POST | Returns data + last_modified |
| `get_supplier_codes` (cached) | curl POST with if_modified_since | Returns not_modified: true |
| `get_pending_transfers` | curl POST | Returns list of DTs |
| `get_transfer_detail` | curl POST with name | Returns items + slips |
| `claim_transfer` | curl POST | Returns locked: true |
| `save_item_inspection` | curl POST | Returns success + modified |
| `save_inspection` (bulk) | curl POST | Returns updated + failed lists |
| `approve_transfer` (incomplete) | curl POST | Error: items incomplete |
| `reject_transfer` | curl POST with reason | Success + comment created |
| `get_history` | curl POST | Returns data + total_count |

**Next:** Phase 2 — Vue SPA Core (router, stores, API client, PIN login, dashboard)
