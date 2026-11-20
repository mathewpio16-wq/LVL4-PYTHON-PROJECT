"""DFIP desktop application: sign in and sign up.

The dashboard screens (reports, users, account) live in dashboard.py and
the shared colours/fonts/widgets (including light and dark mode) live in
theme.py.

The app is a single window. Screens (LoginFrame, DashboardFrame) are
swapped in and out by DFIPApp. Slow work (password hashing) runs in a
background thread so the window never freezes.
"""

import queue
import threading
import time
import traceback
import tkinter as tk
from tkinter import messagebox

try:
    import keyring
    import keyring.errors
    KEYRING_AVAILABLE = True
except ImportError:
    keyring = None
    KEYRING_AVAILABLE = False

import database
import theme
from dashboard import DashboardFrame
from theme import (T, F_BODY, F_CAPTION, F_SMALL, F_TITLE, card, check,
                   field_label, input_box, lbl, make_button, set_enabled,
                   theme_toggle)

# ---------------- CONFIGURATION ----------------

SERVICE_NAME = "DFIP"
TOKEN_NAME = "remembered_session"
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 30

LOGIN_SIZE = (980, 660)
LOGIN_MIN = (900, 600)
DASHBOARD_SIZE = (1360, 840)
DASHBOARD_MIN = (1100, 680)


# ---------------- REMEMBER ME (OS KEYRING) ----------------

def get_saved_token():
    if not KEYRING_AVAILABLE:
        return None
    try:
        return keyring.get_password(SERVICE_NAME, TOKEN_NAME)
    except Exception:
        return None


def save_token(token):
    """Store a session token in the OS credential store when available."""
    if not KEYRING_AVAILABLE:
        return False
    try:
        keyring.set_password(SERVICE_NAME, TOKEN_NAME, token)
        return True
    except Exception:
        return False


def delete_saved_token():
    if not KEYRING_AVAILABLE:
        return
    try:
        keyring.delete_password(SERVICE_NAME, TOKEN_NAME)
    except Exception:
        pass


# ---------------- MAIN APPLICATION ----------------

