from datetime import datetime
from malibbene.schema.branch import Branch
from malibbene.schema.audit import AuditRecord, AuditStatus

def test_branch_minimum():
    b = Branch(id="bpl-brighton", library_id="bpl", name="Brighton Branch")
    assert b.library_id == "bpl"
    assert b.hours is None

def test_audit_status_enum():
    assert {e.value for e in AuditStatus} == {"verified_ok", "corrected", "noted"}

def test_audit_record_fields():
    r = AuditRecord(
        target="library:wakefield:card_eligibility",
        status=AuditStatus.CORRECTED,
        corrected_value="ma_resident",
        note="re-checked policy page 2026-05-20",
        audited_at=datetime(2026,5,20,12,0,0),
        audited_by="rbtsama",
    )
    assert r.status == AuditStatus.CORRECTED
    assert r.corrected_value == "ma_resident"
