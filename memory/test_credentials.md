# Test Credentials

## Standard test flow
Create a new user dynamically via POST `/api/auth/register` with any email/password/company_name.
Example:
```
POST /api/auth/register
{"email":"test@example.com","password":"Pass1234","company_name":"Acme Co"}
```

## Admin access
There is no pre-seeded admin. To test admin features:
1. Register a user (e.g., `admin@test.com` / `AdminPass1`).
2. Flip `is_admin: true` directly in Mongo:
   ```
   mongosh test_database --eval "db.users.updateOne({email:'admin@test.com'}, {\$set: {is_admin: true}})"
   ```
3. Re-login (or refresh) to get the updated token/user object.

## Telephony
`telephony_configured` is intentionally `false` in this environment (blank Twilio
keys in `/app/backend/.env`). All `/api/phone/call` and `/api/dialer/launch` calls
should return a graceful error when telephony is disabled.
