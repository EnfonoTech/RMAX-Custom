# Inter-Branch Receivables & Payables — User Guide (Phase 1)

> **Status:** Deployed on dev (`rmax-dev.fateherp.com`) only. UAT and production rollout pending dev soak.

## What this feature does

When a single company runs multiple branches (Head Office, Riyadh, Jeddah, Snowlite, Malaz, Bahra…), every cross-branch transaction must show in **each branch's own books** even though the consolidated company books stay balanced.

This module captures those cross-branch obligations automatically. You record the actual business event (rent paid, cash transferred, stock moved). The system adds the matching inter-branch receivable/payable legs in the background.

Phase 1 covers three scenarios:
- **Cash transfer** — HO funds a branch's bank account
- **Rent / expense** — HO pays a branch-related bill
- **Stock transfer** — Stock moves from one branch's warehouse to another's

## One-time setup (already done on dev)

Already deployed on rmax_dev2. For reference only:

1. **Branch accounting dimension** — enabled, mandatory on every GL-posting entry per Company.
2. **Chart of Accounts** — for every Company, two new parent groups:
   - `Inter-Branch Receivable` (under Current Assets)
   - `Inter-Branch Payable` (under Current Liabilities)
3. **Cut-over date** — set per Company in **Company → Inter-Branch Cut-Over Date**. **Until you set this, the auto-injector is disabled.**
4. **Account heads per branch** — auto-loaded the moment a new Branch is created. A confirmation message ("Inter-Branch Accounts Created") appears in the desk; you do NOT need to add accounts manually.

### Activating on dev

To start using the system on `rmax_dev2`:

1. Open the relevant Company record (e.g. `Clearlight New Co.`).
2. Set **Inter-Branch Cut-Over Date** to today's date (or whatever fiscal-period boundary you want).
3. Save.

Any Journal Entry posted **on or after** this date with branches involved will get auto-injected. Earlier entries are untouched.

## Daily usage

### Scenario A — HO pays rent for Branch Riyadh

1. Open **Accounting → Journal Entry → New**.
2. Set Posting Date and Company.
3. Add line 1: `Rent Expense` account, **Debit 1,000**, **Branch = Riyadh**.
4. Add line 2: `HO Bank Account`, **Credit 1,000**, **Branch = HO**.
5. Save.

The system auto-adds two more lines:

| Account | Branch | Dr | Cr |
|---|---|---|---|
| Rent Expense | Riyadh | 1000 | |
| HO Bank Account | HO | | 1000 |
| Due to HO | Riyadh | | 1000 |
| Due from Riyadh | HO | 1000 | |

Submit the JE. Each branch now has balanced books:
- **Riyadh:** Rent Expense (Dr 1000) ↔ Due to HO (Cr 1000)
- **HO:** Due from Riyadh (Dr 1000) ↔ Bank (Cr 1000)
- **Consolidated:** Rent (Dr 1000) ↔ Bank (Cr 1000) — inter-branch lines net to zero.

### Scenario B — Cash transfer HO → Branch

Same flow. Enter:
- Line 1: Riyadh Bank, **Dr 5000**, Branch = Riyadh
- Line 2: HO Bank, **Cr 5000**, Branch = HO

Save. System adds Due-from / Due-to legs.

### Scenario C — Stock transfer between branches (automatic)

Two routes — both produce the same accounting outcome:

**Route 1: Stock Transfer workflow (preferred for branch users)**
1. Material Request → Stock Transfer → Approval.
2. On approval, the system creates the Stock Entry as usual.
3. **Automatic**: if source warehouse and target warehouse belong to different branches, a companion Journal Entry records the inter-branch obligation at valuation cost. Source DocType = `Stock Transfer`.

**Route 2: Direct Stock Entry (Material Transfer)**
1. Stock Manager opens Stock Entry directly, picks `Material Transfer`, fills source warehouse + target warehouse + items.
2. On submit:
   - System resolves each warehouse → Branch via Branch Configuration.
   - **If source and target sit on the same branch** (e.g. both warehouses under HO) → no companion JE. Standard Stock Entry GL is enough; intra-branch shuffle.
   - **If source ≠ target branch** → system re-tags the Stock Entry's own GL (source legs get source branch, target legs get target branch) and creates a companion JE at valuation cost. Source DocType = `Stock Entry`.

