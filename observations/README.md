# Observation transcripts

Raw request/response records written by [`scripts/observe_aws.py`](../scripts/observe_aws.py), one
JSON file per AWS call, under `observations/<YYYY-MM-DD>/`.

A vector with `status: observed` carries prose in `observation.evidence` and a path in
`observation.transcript` pointing here. The prose says what the result means; the transcript is what
was actually sent and received — the exact request document, the verbatim response, the argv, the
CLI version, and the derived verdict.

**Why these are committed.** `evidence` is prose, and prose loses the detail you did not know
mattered. The 2026-08-30 `iam:CreateRole` probe was hand-run and its condition operator was never
recorded; the strength of the finding turned on exactly that, and github-aws 0.3.3 had to narrow a
headline claim after the overstated version had already shipped in PyPI 0.3.0. A committed
transcript lets any reader audit a promoted vector without an AWS account and without re-running
anything — which is the standard this corpus asks of the tools it grades.

**Safety.** AWS account ids are replaced with `<ACCOUNT-ID>` before anything is written to disk (see
`scrub()` in the harness, pinned by `tests/test_observe_aws.py`). Transcripts hold synthetic
policies over corpus vectors and fictional orgs; they carry no credentials and no real
infrastructure. Failed and disagreeing runs are recorded too — a rejection is evidence.

Do not hand-edit files in here. If a transcript is wrong, re-run the experiment.
