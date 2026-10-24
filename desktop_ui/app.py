"""Lightweight PySide6 desktop UI for romforge (Windows and Ubuntu)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QMainWindow, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QSpinBox, QStackedWidget, QVBoxLayout,
    QWidget, QFileDialog, QCheckBox, QGroupBox,
)

ROOT = Path(__file__).resolve().parents[1]
ROMFORGE = ROOT / "romforge.py"


def make_button(text: str, primary: bool = False) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        button.setObjectName("primaryButton")
    return button


class DesktopWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AndroidBuilder")
        self.resize(1180, 780)
        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(ROOT))
        self.process.readyReadStandardOutput.connect(self.read_stdout)
        self.process.readyReadStandardError.connect(self.read_stderr)
        self.process.finished.connect(self.process_finished)
        self.process.errorOccurred.connect(self.process_error)
        self.build_running = False
        self.device_report_path: Path | None = None

        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setCentralWidget(root)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        side = QVBoxLayout(sidebar)
        brand = QLabel("AndroidBuilder")
        brand.setObjectName("brand")
        side.addWidget(brand)
        subtitle = QLabel("ROM WORKSPACE")
        subtitle.setObjectName("eyebrow")
        side.addWidget(subtitle)
        self.nav = QListWidget()
        self.nav.addItems(["Dashboard", "Build wizard", "Build monitor", "Device manager"])
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self.change_page)
        side.addWidget(self.nav, 1)
        device_status = QFrame()
        device_status.setObjectName("sidebarDevice")
        device_status_layout = QVBoxLayout(device_status)
        device_status_layout.setContentsMargins(10, 10, 10, 10)
        device_heading = QLabel("CONNECTED DEVICE")
        device_heading.setObjectName("eyebrow")
        self.sidebar_device_name = QLabel("No device detected")
        self.sidebar_device_name.setObjectName("sidebarDeviceName")
        self.sidebar_device_info = QLabel("ADB · waiting for scan")
        self.sidebar_device_info.setObjectName("muted")
        self.sidebar_device_info.setWordWrap(True)
        device_status_layout.addWidget(device_heading)
        device_status_layout.addWidget(self.sidebar_device_name)
        device_status_layout.addWidget(self.sidebar_device_info)
        side.addWidget(device_status)
        side_note = QLabel("Python engine · Windows 10 / Ubuntu")
        side_note.setObjectName("muted")
        side.addWidget(side_note)
        layout.addWidget(sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(28, 24, 28, 24)
        content_layout.setSpacing(16)
        self.page_title = QLabel("Dashboard")
        self.page_title.setObjectName("pageTitle")
        self.page_subtitle = QLabel("Your build environment at a glance.")
        self.page_subtitle.setObjectName("muted")
        content_layout.addWidget(self.page_title)
        content_layout.addWidget(self.page_subtitle)
        self.pages = QStackedWidget()
        content_layout.addWidget(self.pages, 1)
        layout.addWidget(content, 1)

        self.dashboard = self.make_dashboard()
        self.wizard = self.make_wizard()
        self.monitor = self.make_monitor()
        self.devices = self.make_devices()
        for page in (self.dashboard, self.wizard, self.monitor, self.devices):
            self.pages.addWidget(page)

        self.apply_styles()
        self.refresh_environment()
        self.refresh_devices()

    def change_page(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        titles = [
            ("Dashboard", "Your build environment at a glance."),
            ("Build wizard", "Configure a ROM build before launching it."),
            ("Build monitor", "Live output from the active or most recent task."),
            ("Device manager", "Read-only ADB discovery and optional device inspection."),
        ]
        self.page_title.setText(titles[index][0])
        self.page_subtitle.setText(titles[index][1])

    def card(self, title: str, value: str, detail: str = "") -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        box = QVBoxLayout(frame)
        heading = QLabel(title)
        heading.setObjectName("cardTitle")
        metric = QLabel(value)
        metric.setObjectName("metric")
        note = QLabel(detail)
        note.setObjectName("muted")
        note.setWordWrap(True)
        box.addWidget(heading)
        box.addWidget(metric)
        box.addWidget(note)
        return frame

    def make_dashboard(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        row = QHBoxLayout()
        self.python_card = self.card("PYTHON", "Checking…", "Runtime used by romforge")
        self.git_card = self.card("GIT", "Checking…", "Source checkout and repository operations")
        self.adb_card = self.card("ADB", "Checking…", "Optional connected-device access")
        row.addWidget(self.python_card)
        row.addWidget(self.git_card)
        row.addWidget(self.adb_card)
        box.addLayout(row)
        summary = QFrame()
        summary.setObjectName("card")
        sb = QVBoxLayout(summary)
        h = QLabel("Start here")
        h.setObjectName("sectionTitle")
        sb.addWidget(h)
        sb.addWidget(QLabel("Create a build configuration, watch command output, or inspect a connected phone."))
        actions = QHBoxLayout()
        build = make_button("New build", True)
        build.clicked.connect(lambda: self.nav.setCurrentRow(1))
        device = make_button("Refresh devices")
        device.clicked.connect(self.refresh_devices)
        device.clicked.connect(lambda: self.nav.setCurrentRow(3))
        actions.addWidget(build)
        actions.addWidget(device)
        actions.addStretch()
        sb.addLayout(actions)
        box.addWidget(summary)
        warnings = QLabel(
            "Builds run through the existing Python CLI. Full Android ROM compilation should use a supported "
            "Ubuntu environment (or WSL2 Ubuntu on Windows). Review settings carefully before starting."
        )
        warnings.setObjectName("notice")
        warnings.setWordWrap(True)
        box.addWidget(warnings)
        box.addStretch()
        return page

    def make_wizard(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        form_group = QGroupBox("Build configuration")
        form = QFormLayout(form_group)
        self.version = QComboBox()
        self.version.addItems(["14", "13", "12", "11", "10", "9", "8", "7", "6", "5", "4"])
        self.codename = QLineEdit()
        self.codename.setPlaceholderText("e.g. sunfish")
        self.vendor = QLineEdit()
        self.vendor.setPlaceholderText("Optional vendor hint")
        self.arch = QComboBox()
        self.arch.addItems(["arm64", "armv7", "x86_64", "x86"])
        self.source = QComboBox()
        self.source.addItems(["lineage", "aosp"])
        self.backend = QComboBox()
        self.backend.addItems(["local", "docker", "github-actions"])
        self.jobs = QSpinBox()
        self.jobs.setRange(1, max(1, os.cpu_count() or 4))
        self.jobs.setValue(min(4, max(1, os.cpu_count() or 4)))
        self.workdir = QLineEdit(str(ROOT / "romforge-src"))
        choose_dir = make_button("Browse…")
        choose_dir.clicked.connect(self.choose_workdir)
        work_row = QHBoxLayout()
        work_row.addWidget(self.workdir, 1)
        work_row.addWidget(choose_dir)
        work_widget = QWidget()
        work_widget.setLayout(work_row)
        self.lunch = QLineEdit()
        self.lunch.setPlaceholderText("Optional; e.g. lineage_sunfish-userdebug")
        self.device_tree = QLineEdit()
        self.vendor_tree = QLineEdit()
        self.kernel_tree = QLineEdit()
        self.recovery = QLineEdit()
        self.gapps = QCheckBox("Include Google apps (if supported by selected build)")
        self.root_option = QCheckBox("Include root customization")
        self.dry_run = QCheckBox("Dry run (do not run the build pipeline)")
        self.dry_run.setChecked(True)
        form.addRow("Android version", self.version)
        form.addRow("Device codename *", self.codename)
        form.addRow("Vendor hint", self.vendor)
        form.addRow("Architecture", self.arch)
        form.addRow("Source", self.source)
        form.addRow("Backend", self.backend)
        form.addRow("Parallel jobs", self.jobs)
        form.addRow("Work directory", work_widget)
        form.addRow("Lunch target", self.lunch)
        form.addRow("Device tree URL", self.device_tree)
        form.addRow("Vendor tree URL", self.vendor_tree)
        form.addRow("Kernel tree URL", self.kernel_tree)
        form.addRow("Recovery URL", self.recovery)
        form.addRow("", self.gapps)
        form.addRow("", self.root_option)
        form.addRow("", self.dry_run)
        outer.addWidget(form_group)
        note = QLabel("The first launch defaults to dry-run. Uncheck it only after reviewing the source, target, backend, and disk requirements.")
        note.setObjectName("notice")
        note.setWordWrap(True)
        outer.addWidget(note)
        actions = QHBoxLayout()
        actions.addStretch()
        start = make_button("Review & start build", True)
        start.clicked.connect(self.start_build)
        actions.addWidget(start)
        outer.addLayout(actions)
        outer.addStretch()
        return page

    def make_monitor(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        self.build_status = QLabel("No task started")
        self.build_status.setObjectName("statusPill")
        box.addWidget(self.build_status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        box.addWidget(self.progress)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.log.setPlaceholderText("Build output will appear here when a task starts.")
        box.addWidget(self.log, 1)
        actions = QHBoxLayout()
        clear = make_button("Clear log")
        clear.clicked.connect(self.log.clear)
        self.cancel_button = make_button("Terminate process")
        self.cancel_button.clicked.connect(self.cancel_process)
        self.cancel_button.setEnabled(False)
        actions.addWidget(clear)
        actions.addStretch()
        actions.addWidget(self.cancel_button)
        box.addLayout(actions)
        return page

    def make_devices(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        row = QHBoxLayout()
        self.device_list = QListWidget()
        self.device_list.setMinimumHeight(240)
        row.addWidget(self.device_list, 2)
        details = QFrame()
        details.setObjectName("card")
        detail_box = QVBoxLayout(details)
        title = QLabel("Device inspection")
        title.setObjectName("sectionTitle")
        detail_box.addWidget(title)
        detail_box.addWidget(QLabel(
            "Refresh lists ADB devices. Inspection invokes the existing opt-in readiness command and is read-only. "
            "It does not unlock, root, reboot, erase, or flash the phone."
        ))
        self.device_output = QPlainTextEdit()
        self.device_output.setReadOnly(True)
        self.device_output.setPlaceholderText("Device command output appears here.")
        detail_box.addWidget(self.device_output, 1)
        row.addWidget(details, 3)
        box.addLayout(row, 1)
        actions = QHBoxLayout()
        refresh = make_button("Refresh devices", True)
        refresh.clicked.connect(self.refresh_devices)
        inspect = make_button("Inspect selected device")
        inspect.clicked.connect(self.inspect_device)
        actions.addWidget(refresh)
        actions.addWidget(inspect)
        actions.addStretch()
        box.addLayout(actions)
        return page

    def run_command(self, args: list[str], task_name: str) -> None:
        if self.process.state() != QProcess.ProcessState.NotRunning:
            QMessageBox.warning(self, "Task already running", "Wait for the current task to finish before starting another.")
            return
        self.build_status.setText(f"Running: {task_name}")
        self.progress.setVisible(True)
        self.cancel_button.setEnabled(True)
        self.log.appendPlainText(f"$ {sys.executable} " + " ".join(args))
        self.process.start(sys.executable, args)

    def start_build(self) -> None:
        codename = self.codename.text().strip()
        if not codename:
            QMessageBox.warning(self, "Device codename required", "Enter the target device codename before continuing.")
            return
        summary = (
            f"Android {self.version.currentText()} / {codename}\n"
            f"Source: {self.source.currentText()} · Backend: {self.backend.currentText()}\n"
            f"Work directory: {self.workdir.text().strip()}\n"
            f"Dry run: {'yes' if self.dry_run.isChecked() else 'NO — this may download sources and use substantial disk space'}"
        )
        answer = QMessageBox.question(
            self, "Review build configuration",
            summary + "\n\nStart this command?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        args = [
            str(ROMFORGE), "build", "--version", self.version.currentText(),
            "--codename", codename, "--arch", self.arch.currentText(),
            "--source", self.source.currentText(), "--backend", self.backend.currentText(),
            "--jobs", str(self.jobs.value()), "--workdir", self.workdir.text().strip() or "./romforge-src",
        ]
        optional = [
            ("--vendor", self.vendor.text().strip()),
            ("--lunch-target", self.lunch.text().strip()),
            ("--device-tree-url", self.device_tree.text().strip()),
            ("--vendor-tree-url", self.vendor_tree.text().strip()),
            ("--kernel-tree-url", self.kernel_tree.text().strip()),
            ("--recovery", self.recovery.text().strip()),
        ]
        for flag, value in optional:
            if value:
                args.extend([flag, value])
        if self.gapps.isChecked():
            args.append("--gapps")
        if self.root_option.isChecked():
            args.append("--root")
        if self.dry_run.isChecked():
            args.append("--dry-run")
        self.log.clear()
        self.nav.setCurrentRow(2)
        self.run_command(args, "ROM build")

    def refresh_environment(self) -> None:
        def check(cmd: str) -> str:
            path = shutil.which(cmd)
            return f"Available · {path}" if path else "Not found on PATH"
        self.replace_card_metric(self.python_card, sys.version.split()[0], sys.executable)
        self.replace_card_metric(self.git_card, "Available" if shutil.which("git") else "Missing", check("git"))
        self.replace_card_metric(self.adb_card, "Available" if shutil.which("adb") else "Optional", check("adb"))

    @staticmethod
    def replace_card_metric(card: QFrame, value: str, detail: str) -> None:
        labels = card.findChildren(QLabel)
        if len(labels) >= 3:
            labels[1].setText(value)
            labels[2].setText(detail)

    def refresh_devices(self) -> None:
        self.device_list.clear()
        adb = shutil.which("adb")
        if not adb:
            self.device_list.addItem("ADB not found on PATH")
            return
        result = subprocess.run([adb, "devices", "-l"], capture_output=True, text=True, timeout=8, check=False)
        lines = result.stdout.splitlines()[1:]
        found = 0
        for line in lines:
            line = line.strip()
            if line:
                self.device_list.addItem(line)
                found += 1
        if not found:
            self.device_list.addItem("No devices detected")
            self.sidebar_device_name.setText("No device detected")
            self.sidebar_device_info.setText("Connect by USB or wireless ADB")
        else:
            first_device = next((line.strip() for line in lines if line.strip()), "")
            parts = first_device.split()
            serial = parts[0] if parts else "Device detected"
            state = parts[1] if len(parts) > 1 else "unknown"
            self.sidebar_device_name.setText(serial)
            self.sidebar_device_info.setText(f"ADB status: {state}")
        if result.stderr.strip():
            self.device_output.appendPlainText(result.stderr.strip())

    def inspect_device(self) -> None:
        item = self.device_list.currentItem()
        if not item:
            QMessageBox.information(self, "Select a device", "Refresh the device list and select a device row first.")
            return
        line = item.text()
        serial = line.split()[0] if line and not line.startswith(("ADB not found", "No devices")) else ""
        if not serial or serial in {"List", "of"}:
            QMessageBox.warning(self, "No device selected", "Select a connected device row, not a status message.")
            return
        answer = QMessageBox.question(
            self, "Read-only inspection",
            f"Inspect {serial} using the existing Ubuntu Touch readiness checker?\n\nThis is read-only and does not flash or change the phone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.device_output.clear()
        report_dir = Path.home() / ".local" / "share" / "AndroidBuilder"
        try:
            report_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(self, "Cannot save report", f"Could not create the report directory:\\n{exc}")
            return
        self.device_report_path = report_dir / "device-readiness-report.md"
        self.device_output.setPlainText(f"Inspecting {serial} with read-only ADB commands...\\nReport: {self.device_report_path}")
        self.run_command([str(ROMFORGE), "ut-check", "--inspect-device", "--serial", serial, "--markdown-out", str(self.device_report_path)], "Device inspection")

    def choose_workdir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select build work directory", self.workdir.text())
        if path:
            self.workdir.setText(path)

    def read_stdout(self) -> None:
        data = bytes(self.process.readAllStandardOutput()).decode(errors="replace")
        if data:
            self.log.appendPlainText(data.rstrip())
            self.device_output.appendPlainText(data.rstrip())

    def read_stderr(self) -> None:
        data = bytes(self.process.readAllStandardError()).decode(errors="replace")
        if data:
            self.log.appendPlainText(data.rstrip())
            self.device_output.appendPlainText(data.rstrip())

    def process_finished(self, code: int, _status: QProcess.ExitStatus) -> None:
        self.progress.setVisible(False)
        self.cancel_button.setEnabled(False)
        self.build_status.setText("Completed successfully" if code == 0 else f"Finished with exit code {code}")
        self.log.appendPlainText(f"\n[Process exited with code {code}]")
        self.device_output.appendPlainText(f"\n[Process exited with code {code}]")
        self.refresh_environment()
        self.refresh_devices()

    def process_error(self, _error: QProcess.ProcessError) -> None:
        self.log.appendPlainText(f"Process error: {self.process.errorString()}")
        self.build_status.setText("Could not start process")
        self.progress.setVisible(False)
        self.cancel_button.setEnabled(False)

    def cancel_process(self) -> None:
        if self.process.state() != QProcess.ProcessState.NotRunning:
            answer = QMessageBox.warning(
                self, "Terminate running process",
                "This sends a process termination request. Build cleanup may be incomplete. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.process.terminate()

    def apply_styles(self) -> None:
        # Inspired by the user's Android Toolkit reference: compact dark workspace,
        # strong sidebar navigation, quiet borders, and clear action emphasis.
        self.setStyleSheet("""
            QWidget { background: #101012; color: #e8e8ec; font-size: 12px; }
            QMainWindow { background: #101012; }
            #sidebar { background: #171719; border-right: 1px solid #29292d; }
            #brand { font-size: 18px; font-weight: 700; padding: 14px 8px 4px; color: #f5f5f7; }
            #eyebrow { color: #777780; font-size: 9px; font-weight: 700; letter-spacing: 1px; padding: 0 4px 8px; }
            #muted { color: #9999a2; }
            #pageTitle { font-size: 25px; font-weight: 700; color: #f1f1f4; }
            QListWidget { background: transparent; border: 0; outline: 0; padding: 8px 4px; }
            QListWidget::item { padding: 13px 12px; border-radius: 5px; margin: 2px 0; color: #a6a6af; }
            QListWidget::item:selected { background: #29292e; color: #ffffff; border-left: 2px solid #a855f7; font-weight: 600; }
            #card, QGroupBox { background: #1b1b1e; border: 1px solid #2b2b30; border-radius: 8px; }
            #card { padding: 8px; }
            #cardTitle { color: #85858f; font-size: 10px; font-weight: 700; letter-spacing: .5px; }
            #metric { color: #f0f0f3; font-size: 18px; font-weight: 700; }
            #sectionTitle { font-size: 15px; font-weight: 700; color: #eeeeF2; }
            #notice { background: #111d1b; color: #75cfc1; border: 1px solid #203b36; border-radius: 6px; padding: 12px; }
            #sidebarDevice { background: #131315; border: 1px solid #2a2a2e; border-radius: 6px; }
            #sidebarDeviceName { color: #ededf0; font-weight: 700; }
            QGroupBox { margin-top: 10px; padding: 16px; font-weight: 600; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; color: #b5b5bf; }
            QLineEdit, QComboBox, QSpinBox, QPlainTextEdit { background: #141416; color: #ededf0; border: 1px solid #333339; border-radius: 6px; padding: 8px; selection-background-color: #6336a6; }
            QComboBox QAbstractItemView { background: #202024; color: #ededf0; selection-background-color: #6336a6; }
            QCheckBox { spacing: 8px; color: #d6d6dc; }
            QPlainTextEdit { font-family: Consolas, 'DejaVu Sans Mono', monospace; font-size: 12px; }
            QPushButton { background: #202023; color: #dedee4; border: 1px solid #34343a; border-radius: 6px; padding: 9px 15px; font-weight: 600; }
            QPushButton:hover { background: #2a2a30; border-color: #4b4b55; }
            QPushButton#primaryButton { background: #6550a8; color: white; border-color: #8068ce; }
            QPushButton#primaryButton:hover { background: #7962bf; }
            #statusPill { background: #142b27; color: #75cfc1; border: 1px solid #244a43; border-radius: 6px; padding: 9px; font-weight: 600; }
            QProgressBar { border: 0; background: #29292e; border-radius: 4px; height: 8px; text-align: center; }
            QProgressBar::chunk { background: #58b9a9; border-radius: 4px; }
            QScrollBar:vertical { background: #151517; width: 10px; margin: 0; }
            QScrollBar::handle:vertical { background: #3b3b42; min-height: 24px; border-radius: 4px; }
        """)

def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("AndroidBuilder")
    app.setFont(QFont("Segoe UI" if sys.platform == "win32" else "Noto Sans", 10))
    window = DesktopWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
