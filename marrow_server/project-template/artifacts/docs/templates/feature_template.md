# 🚀 Feature: [TITLE]
**Task ID:** `[ID_FROM_BACKLOG]`
**Status:** `[DRAFT / IN_PROGRESS / COMPLETED]`

## 📑 Multi-Agent Pipeline Checklist
> **Rule:** Each phase must be completed and confirmed by the human before proceeding.

### 🔍 Phase A: Discovery & Requirements (Discovery Agent)
- [ ] **Step 1:** Analyze task context & existing code skeletons.
- [ ] **Step 2:** Define User Stories & technical constraints.
- [ ] **Step 3:** Finalize Requirements section (User Confirmation required).

### 🏗️ Phase B: Design & Architecture (Architecture Agent)
- [ ] **Step 4:** Identify affected modules, classes, and dependencies.
- [ ] **Step 5:** Define Data Schemas, API changes, or Interface traits.
- [ ] **Step 6:** Approve Architectural Blueprint (User Confirmation required).

### 📝 Phase C: Planning (Planning Agent)
- [ ] **Step 7:** Break down architecture into atomic execution steps.
- [ ] **Step 8:** Define Definition of Done for each step.
- [ ] **Step 9:** Finalize Implementation Plan (User Confirmation required).

### 🛠️ Phase D: Execution (Execution Agent)
- [ ] **Step 12:** Implement code changes via the Scalpel Protocol.
- [ ] **Step 13:** Self-review, linting, and manual verification.
- [ ] **Step 14:** Run tests and document results.
- [ ] **Step 15:** Handover: update `session.md` and close task via MCP.

---

## 🎯 1. Requirements (Phases 1–3)

### Problem Statement
*Clear description of the “Why”.*

### Functional Requirements
- `REQ-01`: ...
- `REQ-02`: ...

### Constraints
*e.g. Performance limits, forbidden libraries, required design patterns.*

---

## 🏗️ 2. Architecture (Phases 4–6)

### Affected Components
*List of files or modules to be modified or created.*

### Data Flow & Logic
*How data moves through the new implementation.*

### Schema / Interface Changes
*New structs, interfaces, or database migrations.*

---

## 📝 3. Implementation Plan (Phases 7–9)

### Atomic Execution Steps
1. **Step 1:** [Action] → [Verification criteria]
2. **Step 2:** [Action] → [Verification criteria]

### Definition of Done
- [ ] Code follows SOLID principles and passes linter.
- [ ] Unit tests cover all new logic.
- [ ] Integration test confirms end-to-end behaviour.

---

## 💻 4. Execution Log (Phases 12–15)

### Implemented Changes
*Summary of what was built — paths, methods, logic.*

### Verification & Testing
- **Unit Tests:** [PASSED / FAILED]
- **Integration:** [PASSED / FAILED]
- **Evidence:** *Paste relevant test output or diff summary.*

---

## 🏁 5. Handover Note
*Summary for the next agent or the human to close the loop.*
