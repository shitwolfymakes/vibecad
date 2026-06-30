# SPDX-License-Identifier: LGPL-2.1-or-later

"""Native FreeCAD preferences for VibeCAD.

Preferences intentionally store only non-secret settings. API keys are read
from the process environment, OS keyring, or a user-selected .env file by
VibeCADAuth.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import FreeCAD as App

from VibeCADAuth import (
    delete_keyring_key,
    resolve_auth_state,
    store_keyring_key,
    validate_configured_openai_auth,
    validate_openai_api_key,
)
from VibeCADWorkbenchTools import WORKBENCH_TOOL_PACKS


PREFERENCE_GROUP = "User parameter:BaseApp/Preferences/Mod/VibeCAD"
DEFAULT_MODEL = "gpt-5.5"
REASONING_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh")
DEFAULT_REASONING_EFFORT = "high"


@dataclass(frozen=True)
class VibeCADSettings:
    use_online_provider: bool = True
    model: str = DEFAULT_MODEL
    dotenv_path: str = ""
    disabled_workbenches: tuple[str, ...] = ()
    reasoning_effort: str = DEFAULT_REASONING_EFFORT
    allow_primitive_provider_tools: bool = False

    @property
    def resolved_dotenv_path(self) -> Path | None:
        if not self.dotenv_path:
            return None
        return Path(self.dotenv_path).expanduser()


def preferences():
    return App.ParamGet(PREFERENCE_GROUP)


def _parse_disabled_workbenches(value: str) -> tuple[str, ...]:
    known = set(WORKBENCH_TOOL_PACKS)
    items = []
    for item in value.split(","):
        workbench = item.strip()
        if workbench and workbench in known and workbench not in items:
            items.append(workbench)
    return tuple(sorted(items))


def _format_disabled_workbenches(value: tuple[str, ...]) -> str:
    return ",".join(sorted(set(value).intersection(WORKBENCH_TOOL_PACKS)))


def normalize_reasoning_effort(value: str | None) -> str:
    clean = (value or "").strip().lower()
    return clean if clean in REASONING_EFFORTS else DEFAULT_REASONING_EFFORT


def load_settings() -> VibeCADSettings:
    pref = preferences()
    return VibeCADSettings(
        use_online_provider=pref.GetBool("UseOnlineProvider", True),
        model=pref.GetString("Model", DEFAULT_MODEL) or DEFAULT_MODEL,
        dotenv_path=pref.GetString("DotenvPath", ""),
        disabled_workbenches=_parse_disabled_workbenches(
            pref.GetString("DisabledWorkbenches", "")
        ),
        reasoning_effort=normalize_reasoning_effort(
            pref.GetString("ReasoningEffort", DEFAULT_REASONING_EFFORT)
        ),
        allow_primitive_provider_tools=pref.GetBool("AllowPrimitiveProviderTools", False),
    )


def save_settings(settings: VibeCADSettings) -> None:
    pref = preferences()
    pref.SetBool("UseOnlineProvider", bool(settings.use_online_provider))
    pref.SetString("Model", settings.model.strip() or DEFAULT_MODEL)
    pref.SetString("DotenvPath", settings.dotenv_path.strip())
    pref.SetString("DisabledWorkbenches", _format_disabled_workbenches(settings.disabled_workbenches))
    pref.SetString("ReasoningEffort", normalize_reasoning_effort(settings.reasoning_effort))
    pref.SetBool("AllowPrimitiveProviderTools", bool(settings.allow_primitive_provider_tools))


def reset_settings() -> None:
    pref = preferences()
    pref.RemBool("UseOnlineProvider")
    pref.RemString("Model")
    pref.RemString("DotenvPath")
    pref.RemString("DisabledWorkbenches")
    pref.RemString("ReasoningEffort")
    pref.RemBool("AllowPrimitiveProviderTools")


def configured_dotenv_path() -> Path | None:
    settings = load_settings()
    if settings.resolved_dotenv_path is not None:
        return settings.resolved_dotenv_path
    cwd_dotenv = Path.cwd() / ".env"
    return cwd_dotenv if cwd_dotenv.exists() else None


class PreferencesPage:
    def __init__(self, parent=None):
        from PySide import QtCore, QtWidgets

        self.form = QtWidgets.QWidget(parent)
        self.form.setObjectName("VibeCADPreferencesPage")
        layout = QtWidgets.QFormLayout(self.form)

        self.use_online = QtWidgets.QCheckBox(self.form)
        self.use_online.setObjectName("VibeCADPrefUseOnlineProvider")
        layout.addRow("Use OpenAI provider", self.use_online)

        self.model = QtWidgets.QLineEdit(self.form)
        self.model.setObjectName("VibeCADPrefModel")
        layout.addRow("Model", self.model)

        self.reasoning_effort = QtWidgets.QComboBox(self.form)
        self.reasoning_effort.setObjectName("VibeCADPrefReasoningEffort")
        self.reasoning_effort.addItems(REASONING_EFFORTS)
        layout.addRow("Reasoning effort", self.reasoning_effort)

        self.allow_primitives = QtWidgets.QCheckBox(self.form)
        self.allow_primitives.setObjectName("VibeCADPrefAllowPrimitiveProviderTools")
        layout.addRow("Expose Part primitive tools", self.allow_primitives)

        dotenv_row = QtWidgets.QHBoxLayout()
        self.dotenv_path = QtWidgets.QLineEdit(self.form)
        self.dotenv_path.setObjectName("VibeCADPrefDotenvPath")
        browse = QtWidgets.QPushButton("Browse", self.form)
        browse.setObjectName("VibeCADPrefBrowseDotenv")
        browse.clicked.connect(self._browse_dotenv)
        dotenv_row.addWidget(self.dotenv_path, 1)
        dotenv_row.addWidget(browse)
        layout.addRow(".env path", dotenv_row)

        api_key_row = QtWidgets.QHBoxLayout()
        self.api_key = QtWidgets.QLineEdit(self.form)
        self.api_key.setObjectName("VibeCADPrefApiKey")
        self.api_key.setEchoMode(QtWidgets.QLineEdit.Password)
        self.api_key.setPlaceholderText("Paste an OpenAI API key")
        save_key = QtWidgets.QPushButton("Save Key", self.form)
        save_key.setObjectName("VibeCADPrefSaveApiKey")
        save_key.clicked.connect(self._save_api_key)
        logout = QtWidgets.QPushButton("Logout", self.form)
        logout.setObjectName("VibeCADPrefLogout")
        logout.clicked.connect(self._logout)
        validate = QtWidgets.QPushButton("Validate", self.form)
        validate.setObjectName("VibeCADPrefValidateAuth")
        validate.clicked.connect(self._validate_auth)
        api_key_row.addWidget(self.api_key, 1)
        api_key_row.addWidget(save_key)
        api_key_row.addWidget(validate)
        api_key_row.addWidget(logout)
        layout.addRow("OpenAI API key", api_key_row)

        self.status = QtWidgets.QLabel(self.form)
        self.status.setObjectName("VibeCADPrefAuthStatus")
        self.status.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        layout.addRow("Auth status", self.status)

        self.tool_packs = QtWidgets.QListWidget(self.form)
        self.tool_packs.setObjectName("VibeCADPrefToolPacks")
        self.tool_packs.setFixedHeight(150)
        for workbench in sorted(WORKBENCH_TOOL_PACKS):
            item = QtWidgets.QListWidgetItem(workbench)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked)
            self.tool_packs.addItem(item)
        layout.addRow("Enabled tool packs", self.tool_packs)

        refresh = QtWidgets.QPushButton("Refresh", self.form)
        refresh.setObjectName("VibeCADPrefRefreshAuth")
        refresh.clicked.connect(self._refresh_status)
        layout.addRow("", refresh)

    def _browse_dotenv(self) -> None:
        from PySide import QtWidgets

        selected, _filter = QtWidgets.QFileDialog.getOpenFileName(
            self.form,
            "Select .env file",
            self.dotenv_path.text() or str(Path.home()),
            "Environment files (*.env);;All files (*)",
        )
        if selected:
            self.dotenv_path.setText(selected)
            self._refresh_status()

    def _save_api_key(self) -> None:
        result = store_keyring_key(self.api_key.text())
        self.api_key.clear()
        if not result["stored"]:
            self.status.setText(f"not_configured | {result['error']}")
            return
        self._refresh_status()

    def _logout(self) -> None:
        delete_keyring_key()
        self.api_key.clear()
        self._refresh_status()

    def _validate_auth(self) -> None:
        typed_key = self.api_key.text().strip()
        if typed_key:
            auth = validate_openai_api_key(typed_key, source="unsaved API key")
            self.api_key.clear()
        else:
            auth = validate_configured_openai_auth(
                dotenv_path=self._current_settings().resolved_dotenv_path
            )
        source = f" | {auth.source}" if auth.source else ""
        key = f" | {auth.redacted_key}" if auth.redacted_key else ""
        message = f" | {auth.message}" if auth.message else ""
        self.status.setText(f"{auth.status.value}{source}{key}{message}")

    def _current_settings(self) -> VibeCADSettings:
        from PySide import QtCore

        disabled = []
        for index in range(self.tool_packs.count()):
            item = self.tool_packs.item(index)
            if item.checkState() != QtCore.Qt.Checked:
                disabled.append(item.text())
        return VibeCADSettings(
            use_online_provider=self.use_online.isChecked(),
            model=self.model.text().strip() or DEFAULT_MODEL,
            dotenv_path=self.dotenv_path.text().strip(),
            disabled_workbenches=tuple(disabled),
            reasoning_effort=normalize_reasoning_effort(self.reasoning_effort.currentText()),
            allow_primitive_provider_tools=self.allow_primitives.isChecked(),
        )

    def _refresh_status(self) -> None:
        settings = self._current_settings()
        auth = resolve_auth_state(dotenv_path=settings.resolved_dotenv_path)
        source = f" | {auth.source}" if auth.source else ""
        key = f" | {auth.redacted_key}" if auth.redacted_key else ""
        self.status.setText(f"{auth.status.value}{source}{key}")

    def saveSettings(self) -> None:
        save_settings(self._current_settings())

    def loadSettings(self) -> None:
        from PySide import QtCore

        settings = load_settings()
        self.use_online.setChecked(settings.use_online_provider)
        self.model.setText(settings.model)
        index = self.reasoning_effort.findText(settings.reasoning_effort)
        self.reasoning_effort.setCurrentIndex(index if index >= 0 else 0)
        self.allow_primitives.setChecked(settings.allow_primitive_provider_tools)
        self.dotenv_path.setText(settings.dotenv_path)
        disabled = set(settings.disabled_workbenches)
        for index in range(self.tool_packs.count()):
            item = self.tool_packs.item(index)
            state = QtCore.Qt.Unchecked if item.text() in disabled else QtCore.Qt.Checked
            item.setCheckState(state)
        self.api_key.clear()
        self._refresh_status()
