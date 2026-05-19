"""Seed the database with a demo workspace, admin user, and sample documents.

Run via:
    docker compose exec backend python -m scripts.seed_data

Outputs the admin credentials and a bearer token to stdout — useful for
exercising the API from curl or the frontend without setting up OAuth.
"""

import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, hash_password
from app.domain.models import Document, DocumentStatus, User, UserRole, Workspace
from app.repositories.chunks import ChunkRepository
from app.services.embeddings import build_embedding_provider
from app.services.ingestion import IngestionService

DOCUMENTS: list[dict] = [
    {
        "filename": "Aurora_Q1_2025_Review.txt",
        "storage_key": "local://seed-aurora-q1",
        "content": """\
Q1 2025 Performance Review — Aurora Project

Executive summary. Aurora opened the year with solid momentum. Total bookings
reached $11.4M, a 19% increase versus Q1 2024. The quarter was characterised
by strong new logo acquisition, with 38 new enterprise customers signed —
the highest quarterly count in company history. Net revenue retention came
in at 114%, slightly below our 116% target, as a small cohort of SMB
customers churned during January renewals.

Segment performance. Financial services led with $4.2M in bookings (+33% YoY),
buoyed by two landmark deals in the insurance sub-vertical. Healthcare
contributed $2.6M (+18% YoY). Public sector posted a modest recovery to
$1.1M after the Q4 2024 budget freeze began to lift in late February.

Product highlights. The Aurora Insights dashboard reached general availability
in February, with 62% of active enterprise accounts enabling it within the
first four weeks. Early data shows a 9-point NPS improvement for accounts
using the dashboard versus those on the legacy reporting UI.

Headwinds. Gross margin contracted 1.8 pp to 71.2%, driven by higher cloud
infrastructure costs associated with the new embedding pipeline. We have a
cost-reduction initiative underway targeting 200 bps of improvement by Q3.

Outlook. Full-year guidance remains $54–56M. We are monitoring macro
conditions in EMEA closely; our Q2 pipeline coverage there is 2.1x,
slightly below our 2.5x internal target.
""",
    },
    {
        "filename": "Aurora_Q2_2025_Review.txt",
        "storage_key": "local://seed-aurora-q2",
        "content": """\
Q2 2025 Performance Review — Aurora Project

Executive summary. Q2 2025 represented a step-change in Aurora's scale.
Total bookings of $13.1M exceeded the high end of our internal forecast by
$0.4M, a 23% increase year over year. Notably, expansion ARR surpassed new
logo ARR for the first time, signalling the maturing of our land-and-expand
motion. Net revenue retention improved to 116%, recovering from the Q1 dip.

Segment performance. Financial services reached $5.1M (+38% YoY), with
the insurance vertical contributing $1.9M of that total. Healthcare grew
20% to $2.8M. Public sector accelerated sharply to $1.7M as government
budget cycles reopened; we expect this trend to moderate in H2. The newly
formed manufacturing vertical closed its first three deals totalling $0.3M.

Go-to-market. Average contract value grew 14% QoQ to $187K, reflecting the
move upmarket and the attach rate of professional services. Sales cycle
length stabilised at 51 days after the lengthening observed in Q1. We ended
the quarter with 214 enterprise customers, up from 176 at the end of Q1.

Headwinds. Churn in the SMB segment persisted, with 11 accounts lost to
pricing pressure from a low-cost competitor. We have paused new SMB
acquisition and are focusing retention resources on at-risk accounts.

Outlook. We are cautiously raising our full-year guidance to $56–58M. The
board approved headcount additions of 22 in sales and 8 in customer success
to support the Q3 and Q4 pipeline. Infrastructure cost improvements are on
track; gross margin recovered to 72.4% in June.
""",
    },
    {
        "filename": "Aurora_Q3_2025_Review.txt",
        "storage_key": "local://seed-aurora-q3",
        "content": """\
Q3 2025 Performance Review — Aurora Project

Executive summary. Aurora delivered strong Q3 results across every revenue
line. Total bookings reached $14.2M, a 27% increase versus Q3 2024. Net
revenue retention held at 118%, driven primarily by expansion in the
financial services vertical and a successful upsell motion in healthcare.

Segment performance. The financial services segment grew 41% year over
year, contributing $5.8M to total bookings. Healthcare expanded 22% to
$3.1M, with the new compliance module accounting for $1.4M of new ARR.
Public sector contracted 8% as anticipated, reflecting the budget freeze
we flagged in our Q2 letter.

Headwinds. Two material headwinds shaped the quarter. First, the strong
dollar reduced reported European bookings by an estimated $0.6M. Second,
sales cycles in mid-market enterprise lengthened from 47 to 63 days,
which we attribute to tightening procurement reviews rather than competitive
losses; win rates against the named competitor set actually improved 4
percentage points.

Outlook. We are raising our full-year revenue guidance to $58–60M (from
$54–56M), with continued conservatism on Q4 European bookings. The board
approved a $4M increase to the FY26 hiring plan, weighted toward enterprise
account executives and machine learning engineers supporting the new
agent platform.
""",
    },
]


