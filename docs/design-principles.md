# Design Principles

Good design reduces the number of things you must understand at once.

A messy project usually is not messy because it has too few layers. It is messy because the boundaries are unclear, so every change leaks across UI, API, database, auth, config, docs, and tests.

## 1. Design Around Domains

Group code by business capability, not by technical type.

Weak shape:

```text
routes/
services/
components/
utils/
```

Better shape:

```text
features/submissions/
features/leaderboard/
features/admin/
features/classroom-labs/lemon-market/
```

A feature should own its API, data model, business rules, hooks, UI, and tests as much as possible.

## 2. Separate What From How

Business logic should say what happens. Infrastructure should say how it happens.

`SubmissionService.submit_strategy()` should not care whether files are saved locally, S3, SQLite, Postgres, Docker, or background tasks. It should coordinate the business flow.

File storage, database writes, queueing, and runner execution are adapters.

## 3. Keep Dependency Direction One-Way

Good dependency flow:

```text
UI -> API client -> backend route -> service -> repository/runner
```

Bad dependency flow:

```text
service imports route helper
repository knows HTTP error
UI knows database-shaped weirdness
runner mutates app config
```

Lower-level code should not know about higher-level delivery details.

## 4. Pages Should Not Be Controllers

A React page should mostly assemble:

```text
data hook + state hook + presentational components
```

If a page has many `useState`, `useEffect`, filters, mutations, form parsing, validation, and display logic, extract a feature model hook.

For example:

```ts
useAdminDashboardModel()
useLemonMarketTeacherConsole()
useSubmissionDetailModel()
```

Then the page becomes readable.

## 5. One Source Of Truth For Contracts

If backend schemas, docs, and frontend types must all be manually kept in sync, drift is guaranteed.

Better:

```text
Pydantic schemas -> OpenAPI -> generated TypeScript types -> typed API client
```

Docs can still be generated, but docs should not be the only contract mechanism.

## 6. Services Should Use Repositories, Not Raw Tables Everywhere

Database code should be split by ownership.

```text
TeamsRepository
SubmissionsRepository
ConfigRepository
LemonMarketRepository
```

Then services express intent:

```python
team = teams.authenticate(name, password)
submission = submissions.create(...)
jobs.enqueue_scoring(submission.id)
```

instead of route handlers hand-stitching SQL-shaped dictionaries.

## 7. Put Workflows In Application Services

A workflow is usually where mess grows.

Example submission workflow:

```text
validate upload
authenticate team
create submission
save file
enqueue scoring
return public submission
```

That should live in a `SubmissionService`, not directly in `app.py`.

Routes should translate HTTP into service calls.

## 8. Use Explicit Boundaries For Async Work

Scoring is not just a function call. It is a job.

Even if FastAPI background tasks are used locally, design it as:

```text
SubmissionJobQueue
SubmissionRunner
SubmissionResultWriter
```

That makes it easy later to move to RQ, Celery, or Arq without rewriting business logic.

## 9. Prefer Small Internal APIs Over Shared Utility Soup

A `utils.ts` or `helpers.py` file becomes a drawer full of miscellaneous sharp objects.

Prefer:

```text
features/submissions/staleness.py
features/admin/config_draft.ts
features/classroom-labs/lemon-market/settlement.ts
```

Name code after the concept it belongs to.

## 10. Design For Deletion

A good module can be removed with limited damage.

Ask:

- If I delete a classroom lab, how many unrelated files break?
- If I replace SQLite, where does the pain concentrate?
- If I change scoring, do I need to touch UI tables manually?

The answer tells you where boundaries are weak.

## 11. Keep Domain Rules Pure When Possible

Rules like scoring, settlement, validation, ranking, and stale detection should be pure functions/classes with simple inputs and outputs.

That makes them easy to test and hard to accidentally couple to HTTP, React, or SQLite.

## 12. Test Boundaries, Not Implementation Noise

A healthy test mix:

```text
domain tests: scoring, settlement, validation
service tests: workflow behavior
API tests: route contract and auth
frontend tests: user-visible states
e2e tests: critical happy paths
```

Do not test every tiny component. Test the contracts where bugs would hurt.

## 13. Make Names Match Responsibility

Bad names hide design problems.

If something is called:

```text
Database
App
AdminPage
api.ts
utils
```

and it is huge, the name probably became too vague.

Better names force better thinking:

```text
SubmissionRepository
LemonMarketService
AdminTeamsPanel
submissionApi
scoreBreakdownModel
```

## 14. Avoid Layer Theater

More layers are not automatically better.

Bad:

```text
Controller -> Manager -> Service -> Handler -> Processor -> Helper
```

Good:

```text
Route -> Service -> Repository/Adapter
```

Add a layer only when it creates a real boundary.

## 15. Optimize For The Next Developer's Mental Model

Every file should answer quickly:

```text
What does this own?
Who calls it?
What can it call?
What data shape does it return?
Where are its tests?
```

If a file cannot answer those questions, split it or rename it.

## Strongest Advice

Move from technical folders plus big central files to feature-owned modules with clean service, repository, and API boundaries. That will keep the system calmer as it grows.