class DFIPApp(tk.Tk):
    """Root window. Owns screen switching and background work."""

    def __init__(self):
        super().__init__()
        theme.load_saved_mode()
        self.title("DFIP | Reporting Portal")
        self.configure(bg=T["bg"])
        self.minsize(*LOGIN_MIN)
        self.resizable(True, True)
        theme.apply_ttk_styles(self)

        self.current_frame = None
        self.current_spec = None  # (frame class, kwargs) for rebuilding
        self.failed_attempts = 0
        self.locked_until = 0.0

        self.protocol("WM_DELETE_WINDOW", self.destroy)

        # Stay hidden until we know whether auto-login succeeds.
        self.withdraw()
        self.after(100, self.automatic_login)

    def report_callback_exception(self, exc_type, exc_value, exc_traceback):
        """Show any error from a button/callback instead of failing silently.

        Without this, an error while building a screen leaves the window
        hidden and the problem only appears in the terminal.
        """
        traceback.print_exception(exc_type, exc_value, exc_traceback)
        self.deiconify()
        messagebox.showerror(
            "DFIP error",
            f"Something went wrong:\n\n{exc_type.__name__}: {exc_value}")

    # ----- screen switching -----

    def show_frame(self, frame_class, size, minimum, **kwargs):
        if self.current_frame is not None:
            self.current_frame.destroy()
        self.minsize(*minimum)
        self.geometry(theme.window_geometry(self, *size))
        self.current_spec = (frame_class, kwargs)
        self.current_frame = frame_class(self, **kwargs)
        self.current_frame.pack(fill="both", expand=True)
        self.deiconify()

    def show_login(self):
        self.show_frame(LoginFrame, LOGIN_SIZE, LOGIN_MIN)

    def show_dashboard(self, username):
        """Open the dashboard, or force a password change first."""
        profile = database.get_profile(username) or {}
        if profile.get("must_change_password"):
            self.show_frame(ForcePasswordFrame, LOGIN_SIZE, LOGIN_MIN,
                            username=username)
        else:
            self.show_frame(DashboardFrame, DASHBOARD_SIZE, DASHBOARD_MIN,
                            username=username)

    # ----- light / dark mode -----

    def toggle_theme(self):
        mode = "light" if theme.current_mode() == "dark" else "dark"
        self.set_theme_mode(mode)

    def set_theme_mode(self, mode):
        """Switch theme, remember it, and redraw the current screen."""
        if mode == theme.current_mode() or self.current_frame is None:
            return
        theme.set_mode(mode)
        theme.save_mode()
        # Wait until the click that triggered this has finished, because
        # the button being clicked is about to be destroyed.
        self.after_idle(self.rebuild_current_frame)

    def rebuild_current_frame(self):
        theme.apply_ttk_styles(self)
        self.configure(bg=T["bg"])

        frame_class, kwargs = self.current_spec
        state = {}
        if hasattr(self.current_frame, "capture_state"):
            state = self.current_frame.capture_state()
        kwargs = {**kwargs, **state}

        self.current_frame.destroy()
        self.current_spec = (frame_class, kwargs)
        self.current_frame = frame_class(self, **kwargs)
        self.current_frame.pack(fill="both", expand=True)

    # ----- authentication flow -----

    def automatic_login(self):
        token = get_saved_token()

        if token:
            self.run_in_background(
                lambda: database.redeem_remember_token(token),
                self.on_automatic_login_result)
        else:
            self.show_login()

    def on_automatic_login_result(self, ok, value):
        if ok and value:
            username, new_token = value
            save_token(new_token)  # tokens are single-use, so rotate
            self.show_dashboard(username)
        else:
            delete_saved_token()
            self.show_login()

    def clear_saved_session(self):
        """Forget the remembered login on this computer."""
        delete_saved_token()

    def sign_out(self):
        token = get_saved_token()
        if token:
            database.revoke_remember_token(token)
            delete_saved_token()
        self.show_login()

    # ----- background work -----

    def run_in_background(self, work, on_done):
        """Run work() in a thread, then call on_done(ok, value) in the UI."""
        results = queue.Queue()

        def target():
            try:
                results.put((True, work()))
            except Exception as error:  # reported back to the UI thread
                results.put((False, error))

        threading.Thread(target=target, daemon=True).start()

        def poll():
            try:
                ok, value = results.get_nowait()
            except queue.Empty:
                try:
                    self.after(50, poll)
                except tk.TclError:
                    pass  # window was closed
                return
            on_done(ok, value)

        poll()


# ---------------- SHARED SCREEN PIECES ----------------

def labelled_input(parent, text, secret=False, bg="surface", top=14):
    """Caption + bordered input, packed full width. Returns the Entry."""
    field_label(parent, text, bg=bg).pack(anchor="w", pady=(top, 6))
    entry = input_box(parent, secret=secret)
    entry.shell.pack(fill="x")
    return entry


def centred_card(frame, width=420):
    """Theme switch in the corner and a card centred in the window.

    Returns (card_body, footer_parent) where card_body is the padded
    frame to put widgets in.
    """
    frame.configure(bg=T["bg"])
    top = tk.Frame(frame, bg=T["bg"])
    top.pack(fill="x", padx=28, pady=(22, 0))
    theme_toggle(top, frame.app).pack(side="right")

    holder = tk.Frame(frame, bg=T["bg"])
    holder.place(relx=0.5, rely=0.5, anchor="center")
    panel = card(holder)
    panel.pack()
    tk.Frame(panel, width=width, height=1, bg=T["surface"]).pack()
    body = tk.Frame(panel, bg=T["surface"])
    body.pack(fill="both", expand=True, padx=40, pady=(6, 36))
    return body, holder


# ---------------- LOGIN SCREEN ----------------

