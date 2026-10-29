#!/usr/bin/env python3
"""Python с нуля — настольная интерактивная книга на Tkinter."""
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from core import ROOT, TITLES, Runner, Store, output_matches, validate_state
from exercises import EXERCISES

PAPER = "#faf7f0"
INK = "#20332f"
GREEN = "#236654"


class Book(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Python с нуля · интерактивная книга")
        self.geometry("1240x820")
        self.minsize(860, 600)
        self.configure(bg=PAPER)
        self.store = Store()
        self.runner = Runner(self.store.practice)
        self.events = queue.Queue()
        self.busy = False
        self.day = None
        self.exercise_index = 0
        self.loading = False
        self.font_size = 12
        self.blocks = {}
        self.search_map = []
        self.chapters = {i: (ROOT / "course" / f"{i:02}.md").read_text(encoding="utf-8") for i in range(1, 31)}
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.setup_style()
        self.build_menu()
        self.build_layout()
        self.open_day(self.store.state["current"])
        self.bind("<Control-Return>", lambda event: self.run_code(False))
        self.bind("<Control-s>", lambda event: self.save_now())
        self.after(100, self.poll)
        self.after(1500, self.autosave)
        if self.store.warning:
            self.after(300, lambda: messagebox.showwarning("Прогресс", self.store.warning))

    def setup_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 11), background=PAPER, foreground=INK)
        style.configure("TButton", padding=(10, 7))
        style.configure("Accent.TButton", background=GREEN, foreground="white")
        style.map("Accent.TButton", background=[("active", "#194c3e"), ("disabled", "#829d94")])
        style.configure("TNotebook.Tab", padding=(18, 9))
        style.configure("TProgressbar", background=GREEN, troughcolor="#e1e7df")

    def build_menu(self):
        menu = tk.Menu(self)
        data = tk.Menu(menu, tearoff=False)
        data.add_command(label="Сохранить сейчас  Ctrl+S", command=self.save_now)
        data.add_command(label="Экспорт прогресса и заметок…", command=self.export_state)
        data.add_command(label="Импорт резервной копии…", command=self.import_state)
        data.add_separator()
        data.add_command(label="Открыть папку практики", command=lambda: self.open_folder(self.store.practice))
        data.add_command(label="Открыть папку прогресса", command=lambda: self.open_folder(self.store.directory))
        menu.add_cascade(label="Данные", menu=data)
        view = tk.Menu(menu, tearoff=False)
        view.add_command(label="Увеличить текст", command=lambda: self.resize_text(1))
        view.add_command(label="Уменьшить текст", command=lambda: self.resize_text(-1))
        view.add_command(label="Открыть книгу для печати", command=lambda: webbrowser.open((ROOT / "Книга.html").as_uri()))
        menu.add_cascade(label="Вид", menu=view)
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="Как пользоваться", command=self.show_help)
        help_menu.add_command(label="Автор курса и статус перевода", command=self.about)
        menu.add_cascade(label="Справка", menu=help_menu)
        self.config(menu=menu)

    def build_layout(self):
        header = tk.Frame(self, bg=INK, padx=22, pady=14)
        header.pack(fill="x")
        tk.Label(header, text="PYTHON  /  С НУЛЯ", bg=INK, fg="#f7f2e6", font=("Segoe UI", 18, "bold")).pack(side="left")
        tk.Label(header, text="Читай → пробуй → понимай", bg=INK, fg="#a9c9b7", font=("Segoe UI", 12)).pack(side="right")

        outer = ttk.Panedwindow(self, orient="horizontal")
        outer.pack(fill="both", expand=True, padx=14, pady=12)
        sidebar = ttk.Frame(outer, width=260)
        outer.add(sidebar, weight=0)
        ttk.Label(sidebar, text="ТВОЙ МАРШРУТ", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 8))
        self.progress_label = ttk.Label(sidebar)
        self.progress_label.pack(anchor="w")
        self.progress = ttk.Progressbar(sidebar, maximum=30)
        self.progress.pack(fill="x", pady=(6, 14))
        self.search = tk.StringVar()
        search_entry = ttk.Entry(sidebar, textvariable=self.search)
        search_entry.pack(fill="x")
        ttk.Label(sidebar, text="Поиск по тексту всех глав", font=("Segoe UI", 9)).pack(anchor="w", pady=(3, 8))
        self.search.trace_add("write", lambda *_: self.refresh_list())
        self.chapter_list = tk.Listbox(sidebar, font=("Segoe UI", 11), bg="#f0eee5", fg=INK,
                                       selectbackground=GREEN, selectforeground="white", activestyle="none",
                                       relief="flat", borderwidth=0, exportselection=False, width=29)
        self.chapter_list.pack(fill="both", expand=True)
        self.chapter_list.bind("<<ListboxSelect>>", self.select_chapter)
        ttk.Label(sidebar, text="30 тем · в твоём темпе\nПрогресс хранится на компьютере", font=("Segoe UI", 9)).pack(anchor="w", pady=10)

        main = ttk.Frame(outer)
        outer.add(main, weight=1)
        top = ttk.Frame(main)
        top.pack(fill="x", pady=(0, 8))
        self.chapter_label = ttk.Label(top, font=("Segoe UI", 17, "bold"))
        self.chapter_label.pack(side="left")
        self.notebook = ttk.Notebook(main)
        self.notebook.pack(fill="both", expand=True)
        lesson = ttk.Frame(self.notebook)
        practice = ttk.Frame(self.notebook, padding=10)
        notes = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(lesson, text="Урок")
        self.notebook.add(practice, text="Практика")
        self.notebook.add(notes, text="Заметки")
        self.lesson = ScrolledText(lesson, wrap="word", padx=24, pady=18, relief="flat",
                                   bg=PAPER, fg=INK, font=("Segoe UI", self.font_size), spacing3=8)
        self.lesson.pack(fill="both", expand=True)
        self.configure_text_tags()

        self.exercise_choice = ttk.Combobox(practice, state="readonly")
        self.exercise_choice.pack(fill="x")
        self.exercise_choice.bind("<<ComboboxSelected>>", self.change_exercise)
        self.task_label = ttk.Label(practice, wraplength=760, justify="left")
        self.task_label.pack(fill="x", pady=(8, 6))
        practice.bind("<Configure>", lambda event: self.task_label.configure(wraplength=max(300, event.width - 30)))
        self.expected_label = ttk.Label(practice, font=("Segoe UI", 10), foreground=GREEN)
        self.expected_label.pack(anchor="w", pady=(0, 6))
        panes = ttk.Panedwindow(practice, orient="vertical")
        panes.pack(fill="both", expand=True)
        edit_frame = ttk.Frame(panes)
        output_frame = ttk.Frame(panes)
        panes.add(edit_frame, weight=3)
        panes.add(output_frame, weight=2)
        self.editor = ScrolledText(edit_frame, wrap="none", undo=True, bg="#f0f3ed", fg=INK,
                                   insertbackground=INK, font=("Consolas", 12), padx=12, pady=10, height=12)
        self.editor.pack(fill="both", expand=True)
        self.editor.bind("<Tab>", self.insert_tab)
        self.editor.bind("<Return>", self.indent_newline)
        self.editor.bind("<<Modified>>", self.edited)
        self.result = ScrolledText(output_frame, wrap="word", bg="#20332f", fg="#e7eddf",
                                  insertbackground="white", font=("Consolas", 11), padx=12, pady=9, height=7)
        self.result.pack(fill="both", expand=True, pady=(7, 0))
        self.result.configure(state="disabled")

        input_row = ttk.Frame(practice)
        input_row.pack(fill="x", pady=7)
        ttk.Label(input_row, text="Вход для input()\nодно значение на строку", font=("Segoe UI", 9)).pack(side="left", padx=(0, 10))
        self.stdin = tk.Text(input_row, height=2, font=("Consolas", 10), bg="white", relief="solid", bd=1)
        self.stdin.pack(fill="x", expand=True)
        buttons = ttk.Frame(practice)
        buttons.pack(fill="x")
        self.run_button = ttk.Button(buttons, text="▶ Запустить", command=lambda: self.run_code(False), style="Accent.TButton")
        self.run_button.pack(side="left")
        self.check_button = ttk.Button(buttons, text="Проверить вывод", command=lambda: self.run_code(True))
        self.check_button.pack(side="left", padx=5)
        self.stop_button = ttk.Button(buttons, text="Стоп", command=self.runner.stop, state="disabled")
        self.stop_button.pack(side="left")
        ttk.Button(buttons, text="Подсказка", command=self.hint).pack(side="left", padx=5)
        more = ttk.Menubutton(buttons, text="Ещё ▾")
        more_menu = tk.Menu(more, tearoff=False)
        more_menu.add_command(label="Показать решение", command=self.solution)
        more_menu.add_command(label="Вернуть заготовку", command=self.reset_starter)
        more_menu.add_command(label="Сохранить код как .py…", command=self.export_code)
        more["menu"] = more_menu
        more.pack(side="right")
        ttk.Label(practice, text="Ctrl+Enter — запуск · код выполняется локально с доступом к твоим файлам.\nПроверка сравнивает вывод; способ решения оценивай по условию задания.", font=("Segoe UI", 9)).pack(anchor="w", pady=(7, 0))

        ttk.Label(notes, text="Твой блокнот к этой главе. Сохраняется автоматически.").pack(anchor="w", pady=(0, 9))
        self.notes = ScrolledText(notes, wrap="word", font=("Segoe UI", 12), bg="#fffdf6", padx=12, pady=12, undo=True)
        self.notes.pack(fill="both", expand=True)
        bottom = ttk.Frame(main)
        bottom.pack(fill="x", pady=(10, 0))
        self.previous = ttk.Button(bottom, text="← Назад", command=lambda: self.open_day(self.day - 1))
        self.previous.pack(side="left")
        self.complete = ttk.Button(bottom, text="Завершить главу", command=self.toggle_done)
        self.complete.pack(side="left", padx=8)
        self.next_button = ttk.Button(bottom, text="Дальше →", command=lambda: self.open_day(self.day + 1), style="Accent.TButton")
        self.next_button.pack(side="right")
        self.status = tk.StringVar(value="Готово")
        ttk.Label(self, textvariable=self.status, padding=(18, 4), font=("Segoe UI", 9)).pack(fill="x")

    def configure_text_tags(self):
        self.lesson.tag_configure("h1", font=("Segoe UI", self.font_size + 10, "bold"), spacing1=10, spacing3=18)
        self.lesson.tag_configure("h2", font=("Segoe UI", self.font_size + 3, "bold"), foreground=GREEN, spacing1=18, spacing3=8)
        self.lesson.tag_configure("code", font=("Consolas", self.font_size - 1), background="#e9eee5", lmargin1=12, lmargin2=12, spacing3=2)
        self.lesson.tag_configure("copy", font=("Segoe UI", 9, "bold"), foreground=GREEN, spacing1=7)

    def resize_text(self, step):
        self.font_size = max(10, min(22, self.font_size + step))
        self.lesson.configure(font=("Segoe UI", self.font_size))
        self.configure_text_tags()

    def refresh_list(self):
        query = self.search.get().strip().casefold()
        self.chapter_list.delete(0, "end")
        self.search_map = []
        for day, title in enumerate(TITLES, 1):
            if query and query not in (title + self.chapters[day]).casefold():
                continue
            mark = "✓" if day in self.store.state["done"] else "○"
            self.chapter_list.insert("end", f"{mark} {day:02}  {title}")
            self.search_map.append(day)
        if self.day in self.search_map:
            index = self.search_map.index(self.day)
            self.chapter_list.selection_set(index)
            self.chapter_list.see(index)
        count = len(self.store.state["done"])
        self.progress_label.configure(text=f"Пройдено {count} из 30 глав")
        self.progress["value"] = count

    def select_chapter(self, event=None):
        selected = self.chapter_list.curselection()
        if selected:
            self.open_day(self.search_map[selected[0]])

    def remember(self):
        if self.day is None or self.loading:
            return
        page = self.store.page(self.day)
        page.update(draft=self.editor.get("1.0", "end-1c"), input=self.stdin.get("1.0", "end-1c"),
                    notes=self.notes.get("1.0", "end-1c"), exercise=self.exercise_index)
        page.setdefault("drafts", {})[str(self.exercise_index)] = {"code": page["draft"], "input": page["input"]}
        self.store.state["current"] = self.day

    def save_now(self):
        self.remember()
        try:
            self.store.save()
            self.status.set("Код, заметки и прогресс сохранены на этом компьютере")
        except OSError as error:
            self.status.set(f"Не удалось сохранить: {error}. Экспортируй резервную копию через меню «Данные».")

    def autosave(self):
        self.save_now()
        self.after(3000, self.autosave)

    def open_day(self, day):
        if not 1 <= day <= 30 or day == self.day:
            return
        if self.busy:
            self.status.set("Сначала останови текущий запуск")
            self.refresh_list()
            return
        self.remember()
        self.day = day
        self.loading = True
        page = self.store.page(day)
        self.exercise_index = min(page.get("exercise", 0), len(EXERCISES[day]) - 1)
        self.chapter_label.configure(text=f"{day:02} / {TITLES[day - 1]}")
        self.render_lesson()
        self.notes.delete("1.0", "end")
        self.notes.insert("1.0", page.get("notes", ""))
        self.exercise_choice["values"] = [f"{i + 1}. {exercise['title']}" for i, exercise in enumerate(EXERCISES[day])]
        self.exercise_choice.current(self.exercise_index)
        self.set_exercise(page.get("draft"), page.get("input"))
        self.previous.configure(state="normal" if day > 1 else "disabled")
        self.next_button.configure(state="normal" if day < 30 else "disabled")
        self.update_done_button()
        self.loading = False
        self.refresh_list()
        self.save_now()

    def render_lesson(self):
        self.lesson.configure(state="normal")
        self.lesson.delete("1.0", "end")
        self.blocks.clear()
        in_code = False
        code = []
        language = ""
        for line in self.chapters[self.day].splitlines():
            if line.startswith("```"):
                if not in_code:
                    in_code = True
                    language = line[3:].strip()
                    code = []
                else:
                    in_code = False
                    if language == "python":
                        index = len(self.blocks)
                        self.blocks[index] = "\n".join(code) + "\n"
                        tag = f"block_{self.day}_{index}"
                        self.lesson.insert("end", "↗ Открыть этот пример в редакторе\n", ("copy", tag))
                        self.lesson.tag_bind(tag, "<Button-1>", lambda event, i=index: self.load_example(i))
                        self.lesson.tag_bind(tag, "<Enter>", lambda event: self.lesson.configure(cursor="hand2"))
                        self.lesson.tag_bind(tag, "<Leave>", lambda event: self.lesson.configure(cursor="xterm"))
                    self.lesson.insert("end", "\n".join(code) + "\n\n", "code")
                continue
            if in_code:
                code.append(line)
            elif line.startswith("# "):
                self.lesson.insert("end", line[2:] + "\n", "h1")
            elif line.startswith("## "):
                self.lesson.insert("end", line[3:] + "\n", "h2")
            else:
                self.lesson.insert("end", line + "\n")
        self.lesson.configure(state="disabled")
        self.lesson.yview_moveto(0)

    def load_example(self, index):
        if self.busy:
            self.status.set("Сначала останови запуск")
            return
        code = self.blocks[index]
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", code)
        self.notebook.select(1)
        self.show_output("Пример из урока открыт. «Запустить» выполнит его.\nПроверка вывода относится к выбранному заданию, а не к примеру.\n")
        self.save_now()

    def current_exercise(self):
        return EXERCISES[self.day][self.exercise_index]

    def set_exercise(self, draft=None, stdin=None):
        exercise = self.current_exercise()
        self.task_label.configure(text=exercise["task"])
        self.expected_label.configure(text="Ожидаемый вывод: " + exercise["expected"].replace("\n", "  ↵  "))
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", exercise["starter"] if draft is None else draft)
        self.editor.edit_reset()
        self.editor.edit_modified(False)
        self.stdin.delete("1.0", "end")
        self.stdin.insert("1.0", exercise["stdin"] if stdin is None else stdin)
        self.show_output("Напиши решение и нажми «Запустить» или «Проверить вывод».\nПодсказка и готовое решение доступны, если застрял.\n")

    def change_exercise(self, event=None):
        if self.busy:
            self.exercise_choice.current(self.exercise_index)
            return
        new_index = self.exercise_choice.current()
        if new_index == self.exercise_index:
            return
        self.remember()
        self.exercise_index = new_index
        draft = self.store.page(self.day).get("drafts", {}).get(str(new_index), {})
        self.set_exercise(draft.get("code"), draft.get("input"))
        self.save_now()

    def insert_tab(self, event):
        self.editor.insert("insert", "    ")
        return "break"

    def indent_newline(self, event):
        line = self.editor.get("insert linestart", "insert")
        indent = re.match(r" *", line).group()
        if line.rstrip().endswith(":"):
            indent += "    "
        self.editor.insert("insert", "\n" + indent)
        return "break"

    def edited(self, event=None):
        if self.editor.edit_modified():
            self.editor.edit_modified(False)
            if not self.loading:
                self.status.set("Черновик изменён · автосохранение каждые 3 секунды")

    def show_output(self, text):
        self.result.configure(state="normal")
        self.result.delete("1.0", "end")
        self.result.insert("1.0", text)
        self.result.configure(state="disabled")

    def run_code(self, check):
        if self.busy:
            return
        code = self.editor.get("1.0", "end-1c")
        stdin = self.stdin.get("1.0", "end-1c")
        if len(code) > 500_000 or len(stdin.encode("utf-8")) > 32_000:
            messagebox.showerror("Слишком большой ввод", "Максимум 500 тысяч символов кода и 32 КБ входных данных.")
            return
        self.save_now()
        self.busy = True
        self.runner.cancelled.clear()
        self.run_button.configure(state="disabled")
        self.check_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.show_output("Выполняется… Подожди до 8 секунд или нажми «Стоп».\n")
        day, index = self.day, self.exercise_index
        def work():
            result = self.runner.run(code, stdin, reset_cancel=False)
            self.events.put((result, check, day, index))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            result, check, day, index = self.events.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            self.run_button.configure(state="normal")
            self.check_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            output = result["output"]
            report = output + ("\n" if output and not output.endswith("\n") else "")
            if not result["ok"]:
                report += "\n↳ " + result["reason"]
            elif check:
                expected = EXERCISES[day][index]["expected"]
                if output_matches(output, expected):
                    report += "\n✓ Вывод совпал. Проверь также, что использовал приём из условия."
                    passed = self.store.page(day).setdefault("passed", [])
                    if index not in passed:
                        passed.append(index)
                    self.update_done_button()
                    self.save_now()
                else:
                    report += "\nПока не совпало. Ожидалось:\n" + expected + "\n\nПроверь значения, пробелы и лишние строки."
            else:
                report += "\n✓ Программа завершилась" if output else "Код выполнен, вывода нет. Чтобы увидеть результат, используй print()."
            self.show_output(report)
        self.after(100, self.poll)

    def hint(self):
        messagebox.showinfo("Небольшая подсказка", self.current_exercise()["hint"])

    def solution(self):
        window = tk.Toplevel(self)
        window.title("Решение · сначала попробуй объяснить его")
        window.geometry("650x430")
        ttk.Label(window, text="Разбери каждую строку, затем закрой и напиши решение самостоятельно.", wraplength=610, padding=12).pack(fill="x")
        text = ScrolledText(window, font=("Consolas", 12), padx=12, pady=12)
        text.pack(fill="both", expand=True)
        text.insert("1.0", self.current_exercise()["solution"])
        text.configure(state="disabled")

    def reset_starter(self):
        if not self.busy and messagebox.askyesno("Вернуть заготовку", "Заменить текущий код исходной заготовкой этого задания?"):
            self.set_exercise()
            self.save_now()

    def toggle_done(self):
        done = self.store.state["done"]
        if self.day in done:
            done.remove(self.day)
        else:
            done.append(self.day)
        self.update_done_button()
        self.refresh_list()
        self.save_now()

    def update_done_button(self):
        self.complete.configure(text="✓ Глава пройдена · снять отметку" if self.day in self.store.state["done"] else "Завершить главу")
        page = self.store.page(self.day)
        passed = len(set(page.get("passed", [])) & set(range(len(EXERCISES[self.day]))))
        self.status.set(f"Проверено заданий в главе: {passed}/{len(EXERCISES[self.day])}")

    def export_code(self):
        path = filedialog.asksaveasfilename(defaultextension=".py", initialfile=f"lesson_{self.day:02}.py", filetypes=[("Python", "*.py")])
        if path:
            try:
                Path(path).write_text(self.editor.get("1.0", "end-1c"), encoding="utf-8")
            except OSError as error:
                messagebox.showerror("Сохранение", str(error))

    def export_state(self):
        self.remember()
        path = filedialog.asksaveasfilename(defaultextension=".json", initialfile="python-book-backup.json", filetypes=[("JSON", "*.json")])
        if path:
            try:
                Path(path).write_text(json.dumps(self.store.state, ensure_ascii=False, indent=2), encoding="utf-8")
                self.status.set("Резервная копия сохранена")
            except OSError as error:
                messagebox.showerror("Экспорт", str(error))

    def import_state(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            if Path(path).stat().st_size > 64_000_000:
                raise ValueError("Резервная копия слишком большая")
            state = validate_state(json.loads(Path(path).read_text(encoding="utf-8")))
            if not messagebox.askyesno("Восстановление", "Заменить прогресс, код и заметки данными из копии? Текущее состояние будет сохранено в before-import.json."):
                return
            self.remember()
            (self.store.directory / "before-import.json").write_text(json.dumps(self.store.state, ensure_ascii=False, indent=2), encoding="utf-8")
            self.store.state = state
            self.day = None
            self.open_day(state.get("current", 1))
        except (OSError, ValueError) as error:
            messagebox.showerror("Импорт не выполнен", str(error))

    def open_folder(self, path):
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except OSError:
            messagebox.showinfo("Папка", str(path))

    def show_help(self):
        messagebox.showinfo("Как учиться", "1. Выбери главу слева.\n2. Прочитай объяснение. Пример можно открыть в редакторе щелчком по зелёной ссылке.\n3. Реши задание во вкладке «Практика». Для input() заранее заполни входные строки.\n4. «Запустить» показывает результат, «Проверить вывод» сравнивает его с ожидаемым.\n5. Сохраняй свои мысли в заметках и отмечай главы пройденными.\n\nCtrl+Enter — запуск, Ctrl+S — сохранение.\nМеню «Данные» позволяет перенести прогресс на другой компьютер.")

    def about(self):
        messagebox.showinfo("О книге", "Основа: 30 Days Of Python, Asabeneh Yetayeh.\nhttps://github.com/Asabeneh/30-Days-Of-Python\n\nВ этой версии: русская учебная адаптация всех 30 тем и дополнительные задания. Это не полный построчный перевод всех материалов исходника. Английские главы лежат в original, точная версия источника указана в original/SOURCE.json.\n\nПрограмма работает без интернета. Примеры requests, pandas, Flask и MongoDB требуют отдельной установки или сервера; это отмечено в уроках.\nПрогресс хранится локально и автоматически никуда не отправляется.")

    def close(self):
        self.save_now()
        self.runner.stop()
        self.destroy()


if __name__ == "__main__":
    try:
        Book().mainloop()
    except tk.TclError as error:
        print("Не удалось открыть графическое окно. Запусти книгу на компьютере с рабочим столом и Tkinter.", file=sys.stderr)
        print(error, file=sys.stderr)
        sys.exit(1)