The companion JE is linked to the source document (Stock Transfer or Stock Entry). Cancelling the source document auto-cancels the companion JE.

**Same-branch warehouse pair (e.g. WH-HO-1 ↔ WH-HO-2 both under HO branch)** is supported natively — no obligation is recorded because there is no inter-branch movement. Both Stock-in-Hand GL legs end up branch=HO.

**Multi-pair Stock Entry (rare):** if a single SE moves stock across multiple branch pairs (e.g. items going Riyadh→Jeddah AND Riyadh→Malaz in one doc), the system logs a hint and skips companion-JE creation. Split the SE into separate one-pair documents.

## Auto-injected line markers

Every auto-generated line carries:
- `Auto-Inserted (Inter-Branch)` flag = ticked
- `Source DocType` = "Journal Entry" (manual JE) or "Stock Transfer" (companion)
- `Source Document` = the originating document name

These fields are read-only and exist for traceability and audit.

## Multi-branch (3+) Journal Entries — bridge mode

When a single Journal Entry needs to touch 3 or more branches (e.g. HO bank pays one bill consumed by Riyadh + Jeddah + Bahra together), the system needs to know which branch is the **bridge** (the implicit counterparty for every other branch).

### One-time setup
1. Open the **Company** record.
2. Set **Inter-Branch Bridge Branch** = `HO` (or whichever branch acts as your hub).
3. Save.

### How it works
For a JE touching N branches, with the bridge among them:
- Every non-bridge branch is paired against the bridge.
- For each non-bridge branch the system injects 2 legs (one on the branch's side, one on the bridge's side).
- Total injected rows = 2 × (N − 1).
- After injection every branch — including the bridge — nets to zero.

### Example
HO bank pays a 1,500 bill split: Riyadh consumes 1,000, Jeddah consumes 500.

Operator enters 3 lines:
| Account | Branch | Dr | Cr |
|---|---|---|---|
| Office Rent | Riyadh | 1,000 | |
| Office Rent | Jeddah | 500 | |
| HO Bank | HO | | 1,500 |

System auto-adds 4 lines (2 per non-bridge branch):
| Account | Branch | Dr | Cr |
|---|---|---|---|
| Due to HO | Riyadh | | 1,000 |
| Due from Riyadh | HO | 1,000 | |
| Due to HO | Jeddah | | 500 |
| Due from Jeddah | HO | 500 | |

Each branch's books balance. Riyadh owes HO 1,000. Jeddah owes HO 500. HO is owed 1,500 in total.

### Rejection cases
- **Bridge not configured** → error: *"Multi-branch entries require the Company's Inter-Branch Bridge Branch setting."* Either set the bridge or split into separate two-branch JEs.
- **Bridge not in JE** → error: *"the configured bridge branch X is not among them. Add at least one line on branch X, or split into separate two-branch Journal Entries."*

## Rules and limits

