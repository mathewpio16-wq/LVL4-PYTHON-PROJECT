"""Look and feel shared by every DFIP screen.

Holds the light and dark colour palettes, the fonts and a small set of
widget helpers (buttons, cards, inputs, badges...).

Colours are read from the live dictionary ``T`` every time a widget is
built, e.g. ``bg=T["surface"]``. Switching theme updates ``T`` in place
and the app then rebuilds the visible screen, so every module that did
``from theme import T`` automatically sees the new colours.
"""

import json
import os
import shutil
from pathlib import Path
import tkinter as tk
from tkinter import ttk

_settings_dir = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / ".local" / "share")) / "DFIP_Case_Management"
_settings_dir.mkdir(parents=True, exist_ok=True)
SETTINGS_PATH = str(_settings_dir / "dfip_settings.json")
_legacy_settings = Path(__file__).resolve().parent / "dfip_settings.json"
if not Path(SETTINGS_PATH).exists() and _legacy_settings.is_file():
    shutil.copy2(_legacy_settings, SETTINGS_PATH)

# ---------------- FONTS ----------------

FONT = "Segoe UI"
F_DISPLAY = (FONT, 28, "bold")
F_TITLE = (FONT, 22, "bold")
F_HEADING = (FONT, 13, "bold")
F_SUBHEAD = (FONT, 11, "bold")
F_BODY = (FONT, 10)
F_BOLD = (FONT, 10, "bold")
F_SMALL = (FONT, 9)
F_SMALL_BOLD = (FONT, 9, "bold")
F_CAPTION = (FONT, 8, "bold")
F_STAT = (FONT, 30, "bold")

# ---------------- PALETTES ----------------
# badge_* entries are (background, text colour) pairs.

PALETTES = {
    "light": {
        "bg": "#f4f6f8",
        "surface": "#ffffff",
        "surface_alt": "#f7f8fa",
        "row_alt": "#fafbfc",
        "border": "#e3e7ec",
        "border_strong": "#cdd3db",
        "text": "#0f172a",
        "muted": "#64748b",
        "subtle": "#94a3b8",
        "primary": "#0f766e",
        "primary_hover": "#0b5f58",
        "primary_text": "#ffffff",
        "primary_soft": "#e0f5f1",
        "primary_soft_hover": "#cdeee8",
        "selected": "#d9f2ee",
        "danger": "#dc2626",
        "danger_hover": "#b91c1c",
        "danger_text": "#ffffff",
        "success": "#15803d",
        "warning": "#b45309",
        "info": "#1d4ed8",
        "disabled_bg": "#e8ebef",
        "disabled_fg": "#9aa4b2",
        "hero_bg": "#0d3b38",
        "hero_text": "#ffffff",
        "hero_muted": "#9bd0c9",
        "badge_open": ("#fef3c7", "#92400e"),
        "badge_completed": ("#dcfce7", "#166534"),
        "badge_admin": ("#fee2e2", "#991b1b"),
        "badge_expert": ("#dbeafe", "#1e40af"),
        "badge_user": ("#e5e7eb", "#374151"),
    },
    "dark": {
        "bg": "#0e1318",
        "surface": "#161c23",
        "surface_alt": "#1c242d",
        "row_alt": "#19212a",
        "border": "#26303b",
        "border_strong": "#37424f",
        "text": "#e7ecf2",
        "muted": "#9aa6b5",
        "subtle": "#6b7685",
        "primary": "#2dd4bf",
        "primary_hover": "#5eead4",
        "primary_text": "#05211e",
        "primary_soft": "#12332f",
        "primary_soft_hover": "#18433e",
        "selected": "#16423d",
        "danger": "#dc2626",
        "danger_hover": "#ef4444",
        "danger_text": "#ffffff",
        "success": "#4ade80",
        "warning": "#fbbf24",
        "info": "#60a5fa",
        "disabled_bg": "#222b35",
        "disabled_fg": "#5f6b7a",
        "hero_bg": "#0a1f1e",
        "hero_text": "#ffffff",
        "hero_muted": "#7fb9b1",
        "badge_open": ("#3a2f0b", "#fcd34d"),
        "badge_completed": ("#12351f", "#86efac"),
        "badge_admin": ("#3f1618", "#fca5a5"),
        "badge_expert": ("#15294a", "#93c5fd"),
        "badge_user": ("#2a323d", "#cbd5e1"),
    },
}

