"""Dashboard screens for DFIP: home, reports, users and account.

What each role sees here is only a convenience. The real permission
checks live in database.py, so a hidden button cannot be bypassed.

Report titles and descriptions are read-only for EVERYONE (admins and
experts included); database.py enforces this and the screens below simply
never offer a way to edit them.
"""

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

import database
from cases import create_case
from search import search_case_from_db
from sorting import sort_cases_from_db
import theme
from theme import (T, F_BODY, F_BOLD, F_HEADING, F_SMALL, F_SMALL_BOLD,
                   F_STAT, F_SUBHEAD, F_TITLE, ScrollFrame,
                   avatar, badge, card, field_label, input_box, lbl,
                   make_button, progress_bar, separator, set_enabled,
                   set_text, text_box, theme_toggle, update_badge)

ROLE_DESCRIPTIONS = {
    "user": "You can submit reports and view your own reports.",
    "expert": "You can view reports assigned to you and record outcomes.",
    "admin": "You have full access: reports, assignment and user management.",
}

UNASSIGNED = "(unassigned)"
TEXT_LOCKED_NOTE = ("Titles and descriptions are locked once a report has "
                    "been submitted.")


# ---------------- SMALL HELPERS ----------------

def page_header(parent, title, subtitle="", action=None):
    """Page title, optional muted subtitle, optional button on the right."""
    header = tk.Frame(parent, bg=T["bg"])
    header.pack(fill="x", pady=(0, 22))

    text_block = tk.Frame(header, bg=T["bg"])
    text_block.pack(side="left")
    lbl(text_block, title, F_TITLE, bg="bg").pack(anchor="w")
    if subtitle:
        lbl(text_block, subtitle, F_BODY, "muted", bg="bg").pack(
            anchor="w", pady=(2, 0))

    if action:
        text, command = action
        make_button(header, text, command, pady=9).pack(
            side="right", anchor="s")
    return header


def guarded(parent, function, *args):
    """Call a database function, showing a message if it is not allowed.

    Returns None when permission was denied.
    """
    try:
        return function(*args)
    except PermissionError as error:
        messagebox.showerror("Not allowed", str(error), parent=parent)
        return None


