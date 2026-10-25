from module.exception import ScriptError
from tasks.Chess.runtime.frame import RuleFrame, FrameResult


class ChessRuntimeCompatibilityMixin:
    def appear(self, target, interval=None, threshold=None):
        # The shared batch service cannot interpret multi-badge frame rules.
        if threshold is None and (isinstance(target, RuleFrame)
                                  or getattr(target, 'grayscale', False)):
            threshold = target.threshold
        return super().appear(target, interval=interval, threshold=threshold)

    def runframe(self, target: RuleFrame, *range_results, interval=None, threshold=None) -> FrameResult:
        """读取 frame.data（坐标、裁剪图、文字）；仅 Click 显式 True 点击，其余参数可选比对。"""
        if not isinstance(target, RuleFrame):
            raise ScriptError('runframe 的第一个参数必须是 RuleFrame')
        try:
            return target.run(self, *range_results, interval=interval, threshold=threshold)
        except (TypeError, ValueError) as error:
            raise ScriptError(f'runframe 配置或区域无效: {error}') from error


    def ui_click_until_disappear(self, click, interval: float = 1, *,
                                 click_target=None, visible=None, guard=None, before_click=None,
                                 timeout: float | None = None, confirm_frames: int = 1,
                                 max_clicks: int | None = None):
        """点击直到目标消失；可独立指定点击区、可见性判定和有界多帧确认。

        超时或 guard 不满足时返回 False；默认行为与旧调用一致。
        """
        from time import monotonic
        appear_and_clicked = False
        click_count = 0
        missing = 0
        deadline = monotonic() + timeout if timeout is not None else None
        while deadline is None or monotonic() < deadline:
            self.screenshot()
            if guard is not None and not guard():
                return False
            present = visible() if visible is not None else self.appear(click)
            if not present:
                missing += 1
                if missing >= confirm_frames:
                    return appear_and_clicked
                continue
            missing = 0
            if max_clicks is not None and click_count >= max_clicks:
                return False
            if before_click is not None and not before_click():
                return False
            if click_target is not None:
                if self.click(click_target, interval=interval):
                    appear_and_clicked = True
                    click_count += 1
            elif self.appear_then_click(click, interval=interval):
                appear_and_clicked = True
                click_count += 1
        return False
