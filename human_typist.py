import math
import queue
import random
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import pyautogui
import Quartz

pyautogui.PAUSE = 0


DEFAULTS = {
    "wpm": 30,
    "letter_min": 250,
    "letter_max": 550,
    "symbol_min": 550,
    "symbol_max": 1100,
    "pause_chance": 4,
    "pause_min": 0.8,
    "pause_max": 2.5,
}

# macOS virtual key codes.
KEY_CODES = {
    "A": 0,
    "S": 1,
    "D": 2,
    "F": 3,
    "H": 4,
    "G": 5,
    "Z": 6,
    "X": 7,
    "C": 8,
    "V": 9,
    "B": 11,
    "Q": 12,
    "W": 13,
    "E": 14,
    "R": 15,
    "Y": 16,
    "T": 17,
    "1": 18,
    "2": 19,
    "3": 20,
    "4": 21,
    "6": 22,
    "5": 23,
    "=": 24,
    "9": 25,
    "7": 26,
    "-": 27,
    "8": 28,
    "0": 29,
    "]": 30,
    "O": 31,
    "U": 32,
    "[": 33,
    "I": 34,
    "P": 35,
    "L": 37,
    "J": 38,
    "'": 39,
    "K": 40,
    ";": 41,
    "\\": 42,
    ",": 43,
    "/": 44,
    "N": 45,
    "M": 46,
    ".": 47,
    "`": 50,
    "F1": 122,
    "F2": 120,
    "F3": 99,
    "F4": 118,
    "F5": 96,
    "F6": 97,
    "F7": 98,
    "F8": 100,
    "F9": 101,
    "F10": 109,
    "F11": 103,
    "F12": 111,
    "SPACE": 49,
    "RETURN": 36,
    "TAB": 48,
    "ESC": 53,
    "DELETE": 51,
    "FORWARD DELETE": 117,
    "LEFT": 123,
    "RIGHT": 124,
    "DOWN": 125,
    "UP": 126,
    "HOME": 115,
    "END": 119,
    "PAGE UP": 116,
    "PAGE DOWN": 121,
}

KEY_NAMES_BY_CODE = {code: name for name, code in KEY_CODES.items()}

MODIFIER_FLAGS = {
    "Command": Quartz.kCGEventFlagMaskCommand,
    "Control": Quartz.kCGEventFlagMaskControl,
    "Option": Quartz.kCGEventFlagMaskAlternate,
    "Shift": Quartz.kCGEventFlagMaskShift,
}

ALL_STANDARD_MODIFIER_MASK = (
    Quartz.kCGEventFlagMaskCommand
    | Quartz.kCGEventFlagMaskControl
    | Quartz.kCGEventFlagMaskAlternate
    | Quartz.kCGEventFlagMaskShift
)

MODIFIER_KEY_CODES = {
    54,  # Right Command
    55,  # Left Command
    56,  # Left Shift
    57,  # Caps Lock
    58,  # Left Option
    59,  # Left Control
    60,  # Right Shift
    61,  # Right Option
    62,  # Right Control
}

DISPLAY_NAMES = {
    "SPACE": "Space",
    "RETURN": "Return",
    "TAB": "Tab",
    "ESC": "Escape",
    "DELETE": "Delete",
    "FORWARD DELETE": "Forward Delete",
    "LEFT": "←",
    "RIGHT": "→",
    "UP": "↑",
    "DOWN": "↓",
    "HOME": "Home",
    "END": "End",
    "PAGE UP": "Page Up",
    "PAGE DOWN": "Page Down",
    "-": "-",
    "=": "=",
    "[": "[",
    "]": "]",
    ";": ";",
    "'": "'",
    ",": ",",
    ".": ".",
    "/": "/",
    "\\": "\\",
    "`": "`",
}

MODIFIER_SYMBOLS = {
    "Command": "⌘",
    "Control": "⌃",
    "Option": "⌥",
    "Shift": "⇧",
}



