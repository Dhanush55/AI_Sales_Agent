# PRD — Multi-Tenant AI Voice Sales SaaS Platform

## Original problem statement
Build a multi-tenant AI Voice Sales SaaS where platform owner (Dhanush) has many
business clients (automotive workshops, computer hardware, real estate, website/
digital marketing, etc.). Each client logs in, creates campaigns with a product
"goal", uploads leads, and the AI auto-calls leads and pitches their product.
The AI adapts purely through `campaign.goal` — no industry hardcoded anywhere.

## Architecture
- **Backend**: FastAPI + MongoDB (Motor async)
- **Frontend**: React 19 + Tailwind + shadcn/ui
- **Auth**: JWT (`utils/security.py`)
- **AI**: Emergent LLM Key → GPT-4o (via `emergentintegrations`)
- **STT**: `faster_whisper` (local, free) — OpenAI Whisper as fallback
- **TTS**: `edge_tts` (local, free) — ElevenLabs as premium option
- **Telephony**: Twilio (`TwilioProvider` behind `TelephonyService`); webhooks
  at `/api/phone/webhook/{answer,gather,status}`. Gracefully reports
  `telephony_configured: false` until creds provided.
- **Deployment**: Docker + docker-compose (backend + frontend/nginx + mongo).

## Data model
- `users`: `{ id, email, password_hash, company_name, is_admin, created_at }`
- `campaigns`: `{ id, user_id, name, goal, language, status }`
- `leads`: `{ id, campaign_id, name, phone, status }`
- `calls`: `{ id, campaign_id, lead_id, status, duration, call_source,
  twilio_call_sid, dialer_session_id, started_at, ended_at }`
- `conversation_states`: `{ call_id, current_turn, not_interested_count,
  language_detected, context, turns[] }` (unique index on `call_id`)
- `dialer_sessions`: `{ id, user_id, campaign_id, lead_ids[], current_index,
  status, delay_seconds, started_at, completed_at, calls_made }`

## Core API surface
- `POST /api/auth/{register,login}` → TokenResponse (now includes `is_admin`)
- `/api/campaigns`, `/api/leads`, `/api/calls` (all tenant-isolated)
- `/api/test-mode/chat` (text + simulated voice)
- `/api/voice/{stt,tts}` (STT via faster-whisper, TTS via edge-tts)
- `/api/phone/status`, `/api/phone/call`, `/api/phone/webhook/*`
- `/api/dialer/launch`, `/{id}/pause`, `/{id}/resume`, `/{id}`,
  `/campaign/{campaign_id}` (auto-dialer sessions with BackgroundTasks)
- `/api/admin/{users,stats}`, `PUT /api/admin/users/{id}/toggle-admin`
  (requires `is_admin=true`)
- `/api/analytics/{overview,campaign/{id}}` (tenant-scoped)

## Implemented (Feb 2026)
- [x] JWT auth + company_name + `is_admin` flag
- [x] Campaign/Lead/Call CRUD with tenant isolation (all queries filter
      through user's own campaigns)
- [x] AI Orchestrator with generic prompt (no industry hardcoded); locks
      detected language; stops on "not interested" / "busy" / silence
- [x] Test Mode (text + voice-first) with corrected outcome logic
      (turn≥5 → interested+qualified)
- [x] Voice providers: FasterWhisperSTT, EdgeTTSProvider, OpenAIWhisperSTT,
      ElevenLabsTTS (pluggable via env)
- [x] Telephony: TwilioProvider with status probe; graceful disabled state
- [x] Phone call routes: outbound + TwiML webhooks (answer/gather/status)
      with lead status auto-mapping on call completion
- [x] Auto-dialer: BackgroundTasks chain, pause/resume/ownership checks,
      delay between calls; chained via status webhook
- [x] MongoDB indexes created on startup (campaigns.user_id,
      leads.campaign_id+status, calls.campaign_id+status, calls.twilio_call_sid
      sparse, conversation_states.call_id unique, dialer_sessions.campaign_id+status)
- [x] Admin panel: platform-wide stats + user list + toggle admin
- [x] Frontend: CampaignDetail, Settings, AdminPanel, updated CallsList
      (Live + Source + 15s auto-refresh), conditional Admin nav link
- [x] Docker + docker-compose + nginx + .env.example
- [x] Regression test suite at `/app/backend/tests/backend_test.py`

## Verified (iteration_2.json — 13/13 backend + frontend pass)
All 18 behaviors listed by user are working in preview environment.

## Backlog
- **P1**: Webhook support for external CRM integrations (e.g., HubSpot,
  Salesforce lead sync)
- **P1**: Audio streaming via `<Stream>` TwiML for true real-time AI voice
  (vs current `<Gather speech>` request/response)
- **P2**: Self-serve Twilio onboarding wizard inside Settings
- **P2**: Per-campaign call scheduling (time-of-day, timezone aware)
- **P2**: Call recording + transcript download
- **P2**: Lead CSV export + filtering