class LoginFrame(tk.Frame):
    def __init__(self, app, prefill="", remember=False):
        super().__init__(app)
        self.app = app
        self.show_var = tk.BooleanVar()
        self.remember_var = tk.BooleanVar(value=remember)
        self.build()
        if prefill:
            self.username_entry.insert(0, prefill)
            self.password_entry.focus_set()

    def capture_state(self):
        """What to keep when the theme is switched and the screen redrawn."""
        return {"prefill": self.username_entry.get(),
                "remember": self.remember_var.get()}

    def build(self):
        self.configure(bg=T["bg"])
        self.build_hero()

        right = tk.Frame(self, bg=T["bg"])
        right.pack(side="left", fill="both", expand=True)

        top = tk.Frame(right, bg=T["bg"])
        top.pack(fill="x", padx=28, pady=(22, 0))
        theme_toggle(top, self.app).pack(side="right")

        holder = tk.Frame(right, bg=T["bg"])
        holder.place(relx=0.5, rely=0.5, anchor="center")

        panel = card(holder)
        panel.pack()
        tk.Frame(panel, width=400, height=1, bg=T["surface"]).pack()
        inner = tk.Frame(panel, bg=T["surface"])
        inner.pack(fill="both", expand=True, padx=40, pady=(8, 38))

        lbl(inner, "Welcome back", F_TITLE).pack(anchor="w", pady=(26, 0))
        lbl(inner, "Sign in to continue to your workspace.", F_BODY,
            "muted").pack(anchor="w", pady=(4, 8))

        self.username_entry = labelled_input(inner, "Username", top=18)
        self.password_entry = labelled_input(inner, "Password", secret=True)

        options = tk.Frame(inner, bg=T["surface"])
        options.pack(fill="x", pady=(14, 20))
        check(options, "Remember me", self.remember_var).pack(side="left")
        forgot = lbl(options, "Forgot password?", (theme.FONT, 9, "bold"),
                     "primary", cursor="hand2")
        forgot.pack(side="right")
        forgot.bind("<Button-1>", self.forgot_password)

        self.sign_in_button = make_button(
            inner, "Sign in", self.sign_in, pady=11)
        self.sign_in_button.pack(fill="x")

        divider = tk.Frame(inner, bg=T["surface"])
        divider.pack(fill="x", pady=16)
        tk.Frame(divider, height=1, bg=T["border"]).pack(
            side="left", fill="x", expand=True, pady=8)
        lbl(divider, "NEW HERE?", F_CAPTION, "subtle").pack(
            side="left", padx=12)
        tk.Frame(divider, height=1, bg=T["border"]).pack(
            side="left", fill="x", expand=True, pady=8)

        make_button(inner, "Create an account", self.open_signup,
                    kind="secondary", pady=10).pack(fill="x")

        lbl(holder, "Secure access  \u2022  DFIP case management system",
            F_SMALL, "subtle", bg="bg").pack(pady=(18, 0))

        self.username_entry.bind("<Return>", self.sign_in)
        self.password_entry.bind("<Return>", self.sign_in)
        self.username_entry.focus_set()

    def build_hero(self):
        """The coloured brand panel on the left."""
        hero = tk.Frame(self, bg=T["hero_bg"], width=400)
        hero.pack(side="left", fill="y")
        hero.pack_propagate(False)

        body = tk.Frame(hero, bg=T["hero_bg"])
        body.pack(fill="both", expand=True, padx=46, pady=44)

        brand = tk.Frame(body, bg=T["hero_bg"])
        brand.pack(fill="x")
        tk.Label(brand, text="D", font=(theme.FONT, 17, "bold"),
                 bg=T["primary"], fg=T["primary_text"], width=2,
                 pady=3).pack(side="left")
        lbl(brand, "DFIP", (theme.FONT, 18, "bold"), "hero_text",
            "hero_bg").pack(side="left", padx=12)

        footer = lbl(body, "REPORTING PORTAL", F_CAPTION, "hero_muted",
                     "hero_bg")
        footer.pack(side="bottom", anchor="w")

        middle = tk.Frame(body, bg=T["hero_bg"])
        middle.pack(expand=True, fill="x")
        lbl(middle, "Every report,\nfrom submission\nto outcome.",
            (theme.FONT, 27, "bold"), "hero_text", "hero_bg",
            justify="left").pack(anchor="w")
        lbl(middle, "Submit, assign and resolve reports in one secure "
                    "workspace.", F_BODY, "hero_muted", "hero_bg",
            wraplength=300, justify="left").pack(anchor="w", pady=(14, 30))

        for text in ("Submit and track your reports",
                     "Expert review with recorded outcomes",
                     "Role-based access for every team member"):
            row = tk.Frame(middle, bg=T["hero_bg"])
            row.pack(anchor="w", pady=5)
            tk.Frame(row, width=8, height=8, bg=T["primary"]).pack(
                side="left", padx=(0, 12))
            lbl(row, text, F_BODY, "hero_text", "hero_bg").pack(side="left")

    def forgot_password(self, event=None):
        messagebox.showinfo(
            "Forgot Password",
            "Password reset is not available yet.\n"
            "Please contact your DFIP administrator.",
            parent=self.app)

    def open_signup(self):
        SignUpWindow(self.app, self)

    def prefill_username(self, username):
        self.username_entry.delete(0, tk.END)
        self.username_entry.insert(0, username)
        self.password_entry.delete(0, tk.END)
        self.password_entry.focus_set()

    # ----- sign in -----

    def sign_in(self, event=None):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()

        if not username or not password:
            messagebox.showerror(
                "Error", "Please enter both username and password!",
                parent=self.app)
            return

        remaining = self.app.locked_until - time.monotonic()
        if remaining > 0:
            messagebox.showerror(
                "Too many attempts",
                f"Please wait {int(remaining) + 1} seconds and try again.",
                parent=self.app)
            return

        set_enabled(self.sign_in_button, False, "Signing in...")
        self.app.run_in_background(
            lambda: database.login_user(username, password),
            self.on_sign_in_result)

    def on_sign_in_result(self, ok, value):
        if not self.winfo_exists():
            return

        set_enabled(self.sign_in_button, True, "Sign in")

        if not ok:
            messagebox.showerror(
                "Error", f"Something went wrong:\n{value}", parent=self.app)
            return

        if value is None:
            self.register_failure()
            return

        self.app.failed_attempts = 0
        self.finish_login(value)

    def register_failure(self):
        self.app.failed_attempts += 1

        if self.app.failed_attempts >= MAX_FAILED_ATTEMPTS:
            self.app.locked_until = time.monotonic() + LOCKOUT_SECONDS
            self.app.failed_attempts = 0
            message = (f"Too many failed attempts. "
                       f"Locked for {LOCKOUT_SECONDS} seconds.")
        else:
            message = "Invalid username or password!"

        self.password_entry.delete(0, tk.END)
        messagebox.showerror("Error", message, parent=self.app)

    def finish_login(self, username):
        old_token = get_saved_token()
        if old_token:
            database.revoke_remember_token(old_token)
            delete_saved_token()

        profile = database.get_profile(username) or {}
        needs_change = profile.get("must_change_password")

        # No Remember Me until the temporary password has been replaced.
        if self.remember_var.get() and not needs_change:
            token = database.create_remember_token(username)
            if not save_token(token):
                database.revoke_remember_token(token)
                messagebox.showwarning(
                    "Remember Me unavailable",
                    "No secure credential store was found on this "
                    "computer, so you will need to sign in next time.",
                    parent=self.app)

        self.app.show_dashboard(username)


