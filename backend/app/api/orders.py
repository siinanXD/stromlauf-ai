"""Leitstand: Kunden, Auftragsbuch, Bestand und die Durchlauf-Simulation (ohne LLM)."""

import re
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.api.planning import SETTINGS_KEY, _articles, _calc_article, _calc_material, _materials
from app.db import get_session
from app.werk import masterdata
from app.werk.sim import Customer, SimLine, SimOrder, simulate

router = APIRouter(prefix="/api", tags=["orders"])

DEFAULT_CREDIT_LIMIT = 50_000.0  # Richtwert fuer neu angelegte Kunden


class CustomerOut(BaseModel):
    id: str
    name: str
    credit_limit: float


class OrderLineIn(BaseModel):
    article_id: str
    quantity: float = Field(gt=0)
    unit: str = "unit"


class OrderIn(BaseModel):
    customer: str = Field(min_length=1, max_length=200)
    received_at: datetime | None = None
    due_date: date | None = None
    lines: list[OrderLineIn] = Field(min_length=1)


class OrderLineOut(BaseModel):
    article_id: str
    code: str
    name: str
    unit_name: str
    quantity: float
    unit: str


class OrderOut(BaseModel):
    id: str
    number: str
    customer: str | None
    received_at: datetime
    due_date: date | None
    lines: list[OrderLineOut]


class StockOut(BaseModel):
    article_id: str
    code: str
    name: str
    units: int
    pallets: float


class SimulationRequest(BaseModel):
    order_ids: list[str] | None = None  # None = alle Auftraege


def _order_out(order: models.Order) -> OrderOut:
    return OrderOut(
        id=order.id, number=order.number, customer=order.customer.name if order.customer else None,
        received_at=order.received_at, due_date=order.due_date,
        lines=[
            OrderLineOut(article_id=line.article_id, code=line.article.code, name=line.article.name,
                         unit_name=line.article.unit_name, quantity=line.quantity, unit=line.unit)
            for line in order.lines
        ],
    )


def _orders(session: Session) -> list[models.Order]:
    return session.scalars(
        select(models.Order)
        .options(selectinload(models.Order.customer), selectinload(models.Order.lines).selectinload(models.OrderLine.article))
        .order_by(models.Order.received_at, models.Order.number)
    ).all()


def _next_number(session: Session) -> str:
    numbers = [int(m.group(1)) for n in session.scalars(select(models.Order.number)) if (m := re.fullmatch(r"A-(\d+)", n))]
    return f"A-{max(numbers, default=1000) + 1}"


@router.get("/customers", response_model=list[CustomerOut])
def list_customers(session: Session = Depends(get_session)):
    return [CustomerOut(id=c.id, name=c.name, credit_limit=c.credit_limit)
            for c in session.scalars(select(models.Customer).order_by(models.Customer.name))]


@router.get("/orders", response_model=list[OrderOut])
def list_orders(session: Session = Depends(get_session)):
    return [_order_out(o) for o in _orders(session)]


@router.post("/orders", response_model=OrderOut, status_code=201)
def create_order(body: OrderIn, session: Session = Depends(get_session)):
    name = body.customer.strip()
    customer = session.scalar(select(models.Customer).where(models.Customer.name == name))
    if customer is None:
        customer = models.Customer(name=name, credit_limit=DEFAULT_CREDIT_LIMIT)
        session.add(customer)
    for line in body.lines:
        if session.get(models.Article, line.article_id) is None:
            raise HTTPException(400, f"Artikel {line.article_id} nicht gefunden")
        if line.unit not in {"unit", "pallet"}:
            raise HTTPException(400, "Einheit muss unit oder pallet sein")
    received = body.received_at or datetime.now().replace(second=0, microsecond=0)
    order = models.Order(
        number=_next_number(session), customer=customer, received_at=received.replace(tzinfo=None),
        due_date=body.due_date,
        lines=[models.OrderLine(article_id=line.article_id, quantity=line.quantity, unit=line.unit, position=i)
               for i, line in enumerate(body.lines)],
    )
    session.add(order)
    session.commit()
    return _order_out(next(o for o in _orders(session) if o.id == order.id))


@router.delete("/orders/{order_id}", status_code=204)
def delete_order(order_id: str, session: Session = Depends(get_session)):
    order = session.get(models.Order, order_id)
    if order is None:
        raise HTTPException(404, "Auftrag nicht gefunden")
    session.delete(order)
    session.commit()


@router.get("/stock", response_model=list[StockOut])
def list_stock(session: Session = Depends(get_session)):
    rows = session.scalars(select(models.StockItem).options(selectinload(models.StockItem.article))).all()
    return sorted(
        (StockOut(article_id=r.article_id, code=r.article.code, name=r.article.name, units=r.units,
                  pallets=round(r.units / r.article.units_per_pallet, 2)) for r in rows),
        key=lambda s: s.code,
    )


@router.post("/simulation")
def run_simulation(body: SimulationRequest | None = None, session: Session = Depends(get_session)) -> dict:
    setting = session.get(models.PlantSetting, SETTINGS_KEY)
    if setting is None:
        raise HTTPException(409, "Planungsparameter fehlen. Testwerk laden: python scripts/load_testwerk.py")
    articles = {a.id: a for a in _articles(session)}
    calc_articles = {article_id: _calc_article(a) for article_id, a in articles.items()}
    materials = {m.code: _calc_material(m) for m in _materials(session)}
    orders = _orders(session)
    if body and body.order_ids is not None:
        wanted = set(body.order_ids)
        orders = [o for o in orders if o.id in wanted]
    sim_orders = []
    for order in orders:
        customer = (Customer(order.customer.id, order.customer.name, order.customer.credit_limit) if order.customer
                    else Customer("", "ohne Kunde", float("inf")))
        sim_orders.append(SimOrder(
            order.id, order.number, customer, order.received_at, order.due_date,
            [SimLine(calc_articles[line.article_id], line.quantity, line.unit) for line in order.lines],
        ))
    stock = {row.article.code: row.units
             for row in session.scalars(select(models.StockItem).options(selectinload(models.StockItem.article)))}
    prices = {a.code: a.price for a in articles.values()}
    try:
        settings = masterdata.settings_from_json(setting.value)
        workers, hold = masterdata.sim_params(setting.value)
        return simulate(sim_orders, stock, materials, settings, workers, hold, prices)
    except ValueError as err:
        raise HTTPException(400, str(err)) from err
