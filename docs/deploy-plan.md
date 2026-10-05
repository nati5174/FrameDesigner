# Deployment plan — Frame Designer

Render (backend) + Vercel (frontend). Free tiers.

---

## 0 · Rename

The GitHub repo was renamed from `FrameForge` to `frame-designer`. The README badge
URL still points to `FrameForge`; update it as part of this deploy.

---

## 1 · Client IP and rate-limit key

Browser → Vercel edge → Render load balancer → uvicorn.

At the Render service boundary, `X-Forwarded-For` looks like:
`<visitor-ip>, <vercel-egress-ip>`

The `_get_visitor_ip(request)` helper reads the **leftmost** value from the
`X-Forwarded-For` header directly:

```python
def _get_visitor_ip(request: Request) -> str:
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
```

This function is passed as `key_func` to slowapi's `Limiter`. It does **not** rely
on uvicorn `--proxy-headers` or `--forwarded-allow-ips` flags, so it behaves
identically under TestClient (where XFF headers are set explicitly in tests) and in
production.

**Spoofability:** A caller that bypasses Vercel and hits Render directly can prepend
arbitrary IPs to `X-Forwarded-For`. The per-IP rate limit is therefore spoofable for
direct callers. The **global daily SDK-call cap** (see §3) is the real backstop
against cost abuse, regardless of IP.

---

## 2 · CORS

`ALLOWED_ORIGIN` env var is set to the Vercel production URL (e.g.
`https://frame-designer.vercel.app`). The CORSMiddleware rejects cross-origin
requests from any other origin. Direct API calls (curl, scripts) bypass CORS — CORS
is a browser control only.

**Default:** `ALLOWED_ORIGIN=""` → CORS disabled, a startup warning is printed.
This is the safe-fail default (not open). Set the env var before the backend is
made public.

---

## 3 · Rate limits and daily cap

**Per-IP limits** (slowapi, key = leftmost XFF or client host):

| Endpoint | Limit |
|---|---|
| POST /parse | 10/min, 60/hr |
| POST /edit | 10/min, 60/hr |
| POST /suggest | 10/min, 60/hr |
| GET/POST /frame | 120/min |

**Daily SDK-call cap:** 200 calls/day (module-level atomic counter in
`src/framegen/_llm_counter.py`, incremented at each `client.messages.create()`
call site — `llm.py:_call`, `edit_llm.py:_call`, `rank.py:rank_and_describe`).

When the cap is hit (or the SDK fails for any reason, including a Console spending
limit): **fall back to the rule-based path**. Return the normal response shape with
`llm_available: false` and `error: "Daily AI limit reached; using the basic parser"`.
`/suggest` returns unranked candidates. No 503.

The counter resets on process restart (soft cap). A **$5/month spending limit** in
the Anthropic Console is the hard backstop.

