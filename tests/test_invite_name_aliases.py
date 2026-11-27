import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'tasks/Component/GeneralInvite/general_invite.py'


class Box:
    def __getitem__(self, key):
        return ((10, 20), (50, 20), (50, 40))[key[0]][key[1]]


class AliasTest(unittest.TestCase):
    def setUp(self):
        names = {'_normalize_friend_name_text', '_find_exact_friend_area', '_select_current_page_friends'}
        nodes = [n for n in ast.walk(ast.parse(SOURCE.read_text(encoding='utf-8')))
                 if isinstance(n, ast.FunctionDef) and n.name in names]
        cls = ast.ClassDef(name='Invite', bases=[], keywords=[], body=nodes, decorator_list=[])
        env = {'logger': SimpleNamespace(info=lambda *a: None)}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), str(SOURCE), 'exec'), env)
        self.invite = env['Invite']()
        self.invite.device = SimpleNamespace(image=None)

    def find(self, names, text):
        rule = SimpleNamespace(roi=(100, 200), name='friend', detect_and_ocr=lambda _: [
            SimpleNamespace(ocr_text=text, box=Box())])
        return self.invite._find_exact_friend_area(rule, names)

    def test_second_alias_matches(self):
        self.assertEqual(self.find('测试甲;测试乙', '测试乙'), (110, 220, 40, 20))

    def test_chinese_separator_and_whitespace(self):
        self.assertIsNotNone(self.find(' 测试丙； 测试丁 ;', '测试丁'))

    def test_no_partial_or_empty_match(self):
        for names in ('测试', '测试甲;测试乙', ';；', None):
            self.assertIsNone(self.find(names, '测试乙的好友'))

    def test_one_alias_group_selected_once_across_pages(self):
        calls = []
        self.invite._detect_select = lambda name: calls.append(name) or True
        selected = set()
        friends = ['测试甲;测试乙', '另一个好友']
        for _ in range(2):
            self.invite._select_current_page_friends(friends, selected)
        self.assertEqual(calls, friends)
        self.assertEqual(len(selected), 2)


if __name__ == '__main__':
    unittest.main()
