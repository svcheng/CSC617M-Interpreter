from __future__ import annotations

import re
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from language_service import (
    CallStackFrame,
    Diagnostic,
    SymbolScopeView,
    TokenSpan,
    TraceEntry,
    execute_validation,
    validate_source,
)

APP_BG = "#181818"
PANEL_BG = "#252526"
EDITOR_BG = "#1E1E1E"
SIDEBAR_BG = "#2D2D30"
BORDER = "#3C3C3C"
TEXT = "#D4D4D4"
MUTED = "#858585"
ACCENT = "#0E639C"
ACCENT_ACTIVE = "#1177BB"
KEYWORD = "#569CD6"
TYPE = "#4EC9B0"
LITERAL = "#B5CEA8"
IDENTIFIER = "#9CDCFE"
OPERATOR = "#D4D4D4"
ERROR = "#F48771"
ERROR_BG = "#3A1F23"
SUCCESS = "#6A9955"

EDITOR_FONT = ("Consolas", 11)
UI_FONT = ("Segoe UI", 10)
HEADER_FONT = ("Segoe UI Semibold", 10)
TITLE_FONT = ("Segoe UI Semibold", 11)
STARTER_TEMPLATE = "main: {\n    \n}\n"
WATCH_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z_]\w*")
SOURCE_FILETYPES = [
    ("C-cured source files", "*.txt"),
    ("All files", "*.*"),
]


def format_runtime_value(value):
    return repr(value)


def shorten_text(value: str, max_length: int = 44):
    if len(value) <= max_length:
        return value
    return value[: max_length - 3] + "..."


def evaluate_watch_expression(expression: str, snapshot: dict[str, object]):
    expr = "".join(expression.split())
    if not expr:
        raise ValueError("empty watch expression")

    match = WATCH_IDENTIFIER_PATTERN.match(expr)
    if match is None:
        raise ValueError("watch expression must start with an identifier")

    name = match.group(0)
    if name not in snapshot:
        raise NameError(f'"{name}" is not in scope')

    value = snapshot[name]
    cursor = match.end()

    while cursor < len(expr):
        token = expr[cursor]
        if token == ".":
            cursor += 1
            field_match = WATCH_IDENTIFIER_PATTERN.match(expr, cursor)
            if field_match is None:
                raise ValueError("expected field name after '.'")
            field_name = field_match.group(0)
            if not isinstance(value, dict):
                raise TypeError(f'cannot read field "{field_name}" from {type(value).__name__}')
            if field_name not in value:
                raise KeyError(f'field "{field_name}" does not exist')
            value = value[field_name]
            cursor = field_match.end()
            continue

        if token == "[":
            close_index = expr.find("]", cursor)
            if close_index == -1:
                raise ValueError("missing closing ']'")
            index_text = expr[cursor + 1 : close_index]
            if not index_text:
                raise ValueError("missing array index")
            try:
                index_value = int(index_text)
            except ValueError as error:
                raise ValueError("array indices must be integers") from error
            if not isinstance(value, list):
                raise TypeError(f"cannot index into {type(value).__name__}")
            value = value[index_value]
            cursor = close_index + 1
            continue

        raise ValueError(f'unexpected token "{token}"')

    return value


class HoverTooltip:
    def __init__(self, widget):
        self.widget = widget
        self.window: tk.Toplevel | None = None
        self.label: tk.Label | None = None
        self.message = ""

    def show(self, x: int, y: int, message: str):
        if self.window is None:
            self.window = tk.Toplevel(self.widget)
            self.window.overrideredirect(True)
            self.window.configure(bg=BORDER)
            self.window.wm_attributes("-topmost", True)
            self.label = tk.Label(
                self.window,
                bg=PANEL_BG,
                fg=TEXT,
                font=UI_FONT,
                justify="left",
                padx=8,
                pady=6,
                wraplength=420,
            )
            self.label.pack()

        if self.label is not None:
            self.label.configure(text=message)

        self.message = message
        self.window.geometry(f"+{x}+{y}")
        self.window.deiconify()

    def hide(self):
        if self.window is not None:
            self.window.withdraw()
        self.message = ""


