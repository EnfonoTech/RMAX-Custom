# Incident Log — RMAX Custom

## 2026-04-14: Session 1 — Major Implementation

### Issues Fixed (in order)

1. **Branch Configuration missing Company field** — Added Company to Branch Config, auto-creates Company User Permission
2. **Session Defaults showing wrong company** — Set is_default=1 on Company/Warehouse/Cost Center User Permissions
3. **Cost Center not auto-filling** — Set is_default=1 on Cost Center permission too
4. **Sales Tax template "Main - CNC" permission error** — Auto-grant company default cost center permission (is_default=0)
5. **Item Default permission error (Stores - R)** — ignore_user_permissions on Item Default WH/CC fields
6. **Stock Transfer list not showing incoming transfers** — Added permission_query_conditions + ignore_user_permissions on ST WH fields
7. **Branch filters using User Permissions instead of Branch Config** — Changed to query Branch Configuration directly
8. **Snow Light warehouse showing for wrong user** — Cleaned rogue permissions, used Branch Config as source of truth
9. **MR target warehouse showing only one** — Explicit JS fetch of permitted WHs + ignore_user_permissions override
10. **MR Item cost_center permission error** — ignore_user_permissions on MR Item cost_center
11. **Stock Entry permission error after ST approval** — ignore_user_permissions on SE WH/CC fields
12. **"No permission for Accounts Settings"** — Added read permissions for Account, Accounts Settings, Mode of Payment, etc.
13. **Stock Transfer auto-creating warehouse permissions** — REMOVED dangerous before_save code, cleaned 11 rogue permissions
14. **Self-approval on Stock Transfer** — Blocked creator from approving their own ST
15. **MR list showing all documents** — Fixed filter, removed item-level subquery
16. **"Create → Stock Transfer" button not appearing** — Changed from async:false to async callback, created whitelisted API
17. **MR set_warehouse permission blocking document open** — Added ignore_user_permissions Property Setter (was missing from hooks)
18. **Workflow "Warehouse User" role doesn't exist** — Changed to "Stock User" (correct ERPNext name)
19. **Role assignment failing silently** — Changed to direct Has Role insert instead of user_doc.add_roles()
20. **Branch User role not assigned to new users** — Fixed _assign_role, re-saved all branch configs

### Features Implemented

1. Branch Configuration with Company field + auto-permissions
2. Branch User role with 25 DocType permissions (via after_migrate)
3. Stock Transfer branch-based approval workflow
4. Material Request → Stock Transfer flow (replacing Stock Entry)
5. Global Enter key navigation
6. Item cost field restrictions for Branch User
7. Sales Invoice list standard filters (Grand Total, Total Qty, Mobile)
8. Branch-wise list filtering for 8 DocTypes
9. POS payment popup for Cash mode
10. Quick customer creation from Sales Invoice
11. Warehouse stock panel
12. Landed Cost Voucher CBM distribution
13. VAT/phone validation
14. Final GRN flow
15. Bulk Purchase Invoice from multiple PRs
16. Urgent priority on Material Request
17. Role selector in Branch Configuration User table
