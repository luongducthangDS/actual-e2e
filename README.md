# actual-e2e: Page Object E2E framework for a real finance app

End-to-end tests for [Actual Budget](https://github.com/actualbudget/actual) v26.10.0, an open-source budgeting app,
written the way a team would maintain them for years: user journeys on top of page objects, a fresh server per test,
parallel runs, and a Playwright trace saved for every failure.

## Results

| | |
|---|---|
| Journeys | **9** end-to-end user journeys, all green |
| Stability | **5 / 5** full runs green, 3 parallel + 2 sequential ([log](docs/evidence/stability_5_runs.txt), JUnit XML per run in `docs/evidence/`) |
| Runtime on 2 vCPU | sequential 163–171 s · parallel `-n 2` 135–153 s (≈15% faster: browser and server are CPU-bound on 2 cores) |
| Isolation | every test starts its own Actual server with an empty data directory, so tests are order-independent |
| Debuggability | on failure, a Playwright trace (DOM snapshots, screenshots, network) is written to `artifacts/` and uploaded by CI |

## Journeys covered

| Journey | What it proves |
|---|---|
| First-run setup → sign in → new budget | Setting the server password does **not** sign the user in; the test pins that behaviour |
| Wrong password rejected, right one accepted | The error message is shown and the user can retry |
| New account appears in sidebar and in To Budget | Sidebar balance and budget page agree (1,250.50) |
| Categorised expense shows up in the budget | Register and budget stay consistent (spent −84.20) |
| Transfer between accounts | Both balances move (700 / 300) while To Budget stays the same |
| Edit an amount | The balance is recalculated (50 → 80) |
| Delete a transaction | Goes through the bulk-action menu and the confirmation dialog; the balance is restored |
| Search the register | Only matching rows stay visible |
| Data survives a reload | Local-first storage persists the transaction |

## Design

```
tests/test_journeys.py   what the user does          (no selectors here)
pages/app.py             LoginPage · Sidebar · AccountPage · BudgetPage
tests/conftest.py        server per test · browser per worker · trace on failure
```

- **Selector policy:** `data-testid`, then ARIA role + accessible name, then visible text. Generated CSS classes are
  never used, because they change between releases.
- **Waiting:** web-first `expect(...)` where the app exposes a state, plus short, named pauses where the register grid
  moves focus asynchronously. Stabilisation found one real cause of flakiness: pressing Escape right after **Add**
  discarded the row before it committed. The page object now waits for the commit.
- **Checked behaviour, not assumed:** typing an account name as payee and pressing Tab creates a *transfer*, not a
  new payee. This was verified before writing the transfer test, rather than coding around a guess.

## Run it

```bash
mkdir sut && (cd sut && npm i @actual-app/sync-server@26.10.0)
pip install -r requirements.txt && playwright install chromium
ACTUAL_DIR=sut pytest              # sequential
ACTUAL_DIR=sut pytest -n 2         # parallel
playwright show-trace artifacts/<test>.zip   # after a failure
```

## Interview questions this project prepares for

1. Why one server per test instead of one per session? What does it cost?
2. Why did parallelism only save ~15% here, and when would it save more?
3. What is the difference between a fixed wait and a web-first assertion, and why are both used here?
4. How would you keep these tests green when Actual renames a button?