async def ingest_document(
    db: object,
    workspace_id: object,
    user_id: object,
    doc_meta: dict,
    ingestion: "IngestionService",
) -> None:
    from app.core.database import AsyncSessionLocal  # noqa: F401 — type narrowing

    existing = await db.execute(  # type: ignore[union-attr]
        select(Document).where(
            Document.workspace_id == workspace_id,
            Document.filename == doc_meta["filename"],
        )
    )
    if existing.scalar_one_or_none():
        print(f"  ✓ Already ingested: {doc_meta['filename']}")
        return

    raw = doc_meta["content"].encode()
    doc = Document(
        workspace_id=workspace_id,
        uploaded_by=user_id,
        filename=doc_meta["filename"],
        content_type="text/plain",
        size_bytes=len(raw),
        storage_key=doc_meta["storage_key"],
        status=DocumentStatus.PROCESSING,
    )
    db.add(doc)  # type: ignore[union-attr]
    await db.flush()  # type: ignore[union-attr]

    count = await ingestion.ingest(doc, raw)
    print(f"  ✓ Ingested {doc_meta['filename']} — {count} chunk(s)")


async def main() -> None:
    async with AsyncSessionLocal() as db:
        # ---- Workspace ----
        existing_ws = await db.execute(select(Workspace).where(Workspace.slug == "demo"))
        workspace = existing_ws.scalar_one_or_none()
        if not workspace:
            workspace = Workspace(name="Demo Workspace", slug="demo")
            db.add(workspace)
            await db.flush()
            print(f"✓ Created workspace: {workspace.id}")
        else:
            print(f"✓ Workspace exists: {workspace.id}")

        # ---- Admin user ----
        existing_user = await db.execute(
            select(User).where(User.email == "admin@example.com")
        )
        user = existing_user.scalar_one_or_none()
        if not user:
            user = User(
                workspace_id=workspace.id,
                email="admin@example.com",
                name="Demo Admin",
                role=UserRole.ADMIN,
                password_hash=hash_password("demo-password-1234"),
            )
            db.add(user)
            await db.flush()
            print("✓ Created user: admin@example.com / demo-password-1234")
        else:
            print("✓ User exists: admin@example.com")

        # ---- Documents ----
        print("Ingesting documents:")
        ingestion = IngestionService(
            chunk_repo=ChunkRepository(db),
            embeddings=build_embedding_provider(),
        )
        for doc_meta in DOCUMENTS:
            await ingest_document(db, workspace.id, user.id, doc_meta, ingestion)

        await db.commit()

        # ---- Print a token for convenience ----
        token = create_access_token(subject=str(user.id), workspace_id=str(workspace.id))
        print("\n" + "=" * 60)
        print("Ready! Use this access token in the frontend or curl:")
        print(f"\n{token}\n")
        print("Example curl:")
        print(
            f'  curl -X POST http://localhost:8000/api/v1/chat \\\n'
            f'    -H "Authorization: Bearer {token[:40]}..." \\\n'
            f'    -H "Content-Type: application/json" \\\n'
            f'    -d \'{{"message": "How did Aurora perform across quarters?"}}\''
        )
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