class CodeEditor(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=EDITOR_BG)
        self._change_callback = None
        self._tooltip_messages: dict[str, str] = {}
        self._diagnostic_tags: list[str] = []
        self.tooltip = HoverTooltip(self)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.line_numbers = tk.Canvas(
            self,
            width=56,
            bg=PANEL_BG,
            highlightthickness=0,
            bd=0,
        )
        self.line_numbers.grid(row=0, column=0, sticky="ns")

        self.text = tk.Text(
            self,
            wrap="none",
            undo=True,
            bg=EDITOR_BG,
            fg=TEXT,
            insertbackground=TEXT,
            selectbackground="#264F78",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=12,
            pady=10,
            font=EDITOR_FONT,
            tabs=("32",),
        )
        self.text.grid(row=0, column=1, sticky="nsew")

        self.v_scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._on_scrollbar)
        self.v_scrollbar.grid(row=0, column=2, sticky="ns")

        self.h_scrollbar = ttk.Scrollbar(
            self, orient="horizontal", command=self.text.xview
        )
        self.h_scrollbar.grid(row=1, column=1, sticky="ew")

        self.text.configure(
            yscrollcommand=self._on_text_scroll,
            xscrollcommand=self.h_scrollbar.set,
        )

        self._configure_tags()
        self._bind_events()
        self.text.edit_modified(False)

    def _configure_tags(self):
        self.text.tag_configure("current_step", background="#2A2D2E")
        self.text.tag_configure("tok_keyword", foreground=KEYWORD)
        self.text.tag_configure("tok_type", foreground=TYPE)
        self.text.tag_configure("tok_literal", foreground=LITERAL)
        self.text.tag_configure("tok_identifier", foreground=IDENTIFIER)
        self.text.tag_configure("tok_operator", foreground=OPERATOR)
        self.text.tag_configure("tok_punctuation", foreground=MUTED)
        self.text.tag_configure("tok_invalid", foreground=ERROR)

    def _bind_events(self):
        self.text.bind("<<Modified>>", self._on_modified)
        self.text.bind("<Configure>", lambda _event: self.redraw_line_numbers())
        self.text.bind("<MouseWheel>", lambda _event: self.redraw_line_numbers())
        self.text.bind("<ButtonRelease-1>", lambda _event: self.redraw_line_numbers())
        self.text.bind("<KeyRelease>", lambda _event: self.redraw_line_numbers())
        self.text.bind("<Motion>", self._on_hover)
        self.text.bind("<Leave>", lambda _event: self.tooltip.hide())

    def _on_modified(self, _event=None):
        if not self.text.edit_modified():
            return
        self.text.edit_modified(False)
        self.redraw_line_numbers()
        if self._change_callback is not None:
            self._change_callback()

    def _on_text_scroll(self, first, last):
        self.v_scrollbar.set(first, last)
        self.redraw_line_numbers()

    def _on_scrollbar(self, *args):
        self.text.yview(*args)
        self.redraw_line_numbers()

    def _on_hover(self, event):
        index = self.text.index(f"@{event.x},{event.y}")
        messages = []
        for tag in self.text.tag_names(index):
            if tag in self._tooltip_messages:
                message = self._tooltip_messages[tag]
                if message not in messages:
                    messages.append(message)

        if messages:
            self.tooltip.show(
                event.x_root + 16,
                event.y_root + 16,
                "\n\n".join(messages),
            )
        else:
            self.tooltip.hide()

    def set_change_callback(self, callback):
        self._change_callback = callback

    def get_text(self):
        return self.text.get("1.0", "end-1c")

    def set_text(self, value: str):
        self.text.delete("1.0", "end")
        self.text.insert("1.0", value)
        self.text.edit_modified(False)
        self.redraw_line_numbers()

    def redraw_line_numbers(self):
        self.line_numbers.delete("all")
        last_line = max(1, int(self.text.index("end-1c").split(".")[0]))
        digits = len(str(last_line))
        gutter_width = max(48, 16 + digits * 10)
        self.line_numbers.configure(width=gutter_width)

        index = self.text.index("@0,0")
        while True:
            line_info = self.text.dlineinfo(index)
            if line_info is None:
                break
            y = line_info[1]
            line_number = index.split(".")[0]
            self.line_numbers.create_text(
                gutter_width - 10,
                y,
                anchor="ne",
                text=line_number,
                fill=MUTED,
                font=EDITOR_FONT,
            )
            index = self.text.index(f"{index}+1line")

    def _clamp_line(self, line: int):
        last_line = max(1, int(self.text.index("end-1c").split(".")[0]))
        return min(max(line, 1), last_line)

    def _span_to_indices(
        self,
        start_line: int,
        end_line: int,
        start_col: int,
        end_col: int,
    ):
        start_index = f"{self._clamp_line(start_line)}.{max(start_col - 1, 0)}"
        end_index = f"{self._clamp_line(end_line)}.{max(end_col - 1, 0)}"

        if self.text.compare(end_index, "<=", start_index):
            line_end = self.text.index(f"{start_index} lineend")
            if self.text.compare(line_end, ">", start_index):
                end_index = line_end
            else:
                end_index = self.text.index(f"{start_index}+1c")

        return start_index, end_index

    def apply_highlighting(self, tokens: list[TokenSpan]):
        for tag in (
            "tok_keyword",
            "tok_type",
            "tok_literal",
            "tok_identifier",
            "tok_operator",
            "tok_punctuation",
            "tok_invalid",
        ):
            self.text.tag_remove(tag, "1.0", "end")

        for token in tokens:
            if token.category == "text":
                continue
            tag = f"tok_{token.category}"
            start_index, end_index = self._span_to_indices(
                token.start_line,
                token.end_line,
                token.start_col,
                token.end_col,
            )
            self.text.tag_add(tag, start_index, end_index)

    def apply_diagnostics(self, diagnostics: list[Diagnostic]):
        for tag in self._diagnostic_tags:
            self.text.tag_delete(tag)
        self._diagnostic_tags.clear()
        self._tooltip_messages.clear()
        self.tooltip.hide()

        for index, diagnostic in enumerate(diagnostics):
            tag = f"diag_{index}"
            start_index, end_index = self._span_to_indices(
                diagnostic.start_line,
                diagnostic.end_line,
                diagnostic.start_col,
                diagnostic.end_col,
            )
            self.text.tag_configure(
                tag,
                underline=1,
                foreground=ERROR,
                background=ERROR_BG,
            )
            self.text.tag_add(tag, start_index, end_index)
            self.text.tag_raise(tag)
            self._diagnostic_tags.append(tag)
            self._tooltip_messages[tag] = diagnostic.message

    def clear_execution_highlight(self):
        self.text.tag_remove("current_step", "1.0", "end")

    def highlight_execution_span(
        self,
        start_line: int | None,
        end_line: int | None,
        start_col: int | None,
        end_col: int | None,
    ):
        self.clear_execution_highlight()
        if start_line is None or end_line is None or start_col is None or end_col is None:
            return

        start_index, end_index = self._span_to_indices(
            start_line,
            end_line,
            start_col,
            end_col,
        )
        self.text.tag_add("current_step", start_index, end_index)
        self.text.see(start_index)


class IDEApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("C-cured IDE")
        self.root.geometry("1480x920")
        self.root.minsize(1120, 720)
        self.root.configure(bg=APP_BG)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.validation_job = None
        self.current_validation = None
        self.current_file_path: Path | None = None
        self.is_dirty = False
        self._suppress_editor_change = False
        self.watch_expressions: list[str] = []
        self.watch_counter = 0
        self.trace_entries: list[TraceEntry] = []
        self.symbol_scopes: list[SymbolScopeView] = []
        self.current_trace_index: int | None = None
        self._syncing_trace_selection = False
        self.is_running = False
        self.awaiting_runtime_input = False
        self.runtime_input_request = 0
        self.runtime_input_signal = tk.IntVar(value=0)
        self.pending_runtime_input: list[str] = []
        self.current_input_target: str | None = None
        self.show_inspection_var = tk.BooleanVar(value=True)
        self.show_call_stack_var = tk.BooleanVar(value=True)
        self.show_timeline_var = tk.BooleanVar(value=True)
        self.sidebar_panels: dict[str, tk.Frame] = {}
        self.sidebar_panel_weights = {
            "inspection": 2,
            "call_stack": 1,
            "timeline": 2,
        }

        self._configure_styles()
        self._build_menu()
        self._build_toolbar()
        self._build_main_layout()
        self._bind_shortcuts()

        self.editor.set_change_callback(self._on_editor_changed)
        self._load_document(STARTER_TEMPLATE, None)
        self.editor.text.focus_set()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_menu(self):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New", command=self.new_file, accelerator="Ctrl+N")
        file_menu.add_command(label="Open...", command=self.open_file, accelerator="Ctrl+O")
        file_menu.add_command(label="Save", command=self.save_file, accelerator="Ctrl+S")
        file_menu.add_command(
            label="Save As...",
            command=self.save_file_as,
            accelerator="Ctrl+Shift+S",
        )
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_checkbutton(
            label="Inspection",
            variable=self.show_inspection_var,
            command=self._update_sidebar_layout,
        )
        view_menu.add_checkbutton(
            label="Call Stack",
            variable=self.show_call_stack_var,
            command=self._update_sidebar_layout,
        )
        view_menu.add_checkbutton(
            label="Execution Timeline",
            variable=self.show_timeline_var,
            command=self._update_sidebar_layout,
        )

        menubar.add_cascade(label="File", menu=file_menu)
        menubar.add_cascade(label="View", menu=view_menu)
        self.root.config(menu=menubar)

    def _update_window_title(self):
        document_name = (
            self.current_file_path.name if self.current_file_path is not None else "Untitled"
        )
        dirty_marker = "*" if self.is_dirty else ""
        self.root.title(f"{dirty_marker}{document_name} - C-cured IDE")

    def _set_dirty(self, is_dirty: bool):
        self.is_dirty = is_dirty
        self._update_window_title()

    def _configure_styles(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "Treeview",
            background=PANEL_BG,
            fieldbackground=PANEL_BG,
            foreground=TEXT,
            bordercolor=BORDER,
            rowheight=24,
            relief="flat",
        )
        style.map(
            "Treeview",
            background=[("selected", ACCENT)],
            foreground=[("selected", "#FFFFFF")],
        )
        style.configure(
            "Treeview.Heading",
            background=SIDEBAR_BG,
            foreground=TEXT,
            bordercolor=BORDER,
            relief="flat",
            font=HEADER_FONT,
        )
        style.configure(
            "Sidebar.TNotebook",
            background=PANEL_BG,
            borderwidth=0,
            tabmargins=(0, 0, 0, 0),
        )
        style.configure(
            "Sidebar.TNotebook.Tab",
            background=SIDEBAR_BG,
            foreground=TEXT,
            padding=(12, 6),
            borderwidth=0,
            font=HEADER_FONT,
        )
        style.map(
            "Sidebar.TNotebook.Tab",
            background=[("selected", PANEL_BG), ("active", BORDER)],
            foreground=[("selected", TEXT), ("active", TEXT)],
        )
        style.configure(
            "Vertical.TScrollbar",
            gripcount=0,
            background=SIDEBAR_BG,
            darkcolor=SIDEBAR_BG,
            lightcolor=SIDEBAR_BG,
            troughcolor=EDITOR_BG,
            bordercolor=EDITOR_BG,
            arrowcolor=TEXT,
        )
        style.configure(
            "Horizontal.TScrollbar",
            gripcount=0,
            background=SIDEBAR_BG,
            darkcolor=SIDEBAR_BG,
            lightcolor=SIDEBAR_BG,
            troughcolor=EDITOR_BG,
            bordercolor=EDITOR_BG,
            arrowcolor=TEXT,
        )

    def _build_toolbar(self):
        toolbar = tk.Frame(self.root, bg=SIDEBAR_BG, height=52)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.grid_columnconfigure(8, weight=1)
        toolbar.grid_propagate(False)

        title = tk.Label(
            toolbar,
            text="C-cured IDE",
            bg=SIDEBAR_BG,
            fg=TEXT,
            font=TITLE_FONT,
        )
        title.grid(row=0, column=0, padx=(16, 14), pady=10, sticky="w")

        self.new_button = tk.Button(
            toolbar,
            text="New",
            command=self.new_file,
            bg=BORDER,
            fg=TEXT,
            activebackground="#4A4A4A",
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            padx=10,
            pady=6,
            font=HEADER_FONT,
            cursor="hand2",
        )
        self.new_button.grid(row=0, column=1, padx=(0, 6), pady=10, sticky="w")

        self.open_button = tk.Button(
            toolbar,
            text="Open",
            command=self.open_file,
            bg=BORDER,
            fg=TEXT,
            activebackground="#4A4A4A",
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            padx=10,
            pady=6,
            font=HEADER_FONT,
            cursor="hand2",
        )
        self.open_button.grid(row=0, column=2, padx=(0, 6), pady=10, sticky="w")

        self.save_button = tk.Button(
            toolbar,
            text="Save",
            command=self.save_file,
            bg=BORDER,
            fg=TEXT,
            activebackground="#4A4A4A",
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            padx=10,
            pady=6,
            font=HEADER_FONT,
            cursor="hand2",
        )
        self.save_button.grid(row=0, column=3, padx=(0, 10), pady=10, sticky="w")

        self.run_button = tk.Button(
            toolbar,
            text="Run",
            command=self.run_program,
            bg=ACCENT,
            fg="#FFFFFF",
            activebackground=ACCENT_ACTIVE,
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            padx=14,
            pady=6,
            font=HEADER_FONT,
            cursor="hand2",
        )
        self.run_button.grid(row=0, column=4, pady=10, sticky="w")

        self.prev_button = tk.Button(
            toolbar,
            text="Prev",
            command=self.step_previous,
            state="disabled",
            bg=BORDER,
            fg=TEXT,
            activebackground="#4A4A4A",
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            padx=12,
            pady=6,
            font=HEADER_FONT,
            cursor="hand2",
        )
        self.prev_button.grid(row=0, column=5, padx=(10, 6), pady=10, sticky="w")

        self.next_button = tk.Button(
            toolbar,
            text="Next",
            command=self.step_next,
            state="disabled",
            bg=BORDER,
            fg=TEXT,
            activebackground="#4A4A4A",
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            padx=12,
            pady=6,
            font=HEADER_FONT,
            cursor="hand2",
        )
        self.next_button.grid(row=0, column=6, padx=(0, 10), pady=10, sticky="w")

        self.step_label = tk.Label(
            toolbar,
            text="No Timeline",
            bg=SIDEBAR_BG,
            fg=MUTED,
            font=UI_FONT,
        )
        self.step_label.grid(row=0, column=7, padx=(0, 16), pady=10, sticky="w")

        self.status_label = tk.Label(
            toolbar,
            text="Ready",
            bg=SIDEBAR_BG,
            fg=MUTED,
            font=UI_FONT,
        )
        self.status_label.grid(row=0, column=8, padx=(16, 18), pady=10, sticky="e")

    def _build_main_layout(self):
        self.main_layout = tk.Frame(self.root, bg=APP_BG)
        self.main_layout.grid(row=1, column=0, sticky="nsew", padx=12, pady=(12, 12))
        self.main_layout.grid_rowconfigure(0, weight=1)
        self.main_layout.grid_columnconfigure(0, weight=4)
        self.main_layout.grid_columnconfigure(1, weight=2, minsize=330)

        self.editor_panel, editor_body = self._create_panel(self.main_layout, "Editor")
        self.editor_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        editor_body.grid_rowconfigure(0, weight=1)
        editor_body.grid_columnconfigure(0, weight=1)

        self.editor = CodeEditor(editor_body)
        self.editor.grid(row=0, column=0, sticky="nsew")

        self.sidebar = tk.Frame(self.main_layout, bg=APP_BG)
        self.sidebar.grid(row=0, column=1, sticky="nsew")
        self.sidebar.grid_columnconfigure(0, weight=1)

        inspector_panel, inspector_body = self._create_panel(self.sidebar, "Inspection")
        inspector_body.grid_rowconfigure(0, weight=1)
        inspector_body.grid_columnconfigure(0, weight=1)

        inspector_tabs = ttk.Notebook(inspector_body, style="Sidebar.TNotebook")
        inspector_tabs.grid(row=0, column=0, sticky="nsew")

        watch_tab = tk.Frame(inspector_tabs, bg=PANEL_BG)
        symbol_tab = tk.Frame(inspector_tabs, bg=PANEL_BG)
        inspector_tabs.add(watch_tab, text="Value Inspector")
        inspector_tabs.add(symbol_tab, text="Symbol Table")

        self._build_watch_panel(watch_tab)
        self._build_symbol_panel(symbol_tab)
        self.sidebar_panels["inspection"] = inspector_panel

        stack_panel, stack_body = self._create_panel(self.sidebar, "Call Stack")
        self._build_call_stack_panel(stack_body)
        self.sidebar_panels["call_stack"] = stack_panel

        trace_panel, trace_body = self._create_panel(self.sidebar, "Execution Timeline")
        self._build_trace_panel(trace_body)
        self.sidebar_panels["timeline"] = trace_panel
        self._update_sidebar_layout()

        console_panel, console_body = self._create_panel(
            self.root, "Output Console", height=190
        )
        console_panel.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
        self._build_console_panel(console_body)

    def _update_sidebar_layout(self):
        if not hasattr(self, "sidebar"):
            return

        for row in range(len(self.sidebar_panel_weights)):
            self.sidebar.grid_rowconfigure(row, weight=0)

        for panel in self.sidebar_panels.values():
            panel.grid_forget()

        visible_panels = []
        if self.show_inspection_var.get() and self.sidebar_panels.get("inspection") is not None:
            visible_panels.append(("inspection", self.sidebar_panels["inspection"]))
        if self.show_call_stack_var.get() and self.sidebar_panels.get("call_stack") is not None:
            visible_panels.append(("call_stack", self.sidebar_panels["call_stack"]))
        if self.show_timeline_var.get() and self.sidebar_panels.get("timeline") is not None:
            visible_panels.append(("timeline", self.sidebar_panels["timeline"]))

        if not visible_panels:
            self.sidebar.grid_remove()
            self.main_layout.grid_columnconfigure(1, weight=0, minsize=0)
            self.editor_panel.grid_configure(padx=(0, 0))
            return

        self.sidebar.grid()
        self.main_layout.grid_columnconfigure(1, weight=2, minsize=330)
        self.editor_panel.grid_configure(padx=(0, 12))

        for row_index, (panel_key, panel) in enumerate(visible_panels):
            self.sidebar.grid_rowconfigure(
                row_index,
                weight=self.sidebar_panel_weights[panel_key],
            )
            panel.grid(
                row=row_index,
                column=0,
                sticky="nsew",
                pady=(0, 6) if row_index < len(visible_panels) - 1 else (0, 0),
            )

    def _create_panel(self, parent, title: str, height: int | None = None):
        panel = tk.Frame(
            parent,
            bg=PANEL_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
            bd=0,
        )
        if height is not None:
            panel.configure(height=height)
            panel.grid_propagate(False)

        panel.grid_rowconfigure(1, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        header = tk.Label(
            panel,
            text=title,
            bg=SIDEBAR_BG,
            fg=TEXT,
            font=HEADER_FONT,
            anchor="w",
            padx=10,
            pady=8,
        )
        header.grid(row=0, column=0, sticky="ew")

        body = tk.Frame(panel, bg=PANEL_BG)
        body.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)

        return panel, body

    def _build_readonly_text(self, parent, wrap="none"):
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        text = tk.Text(
            parent,
            wrap=wrap,
            bg=EDITOR_BG,
            fg=TEXT,
            relief="flat",
            bd=0,
            highlightthickness=0,
            insertbackground=TEXT,
            font=EDITOR_FONT,
            padx=10,
            pady=10,
            state="disabled",
        )
        text.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        text.configure(yscrollcommand=scrollbar.set)

        return text

    def _build_console_panel(self, parent):
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        output_frame = tk.Frame(parent, bg=PANEL_BG)
        output_frame.grid(row=0, column=0, sticky="nsew")
        self.console_output = self._build_readonly_text(output_frame, wrap="word")

        input_bar = tk.Frame(parent, bg=PANEL_BG)
        input_bar.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        input_bar.grid_columnconfigure(1, weight=1)

        self.console_prompt_label = tk.Label(
            input_bar,
            text=">",
            bg=PANEL_BG,
            fg=MUTED,
            font=HEADER_FONT,
            anchor="w",
            width=3,
        )
        self.console_prompt_label.grid(row=0, column=0, sticky="w", padx=(0, 8))

        self.console_input = tk.Entry(
            input_bar,
            bg=EDITOR_BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            disabledbackground=EDITOR_BG,
            disabledforeground=MUTED,
            font=UI_FONT,
            state="disabled",
        )
        self.console_input.grid(row=0, column=1, sticky="ew", ipady=6)
        self.console_input.bind("<Return>", self.submit_console_input)

        self.console_submit_button = tk.Button(
            input_bar,
            text="Enter",
            command=self.submit_console_input,
            state="disabled",
            bg=BORDER,
            fg=TEXT,
            activebackground="#4A4A4A",
            activeforeground=TEXT,
            disabledforeground=MUTED,
            relief="flat",
            bd=0,
            padx=10,
            pady=5,
            font=UI_FONT,
            cursor="hand2",
        )
        self.console_submit_button.grid(row=0, column=2, padx=(8, 0))

    def _build_watch_panel(self, parent):
        parent.grid_rowconfigure(1, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        controls = tk.Frame(parent, bg=PANEL_BG)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        controls.grid_columnconfigure(0, weight=1)

        self.watch_entry = tk.Entry(
            controls,
            bg=EDITOR_BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            font=UI_FONT,
        )
        self.watch_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8), ipady=6)
        self.watch_entry.bind("<Return>", self.add_watch)

        add_button = tk.Button(
            controls,
            text="Add",
            command=self.add_watch,
            bg=ACCENT,
            fg="#FFFFFF",
            activebackground=ACCENT_ACTIVE,
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            padx=10,
            pady=5,
            font=UI_FONT,
            cursor="hand2",
        )
        add_button.grid(row=0, column=1, padx=(0, 8))

        remove_button = tk.Button(
            controls,
            text="Remove",
            command=self.remove_selected_watch,
            bg=BORDER,
            fg=TEXT,
            activebackground="#4A4A4A",
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            padx=10,
            pady=5,
            font=UI_FONT,
            cursor="hand2",
        )
        remove_button.grid(row=0, column=2)

        tree_frame = tk.Frame(parent, bg=PANEL_BG)
        tree_frame.grid(row=1, column=0, sticky="nsew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.watch_tree = ttk.Treeview(
            tree_frame,
            columns=("name", "value"),
            show="headings",
        )
        self.watch_tree.heading("name", text="Expression")
        self.watch_tree.heading("value", text="Value Before Step")
        self.watch_tree.column("name", width=150, anchor="w")
        self.watch_tree.column("value", width=180, anchor="w")
        self.watch_tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self.watch_tree.yview
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.watch_tree.configure(yscrollcommand=scrollbar.set)

    def _build_symbol_panel(self, parent):
        parent.grid_rowconfigure(1, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        self.symbol_summary_label = tk.Label(
            parent,
            text="No symbols available",
            bg=PANEL_BG,
            fg=MUTED,
            font=UI_FONT,
            anchor="w",
        )
        self.symbol_summary_label.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        tree_frame = tk.Frame(parent, bg=PANEL_BG)
        tree_frame.grid(row=1, column=0, sticky="nsew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.symbol_tree = ttk.Treeview(
            tree_frame,
            columns=("kind", "type", "details", "line"),
            show="tree headings",
        )
        self.symbol_tree.heading("#0", text="Name / Scope")
        self.symbol_tree.heading("kind", text="Kind")
        self.symbol_tree.heading("type", text="Type")
        self.symbol_tree.heading("details", text="Details")
        self.symbol_tree.heading("line", text="Line")
        self.symbol_tree.column("#0", width=180, anchor="w")
        self.symbol_tree.column("kind", width=92, anchor="w", stretch=False)
        self.symbol_tree.column("type", width=120, anchor="w", stretch=False)
        self.symbol_tree.column("details", width=240, anchor="w")
        self.symbol_tree.column("line", width=58, anchor="center", stretch=False)
        self.symbol_tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self.symbol_tree.yview
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.symbol_tree.configure(yscrollcommand=scrollbar.set)

    def _build_call_stack_panel(self, parent):
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        tree_frame = tk.Frame(parent, bg=PANEL_BG)
        tree_frame.grid(row=0, column=0, sticky="nsew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.call_stack_tree = ttk.Treeview(
            tree_frame,
            columns=("frame", "locals"),
            show="headings",
        )
        self.call_stack_tree.heading("frame", text="Frame")
        self.call_stack_tree.heading("locals", text="Local Bindings")
        self.call_stack_tree.column("frame", width=110, anchor="w", stretch=False)
        self.call_stack_tree.column("locals", width=260, anchor="w")
        self.call_stack_tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self.call_stack_tree.yview
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.call_stack_tree.configure(yscrollcommand=scrollbar.set)

    def _build_trace_panel(self, parent):
        parent.grid_rowconfigure(1, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        controls = tk.Frame(parent, bg=PANEL_BG)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        controls.grid_columnconfigure(2, weight=1)

        self.trace_prev_button = tk.Button(
            controls,
            text="Prev",
            command=self.step_previous,
            state="disabled",
            bg=BORDER,
            fg=TEXT,
            activebackground="#4A4A4A",
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            padx=10,
            pady=5,
            font=UI_FONT,
            cursor="hand2",
        )
        self.trace_prev_button.grid(row=0, column=0, padx=(0, 8))

        self.trace_next_button = tk.Button(
            controls,
            text="Next",
            command=self.step_next,
            state="disabled",
            bg=BORDER,
            fg=TEXT,
            activebackground="#4A4A4A",
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            padx=10,
            pady=5,
            font=UI_FONT,
            cursor="hand2",
        )
        self.trace_next_button.grid(row=0, column=1)

        self.trace_summary_label = tk.Label(
            controls,
            text="No timeline loaded",
            bg=PANEL_BG,
            fg=MUTED,
            font=UI_FONT,
            anchor="e",
        )
        self.trace_summary_label.grid(row=0, column=2, sticky="e")

        tree_frame = tk.Frame(parent, bg=PANEL_BG)
        tree_frame.grid(row=1, column=0, sticky="nsew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.trace_tree = ttk.Treeview(
            tree_frame,
            columns=("step", "line", "statement", "result"),
            show="headings",
        )
        self.trace_tree.heading("step", text="Step")
        self.trace_tree.heading("line", text="Line")
        self.trace_tree.heading("statement", text="Statement")
        self.trace_tree.heading("result", text="Effect")
        self.trace_tree.column("step", width=58, anchor="center", stretch=False)
        self.trace_tree.column("line", width=58, anchor="center", stretch=False)
        self.trace_tree.column("statement", width=190, anchor="w")
        self.trace_tree.column("result", width=240, anchor="w")
        self.trace_tree.grid(row=0, column=0, sticky="nsew")
        self.trace_tree.bind("<<TreeviewSelect>>", self._on_trace_select)

        scrollbar = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self.trace_tree.yview
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.trace_tree.configure(yscrollcommand=scrollbar.set)

    def _bind_shortcuts(self):
        self.root.bind("<F5>", self.run_program)
        self.root.bind("<Control-r>", self.run_program)
        self.root.bind("<Control-n>", self.new_file)
        self.root.bind("<Control-o>", self.open_file)
        self.root.bind("<Control-s>", self.save_file)
        self.root.bind("<Control-Shift-s>", self.save_file_as)
        self.root.bind("<Control-S>", self.save_file_as)

    def _set_status(self, text: str, color: str = MUTED):
        self.status_label.configure(text=text, fg=color)

    def _format_locals_preview(self, values: dict[str, object], limit: int = 3):
        if not values:
            return "<no locals>"

        preview_parts = []
        for index, (name, value) in enumerate(values.items()):
            if index >= limit:
                preview_parts.append("...")
                break
            preview_parts.append(f"{name}={shorten_text(format_runtime_value(value), 28)}")
        return ", ".join(preview_parts)

    def _clear_symbol_table(self, summary: str = "No symbols available"):
        self.symbol_scopes = []
        if not hasattr(self, "symbol_tree"):
            return

        for item in self.symbol_tree.get_children():
            self.symbol_tree.delete(item)
        self.symbol_summary_label.configure(text=summary, fg=MUTED)

    def _populate_symbol_table(self, scopes: list[SymbolScopeView]):
        self._clear_symbol_table()
        self.symbol_scopes = list(scopes)

        if not scopes:
            self.symbol_summary_label.configure(text="No symbols declared", fg=MUTED)
            return

        symbol_count = 0
        for scope_index, scope_view in enumerate(scopes):
            scope_id = f"scope_{scope_index}"
            scope_count = len(scope_view.entries)
            scope_summary = (
                f"{scope_count} symbol" if scope_count == 1 else f"{scope_count} symbols"
            )
            self.symbol_tree.insert(
                "",
                "end",
                iid=scope_id,
                text=scope_view.label,
                values=(scope_view.kind.title(), "", scope_summary, ""),
                open=True,
            )

            for entry_index, entry in enumerate(scope_view.entries):
                symbol_count += 1
                self.symbol_tree.insert(
                    scope_id,
                    "end",
                    iid=f"{scope_id}_entry_{entry_index}",
                    text=entry.name,
                    values=(
                        entry.kind.title(),
                        entry.type_name,
                        entry.details,
                        entry.line if entry.line is not None else "",
                    ),
                )

        if symbol_count == 0:
            self.symbol_summary_label.configure(text="No symbols declared", fg=MUTED)
            return

        scope_count = len(scopes)
        symbol_suffix = "" if symbol_count == 1 else "s"
        scope_suffix = "" if scope_count == 1 else "s"
        self.symbol_summary_label.configure(
            text=f"{symbol_count} symbol{symbol_suffix} across {scope_count} scope{scope_suffix}",
            fg=MUTED,
        )

    def _clear_call_stack(self):
        if not hasattr(self, "call_stack_tree"):
            return
        for item in self.call_stack_tree.get_children():
            self.call_stack_tree.delete(item)

    def _update_call_stack(self, frames: list[CallStackFrame] | None):
        self._clear_call_stack()
        if not frames:
            return

        for index, frame_info in enumerate(frames):
            label = frame_info.name if index > 0 else f"{frame_info.name} (current)"
            self.call_stack_tree.insert(
                "",
                "end",
                iid=f"stack_{index}",
                values=(label, self._format_locals_preview(frame_info.locals)),
            )

    def _set_toolbar_busy(self, is_busy: bool):
        button_state = "disabled" if is_busy else "normal"
        self.run_button.configure(state=button_state, bg=ACCENT_ACTIVE if is_busy else ACCENT)
        self.new_button.configure(state=button_state)
        self.open_button.configure(state=button_state)
        self.save_button.configure(state=button_state)

    def _load_document(self, content: str, file_path: Path | None):
        self._suppress_editor_change = True
        try:
            self.editor.set_text(content)
        finally:
            self._suppress_editor_change = False

        self.current_file_path = file_path
        self._clear_trace_entries()
        self._reset_watch_values("<not run>")
        self.current_validation = self.refresh_validation()
        self._set_dirty(False)

    def _confirm_discard_changes(self):
        if not self.is_dirty:
            return True

        answer = messagebox.askyesnocancel(
            "Unsaved Changes",
            "Save your changes before continuing?",
            parent=self.root,
        )
        if answer is None:
            return False
        if answer:
            return bool(self.save_file())
        return True

    def _write_file(self, target_path: Path):
        target_path.write_text(self.editor.get_text(), encoding="utf-8")
        self.current_file_path = target_path
        self._set_dirty(False)
        self._set_status(f"Saved {target_path.name}", SUCCESS)
        return True

    def new_file(self, _event=None):
        if not self._confirm_discard_changes():
            return "break"
        self._load_document(STARTER_TEMPLATE, None)
        self._set_status("Created a new file", MUTED)
        return "break"

    def open_file(self, _event=None):
        if not self._confirm_discard_changes():
            return "break"

        selected_path = filedialog.askopenfilename(
            title="Open Source File",
            filetypes=SOURCE_FILETYPES,
            initialdir=str(
                self.current_file_path.parent
                if self.current_file_path is not None
                else Path.cwd()
            ),
        )
        if not selected_path:
            return "break"

        path = Path(selected_path)
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as error:
            messagebox.showerror("Open Failed", str(error), parent=self.root)
            return "break"

        self._load_document(content, path)
        self._set_status(f"Opened {path.name}", MUTED)
        return "break"

    def save_file(self, _event=None):
        if self.current_file_path is None:
            result = self.save_file_as()
            return "break" if _event is not None else result

        try:
            result = self._write_file(self.current_file_path)
        except OSError as error:
            messagebox.showerror("Save Failed", str(error), parent=self.root)
            result = False
        return "break" if _event is not None else result

    def save_file_as(self, _event=None):
        selected_path = filedialog.asksaveasfilename(
            title="Save Source File",
            defaultextension=".txt",
            filetypes=SOURCE_FILETYPES,
            initialdir=str(
                self.current_file_path.parent
                if self.current_file_path is not None
                else Path.cwd()
            ),
            initialfile=(
                self.current_file_path.name if self.current_file_path is not None else "program.txt"
            ),
        )
        if not selected_path:
            return "break" if _event is not None else False

        path = Path(selected_path)
        try:
            result = self._write_file(path)
        except OSError as error:
            messagebox.showerror("Save Failed", str(error), parent=self.root)
            result = False
        return "break" if _event is not None else result

    def on_close(self):
        if not self._confirm_discard_changes():
            return
        self.root.destroy()

    def _replace_text_content(self, widget: tk.Text, value: str):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        if value:
            widget.insert("1.0", value)
        widget.configure(state="disabled")

    def _append_text_content(self, widget: tk.Text, value: str):
        widget.configure(state="normal")
        widget.insert("end", value + "\n")
        widget.see("end")
        widget.configure(state="disabled")

    def _replace_last_output_line(self, value: str):
        content = self.console_output.get("1.0", "end-1c").splitlines()
        if content:
            content[-1] = value
        else:
            content = [value]
        self._replace_text_content(self.console_output, "\n".join(content) + "\n")

    def _set_console_input_state(self, enabled: bool, prompt: str = ">"):
        state = "normal" if enabled else "disabled"
        button_bg = ACCENT if enabled else BORDER

        self.console_prompt_label.configure(text=prompt, fg=TEXT if enabled else MUTED)
        self.console_input.configure(state=state)
        self.console_submit_button.configure(state=state, bg=button_bg)

        if enabled:
            self.console_input.focus_set()
        else:
            self.console_input.delete(0, "end")

    def submit_console_input(self, _event=None):
        if not self.awaiting_runtime_input:
            return "break"

        value = self.console_input.get()
        self.pending_runtime_input.append(value)
        self.console_input.delete(0, "end")
        self.runtime_input_request += 1
        self.runtime_input_signal.set(self.runtime_input_request)
        return "break"

    def _reset_runtime_input(self):
        self.awaiting_runtime_input = False
        self.pending_runtime_input.clear()
        self.current_input_target = None
        self._set_console_input_state(False)

    def _handle_runtime_output(self, text: str):
        self._append_text_content(self.console_output, text)

    def _clear_output_views(self):
        self._reset_runtime_input()
        self._replace_text_content(self.console_output, "")
        self._clear_trace_entries()

    def _format_diagnostic(self, diagnostic: Diagnostic):
        return (
            f"{diagnostic.kind.upper()} at line {diagnostic.start_line}, "
            f"column {diagnostic.start_col}\n{diagnostic.message}"
        )

    def _reset_watch_values(self, placeholder: str = "<not run>"):
        for item in self.watch_tree.get_children():
            values = self.watch_tree.item(item, "values")
            if not values:
                continue
            self.watch_tree.item(item, values=(values[0], placeholder))

    def _render_watch_value(self, expression: str, snapshot: dict[str, object] | None):
        if snapshot is None:
            return "<select a step>"

        try:
            value = evaluate_watch_expression(expression, snapshot)
            return format_runtime_value(value)
        except NameError:
            return "<not in scope>"
        except Exception as error:
            return f"<invalid watch: {error}>"

    def _update_watch_values(self, snapshot: dict[str, object] | None):
        for item in self.watch_tree.get_children():
            values = self.watch_tree.item(item, "values")
            if not values:
                continue
            expression = values[0]
            rendered = self._render_watch_value(expression, snapshot)
            self.watch_tree.item(item, values=(expression, rendered))

    def add_watch(self, _event=None):
        expression = self.watch_entry.get().strip()
        if not expression or expression in self.watch_expressions:
            return "break"

        self.watch_expressions.append(expression)
        self.watch_counter += 1
        watch_id = f"watch_{self.watch_counter}"
        current_snapshot = (
            self.trace_entries[self.current_trace_index].snapshot
            if self.current_trace_index is not None and self.trace_entries
            else None
        )
        self.watch_tree.insert(
            "",
            "end",
            iid=watch_id,
            values=(expression, self._render_watch_value(expression, current_snapshot)),
        )
        self.watch_entry.delete(0, "end")
        return "break"

    def remove_selected_watch(self):
        for item in self.watch_tree.selection():
            values = self.watch_tree.item(item, "values")
            if values and values[0] in self.watch_expressions:
                self.watch_expressions.remove(values[0])
            self.watch_tree.delete(item)

    def _set_navigation_state(self):
        has_trace = bool(self.trace_entries)
        has_selection = has_trace and self.current_trace_index is not None

        prev_state = (
            "normal"
            if has_selection and self.current_trace_index is not None and self.current_trace_index > 0
            else "disabled"
        )
        next_state = (
            "normal"
            if has_selection
            and self.current_trace_index is not None
            and self.current_trace_index < len(self.trace_entries) - 1
            else "disabled"
        )

        self.prev_button.configure(state=prev_state)
        self.next_button.configure(state=next_state)
        self.trace_prev_button.configure(state=prev_state)
        self.trace_next_button.configure(state=next_state)

    def _clear_trace_entries(self):
        if hasattr(self, "trace_tree"):
            for item in self.trace_tree.get_children():
                self.trace_tree.delete(item)
        self.trace_entries = []
        self.current_trace_index = None
        self.trace_summary_label.configure(text="No timeline loaded")
        self.step_label.configure(text="No Timeline")
        self.editor.clear_execution_highlight()
        self._clear_call_stack()
        self._set_navigation_state()

    def _show_trace_entry(self, index: int):
        if not self.trace_entries:
            self.current_trace_index = None
            self._reset_watch_values("<select a step>")
            self.editor.clear_execution_highlight()
            self._clear_call_stack()
            self._set_navigation_state()
            return

        index = max(0, min(index, len(self.trace_entries) - 1))
        self.current_trace_index = index
        entry = self.trace_entries[index]
        item_id = str(index)
        current_selection = self.trace_tree.selection()
        if current_selection != (item_id,):
            self._syncing_trace_selection = True
            try:
                self.trace_tree.selection_set(item_id)
            finally:
                self._syncing_trace_selection = False
        self.trace_tree.focus(item_id)
        self.trace_tree.see(item_id)
        self.step_label.configure(text=f"Step {index + 1}/{len(self.trace_entries)}")
        self.trace_summary_label.configure(
            text=f"Selected line {entry.line if entry.line is not None else '?'}"
        )
        self._update_watch_values(entry.snapshot)
        self._update_call_stack(entry.call_stack)
        self.editor.highlight_execution_span(
            entry.start_line,
            entry.end_line,
            entry.start_col,
            entry.end_col,
        )
        self._set_navigation_state()

    def _populate_trace_entries(
        self,
        entries: list[TraceEntry],
        selected_index: int | None = None,
    ):
        self._clear_trace_entries()
        self.trace_entries = list(entries)

        for index, entry in enumerate(self.trace_entries):
            self.trace_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    index + 1,
                    entry.line if entry.line is not None else "?",
                    entry.snippet,
                    entry.result,
                ),
            )

        if not self.trace_entries:
            self._reset_watch_values("<no trace>")
            self._clear_call_stack()
            return

        if selected_index is None:
            selected_index = 0
        self._show_trace_entry(selected_index)

    def _on_trace_select(self, _event=None):
        if self._syncing_trace_selection:
            return
        selection = self.trace_tree.selection()
        if not selection:
            return
        selected_index = int(selection[0])
        if selected_index == self.current_trace_index:
            return
        self._show_trace_entry(selected_index)

    def step_previous(self):
        if self.current_trace_index is None:
            return
        self._show_trace_entry(self.current_trace_index - 1)

    def step_next(self):
        if self.current_trace_index is None:
            return
        self._show_trace_entry(self.current_trace_index + 1)

    def _on_editor_changed(self):
        if self._suppress_editor_change:
            return

        self._set_dirty(True)
        if self.trace_entries:
            self._clear_trace_entries()
            self._reset_watch_values("<rerun required>")
            self.step_label.configure(text="Timeline Outdated")
            self.trace_summary_label.configure(text="Edit detected, rerun to rebuild timeline")
        self.schedule_validation()

    def schedule_validation(self):
        if self.validation_job is not None:
            self.root.after_cancel(self.validation_job)
        self.validation_job = self.root.after(250, self.refresh_validation)

    def refresh_validation(self):
        self.validation_job = None
        validation = validate_source(self.editor.get_text())
        self.current_validation = validation
        self.editor.apply_highlighting(validation.tokens)
        self.editor.apply_diagnostics(validation.diagnostics)
        if validation.symbols:
            self._populate_symbol_table(validation.symbols)
        elif validation.ast is None and validation.diagnostics:
            self._clear_symbol_table("Symbol table unavailable until the file parses")
        else:
            self._populate_symbol_table([])

        if validation.diagnostics:
            issue_count = len(validation.diagnostics)
            suffix = "" if issue_count == 1 else "s"
            self._set_status(f"{issue_count} issue{suffix} detected", ERROR)
        else:
            self._set_status("Ready", MUTED)

        return validation

    def _request_runtime_input(self, target_name: str):
        if self.pending_runtime_input:
            value = self.pending_runtime_input.pop(0)
            self._append_text_content(self.console_output, f"> {value}")
            return value

        self.awaiting_runtime_input = True
        self.current_input_target = target_name
        self._set_console_input_state(True, prompt=">")
        self._append_text_content(self.console_output, ">")
        self._set_status("Waiting for input...", ACCENT)
        self.root.wait_variable(self.runtime_input_signal)

        value = self.pending_runtime_input.pop(0) if self.pending_runtime_input else ""
        self.awaiting_runtime_input = False
        self.current_input_target = None
        self._set_console_input_state(False)
        self._replace_last_output_line(f"> {value}")
        self._set_status("Running...", ACCENT)
        return value

    def run_program(self, _event=None):
        if self.is_running:
            return "break"

        validation = self.refresh_validation()
        self._clear_output_views()
        self._reset_watch_values("<not run>")

        if validation.diagnostics:
            for diagnostic in validation.diagnostics:
                self._append_text_content(
                    self.console_output, self._format_diagnostic(diagnostic)
                )
                self._append_text_content(self.console_output, "")
            self._set_status("Cannot run until editor issues are fixed", ERROR)
            return "break"

        self.is_running = True
        self._set_toolbar_busy(True)
        self._set_status("Running...", ACCENT)

        try:
            result = execute_validation(
                validation,
                input_provider=self._request_runtime_input,
                output_callback=self._handle_runtime_output,
            )
        finally:
            self.is_running = False
            self._set_toolbar_busy(False)
            self._reset_runtime_input()

        selected_index = len(result.trace) - 1 if result.runtime_error else 0
        self._populate_trace_entries(result.trace, selected_index=selected_index)

        if result.success:
            self._set_status(f"Run completed with {len(result.trace)} step(s)", SUCCESS)
        elif result.runtime_error:
            self._set_status(
                f"Runtime error after {len(result.trace)} recorded step(s)", ERROR
            )
        else:
            self._set_status("Execution stopped", ERROR)

        return "break"


def main():
    root = tk.Tk()
    IDEApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
