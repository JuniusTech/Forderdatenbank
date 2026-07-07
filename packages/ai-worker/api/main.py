"""MVP Demo API — FastAPI."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from ai.draft.generator import generate_draft
from db.config import API_PORT
from db.models import Application, Company, FundingProgram, Match
from db.session import get_session, init_db
from matcher.pipeline import DISCLAIMER, match_company_to_programs

STATIC_DIR = Path(__file__).parent / "static"
SEEDS_DIR = Path(__file__).resolve().parents[3] / "seeds"

app = FastAPI(title="Culinary Funding OS — MVP Demo", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    region: str = Field(min_length=1, max_length=100)
    sector: str | None = None
    employees: int | None = Field(default=None, ge=1, le=100000)
    company_size: str | None = None
    investment_need: str | None = None
    notes: str | None = None


class CompanyOut(CompanyCreate):
    id: uuid.UUID
    created_at: datetime


class ProgramSummary(BaseModel):
    id: uuid.UUID
    title: str
    region: str | None
    funding_type: list[str]
    provider_name: str | None
    application_url: str | None
    last_synced_at: datetime


class ProgramDetail(ProgramSummary):
    source_id: str
    target_groups: list[str]
    eligible_costs: list[str]
    company_sizes: list[str]
    contact: dict | None
    external_links: list
    raw_text: str
    license_attribution: str


class MatchOut(BaseModel):
    id: uuid.UUID
    score: float
    score_breakdown: dict
    matched_terms: list[str]
    estimated_amount_range: str | None
    human_review_required: bool
    disclaimer: str
    program: ProgramSummary


class DraftOut(BaseModel):
    id: uuid.UUID
    state: str
    draft: dict
    created_at: datetime
    program_title: str
    company_name: str


def _program_summary(p: FundingProgram) -> ProgramSummary:
    return ProgramSummary(
        id=p.id,
        title=p.title,
        region=p.region,
        funding_type=p.funding_type or [],
        provider_name=p.provider_name,
        application_url=p.application_url,
        last_synced_at=p.last_synced_at,
    )


def _program_detail(p: FundingProgram) -> ProgramDetail:
    return ProgramDetail(
        **_program_summary(p).model_dump(),
        source_id=p.source_id,
        target_groups=p.target_groups or [],
        eligible_costs=p.eligible_costs or [],
        company_sizes=p.company_sizes or [],
        contact=p.contact,
        external_links=p.external_links or [],
        raw_text=p.raw_text[:4000],
        license_attribution=p.license_attribution,
    )


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict[str, Any]:
    with get_session() as session:
        program_count = session.scalar(select(func.count()).select_from(FundingProgram))
    return {"status": "ok", "programs": program_count}


@app.get("/api/stats")
def stats() -> dict[str, Any]:
    with get_session() as session:
        program_count = session.scalar(select(func.count()).select_from(FundingProgram))
        rows = session.execute(select(FundingProgram.region, FundingProgram.funding_type)).all()
    region_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    for region, types in rows:
        if region:
            region_counts[region] = region_counts.get(region, 0) + 1
        for t in types or []:
            type_counts[t] = type_counts.get(t, 0) + 1
    top_regions = sorted(region_counts.items(), key=lambda x: x[1], reverse=True)[:12]
    top_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:8]
    return {
        "program_count": program_count,
        "top_regions": [{"region": r, "count": c} for r, c in top_regions],
        "top_funding_types": [{"type": t, "count": c} for t, c in top_types],
    }


@app.get("/api/programs", response_model=dict)
def list_programs(
    q: str | None = None,
    region: str | None = None,
    funding_type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    with get_session() as session:
        filters = [FundingProgram.status == "active"]
        if q:
            pattern = f"%{q}%"
            filters.append(
                or_(FundingProgram.title.ilike(pattern), FundingProgram.raw_text.ilike(pattern))
            )
        if region:
            filters.append(FundingProgram.region.ilike(f"%{region}%"))
        if funding_type:
            filters.append(FundingProgram.funding_type.any(funding_type))

        total = session.scalar(select(func.count()).where(*filters))
        rows = list(
            session.scalars(
                select(FundingProgram)
                .where(*filters)
                .order_by(FundingProgram.title)
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        items = [_program_summary(p).model_dump() for p in rows]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@app.get("/api/programs/{program_id}", response_model=ProgramDetail)
def get_program(program_id: uuid.UUID) -> ProgramDetail:
    with get_session() as session:
        program = session.get(FundingProgram, program_id)
        if not program:
            raise HTTPException(404, "Programm nicht gefunden")
        return _program_detail(program)


@app.get("/api/regions")
def list_regions() -> list[str]:
    with get_session() as session:
        rows = session.execute(
            select(FundingProgram.region)
            .where(FundingProgram.region.is_not(None))
            .distinct()
            .order_by(FundingProgram.region)
        ).all()
    return [r[0] for r in rows if r[0]]


@app.get("/api/funding-types")
def list_funding_types() -> list[str]:
    with get_session() as session:
        rows = session.execute(select(FundingProgram.funding_type)).all()
    types: set[str] = set()
    for (funding_types,) in rows:
        for t in funding_types or []:
            if t:
                types.add(t)
    return sorted(types)


@app.get("/api/seeds/demo-company")
def get_demo_seed() -> dict:
    path = SEEDS_DIR / "demo_company.json"
    if not path.is_file():
        raise HTTPException(404, "Seed nicht gefunden")
    return json.loads(path.read_text(encoding="utf-8"))


@app.post("/api/seeds/demo-company", response_model=CompanyOut)
def create_demo_company() -> CompanyOut:
    seed = get_demo_seed()
    body = CompanyCreate(
        name=seed["name"],
        region=seed["region"],
        sector=seed.get("sector"),
        employees=seed.get("employees"),
        company_size=seed.get("company_size"),
        investment_need=seed.get("investment_need"),
        notes=seed.get("notes"),
    )
    return create_company(body)


@app.post("/api/companies", response_model=CompanyOut)
def create_company(body: CompanyCreate) -> CompanyOut:
    with get_session() as session:
        company = Company(**body.model_dump())
        session.add(company)
        session.flush()
        session.refresh(company)
        return CompanyOut(
            id=company.id,
            created_at=company.created_at,
            **body.model_dump(),
        )


@app.get("/api/companies/{company_id}", response_model=CompanyOut)
def get_company(company_id: uuid.UUID) -> CompanyOut:
    with get_session() as session:
        company = session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Unternehmen nicht gefunden")
        return CompanyOut(
            id=company.id,
            created_at=company.created_at,
            name=company.name,
            region=company.region,
            sector=company.sector,
            employees=company.employees,
            company_size=company.company_size,
            investment_need=company.investment_need,
            notes=company.notes,
        )


@app.post("/api/companies/{company_id}/match", response_model=list[MatchOut])
def run_match(company_id: uuid.UUID, min_score: float = Query(35, ge=0, le=100)) -> list[MatchOut]:
    with get_session() as session:
        company = session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Unternehmen nicht gefunden")

        programs = list(
            session.scalars(select(FundingProgram).where(FundingProgram.status == "active")).all()
        )
        results = match_company_to_programs(company, programs, min_score=min_score, limit=8)

        session.execute(Match.__table__.delete().where(Match.company_id == company_id))
        out: list[MatchOut] = []
        for result in results:
            match = Match(
                company_id=company.id,
                program_id=result.program.id,
                score=result.score,
                score_breakdown=result.breakdown,
                matched_terms=result.matched_terms,
                estimated_amount_range=result.estimated_amount_range,
                human_review_required=True,
                disclaimer=DISCLAIMER,
            )
            session.add(match)
            session.flush()
            out.append(_match_out(match, result.program))
        return out


def _match_out(m: Match, p: FundingProgram) -> MatchOut:
    return MatchOut(
        id=m.id,
        score=float(m.score),
        score_breakdown=m.score_breakdown,
        matched_terms=m.matched_terms or [],
        estimated_amount_range=m.estimated_amount_range,
        human_review_required=m.human_review_required,
        disclaimer=m.disclaimer,
        program=_program_summary(p),
    )


@app.get("/api/companies/{company_id}/matches", response_model=list[MatchOut])
def list_matches(company_id: uuid.UUID) -> list[MatchOut]:
    with get_session() as session:
        company = session.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Unternehmen nicht gefunden")
        rows = session.execute(
            select(Match, FundingProgram)
            .join(FundingProgram, Match.program_id == FundingProgram.id)
            .where(Match.company_id == company_id)
            .order_by(Match.score.desc())
        ).all()
        return [_match_out(m, p) for m, p in rows]


@app.post("/api/matches/{match_id}/draft", response_model=DraftOut)
def create_draft(match_id: uuid.UUID) -> DraftOut:
    with get_session() as session:
        match = session.get(Match, match_id)
        if not match:
            raise HTTPException(404, "Match nicht gefunden")
        company = session.get(Company, match.company_id)
        program = session.get(FundingProgram, match.program_id)
        if not company or not program:
            raise HTTPException(404, "Daten unvollständig")

        draft_data = generate_draft(company, program, match)
        app_row = Application(
            company_id=company.id,
            program_id=program.id,
            match_id=match.id,
            state="draft_ready",
            draft=draft_data,
        )
        session.add(app_row)
        session.flush()
        session.refresh(app_row)
        return DraftOut(
            id=app_row.id,
            state=app_row.state,
            draft=app_row.draft,
            created_at=app_row.created_at,
            program_title=program.title,
            company_name=company.name,
        )


@app.get("/api/matches/{match_id}/draft/stream")
def stream_draft(match_id: uuid.UUID) -> StreamingResponse:
    """SSE — taslak metnini parça parça gönder (demo etkisi)."""

    def generate():
        with get_session() as session:
            match = session.get(Match, match_id)
            if not match:
                yield "data: {\"error\": \"not found\"}\n\n"
                return
            company = session.get(Company, match.company_id)
            program = session.get(FundingProgram, match.program_id)
            if not company or not program:
                yield "data: {\"error\": \"incomplete\"}\n\n"
                return
            draft_data = generate_draft(company, program, match)
            text = draft_data.get("application_text_de", "")
            chunk_size = 40
            for i in range(0, len(text), chunk_size):
                chunk = text[i : i + chunk_size]
                payload = json.dumps({"chunk": chunk, "done": False}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
            final = json.dumps(
                {"chunk": "", "done": True, "draft": draft_data},
                ensure_ascii=False,
            )
            yield f"data: {final}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def main() -> None:
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=API_PORT, reload=True)


if __name__ == "__main__":
    main()
