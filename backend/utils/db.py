from motor.motor_asyncio import AsyncIOMotorClient
from config import settings
import certifi

# tlsCAFile is required on macOS + Python 3.14 to avoid TLSV1_ALERT_INTERNAL_ERROR
# when connecting to MongoDB Atlas SRV cluster.
client = AsyncIOMotorClient(settings.MONGO_URL, tlsCAFile=certifi.where())
db = client[settings.DB_NAME]


def prepare_for_mongo(data: dict) -> dict:
    result = data.copy()
    for key, value in result.items():
        if hasattr(value, 'isoformat'):
            result[key] = value.isoformat()
    return result


async def get_db():
    return db


async def create_indexes():
    await db.campaigns.create_index([("user_id", 1)])
    await db.leads.create_index([("campaign_id", 1), ("status", 1)])
    await db.calls.create_index([("campaign_id", 1), ("status", 1)])
    await db.calls.create_index([("call_sid", 1)], sparse=True)
    await db.calls.create_index([("twilio_call_sid", 1)], sparse=True)
    await db.conversation_states.create_index([("call_id", 1)], unique=True)
    await db.dialer_sessions.create_index([("campaign_id", 1), ("status", 1)])
