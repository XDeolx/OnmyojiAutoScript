import unittest
from unittest.mock import patch

from module.atom.click import RuleClick
from module.base.utils import random_normal_distribution_int


class HumanizedInputTest(unittest.TestCase):
    def test_normal_distribution_uses_average_and_stays_in_range(self):
        with patch(
            'module.base.utils.utils.np.random.randint',
            return_value=[10, 50, 90],
        ):
            self.assertEqual(random_normal_distribution_int(0, 100), 50)

    def test_rule_click_uses_humanized_coordinate_distribution(self):
        rule = RuleClick((10, 20, 30, 40), (0, 0, 1, 1), name='TEST')
        with patch(
            'module.atom.click.random_normal_distribution_int',
            side_effect=[25, 45],
        ) as random_coordinate:
            self.assertEqual(rule.coord(), (25, 45))
        self.assertEqual(random_coordinate.call_count, 2)


if __name__ == '__main__':
    unittest.main()
