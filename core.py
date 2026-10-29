"""Хранение данных и выполнение кода независимо от графического интерфейса."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parent
TITLES = [
    "Первые шаги", "Переменные и функции", "Операторы", "Строки", "Списки",
    "Кортежи", "Множества", "Словари", "Условия", "Циклы", "Функции",
    "Модули", "Генераторы списков", "Функции высшего порядка", "Ошибки",
    "Даты и время", "Исключения", "Регулярные выражения", "Файлы и JSON",
    "Пакеты и pip", "Классы и объекты", "Сбор данных со страниц", "Окружения",
    "Статистика и NumPy", "Pandas", "Python для веба", "MongoDB", "API",
    "Создаём API", "Финальный проект",
]


def data_directory():
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "python-book-ru"


def validate_state(value):
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ValueError("Это не резервная копия книги версии 1")
    current = value.get("current", 1)
    if type(current) is not int or not 1 <= current <= 30:
        raise ValueError("Неверный номер главы")
    done = value.get("done", [])
    if not isinstance(done, list) or any(type(x) is not int or not 1 <= x <= 30 for x in done):
        raise ValueError("Неверный список пройденных глав")
    pages = value.get("pages", {})
    if not isinstance(pages, dict) or len(pages) > 30:
        raise ValueError("Неверные данные глав")
    for key, page in pages.items():
        if key not in {str(i) for i in range(1, 31)} or not isinstance(page, dict):
            raise ValueError("Неверная запись главы")
        for field in ("notes", "draft", "input"):
            if field in page and (not isinstance(page[field], str) or len(page[field]) > 500_000):
                raise ValueError("Слишком большой или неверный текст")
        drafts = page.get("drafts", {})
        if not isinstance(drafts, dict) or len(drafts) > 10:
            raise ValueError("Неверные черновики заданий")
        for index, draft in drafts.items():
            if index not in {str(i) for i in range(10)} or not isinstance(draft, dict):
                raise ValueError("Неверный черновик")
            if any(not isinstance(draft.get(field, ""), str) or len(draft.get(field, "")) > 500_000 for field in ("code", "input")):
                raise ValueError("Неверный текст черновика")
        if "exercise" in page and (type(page["exercise"]) is not int or not 0 <= page["exercise"] < 10):
            raise ValueError("Неверное задание")
        passed = page.get("passed", [])
        if not isinstance(passed, list) or any(type(i) is not int or not 0 <= i < 10 for i in passed):
            raise ValueError("Неверные результаты заданий")
    return value


class Store:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory else data_directory()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.practice = self.directory / "practice"
        self.practice.mkdir(exist_ok=True)
        self.path = self.directory / "progress.json"
        self.warning = ""
        self.state = {"version": 1, "current": 1, "done": [], "pages": {}}
        if self.path.exists():
            try:
                self.state = validate_state(json.loads(self.path.read_text(encoding="utf-8")))
            except (ValueError, OSError) as error:
                # Сохраняем исходные байты, чтобы не потерять повреждённую запись.
                backup = self.directory / "progress-damaged.json"
                try:
                    import shutil
                    shutil.copy2(self.path, backup)
                except OSError:
                    raise OSError("Не удалось сохранить повреждённый прогресс; исходный файл не изменён")
                self.warning = f"Не удалось прочитать прогресс: {error}. Копия: {backup}"

    def page(self, day):
        return self.state["pages"].setdefault(str(day), {})

    def save(self):
        text = json.dumps(self.state, ensure_ascii=False, indent=2)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(text, encoding="utf-8")
        temp.replace(self.path)


def error_help(output):
    messages = {
        "SyntaxError": "Проверь кавычки, скобки и двоеточия. В поле Python не вводят команды терминала.",
        "IndentationError": "Проверь отступы: внутри блока обычно четыре пробела. Tab вставляет их автоматически.",
        "NameError": "Проверь написание имени и создай переменную или функцию до её использования.",
        "TypeError": "Проверь типы через type(). input возвращает текст; для вычислений нужен int или float.",
        "ValueError": "Тип подходит, но значение не удалось обработать. Например, int не может разобрать слово.",
        "IndexError": "Такого индекса нет. Первый индекс — 0, последний — len(список) - 1.",
        "KeyError": "Такого ключа в словаре нет. Проверь ключ или используй get.",
        "ZeroDivisionError": "Знаменатель оказался равен нулю. Добавь проверку перед делением.",
        "ModuleNotFoundError": "Пакет не найден. Установи его в тот Python, которым запущена книга. Инструкция в главе 20.",
        "EOFError": "Не хватило входных строк для input(). Заполни поле входных данных до запуска.",
        "FileNotFoundError": "Проверь имя и путь. Относительные пути считаются от папки практики.",
        "AttributeError": "У этого объекта нет такого метода. Проверь тип объекта и написание метода.",
    }
    last_line = output.splitlines()[-1] if output.splitlines() else ""
    for key, help_text in messages.items():
        if key in last_line:
            return help_text
    return "Прочитай последнюю строку ошибки и номер строки своего кода выше. Глава 15 поможет разобраться."


class Runner:
    LIMIT = 64_000

    def __init__(self, practice):
        self.practice = Path(practice)
        self.process = None
        self.lock = threading.Lock()
        self.cancelled = threading.Event()

    def stop(self):
        self.cancelled.set()
        with self.lock:
            process = self.process
        if process and process.poll() is None:
            try:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
            except ProcessLookupError:
                pass

    def run(self, code, stdin="", timeout=8, reset_cancel=True):
        """Вызывается в рабочем потоке; результат не обращается к Tk."""
        if reset_cancel:
            self.cancelled.clear()
        output = bytearray()
        limited = threading.Event()
        script_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", prefix="lesson_", dir=self.practice,
                                             encoding="utf-8", delete=False) as script:
                script.write(code)
                script_path = Path(script.name)
            with tempfile.TemporaryFile() as input_file:
                input_file.write(stdin.encode("utf-8"))
                input_file.seek(0)
                kwargs = {"start_new_session": True} if os.name == "posix" else {"creationflags": subprocess.CREATE_NO_WINDOW}
                process = subprocess.Popen(
                    [sys.executable, "-X", "utf8", "-u", str(script_path)],
                    cwd=self.practice, stdin=input_file, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, **kwargs)
                with self.lock:
                    self.process = process
                if self.cancelled.is_set():
                    self.stop()

                def read_output():
                    while True:
                        chunk = process.stdout.read(1024)
                        if not chunk:
                            break
                        remaining = self.LIMIT - len(output)
                        output.extend(chunk[:remaining])
                        if len(chunk) > remaining:
                            limited.set()
                            self.stop()
                            break

                reader = threading.Thread(target=read_output, daemon=True)
                reader.start()
                timed_out = False
                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    self.stop()
                    process.wait(timeout=2)
                reader.join(timeout=2)
                process.stdout.close()
                text = output.decode("utf-8", errors="replace")
                if limited.is_set():
                    return {"ok": False, "output": text, "reason": "Слишком много вывода (предел 64 КБ). Проверь цикл."}
                if timed_out:
                    return {"ok": False, "output": text, "reason": "Время вышло (8 секунд). Проверь условие цикла или запусти длительный пример отдельно."}
                if self.cancelled.is_set():
                    return {"ok": False, "output": text, "reason": "Запуск остановлен."}
                return {"ok": process.returncode == 0, "output": text, "reason": "" if process.returncode == 0 else error_help(text)}
        except Exception as error:
            return {"ok": False, "output": "", "reason": f"Не удалось запустить код: {error}"}
        finally:
            with self.lock:
                self.process = None
            if script_path:
                script_path.unlink(missing_ok=True)


def output_matches(actual, expected):
    # Не учитываем переводы строк Windows и завершающий перенос.
    return actual.replace("\r\n", "\n").rstrip("\n") == expected.replace("\r\n", "\n").rstrip("\n")
