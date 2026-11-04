import json
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.models.db_models import AuditLogEntry, VendorMemoryRecord

def record_audit_log(
    db: Session,
    event_type: str,
    source: str,
    description: str,
    severity: str = "INFO",
    reconciliation_id: Optional[int] = None
) -> AuditLogEntry:
    """Creates an immutable audit log record for end-to-end traceability."""
    log_entry = AuditLogEntry(
        reconciliation_id=reconciliation_id,
        event_type=event_type,
        source=source,
        description=description,
        severity=severity,
        timestamp=datetime.utcnow()
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry


def update_vendor_memory(
    db: Session,
    vendor_name: str,
    was_matched: bool
):
    """Tracks vendor transaction metrics and historical reconciliation performance."""
    if not vendor_name:
        return

    record = db.query(VendorMemoryRecord).filter(
        VendorMemoryRecord.canonical_name.ilike(vendor_name.strip())
    ).first()

    if not record:
        aliases = [vendor_name.strip()]
        record = VendorMemoryRecord(
            canonical_name=vendor_name.strip(),
            aliases_json=json.dumps(aliases),
            total_reconciliations=1,
            successful_matches=1 if was_matched else 0,
            notes="Auto-registered by CacheFlow agent"
        )
        db.add(record)
    else:
        record.total_reconciliations += 1
        if was_matched:
            record.successful_matches += 1
    
    db.commit()