class MacHotkey:
    """Global macOS hotkey listener using a Quartz CGEventTap."""

    def __init__(self, root, callback):
        self.root = root
        self.callback = callback
        self.queue = queue.Queue()
        self.thread = None
        self.stop_event = threading.Event()
        self.key_name = "F8"
        self.modifiers = []
        self.poll_job = None
        self.run_loop = None

    def configure(self, key_name, modifiers):
        if key_name not in KEY_CODES:
            raise ValueError(f"Unsupported hotkey key: {key_name}")
        self.key_name = key_name
        self.modifiers = [m for m in modifiers if m in MODIFIER_FLAGS]

    def start(self):
        self.stop()

        while True:
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break

        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="QuartzHotkeyListener",
        )
        self.thread.start()
        self.poll_job = self.root.after(30, self.poll)

    def stop(self):
        self.stop_event.set()

        if self.poll_job is not None:
            try:
                self.root.after_cancel(self.poll_job)
            except tk.TclError:
                pass
            self.poll_job = None

        if self.run_loop is not None:
            try:
                Quartz.CFRunLoopStop(self.run_loop)
            except Exception:
                pass

        thread = self.thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.0)

        self.thread = None
        self.run_loop = None

    def poll(self):
        try:
            while True:
                item = self.queue.get_nowait()

                kind = item[0] if isinstance(item, tuple) else item

                if kind == "trigger":
                    self.callback()
                elif kind == "error":
                    self.stop_event.set()
                    message = item[1]
                    self.root.after(
                        0,
                        lambda text=message: messagebox.showerror(
                            "Hotkey Error",
                            text,
                        ),
                    )
        except queue.Empty:
            pass

        if not self.stop_event.is_set():
            self.poll_job = self.root.after(30, self.poll)

    def _run(self):
        key_code = KEY_CODES.get(self.key_name)
        if key_code is None:
            self.queue.put(("error", f"Unsupported key: {self.key_name}"))
            return

        required_mask = 0
        for modifier in self.modifiers:
            required_mask |= MODIFIER_FLAGS[modifier]

        def callback(proxy, event_type, event, refcon):
            if event_type in (
                Quartz.kCGEventTapDisabledByTimeout,
                Quartz.kCGEventTapDisabledByUserInput,
            ):
                if not self.stop_event.is_set():
                    Quartz.CGEventTapEnable(tap, True)
                return event

            if self.stop_event.is_set():
                return event

            if event_type != Quartz.kCGEventKeyDown:
                return event

            code = Quartz.CGEventGetIntegerValueField(
                event,
                Quartz.kCGKeyboardEventKeycode,
            )

            if code != key_code:
                return event

            # Do not trigger repeatedly while the key is held.
            try:
                autorepeat = Quartz.CGEventGetIntegerValueField(
                    event,
                    Quartz.kCGKeyboardEventAutorepeat,
                )
                if autorepeat:
                    return event
            except Exception:
                pass

            flags = Quartz.CGEventGetFlags(event)
            standard_flags = flags & ALL_STANDARD_MODIFIER_MASK

            if standard_flags == required_mask:
                self.queue.put(("trigger",))

            return event

        event_mask = 1 << Quartz.kCGEventKeyDown

        tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionListenOnly,
            event_mask,
            callback,
            None,
        )

        if tap is None:
            self.stop_event.set()
            self.queue.put(
                (
                    "error",
                    "macOS blocked the global hotkey listener.\n\n"
                    "Enable Human Typist in:\n"
                    "System Settings → Privacy & Security → Accessibility\n"
                    "and\n"
                    "System Settings → Privacy & Security → Input Monitoring.",
                )
            )
            return

        source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
        run_loop = Quartz.CFRunLoopGetCurrent()
        self.run_loop = run_loop

        Quartz.CFRunLoopAddSource(
            run_loop,
            source,
            Quartz.kCFRunLoopCommonModes,
        )
        Quartz.CGEventTapEnable(tap, True)

        try:
            while not self.stop_event.is_set():
                Quartz.CFRunLoopRunInMode(
                    Quartz.kCFRunLoopDefaultMode,
                    0.25,
                    False,
                )
        finally:
            Quartz.CGEventTapEnable(tap, False)
            self.run_loop = None


