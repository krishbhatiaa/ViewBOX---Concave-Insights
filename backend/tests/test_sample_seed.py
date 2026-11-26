from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Completion, Member, Referral, Source
from app.seed import import_sample_respondents, sample_csv_path


def test_bundled_sample_csv_is_used_as_seed_data():
    assert sample_csv_path() is not None

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    summary = import_sample_respondents(db)

    assert summary["total_rows"] == 189
    assert summary["imported"] >= 160
    assert summary["skipped"] >= 20
    assert db.query(Member).count() == summary["imported"]
    assert db.query(Source).filter_by(name="WhatsApp Group - Mumbai").first() is not None
    assert db.query(Completion).filter(Completion.survey_id.is_(None)).count() > 0
    assert db.query(Referral).filter(Referral.referrer_id.isnot(None)).count() > 0
    assert db.query(Member).filter(Member.interests.like("%,%")).count() > 0
    assert db.query(Member).filter_by(income_range="10L+").count() > 0
    assert db.query(Member).filter_by(gender="Female").count() > 0
