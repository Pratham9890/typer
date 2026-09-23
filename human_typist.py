import queue
import random
import string
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import pyautogui

# macOS-only global hotkey implementation.
# This deliberately avoids pynput: on macOS 26, pynput's background
# keyboard listener can call HIToolbox/TSM from the wrong dispatch queue,
# causing EXC_BREAKPOINT / dispatch_assert_queue crashes.
import Quartz


DEFAULTS = {
    "wpm": "30",
    "letter_min": "250",
    "letter_max": "550",
    "symbol_min": "550",
    "symbol_max": "1100",
    "pause_chance": "4",
    "pause_min": "0.8",
    "pause_max": "2.5",
}

# macOS virtual key codes (US ANSI keyboard layout).
KEY_CODES = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7,
    "c": 8, "v": 9, "b": 11, "q": 12, "w": 13, "e": 14, "r": 15,
    "y": 16, "t": 17, "1": 18, "2": 19, "3": 20, "4": 21, "6": 22,
    "5": 23, "=": 24, "9": 25, "7": 26, "-": 27, "8": 28, "0": 29,
    "]": 30, "o": 31, "u": 32, "[": 33, "i": 34, "p": 35, "l": 37,
    "j": 38, "'": 39, "k": 40, ";": 41, "\\": 42, ",": 43, "/": 44,
    "n": 45, "m": 46, ".": 47, "`": 50,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97,
    "f7": 98, "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
    "space": 49, "return": 36, "enter": 36, "tab": 48, "esc": 53,
}

MODIFIERS = {
    "cmd": Quartz.kCGEventFlagMaskCommand,
    "command": Quartz.kCGEventFlagMaskCommand,
    "ctrl": Quartz.kCGEventFlagMaskControl,
    "control": Quartz.kCGEventFlagMaskControl,
    "alt": Quartz.kCGEventFlagMaskAlternate,
    "option": Quartz.kCGEventFlagMaskAlternate,
    "shift": Quartz.kCGEventFlagMaskShift,
}

EVENT_TAP_DISABLED = {
    getattr(Quartz, "kCGEventTapDisabledByTimeout", None),
    getattr(Quartz, "kCGEventTapDisabledByUserInput", None),
}


class MacHotkey:
    """Global macOS hotkey using Quartz CGEventTap."""

    def __init__(self, callback):
        self.callback = callback
        self.stop_event = threading.Event()
        self.thread = None
        self.tap = None
        self.run_loop = None
        self.queue = queue.Queue()
        self.callback_root = None
        self._poll_job = None

    def start(self, expression):
        key_code, modifiers = self._parse(expression)
        self.stop()

        self.stop_event.clear()

        def event_callback(proxy, event_type, event, refcon):
            if event_type in EVENT_TAP_DISABLED:
                if self.tap is not None:
                    Quartz.CGEventTapEnable(self.tap, True)
                return event

            if event_type == Quartz.kCGEventKeyDown:
                code = Quartz.CGEventGetIntegerValueField(
                    event,
                    Quartz.kCGKeyboardEventKeycode,
                )
                flags = Quartz.CGEventGetFlags(event)

                if code == key_code and (flags & modifiers) == modifiers:
                    self.queue.put(True)

            return event

        def runner():
            mask = 1 << Quartz.kCGEventKeyDown

            self.tap = Quartz.CGEventTapCreate(
                Quartz.kCGHIDEventTap,
                Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionListenOnly,
                mask,
                event_callback,
                None,
            )

            if not self.tap:
                self.queue.put(
                    RuntimeError(
                        "macOS denied the global keyboard event tap. "
                        "Grant HumanTypist Accessibility/Input Monitoring "
                        "permission in System Settings → "
                        "Privacy & Security."
                    )
                )
                return

            source = Quartz.CFMachPortCreateRunLoopSource(
                None,
                self.tap,
                0,
            )

            self.run_loop = Quartz.CFRunLoopGetCurrent()

            Quartz.CFRunLoopAddSource(
                self.run_loop,
                source,
                Quartz.kCFRunLoopCommonModes,
            )

            Quartz.CGEventTapEnable(self.tap, True)

            while not self.stop_event.is_set():
                Quartz.CFRunLoopRunInMode(
                    Quartz.kCFRunLoopDefaultMode,
                    0.25,
                    False,
                )

            Quartz.CGEventTapEnable(self.tap, False)

        self.thread = threading.Thread(
            target=runner,
            daemon=True,
        )
        self.thread.start()

        self._poll_queue()

    def _poll_queue(self):
        try:
            while True:
                item = self.queue.get_nowait()

                if isinstance(item, Exception):
                    raise item

                self.callback()

        except queue.Empty:
            pass

        except Exception as exc:
            self.callback(error=exc)

        if not self.stop_event.is_set() and self.callback_root:
            self._poll_job = self.callback_root.after(
                30,
                self._poll_queue,
            )

    def attach_root(self, root):
        self.callback_root = root

    def stop(self):
        self.stop_event.set()

        if self.run_loop is not None:
            Quartz.CFRunLoopStop(self.run_loop)

        self.run_loop = None
        self.tap = None

    @staticmethod
    def _parse(expression):
        text = expression.strip().lower().replace(" ", "")

        if not text:
            raise ValueError(
                "Enter a hotkey, for example F8 or Cmd+Shift+T."
            )

        parts = text.split("+")
        key = parts[-1]
        modifier_names = parts[:-1]

        if key not in KEY_CODES:
            raise ValueError(
                "Unsupported key. Use F1–F12 or a letter/number, "
                "optionally with Cmd/Ctrl/Alt/Shift."
            )

        modifiers = 0

        for name in modifier_names:
            if name not in MODIFIERS:
                raise ValueError(
                    f"Unknown modifier '{name}'. "
                    "Use Cmd, Ctrl, Alt, or Shift."
                )

            modifiers |= MODIFIERS[name]

        return KEY_CODES[key], modifiers


