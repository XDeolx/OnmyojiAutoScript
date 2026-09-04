from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class EllipseRegion:
    """A safe settlement click region represented by an ellipse."""

    name: str
    bounds: tuple[int, int, int, int]

    def contains(self, point: tuple[int, int], scale: float = 1.0) -> bool:
        x1, y1, x2, y2 = self.bounds
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        rx = max((x2 - x1) * scale / 2, 1)
        ry = max((y2 - y1) * scale / 2, 1)
        x, y = point
        return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1

    def sample(self, scale: float = 0.82) -> tuple[int, int]:
        """Sample uniformly by area inside an inset copy of the ellipse."""
        x1, y1, x2, y2 = self.bounds
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        radius = math.sqrt(random.random()) * scale
        angle = random.uniform(0, math.tau)
        x = round(cx + math.cos(angle) * radius * (x2 - x1) / 2)
        y = round(cy + math.sin(angle) * radius * (y2 - y1) / 2)
        return max(0, min(1279, x)), max(0, min(719, y))


SETTLEMENT_REGIONS = {
    1: EllipseRegion('R1', (70, 281, 322, 494)),
    2: EllipseRegion('R2', (309, 19, 528, 143)),
    3: EllipseRegion('R3', (586, 30, 777, 143)),
    4: EllipseRegion('R4', (801, 52, 1022, 178)),
    5: EllipseRegion('R5', (946, 145, 1264, 318)),
    6: EllipseRegion('R6', (900, 308, 1179, 489)),
    7: EllipseRegion('R7', (938, 476, 1265, 692)),
    8: EllipseRegion('R8', (645, 524, 1008, 713)),
    9: EllipseRegion('R9', (457, 553, 692, 685)),
    10: EllipseRegion('R10', (16, 105, 260, 288)),
    11: EllipseRegion('R11', (18, 485, 276, 695)),
}

DETAIL_REGIONS = {
    1: EllipseRegion('Detail1', (600, 371, 662, 433)),
    2: EllipseRegion('Detail2', (696, 371, 758, 433)),
    3: EllipseRegion('Detail3', (791, 371, 853, 433)),
}

CATEGORY_POOLS = {
    'A': (1, 10, 11),
    'B': (2, 3, 4),
    'C': (5, 6),
    'D': (8, 9),
    'E': (7,),
}
CATEGORY_COUNTS = {'A': 2, 'B': 2, 'C': 1, 'D': 1, 'E': 1}
CATEGORY_WEIGHTS = {'A': 5, 'B': 5, 'C': 25, 'D': 20, 'E': 45}


@dataclass(frozen=True)
class SettlementDecision:
    kind: str
    battle_number: int
    detail_progress: int
    detail_target: int


class ClimbSettlementPlanner:
    """Build one task-level region template and settlement behavior sequence."""

    def __init__(
        self,
        *,
        detail_enabled: bool,
        detail_interval_min: int,
        detail_interval_max: int,
        detail_delay_min: float,
        detail_delay_max: float,
        burst_percent: int,
    ) -> None:
        self.detail_enabled = detail_enabled
        self.detail_interval_min = detail_interval_min
        self.detail_interval_max = detail_interval_max
        self.detail_delay_min = detail_delay_min
        self.detail_delay_max = detail_delay_max
        self.burst_percent = burst_percent
        self.template = {
            category: tuple(random.sample(pool, CATEGORY_COUNTS[category]))
            for category, pool in CATEGORY_POOLS.items()
        }
        self.battle_count = 0
        self.detail_target = self._next_detail_target()
        # Randomize the first cycle phase so each task does not always begin at zero.
        self.detail_progress = random.randint(0, self.detail_target - 1)

    def _next_detail_target(self) -> int:
        return random.randint(self.detail_interval_min, self.detail_interval_max)

    def begin_settlement(self) -> SettlementDecision:
        self.battle_count += 1
        if self.detail_enabled:
            self.detail_progress += 1
            if self.detail_progress >= self.detail_target:
                completed_target = self.detail_target
                self.detail_progress = 0
                self.detail_target = self._next_detail_target()
                return SettlementDecision(
                    kind='detail',
                    battle_number=self.battle_count,
                    detail_progress=completed_target,
                    detail_target=completed_target,
                )

        kind = 'burst' if random.random() < self.burst_percent / 100 else 'weighted'
        return SettlementDecision(
            kind=kind,
            battle_number=self.battle_count,
            detail_progress=self.detail_progress,
            detail_target=self.detail_target,
        )

    def weighted_point(self) -> tuple[str, str, tuple[int, int]]:
        category = random.choices(
            tuple(CATEGORY_WEIGHTS),
            weights=tuple(CATEGORY_WEIGHTS.values()),
            k=1,
        )[0]
        region_id = random.choice(self.template[category])
        region = SETTLEMENT_REGIONS[region_id]
        return category, region.name, region.sample()

    def detail_point(self) -> tuple[str, tuple[int, int]]:
        region = random.choice(tuple(DETAIL_REGIONS.values()))
        return region.name, region.sample(scale=0.72)

    def detail_delay(self) -> float:
        return round(random.uniform(self.detail_delay_min, self.detail_delay_max), 2)

    def burst_points(self) -> list[tuple[int, int]]:
        region = SETTLEMENT_REGIONS[7]
        count = random.randint(3, 4)
        anchor = region.sample(scale=0.62)
        points = []
        for _ in range(count):
            for _attempt in range(12):
                point = (
                    anchor[0] + random.randint(-7, 7),
                    anchor[1] + random.randint(-6, 6),
                )
                if region.contains(point, scale=0.82):
                    points.append(point)
                    break
            else:
                points.append(anchor)
        return points

    @property
    def template_summary(self) -> str:
        return ', '.join(
            f'{category}={"/".join(SETTLEMENT_REGIONS[index].name for index in indexes)}'
            for category, indexes in self.template.items()
        )
