"""Chess image compatibility without changing the shared image service."""
import cv2

from module.atom.image import RuleImage as SharedRuleImage


class RuleImage(SharedRuleImage):
    METHOD_MASKED_TEMPLATE_MATCH = 'Masked template matching'

    def __init__(self, roi_front, roi_back, method, threshold, file, profile='High'):
        super().__init__(roi_front, roi_back, method, threshold, file)
        self.profile = profile

    def template_match(self, image, threshold=None):
        source, template = self.corp(image), self.image
        if (not source.size or not template.size
                or source.shape[0] < template.shape[0]
                or source.shape[1] < template.shape[1]):
            return False
        if getattr(self, 'grayscale', False):
            if source.ndim == 3:
                source = cv2.cvtColor(source, cv2.COLOR_RGB2GRAY)
            if template.ndim == 3:
                template = cv2.cvtColor(template, cv2.COLOR_RGB2GRAY)
        result = cv2.matchTemplate(source, template, cv2.TM_CCOEFF_NORMED)
        _, score, _, location = cv2.minMaxLoc(result)
        if score > (self.threshold if threshold is None else threshold):
            self._update_roi_front(location, (template.shape[1], template.shape[0]))
            return True
        return False

    def match(self, image, threshold=None, frame_id=None):
        if getattr(self, 'grayscale', False):
            return self.template_match(image, threshold)
        return super().match(image, threshold, frame_id)
