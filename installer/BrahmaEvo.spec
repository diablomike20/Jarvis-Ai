# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata, collect_dynamic_libs

cwd = os.path.abspath(os.getcwd())

# Package the reconstructed Claude Code build and the Node runtime, not the
# official installed CLI. The full installer build sets REQUIRE=1 to fail
# instead of silently shipping without the engine.
claude_dist = os.path.join(cwd, 'runtime', 'claude-code', 'dist')
node_binary = os.path.join(cwd, 'runtime', 'node', 'node.exe')
runtime_datas = []
if os.path.isfile(os.path.join(claude_dist, 'cli.js')) and os.path.isdir(
    os.path.join(claude_dist, 'cli.bundle')
):
    runtime_datas.append((claude_dist, 'runtime/claude-code/dist'))
if os.path.isfile(node_binary):
    runtime_datas.append((node_binary, 'runtime/node'))
if os.environ.get('BRAHMA_REQUIRE_CLAUDE_BUNDLE') == '1' and len(runtime_datas) != 2:
    raise RuntimeError(
        'Full JARVIS package requires runtime/claude-code/dist and '
        'runtime/node/node.exe. Run installer/prepare_claude_runtime.ps1.'
    )

a = Analysis(
    [os.path.join(cwd, 'main.py')],
    pathex=[],
    binaries=[*collect_dynamic_libs('torchcodec')],
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
        *collect_data_files('imageio_ffmpeg', includes=['binaries/*']),
        # The *real* F5 runtime opens configs/F5TTS_v1_Base.yaml via
        # importlib.resources. collect_submodules alone omits this YAML.
        *collect_data_files('f5_tts'),
        # Coqui imports TTS.vocoder.configs.__init__ and enumerates sibling .py
        # files with os.listdir(Path(__file__).parent). PyInstaller normally
        # keeps .py in PYZ (not on disk), causing WinError 3 at EXE startup.
        # Ship actual source files for the installed Coqui distribution.
        *collect_data_files('TTS', include_py_files=True),
        # XTTS imports ko_speech_tools.g2p, which dynamically resolves
        # importlib.resources.files('ko_speech_tools.data'). PyInstaller
        # misses that package/data tree unless bundled explicitly.
        *collect_data_files('ko_speech_tools', include_py_files=True),
        # Transformers checks installed torchcodec distribution metadata at import.
        # PyInstaller does NOT copy *.dist-info automatically, despite copying
        # torchcodec's Python package; the frozen EXE crashed here in CI.
        *copy_metadata('torchcodec'),
        *copy_metadata('torch'),
        *copy_metadata('torchaudio'),
        *copy_metadata('transformers'),
        *copy_metadata('f5-tts'),
        *copy_metadata('coqui-tts'),
        *copy_metadata('safetensors'),
        *copy_metadata('tokenizers'),
        *collect_data_files('torchcodec'),
        # x-transformers defines @torch.jit.script functions (e.g. softclamp)
        # during import. TorchScript calls inspect.getsource(), which fails
        # against source-less modules in PyInstaller's PYZ archive.
        # Bundle the original .py sources alongside bytecode for inspection.
        *collect_data_files('x_transformers', include_py_files=True,
                            includes=['**/*.py']),
        # Coqui -> inflect -> typeguard: @typechecked introspects
        # the original inflect.engine source during module import.
        # The compiled PYZ contains bytecode but inspect.getsource() needs
        # physical Python sources in _internal/inflect and _internal/typeguard.
        *collect_data_files('inflect', include_py_files=True),
        *collect_data_files('typeguard', include_py_files=True),
    ] + runtime_datas,
    hiddenimports=[
        'mediapipe', 'cv2', 'instagrapi', 'google.genai', 'google.generativeai', 'PyQt6', 'PyQt6.QtWebEngineCore',
        'PyQt6.QtWebEngineWidgets', 'PyQt6.QtWebChannel', 'pyautogui', 'sounddevice',
        'keyboard', 'docx', 'pptx', 'multipart', 'passlib', 'bcrypt', 'aiohttp', 'websockets',
        'uvicorn', 'fastapi', 'plyer', 'pydantic', 'typing_extensions', 'requests', 'beautifulsoup4',
        'pyaudio', 'numpy', 'torch', 'torchaudio', 'soundfile', 'imageio_ffmpeg',
        'huggingface_hub', 'torchcodec', *collect_submodules('torchcodec'),
        *collect_submodules('f5_tts'), *collect_submodules('TTS'),
        'ko_speech_tools.data', *collect_submodules('ko_speech_tools')
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[os.path.join(cwd, 'installer', 'frozen_smoke_runtime.py')],
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
    icon=os.path.join(cwd, 'assets/JARVIS_AI_Logo.ico'),
    version=os.path.join(cwd, 'version.txt') if os.path.exists(os.path.join(cwd, 'version.txt')) else None
)

# Dedicated console executable so Node's MCP stdio transport can communicate
# with the exact same installed Brahma Windows desktop capabilities.
mcp_analysis = Analysis(
    [os.path.join(cwd, 'installer', 'brahma_mcp_launcher.py')],
    pathex=[cwd],
    binaries=[],
    datas=[],
    hiddenimports=['pyautogui', 'PIL.ImageGrab'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
mcp_pyz = PYZ(mcp_analysis.pure)
mcp_exe = EXE(
    mcp_pyz,
    mcp_analysis.scripts,
    [],
    exclude_binaries=True,
    name='BrahmaMcp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    mcp_exe,
    a.binaries,
    mcp_analysis.binaries,
    a.datas,
    mcp_analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BrahmaEvo'
)
