# This Python file uses the following encoding: utf-8
import time

from module.logger import logger
from tasks.Chess.assets import ChessAssets
from tasks.Component.Buy.buy import Buy
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_entertainment
from tasks.RichMan.assets import RichManAssets
from tasks.RichMan.config import ItachiCoinShop as ItachiCoinShopConfig
from tasks.RichMan.page import page_itachi_shop


class ItachiCoinShop(Buy, GameUi, RichManAssets):
    """购买鼬乐币商店中自动前移的勾玉礼盒。"""

    ENTERTAINMENT_OVERLAY_TIMEOUT = 8.0
    ENTERTAINMENT_STABLE_TIME = 1.0
    GIFT_DIALOG_TIMEOUT = 3.0
    PURCHASE_RESULT_TIMEOUT = 8.0
    PURCHASE_RETURN_GRACE = 3.0
    REWARD_DISMISS_TIMEOUT = 5.0
    MAX_GIFT_PURCHASES = 3
    GIFT_OPENED = 'opened'
    GIFT_PURCHASED = 'purchased'
    GIFT_SOLD_OUT = 'sold_out'
    GIFT_STOP = 'stop'

    def execute_itachi_coin_shop(self, con: ItachiCoinShopConfig) -> None:
        if not con.itachi_coin_buy_jade:
            logger.info('鼬乐币商店购买未启用')
            return

        logger.hr('鼬乐币商店', 1)
        self.goto_page(page_entertainment)
        if not self._wait_entertainment_overlay_closed():
            logger.warning('鼬乐园附属页未关闭，跳过本次购买')
            return

        self.goto_page(page_itachi_shop)
        purchased = 0
        for _ in range(self.MAX_GIFT_PURCHASES):
            open_result = self._open_front_gift_once()
            if open_result == self.GIFT_SOLD_OUT:
                logger.info('当前鼬乐礼盒已售罄，继续尝试下一个')
                continue
            if open_result != self.GIFT_OPENED:
                logger.info('鼬乐币勾玉礼盒已购买或不可购买')
                break

            purchase_result = self._buy_opened_gift()
            if purchase_result == self.GIFT_SOLD_OUT:
                logger.info('当前鼬乐礼盒已售罄，继续尝试下一个')
                continue
            if purchase_result != self.GIFT_PURCHASED:
                break
            purchased += 1

        logger.info(f'鼬乐币礼盒购买完成: count={purchased}')
        self.goto_page(page_entertainment)

    def _wait_entertainment_overlay_closed(self) -> bool:
        deadline = time.monotonic() + self.ENTERTAINMENT_OVERLAY_TIMEOUT
        stable_since = None
        while time.monotonic() < deadline:
            self.screenshot()
            if self.appear(ChessAssets.I_SKIP):
                self.appear_then_click(ChessAssets.I_SKIP, interval=0.5)
                stable_since = None
                continue

            if stable_since is None:
                stable_since = time.monotonic()
                continue
            if time.monotonic() - stable_since >= self.ENTERTAINMENT_STABLE_TIME:
                return True
        return False

    def _open_front_gift_once(self) -> str:
        self.screenshot()
        self.click(self.C_ITACHI_GIFT)
        deadline = time.monotonic() + self.GIFT_DIALOG_TIMEOUT
        while time.monotonic() < deadline:
            self.screenshot()
            status = self._read_purchase_status()
            if status is not None:
                return status
            if self.appear(self.I_BUY_PLUS):
                return self.GIFT_OPENED
        return self.GIFT_STOP

    def _read_itachi_coin(self) -> tuple[int, int] | None:
        result = self.O_ITACHI_COIN.ocr(self.device.image)
        if isinstance(result, tuple) and len(result) >= 3:
            current, _, total = result[:3]
            if total > 0:
                logger.info(f'鼬乐币: {current}/{total}')
                return int(current), int(total)
        logger.warning(f'鼬乐币 OCR 失败: result={result}')
        return None

    def _read_buy_cost(self) -> int | None:
        result = self.O_ITACHI_BUY_COST.ocr(self.device.image)
        if isinstance(result, int) and result > 0:
            logger.info(f'鼬乐礼盒价格: cost={result}')
            return result
        logger.warning(f'鼬乐礼盒价格 OCR 失败: result={result}')
        return None

    def _read_purchase_status(self) -> str | None:
        image = self.device.image
        if self.O_ITACHI_COIN_INSUFFICIENT.ocr(image) != (0, 0, 0, 0):
            logger.warning('鼬乐币不足，停止礼盒购买')
            return self.GIFT_STOP
        if self.O_ITACHI_GIFT_SOLD_OUT.ocr(image) != (0, 0, 0, 0):
            return self.GIFT_SOLD_OUT
        return None

    def _buy_opened_gift(self) -> str:
        self.screenshot()
        before_coin = self._read_itachi_coin()
        cost = self._read_buy_cost()
        self.click(self.C_BUY_MORE)

        deadline = time.monotonic() + self.PURCHASE_RESULT_TIMEOUT
        dialog_absent_since = None
        while time.monotonic() < deadline:
            self.screenshot()
            status = self._read_purchase_status()
            if status is not None:
                return status

            if self.appear(self.I_UI_CONFIRM_SAMLL):
                self.ui_click_until_disappear(
                    self.I_UI_CONFIRM_SAMLL,
                    interval=1,
                )
                logger.warning('鼬乐礼盒出现其他购买提示，已确认并停止购买')
                return self.GIFT_STOP

            if self.appear(self.I_UI_REWARD, threshold=0.6):
                reward_closed = self._dismiss_purchase_reward()
                if reward_closed:
                    if self._verify_coin_cost(before_coin, cost):
                        return self.GIFT_PURCHASED
                return self.GIFT_STOP

            if self.appear(self.I_BUY_PLUS):
                dialog_absent_since = None
                continue

            if dialog_absent_since is None:
                dialog_absent_since = time.monotonic()
                continue
            if time.monotonic() - dialog_absent_since >= self.PURCHASE_RETURN_GRACE:
                logger.warning('鼬乐礼盒购买失败或鼬乐币不足')
                return self.GIFT_STOP

        logger.warning('鼬乐礼盒购买结果等待超时')
        return self.GIFT_STOP

    def _dismiss_purchase_reward(self) -> bool:
        deadline = time.monotonic() + self.REWARD_DISMISS_TIMEOUT
        while time.monotonic() < deadline:
            self.screenshot()
            if not self.appear(self.I_UI_REWARD, threshold=0.6):
                return True
            self.ui_reward_appear_click()
        logger.warning('鼬乐礼盒奖励页未能关闭')
        return False

    def _verify_coin_cost(
        self,
        before_coin: tuple[int, int] | None,
        cost: int | None,
    ) -> bool:
        self.screenshot()
        after_coin = self._read_itachi_coin()
        if before_coin is None or after_coin is None or cost is None:
            return True

        consumed = before_coin[0] - after_coin[0]
        if consumed == cost:
            logger.info(f'鼬乐礼盒购买确认: consumed={consumed}')
            return True
        logger.warning(
            '鼬乐币变化与价格不一致: '
            f'before={before_coin[0]}, after={after_coin[0]}, cost={cost}'
        )
        return False