class HotkeyRecorder:
    """Temporary Quartz event tap that records one key + its modifiers."""

    def __init__(self, root, captured_callback, error_callback):
        self.root = root
        self.captured_callback = captured_callback
        self.error_callback = error_callback
        self.queue = queue.Queue()
        self.stop_event = threading.Event()
        self.thread = None
        self.poll_job = None
        self.run_loop = None

    def start(self):
        self.stop()

        while True:
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break

        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="QuartzHotkeyRecorder",
        )
        self.thread.start()
        self.poll_job = self.root.after(20, self.poll)

    def stop(self):
        self.stop_event.set()

        if self.poll_job is not None:
            try:
                self.root.after_cancel(self.poll_job)
            except tk.TclError:
                pass
            self.poll_job = None

        if self.run_loop is not None:
            try:
                Quartz.CFRunLoopStop(self.run_loop)
            except Exception:
                pass

        thread = self.thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.0)

        self.thread = None
        self.run_loop = None

    def poll(self):
        try:
            while True:
                item = self.queue.get_nowait()
                kind = item[0]

                if kind == "captured":
                    self.stop_event.set()
                    self.captured_callback(item[1], item[2])
                elif kind == "error":
                    self.stop_event.set()
                    self.error_callback(item[1])
        except queue.Empty:
            pass

        if not self.stop_event.is_set():
            self.poll_job = self.root.after(20, self.poll)
        else:
            self.poll_job = None

    def _run(self):
        def callback(proxy, event_type, event, refcon):
            if event_type in (
                Quartz.kCGEventTapDisabledByTimeout,
                Quartz.kCGEventTapDisabledByUserInput,
            ):
                if not self.stop_event.is_set():
                    Quartz.CGEventTapEnable(tap, True)
                return event

            if self.stop_event.is_set():
                return event

            if event_type != Quartz.kCGEventKeyDown:
                return event

            key_code = Quartz.CGEventGetIntegerValueField(
                event,
                Quartz.kCGKeyboardEventKeycode,
            )

            if key_code in MODIFIER_KEY_CODES:
                return event

            key_name = KEY_NAMES_BY_CODE.get(key_code)
            if not key_name:
                self.queue.put(
                    (
                        "error",
                        f"That key is not supported by Human Typist "
                        f"(macOS key code {key_code}).",
                    )
                )
                return event

            try:
                autorepeat = Quartz.CGEventGetIntegerValueField(
                    event,
                    Quartz.kCGKeyboardEventAutorepeat,
                )
                if autorepeat:
                    return event
            except Exception:
                pass

            flags = Quartz.CGEventGetFlags(event)
            modifiers = [
                name
                for name in ("Command", "Control", "Option", "Shift")
                if flags & MODIFIER_FLAGS[name]
            ]

            self.queue.put(("captured", key_name, modifiers))
            self.stop_event.set()
            return event

        event_mask = 1 << Quartz.kCGEventKeyDown

        tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionListenOnly,
            event_mask,
            callback,
            None,
        )

        if tap is None:
            self.stop_event.set()
            self.queue.put(
                (
                    "error",
                    "macOS could not start the key recorder.\n\n"
                    "Make sure Human Typist has Accessibility and "
                    "Input Monitoring permissions.",
                )
            )
            return

        source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
        run_loop = Quartz.CFRunLoopGetCurrent()
        self.run_loop = run_loop

        Quartz.CFRunLoopAddSource(
            run_loop,
            source,
            Quartz.kCFRunLoopCommonModes,
        )
        Quartz.CGEventTapEnable(tap, True)

        try:
            while not self.stop_event.is_set():
                Quartz.CFRunLoopRunInMode(
                    Quartz.kCFRunLoopDefaultMode,
                    0.25,
                    False,
                )
        finally:
            Quartz.CGEventTapEnable(tap, False)
            self.run_loop = None


