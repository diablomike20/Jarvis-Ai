# -*- mode: python ; coding: utf-8 -*-
import os
import sys

cwd = os.path.abspath(os.getcwd())
# A single installer is built locally with the three editor CLIs already
# compiled. JARVIS_BUNDLED_ENGINE_DIR is set by build_full_jarvis.ps1.
engine_stage = os.environ.get("JARVIS_BUNDLED_ENGINE_DIR", "").strip()
engine_datas = []
if engine_stage:
    for app in ("photocraft", "lightcraft", "filmcraft"):
        root = os.path.join(engine_stage, app)
        executable = os.path.join(root, app + "-cli.exe")
        if not os.path.isfile(executable):
            raise FileNotFoundError("Required bundled editor engine is missing: " + executable)
        engine_datas.append((executable, os.path.join("editor_engines", app)))
        for name in sorted(os.listdir(root)):
            if name.lower().endswith(".dll"):
                engine_datas.append(
                    (os.path.join(root, name), os.path.join("editor_engines", app))
                )
    licenses = os.path.join(engine_stage, "licenses")
    if os.path.isdir(licenses):
        engine_datas.append((licenses, "licenses" + os.sep + "editor_engines"))


a = Analysis(
    [os.path.join(cwd, 'main.py')],
    pathex=[],
    binaries=[],
    datas=[
        (os.path.join(cwd, 'assets'), 'assets'),
        (os.path.join(cwd, 'config'), 'config'),
        (os.path.join(cwd, 'core'), 'core'),
        (os.path.join(cwd, 'brahma_connect'), 'brahma_connect'),
        (os.path.join(cwd, 'actions'), 'actions'),
        (os.path.join(cwd, 'dashboard/static'), 'dashboard/static'),
        (os.path.join(cwd, 'smart_home'), 'smart_home'),
        (os.path.join(cwd, 'memory'), 'memory'),
        (os.path.join(cwd, 'plugins'), 'plugins'),
        (os.path.join(cwd, 'features'), 'features'),
        (os.path.join(cwd, 'workspace_store.py'), '.'),
        (os.path.join(cwd, 'README.md'), '.'),
        (os.path.join(cwd, 'requirements.txt'), '.'),
        (os.path.join(cwd, 'version.txt'), '.'),
        (os.path.join(cwd, 'integrations', 'sources'), 'integrations/sources'),
        (os.path.join(cwd, 'docs', 'SOURCE_PLUGINS_HU.md'), 'docs'),
        (os.path.join(cwd, 'docs', 'CREATIVE_STUDIO_HU.md'), 'docs'),
    ] + engine_datas,
    hiddenimports=[
        'mediapipe', 'cv2', 'instagrapi', 'PyQt6', 'PyQt6.QtWebEngineCore',
        'PyQt6.QtWebEngineWidgets', 'PyQt6.QtWebChannel', 'pyautogui', 'sounddevice',
        'keyboard', 'docx', 'pptx', 'multipart', 'passlib', 'bcrypt', 'aiohttp', 'websockets',
        'uvicorn', 'fastapi', 'plyer', 'pydantic', 'typing_extensions', 'requests', 'beautifulsoup4',
        'pyaudio', 'numpy'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# STRICT EXCLUSIONS FOR PERSONAL DATA
excluded_files = [
    'ig_browser_profile',
    'patch_backups',
    'patch_history.json',
    'api_keys.json',
    'ig_session.json',
    'email_credentials.json',
    'identity.json',
    'device_location_cache.json',
    'learned_rules.json',
    'organizer_history.json',
    'calendar_events.json',
    'long_term.json',
    'nutrition_log.json',
    'brahma_connect.json',
    'devices.json'
]

a.datas = [x for x in a.datas if not any(excl in x[0].replace('\\', '/') for excl in excluded_files)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BrahmaEvo',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(cwd, 'assets/Brahma_Lite_Logo.ico') if os.path.exists(os.path.join(cwd, 'assets/Brahma_Lite_Logo.ico')) else None,
    version=os.path.join(cwd, 'version.txt') if os.path.exists(os.path.join(cwd, 'version.txt')) else None
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BrahmaEvo'
)