T = dict(PALETTES["light"])  # the live palette
_mode = {"name": "light"}


def current_mode():
    return _mode["name"]


def set_mode(mode):
    """Switch palette in place (the caller must rebuild the screens)."""
    if mode not in PALETTES:
        mode = "light"
    _mode["name"] = mode
    T.update(PALETTES[mode])


def load_saved_mode():
    """Restore the theme chosen last time, if any."""
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as handle:
            set_mode(json.load(handle).get("theme", "light"))
    except (OSError, ValueError, AttributeError):
        set_mode("light")


def save_mode():
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as handle:
            json.dump({"theme": _mode["name"]}, handle)
    except OSError:
        pass  # not being able to remember the theme is not an error


# ---------------- ttk (tables, dropdowns, scrollbars) ----------------

def apply_ttk_styles(root):
    style = ttk.Style(root)
    style.theme_use("clam")

    style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    style.configure(
        "Treeview", background=T["surface"], fieldbackground=T["surface"],
        foreground=T["text"], rowheight=42, borderwidth=0, font=F_BODY)
    style.configure(
        "Treeview.Heading", background=T["surface_alt"],
        foreground=T["muted"], font=F_SMALL_BOLD, relief="flat",
        borderwidth=0, padding=(12, 11), bordercolor=T["border"],
        lightcolor=T["surface_alt"], darkcolor=T["surface_alt"])
    style.map("Treeview",
              background=[("selected", T["selected"])],
              foreground=[("selected", T["text"])])
    style.map("Treeview.Heading",
              background=[("active", T["surface_alt"])],
              relief=[("active", "flat")])

    for orient in ("Vertical", "Horizontal"):
        name = f"{orient}.TScrollbar"
        style.configure(
            name, background=T["border_strong"], troughcolor=T["surface"],
            bordercolor=T["surface"], lightcolor=T["border_strong"],
            darkcolor=T["border_strong"], arrowcolor=T["muted"],
            gripcount=0, relief="flat", arrowsize=12)
        style.map(name, background=[("active", T["subtle"]),
                                    ("pressed", T["subtle"])])

    style.configure(
        "TCombobox", fieldbackground=T["surface"],
        background=T["surface_alt"], foreground=T["text"],
        arrowcolor=T["muted"], bordercolor=T["border_strong"],
        lightcolor=T["surface"], darkcolor=T["surface"], padding=6,
        relief="flat")
    style.map("TCombobox",
              fieldbackground=[("readonly", T["surface"]),
                               ("disabled", T["disabled_bg"])],
              foreground=[("disabled", T["disabled_fg"])],
              selectbackground=[("readonly", T["surface"])],
              selectforeground=[("readonly", T["text"])],
              bordercolor=[("focus", T["primary"])],
              arrowcolor=[("disabled", T["disabled_fg"])])

    # The dropdown list of a combobox is a plain Tk listbox.
    root.option_add("*TCombobox*Listbox.background", T["surface"])
    root.option_add("*TCombobox*Listbox.foreground", T["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", T["primary"])
    root.option_add("*TCombobox*Listbox.selectForeground",
                    T["primary_text"])
    root.option_add("*TCombobox*Listbox.font", F_BODY)


# ---------------- WINDOW PLACEMENT ----------------

def window_geometry(win, width, height, parent=None):
    """Return 'WxH+X+Y', shrunk to fit the screen and centred."""
    win.update_idletasks()
    screen_w = win.winfo_screenwidth()
    screen_h = win.winfo_screenheight()
    width = min(width, screen_w - 40)
    height = min(height, screen_h - 90)

    if parent is not None and parent.winfo_viewable():
        x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
    else:
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2 - 20

    x = max(0, min(x, screen_w - width))
    y = max(0, min(y, screen_h - height - 40))
    return f"{width}x{height}+{x}+{y}"


# ---------------- LABELS ----------------

def lbl(parent, text="", font=F_BODY, fg="text", bg="surface", **options):
    """A label whose colours are theme keys, e.g. fg='muted'."""
    return tk.Label(parent, text=text, font=font, fg=T[fg], bg=T[bg],
                    **options)


def field_label(parent, text, bg="surface"):
    """Small upper-case caption that sits above an input."""
    return tk.Label(parent, text=text.upper(), font=F_CAPTION,
                    fg=T["muted"], bg=T[bg], anchor="w", justify="left")


def separator(parent, bg="border"):
    return tk.Frame(parent, height=1, bg=T[bg])


# ---------------- BUTTONS ----------------

def button_palette(kind):
    """(background, hover background, text colour, border colour)."""
    if kind == "primary":
        return (T["primary"], T["primary_hover"], T["primary_text"],
                T["primary"], T["primary_hover"])
    if kind == "danger":
        return (T["danger"], T["danger_hover"], T["danger_text"],
                T["danger"], T["danger_hover"])
    if kind == "soft":
        return (T["primary_soft"], T["primary_soft_hover"], T["primary"],
                T["primary_soft"], T["primary_soft_hover"])
    return (T["surface"], T["surface_alt"], T["text"],
            T["border_strong"], T["border_strong"])  # secondary


def make_button(parent, text, command, kind="primary", padx=16, pady=8):
    """A flat button with a hover effect. kind: primary, secondary,
    soft or danger."""
    bg, hover, fg, border, border_hover = button_palette(kind)
    button = tk.Button(
        parent, text=text, command=command, relief="flat", bd=0,
        cursor="hand2", font=F_BOLD, bg=bg, fg=fg, activebackground=hover,
        activeforeground=fg, disabledforeground=T["disabled_fg"],
        padx=padx, pady=pady, highlightthickness=1,
        highlightbackground=border, highlightcolor=border,
        takefocus=0)
    button.palette = (bg, hover, fg, border, border_hover)

    def on_enter(event):
        if str(button["state"]) != "disabled":
            button.config(bg=hover, highlightbackground=border_hover)

    def on_leave(event):
        if str(button["state"]) != "disabled":
            button.config(bg=bg, highlightbackground=border)

    button.bind("<Enter>", on_enter)
    button.bind("<Leave>", on_leave)
    return button


def set_enabled(button, enabled, text=None):
    """Enable/disable a make_button() button with matching colours."""
    bg, _hover, _fg, border, _bh = button.palette
    if enabled:
        button.config(state="normal", bg=bg, highlightbackground=border,
                      cursor="hand2")
    else:
        button.config(state="disabled", bg=T["disabled_bg"],
                      highlightbackground=T["disabled_bg"], cursor="arrow")
    if text is not None:
        button.config(text=text)


def theme_toggle(parent, app):
    """The light/dark switch shown in the corner of every screen."""
    if current_mode() == "dark":
        text = "\u2600  Light mode"
    else:
        text = "\u263e  Dark mode"
    return make_button(parent, text, app.toggle_theme, kind="secondary",
                       padx=12, pady=6)


def check(parent, text, variable, bg="surface", command=None):
    """A theme-aware checkbox (the native Windows one always draws a
    black tick, which disappears on a dark background)."""
    row = tk.Frame(parent, bg=T[bg], cursor="hand2")
    box = tk.Label(row, text="", width=2, font=(FONT, 8, "bold"),
                   cursor="hand2", highlightthickness=1)
    box.pack(side="left")
    label = tk.Label(row, text=text, font=F_BODY, fg=T["muted"], bg=T[bg],
                     cursor="hand2", padx=8)
    label.pack(side="left")

    def paint():
        on = bool(variable.get())
        box.config(
            text="\u2713" if on else "",
            bg=T["primary"] if on else T["surface"],
            fg=T["primary_text"],
            highlightbackground=T["primary"] if on else T["border_strong"])

    def toggle(event=None):
        variable.set(not variable.get())
        paint()
        if command:
            command()

    for widget in (row, box, label):
        widget.bind("<Button-1>", toggle)
    paint()
    return row


# ---------------- CARDS, BADGES, AVATARS ----------------

def card(parent, **options):
    """A white (or dark grey) panel with a thin border."""
    return tk.Frame(parent, bg=T["surface"], highlightthickness=1,
                    highlightbackground=T["border"], **options)


def badge(parent, key=""):
    label = tk.Label(parent, font=F_CAPTION, padx=9, pady=3)
    update_badge(label, key)
    return label


def update_badge(label, key):
    """key is 'Open', 'Completed', 'admin', 'expert', 'user' or ''."""
    colours = T.get(f"badge_{key.lower()}") if key else None
    if colours is None:
        label.config(text="", bg=T["surface"], fg=T["surface"], padx=0)
        return
    label.config(text=key.upper(), bg=colours[0], fg=colours[1], padx=9)


def avatar(parent, name, size=38, bg="surface"):
    """A circle with the person's initials."""
    parts = [p for p in (name or "?").split() if p]
    initials = "".join(p[0] for p in parts[:2]).upper() or "?"
    canvas = tk.Canvas(parent, width=size, height=size, bg=T[bg],
                       highlightthickness=0, bd=0)
    canvas.create_oval(1, 1, size - 1, size - 1, fill=T["primary"],
                       outline="")
    canvas.create_text(size / 2, size / 2, text=initials,
                       fill=T["primary_text"],
                       font=(FONT, max(8, size // 3), "bold"))
    return canvas


def progress_bar(parent, fraction, colour="primary", bg="surface"):
    """A thin horizontal bar. fraction is 0.0 to 1.0."""
    track = tk.Frame(parent, height=8, bg=T["border"])
    track.pack_propagate(False)
    fill = tk.Frame(track, bg=T[colour])
    fill.place(x=0, y=0, relheight=1, relwidth=max(0.0, min(1.0, fraction)))
    return track


# ---------------- INPUTS ----------------

def input_box(parent, show=None, secret=False, width=20, textvariable=None,
              font=F_BODY, ipady=8):
    """A bordered text input. Pack/grid ``entry.shell``, not the entry.

    With secret=True a small Show/Hide switch is added on the right.
    """
    shell = tk.Frame(parent, bg=T["surface"], highlightthickness=1,
                     highlightbackground=T["border_strong"])
    entry = tk.Entry(
        shell, show=("*" if secret else show), width=width, relief="flat",
        bd=0, font=font, bg=T["surface"], fg=T["text"],
        insertbackground=T["text"], highlightthickness=0,
        readonlybackground=T["surface_alt"], disabledbackground=T["surface_alt"],
        disabledforeground=T["muted"], selectbackground=T["primary"],
        selectforeground=T["primary_text"], textvariable=textvariable)
    entry.shell = shell

    if secret:
        toggle = tk.Label(shell, text="Show", font=F_SMALL_BOLD,
                          fg=T["primary"], bg=T["surface"], cursor="hand2",
                          padx=12)
        toggle.pack(side="right", fill="y")

        def flip(event=None):
            if entry.cget("show"):
                entry.config(show="")
                toggle.config(text="Hide")
            else:
                entry.config(show="*")
                toggle.config(text="Show")

        toggle.bind("<Button-1>", flip)

    entry.pack(side="left", fill="x", expand=True, ipady=ipady, padx=(12, 6))

    entry.bind("<FocusIn>", lambda e: shell.config(
        highlightbackground=T["primary"]))
    entry.bind("<FocusOut>", lambda e: shell.config(
        highlightbackground=T["border_strong"]))
    return entry


def text_box(parent, height=4, scroll=True):
    """A bordered multi-line input. Pack/grid ``text.shell``."""
    shell = tk.Frame(parent, bg=T["surface"], highlightthickness=1,
                     highlightbackground=T["border_strong"])
    text = tk.Text(
        shell, height=height, width=10, wrap="word", relief="flat", bd=0,
        font=F_BODY, bg=T["surface"], fg=T["text"],
        insertbackground=T["text"], highlightthickness=0, padx=10, pady=8,
        selectbackground=T["primary"], selectforeground=T["primary_text"],
        spacing3=2)
    text.shell = shell

    if scroll:
        bar = ttk.Scrollbar(shell, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
    text.pack(side="left", fill="both", expand=True)

    text.bind("<FocusIn>", lambda e: shell.config(
        highlightbackground=T["primary"]))
    text.bind("<FocusOut>", lambda e: shell.config(
        highlightbackground=T["border_strong"]))
    return text


def set_text(widget, text, editable):
    """Fill an Entry or Text widget, then lock or unlock it."""
    locked_bg = T["surface_alt"]
    if isinstance(widget, tk.Text):
        widget.config(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)
        widget.config(state="normal" if editable else "disabled",
                      bg=T["surface"] if editable else locked_bg)
    else:
        widget.config(state="normal")
        widget.delete(0, tk.END)
        widget.insert(0, text)
        widget.config(state="normal" if editable else "readonly")
    shell = getattr(widget, "shell", None)
    if shell is not None:
        shell.config(bg=T["surface"] if editable else locked_bg)


# ---------------- SCROLLABLE PANEL ----------------

class ScrollFrame(tk.Frame):
    """A frame whose ``inner`` area scrolls vertically when it is taller
    than the space available. The scrollbar only appears when needed."""

    def __init__(self, parent, bg="surface"):
        super().__init__(parent, bg=T[bg])
        self.canvas = tk.Canvas(self, bg=T[bg], highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self._on_scroll)

        self.inner = tk.Frame(self.canvas, bg=T[bg])
        self._window = self.canvas.create_window(
            (0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner_resize)
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        self.bind("<Enter>", self._grab_wheel)
        self.bind("<Leave>", self._release_wheel)

    def _on_inner_resize(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_resize(self, event):
        self.canvas.itemconfigure(self._window, width=event.width)

    def _on_scroll(self, first, last):
        self.scrollbar.set(first, last)
        if float(first) <= 0.0 and float(last) >= 1.0:
            self.scrollbar.place_forget()
        else:
            # Overlaid on the right edge so showing it never re-flows
            # the content.
            self.scrollbar.place(relx=1.0, rely=0, relheight=1.0,
                                 anchor="ne")

    def _needs_scroll(self):
        return self.inner.winfo_reqheight() > self.canvas.winfo_height()

    def _grab_wheel(self, event=None):
        self.bind_all("<MouseWheel>", self._on_wheel)
        self.bind_all("<Button-4>", self._on_wheel)
        self.bind_all("<Button-5>", self._on_wheel)

    def _release_wheel(self, event=None):
        self.unbind_all("<MouseWheel>")
        self.unbind_all("<Button-4>")
        self.unbind_all("<Button-5>")

    def _on_wheel(self, event):
        # Text boxes and tables scroll themselves.
        if isinstance(event.widget, (tk.Text, ttk.Treeview)):
            return
        if not self._needs_scroll():
            return
        if getattr(event, "num", None) == 4 or event.delta > 0:
            self.canvas.yview_scroll(-2, "units")
        else:
            self.canvas.yview_scroll(2, "units")

    def scroll_to_top(self):
        self.canvas.yview_moveto(0)
