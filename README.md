# 🎵 Vibe Standalone (Termux Edition)

[![Status](https://img.shields.io/badge/Status-Standalone_Active-success?style=for-the-badge&logo=android)](https://github.com/Ace7753/vibeandroid)
[![Platform](https://img.shields.io/badge/Platform-Android_Universal-blue?style=for-the-badge&logo=android)](https://github.com/Ace7753/vibeandroid)

**The 100% standalone music downloader for your Android device.** 
This branch (`option-2`) contains the configuration for running Vibe entirely on your phone using **Termux**. No computer, no cloud, no limits.

---

## 🚀 Quick Setup (Any Android Device)

Follow these 3 steps to turn your phone into a powerful music engine.

### 1️⃣ Install the Vibe App
Install the [**vibe.apk**](vibe.apk) found in the root of this project onto your phone. 
*Note: This is the Universal version—it works on Pixel 6, older phones, tablets, and budget devices.*

### 2️⃣ Install Termux
Use the version from the Google Play Store; it is perfectly functional and will install the engine. If it doesn't work then use **[F-Droid](https://f-droid.org/en/packages/com.termux/)**.

### 3️⃣ Start the Engine
Open Termux and paste this "Clean Start" command. It will set up everything automatically:

```bash
cd ~ && rm -rf vibeandroid && git clone https://github.com/Ace7753/vibeandroid.git && cd vibeandroid/app && pkg install python ffmpeg rust binutils git -y && pip install spotdl fastapi uvicorn python-multipart && python3 -m uvicorn main:app --host 127.0.0.1 --port 8080
```

---

## 🏁 How to use it

1.  **Wait for the Engine**: Wait until Termux shows `INFO: Uvicorn running on http://127.0.0.1:8080`.
2.  **Open Vibe**: Launch the Vibe app on your phone.
3.  **Refresh**: If the screen is blank, **long-press** anywhere on the screen and tap **"Reset to Local"**.
4.  **Download**: Paste a Spotify link and watch the music download directly to your phone's storage!

---

## ⚡ Features

- ✅ **100% Standalone**: Runs on your phone's processor. No PC required.
- ✅ **Universal APK**: Compatible with almost any modern Android device.
- ✅ **High Quality**: Downloads with metadata, synced lyrics, and album art.
- ✅ **Dual Mode**: Easily switch between **Offline Mode** (Termux) and **Cloud Mode** (Render) via the secret settings menu.

---

## 🛠️ Maintenance & Shortcuts

### The 1-Second Restart
Don't type the long command every time! Run this **once** in Termux to create a shortcut:

```bash
echo "alias vibe='cd ~/vibeandroid/app && python3 -m uvicorn main:app --host 127.0.0.1 --port 8080'" >> ~/.bashrc && source ~/.bashrc
```

**Now, to start Vibe later, just type:**  
`vibe`

### Prevent Android from sleeping
To keep downloads running in the background:
1. Open Termux.
2. Pull down your notification bar.
3. Tap **"Acquire Wake Lock"**.

---

## 📂 Project Structure (Option 2)

```text
vibe/
├── android/        # Android Studio project (Universal Client)
├── app/            # Vibe Engine (FastAPI + SpotDL logic)
├── vibe.apk        # The final installable app
└── README.md       # You are here!
```

**Built for independence. Ready to Vibe.** 🎵📱🔥
