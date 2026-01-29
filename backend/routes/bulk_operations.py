from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File
from utils.security import get_current_user
from utils.db import db, prepare_for_mongo
from models.lead import Lead
from typing import List
import logging
import csv
import io

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/leads", tags=["Leads - Bulk Operations"])

@router.post("/bulk-import")
async def bulk_import_leads(
    campaign_id: str,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user)
):
    """
    Bulk import leads from CSV file
    
    CSV Format: name,phone
    Example:
    John Doe,+919876543210
    Jane Smith,+919876543211
    """
    try:
        # Verify campaign belongs to user
        campaign = await db.campaigns.find_one(
            {"id": campaign_id, "user_id": user_id}
        )
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
        
        # Read CSV file
        contents = await file.read()
        csv_data = contents.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_data))
        
        # Validate CSV headers
        expected_headers = {'name', 'phone'}
        if not expected_headers.issubset(set(csv_reader.fieldnames or [])):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"CSV must have columns: {', '.join(expected_headers)}"
            )
        
        # Process leads
        imported_leads = []
        skipped_rows = []
        
        for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 (header is row 1)
            try:
                name = row.get('name', '').strip()
                phone = row.get('phone', '').strip()
                
                if not name or not phone:
                    skipped_rows.append({
                        'row': row_num,
                        'reason': 'Missing name or phone'
                    })
                    continue
                
                # Create lead
                lead = Lead(
                    name=name,
                    phone=phone,
                    campaign_id=campaign_id
                )
                
                lead_doc = prepare_for_mongo(lead.model_dump())
                await db.leads.insert_one(lead_doc)
                imported_leads.append(lead)
                
            except Exception as e:
                logger.error(f"Error processing row {row_num}: {str(e)}")
                skipped_rows.append({
                    'row': row_num,
                    'reason': str(e)
                })
        
        return {
            "imported_count": len(imported_leads),
            "skipped_count": len(skipped_rows),
            "skipped_rows": skipped_rows
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk import error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import leads: {str(e)}"
        )