# ---------------- FORCED PASSWORD CHANGE ----------------

class ForcePasswordFrame(tk.Frame):
    """Shown to accounts that were given a temporary password."""

    def __init__(self, app, username):
        super().__init__(app)
        self.app = app
        self.username = username
        self.build()

    def build(self):
        inner, _holder = centred_card(self, width=420)

        lbl(inner, "Secure your account", F_TITLE).pack(
            anchor="w", pady=(26, 0))
        lbl(inner, "You are using a temporary password. Choose a new "
                   "password to continue.", F_BODY, "muted",
            wraplength=390, justify="left").pack(anchor="w", pady=(6, 8))

        self.current_entry = labelled_input(
            inner, "Temporary password", secret=True, top=16)
        self.new_entry = labelled_input(inner, "New password", secret=True)
        self.confirm_entry = labelled_input(
            inner, "Confirm new password", secret=True)

        self.change_button = make_button(
            inner, "Update password", self.change_password, pady=11)
        self.change_button.pack(fill="x", pady=(24, 10))
        make_button(inner, "Sign out", self.app.sign_out,
                    kind="secondary", pady=10).pack(fill="x")

        for entry in (self.current_entry, self.new_entry, self.confirm_entry):
            entry.bind("<Return>", self.change_password)
        self.current_entry.focus_set()

    def change_password(self, event=None):
        current = self.current_entry.get()
        new = self.new_entry.get()
        confirmation = self.confirm_entry.get()

        if not current or not new or not confirmation:
            messagebox.showerror(
                "Error", "Please fill in all fields!", parent=self.app)
            return

        if new != confirmation:
            messagebox.showerror(
                "Error", "New passwords do not match!", parent=self.app)
            return

        set_enabled(self.change_button, False, "Updating...")
        self.app.run_in_background(
            lambda: database.change_password(self.username, current, new),
            self.on_result)

    def on_result(self, ok, value):
        if not self.winfo_exists():
            return

        set_enabled(self.change_button, True, "Update password")

        if not ok:
            messagebox.showerror(
                "Error", f"Something went wrong:\n{value}", parent=self.app)
            return

        success, message = value
        if success:
            messagebox.showinfo("Success", message, parent=self.app)
            self.app.show_dashboard(self.username)
        else:
            messagebox.showerror("Error", message, parent=self.app)


