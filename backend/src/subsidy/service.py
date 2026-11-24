from fastapi import HTTPException
from sqlalchemy import select

from ..models import now_utc
from ..services.workflow import audit
from .models import SubsidyPool, SubsidyReservation

POOL_CODE = 'weekend'


def get_pool(db, *, lock=False):
    statement = select(SubsidyPool).where(SubsidyPool.code == POOL_CODE)
    if lock:
        statement = statement.with_for_update()
    return db.scalar(statement)


def pool_json(pool):
    if pool is None:
        return {'configured': False}
    return {
        'configured': True,
        'code': pool.code,
        'total_cents': pool.total_cents,
        'per_seat_cents': pool.per_seat_cents,
        'reserved_cents': pool.reserved_cents,
        'charged_cents': pool.charged_cents,
        'remaining_cents': pool.total_cents - pool.reserved_cents - pool.charged_cents,
        'updated_at': pool.updated_at,
    }


def reservation_json(row):
    return {
        'state': row.state,
        'per_seat_cents': row.per_seat_cents,
        'reserved_cents': row.reserved_cents,
        'charged_cents': row.charged_cents,
    }


def configure(db, payload, actor):
    total_cents = int(payload.total * 100)
    per_seat_cents = int(payload.per_seat * 100)
    pool = get_pool(db, lock=True)
    if pool is None:
        pool = SubsidyPool(code=POOL_CODE, total_cents=total_cents, per_seat_cents=per_seat_cents)
        db.add(pool)
    else:
        if total_cents < pool.reserved_cents + pool.charged_cents:
            raise HTTPException(409, '补贴总额不能低于已占用与已实扣之和')
        pool.total_cents = total_cents
        pool.per_seat_cents = per_seat_cents
    pool.updated_at = now_utc()
    db.flush()
    audit(db, actor, 'subsidy_pool_configured', 'subsidy_pool', pool.id,
          f'总额 {total_cents} 分 · 每座标准 {per_seat_cents} 分')
    return pool_json(pool)


def reserve(db, pilot, actor):
    """派单占用：池行锁内检查并扣减余额，余额不足则整个工单不落账。"""
    pool = get_pool(db, lock=True)
    if pool is None:
        raise HTTPException(409, '周末试行补贴尚未配置，无法派发工单')
    cost = pool.per_seat_cents * pilot.pilot_seats
    if pool.total_cents - pool.reserved_cents - pool.charged_cents < cost:
        raise HTTPException(409, '周末试行补贴余额不足，工单未派发')
    pool.reserved_cents += cost
    pool.updated_at = now_utc()
    db.add(SubsidyReservation(pilot_id=pilot.id, per_seat_cents=pool.per_seat_cents,
                              reserved_cents=cost, state='reserved'))
    db.flush()
    audit(db, actor, 'subsidy_reserved', 'scheduling_pilot', pilot.id,
          f'计划 {pilot.pilot_seats} 座 · 占用 {cost} 分')


def _reservation_for(db, pilot_id):
    return db.scalar(select(SubsidyReservation).where(SubsidyReservation.pilot_id == pilot_id))


def settle(db, pilot, actor):
    """排片确认：按实投座位扣款，占用与实扣的差额回到余额。"""
    reservation = _reservation_for(db, pilot.id)
    if reservation is None or reservation.state != 'reserved':
        return
    charged = reservation.per_seat_cents * pilot.actual_seats
    pool = get_pool(db, lock=True)
    if pool is not None:
        pool.reserved_cents -= reservation.reserved_cents
        pool.charged_cents += charged
        pool.updated_at = now_utc()
    reservation.state = 'charged'
    reservation.charged_cents = charged
    reservation.resolved_at = now_utc()
    db.flush()
    audit(db, actor, 'subsidy_charged', 'scheduling_pilot', pilot.id,
          f'实投 {pilot.actual_seats} 座 · 实扣 {charged} 分 · 回池 {reservation.reserved_cents - charged} 分')


def release(db, pilot, actor):
    """工单撤回：整笔占用释放回余额。"""
    reservation = _reservation_for(db, pilot.id)
    if reservation is None or reservation.state != 'reserved':
        return
    pool = get_pool(db, lock=True)
    if pool is not None:
        pool.reserved_cents -= reservation.reserved_cents
        pool.updated_at = now_utc()
    reservation.state = 'released'
    reservation.resolved_at = now_utc()
    db.flush()
    audit(db, actor, 'subsidy_released', 'scheduling_pilot', pilot.id,
          f'释放占用 {reservation.reserved_cents} 分')