**Token cost arithmetic** (Haiku 4.5, `claude-haiku-4-5-20251001`,
$1.00/MTok input, $5.00/MTok output — verified at
https://docs.anthropic.com/en/docs/about-claude/pricing):

| Endpoint | Input tokens | Output tokens | Cost/call |
|---|---|---|---|
| POST /edit (with spec) | ~825 | ~100 | $0.00133 |
| POST /parse | ~600 | ~100 | $0.00110 |
| POST /suggest ranking | ~350 | ~150 | $0.00110 |

200 calls/day worst case: 200 × $0.00133 = **$0.27/day ≈ $7.95/month**.

---

## 4 · Cap placement

The counter lives in `src/framegen/_llm_counter.py`. It is incremented **before**
each `client.messages.create()` call. Call sites:

- `src/framegen/parser/llm.py` — `_call()` (main + retry each count separately)
- `src/framegen/parser/edit_llm.py` — `_call()` (main + retry each count separately)
- `src/framegen/suggestions/rank.py` — `rank_and_describe()` (one call)

`DailyCapReached(Exception)` is raised if `_calls >= DAILY_CAP`. Caught in each
module: `llm.py` returns `ParseResult(outcome="not_parsed", parser_used="rule_based")`;
`edit_llm.py` returns `EditLlmResult(outcome="not_matched")`; `rank.py` returns
the original candidates. The `api.py` layer adds the cap note to the `error` field
where applicable and sets `llm_available=False`.

---

## 5 · Structured logging

Each request produces one JSON log line. Fields:

| Field | Type | Value |
|---|---|---|
| `ts` | string | UTC ISO-8601 |
| `endpoint` | string | Request path |
| `status` | int | HTTP status code |
| `latency_ms` | int | Latency in milliseconds |
| `llm_called` | bool | **True only when an SDK call was actually made** |
| `parser_used` | string\|null | `"rule_based"`, `"llm"`, `"none"`, or null |
| `frame_type` | string\|null | `"table"`, `"shelf_unit"`, or null |
| `outcome` | string\|null | outcome field of the response, or "pass"/"fail" for /frame |

No IP address in any log field. Uvicorn's default access log disabled with
`--no-access-log` in the Render start command.

`llm_called` is `False` when: the rule-based parser handled the request, the daily
cap has been hit, or no API key is set.

---

## 6 · Secret-leak tests

`tests/test_limits.py` includes a test at the API level:

1. Set `ANTHROPIC_API_KEY` to a fake value with monkeypatch
2. Inject a mock client (via `set_client()` for llm/edit_llm; via `monkeypatch.setattr`
   for rank.py's `anthropic.Anthropic`) that raises an exception whose message contains
   the fake key
3. Call `/parse`, `/edit`, and `/suggest` through TestClient
4. Assert the key is absent from every response body
5. Assert the key is absent from caplog output

The parsers already catch all exceptions and return fixed strings — these tests make
that guarantee explicit and catch regressions.

---

## 7 · Rate-limit tests

`tests/test_limits.py` includes tests that use the real slowapi middleware:

- `test_per_ip_rate_limit`: 11 calls with `X-Forwarded-For: 10.0.0.1`; 11th returns 429
- `test_different_ips_not_rate_limited_together`: 10 calls for IP A, then 1 for IP B;
  IP B gets 200
- `test_daily_cap_fallback`: monkeypatch counter to DAILY_CAP; assert 200 response,
  `llm_available=False`, `parser_used="rule_based"`, error contains cap note

An autouse fixture in `tests/conftest.py` resets both the limiter storage and the
SDK-call counter before every test, preventing order dependence.

---

## 8 · Cold-start UX

Render free dynos spin down after 15 minutes of inactivity; the first request after
spin-down can take ~30 seconds.

`frontend/hooks/useHealthCheck.ts` polls `GET /health` on mount, retrying every 3
seconds on any failure (network error, 502, 504, timeout). While health is pending,
`FrameDesigner` shows "Starting the server, this can take up to a minute…" in place
of the normal UI. When health succeeds, the normal UI appears.

A unit test (`frontend/__tests__/useHealthCheck.test.ts`) verifies the hook returns
`false` initially, `true` after a successful fetch, and retries on 502 and network errors.

---

## 9 · Python version pinning

A `.python-version` file at the repo root contains `3.11`. Render reads this file and
uses the latest 3.11.x patch release (verified at https://render.com/docs/python-version;
the file-based approach is preferred over the `PYTHON_VERSION` env var for readability).

The CI workflow already pins `python-version: "3.11"` via `actions/setup-python`.

---

## 10 · `ALLOWED_ORIGIN`

**Assumption:** the Vercel deployment URL is known before the backend is made public.
`ALLOWED_ORIGIN` must be set to that URL in the Render dashboard before traffic is
sent. If `ALLOWED_ORIGIN` is absent, CORS is disabled and a startup warning is
printed; the backend does **not** default to `*`.

---

## 11 · Production smoke checks

Run these after deploying, in order. All values are deterministic; exact numbers must
match.

```bash
# 1. Health — catalog version 3 and the deployed git commit
curl https://<render-url>/health
# Expected: {"catalog_version":3,"git_commit":"<sha>"}
# Verify: git_commit matches `git rev-parse --short HEAD` on the deployed branch

# 2. Frame — workbench 1500 × 700 mm, holds 100 kg
#    Expected: Pass, concentrated-load warning, 8 bars, $362.69, 18.12 kg
curl -s -X POST https://<render-url>/frame \
  -H "Content-Type: application/json" \
  -d '{"spec":{"frame_type":"table","width_mm":1500,"depth_mm":700,"height_mm":900,
       "profile_series":"40-series","target_load_kg":100,"centre_legs":false,
       "shelf_height_mm":null,"level_heights_mm":null,"load_per_level_kg":null}}'
# Check: bars length == 8
#        check_report.load.passed == true
#        check_report.load.governing_rail.concentrated.warning present
#        cut_list_total_cost_usd == 362.69
#        cut_list_total_weight_kg == 18.12

# 3. Failing frame — 3000 mm wide, same otherwise
#    Expected: Fail, 16.73 mm deflection vs 9.73 mm limit
#    Suggestions: reduce span to ~2300 mm / reduce load to ~55 kg / add centre legs
curl -s -X POST https://<render-url>/frame \
  -H "Content-Type: application/json" \
  -d '{"spec":{"frame_type":"table","width_mm":3000,"depth_mm":700,"height_mm":900,
       "profile_series":"40-series","target_load_kg":100,"centre_legs":false,
       "shelf_height_mm":null,"level_heights_mm":null,"load_per_level_kg":null}}'
# Check: check_report.load.passed == false
#        deflection numbers 16.73 mm vs 9.73 mm
#        suggestions contains span reduction (~2300), load reduction (~55 kg),
#        and centre_legs fix

# 4. Shelf unit — 900 × 400 × 1800 mm, 4 levels, 30 kg/level
#    Expected: 20 bars, level rail check, leg check, tipping warning
curl -s -X POST https://<render-url>/frame \
  -H "Content-Type: application/json" \
  -d '{"spec":{"frame_type":"shelf_unit","width_mm":900,"depth_mm":400,
       "height_mm":1800,"profile_series":"40-series",
       "level_heights_mm":[450,900,1350,1800],"load_per_level_kg":30,
       "centre_legs":false,"shelf_height_mm":null,"target_load_kg":null}}'
# Check: bars length == 20
#        check_report.load.levels present, level rail checks present
#        check_report.load.leg present
#        check_report.load.tipping.warning present

# 5. Edit — "make it 1200 wide"
curl -s -X POST https://<render-url>/edit \
  -H "Content-Type: application/json" \
  -d '{"text":"make it 1200 wide","spec":{"frame_type":"table","width_mm":1500,
       "depth_mm":700,"height_mm":900,"profile_series":"40-series",
       "target_load_kg":100,"centre_legs":false,"shelf_height_mm":null,
       "level_heights_mm":null,"load_per_level_kg":null}}'
# Check: outcome == "edit", spec.width_mm == 1200
#        changes contains {field: "width_mm", old: 1500, new: 1200}

# 6. Edit — "make it taller" (clarify — no number given)
curl -s -X POST https://<render-url>/edit \
  -H "Content-Type: application/json" \
  -d '{"text":"make it taller","spec":{"frame_type":"table","width_mm":1500,
       "depth_mm":700,"height_mm":900,"profile_series":"40-series",
       "target_load_kg":100,"centre_legs":false,"shelf_height_mm":null,
       "level_heights_mm":null,"load_per_level_kg":null}}'
# Check: outcome == "clarify", spec is null (frame unchanged)

# 7. Rate limit — 11 quick /parse calls (rule-based text, no LLM spend)
for i in $(seq 1 11); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST https://<render-url>/parse \
    -H "Content-Type: application/json" \
    -d '{"text":"1500 x 700 x 900 mm"}'
done
# Expected: first 10 lines = 200, 11th line = 429

# 8. Mobile check — load the Vercel URL from a phone on mobile data
# (different IP than the rate-limit test above, so still works)
# Expected: app loads, cold-start message if dyno is spinning up, then normal UI
```

---

## 12 · Files changed

| File | Action |
|---|---|
| `README.md` | Update CI badge URL (`FrameForge` → `frame-designer`) |
| `.python-version` | New — `3.11` |
| `render.yaml` | New — Render service definition |
| `pyproject.toml` | Add `slowapi>=0.1.9`; add mypy overrides for slowapi/limits |
| `src/framegen/_llm_counter.py` | New — daily SDK-call counter |
| `src/framegen/api.py` | CORS, slowapi rate limiting, JSON logging middleware, cap fallback |
| `src/framegen/parser/llm.py` | Increment counter + catch DailyCapReached in `_call()` |
| `src/framegen/parser/edit_llm.py` | Same |
| `src/framegen/suggestions/rank.py` | Increment counter in `rank_and_describe()` |
| `tests/conftest.py` | New — autouse fixture (reset counter + limiter) |
| `tests/test_limits.py` | New — rate limit, cap fallback, secret-leak tests |
| `frontend/next.config.ts` | Add `/health` rewrite |
| `frontend/hooks/useHealthCheck.ts` | New — health polling hook |
| `frontend/components/FrameDesigner.tsx` | Cold-start overlay using useHealthCheck |
| `frontend/__tests__/useHealthCheck.test.ts` | New — hook unit test |

---

## 13 · Steps you do by hand

1. **Anthropic Console:** set a $5/month spending limit.
2. **GitHub:** create repo `frame-designer` (or the existing `FrameForge` renamed to
   `frame-designer`); push this branch.
3. **Render:** create a new Web Service, connect the GitHub repo, set env vars:
   - `ANTHROPIC_API_KEY` — your key (set manually in dashboard, never in YAML)
   - `ALLOWED_ORIGIN` — the Vercel URL (set after Vercel deploy)
4. **Vercel:** import the GitHub repo, set Root Directory = `frontend`, set env var:
   - `BACKEND_URL` — the Render service URL (e.g. `https://frame-designer-api.onrender.com`)
5. **After both services deploy:** run the production smoke checks in §11 in order.
6. **Update README badge URL** to `frame-designer` if not already done.