# ---------------- SIGN UP WINDOW ----------------

class SignUpWindow(tk.Toplevel):
    def __init__(self, app, login_frame):
        super().__init__(app, bg=T["bg"])
        self.app = app
        self.login_frame = login_frame

        self.title("DFIP - Sign Up")
        self.geometry(theme.window_geometry(self, 500, 700, parent=app))
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()  # modal: only one sign-up window at a time

        self.build()

    def build(self):
        shell = tk.Frame(self, bg=T["bg"])
        shell.pack(fill="both", expand=True, padx=22, pady=22)
        panel = card(shell)
        panel.pack(fill="both", expand=True)
        inner = tk.Frame(panel, bg=T["surface"])
        inner.pack(fill="both", expand=True, padx=34, pady=(22, 26))

        lbl(inner, "Create your account", F_TITLE).pack(anchor="w")
        lbl(inner, "Enter your details to get started.", F_BODY,
            "muted").pack(anchor="w", pady=(4, 6))

        self.full_name_entry = labelled_input(inner, "Full name", top=12)
        self.phone_entry = labelled_input(inner, "Phone number", top=10)
        self.username_entry = labelled_input(inner, "Username", top=10)
        self.password_entry = labelled_input(
            inner, "Password", secret=True, top=10)
        self.confirm_entry = labelled_input(
            inner, "Confirm password", secret=True, top=10)

        self.register_button = make_button(
            inner, "Create account", self.register, pady=10)
        self.register_button.pack(fill="x", pady=(22, 8))
        make_button(inner, "Cancel", self.destroy, kind="secondary",
                    pady=9).pack(fill="x")

        self.bind("<Return>", self.register)
        self.full_name_entry.focus_set()

    def register(self, event=None):
        full_name = self.full_name_entry.get().strip()
        phone = self.phone_entry.get().strip()
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        confirmation = self.confirm_entry.get()

        if not all((full_name, phone, username, password, confirmation)):
            messagebox.showerror(
                "Error", "Please fill in all fields!", parent=self)
            return

        if password != confirmation:
            messagebox.showerror(
                "Error", "Passwords do not match!", parent=self)
            return

        set_enabled(self.register_button, False, "Creating...")
        self.app.run_in_background(
            lambda: database.register_user(
                username, password, full_name, phone),
            lambda ok, value: self.on_result(ok, value, username))

    def on_result(self, ok, value, username):
        if not self.winfo_exists():
            return

        set_enabled(self.register_button, True, "Create account")

        if not ok:
            messagebox.showerror(
                "Error", f"Something went wrong:\n{value}", parent=self)
            return

        success, message = value
        if success:
            messagebox.showinfo("Success", message, parent=self)
            self.login_frame.prefill_username(username)
            self.destroy()
        else:
            messagebox.showerror("Error", message, parent=self)


# ---------------- START APPLICATION ----------------

if __name__ == "__main__":
    DFIPApp().mainloop()