class HumanTypist:
    def __init__(self, root):
        self.root = root
        self.root.title("Human Typist")
        self.root.geometry("760x700")
        self.root.minsize(650, 600)

        self.typing = False
        self.typing_thread = None
        self.stop_typing_event = threading.Event()
        self.ui_queue = queue.Queue()
        self.ui_poll_job = None
        self.typing_generation = 0

        self.hotkey = MacHotkey(root, self.toggle_typing)
        self.recorder = HotkeyRecorder(
            root,
            self._handle_recorded_hotkey,
            self._handle_recording_error,
        )

        self.hotkey_key = "F8"
        self.hotkey_modifiers = []
        self.recording_hotkey = False

        self.wpm_var = tk.StringVar(value=str(DEFAULTS["wpm"]))
        self.letter_min_var = tk.StringVar(value=str(DEFAULTS["letter_min"]))
        self.letter_max_var = tk.StringVar(value=str(DEFAULTS["letter_max"]))
        self.symbol_min_var = tk.StringVar(value=str(DEFAULTS["symbol_min"]))
        self.symbol_max_var = tk.StringVar(value=str(DEFAULTS["symbol_max"]))
        self.pause_chance_var = tk.StringVar(value=str(DEFAULTS["pause_chance"]))
        self.pause_min_var = tk.StringVar(value=str(DEFAULTS["pause_min"]))
        self.pause_max_var = tk.StringVar(value=str(DEFAULTS["pause_max"]))

        self.build_ui()
        self.apply_saved_hotkey()
        self.ui_poll_job = self.root.after(30, self.poll_ui_queue)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def build_ui(self):
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text="Human Typist",
            font=("SF Pro Display", 24, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            outer,
            text="Type naturally with randomized timing and a global start/stop shortcut.",
        ).pack(anchor="w", pady=(2, 15))

        text_frame = ttk.LabelFrame(outer, text="Text to type", padding=10)
        text_frame.pack(fill="both", expand=True)

        self.text_box = tk.Text(
            text_frame,
            height=12,
            wrap="word",
            font=("SF Mono", 13),
            undo=True,
        )
        self.text_box.pack(fill="both", expand=True)

        settings = ttk.LabelFrame(outer, text="Typing settings", padding=10)
        settings.pack(fill="x", pady=(14, 0))

        self.add_setting(settings, "Words per minute", self.wpm_var, 0, 0)
        self.add_setting(settings, "Letter min (ms)", self.letter_min_var, 0, 2)
        self.add_setting(settings, "Letter max (ms)", self.letter_max_var, 0, 4)
        self.add_setting(settings, "Symbol min (ms)", self.symbol_min_var, 1, 0)
        self.add_setting(settings, "Symbol max (ms)", self.symbol_max_var, 1, 2)
        self.add_setting(settings, "Pause chance (%)", self.pause_chance_var, 1, 4)
        self.add_setting(settings, "Pause min (sec)", self.pause_min_var, 2, 0)
        self.add_setting(settings, "Pause max (sec)", self.pause_max_var, 2, 2)

        hotkey_frame = ttk.LabelFrame(
            outer,
            text="Global start / stop hotkey",
            padding=12,
        )
        hotkey_frame.pack(fill="x", pady=(14, 0))

        self.hotkey_button = ttk.Button(
            hotkey_frame,
            text="",
            command=self.begin_hotkey_recording,
        )
        self.hotkey_button.pack(
            side="left",
            ipadx=18,
            ipady=8,
        )

        ttk.Label(
            hotkey_frame,
            text="Click the shortcut to change it.",
        ).pack(side="left", padx=(14, 0))

        self.hotkey_status_var = tk.StringVar(
            value="Your shortcut starts and stops typing globally."
        )
        ttk.Label(
            hotkey_frame,
            textvariable=self.hotkey_status_var,
        ).pack(side="left", padx=(14, 0))

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(16, 0))

        self.status_var = tk.StringVar(value="Ready — press your hotkey to start.")
        ttk.Label(
            controls,
            textvariable=self.status_var,
        ).pack(side="left", fill="x", expand=True)

        self.start_button = ttk.Button(
            controls,
            text="Start Typing",
            command=self.toggle_typing,
        )
        self.start_button.pack(side="right")

        self.update_hotkey_display()

    def add_setting(self, parent, label, variable, row, column):
        ttk.Label(parent, text=label).grid(
            row=row,
            column=column,
            sticky="w",
            padx=(0, 6),
            pady=4,
        )
        ttk.Entry(
            parent,
            textvariable=variable,
            width=10,
        ).grid(
            row=row,
            column=column + 1,
            sticky="w",
            padx=(0, 18),
            pady=4,
        )

    def hotkey_display(self, key=None, modifiers=None):
        key = key or self.hotkey_key
        modifiers = self.hotkey_modifiers if modifiers is None else modifiers

        parts = [MODIFIER_SYMBOLS[m] for m in modifiers]
        parts.append(DISPLAY_NAMES.get(key, key))
        return " ".join(parts)

    def update_hotkey_display(self):
        display = self.hotkey_display()
        self.hotkey_button.configure(text=display)

    def set_hotkey_recording_ui(self, recording):
        if recording:
            self.hotkey_button.configure(
                text="Listening…",
                state="disabled",
            )
        else:
            self.hotkey_button.configure(
                text=self.hotkey_display(),
                state="normal",
            )

    def apply_saved_hotkey(self):
        try:
            self.hotkey.configure(self.hotkey_key, self.hotkey_modifiers)
            self.hotkey.start()
        except ValueError as exc:
            messagebox.showerror("Hotkey Error", str(exc))

    def begin_hotkey_recording(self):
        if self.recording_hotkey:
            return

        self.recording_hotkey = True
        self.hotkey.stop()
        self.set_hotkey_recording_ui(True)
        self.recorder.start()

        dialog = tk.Toplevel(self.root)
        self.recording_window = dialog
        dialog.title("Set Hotkey")
        dialog.geometry("480x250")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.protocol("WM_DELETE_WINDOW", self.cancel_hotkey_recording)

        frame = ttk.Frame(dialog, padding=24)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text="Set your hotkey",
            font=("SF Pro Display", 20, "bold"),
        ).pack(pady=(0, 8))

        ttk.Label(
            frame,
            text="Press a key or key combination.\n"
            "Examples: F8, ⌘ ⇧ T, or ⌥ ⇧ T",
            justify="center",
        ).pack()

        self.recording_display_var = tk.StringVar(
            value="Waiting for input…"
        )
        ttk.Label(
            frame,
            textvariable=self.recording_display_var,
            font=("SF Pro Display", 22, "bold"),
        ).pack(pady=18)

        self.set_hotkey_button = ttk.Button(
            frame,
            text="Set Hotkey",
            command=self.confirm_hotkey_recording,
            state="disabled",
        )
        self.set_hotkey_button.pack(side="left", padx=(70, 5))

        ttk.Button(
            frame,
            text="Cancel",
            command=self.cancel_hotkey_recording,
        ).pack(side="left", padx=5)

        dialog.focus_force()

    def _handle_recorded_hotkey(self, key_name, modifiers):
        if not self.recording_hotkey:
            return

        self.recorded_key = key_name
        self.recorded_modifiers = list(modifiers)

        self.recording_display_var.set(
            self.hotkey_display(key_name, modifiers)
        )
        self.set_hotkey_button.configure(state="normal")

    def _handle_recording_error(self, message):
        if not self.recording_hotkey:
            return

        self.cancel_hotkey_recording()
        messagebox.showerror("Could Not Record Hotkey", message)

    def confirm_hotkey_recording(self):
        if not self.recording_hotkey:
            return

        if not getattr(self, "recorded_key", None):
            return

        new_key = self.recorded_key
        new_modifiers = list(self.recorded_modifiers)

        try:
            self.hotkey.configure(new_key, new_modifiers)
        except ValueError as exc:
            messagebox.showerror("Invalid Hotkey", str(exc))
            return

        self.hotkey_key = new_key
        self.hotkey_modifiers = new_modifiers

        self.recorder.stop()
        self.recording_hotkey = False

        if self.recording_window is not None:
            try:
                self.recording_window.grab_release()
                self.recording_window.destroy()
            except tk.TclError:
                pass
            self.recording_window = None

        self.hotkey.start()
        self.set_hotkey_recording_ui(False)

        self.update_hotkey_display()
        self.hotkey_status_var.set(
            f"Hotkey set to {self.hotkey_display()}."
        )
        self.status_var.set(
            f"Ready — press {self.hotkey_display()} to start."
        )

    def cancel_hotkey_recording(self):
        if not self.recording_hotkey:
            return

        self.recorder.stop()
        self.recording_hotkey = False

        if getattr(self, "recording_window", None) is not None:
            try:
                self.recording_window.grab_release()
                self.recording_window.destroy()
            except tk.TclError:
                pass
            self.recording_window = None

        self.hotkey.start()
        self.set_hotkey_recording_ui(False)

        self.hotkey_status_var.set("Hotkey unchanged.")

    def read_settings(self):
        try:
            values = {
                "wpm": float(self.wpm_var.get()),
                "letter_min": float(self.letter_min_var.get()),
                "letter_max": float(self.letter_max_var.get()),
                "symbol_min": float(self.symbol_min_var.get()),
                "symbol_max": float(self.symbol_max_var.get()),
                "pause_chance": float(self.pause_chance_var.get()),
                "pause_min": float(self.pause_min_var.get()),
                "pause_max": float(self.pause_max_var.get()),
            }
        except ValueError:
            raise ValueError("All timing settings must contain numbers.")

        if not all(math.isfinite(value) for value in values.values()):
            raise ValueError("Timing settings must contain finite numbers.")

        if values["wpm"] <= 0:
            raise ValueError("Words per minute must be greater than 0.")

        if values["letter_min"] < 0 or values["letter_max"] < 0:
            raise ValueError("Letter delays cannot be negative.")

        if values["symbol_min"] < 0 or values["symbol_max"] < 0:
            raise ValueError("Symbol delays cannot be negative.")

        if values["letter_min"] > values["letter_max"]:
            raise ValueError("Letter minimum cannot be greater than maximum.")

        if values["symbol_min"] > values["symbol_max"]:
            raise ValueError("Symbol minimum cannot be greater than maximum.")

        if values["pause_min"] < 0 or values["pause_max"] < 0:
            raise ValueError("Pause durations cannot be negative.")

        if values["pause_min"] > values["pause_max"]:
            raise ValueError("Pause minimum cannot be greater than maximum.")

        if not 0 <= values["pause_chance"] <= 100:
            raise ValueError("Pause chance must be between 0 and 100.")

        return values

    def poll_ui_queue(self):
        try:
            while True:
                item = self.ui_queue.get_nowait()
                kind = item[0]
                generation = item[1]

                if generation != self.typing_generation:
                    continue

                if kind == "typing_error":
                    messagebox.showerror("Typing Error", item[2])
                    self.typing_finished()
                elif kind == "typing_finished":
                    self.typing_finished()
        except queue.Empty:
            pass

        self.ui_poll_job = self.root.after(30, self.poll_ui_queue)

    def toggle_typing(self):
        if self.typing:
            self.stop_typing()
        else:
            self.start_typing()

    def start_typing(self):
        text = self.text_box.get("1.0", "end-1c")
        if not text:
            messagebox.showwarning("No text", "Enter some text first.")
            return

        try:
            settings = self.read_settings()
        except ValueError as exc:
            messagebox.showerror("Invalid settings", str(exc))
            return

        if self.typing_thread and self.typing_thread.is_alive():
            return

        self.stop_typing_event.clear()
        self.typing_generation += 1
        generation = self.typing_generation
        self.typing = True
        self.start_button.configure(text="Stop Typing")
        self.status_var.set("Typing...")

        self.typing_thread = threading.Thread(
            target=self.type_text,
            args=(text, settings, generation),
            daemon=True,
            name="HumanTypistWriter",
        )
        self.typing_thread.start()

    def stop_typing(self):
        self.stop_typing_event.set()
        self.typing_generation += 1
        self.typing = False
        self.start_button.configure(text="Start Typing")
        self.status_var.set("Stopped.")

    def interruptible_sleep(self, seconds):
        end = time.monotonic() + seconds

        while time.monotonic() < end:
            if self.stop_typing_event.is_set():
                return False

            time.sleep(min(0.02, max(0.001, end - time.monotonic())))

        return True

    def type_text(self, text, settings, generation):
        try:
            speed_scale = 30.0 / settings["wpm"]

            for char in text:
                if self.stop_typing_event.is_set():
                    break

                if char == "\n":
                    pyautogui.press("enter")
                    base_delay = random.uniform(
                        settings["symbol_min"],
                        settings["symbol_max"],
                    ) / 1000.0

                elif char == "\t":
                    pyautogui.press("tab")
                    base_delay = random.uniform(
                        settings["symbol_min"],
                        settings["symbol_max"],
                    ) / 1000.0

                else:
                    if not self._type_character(char):
                        raise ValueError(
                            f"Unsupported character: {char!r}\n"
                            "Use standard keyboard characters."
                        )

                    if char.isalpha() or char.isdigit():
                        base_delay = random.uniform(
                            settings["letter_min"],
                            settings["letter_max"],
                        ) / 1000.0
                    else:
                        base_delay = random.uniform(
                            settings["symbol_min"],
                            settings["symbol_max"],
                        ) / 1000.0

                base_delay *= speed_scale

                if not self.interruptible_sleep(base_delay):
                    break

                if random.random() < settings["pause_chance"] / 100.0:
                    pause = random.uniform(
                        settings["pause_min"],
                        settings["pause_max"],
                    )
                    if not self.interruptible_sleep(pause):
                        break

        except Exception as exc:
            self.ui_queue.put(("typing_error", generation, str(exc)))
        finally:
            self.ui_queue.put(("typing_finished", generation))

    @staticmethod
    def _type_character(char):
        try:
            pyautogui.write(char)
            return True
        except Exception:
            return False

    def typing_finished(self):
        self.typing = False
        self.stop_typing_event.clear()
        self.start_button.configure(text="Start Typing")
        self.status_var.set("Finished — ready.")

    def on_close(self):
        self.stop_typing_event.set()
        self.typing_generation += 1

        if self.ui_poll_job is not None:
            try:
                self.root.after_cancel(self.ui_poll_job)
            except tk.TclError:
                pass
            self.ui_poll_job = None

        self.recorder.stop()
        self.hotkey.stop()

        if getattr(self, "recording_window", None) is not None:
            try:
                self.recording_window.destroy()
            except tk.TclError:
                pass

        self.root.destroy()


def main():
    root = tk.Tk()
    HumanTypist(root)
    root.mainloop()


if __name__ == "__main__":
    main()
