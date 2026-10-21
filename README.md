# AndroidBuilder / romforge

Android ROM build and device-tree discovery tools, with an offline-first Ubuntu Touch readiness assessment.

## Ubuntu Touch readiness check

```bash
python3 romforge.py ut-check \
  --manufacturer Sony --model "Xperia R1" --ram-gb 2 \
  --json-out reports/xperia-r1.json \
  --markdown-out reports/xperia-r1.md
```

The checker does not require a connected phone. On Windows 10, install Android SDK Platform-Tools, add its folder to `PATH`, enable USB debugging on the phone, connect by USB, and accept the authorization prompt. Then run:

```powershell
python romforge.py ut-check --inspect-device
# If more than one phone is connected:
python romforge.py ut-check --inspect-device --serial YOUR_ADB_SERIAL
```

Device inspection is opt-in and read-only: it runs `adb devices -l`, `getprop`, reads `/proc/meminfo`, and queries `uname -r`. It does not root, unlock, flash, or change phone settings. Add `--online` to search GitHub for candidate repositories; network failures are reported and repository metadata is never treated as compatibility proof. User-provided facts are marked as candidates, unknown properties remain unknown, and no report claims that a port builds or boots. See [device readiness](docs/device-readiness.md), [porting notes](docs/ubuntu-touch-porting.md), and the [repository audit](docs/repository-audit.md).

## Windows 10 setup automation

From PowerShell in the repository folder, run the prerequisite checks:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup_windows.ps1
```

Optional switches can attempt to install Git/Python/ADB with WinGet, request WSL2 Ubuntu installation, or install Python requirements and run project checks:

```powershell
.\setup_windows.ps1 -InstallTools
.\setup_windows.ps1 -InstallWSL
.\setup_windows.ps1 -InstallPythonDependencies
```

Review [Windows setup instructions](docs/windows-setup.md) before using installation switches. WSL2 Ubuntu is recommended for actual Android ROM builds; the script does not restart the PC and does not modify or flash the phone.

## Existing ROM builder

Run `python3 romforge.py --help` for CLI usage. The interactive menu requires `questionary`; see `requirements.txt` for dependencies and external build tools.

## Tests

```bash
python3 -m unittest discover -s tests -v
```