def format_timestamp(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%d %b %Y %H:%M")


def format_date(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%d %b %Y")


def report_status(report):
    return "Completed" if report["outcome"] else "Open"


def greeting():
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning"
    if hour < 18:
        return "Good afternoon"
    return "Good evening"


def bind_click(widget, callback):
    """Make a widget (and everything inside it) clickable."""
    widget.bind("<Button-1>", lambda event: callback())
    widget.configure(cursor="hand2")
    for child in widget.winfo_children():
        bind_click(child, callback)


# ---------------- DASHBOARD FRAME ----------------

class NavTab(tk.Frame):
    """A top-bar navigation tab with an underline when active."""

    def __init__(self, parent, text, command):
        super().__init__(parent, bg=T["surface"], cursor="hand2")
        self.active = False
        self.label = tk.Label(
            self, text=text, font=F_BOLD, bg=T["surface"], fg=T["muted"],
            padx=18, pady=21, cursor="hand2")
        self.label.pack()
        self.line = tk.Frame(self, height=3, bg=T["surface"])
        self.line.pack(side="bottom", fill="x")

        for widget in (self, self.label):
            widget.bind("<Button-1>", lambda event: command())
            widget.bind("<Enter>", self.on_enter)
            widget.bind("<Leave>", self.on_leave)

    def on_enter(self, event):
        if not self.active:
            self.label.config(fg=T["text"])

    def on_leave(self, event):
        if not self.active:
            self.label.config(fg=T["muted"])

    def set_active(self, active):
        self.active = active
        self.label.config(fg=T["primary"] if active else T["muted"])
        self.line.config(bg=T["primary"] if active else T["surface"])


class DashboardFrame(tk.Frame):
    """Top navigation bar plus a content area that swaps between pages."""

    def __init__(self, app, username, start_page="home",
                 selected_report=None):
        super().__init__(app, bg=T["bg"])
        self.app = app
        self.username = username
        self.role = database.get_role(username) or "user"
        self.profile = database.get_profile(username) or {}
        self.display_name = self.profile.get("full_name") or username
        self.selected_report = selected_report
        self.pages = {}
        self.nav_tabs = {}
        self.active_page = None
        self.build()
        self.show_page(start_page if start_page in self.pages else "home")

    def capture_state(self):
        """What to keep when the theme is switched and the screen redrawn."""
        reports = self.pages.get("reports")
        return {"start_page": self.active_page,
                "selected_report": reports.selected_id if reports else None}

    def build(self):
        self.build_topbar()

        self.content = tk.Frame(self, bg=T["bg"])
        self.content.pack(fill="both", expand=True)

        self.pages["home"] = HomePage(
            self.content, self.username, self.role, self.display_name,
            on_new_report=self.new_report, on_open_report=self.open_report)
        self.pages["reports"] = ReportsPage(
            self.content, self.username, self.role, self.selected_report)
        self.pages["cases"] = CasesPage(self.content, self.username, self.role, self.open_case_reports)
        nav = [("Home", "home"), ("Cases", "cases"), ("Reports", "reports")]
        if self.role == "admin":
            self.pages["users"] = UsersPage(self.content, self.username)
            nav.append(("Users", "users"))
        self.pages["account"] = AccountPage(
            self.content, self.app, self.username, self.profile, self.role)
        nav.append(("Account", "account"))

        for label, page in nav:
            tab = NavTab(self.nav, label, lambda p=page: self.navigate(p))
            tab.pack(side="left", fill="y")
            self.nav_tabs[page] = tab

    def build_topbar(self):
        topbar = tk.Frame(self, bg=T["surface"])
        topbar.pack(fill="x")
        bar = tk.Frame(topbar, bg=T["surface"])
        bar.pack(fill="x", padx=(30, 26))

        brand = tk.Frame(bar, bg=T["surface"])
        brand.pack(side="left", padx=(0, 40), pady=14)
        tk.Label(brand, text="D", font=(theme.FONT, 14, "bold"),
                 bg=T["primary"], fg=T["primary_text"], width=2,
                 pady=2).pack(side="left")
        lbl(brand, "DFIP", (theme.FONT, 16, "bold")).pack(
            side="left", padx=(10, 0))

        right = tk.Frame(bar, bg=T["surface"])
        right.pack(side="right", pady=12)
        theme_toggle(right, self.app).pack(side="left", padx=(0, 22))
        avatar(right, self.display_name, 38).pack(side="left")
        who = tk.Frame(right, bg=T["surface"])
        who.pack(side="left", padx=(10, 20))
        lbl(who, self.display_name, F_BOLD).pack(anchor="w")
        lbl(who, self.role.capitalize(), F_SMALL, "muted").pack(anchor="w")
        make_button(right, "Sign out", self.app.sign_out,
                    kind="secondary", padx=14, pady=6).pack(side="left")

        self.nav = tk.Frame(bar, bg=T["surface"])
        self.nav.pack(side="left", fill="y")

        separator(self).pack(fill="x")

    def navigate(self, name):
        if name == "reports":
            self.pages["reports"].case_filter = None
        self.show_page(name)

    def show_page(self, name):
        self.active_page = name
        for key, tab in self.nav_tabs.items():
            tab.set_active(key == name)

        for page in self.pages.values():
            page.pack_forget()
        page = self.pages[name]
        page.pack(fill="both", expand=True, padx=40, pady=(30, 28))
        page.refresh()

    def open_case_reports(self, case_id):
        """Show reports related to one case, subject to the user's permissions."""
        reports = self.pages["reports"]
        reports.filter_key = "all"
        reports.search_var.set("")
        reports.case_filter = case_id
        self.show_page("reports")

    def new_report(self):
        self.pages["reports"].case_filter = None
        self.show_page("reports")
        self.pages["reports"].new_report()

    def open_report(self, report_id=None):
        """Jump to the reports page, optionally selecting one report."""
        if report_id is not None:
            self.pages["reports"].focus_report(report_id)
        self.show_page("reports")



# ---------------- CASE MANAGEMENT PAGE ----------------
class CasesPage(tk.Frame):
    """Add, view, search and sort cases stored in SQLite."""

    def __init__(self, parent, username, role, on_case_reports):
        super().__init__(parent, bg=T["bg"])
        self.username = username
        self.role = role
        self.on_case_reports = on_case_reports
        self.build()

    def build(self):
        page_header(self, "Case Management", "Register, search and prioritise investigation cases")
        actions = tk.Frame(self, bg=T["bg"])
        actions.pack(fill="x", pady=(0, 15))
        for text, callback in (("Add Case", self.add_case),
                               ("View All", self.refresh),
                               ("Sort by Priority", self.sort_cases)):
            make_button(actions, text, callback, kind="secondary", padx=12, pady=8).pack(side="left", padx=(0, 10))
        make_button(actions, "Case Reports", self.view_reports,
                    kind="secondary", padx=12, pady=8).pack(side="left", padx=(0, 10))
        if self.role in ("admin", "expert"):
            make_button(actions, "Change Status", self.change_status,
                        kind="secondary", padx=12, pady=8).pack(side="left", padx=(0, 10))
        tk.Label(actions, text="Case ID", bg=T["bg"], fg=T["text"], font=F_BODY).pack(side="left", padx=(15, 6))
        self.search_var = tk.StringVar()
        tk.Entry(actions, textvariable=self.search_var, width=13, font=F_BODY).pack(side="left", padx=(0, 8))
        make_button(actions, "Search", self.search, padx=12, pady=8).pack(side="left")

        columns = ("case_id", "case_title", "client_name", "priority", "status")
        table_frame = tk.Frame(self, bg=T["surface"])
        table_frame.pack(fill="both", expand=True)
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        for key, label, width in (("case_id", "Case ID", 85), ("case_title", "Case Title", 240),
                                  ("client_name", "Client", 190), ("priority", "Priority", 90),
                                  ("status", "Status", 110)):
            self.table.heading(key, text=label)
            self.table.column(key, width=width, minwidth=70, stretch=key in ("case_title", "client_name"))
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.table.pack(fill="both", expand=True)
        self.table.bind("<<TreeviewSelect>>", self.show_selected)
        self.details = tk.StringVar(value="Select a case to view its description.")
        tk.Label(self, textvariable=self.details, bg=T["bg"], fg=T["muted"],
                 font=F_BODY, anchor="w", justify="left", wraplength=850).pack(fill="x", pady=(14, 0))
        self.rows = {}

    def populate(self, cases):
        for item in self.table.get_children():
            self.table.delete(item)
        self.rows = {}
        for case in cases:
            key = str(case["case_id"])
            self.rows[key] = case
            self.table.insert("", "end", iid=key, values=(
                case["case_id"], case["case_title"], case["client_name"],
                case["priority"], case["status"]))
        self.details.set(f"{len(cases)} case(s) displayed. Select one to see the description.")

    def refresh(self):
        try:
            self.populate(database.get_all_cases())
        except Exception as error:
            messagebox.showerror("Database error", str(error), parent=self)

    def sort_cases(self):
        try:
            self.populate(sort_cases_from_db())
        except Exception as error:
            messagebox.showerror("Sorting error", str(error), parent=self)

    def search(self):
        value = self.search_var.get().strip()
        if not value.isdigit() or int(value) <= 0:
            messagebox.showwarning("Invalid Case ID", "Enter a positive numeric Case ID.", parent=self)
            return
        try:
            case = search_case_from_db(value)
        except Exception as error:
            messagebox.showerror("Search error", str(error), parent=self)
            return
        if case is None:
            self.populate([])
            self.details.set("No case found for ID " + value)
        else:
            self.populate([case])
            self.table.selection_set(str(case["case_id"]))
            self.show_selected()

    def show_selected(self, event=None):
        selection = self.table.selection()
        if selection:
            case = self.rows.get(selection[0])
            if case:
                self.details.set(f"Case {case['case_id']} | {case['case_title']} | "
                                 f"Priority {case['priority']} | {case['status']}\n"
                                 f"Description: {case['description']}")

    def selected_case(self):
        selected = self.table.selection()
        if not selected:
            messagebox.showwarning("Select a case", "Select a case from the table first.", parent=self)
            return None
        return self.rows.get(selected[0])

    def view_reports(self):
        case = self.selected_case()
        if case:
            self.on_case_reports(case["case_id"])

    def change_status(self):
        case = self.selected_case()
        if not case:
            return
        window = tk.Toplevel(self)
        window.title(f"Case #{case['case_id']} status")
        window.geometry("390x205")
        window.transient(self.winfo_toplevel())
        window.grab_set()
        window.configure(bg=T["bg"])
        tk.Label(window, text=f"Change status for Case #{case['case_id']}",
                 font=F_BOLD, bg=T["bg"], fg=T["text"]).pack(pady=(22, 12))
        status = ttk.Combobox(window, values=("Open", "In Progress", "Closed"),
                              state="readonly")
        status.set(case["status"])
        status.pack(pady=5)

        def save():
            success, message = database.change_case_status(
                self.username, case["case_id"], status.get())
            if success:
                messagebox.showinfo("Case updated", message, parent=window)
                window.destroy()
                self.refresh()
            else:
                messagebox.showwarning("Cannot update case", message, parent=window)
        make_button(window, "Save Status", save).pack(pady=15)

    def add_case(self):
        window = tk.Toplevel(self)
        window.title("Add New Case")
        window.geometry("490x510")
        window.configure(bg=T["bg"])
        window.transient(self.winfo_toplevel())
        window.grab_set()
        form = tk.Frame(window, bg=T["bg"], padx=25, pady=20)
        form.pack(fill="both", expand=True)
        tk.Label(form, text="Register a New Case", font=F_HEADING,
                 bg=T["bg"], fg=T["text"]).pack(anchor="w", pady=(0, 15))
        tk.Label(form, text="Case ID is assigned automatically when you save.",
                 bg=T["bg"], fg=T["muted"], font=F_BODY).pack(anchor="w", pady=(0, 8))
        fields = {}
        for key, label in (("case_title", "Case Title"),
                           ("client_name", "Client Name"), ("description", "Description")):
            tk.Label(form, text=label, bg=T["bg"], fg=T["text"], font=F_SMALL_BOLD).pack(anchor="w", pady=(8, 3))
            if key == "description":
                widget = tk.Text(form, height=3, width=44, font=F_BODY)
            else:
                widget = tk.Entry(form, font=F_BODY)
            widget.pack(fill="x")
            fields[key] = widget
        tk.Label(form, text="Priority", bg=T["bg"], fg=T["text"], font=F_SMALL_BOLD).pack(anchor="w", pady=(10, 3))
        priority = ttk.Combobox(form, values=("1", "2", "3"), state="readonly", width=12)
        priority.set("2")
        priority.pack(anchor="w")

        def submit():
            values = {key: widget.get("1.0", "end-1c") if key == "description" else widget.get()
                      for key, widget in fields.items()}
            values["priority"] = priority.get()
            success, message = create_case(values)
            if success:
                messagebox.showinfo("Success", message, parent=window)
                window.destroy()
                self.refresh()
            else:
                messagebox.showerror("Cannot add case", message, parent=window)

        make_button(form, "Save Case", submit, padx=20, pady=9).pack(anchor="e", pady=(20, 0))


# ---------------- HOME PAGE ----------------

class HomePage(tk.Frame):
    def __init__(self, parent, username, role, display_name,
                 on_new_report, on_open_report):
        super().__init__(parent, bg=T["bg"])
        self.username = username
        self.role = role
        self.on_new_report = on_new_report
        self.on_open_report = on_open_report

        first_name = (display_name.split() or [display_name])[0]
        page_header(self, f"{greeting()}, {first_name}",
                    ROLE_DESCRIPTIONS.get(role, ""),
                    action=("+  New report", on_new_report))

        self.stats_row = tk.Frame(self, bg=T["bg"])
        self.stats_row.pack(fill="x", pady=(0, 18))

        lower = tk.Frame(self, bg=T["bg"])
        lower.pack(fill="both", expand=True)

        # Overview panel (right)
        side = card(lower, width=330)
        side.pack(side="right", fill="y", padx=(18, 0))
        side.pack_propagate(False)
        side_inner = tk.Frame(side, bg=T["surface"])
        side_inner.pack(fill="both", expand=True, padx=24, pady=22)
        lbl(side_inner, "Overview", F_HEADING).pack(anchor="w")
        field_label(side_inner, "Completion rate").pack(
            anchor="w", pady=(18, 0))
        self.rate_label = lbl(side_inner, "0%", F_STAT, "primary")
        self.rate_label.pack(anchor="w")
        self.rate_holder = tk.Frame(side_inner, bg=T["surface"])
        self.rate_holder.pack(fill="x", pady=(6, 6))
        self.rate_caption = lbl(side_inner, "", F_SMALL, "muted")
        self.rate_caption.pack(anchor="w")
        separator(side_inner).pack(fill="x", pady=20)
        lbl(side_inner, "Your access", F_SUBHEAD).pack(anchor="w")
        lbl(side_inner, ROLE_DESCRIPTIONS.get(role, ""), F_BODY, "muted",
            wraplength=280, justify="left").pack(anchor="w", pady=(6, 0))

        # Recent reports (left)
        recent = card(lower)
        recent.pack(side="left", fill="both", expand=True)
        head = tk.Frame(recent, bg=T["surface"])
        head.pack(fill="x", padx=24, pady=(20, 8))
        lbl(head, "Recent reports", F_HEADING).pack(side="left")
        view_all = lbl(head, "View all", F_SMALL_BOLD, "primary",
                       cursor="hand2")
        view_all.pack(side="right")
        view_all.bind("<Button-1>", lambda event: self.on_open_report())
        self.recent_body = tk.Frame(recent, bg=T["surface"])
        self.recent_body.pack(fill="both", expand=True, padx=24,
                              pady=(0, 14))

    def refresh(self):
        reports = guarded(self, database.list_reports, self.username) or []

        total = len(reports)
        completed = sum(1 for r in reports if r["outcome"])
        open_count = total - completed

        if self.role == "admin":
            unassigned = sum(1 for r in reports if not r["assigned_to"])
            stats = [("Total reports", total, "text"),
                     ("Unassigned", unassigned, "warning"),
                     ("Open", open_count, "primary"),
                     ("Completed", completed, "success")]
        elif self.role == "expert":
            stats = [("Assigned to me", total, "text"),
                     ("Awaiting outcome", open_count, "warning"),
                     ("Completed", completed, "success")]
        else:
            stats = [("My reports", total, "text"),
                     ("Open", open_count, "warning"),
                     ("Completed", completed, "success")]

        for child in self.stats_row.winfo_children():
            child.destroy()
        for index, (caption, number, colour) in enumerate(stats):
            self.stat_card(caption, number, colour, index == len(stats) - 1)

        rate = completed / total if total else 0.0
        self.rate_label.config(text=f"{round(rate * 100)}%")
        for child in self.rate_holder.winfo_children():
            child.destroy()
        progress_bar(self.rate_holder, rate, "primary").pack(fill="x")
        self.rate_caption.config(
            text=f"{completed} of {total} report{'s' if total != 1 else ''} "
                 f"completed")

        for child in self.recent_body.winfo_children():
            child.destroy()
        if not reports:
            lbl(self.recent_body, "No reports yet.", F_BODY, "muted").pack(
                anchor="w", pady=14)
        for report in reports[:6]:
            self.recent_row(report)

    def stat_card(self, caption, number, colour, last):
        stat = card(self.stats_row)
        stat.pack(side="left", fill="both", expand=True,
                  padx=(0, 0 if last else 16))
        tk.Frame(stat, width=4, bg=T[colour]).pack(side="left", fill="y")
        body = tk.Frame(stat, bg=T["surface"])
        body.pack(side="left", fill="both", expand=True, padx=20, pady=16)
        field_label(body, caption).pack(anchor="w")
        lbl(body, str(number), F_STAT, colour).pack(anchor="w")

    def recent_row(self, report):
        row = tk.Frame(self.recent_body, bg=T["surface"])
        row.pack(fill="x")
        separator(row).pack(fill="x")

        line = tk.Frame(row, bg=T["surface"])
        line.pack(fill="x", pady=10)
        text_block = tk.Frame(line, bg=T["surface"])
        text_block.pack(side="left")
        lbl(text_block, report["title"], F_BOLD).pack(anchor="w")
        meta = f"{report['author']}  \u2022  {format_date(report['created_at'])}"
        lbl(text_block, meta, F_SMALL, "muted").pack(anchor="w")
        badge(line, report_status(report)).pack(side="right")

        report_id = report["id"]
        bind_click(line, lambda: self.on_open_report(report_id))


# ---------------- REPORTS PAGE ----------------

class ReportsPage(tk.Frame):
    def __init__(self, parent, username, role, selected_report=None):
        super().__init__(parent, bg=T["bg"])
        self.username = username
        self.role = role
        self.selected_id = None          # report currently shown in details
        self.pending_id = selected_report  # report to select on next refresh
        self.reports = []
        self.current_report = None   # report shown in the details panel
        self.editing = False         # outcome fields unlocked for editing
        self.filter_key = "all"
        self.case_filter = None
        self.chips = {}
        self.build()

    # ----- layout -----

    def build(self):
        heading, subtitle = {
            "user": ("My Reports", "Reports you have submitted"),
            "expert": ("Assigned Reports",
                       "Reports assigned to you for an outcome"),
        }.get(self.role, ("All Reports",
                          "Review, assign and manage every report"))
        page_header(self, heading, subtitle,
                    action=("+  New report", self.new_report))

        self.build_toolbar()

        body = tk.Frame(self, bg=T["bg"])
        body.pack(fill="both", expand=True, pady=(14, 0))
        self.build_table(body)
        self.build_details(body)
        self.clear_details()

        self.search_var.trace_add("write", lambda *args: self.populate())

    def build_toolbar(self):
        bar = tk.Frame(self, bg=T["bg"])
        bar.pack(fill="x")

        keys = [("all", "All"), ("open", "Open"), ("completed", "Completed")]
        if self.role == "admin":
            keys.append(("unassigned", "Unassigned"))
        for key, text in keys:
            chip = tk.Label(bar, font=F_SMALL_BOLD, padx=14, pady=6,
                            cursor="hand2", highlightthickness=1)
            chip.pack(side="left", padx=(0, 8))
            chip.bind("<Button-1>", lambda event, k=key: self.set_filter(k))
            self.chips[key] = (chip, text)

        self.search_var = tk.StringVar()
        search = input_box(bar, width=28, textvariable=self.search_var,
                           ipady=5)
        search.shell.pack(side="right")
        lbl(bar, "Search", F_SMALL, "muted", bg="bg").pack(
            side="right", padx=(0, 10))
        self.update_chips()

    def build_table(self, body):
        table_card = card(body)
        table_card.pack(side="left", fill="both", expand=True)

        columns = (("id", "#", 50), ("case", "Case ID", 80), ("title", "Title", 220),
                   ("author", "Author", 110),
                   ("assigned", "Assigned to", 120),
                   ("status", "Status", 110), ("submitted", "Submitted", 110))
        self.tree = ttk.Treeview(
            table_card, columns=[c[0] for c in columns], show="headings",
            selectmode="browse")
        for key, text, width in columns:
            self.tree.heading(key, text=text)
            self.tree.column(key, width=width, anchor="w",
                             stretch=(key == "title"))

        visible = {
            "user": ("id", "case", "title", "status", "submitted"),
            "expert": ("id", "case", "title", "author", "status", "submitted"),
        }
        if self.role in visible:
            self.tree.config(displaycolumns=visible[self.role])

        scrollbar = ttk.Scrollbar(
            table_card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

        self.tree.tag_configure("even", background=T["surface"])
        self.tree.tag_configure("odd", background=T["row_alt"])
        self.tree.tag_configure("Completed", foreground=T["success"])
        self.tree.tag_configure("Open", foreground=T["warning"])
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        self.empty_label = tk.Label(
            table_card, text="No reports to show yet.", font=F_BODY,
            bg=T["surface"], fg=T["muted"])

    def build_details(self, body):
        panel = card(body, width=430)
        panel.pack(side="left", fill="y", padx=(16, 0))
        panel.pack_propagate(False)

        self.scroller = ScrollFrame(panel)
        self.scroller.pack(fill="both", expand=True)
        inner = tk.Frame(self.scroller.inner, bg=T["surface"])
        inner.pack(fill="both", expand=True, padx=24, pady=22)

        head = tk.Frame(inner, bg=T["surface"])
        head.pack(fill="x")
        self.heading = lbl(head, "Report details", F_HEADING)
        self.heading.pack(side="left")
        self.status_badge = badge(head, "")
        self.status_badge.pack(side="right")

        self.info_label = lbl(inner, "", F_SMALL, "muted", anchor="w",
                              justify="left", wraplength=370)
        self.info_label.pack(fill="x", pady=(6, 14))
        separator(inner).pack(fill="x")

        field_label(inner, "Title").pack(anchor="w", pady=(16, 4))
        self.title_label = lbl(inner, "", F_SUBHEAD, anchor="w",
                               justify="left", wraplength=370)
        self.title_label.pack(fill="x")

        field_label(inner, "Description").pack(anchor="w", pady=(16, 4))
        self.description_text = text_box(inner, 6)
        self.description_text.shell.pack(fill="x")
        lbl(inner, TEXT_LOCKED_NOTE, F_SMALL, "subtle", anchor="w",
            justify="left", wraplength=370).pack(fill="x", pady=(6, 0))

        separator(inner).pack(fill="x", pady=(16, 0))

        field_label(inner, "Outcome").pack(anchor="w", pady=(16, 4))
        self.outcome_text = text_box(inner, 4)
        self.outcome_text.shell.pack(fill="x")

        field_label(inner, "Completed on (YYYY-MM-DD)").pack(
            anchor="w", pady=(14, 4))
        self.date_entry = input_box(inner, ipady=6)
        self.date_entry.shell.pack(fill="x")

        if self.role == "admin":
            field_label(inner, "Assigned to").pack(anchor="w", pady=(14, 4))
            assign_row = tk.Frame(inner, bg=T["surface"])
            assign_row.pack(fill="x")
            self.assign_var = tk.StringVar()
            self.assign_box = ttk.Combobox(
                assign_row, textvariable=self.assign_var,
                state="readonly", width=18)
            self.assign_box.pack(side="left", fill="x", expand=True)
            self.assign_button = make_button(
                assign_row, "Assign", self.assign, kind="soft", pady=5)
            self.assign_button.pack(side="left", padx=(8, 0))

        buttons = tk.Frame(inner, bg=T["surface"])
        buttons.pack(fill="x", pady=(20, 0))
        self.edit_button = make_button(
            buttons, "Edit outcome", self.start_edit, kind="soft")
        self.cancel_button = make_button(
            buttons, "Cancel", self.cancel_edit, kind="secondary")
        self.save_button = make_button(buttons, "Save outcome", self.save)
        self.set_action_buttons(edit=False, cancel=False)
        self.delete_button = make_button(
            buttons, "Delete", self.delete, kind="danger")
        if self.role == "admin":  # only admins ever see this button
            self.delete_button.pack(side="right")

        self.hint_label = lbl(inner, "", F_SMALL, "subtle", anchor="w",
                              justify="left", wraplength=370)
        self.hint_label.pack(fill="x", pady=(10, 0))

    # ----- filters -----

    def set_filter(self, key):
        self.case_filter = None
        self.filter_key = key
        self.update_chips()
        self.populate()

    def update_chips(self):
        counts = {
            "all": len(self.reports),
            "open": sum(1 for r in self.reports if not r["outcome"]),
            "completed": sum(1 for r in self.reports if r["outcome"]),
            "unassigned": sum(1 for r in self.reports
                              if not r["assigned_to"]),
        }
        for key, (chip, text) in self.chips.items():
            active = key == self.filter_key
            chip.config(
                text=f"{text}  {counts[key]}",
                bg=T["primary"] if active else T["surface"],
                fg=T["primary_text"] if active else T["muted"],
                highlightbackground=(T["primary"] if active
                                     else T["border_strong"]))

    def matches(self, report, query):
        if self.filter_key == "open" and report["outcome"]:
            return False
        if self.filter_key == "completed" and not report["outcome"]:
            return False
        if self.filter_key == "unassigned" and report["assigned_to"]:
            return False
        if not query:
            return True
        haystack = " ".join((str(report["id"]), report["title"],
                             report["author"],
                             report["assigned_to"] or "", str(report["case_id"] or ""))).lower()
        return query in haystack

    # ----- loading -----

    def refresh(self):
        reports = guarded(self, database.list_reports, self.username)
        if reports is None:
            return
        self.reports = reports

        if self.role == "admin":
            experts = guarded(self, database.list_experts, self.username)
            self.assign_box.config(values=[UNASSIGNED] + (experts or []))

        keep = (self.pending_id if self.pending_id is not None
                else self.selected_id)
        self.pending_id = None
        self.update_chips()
        self.populate(select=keep, reload=True)

    def populate(self, select=None, reload=False):
        """Fill the table from self.reports using the current filters.

        Typing in the search box calls this too, which must not wipe
        text the person is typing into the details panel, so the details
        are only reloaded when asked (reload=True) or when the selection
        really changed.
        """
        query = self.search_var.get().strip().lower()
        visible = [r for r in self.reports
                   if self.matches(r, query)
                   and (self.case_filter is None or r["case_id"] == self.case_filter)]
        target = select if select is not None else self.selected_id

        self.tree.delete(*self.tree.get_children())
        for index, report in enumerate(visible):
            status = report_status(report)
            stripe = "odd" if index % 2 else "even"
            self.tree.insert(
                "", "end", iid=str(report["id"]), tags=(stripe, status),
                values=(report["id"], report["case_id"] if report["case_id"] is not None else "Legacy", report["title"], report["author"],
                        report["assigned_to"] or "-", f"\u25cf  {status}",
                        format_date(report["created_at"])))

        if visible:
            self.empty_label.place_forget()
        else:
            self.empty_label.config(
                text=("No reports match your filters."
                      if self.reports else "No reports to show yet."))
            self.empty_label.place(relx=0.5, rely=0.45, anchor="center")

        if target is not None and self.tree.exists(str(target)):
            self.tree.selection_set(str(target))
            self.tree.see(str(target))
            if reload or target != self.selected_id:
                self.load_report(target)
        elif self.selected_id is not None or select is not None:
            self.selected_id = None
            self.clear_details()

    def focus_report(self, report_id):
        """Select a report on the next refresh (used from the home page)."""
        self.filter_key = "all"
        self.search_var.set("")
        self.pending_id = report_id

    def clear_details(self):
        self.current_report = None
        self.heading.config(text="Report details")
        self.info_label.config(
            text="Select a report from the list to view it.")
        update_badge(self.status_badge, "")
        self.title_label.config(text="")
        set_text(self.description_text, "", editable=False)
        set_text(self.outcome_text, "", editable=False)
        set_text(self.date_entry, "", editable=False)
        self.hint_label.config(text="")
        self.set_action_buttons(edit=False, cancel=False)
        set_enabled(self.save_button, False, "Save outcome")
        set_enabled(self.delete_button, False)
        if self.role == "admin":
            self.assign_var.set("")
            set_enabled(self.assign_button, False)

    def on_select(self, event=None):
        selection = self.tree.selection()
        if not selection:
            return
        report_id = int(selection[0])
        if report_id == self.selected_id:
            return  # already showing it; do not discard typed text
        self.load_report(report_id)

    def load_report(self, report_id):
        report = guarded(self, database.get_report,
                         self.username, report_id)
        if report is None:
            self.selected_id = None
            self.clear_details()
            self.refresh()
            return

        self.selected_id = report["id"]
        self.show_report(report)

    def show_report(self, report):
        self.current_report = report
        is_admin = self.role == "admin"
        can_edit = self.role in ("admin", "expert")
        has_outcome = bool(report["outcome"])
        # A report with no outcome is open for recording straight away.
        editing = can_edit and not has_outcome

        case_label = (f"Case #{report['case_id']}" if report['case_id'] is not None
                      else "Legacy report (not linked to a case)")
        info = case_label + "\n" + (f"Submitted by {report['author']} on "
                f"{format_timestamp(report['created_at'])}")
        if is_admin:
            info += f"\nAssigned to: {report['assigned_to'] or 'nobody'}"
        if report["completed_by"]:
            info += f"\nLast updated by {report['completed_by']}"
        self.heading.config(text=f"Report #{report['id']}")
        self.info_label.config(text=info)
        update_badge(self.status_badge, report_status(report))

        # Title and description are never editable, for any role.
        self.title_label.config(text=report["title"])
        set_text(self.description_text, report["description"],
                 editable=False)

        set_text(self.outcome_text, report["outcome"] or "", editing)
        date = report["completed_date"] or ""
        if editing and not date:
            date = datetime.now().strftime(database.DATE_FORMAT)
        set_text(self.date_entry, date, editing)

        self.apply_edit_state(report, editing)

        if is_admin:
            self.assign_var.set(report["assigned_to"] or UNASSIGNED)
            set_enabled(self.assign_button, True)

        self.scroller.scroll_to_top()

    def set_action_buttons(self, edit, cancel):
        """Show Edit / Cancel as needed. Save is always shown, last."""
        for button in (self.edit_button, self.cancel_button,
                       self.save_button):
            button.pack_forget()
        if edit:
            self.edit_button.pack(side="left", padx=(0, 8))
        if cancel:
            self.cancel_button.pack(side="left", padx=(0, 8))
        self.save_button.pack(side="left")

    def apply_edit_state(self, report, editing):
        """Set which buttons and hints match the current mode."""
        is_admin = self.role == "admin"
        has_outcome = bool(report["outcome"])
        can_edit = self.role in ("admin", "expert")
        self.editing = editing

        self.set_action_buttons(
            edit=can_edit and has_outcome and not editing,
            cancel=editing and has_outcome)
        set_enabled(self.save_button, editing,
                    "Save changes" if has_outcome else "Save outcome")

        if editing and has_outcome:
            hint = ("Clear both the outcome and the date, then save, to "
                    "reopen this report." if is_admin else
                    "Saving will replace the recorded outcome.")
        else:
            hint = ""
        self.hint_label.config(text=hint)
        set_enabled(self.delete_button, is_admin)

    def start_edit(self):
        """Unlock the outcome and date of a report that already has one."""
        if self.current_report is None:
            return
        self.apply_edit_state(self.current_report, True)
        set_text(self.outcome_text, self.current_report["outcome"] or "",
                 editable=True)
        set_text(self.date_entry, self.current_report["completed_date"] or "",
                 editable=True)
        self.outcome_text.focus_set()

    def cancel_edit(self):
        """Throw away unsaved changes and show the stored report again."""
        if self.current_report is not None:
            self.show_report(self.current_report)

    # ----- actions -----

    def new_report(self):
        NewReportWindow(self, self.username)

    def save(self):
        if self.selected_id is None:
            return

        outcome = self.outcome_text.get("1.0", tk.END).strip()
        date = self.date_entry.get().strip()

        if self.role == "admin":
            result = guarded(
                self, database.update_outcome, self.username,
                self.selected_id, outcome, date)
        else:
            result = guarded(
                self, database.complete_report, self.username,
                self.selected_id, outcome, date)

        self.finish_action(result)

    def assign(self):
        if self.selected_id is None:
            return

        choice = self.assign_var.get()
        expert = None if choice in ("", UNASSIGNED) else choice

        result = guarded(self, database.assign_report,
                         self.username, self.selected_id, expert)
        self.finish_action(result)

    def finish_action(self, result):
        """Show the outcome of an action, then reload the list."""
        if result is None:
            return

        success, message = result
        if success:
            messagebox.showinfo("Success", message, parent=self)
            self.refresh()
        else:
            messagebox.showerror("Error", message, parent=self)

    def delete(self):
        if self.selected_id is None:
            return
        if not messagebox.askyesno(
                "Delete report", "Delete this report permanently?",
                parent=self):
            return

        result = guarded(self, database.delete_report,
                         self.username, self.selected_id)
        if result is not None:
            self.selected_id = None
            self.refresh()


# ---------------- POPUP WINDOWS ----------------

class Popup(tk.Toplevel):
    """A modal window with a heading and a white card to put fields in."""

    def __init__(self, anchor, title, width, height, heading, subtitle=""):
        app = anchor.winfo_toplevel()
        super().__init__(app, bg=T["bg"])
        self.app = app

        self.title(title)
        self.geometry(theme.window_geometry(self, width, height, parent=app))
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()

        lbl(self, heading, F_TITLE, bg="bg").pack(
            anchor="w", padx=28, pady=(24, 4 if subtitle else 14))
        if subtitle:
            lbl(self, subtitle, F_SMALL, "muted", bg="bg",
                wraplength=width - 64, justify="left").pack(
                    anchor="w", padx=28, pady=(0, 14))

        panel = card(self)
        panel.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.body = tk.Frame(panel, bg=T["surface"])
        self.body.pack(fill="both", expand=True, padx=22, pady=20)

    def add_entry(self, label, **options):
        field_label(self.body, label).pack(anchor="w", pady=(0, 4))
        entry = input_box(self.body, **options)
        entry.shell.pack(fill="x", pady=(0, 14))
        return entry


class NewReportWindow(Popup):
    """Popup for submitting a new report."""

    def __init__(self, reports_page, username):
        super().__init__(
            reports_page, "DFIP - New Report", 540, 620, "Submit a report",
            "Titles and descriptions cannot be edited after submission, "
            "so please check them before you submit.")
        self.reports_page = reports_page
        self.username = username

        field_label(self.body, "Related case (required)").pack(anchor="w", pady=(0, 4))
        self.case_choices = database.list_case_choices()
        self.case_labels = {
            f"#{case_id} - {title}": case_id
            for case_id, title in self.case_choices
        }
        self.case_var = tk.StringVar()
        self.case_box = ttk.Combobox(
            self.body, textvariable=self.case_var, state="readonly",
            values=list(self.case_labels), width=50)
        self.case_box.pack(fill="x", pady=(0, 14))
        if self.case_choices:
            self.case_box.current(0)
        else:
            lbl(self.body, "Create a case in the Cases tab first.",
                F_SMALL, "muted").pack(anchor="w", pady=(0, 8))

        title_row = tk.Frame(self.body, bg=T["surface"])
        title_row.pack(fill="x", pady=(0, 4))
        field_label(title_row, "Title").pack(side="left")
        self.title_counter = lbl(
            title_row, f"0/{database.MAX_REPORT_TITLE_LENGTH}", F_SMALL,
            "subtle")
        self.title_counter.pack(side="right")
        self.title_entry = input_box(self.body)
        self.title_entry.shell.pack(fill="x", pady=(0, 14))

        text_row = tk.Frame(self.body, bg=T["surface"])
        text_row.pack(fill="x", pady=(0, 4))
        field_label(text_row, "Description").pack(side="left")
        self.text_counter = lbl(
            text_row, f"0/{database.MAX_REPORT_TEXT_LENGTH}", F_SMALL,
            "subtle")
        self.text_counter.pack(side="right")
        self.description_text = text_box(self.body, 9)
        self.description_text.shell.pack(fill="x", pady=(0, 18))

        buttons = tk.Frame(self.body, bg=T["surface"])
        buttons.pack(anchor="e")
        make_button(buttons, "Cancel", self.destroy,
                    kind="secondary").pack(side="left", padx=(0, 8))
        make_button(buttons, "Submit report", self.submit).pack(side="left")

        self.title_entry.bind("<KeyRelease>", self.update_counters)
        self.description_text.bind("<KeyRelease>", self.update_counters)
        self.title_entry.focus_set()

    def update_counters(self, event=None):
        title_length = len(self.title_entry.get())
        text_length = len(self.description_text.get("1.0", "end-1c"))
        self.title_counter.config(
            text=f"{title_length}/{database.MAX_REPORT_TITLE_LENGTH}",
            fg=T["danger"] if title_length > database.MAX_REPORT_TITLE_LENGTH
            else T["subtle"])
        self.text_counter.config(
            text=f"{text_length}/{database.MAX_REPORT_TEXT_LENGTH}",
            fg=T["danger"] if text_length > database.MAX_REPORT_TEXT_LENGTH
            else T["subtle"])

    def submit(self):
        result = guarded(
            self, database.submit_report, self.username,
            self.title_entry.get(),
            self.description_text.get("1.0", tk.END),
            self.case_labels.get(self.case_var.get()))
        if result is None:
            return

        success, message = result
        if success:
            self.reports_page.refresh()
            messagebox.showinfo("Success", message,
                                parent=self.reports_page)
            self.destroy()
        else:
            messagebox.showerror("Error", message, parent=self)


# ---------------- USERS PAGE (ADMIN ONLY) ----------------

class UsersPage(tk.Frame):
    def __init__(self, parent, username):
        super().__init__(parent, bg=T["bg"])
        self.username = username
        self.build()

    def build(self):
        page_header(self, "Users", "Manage roles and access",
                    action=("+  Add expert", self.add_expert))

        table_card = card(self)
        table_card.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(
            table_card,
            columns=("username", "name", "phone", "role", "status"),
            show="headings", selectmode="browse")
        for key, text, width in (("username", "Username", 140),
                                 ("name", "Full name", 220),
                                 ("phone", "Phone", 150),
                                 ("role", "Role", 100),
                                 ("status", "Status", 190)):
            self.tree.heading(key, text=text)
            self.tree.column(key, width=width, anchor="w")
        self.tree.tag_configure("even", background=T["surface"])
        self.tree.tag_configure("odd", background=T["row_alt"])
        self.tree.tag_configure("admin", foreground=T["badge_admin"][1])
        self.tree.tag_configure("expert", foreground=T["badge_expert"][1])

        scrollbar = ttk.Scrollbar(
            table_card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

        controls = card(self)
        controls.pack(fill="x", pady=(16, 0))
        row = tk.Frame(controls, bg=T["surface"])
        row.pack(fill="x", padx=22, pady=14)

        field_label(row, "Set role to").pack(side="left", padx=(0, 10))
        self.role_var = tk.StringVar(value="user")
        ttk.Combobox(
            row, textvariable=self.role_var, values=database.ROLES,
            state="readonly", width=12).pack(side="left")
        make_button(row, "Apply", self.set_role, kind="soft",
                    pady=5).pack(side="left", padx=10)
        make_button(row, "Delete user", self.delete_user,
                    kind="danger", pady=6).pack(side="right")

    def refresh(self):
        users = guarded(self, database.list_users, self.username)
        if users is None:
            return
        self.tree.delete(*self.tree.get_children())
        for index, (username, full_name, phone, role, must_change) in \
                enumerate(users):
            status = "Pending password change" if must_change else "Active"
            stripe = "odd" if index % 2 else "even"
            self.tree.insert("", "end", iid=username, tags=(stripe, role),
                             values=(username, full_name or "-",
                                     phone or "-", role, status))

    def add_expert(self):
        CreateExpertWindow(self, self.username)

    def selected_user(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Select a user",
                                "Please select a user first.", parent=self)
            return None
        return selection[0]

    def set_role(self):
        target = self.selected_user()
        if target is None:
            return
        result = guarded(self, database.set_role, self.username,
                         target, self.role_var.get())
        self.report_result(result)

    def delete_user(self):
        target = self.selected_user()
        if target is None:
            return
        if not messagebox.askyesno(
                "Delete user",
                f"Delete {target} and all of their reports?",
                parent=self):
            return
        result = guarded(self, database.delete_user, self.username, target)
        self.report_result(result)

    def report_result(self, result):
        if result is None:
            return
        success, message = result
        if success:
            self.refresh()
        else:
            messagebox.showerror("Error", message, parent=self)


class CreateExpertWindow(Popup):
    """Popup where an admin creates an expert account."""

    def __init__(self, users_page, username):
        super().__init__(
            users_page, "DFIP - Add Expert", 500, 510, "Add an expert",
            "A temporary password will be generated. The expert must "
            "change it when they first sign in.")
        self.users_page = users_page
        self.username = username

        self.full_name_entry = self.add_entry("Full name")
        self.phone_entry = self.add_entry("Phone number")
        self.username_entry = self.add_entry("Username")

        buttons = tk.Frame(self.body, bg=T["surface"])
        buttons.pack(anchor="e", pady=(4, 0))
        make_button(buttons, "Cancel", self.destroy,
                    kind="secondary").pack(side="left", padx=(0, 8))
        self.create_button = make_button(
            buttons, "Create account", self.create)
        self.create_button.pack(side="left")

        self.full_name_entry.focus_set()

    def create(self):
        full_name = self.full_name_entry.get()
        phone = self.phone_entry.get()
        username = self.username_entry.get()

        set_enabled(self.create_button, False, "Creating...")
        self.app.run_in_background(
            lambda: database.create_expert_account(
                self.username, username, full_name, phone),
            self.on_result)

    def on_result(self, ok, value):
        if not self.winfo_exists():
            return

        set_enabled(self.create_button, True, "Create account")

        if not ok:
            if isinstance(value, PermissionError):
                messagebox.showerror("Not allowed", str(value), parent=self)
            else:
                messagebox.showerror(
                    "Error", f"Something went wrong:\n{value}", parent=self)
            return

        success, message, temporary_password = value
        if not success:
            messagebox.showerror("Error", message, parent=self)
            return

        new_username = self.username_entry.get().strip()
        self.users_page.refresh()
        self.destroy()
        CredentialsWindow(self.users_page, new_username, temporary_password)


class CredentialsWindow(Popup):
    """Shows the new expert's sign-in details once, so the admin can pass
    them on."""

    def __init__(self, parent, username, temporary_password):
        super().__init__(
            parent, "DFIP - Account Created", 500, 460, "Account created",
            "Give these sign-in details to the expert. The password is "
            "not stored anywhere readable, so it will not be shown again.")
        self.username = username
        self.temporary_password = temporary_password

        for label, value in (("Username", username),
                             ("Temporary password", temporary_password)):
            entry = self.add_entry(label, font=(theme.FONT, 12, "bold"))
            set_text(entry, value, editable=False)

        self.copy_button = make_button(
            self.body, "Copy details", self.copy, kind="secondary")
        self.copy_button.pack(anchor="w")
        make_button(self.body, "Done", self.destroy).pack(
            anchor="e", pady=(10, 0))

    def copy(self):
        self.clipboard_clear()
        self.clipboard_append(
            f"Username: {self.username}\n"
            f"Temporary password: {self.temporary_password}")
        self.copy_button.config(text="Copied!")


# ---------------- ACCOUNT PAGE ----------------

class AccountPage(tk.Frame):
    def __init__(self, parent, app, username, profile, role):
        super().__init__(parent, bg=T["bg"])
        self.app = app
        self.username = username
        self.profile = profile
        self.role = role
        self.build()

    def build(self):
        page_header(self, "Account", "Your details, password and appearance")

        columns = tk.Frame(self, bg=T["bg"])
        columns.pack(fill="both", expand=True)
        left = tk.Frame(columns, bg=T["bg"])
        left.pack(side="left", fill="y", anchor="n")
        right = tk.Frame(columns, bg=T["bg"])
        right.pack(side="left", fill="y", anchor="n", padx=(20, 0))

        self.build_profile(left)
        self.build_appearance(left)
        self.build_password(right)

    def build_profile(self, parent):
        panel = card(parent)
        panel.pack(fill="x")
        inner = tk.Frame(panel, bg=T["surface"])
        inner.pack(fill="x", padx=26, pady=24)

        name = self.profile.get("full_name") or self.username
        top = tk.Frame(inner, bg=T["surface"])
        top.pack(fill="x")
        avatar(top, name, 56).pack(side="left")
        who = tk.Frame(top, bg=T["surface"])
        who.pack(side="left", padx=16)
        lbl(who, name, F_HEADING).pack(anchor="w")
        badge(who, self.role).pack(anchor="w", pady=(5, 0))

        separator(inner).pack(fill="x", pady=18)

        grid = tk.Frame(inner, bg=T["surface"])
        grid.pack(fill="x")
        rows = (("Full name", self.profile.get("full_name") or "-"),
                ("Username", self.username),
                ("Phone", self.profile.get("phone") or "-"))
        for index, (label, value) in enumerate(rows):
            field_label(grid, label).grid(
                row=index, column=0, sticky="w", padx=(0, 36), pady=5)
            lbl(grid, value, F_BODY).grid(
                row=index, column=1, sticky="w", pady=5)

    def build_appearance(self, parent):
        panel = card(parent)
        panel.pack(fill="x", pady=(18, 0))
        inner = tk.Frame(panel, bg=T["surface"])
        inner.pack(fill="x", padx=26, pady=22)

        lbl(inner, "Appearance", F_HEADING).pack(anchor="w")
        lbl(inner, "Choose how DFIP looks. Your choice is remembered on "
                   "this computer.", F_SMALL, "muted", wraplength=360,
            justify="left").pack(anchor="w", pady=(4, 14))

        row = tk.Frame(inner, bg=T["surface"])
        row.pack(anchor="w")
        for mode, text in (("light", "\u2600  Light"),
                           ("dark", "\u263e  Dark")):
            active = theme.current_mode() == mode
            make_button(
                row, text, lambda m=mode: self.app.set_theme_mode(m),
                kind="primary" if active else "secondary",
                padx=22, pady=8).pack(side="left", padx=(0, 8))

    def build_password(self, parent):
        panel = card(parent)
        panel.pack(fill="x")
        inner = tk.Frame(panel, bg=T["surface"])
        inner.pack(fill="x", padx=26, pady=24)

        lbl(inner, "Change password", F_HEADING).pack(anchor="w")
        lbl(inner, "You will need to sign in again on other devices.",
            F_SMALL, "muted").pack(anchor="w", pady=(4, 6))

        self.current_entry = self.labelled_entry(inner, "Current password")
        self.new_entry = self.labelled_entry(inner, "New password")
        self.confirm_entry = self.labelled_entry(
            inner, "Confirm new password")

        self.change_button = make_button(
            inner, "Change password", self.change_password)
        self.change_button.pack(anchor="w", pady=(6, 0))

    def refresh(self):
        pass

    @staticmethod
    def labelled_entry(parent, text):
        field_label(parent, text).pack(anchor="w", pady=(12, 4))
        entry = input_box(parent, secret=True, width=34)
        entry.shell.pack(fill="x")
        return entry

    def change_password(self):
        current = self.current_entry.get()
        new = self.new_entry.get()
        confirmation = self.confirm_entry.get()

        if not current or not new or not confirmation:
            messagebox.showerror(
                "Error", "Please fill in all fields!", parent=self)
            return

        if new != confirmation:
            messagebox.showerror(
                "Error", "New passwords do not match!", parent=self)
            return

        set_enabled(self.change_button, False, "Changing...")
        self.app.run_in_background(
            lambda: database.change_password(self.username, current, new),
            self.on_password_changed)

    def on_password_changed(self, ok, value):
        if not self.winfo_exists():
            return

        set_enabled(self.change_button, True, "Change password")

        if not ok:
            messagebox.showerror(
                "Error", f"Something went wrong:\n{value}", parent=self)
            return

        success, message = value
        if success:
            for entry in (self.current_entry, self.new_entry,
                          self.confirm_entry):
                entry.delete(0, tk.END)
            # Changing the password revoked every remembered session.
            self.app.clear_saved_session()
            messagebox.showinfo("Success", message, parent=self)
        else:
            messagebox.showerror("Error", message, parent=self)
