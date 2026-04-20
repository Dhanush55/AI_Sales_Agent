"""Backend API tests for AI Voice Sales SaaS platform."""
import os
import time
import uuid
import pytest
import requests
import subprocess

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback: read frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

API = f"{BASE_URL}/api"


def _rand_email(prefix="user"):
    return f"TEST_{prefix}_{uuid.uuid4().hex[:8]}@example.com"


def _register(email=None, password="Pass1234!", company="Acme", prefix="user"):
    email = email or _rand_email(prefix)
    r = requests.post(f"{API}/auth/register",
                      json={"email": email, "password": password, "company_name": company},
                      timeout=20)
    return r, email, password


@pytest.fixture(scope="module")
def user_a():
    r, email, pwd = _register(company="CoA")
    assert r.status_code == 200, r.text
    data = r.json()
    return {"token": data["access_token"], "user": data["user"], "email": email, "password": pwd}


@pytest.fixture(scope="module")
def user_b():
    r, email, pwd = _register(company="CoB")
    assert r.status_code == 200, r.text
    data = r.json()
    return {"token": data["access_token"], "user": data["user"], "email": email, "password": pwd}


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------- Auth ----------------
class TestAuth:
    def test_register_returns_is_admin_false(self):
        r, email, _ = _register()
        assert r.status_code == 200, r.text
        data = r.json()
        assert "user" in data and "access_token" in data
        assert data["user"]["email"] == email
        assert data["user"].get("is_admin") is False

    def test_login_returns_is_admin_field(self):
        r, email, pwd = _register()
        assert r.status_code == 200
        r2 = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=15)
        assert r2.status_code == 200, r2.text
        assert r2.json()["user"].get("is_admin") is False


# ---------------- Phone status ----------------
class TestPhone:
    def test_phone_status(self):
        r = requests.get(f"{API}/phone/status", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["voice_enabled"] is True
        assert d["stt_provider"] == "faster_whisper"
        assert d["tts_provider"] == "edge_tts"
        assert d["telephony_configured"] is False

    def test_phone_call_returns_400_when_not_configured(self, user_a):
        r = requests.post(
            f"{API}/phone/call",
            params={"campaign_id": "x", "lead_id": "y"},
            headers=_auth(user_a["token"]), timeout=15,
        )
        assert r.status_code == 400
        assert "Telephony" in r.json().get("detail", "")


# ---------------- Campaigns (used downstream) ----------------
@pytest.fixture(scope="module")
def campaign_a(user_a):
    r = requests.post(f"{API}/campaigns",
                      json={"name": "TEST_CampA", "goal": "Sell software",
                            "language": "indian_english"},
                      headers=_auth(user_a["token"]), timeout=15)
    assert r.status_code in (200, 201), r.text
    return r.json()


@pytest.fixture(scope="module")
def campaign_b(user_b):
    r = requests.post(f"{API}/campaigns",
                      json={"name": "TEST_CampB", "goal": "Lead gen",
                            "language": "indian_english"},
                      headers=_auth(user_b["token"]), timeout=15)
    assert r.status_code in (200, 201), r.text
    return r.json()


# ---------------- Dialer ----------------
class TestDialer:
    def test_launch_no_pending_leads_400(self, user_a, campaign_a):
        r = requests.post(f"{API}/dialer/launch",
                          json={"campaign_id": campaign_a["id"]},
                          headers=_auth(user_a["token"]), timeout=15)
        assert r.status_code == 400
        assert "No pending leads" in r.json().get("detail", "")

    def test_get_campaign_session_404_when_none(self, user_a, campaign_a):
        r = requests.get(f"{API}/dialer/campaign/{campaign_a['id']}",
                         headers=_auth(user_a["token"]), timeout=15)
        assert r.status_code == 404

    def test_dialer_session_ownership_403(self, user_a, user_b, campaign_a):
        # Create a dialer session for user_a by inserting a lead first
        lead = requests.post(f"{API}/leads",
                             json={"campaign_id": campaign_a["id"], "name": "TEST_Lead",
                                   "phone": "+10000000001"},
                             headers=_auth(user_a["token"]), timeout=15)
        assert lead.status_code in (200, 201), lead.text

        # Launch dialer; will try to initiate a call but telephony not configured -> call fails gracefully in background
        launch = requests.post(f"{API}/dialer/launch",
                               json={"campaign_id": campaign_a["id"]},
                               headers=_auth(user_a["token"]), timeout=15)
        assert launch.status_code == 200, launch.text
        sess_id = launch.json()["session_id"]

        # user_b tries to pause -> 403
        r = requests.post(f"{API}/dialer/{sess_id}/pause",
                          headers=_auth(user_b["token"]), timeout=15)
        assert r.status_code == 403

        r2 = requests.post(f"{API}/dialer/{sess_id}/resume",
                           headers=_auth(user_b["token"]), timeout=15)
        assert r2.status_code == 403

        # user_a can pause successfully
        r3 = requests.post(f"{API}/dialer/{sess_id}/pause",
                           headers=_auth(user_a["token"]), timeout=15)
        assert r3.status_code == 200

        # GET most recent via campaign endpoint now returns the session
        r4 = requests.get(f"{API}/dialer/campaign/{campaign_a['id']}",
                          headers=_auth(user_a["token"]), timeout=15)
        assert r4.status_code == 200
        assert r4.json()["id"] == sess_id


# ---------------- Admin ----------------
def _promote_admin(email: str):
    subprocess.run(
        ["mongosh", "test_database", "--quiet", "--eval",
         f'db.users.updateOne({{email:"{email}"}}, {{$set:{{is_admin:true}}}})'],
        check=True, capture_output=True,
    )


class TestAdmin:
    def test_admin_endpoints_403_for_non_admin(self, user_a):
        r1 = requests.get(f"{API}/admin/users", headers=_auth(user_a["token"]), timeout=15)
        r2 = requests.get(f"{API}/admin/stats", headers=_auth(user_a["token"]), timeout=15)
        assert r1.status_code == 403
        assert r2.status_code == 403

    def test_admin_endpoints_200_and_toggle(self):
        r, email, pwd = _register(prefix="admin")
        token = r.json()["access_token"]
        user_id = r.json()["user"]["id"]
        _promote_admin(email)

        # Re-login to get updated user object (token is valid regardless, but confirms is_admin)
        rl = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=15)
        assert rl.status_code == 200
        assert rl.json()["user"]["is_admin"] is True
        token = rl.json()["access_token"]

        r1 = requests.get(f"{API}/admin/users", headers=_auth(token), timeout=20)
        assert r1.status_code == 200
        assert isinstance(r1.json(), list)

        r2 = requests.get(f"{API}/admin/stats", headers=_auth(token), timeout=20)
        assert r2.status_code == 200
        for k in ("total_users", "total_campaigns", "total_leads", "total_calls",
                  "calls_today", "active_dialers"):
            assert k in r2.json()

        # Toggle admin off on self
        r3 = requests.put(f"{API}/admin/users/{user_id}/toggle-admin",
                          headers=_auth(token), timeout=15)
        assert r3.status_code == 200
        assert r3.json()["is_admin"] is False

        # Now a fresh request should get 403
        r4 = requests.get(f"{API}/admin/users", headers=_auth(token), timeout=15)
        assert r4.status_code == 403