1. **2-branch JE → counterparty inferred from imbalance.** No bridge needed.
2. **3+-branch JE → bridge must be configured + present.** Otherwise rejected.
2. **JE must be globally balanced before save.** Standard ERPNext rule: total debits = total credits. The auto-injector only handles per-branch imbalance, not global imbalance.
3. **Branch is mandatory on every GL-posting line.** This is enforced per Company at the GL layer (set up via the Branch accounting dimension's per-company `mandatory_for_bs` and `mandatory_for_pl` flags).
4. **Cut-over is prospective only.** Entries dated before the cut-over never get auto-injected. There is no historical restate.
5. **Settlement is NOT in Phase 1.** When two branches need to settle accumulated balances against a clearing account or via cash movement, use a manual JE for now. Phase 2 will add a guided settlement flow.
6. **Salary, Expense Claim, Vendor-on-behalf are NOT in Phase 1.** For now, record those events with manual JEs that include both branches' lines — the auto-injector will balance them per-branch.

## Reconciliation report

**Reports → Inter-Branch Reconciliation**

Filters: Company (required), From Date, To Date.

Output: matrix view where rows are "from" branches and columns are "to" branches. Each cell shows the net balance owed.

**Health check:** for any pair (Branch A → Branch B vs Branch B → Branch A), the two cells should sum to zero. If they don't, it indicates one of:
- A missing counterparty tag on a manual JE
- An unbalanced manual JE
- A timing difference (one side hasn't posted yet)

Investigate and fix any non-zero diagonal pairs before period-end.

## Adding a new branch

1. Create the Branch master normally.
2. On save, the system shows: *"Inter-Branch account heads have been auto-loaded for branch <Name>. Verify the Chart of Accounts before posting transactions."*
3. The new branch automatically gets `Due from <each existing branch>` and `Due to <each existing branch>` accounts created in the COA, AND every existing branch gets `Due from <new>` and `Due to <new>` accounts.
4. No further setup needed.

## Branch auto-fill on stock-side documents

ERPNext rejects any GL posting whose Branch dimension is empty (per-Company `mandatory_for_bs` / `mandatory_for_pl` flags set during activation). To prevent operators from hitting this on every Purchase Receipt / Stock Reconciliation / Stock Entry / etc., a `validate` hook auto-fills the Branch field from each item row's warehouse → branch mapping.

**Hook coverage:**
- Stock Entry
- Stock Reconciliation (including opening stock)
- Purchase Receipt
- Delivery Note
- Purchase Invoice
- Sales Invoice

**Behaviour:**
- For each item row with no `branch`, the warehouse → branch mapping is looked up and the field is filled.
- Header `branch` is set to the first row that resolves successfully — operator can override.
- If a row's warehouse has no branch mapping (e.g. Damage warehouses before they're added to Branch Configuration), `branch` stays empty for that row → ERPNext throws the standard *"Accounting Dimension Branch is required for 'Balance Sheet' account..."* error. Map the warehouse via Branch Configuration to fix.

## Warehouse → Branch mapping (operational requirement)

Every leaf warehouse on the Company that posts to GL must appear in at least one **Branch Configuration → Warehouses** child table row. Without the mapping:
- Stock-side documents fail with the dimension error
- Direct Stock Entry inter-branch hook silently skips companion JE creation (one warehouse unresolvable)
- Reconciliation report cannot place that warehouse's GL on any branch row

**Special cases on RMAX:**
- **Damage warehouses** (`Damage Jeddah - CNC`, `Damage Riyadh - CNC`) — pick one of:
  - Map per city (Damage Jeddah → Jeddah, Damage Riyadh → Riyadh) — damage write-off stays branch-local
  - Map all under HO — centralized damage handling; any branch → its city's Damage WH = inter-branch obligation to HO
  - Map under a dedicated `Damage` branch — cleanest separation if damage P&L is its own center

## Cancelling Stock Entry / Stock Transfer

Cancelling either document automatically cancels its companion JE (mirror hook on `on_cancel` for both source documents). The reversal posts canceling GL Entries.

If the underlying issue is a wrong **valuation rate** at the source warehouse (Bin's `valuation_rate` inflated by a previous bad PR / Stock Reconciliation / LCV), the inter-branch JE faithfully copies that bad number — the module is NOT the source of truth for valuation. Fix the upstream stock data (cancel the offending PR / reconcile / LCV), then re-create the SE/ST.

## Viewing the companion JE from a Stock Entry / Stock Transfer

Two paths surface the linked JE:

1. **Top button bar** — the SE/ST form shows a custom button labelled `Inter-Branch JE → ACC-JV-...` for each linked JE. Click to navigate.
2. **Connections sidebar** — the standard Connections panel lists "Journal Entry" under an "Inter-Branch" section.

Both rely on the JE header fields `Inter-Branch Source DocType` (= "Stock Entry" or "Stock Transfer") and `Inter-Branch Source Document` (= source doc name). These fields are read-only — set automatically by the hooks at injection time.

For pre-Phase-2 JEs that lack the header fields, run the backfill helper (admin only):
```
bench --site rmax_dev2 execute rmax_custom.inter_branch.backfill_je_header_source
```
Idempotent — only updates JEs whose header is empty AND whose child rows agree on a single source.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Save fails with "Inter-Branch auto-injection supports exactly two branches…" | JE has 3+ branches across its lines | Split into multiple JEs, one per branch pair |
| Branch field rejected as required | Mandatory dimension is on, branch column empty | Pick a Branch on every line |
| Cross-branch JE saves but no auto-legs added | Cut-over date not set on Company, OR posting_date is earlier than cut-over | Set/adjust **Inter-Branch Cut-Over Date** on the Company |
| Branch has no Inter-Branch leaves in COA | Branch was created before this feature was deployed | Re-save the Branch master OR run `bench execute rmax_custom.inter_branch.on_branch_insert` for that Branch (admin only) |
| Reconciliation report shows non-zero diagonal pair | Manual JE was unbalanced per-branch, OR a Stock Transfer's companion JE wasn't created (warehouse not mapped to a branch via Branch Configuration) | Check Branch Configuration → Warehouses mapping; investigate the offending JE |
| Stock Transfer submission fails with "Inter-Branch companion JE failed" | Either source or target warehouse isn't mapped to a Branch via Branch Configuration, or the company has no `default_currency` set | Map the warehouse to its Branch in Branch Configuration; ensure Company default currency is set |
| Stock Entry submitted but no companion JE created | At least one warehouse on the SE has no Branch Configuration mapping (e.g. Damage WH) — hook silently skipped | Map the warehouse via Branch Configuration → Warehouses, then re-submit the SE (cancel + recreate) |
| "Accounting Dimension Branch is required for 'Balance Sheet' account..." on Stock Reconciliation / opening stock / Purchase Receipt | Item row's warehouse has no Branch mapping, OR a row has no warehouse at all | Map every warehouse in Branch Configuration; the validate hook auto-fills branch from warehouse mapping |
| Companion JE amount looks wildly wrong | Source warehouse's Bin `valuation_rate` is inflated/incorrect (bad past Purchase Receipt / Stock Reconciliation / LCV) | Trace via Stock Ledger Entry → fix offending upstream document → cancel + re-submit the SE |
| "Could not find Row #1: Source Document: SE-..." on JE insert | Stub / test fixture with a non-existent source doc name | Use a real submitted Stock Entry / Stock Transfer name (Dynamic Link is validated by Frappe at insert) |
| Multi-pair Stock Entry produces no JE and an Error Log entry | One SE moves stock across multiple branch pairs (Phase 1 supports single-pair only) | Split the SE — one Material Transfer per branch pair |

## What changed in this release

| Component | Change |
|---|---|
| Custom Fields on Journal Entry Account | `Auto-Inserted (Inter-Branch)`, `Source DocType`, `Source Document` |
| Custom Fields on Journal Entry header | `Inter-Branch Source DocType`, `Inter-Branch Source Document` (mirror of child fields, powers Connections sidebar) |
| Custom Fields on Company | `Inter-Branch Cut-Over Date`, `Inter-Branch Bridge Branch` |
| Chart of Accounts | `Inter-Branch Receivable` (Asset, group) + `Inter-Branch Payable` (Liability, group) per root Company; lazy `Due from / Due to <Branch>` leaves on demand |
| Branch master | `after_insert` hook auto-creates leaf accounts both directions |
| Journal Entry | `validate` hook auto-injects balancing inter-branch legs (chained after the BNPL clearing guard); supports 2-branch direct mode + 3+ branch bridge mode |
| Stock Transfer | `on_submit` triggers companion JE; `on_cancel` reverses it |
| Stock Entry (direct path) | `on_submit` creates companion JE for cross-branch Material Transfer (skips when `flags.from_stock_transfer`); `on_cancel` reverses |
| Stock-side validate hook | Auto-fills `branch` from item warehouse on Stock Entry, Stock Reconciliation, Purchase Receipt, Delivery Note, Purchase Invoice, Sales Invoice |
| Connections sidebar | Stock Entry + Stock Transfer dashboards show linked Inter-Branch JE |
| JS — Stock Entry form | Top-bar button + sidebar badges for linked JE on submitted Material Transfer SEs |
| Reports | Script Report "Inter-Branch Reconciliation" with health check |
| Backfill helper | `rmax_custom.inter_branch.backfill_je_header_source` populates header source fields on pre-Phase-2 companion JEs |

## Out of scope (deferred to Phase 2+)

- Settlement / clearing account flow with hard cap
- Salary auto-routing per employee branch
- Expense Claim auto-routing per claimant branch
- Vendor-on-behalf scenarios
- Branch-wise Trial Balance / P&L / Balance Sheet (rich variants beyond reconciliation)
- HO overhead allocation rule engine
- Historical-period restate

## Support

- Dev URL: https://rmax-dev.fateherp.com
- Source: `rmax_custom/inter_branch.py`
- Plan: `docs/superpowers/plans/2026-04-28-inter-branch-rp-foundation.md`
- Tests: `rmax_custom/test_inter_branch.py` (run with `bench --site rmax_dev2 run-tests --module rmax_custom.test_inter_branch`)
