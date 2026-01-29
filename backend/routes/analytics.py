from fastapi import APIRouter, HTTPException, Depends, status
from utils.security import get_current_user
from utils.db import db
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/campaign/{campaign_id}")
async def get_campaign_analytics(campaign_id: str, user_id: str = Depends(get_current_user)):
    """Get analytics for a specific campaign"""
    try:
        # Verify campaign belongs to user
        campaign = await db.campaigns.find_one(
            {"id": campaign_id, "user_id": user_id},
            {"_id": 0}
        )
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
        
        # Get leads
        leads = await db.leads.find(
            {"campaign_id": campaign_id},
            {"_id": 0}
        ).to_list(10000)
        
        # Get calls
        calls = await db.calls.find(
            {"campaign_id": campaign_id},
            {"_id": 0}
        ).to_list(10000)
        
        # Get call outcomes
        call_ids = [call["id"] for call in calls]
        outcomes = await db.call_outcomes.find(
            {"call_id": {"$in": call_ids}},
            {"_id": 0}
        ).to_list(10000)
        
        # Calculate metrics
        total_leads = len(leads)
        total_calls = len(calls)
        completed_calls = len([c for c in calls if c["status"] == "completed"])
        
        # Lead status breakdown
        lead_status_counts = {}
        for lead in leads:
            status = lead.get("status", "pending")
            lead_status_counts[status] = lead_status_counts.get(status, 0) + 1
        
        # Call outcomes breakdown
        outcome_counts = {}
        qualified_count = 0
        for outcome in outcomes:
            outcome_type = outcome.get("outcome", "unknown")
            outcome_counts[outcome_type] = outcome_counts.get(outcome_type, 0) + 1
            if outcome.get("is_qualified"):
                qualified_count += 1
        
        # Calculate average call duration
        completed_call_durations = [c.get("duration", 0) for c in calls if c["status"] == "completed" and c.get("duration")]
        avg_duration = sum(completed_call_durations) / len(completed_call_durations) if completed_call_durations else 0
        
        # Contact rate
        contact_rate = (completed_calls / total_leads * 100) if total_leads > 0 else 0
        
        # Qualification rate
        qualification_rate = (qualified_count / completed_calls * 100) if completed_calls > 0 else 0
        
        return {
            "campaign": campaign,
            "metrics": {
                "total_leads": total_leads,
                "total_calls": total_calls,
                "completed_calls": completed_calls,
                "contact_rate": round(contact_rate, 2),
                "qualification_rate": round(qualification_rate, 2),
                "avg_call_duration": round(avg_duration, 2),
                "qualified_leads": qualified_count
            },
            "lead_status_breakdown": lead_status_counts,
            "outcome_breakdown": outcome_counts
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analytics error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch analytics"
        )

@router.get("/overview")
async def get_overview_analytics(user_id: str = Depends(get_current_user)):
    """Get overview analytics across all campaigns"""
    try:
        # Get all campaigns for user
        campaigns = await db.campaigns.find(
            {"user_id": user_id},
            {"_id": 0}
        ).to_list(1000)
        
        campaign_ids = [c["id"] for c in campaigns]
        
        # Get all leads
        leads = await db.leads.find(
            {"campaign_id": {"$in": campaign_ids}},
            {"_id": 0}
        ).to_list(10000)
        
        # Get all calls
        calls = await db.calls.find(
            {"campaign_id": {"$in": campaign_ids}},
            {"_id": 0}
        ).to_list(10000)
        
        # Get all outcomes
        call_ids = [call["id"] for call in calls]
        outcomes = await db.call_outcomes.find(
            {"call_id": {"$in": call_ids}},
            {"_id": 0}
        ).to_list(10000)
        
        # Calculate metrics
        total_campaigns = len(campaigns)
        total_leads = len(leads)
        total_calls = len(calls)
        completed_calls = len([c for c in calls if c["status"] == "completed"])
        qualified_count = len([o for o in outcomes if o.get("is_qualified")])
        
        # Per campaign metrics
        campaign_metrics = []
        for campaign in campaigns:
            camp_leads = [l for l in leads if l["campaign_id"] == campaign["id"]]
            camp_calls = [c for c in calls if c["campaign_id"] == campaign["id"]]
            camp_completed = len([c for c in camp_calls if c["status"] == "completed"])
            
            campaign_metrics.append({
                "campaign_id": campaign["id"],
                "campaign_name": campaign["name"],
                "leads": len(camp_leads),
                "calls": len(camp_calls),
                "completed_calls": camp_completed,
                "contact_rate": round((camp_completed / len(camp_leads) * 100) if camp_leads else 0, 2)
            })
        
        return {
            "overview": {
                "total_campaigns": total_campaigns,
                "total_leads": total_leads,
                "total_calls": total_calls,
                "completed_calls": completed_calls,
                "qualified_leads": qualified_count,
                "overall_contact_rate": round((completed_calls / total_leads * 100) if total_leads > 0 else 0, 2),
                "overall_qualification_rate": round((qualified_count / completed_calls * 100) if completed_calls > 0 else 0, 2)
            },
            "campaign_metrics": campaign_metrics
        }
        
    except Exception as e:
        logger.error(f"Overview analytics error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch overview analytics"
        )
