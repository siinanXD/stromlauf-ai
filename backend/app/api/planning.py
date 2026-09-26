"""Vorkalkulation: Stammdaten lesen/ersetzen und Auftraege durchrechnen (ohne LLM)."""

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.db import get_session
from app.werk import calc, masterdata

router = APIRouter(prefix="/api", tags=["planning"])

SETTINGS_KEY = "calc"


class BomOut(BaseModel):
    material_code: str
    material_name: str
    unit: str
    qty: float
    per: str


class RoutingOut(BaseModel):
    seq: int
    machine_id: str
    machine_name: str
    machine_line: str
    rate: float
    rate_unit: str
    setup_min: float
    coupled: bool
    basis: str
    hourly_rate: float | None


class ArticleOut(BaseModel):
    id: str
    code: str
    name: str
    unit_name: str
    units_per_pallet: int
    sheets_per_unit: int
    sheet_w_mm: float
    sheet_l_mm: float
    plies: int
    gsm: float
    waste_pct: float
    line: str
    description: str
    paper_kg_per_unit: float
    routing: list[RoutingOut]
    bom: list[BomOut]


class MaterialOut(BaseModel):
    id: str
    code: str
    name: str
    unit: str
    price: float | None
    price_source: str
    made_on: str | None
    made_rate_per_h: float | None
    made_basis: str
    bom: list[BomOut]


class BomIn(BaseModel):
    material: str
    qty: float = Field(ge=0)
    per: str = "unit"


class RoutingIn(BaseModel):
    machine_id: str
    rate: float = Field(gt=0)
    rate_unit: str = "unit_min"
    setup_min: float = Field(default=0, ge=0)
    coupled: bool = True
    basis: str = ""


class MaterialIn(BaseModel):
    code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=200)
    unit: str = Field(min_length=1, max_length=20)
    price: float | None = Field(default=None, ge=0)
    price_source: str = ""
    made_on_machine_id: str | None = None
    made_rate_per_h: float | None = Field(default=None, gt=0)
    made_basis: str = ""
    bom: list[BomIn] = []


class ArticleIn(BaseModel):
    code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=200)
    unit_name: str = Field(default="Paket", max_length=40)
    units_per_pallet: int = Field(gt=0)
    sheets_per_unit: int = Field(gt=0)
    sheet_w_mm: float = Field(gt=0)
    sheet_l_mm: float = Field(gt=0)
    plies: int = Field(gt=0)
    gsm: float = Field(gt=0)
    waste_pct: float = Field(default=3, ge=0)
    line: str = Field(default="", max_length=120)
    description: str = ""
    routing: list[RoutingIn] = []
    bom: list[BomIn] = []


class MasterDataIn(BaseModel):
    materials: list[MaterialIn] = []
    articles: list[ArticleIn] = []
    settings: dict[str, dict] = {}


class CalcPosition(BaseModel):
    article_id: str
    quantity: float
    unit: str = "unit"


class CalcRequest(BaseModel):
    received_at: datetime | None = None
    due_date: date | None = None
    positions: list[CalcPosition]


# --- ORM -> Rechenkern ----------------------------------------------------------------------------


def _hourly(machine: models.Machine) -> float | None:
    return masterdata.hourly_rate([{"label": s.label, "value": s.value} for s in machine.specs])


def _bom_out(line: models.BomLine) -> BomOut:
    return BomOut(
        material_code=line.material.code, material_name=line.material.name, unit=line.material.unit,
        qty=line.qty, per=line.per,
    )


def _calc_article(article: models.Article) -> calc.Article:
    return calc.Article(
        article.id, article.code, article.name, article.unit_name, article.units_per_pallet,
        article.sheets_per_unit, article.sheet_w_mm, article.sheet_l_mm, article.plies, article.gsm,
        article.waste_pct, article.line,
        [
            calc.Step(
                s.machine_id, s.machine.name, s.machine.line, s.rate, s.rate_unit, s.setup_min, s.coupled,
                _hourly(s.machine), s.basis,
            )
            for s in article.routing
        ],
        [calc.BomLine(line.material.code, line.qty, line.per) for line in article.bom],
    )


def _calc_material(material: models.Material) -> calc.Material:
    maker = None
    if material.made_on is not None and material.made_rate_per_h:
        maker = calc.Maker(
            material.made_on.id, material.made_on.name, material.made_rate_per_h, _hourly(material.made_on)
        )
    return calc.Material(
        material.code, material.name, material.unit, material.price, material.price_source, maker,
        [calc.BomLine(line.material.code, line.qty) for line in material.bom],
    )


def _articles(session: Session) -> list[models.Article]:
    return session.scalars(
        select(models.Article)
        .options(
            selectinload(models.Article.routing)
            .selectinload(models.RoutingStep.machine)
            .selectinload(models.Machine.specs),
            selectinload(models.Article.bom).selectinload(models.BomLine.material),
        )
        .order_by(models.Article.line, models.Article.code)
    ).all()


def _materials(session: Session) -> list[models.Material]:
    return session.scalars(
        select(models.Material)
        .options(
            selectinload(models.Material.bom).selectinload(models.BomLine.material),
            selectinload(models.Material.made_on).selectinload(models.Machine.specs),
        )
        .order_by(models.Material.code)
    ).all()


# --- Endpunkte ------------------------------------------------------------------------------------


