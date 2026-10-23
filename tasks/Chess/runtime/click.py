"""Accept frame metadata while retaining the installed click implementation."""
from module.atom.click import RuleClick as SharedRuleClick


class RuleClick(SharedRuleClick):
    def __init__(self, roi_front, roi_back, name, profile='High'):
        super().__init__(roi_front, roi_back, name)
        self.profile = profile
