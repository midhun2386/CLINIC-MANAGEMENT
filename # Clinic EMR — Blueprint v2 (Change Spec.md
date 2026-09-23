# Clinic EMR — Blueprint v2 (Change Spec)

This document only covers what's **changing** from the version already built/running
in Antigravity. Treat it as a delta spec your dev environment (or Antigravity) can
implement against the existing project.

---

## 1. Roles simplified: Admin & Staff

Replace the previous 3-role system (admin/doctor/receptionist) with **two** roles.

| Action | Admin | Staff |
|---|---|---|
| Create patient / treatment entry | ✅ | ✅ |
| Edit patient / treatment entry | ✅ | ⚠️ only after admin approves |
| Delete patient / treatment entry | ✅ | ⚠️ only after admin approves |
| Create staff account | ✅ | ❌ |
| Delete staff account | ✅ | ❌ |
| Edit any staff username/password | ✅ | ❌ (staff cannot self-edit either — must go through admin) |

**New model: `ApprovalRequest`** — staff edits/deletes don't happen immediately; they
create a pending request an admin must approve or reject.

```
ApprovalRequest
  id
  requested_by        (staff user id)
  action_type          "EDIT" | "DELETE"
  target_type          "PATIENT" | "TREATMENT"
  target_id
  proposed_changes     JSON  (for EDIT — the new field values; null for DELETE)
  status                "PENDING" | "APPROVED" | "REJECTED"
  reviewed_by           (admin user id, nullable until reviewed)
  created_at / reviewed_at
```

**New endpoints:**
- `POST /api/requests` — staff submits an edit/delete request
- `GET /api/requests?status=pending` — admin views the queue
- `PATCH /api/requests/<id>` — admin approves (applies the change) or rejects

**Existing endpoints to lock down:**
- `PUT /records/<id>` and `DELETE /records/<id>` (and the equivalent for patients)
  become **admin-only** for direct execution. Staff calling these gets redirected
  to create an `ApprovalRequest` instead (or the frontend simply shows "Request
  edit" / "Request delete" buttons for staff instead of direct Save/Delete).

---

## 2. Patient details — required vs optional fields

| Field | Required? |
|---|---|
| Name | **Required** |
| Date of birth | **Required** |
| Phone number | **Required** |
| Gender | **Required** |
| Photo | Optional |
| Email | Optional |
| Additional phone number | Optional |
| Address | Optional |

**Patient model changes:**
```
Patient
  full_name            required
  date_of_birth         required
  phone                 required
  gender                required
  photo_url             optional (store file, save path/URL here)
  email                 optional
  additional_phone      optional
  address                optional
```
Photo handling: store uploaded image in a `/uploads/patients/` folder (or an
object storage bucket if you move beyond a single server later) and save only
the file path/URL in the DB — never store binary image data directly in SQLite.

---

## 3. Treatment entries — replaces the old generic "MedicalRecord"

Rename `MedicalRecord` → `TreatmentEntry` and change its fields to:

```
TreatmentEntry
  patient_id
  date_of_treatment        required
  consultation_number       required   (1st, 2nd, 3rd ... nth visit — auto-increment
                                        per patient, but editable in case of
                                        correction)
  medicine                  text
  treatment_name             text   (the "problem"/diagnosis-equivalent field)
  remark                     text
  next_consultation          date, optional
  payment                    number (amount)
  payment_method             text (e.g. Cash / Card / UPI / Insurance)
  created_by, created_at     (as before, for audit trail)
```

**Consultation numbering:** when a new `TreatmentEntry` is created for a patient,
auto-set `consultation_number = (count of existing entries for this patient) + 1`,
but let staff/admin override it manually if a past record needs correcting.

---

## 4. Data export — Excel & PDF column spec

Both Excel and PDF exports use the **same column set and order**:

| # | Column |
|---|---|
| 1 | Name |
| 2 | Date of Birth |
| 3 | Phone Number |
| 4 | Treatment Name |
| 5 | Next Consultation |
| 6 | Payment |
| 7 | Payment Method |
| 8 | Gender |

This is a join across `Patient` + `TreatmentEntry` (one row per treatment entry,
patient fields repeated). Existing export code should switch from the old
`diagnosis/condition_tags/notes/prescription` column set to this one, and pull
`next_consultation`, `payment`, `payment_method` from `TreatmentEntry` instead.

Word export: keep as a flexible/full-detail dump (all fields) unless you want it
restricted to the same 8 columns too — confirm if you want Word matched to
Excel/PDF or left as the fuller version.

---

## 5. Chatbot — full data access, real Q&A

Upgrade from the rule-based keyword parser to an **AI-powered** chatbot that can
answer open-ended questions against everything stored (patients + treatment
entries), not just simple filtered searches.

**Approach (function-calling / tool-use pattern):**
1. User asks a free-text question (e.g. *"which patients have a follow-up next
   week?"*, *"how much did we collect from cash payments this month?"*, *"show
   me Raghav's treatment history"*).
2. The backend sends the question to an LLM (e.g. Claude via the Anthropic API)
   along with a small set of **tool definitions** it's allowed to call, such as:
   - `search_patients(name, gender, phone)`
   - `search_treatments(patient_name, treatment_name, date_from, date_to, payment_method)`
   - `get_upcoming_consultations(date_from, date_to)`
   - `get_payment_totals(date_from, date_to, group_by)`
3. The LLM decides which tool(s) to call with what filters; the backend runs the
   *actual* DB query (still through SQLAlchemy — the LLM never touches the
   database directly), returns the results to the LLM, and the LLM composes a
   plain-language answer.
4. This keeps a strict boundary: the AI can only retrieve data through the
   defined tool functions (so it can't be tricked into leaking data outside
   normal query rules), and every tool call is still subject to the same
   role checks (staff cannot pull data they wouldn't otherwise be allowed to
   see, once you have role-based data visibility rules).

This replaces the old `interpret_message()` regex parser — the plug-in point
already left in the chatbot route is exactly where this tool-calling logic goes.

**New endpoint stays the same:** `POST /api/chatbot/query` — request/response
shape doesn't need to change, only the internals.

---

## 6. Summary of model/endpoint changes to implement

- [ ] Simplify `User.role` to `admin` / `staff` only; migrate existing doctor/receptionist users to `staff`
- [ ] Add `ApprovalRequest` model + endpoints; gate staff edit/delete through it
- [ ] Update `Patient` model: add `photo_url`, `email`, `additional_phone`; keep `full_name`, `date_of_birth`, `phone`, `gender` required
- [ ] Rename `MedicalRecord` → `TreatmentEntry`; replace fields per §3
- [ ] Update Excel/PDF export column set per §4
- [ ] Replace chatbot's rule-based parser with tool-calling AI flow per §5
- [ ] Update frontend forms (patient form, treatment form) to match new required/optional fields
- [ ] Update frontend to show "Request edit/delete" for staff vs direct "Save/Delete" for admin, plus an admin "Approval queue" screen