@router.get("/articles", response_model=list[ArticleOut])
def list_articles(session: Session = Depends(get_session)):
    result = []
    for article in _articles(session):
        base = _calc_article(article)
        result.append(ArticleOut(
            id=article.id, code=article.code, name=article.name, unit_name=article.unit_name,
            units_per_pallet=article.units_per_pallet, sheets_per_unit=article.sheets_per_unit,
            sheet_w_mm=article.sheet_w_mm, sheet_l_mm=article.sheet_l_mm, plies=article.plies,
            gsm=article.gsm, waste_pct=article.waste_pct, line=article.line, description=article.description,
            paper_kg_per_unit=calc.paper_kg_per_unit(base),
            routing=[
                RoutingOut(
                    seq=s.seq, machine_id=s.machine_id, machine_name=s.machine.name, machine_line=s.machine.line,
                    rate=s.rate, rate_unit=s.rate_unit, setup_min=s.setup_min, coupled=s.coupled, basis=s.basis,
                    hourly_rate=_hourly(s.machine),
                )
                for s in article.routing
            ],
            bom=[_bom_out(line) for line in article.bom],
        ))
    return result


@router.get("/materials", response_model=list[MaterialOut])
def list_materials(session: Session = Depends(get_session)):
    return [
        MaterialOut(
            id=m.id, code=m.code, name=m.name, unit=m.unit, price=m.price, price_source=m.price_source,
            made_on=m.made_on.name if m.made_on else None, made_rate_per_h=m.made_rate_per_h,
            made_basis=m.made_basis, bom=[_bom_out(line) for line in m.bom],
        )
        for m in _materials(session)
    ]


@router.get("/plant-settings")
def plant_settings(session: Session = Depends(get_session)) -> dict[str, dict]:
    return {s.key: s.value for s in session.scalars(select(models.PlantSetting))}


@router.put("/master-data")
def replace_master_data(body: MasterDataIn, session: Session = Depends(get_session)) -> dict:
    """Stammdaten mit gleichem Code ersetzen (andere bleiben); Parameter je Schluessel ueberschreiben."""
    for key, value in body.settings.items():
        if key == SETTINGS_KEY:
            try:
                masterdata.settings_from_json(value)
            except (KeyError, TypeError, ValueError) as err:
                raise HTTPException(400, f"Parameter 'calc' unvollstaendig: {err}") from err
    machine_ids = set(session.scalars(select(models.Machine.id)).all())
    codes = {m.code for m in body.materials}
    for article in session.scalars(select(models.Article).where(models.Article.code.in_([a.code for a in body.articles]))):
        session.delete(article)
    for material in session.scalars(select(models.Material).where(models.Material.code.in_(codes))):
        session.delete(material)
    session.flush()

    by_code = {m.code: m for m in session.scalars(select(models.Material))}
    for item in body.materials:
        if item.made_on_machine_id and item.made_on_machine_id not in machine_ids:
            raise HTTPException(400, f"Material {item.code}: Maschine nicht gefunden")
        material = models.Material(**item.model_dump(exclude={"bom"}))
        session.add(material)
        by_code[item.code] = material
    session.flush()

    def lines(items: list[BomIn], owner: str) -> list[models.BomLine]:
        result = []
        for index, line in enumerate(items):
            if line.material not in by_code:
                raise HTTPException(400, f"{owner}: Material {line.material} unbekannt")
            if line.per not in {"unit", "pallet"}:
                raise HTTPException(400, f"{owner}: 'per' muss unit oder pallet sein")
            result.append(models.BomLine(material_id=by_code[line.material].id, qty=line.qty, per=line.per, position=index))
        return result

    for item in body.materials:
        by_code[item.code].bom = lines(item.bom, f"Material {item.code}")
    for item in body.articles:
        for step in item.routing:
            if step.machine_id not in machine_ids:
                raise HTTPException(400, f"Artikel {item.code}: Maschine {step.machine_id} nicht gefunden")
            if step.rate_unit not in {"unit_min", "pallet_h"}:
                raise HTTPException(400, f"Artikel {item.code}: rate_unit muss unit_min oder pallet_h sein")
        article = models.Article(**item.model_dump(exclude={"routing", "bom"}))
        article.routing = [models.RoutingStep(seq=i, **step.model_dump()) for i, step in enumerate(item.routing)]
        article.bom = lines(item.bom, f"Artikel {item.code}")
        session.add(article)
    for key, value in body.settings.items():
        session.merge(models.PlantSetting(key=key, value=value))
    session.commit()
    return {"materials": len(body.materials), "articles": len(body.articles), "settings": sorted(body.settings)}


@router.post("/calc")
def calculate_order(body: CalcRequest, session: Session = Depends(get_session)) -> dict:
    setting = session.get(models.PlantSetting, SETTINGS_KEY)
    if setting is None:
        raise HTTPException(409, "Planungsparameter fehlen. Testwerk laden: python scripts/load_testwerk.py")
    if not body.positions:
        raise HTTPException(400, "Auftrag ohne Positionen")
    articles = {a.id: a for a in _articles(session)}
    materials = {m.code: _calc_material(m) for m in _materials(session)}
    positions = []
    for position in body.positions:
        article = articles.get(position.article_id)
        if article is None:
            raise HTTPException(400, f"Artikel {position.article_id} nicht gefunden")
        positions.append(calc.Position(_calc_article(article), position.quantity, position.unit))
    received = body.received_at or datetime.now().replace(second=0, microsecond=0)
    if received.tzinfo is not None:
        received = received.astimezone().replace(tzinfo=None)
    try:
        return calc.calculate(received, body.due_date, positions, materials, masterdata.settings_from_json(setting.value))
    except ValueError as err:
        raise HTTPException(400, str(err)) from err
