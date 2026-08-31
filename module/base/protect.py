import random
from time import sleep

from module.logger import logger


def random_delay(
    min_value: float = 2.0,
    max_value: float = 6.0,
    decimal: int = 1,
) -> float:
    """
    防封
    """
    delay = round(random.uniform(min_value, max_value), decimal)
    logger.info(f'通用随机休息: delay={delay:.1f}s')
    sleep(delay)
    return delay


def random_sleep(probability: float = 0.05):
    if random.random() <= probability:
        return random_delay()
    return 0.0
