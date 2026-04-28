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

Use the existing **Stock Transfer** workflow:
1. Material Request → Stock Transfer → Approval.
2. On approval, ERPNext creates the Stock Entry as usual.
3. **Automatic**: if source warehouse and target warehouse belong to different branches, the system creates a companion Journal Entry recording the inter-branch obligation at valuation cost.

The companion JE is linked back to the Stock Transfer (visible on the JE's Source DocType / Source Document fields). If you cancel the Stock Transfer later, the companion JE is auto-cancelled.

## Auto-injected line markers

Every auto-generated line carries:
- `Auto-Inserted (Inter-Branch)` flag = ticked
- `Source DocType` = "Journal Entry" (manual JE) or "Stock Transfer" (companion)
- `Source Document` = the originating document name

These fields are read-only and exist for traceability and audit.

## Rules and limits

1. **Two branches max per JE.** A Journal Entry can touch at most 2 branches. If you try to post a JE that involves 3 or more branches, save will fail with: *"Inter-Branch auto-injection supports exactly two branches per Journal Entry. Please split into separate Journal Entries — one per branch pair."*
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

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Save fails with "Inter-Branch auto-injection supports exactly two branches…" | JE has 3+ branches across its lines | Split into multiple JEs, one per branch pair |
| Branch field rejected as required | Mandatory dimension is on, branch column empty | Pick a Branch on every line |
| Cross-branch JE saves but no auto-legs added | Cut-over date not set on Company, OR posting_date is earlier than cut-over | Set/adjust **Inter-Branch Cut-Over Date** on the Company |
| Branch has no Inter-Branch leaves in COA | Branch was created before this feature was deployed | Re-save the Branch master OR run `bench execute rmax_custom.inter_branch.on_branch_insert` for that Branch (admin only) |
| Reconciliation report shows non-zero diagonal pair | Manual JE was unbalanced per-branch, OR a Stock Transfer's companion JE wasn't created (warehouse not mapped to a branch via Branch Configuration) | Check Branch Configuration → Warehouses mapping; investigate the offending JE |
| Stock Transfer submission fails with "Inter-Branch companion JE failed" | Either source or target warehouse isn't mapped to a Branch via Branch Configuration, or the company has no `default_currency` set | Map the warehouse to its Branch in Branch Configuration; ensure Company default currency is set |

## What changed in this release

| Component | Change |
|---|---|
| Custom Fields on Journal Entry Account | Added `Auto-Inserted (Inter-Branch)`, `Source DocType`, `Source Document` |
| Custom Field on Company | Added `Inter-Branch Cut-Over Date` |
| Chart of Accounts | Added `Inter-Branch Receivable` (Asset, group) + `Inter-Branch Payable` (Liability, group) per root Company |
| Branch master | New `after_insert` hook auto-creates leaf accounts |
| Journal Entry | New `validate` hook auto-injects balancing inter-branch legs (chained after the BNPL clearing guard) |
| Stock Transfer | `on_submit` triggers companion JE; `on_cancel` reverses it |
| Reports | New script report "Inter-Branch Reconciliation" |

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
