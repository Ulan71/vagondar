"""
Расчёт объёма и стоимости подачи/уборки вагонов — единственное место с формулой.

Для события с N вагонами (учитываются только вагоны с направлением):
    min_d          — минимальное расстояние среди вагонов события
    distance_1     — min_d (общий участок пути)
    distance_2     — расстояние вагона - min_d (индивидуальный участок)
    distance_3     — 0 (резерв)
    dist_sum       — distance_1 + distance_2 + distance_3      («Объём за вагон»)
    vol_per_loko   — 3 * distance_1 / N + 3 * distance_2 / (N - 1)   (при N = 1 делитель N)
                     («Объём за локомотив», 3 = проезд локомотива 1,5 * 2)
    total_vol      — dist_sum + vol_per_loko                    («Итого объём»)
    price          — total_vol * тариф                          («Итого»)
"""
from dataclasses import dataclass, field
from decimal import Decimal

LOCO_FACTOR = Decimal(3)  # проезд локомотива (1,5 * 2)
ZERO = Decimal(0)


@dataclass
class WagonCalc:
    wagon: object
    distance_1: Decimal = ZERO
    distance_2: Decimal = ZERO
    distance_3: Decimal = ZERO
    dist_sum: Decimal = ZERO
    vol_per_loko: Decimal = ZERO
    total_vol: Decimal = ZERO
    price: Decimal | None = None
    has_destination: bool = True


@dataclass
class EventCalc:
    rows: list = field(default_factory=list)
    wagons_count: int = 0          # вагоны, участвующие в расчёте
    min_distance: Decimal = ZERO
    tariff: Decimal | None = None
    total_vol: Decimal = ZERO
    total_price: Decimal | None = None
    skipped_wagons: int = 0        # вагоны без направления

    @property
    def loko_divisor_2(self):
        return self.wagons_count - 1 if self.wagons_count > 1 else self.wagons_count


def calculate_event(event, wagons=None):
    """Считает событие. wagons можно передать, чтобы не делать лишний запрос."""
    if wagons is None:
        wagons = list(event.wagons.all())
    tariff = event.tariff.tariff if event.tariff_id and event.tariff else None

    result = EventCalc(tariff=tariff)
    counted = [w for w in wagons if w.destination is not None]
    result.wagons_count = n = len(counted)
    result.skipped_wagons = len(wagons) - n

    if n:
        result.min_distance = min(w.destination.distance_km for w in counted)
    divisor_2 = result.loko_divisor_2

    for wagon in wagons:
        if wagon.destination is None:
            result.rows.append(WagonCalc(wagon=wagon, has_destination=False))
            continue

        row = WagonCalc(wagon=wagon)
        row.distance_1 = result.min_distance
        row.distance_2 = wagon.destination.distance_km - result.min_distance
        row.dist_sum = row.distance_1 + row.distance_2 + row.distance_3
        row.vol_per_loko = LOCO_FACTOR * row.distance_1 / n + LOCO_FACTOR * row.distance_2 / divisor_2
        row.total_vol = row.dist_sum + row.vol_per_loko
        if tariff is not None:
            row.price = row.total_vol * tariff

        result.total_vol += row.total_vol
        result.rows.append(row)

    if tariff is not None:
        result.total_price = sum((r.price for r in result.rows if r.price is not None), ZERO)
    return result
