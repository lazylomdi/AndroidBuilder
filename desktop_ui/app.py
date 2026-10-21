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
        side_note = QLabel("Python engine\nWindows 10 · Ubuntu")
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
        self.nav.setCurrentRow(2)
        self.run_command([str(ROMFORGE), "ut-check", "--inspect-device", "--serial", serial, "--markdown-out", str(ROOT / "device-readiness-report.md")], "Device inspection")

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
        self.setStyleSheet("""
            QWidget { background: #f5f7fb; color: #182230; font-size: 13px; }
            #sidebar { background: #ffffff; border-right: 1px solid #e1e6ef; }
            #brand { font-size: 20px; font-weight: 700; padding: 14px 8px 4px; color: #172b4d; }
            #eyebrow { color: #7b8798; font-size: 10px; font-weight: 700; letter-spacing: 1px; padding: 0 8px 10px; }
            #muted { color: #66758a; }
            #pageTitle { font-size: 27px; font-weight: 700; color: #16253d; }
            QListWidget { background: transparent; border: 0; outline: 0; padding: 8px 4px; }
            QListWidget::item { padding: 13px 12px; border-radius: 8px; margin: 2px 0; color: #4a5a70; }
            QListWidget::item:selected { background: #e8efff; color: #2458c6; font-weight: 600; }
            #card, QGroupBox { background: white; border: 1px solid #e2e8f0; border-radius: 12px; }
            #card { padding: 8px; }
            #cardTitle { color: #75849a; font-size: 11px; font-weight: 700; }
            #metric { color: #1f3b66; font-size: 19px; font-weight: 700; }
            #sectionTitle { font-size: 16px; font-weight: 700; }
            #notice { background: #eef4ff; color: #31517c; border: 1px solid #dce8ff; border-radius: 9px; padding: 12px; }
            QGroupBox { margin-top: 10px; padding: 16px; font-weight: 600; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
            QLineEdit, QComboBox, QSpinBox, QPlainTextEdit { background: white; border: 1px solid #d6deea; border-radius: 7px; padding: 8px; selection-background-color: #c9d9ff; }
            QPlainTextEdit { font-family: Consolas, 'DejaVu Sans Mono', monospace; font-size: 12px; }
            QPushButton { background: white; border: 1px solid #d4dce8; border-radius: 8px; padding: 9px 15px; font-weight: 600; }
            QPushButton:hover { background: #f0f4fa; }
            QPushButton#primaryButton { background: #2864dc; color: white; border-color: #2864dc; }
            QPushButton#primaryButton:hover { background: #1f52ba; }
            #statusPill { background: #e8efff; color: #2458c6; border-radius: 7px; padding: 9px; font-weight: 600; }
            QProgressBar { border: 0; background: #e5eaf2; border-radius: 4px; height: 8px; text-align: center; }
            QProgressBar::chunk { background: #2864dc; border-radius: 4px; }
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