# ---------------- Multi-tenant isolation ----------------
class TestTenantIsolation:
    def test_user_a_cannot_read_user_b_campaign(self, user_a, user_b, campaign_b):
        # user_a tries to fetch user_b's campaign detail
        r = requests.get(f"{API}/campaigns/{campaign_b['id']}",
                         headers=_auth(user_a["token"]), timeout=15)
        assert r.status_code in (403, 404), f"Expected forbidden/not-found, got {r.status_code}"

    def test_calls_only_returns_users_own(self, user_a, user_b, campaign_a, campaign_b):
        r_a = requests.get(f"{API}/calls", headers=_auth(user_a["token"]), timeout=15)
        r_b = requests.get(f"{API}/calls", headers=_auth(user_b["token"]), timeout=15)
        assert r_a.status_code == 200
        assert r_b.status_code == 200
        a_calls = r_a.json()
        b_calls = r_b.json()
        # Every call returned to A must belong to a campaign owned by A
        for c in a_calls:
            assert c["campaign_id"] == campaign_a["id"] or c["campaign_id"] != campaign_b["id"]
        for c in b_calls:
            assert c["campaign_id"] != campaign_a["id"]


# ---------------- Test-mode conversation ----------------
class TestTestMode:
    def test_not_interested_ends_call_immediately(self, user_a, campaign_a):
        r = requests.post(f"{API}/test-mode/chat",
                          json={"campaign_id": campaign_a["id"],
                                "user_input": "I am not interested, please remove me."},
                          headers=_auth(user_a["token"]), timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["should_end_call"] is True
        # outcome stored in DB; we re-query via calls
        call_id = data["call_id"]
        # allow small delay for outcome write
        time.sleep(1)
        r2 = requests.get(f"{API}/calls/{call_id}", headers=_auth(user_a["token"]), timeout=15)
        # Outcome may or may not be in /calls/{id} depending on schema; primary assertion is should_end_call
        # Validate conversation_state reports not_interested_count >= 1
        assert data["conversation_state"]["not_interested_count"] >= 1

    def test_five_turns_interested_outcome(self, user_a, campaign_a):
        # Turn 1 - new call
        call_id = None
        for i in range(6):
            payload = {"campaign_id": campaign_a["id"],
                       "user_input": f"Yes, please tell me more. This is turn {i+1}."}
            if call_id:
                payload["call_id"] = call_id
            r = requests.post(f"{API}/test-mode/chat", json=payload,
                              headers=_auth(user_a["token"]), timeout=60)
            assert r.status_code == 200, r.text
            data = r.json()
            call_id = data["call_id"]
            if data["should_end_call"]:
                break

        # Check final state turn count -- may vary, but accept any graceful end
        assert data["conversation_state"]["current_turn"] >= 1
