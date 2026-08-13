# -*- mode: python ; coding: utf-8 -*-
#
# HUSTLER — PyInstaller spec. r68.
#
# ONE-DIR AND PORTABLE, which is Fork B as the Maker signed it off: the game's
# saves sit beside HUSTLER.exe rather than in %APPDATA%, so a tester can zip
# the whole folder and send the shot log back. That relies on this staying
# one-dir (a COLLECT step, not a one-file EXE) — a one-file build unpacks into
# a temp directory Windows DELETES ON EXIT, and every career, league table,
# shot log and resume save would go with it.
#
# BUNDLE CODE ONLY. `datas` is deliberately empty and must stay that way.
# `hustler_league.json` and `hustler_profiles.json` are TRACKED IN THE REPO —
# they are the Maker's own career — so shipping them would hand every tester
# his league standings and his 9:13.6 solo best as their starting position. A
# virgin store is safe and was checked: the readers say
# `no league at … — run --league new to start one` and the game starts clean.
#
# There are no asset files to bundle in any case. Everything HUSTLER draws or
# plays is synthesised in code at runtime, which is the whole reason this
# project freezes as easily as it does.

block_cipher = None


a = Analysis(
    ['hustler.py'],
    pathex=[],
    binaries=[],
    # NOT A PLACE TO ADD CONVENIENCE FILES — see the note above.
    datas=[],
    # pymunk ships the compiled Chipmunk library and provides its own
    # PyInstaller hook, so it should be collected automatically. If the
    # Windows build fails to find it, the fix is `collect_dynamic_libs` on
    # pymunk rather than copying a DLL in by hand.
    hiddenimports=['cushion_path'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Trimmed because they are large, unused, and drag in their own binaries.
    # If any of these turns out to be needed, the symptom is an ImportError on
    # launch naming the module — take it out of this list rather than guessing.
    excludes=[
        'numpy', 'matplotlib', 'scipy', 'pandas',
        'tkinter', 'PIL', 'PyQt5', 'PySide2',
        'pytest', 'setuptools', 'pip',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,          # one-dir: binaries go in COLLECT below
    name='HUSTLER',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                      # UPX trips antivirus more than it saves
    # console=False so a tester gets the game and not a black window behind
    # it. That means there is nowhere for a traceback to be read, which is
    # exactly why r68 writes `hustler_crash.log` beside the exe. If a build
    # misbehaves and the log is not enough, flip this to True for a debug
    # build — it is the single most useful switch in this file.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='HUSTLER',
)
