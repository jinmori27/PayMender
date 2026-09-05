# Reviewer runbook

PayMender has three deliberately separate evidence paths. Synthetic results are never presented as merchant uplift, and real provider evidence always means Razorpay Test Mode.

## 1. Clean clone and automated proof

```powershell
Copy-Item .env.example .env.local
.\scripts\Set-OperatorToken.ps1
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements-dev.txt
Set-Location frontend
pnpm install --frozen-lockfile --ignore-scripts
Set-Location ..
.\scripts\Verify-PayMender.ps1
```

The verification gate covers backend behavior, dependency consistency and advisories, tracked secrets, frontend types/build, Chrome reviewer flows, and the contained Reliability Lab. Browser coverage includes queue search, slow case responses, refresh failures, reset confirmation and mobile layout. The committed backend lock is generated with:

```powershell
$env:UV_CACHE_DIR = Join-Path $PWD ".runtime\uv-cache"
uv pip compile backend\requirements.txt --output-file backend\requirements.lock
```

## 2. Synthetic demo

Keep `DEMO_MODE=true`, start with `.\scripts\Start-PayMender.ps1`, and open `http://127.0.0.1:8000`. Demo mode remains offline even if Razorpay credentials happen to exist.

1. Unlock with the token stored in `.env.local`.
2. Show a gated halted case and a contact-capped `STOP_CONTACT` case.
3. Run the held-out evaluation and point to mean plus standard deviation for every metric.
4. Run each Reliability Lab check. Confirm every assertion says `Passed` and copy the displayed evidence IDs into review notes.
5. Describe the audit as application-enforced append-only history within an evidence run. The explicit demo reset clears that synthetic run; the SQLite file is not immutable storage.

### Command-center controls

- Search by customer, subscription, case ID or failure reason; filter by subscription status and sort by amount, overdue days or last update. Filtering the queue keeps your currently reviewed case open.
- Use **Refresh portfolio** to fetch current cases and evidence without resetting the run. A failed refresh visibly marks the data as stale and disables approval until a successful refresh. While switching cases, decisions stay unavailable until the selected case loads.
- Switch **Audit scope** to **Selected case** and expand **Evidence references** to correlate event and case IDs. This view filters the latest 80 loaded run events; it is not a complete historical export.
- Use **Export evaluation** for a JSON copy of the displayed synthetic evaluation, including its disclaimer, run ID and every metric's mean and standard deviation. This download is synthetic evidence, not Razorpay provider proof.
- **Reset demo data** asks before removing the current synthetic run. **Keep current run** cancels; **Start new run** resets the cases and clears earlier Reliability Lab results.

## 3. Razorpay Test Mode evidence

Set `DEMO_MODE=false` and add only local test credentials. Follow [RAZORPAY_TEST_REHEARSAL.md](RAZORPAY_TEST_REHEARSAL.md) for the provider-authentic batch and dashboard correlation. Do not reuse synthetic cases or screenshots as provider proof.

Completion requires at least five signed failure events across three subscriptions, two approved actions, one matching `payment_link.paid` recovery, one policy stop and one duplicate delivery. Capture provider event IDs alongside PayMender case, execution and audit IDs. Stop the public tunnel immediately afterward.

## Submission handoff

- Verify the repository and video links in a signed-out browser.
- Keep `.env.local`, SQLite/WAL files, terminal history and account identifiers out of screenshots and video.
- Run `python scripts\check_secrets.py` immediately before the final push.
- Confirm the video is no longer than five minutes and distinguishes synthetic evaluation from Razorpay Test Mode recovery.
