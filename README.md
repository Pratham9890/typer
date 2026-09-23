# Human Typist

A desktop app that simulates human-like typing with configurable delays, random pauses, and a global start/stop hotkey.

## macOS Support

- Apple Silicon (M1/M2/M3/M4)
- macOS 14+
- Uses Quartz `CGEventTap` for the global hotkey
- Does **not** use `pynput`

## Features

- Paste/type any text from the app's text box
- Global start/stop hotkey
- Configurable typing speed
- Randomized letter delays
- Longer randomized symbol delays
- Random pauses while typing
- Start/stop typing without bringing the app to the foreground
- Apple Silicon macOS build

## Important: If You Have an Older Version

Before installing the new version, completely remove the old Human Typist app.

### 1. Quit the old app

If Human Typist is running, quit it first.

### 2. Remove the old app

If the old app is in Downloads:

```bash
rm -rf ~/Downloads/HumanTypist.app
```

If you previously had a version with `2` in the name:

```bash
rm -rf ~/Downloads/"HumanTypist 2.app"
```

If you installed it in Applications:

```bash
rm -rf /Applications/HumanTypist.app
```

### 3. Download the newest release

Download the latest:

```text
HumanTypist-macOS-arm64-vX.zip
```

from the project's GitHub Releases page.

### 4. Extract the ZIP

Double-click the downloaded ZIP in Finder.

You should get:

```text
HumanTypist.app
```

### 5. Move the app to Applications

Optional, but recommended:

```bash
mv ~/Downloads/HumanTypist.app /Applications/
```

If macOS says the app is already there, remove the old copy first:

```bash
rm -rf /Applications/HumanTypist.app
```

Then move the new one:

```bash
mv ~/Downloads/HumanTypist.app /Applications/
```

### 6. Remove macOS quarantine

Run:

```bash
xattr -dr com.apple.quarantine /Applications/HumanTypist.app
```

If you kept the app in Downloads instead:

```bash
xattr -dr com.apple.quarantine ~/Downloads/HumanTypist.app
```

### 7. Open Human Typist

If it is in Applications:

```bash
open /Applications/HumanTypist.app
```

If it is still in Downloads:

```bash
open ~/Downloads/HumanTypist.app
```

## macOS Permissions

The app needs permission to detect the global hotkey and control keyboard input.

Go to:

```text
System Settings → Privacy & Security → Accessibility
```

Enable **Human Typist**.

Then go to:

```text
System Settings → Privacy & Security → Input Monitoring
```

Enable **Human Typist** there as well.

If Human Typist was already listed from an older version, turn the permission off and back on after installing the new version.

If macOS does not show the app in the list, open the new app once and check the permission pages again.

## Configure the Hotkey

The default hotkey is:

```text
F8
```

You can change it in the app.

Examples:

```text
F8
```

```text
Cmd+Shift+T
```

```text
Ctrl+Alt+T
```

```text
Option+Shift+T
```

After entering a new hotkey, click **Apply**.

The hotkey field is only for entering the shortcut. It is not used for typing the text you want to send.

## Using Human Typist

1. Open Human Typist.
2. Enter the text you want to type.
3. Configure your typing settings.
4. Click into the application where the text should be typed.
5. Press your global hotkey.
6. Human Typist will start typing.
7. Press the hotkey again to stop.

## Default Settings

| Setting | Default |
|---|---:|
| Words per minute | 30 |
| Letter delay | 250–550 ms |
| Symbol delay | 550–1100 ms |
| Random pause chance | 4% |
| Random pause duration | 0.8–2.5 seconds |
| Hotkey | F8 |

## Installing From Source

You can also build the application yourself.

### 1. Clone the repository

```bash
git clone https://github.com/Pratham9890/typer.git
```

### 2. Enter the project directory

```bash
cd typer
```

### 3. Create a virtual environment

```bash
python3 -m venv .venv
```

### 4. Activate the virtual environment

```bash
source .venv/bin/activate
```

### 5. Upgrade pip

```bash
python -m pip install --upgrade pip
```

### 6. Install project dependencies

```bash
python -m pip install -r requirements.txt
```

### 7. Install PyInstaller

```bash
python -m pip install pyinstaller
```

### 8. Build the macOS app

For Apple Silicon:

```bash
python -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --target-architecture arm64 \
  --name HumanTypist \
  human_typist.py
```

The application will be created here:

```text
dist/HumanTypist.app
```

### 9. Remove quarantine from the locally built app

```bash
xattr -dr com.apple.quarantine dist/HumanTypist.app
```

### 10. Run the locally built app

```bash
open dist/HumanTypist.app
```

## Updating to a New Version

When a new release is available:

### 1. Quit Human Typist

Quit the currently running application.

### 2. Delete the old version

If installed in Applications:

```bash
rm -rf /Applications/HumanTypist.app
```

### 3. Download the newest release

Download the newest:

```text
HumanTypist-macOS-arm64-vX.zip
```

### 4. Extract it

Double-click the ZIP.

### 5. Move the new version to Applications

```bash
mv ~/Downloads/HumanTypist.app /Applications/
```

### 6. Remove quarantine

```bash
xattr -dr com.apple.quarantine /Applications/HumanTypist.app
```

### 7. Start the new version

```bash
open /Applications/HumanTypist.app
```

## GitHub Actions Builds

The repository includes a GitHub Actions workflow that automatically builds the Apple Silicon macOS application.

Every push to `main` triggers a build.

You can also start a build manually from:

```text
GitHub → Actions → Build macOS App → Run workflow
```

The workflow:

1. Installs Python 3.12.
2. Installs the required dependencies.
3. Builds an Apple Silicon `HumanTypist.app`.
4. Creates a ZIP file.
5. Creates a GitHub Release.
6. Uploads the ZIP to the release.
7. Uploads the ZIP as a GitHub Actions artifact.

## Automatic Version Numbers

Releases are automatically numbered:

```text
v1
```

```text
v2
```

```text
v3
```

and so on.

The workflow looks at the latest existing `v*` Git tag and increments it by one.

For example:

```text
Latest release: v7
```

The next build becomes:

```text
v8
```

The release asset will be named:

```text
HumanTypist-macOS-arm64-v8.zip
```

## Troubleshooting

### The global hotkey does not work

Make sure Human Typist has permission under:

```text
System Settings → Privacy & Security → Accessibility
```

and:

```text
System Settings → Privacy & Security → Input Monitoring
```

Then completely quit and reopen Human Typist.

### macOS says the app cannot be opened

Remove the quarantine attribute:

```bash
xattr -dr com.apple.quarantine /Applications/HumanTypist.app
```

Then open it:

```bash
open /Applications/HumanTypist.app
```

### The hotkey field does not capture my shortcut

Click the hotkey field, enter a supported shortcut such as:

```text
Cmd+Shift+T
```

Then click **Apply**.

The current macOS version uses Quartz directly for global hotkeys rather than `pynput`.

### The app crashes when setting a hotkey

Make sure you are using the newest release.

Older versions used `pynput` for the global keyboard listener. The current macOS version uses Apple's Quartz `CGEventTap` instead.

If you still have an old copy installed, remove it before installing the new version.

### F-keys do not work

Depending on your Mac keyboard settings, you may need to hold `Fn` when using function keys.

You can also use a modifier shortcut instead:

```text
Cmd+Shift+T
```

## Files

Main application:

```text
human_typist.py
```

Dependencies:

```text
requirements.txt
```

macOS build workflow:

```text
.github/workflows/build-macos.yml
```

## License

Add your preferred license here.
