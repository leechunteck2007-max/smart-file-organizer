"""Launch bundled EXE without Python on PATH, confirm Tk windows, close cleanly."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    exe = ROOT / 'dist' / 'UniversalFileLibrarian' / 'UniversalFileLibrarian.exe'
    state = ROOT / 'build' / 'package-check-state'
    environment = dict(os.environ)
    environment['PATH'] = str(Path(os.environ['WINDIR']) / 'System32')
    for key in ['PYTHONHOME', 'PYTHONPATH']:
        environment.pop(key, None)
    smoke = subprocess.run([str(exe), '--state-dir', str(state), '--smoke-test'], env=environment, timeout=20)
    assert smoke.returncode == 0
    process = subprocess.Popen([str(exe), '--state-dir', str(state)], env=environment)
    user = ctypes.WinDLL('user32', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    windows = []

    @callback_type
    def callback(hwnd, parameter):
        pid = wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == process.pid:
            title = ctypes.create_unicode_buffer(300)
            user.GetWindowTextW(hwnd, title, 300)
            if title.value:
                windows.append((hwnd, title.value))
        return True

    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            windows.clear()
            user.EnumWindows(callback, 0)
            if any('First Run' in title for hwnd, title in windows):
                break
            if process.poll() is not None:
                raise RuntimeError('Packaged GUI exited before onboarding')
            time.sleep(.2)
        main_window = next(hwnd for hwnd, title in windows if title.startswith('Universal File Librarian'))
        assert any('First Run' in title for hwnd, title in windows)
        user.PostMessageW(main_window, 0x10, 0, 0)
        exit_code = process.wait(timeout=10)
        assert exit_code == 0
        report = dict(smoke_exit=smoke.returncode, gui_exit=exit_code, main_window=True, first_run_window=True,
                      python_on_path=False, separate_computer_tested=False)
        (ROOT / 'docs' / 'package-test.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report))
    finally:
        if process.poll() is None:
            process.terminate()


if __name__ == '__main__':
    main()
