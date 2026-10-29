import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import ROOT, Runner, Store, output_matches, validate_state
from exercises import EXERCISES


class BookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runner = Runner(self.temp.name)

    def tearDown(self):
        self.runner.stop()
        self.temp.cleanup()

    def test_every_exercise_solution(self):
        self.assertEqual(set(EXERCISES), set(range(1, 31)))
        for day, exercises in EXERCISES.items():
            for exercise in exercises:
                with self.subTest(day=day, task=exercise['title']):
                    result = self.runner.run(exercise['solution'], exercise['stdin'])
                    self.assertTrue(result['ok'], result)
                    self.assertTrue(output_matches(result['output'], exercise['expected']), result)

    def test_traceback_and_russian_help(self):
        result = self.runner.run('value = "5"\nprint(value + 2)\n')
        self.assertFalse(result['ok'])
        self.assertIn('TypeError', result['output'])
        self.assertIn('типы', result['reason'])

    def test_input_eof_and_unicode(self):
        good = self.runner.run('print(input() + "!")', 'Привет\n')
        self.assertTrue(good['ok'])
        self.assertEqual(good['output'], 'Привет!\n')
        bad = self.runner.run('input()')
        self.assertFalse(bad['ok'])
        self.assertIn('входных строк', bad['reason'])

    def test_timeout(self):
        result = self.runner.run('while True:\n    pass\n', timeout=0.2)
        self.assertFalse(result['ok'])
        self.assertIn('Время вышло', result['reason'])

    def test_output_limit(self):
        result = self.runner.run('while True:\n    print("x" * 1024)\n')
        self.assertFalse(result['ok'])
        self.assertLessEqual(len(result['output'].encode()), self.runner.LIMIT)
        self.assertIn('Слишком много вывода', result['reason'])

    def test_stop(self):
        results = []
        worker = threading.Thread(target=lambda: results.append(self.runner.run('while True:\n    pass\n')))
        worker.start()
        deadline = time.monotonic() + 2
        while self.runner.process is None and time.monotonic() < deadline:
            time.sleep(0.01)
        self.runner.stop()
        worker.join(timeout=3)
        self.assertFalse(worker.is_alive())
        self.assertIn('остановлен', results[0]['reason'])

    def test_files_persist_but_temporary_script_removed(self):
        result = self.runner.run('from pathlib import Path\nPath("hello.txt").write_text("Привет", encoding="utf-8")\n')
        self.assertTrue(result['ok'])
        self.assertEqual((Path(self.temp.name) / 'hello.txt').read_text(encoding='utf-8'), 'Привет')
        self.assertEqual(list(Path(self.temp.name).glob('lesson_*.py')), [])

    def test_state_roundtrip_and_corruption_backup(self):
        store = Store(self.temp.name)
        store.page(4).update(notes='Заметка', draft='print(42)', input='25', exercise=0, passed=[0])
        store.state['done'] = [1, 2]
        store.save()
        self.assertEqual(Store(self.temp.name).state, store.state)
        store.path.write_text('{повреждено', encoding='utf-8')
        recovered = Store(self.temp.name)
        self.assertTrue(recovered.warning)
        self.assertEqual((Path(self.temp.name) / 'progress-damaged.json').read_text(encoding='utf-8'), '{повреждено')
        self.assertEqual(recovered.state['done'], [])

    def test_invalid_backup(self):
        for value in ([], {}, {'version': 1, 'current': -1}, {'version': 1, 'done': [True]},
                      {'version': 1, 'pages': {'1': {'draft': 5}}},
                      {'version': 1, 'pages': {'../../x': {}}}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_state(value)

    def test_course_integrity(self):
        chapters = list((ROOT / 'course').glob('*.md'))
        self.assertEqual(len(chapters), 30)
        for path in chapters:
            text = path.read_text(encoding='utf-8')
            self.assertTrue(text.startswith('# '))
            self.assertEqual(text.count('```') % 2, 0, path.name)
        source = json.loads((ROOT / 'original' / 'SOURCE.json').read_text())
        self.assertEqual(len(source['files']), 30)

    def test_output_normalization(self):
        self.assertTrue(output_matches('Привет\r\n5\r\n', 'Привет\n5'))
        self.assertFalse(output_matches(' 5\n', '5'))


if __name__ == '__main__':
    unittest.main()