class HumanTypist:
    def __init__(self, root):
        self.root = root
        self.root.title("Human Typist")
        self.root.geometry("760x650")
        self.root.minsize(650, 520)

        self.stop_event = threading.Event()
        self.active = False

        self.vars = {
            key: tk.StringVar(value=value)
            for key, value in DEFAULTS.items()
        }

        self.hotkey_var = tk.StringVar(value="F8")

        self.status_var = tk.StringVar(
            value="Ready — press F8 to start/stop."
        )

        self.hotkey = MacHotkey(self._hotkey_fired)
        self.hotkey.attach_root(root)

        self._build_ui()

        try:
            self.hotkey.start("F8")
        except Exception as exc:
            self.status_var.set(f"Hotkey error: {exc}")

        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=14)
        main.pack(fill="both", expand=True)

        ttk.Label(
            main,
            text="Human Typist",
            font=("SF Pro Display", 20, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            main,
            text=(
                "Enter text, focus the target application, "
                "then press your global hotkey."
            ),
        ).pack(anchor="w", pady=(2, 10))

        text_frame = ttk.LabelFrame(
            main,
            text="Text to type",
            padding=8,
        )
        text_frame.pack(fill="both", expand=True)

        self.text_box = tk.Text(
            text_frame,
            wrap="word",
            font=("SF Mono", 12),
            undo=True,
        )
        self.text_box.pack(
            side="left",
            fill="both",
            expand=True,
        )

        scrollbar = ttk.Scrollbar(
            text_frame,
            orient="vertical",
            command=self.text_box.yview,
        )
        scrollbar.pack(side="right", fill="y")

        self.text_box.configure(
            yscrollcommand=scrollbar.set
        )

        timing = ttk.LabelFrame(
            main,
            text="Timing",
            padding=10,
        )
        timing.pack(fill="x", pady=10)

        fields = [
            ("WPM", "wpm"),
            ("Letter min (ms)", "letter_min"),
            ("Letter max (ms)", "letter_max"),
            ("Symbol min (ms)", "symbol_min"),
            ("Symbol max (ms)", "symbol_max"),
            ("Pause chance (%)", "pause_chance"),
            ("Pause min (sec)", "pause_min"),
            ("Pause max (sec)", "pause_max"),
        ]

        for i, (label, key) in enumerate(fields):
            row, col = divmod(i, 4)

            ttk.Label(
                timing,
                text=label,
            ).grid(
                row=row * 2,
                column=col,
                sticky="w",
                padx=5,
                pady=(3, 0),
            )

            ttk.Entry(
                timing,
                textvariable=self.vars[key],
                width=12,
            ).grid(
                row=row * 2 + 1,
                column=col,
                sticky="w",
                padx=5,
                pady=(0, 5),
            )

        hotkey_frame = ttk.LabelFrame(
            main,
            text="Global hotkey",
            padding=10,
        )
        hotkey_frame.pack(fill="x")

        ttk.Label(
            hotkey_frame,
            text="Hotkey:",
        ).pack(side="left")

        self.hotkey_entry = ttk.Entry(
            hotkey_frame,
            textvariable=self.hotkey_var,
            width=18,
        )
        self.hotkey_entry.pack(
            side="left",
            padx=6,
        )

        ttk.Button(
            hotkey_frame,
            text="Apply",
            command=self.apply_hotkey,
        ).pack(side="left")

        ttk.Label(
            hotkey_frame,
            text="Examples: F8, Cmd+Shift+T, Ctrl+Alt+T",
        ).pack(
            side="left",
            padx=10,
        )

        buttons = ttk.Frame(main)
        buttons.pack(
            fill="x",
            pady=(10, 0),
        )

        self.toggle_button = ttk.Button(
            buttons,
            text="Start / Stop (F8)",
            command=self.toggle_typing,
        )
        self.toggle_button.pack(side="left")

        ttk.Button(
            buttons,
            text="Clear",
            command=lambda: self.text_box.delete(
                "1.0",
                "end",
            ),
        ).pack(
            side="left",
            padx=8,
        )

        ttk.Label(
            buttons,
            textvariable=self.status_var,
        ).pack(side="right")

    def _hotkey_fired(self, error=None):
        if error is not None:
            self.status_var.set(str(error))
            return

        self.toggle_typing()

    def apply_hotkey(self):
        if self.active:
            messagebox.showwarning(
                "Busy",
                "Stop typing before changing the hotkey.",
            )
            return

        try:
            self.hotkey.start(
                self.hotkey_var.get()
            )

            self.toggle_button.config(
                text=(
                    "Start / Stop "
                    f"({self.hotkey_var.get().upper()})"
                ),
            )

            self.status_var.set(
                "Hotkey set to "
                f"{self.hotkey_var.get().upper()}."
            )

        except Exception as exc:
            messagebox.showerror(
                "Hotkey error",
                str(exc),
            )

    def _read_settings(self):
        try:
            values = {
                key: float(var.get())
                for key, var in self.vars.items()
            }
        except ValueError:
            raise ValueError(
                "All timing fields must contain numbers."
            )

        if values["wpm"] <= 0:
            raise ValueError(
                "WPM must be greater than 0."
            )

        if (
            values["letter_min"] < 0
            or values["symbol_min"] < 0
        ):
            raise ValueError(
                "Delays cannot be negative."
            )

        if values["letter_min"] > values["letter_max"]:
            raise ValueError(
                "Letter minimum cannot exceed maximum."
            )

        if values["symbol_min"] > values["symbol_max"]:
            raise ValueError(
                "Symbol minimum cannot exceed maximum."
            )

        if not 0 <= values["pause_chance"] <= 100:
            raise ValueError(
                "Pause chance must be between 0 and 100."
            )

        if (
            values["pause_min"] < 0
            or values["pause_max"] < 0
        ):
            raise ValueError(
                "Pause duration cannot be negative."
            )

        if values["pause_min"] > values["pause_max"]:
            raise ValueError(
                "Pause minimum cannot exceed maximum."
            )

        return values

    def toggle_typing(self):
        if self.active:
            self.stop_event.set()
            self.status_var.set("Stopping…")
            return

        text = self.text_box.get(
            "1.0",
            "end-1c",
        )

        if not text:
            self.status_var.set(
                "Enter some text first."
            )
            return

        try:
            settings = self._read_settings()
        except ValueError as exc:
            messagebox.showerror(
                "Timing settings",
                str(exc),
            )
            return

        self.stop_event.clear()
        self.active = True

        self.toggle_button.config(
            text="Stop typing"
        )

        self.status_var.set(
            "Typing… press the hotkey again to stop."
        )

        threading.Thread(
            target=self._typing_worker,
            args=(text, settings),
            daemon=True,
        ).start()

    def _interruptible_sleep(self, seconds):
        return not self.stop_event.wait(
            max(0.0, seconds)
        )

    def _typing_worker(self, text, settings):
        speed_scale = (
            30.0 / settings["wpm"]
        )

        symbols = set(
            string.punctuation
        )

        stopped = False

        try:
            for char in text:
                if self.stop_event.is_set():
                    stopped = True
                    break

                if char == "\n":
                    pyautogui.press("enter")

                elif char == "\t":
                    pyautogui.press("tab")

                else:
                    pyautogui.write(char)

                if char in symbols:
                    low = settings["symbol_min"]
                    high = settings["symbol_max"]
                else:
                    low = settings["letter_min"]
                    high = settings["letter_max"]

                delay = (
                    random.uniform(low, high)
                    / 1000.0
                    * speed_scale
                )

                if not self._interruptible_sleep(
                    delay
                ):
                    stopped = True
                    break

                if (
                    random.random()
                    < settings["pause_chance"] / 100.0
                ):
                    pause = random.uniform(
                        settings["pause_min"],
                        settings["pause_max"],
                    )

                    if not self._interruptible_sleep(
                        pause
                    ):
                        stopped = True
                        break

        except Exception as exc:
            stopped = True

            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Typing error",
                    str(exc),
                ),
            )

        finally:
            self.active = False
            self.stop_event.clear()

            self.root.after(
                0,
                lambda: self.toggle_button.config(
                    text=(
                        "Start / Stop "
                        f"({self.hotkey_var.get().upper()})"
                    ),
                ),
            )

            self.root.after(
                0,
                lambda: self.status_var.set(
                    "Stopped."
                    if stopped
                    else "Finished."
                ),
            )

    def close(self):
        self.stop_event.set()
        self.hotkey.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    HumanTypist(root)
    root.mainloop()        }
        self.hotkey_var = tk.StringVar(value="F8")
        self.status_var = tk.StringVar(
            value="Ready — press F8 to start/stop."
        )

        self._build_ui()
        self._start_hotkey_listener()

        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=14)
        main.pack(fill="both", expand=True)

        ttk.Label(
            main,
            text="Human Typist",
            font=("SF Pro Display", 20, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            main,
            text="Enter text, focus the target application, then press F8.",
        ).pack(anchor="w", pady=(2, 10))

        text_frame = ttk.LabelFrame(main, text="Text to type", padding=8)
        text_frame.pack(fill="both", expand=True)

        self.text_box = tk.Text(
            text_frame,
            wrap="word",
            font=("SF Mono", 12),
            undo=True,
        )
        self.text_box.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(
            text_frame,
            orient="vertical",
            command=self.text_box.yview,
        )
        scrollbar.pack(side="right", fill="y")
        self.text_box.configure(yscrollcommand=scrollbar.set)

        timing = ttk.LabelFrame(main, text="Timing", padding=10)
        timing.pack(fill="x", pady=10)

        fields = [
            ("WPM", "wpm"),
            ("Letter min (ms)", "letter_min"),
            ("Letter max (ms)", "letter_max"),
            ("Symbol min (ms)", "symbol_min"),
            ("Symbol max (ms)", "symbol_max"),
            ("Pause chance (%)", "pause_chance"),
            ("Pause min (sec)", "pause_min"),
            ("Pause max (sec)", "pause_max"),
        ]

        for i, (label, key) in enumerate(fields):
            row, col = divmod(i, 4)

            ttk.Label(timing, text=label).grid(
                row=row * 2,
                column=col,
                sticky="w",
                padx=5,
                pady=(3, 0),
            )

            ttk.Entry(
                timing,
                textvariable=self.vars[key],
                width=12,
            ).grid(
                row=row * 2 + 1,
                column=col,
                sticky="w",
                padx=5,
                pady=(0, 5),
            )

        hotkey_frame = ttk.LabelFrame(main, text="Global hotkey", padding=10)
        hotkey_frame.pack(fill="x")

        ttk.Label(hotkey_frame, text="Hotkey:").pack(side="left")

        ttk.Entry(
            hotkey_frame,
            textvariable=self.hotkey_var,
            width=12,
        ).pack(side="left", padx=6)

        ttk.Button(
            hotkey_frame,
            text="Apply",
            command=self.apply_hotkey,
        ).pack(side="left")

        ttk.Label(
            hotkey_frame,
            text="Currently supports F1–F12.",
        ).pack(side="left", padx=10)

        buttons = ttk.Frame(main)
        buttons.pack(fill="x", pady=(10, 0))

        self.toggle_button = ttk.Button(
            buttons,
            text="Start / Stop (F8)",
            command=self.toggle_typing,
        )
        self.toggle_button.pack(side="left")

        ttk.Button(
            buttons,
            text="Clear",
            command=lambda: self.text_box.delete("1.0", "end"),
        ).pack(side="left", padx=8)

        ttk.Label(
            buttons,
            textvariable=self.status_var,
        ).pack(side="right")

    def _start_hotkey_listener(self):
        self._stop_hotkey_listener()

        key_name = self.hotkey_var.get().strip().lower()

        key_map = {
            f"f{i}": getattr(pynput_keyboard.Key, f"f{i}")
            for i in range(1, 13)
        }

        if key_name not in key_map:
            raise ValueError("Hotkey must be F1 through F12.")

        self.hotkey_keys = {key_map[key_name]}

        def on_press(key):
            if key in self.hotkey_keys:
                self.root.after(0, self.toggle_typing)

        self.hotkey_listener = pynput_keyboard.Listener(on_press=on_press)
        self.hotkey_listener.daemon = True
        self.hotkey_listener.start()

    def _stop_hotkey_listener(self):
        if self.hotkey_listener is not None:
            self.hotkey_listener.stop()
            self.hotkey_listener = None

    def apply_hotkey(self):
        if self.active:
            messagebox.showwarning(
                "Busy",
                "Stop typing before changing the hotkey.",
            )
            return

        try:
            self._start_hotkey_listener()
        except Exception as exc:
            messagebox.showerror("Hotkey error", str(exc))

    def _read_settings(self):
        try:
            values = {
                key: float(var.get())
                for key, var in self.vars.items()
            }
        except ValueError:
            raise ValueError("All timing fields must contain numbers.")

        if values["wpm"] <= 0:
            raise ValueError("WPM must be greater than 0.")

        if values["letter_min"] < 0 or values["symbol_min"] < 0:
            raise ValueError("Delays cannot be negative.")

        if values["letter_min"] > values["letter_max"]:
            raise ValueError("Letter minimum cannot exceed maximum.")

        if values["symbol_min"] > values["symbol_max"]:
            raise ValueError("Symbol minimum cannot exceed maximum.")

        if not 0 <= values["pause_chance"] <= 100:
            raise ValueError("Pause chance must be between 0 and 100.")

        if values["pause_min"] < 0 or values["pause_max"] < 0:
            raise ValueError("Pause duration cannot be negative.")

        if values["pause_min"] > values["pause_max"]:
            raise ValueError("Pause minimum cannot exceed maximum.")

        return values

    def toggle_typing(self):
        if self.active:
            self.stop_event.set()
            self.status_var.set("Stopping…")
            return

        text = self.text_box.get("1.0", "end-1c")

        if not text:
            self.status_var.set("Enter some text first.")
            return

        try:
            settings = self._read_settings()
        except ValueError as exc:
            messagebox.showerror("Timing settings", str(exc))
            return

        self.stop_event.clear()
        self.active = True
        self.toggle_button.config(text="Stop typing")
        self.status_var.set("Typing… press the hotkey again to stop.")

        threading.Thread(
            target=self._typing_worker,
            args=(text, settings),
            daemon=True,
        ).start()

    def _interruptible_sleep(self, seconds):
        return not self.stop_event.wait(max(0.0, seconds))

    def _typing_worker(self, text, settings):
        # 30 WPM is the default reference. Changing WPM scales the
        # configured timing ranges proportionally.
        speed_scale = 30.0 / settings["wpm"]
        symbols = set(string.punctuation)
        stopped = False

        try:
            for char in text:
                if self.stop_event.is_set():
                    stopped = True
                    break

                if char == "\n":
                    pyautogui.press("enter")
                elif char == "\t":
                    pyautogui.press("tab")
                else:
                    pyautogui.write(char)

                if char in symbols:
                    low = settings["symbol_min"]
                    high = settings["symbol_max"]
                else:
                    low = settings["letter_min"]
                    high = settings["letter_max"]

                delay = random.uniform(low, high) / 1000.0
                delay *= speed_scale

                if not self._interruptible_sleep(delay):
                    stopped = True
                    break

                if random.random() < settings["pause_chance"] / 100.0:
                    pause = random.uniform(
                        settings["pause_min"],
                        settings["pause_max"],
                    )

                    if not self._interruptible_sleep(pause):
                        stopped = True
                        break

        except Exception as exc:
            stopped = True
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Typing error",
                    str(exc),
                ),
            )

        finally:
            self.active = False
            self.stop_event.clear()

            self.root.after(
                0,
                lambda: self.toggle_button.config(
                    text="Start / Stop (F8)"
                ),
            )

            self.root.after(
                0,
                lambda: self.status_var.set(
                    "Stopped." if stopped else "Finished."
                ),
            )

    def close(self):
        self.stop_event.set()
        self._stop_hotkey_listener()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    HumanTypist(root)
    root.mainloop()
