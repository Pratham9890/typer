# Human Typist — macOS

A macOS version of Human Typist using `pynput` for the global hotkey instead of the `keyboard` package.

## Features

- 30 WPM default
- Configurable WPM
- Random letter delays
- Longer punctuation/symbol delays
- Random pauses
- Configurable pause chance and duration
- Global F1–F12 hotkey
- Start/stop while another application has focus
- PyAutoGUI-based typing

## macOS permissions

macOS may require permission for the application to control the keyboard.

Go to:

**System Settings → Privacy & Security → Accessibility**

Enable access for `HumanTypist`.

If macOS asks for Input Monitoring permission, enable it as well.

## GitHub Actions

The included workflow builds:

`dist/HumanTypist.app`

and uploads:

`HumanTypist-macOS.zip`

as a GitHub Actions artifact.

## Local build

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller

python -m PyInstaller   --noconfirm   --clean   --windowed   --name HumanTypist   human_typist.py
```

The application will be in `dist/HumanTypist.app`.
