"""Windows registry monitoring using winreg + win32api (pywin32).

Uses RegNotifyChangeKeyValue for event-driven, zero-polling detection of
registry value and subkey changes. Falls back with a warning if pywin32
is not installed.
"""

import asyncio
import threading
import logging
import sys
from typing import List, Dict, Any, Tuple, Set, Optional

from hips_service.monitors.base_monitor import BaseMonitor
from hips_service.core.event_bus import EventBus, MonitorEvent
from hips_service.core.platform_detector import PlatformDetector
from hips_service.utils.time import get_local_time

logger = logging.getLogger(__name__)

# ── Optional Windows-only imports ────────────────────────────────────────────
_winreg_ok = False
_win32_ok = False

if sys.platform == "win32":
    try:
        import winreg
        _winreg_ok = True
    except ImportError:
        pass

    try:
        import win32api
        import win32con
        import win32event
        _win32_ok = True
    except ImportError:
        pass

# Registry notification filter flags (not always present in win32con)
REG_NOTIFY_CHANGE_NAME     = 0x00000001  # subkey added/removed
REG_NOTIFY_CHANGE_LAST_SET = 0x00000004  # value created/modified/deleted
KEY_NOTIFY                 = 0x00000010
KEY_READ                   = 0x00020019

# ── Hive constants (same as winreg.HKEY_* integer values) ───────────────────
HKEY_CLASSES_ROOT  = 0x80000000
HKEY_CURRENT_USER  = 0x80000001
HKEY_LOCAL_MACHINE = 0x80000002
HKEY_USERS         = 0x80000003
HKEY_CURRENT_CONFIG = 0x80000005

_HIVE_NAMES: Dict[int, str] = {
    HKEY_CLASSES_ROOT:   "HKCR",
    HKEY_CURRENT_USER:   "HKCU",
    HKEY_LOCAL_MACHINE:  "HKLM",
    HKEY_USERS:          "HKU",
    HKEY_CURRENT_CONFIG: "HKCC",
}


def _hive_name(hive: int) -> str:
    return _HIVE_NAMES.get(hive, f"0x{hive:08X}")


# ── Key state snapshot ────────────────────────────────────────────────────────

def _read_key_state(hive: int, subkey: str) -> Dict[str, Any]:
    """Return {'values': {name: (data, vtype)}, 'subkeys': set(names)}."""
    state: Dict[str, Any] = {"values": {}, "subkeys": set()}
    if not _winreg_ok:
        return state
    try:
        key = winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ)
        try:
            i = 0
            while True:
                try:
                    name, data, vtype = winreg.EnumValue(key, i)
                    if isinstance(data, (bytes, bytearray)) and len(data) > 512:
                        data = data[:512]
                    state["values"][name] = (data, vtype)
                    i += 1
                except OSError:
                    break

            i = 0
            while True:
                try:
                    state["subkeys"].add(winreg.EnumKey(key, i))
                    i += 1
                except OSError:
                    break
        finally:
            winreg.CloseKey(key)
    except FileNotFoundError:
        pass  # key not present yet
    except PermissionError:
        logger.debug("Permission denied: %s\\%s", _hive_name(hive), subkey)
    except OSError as exc:
        logger.debug("Cannot read %s\\%s: %s", _hive_name(hive), subkey, exc)
    return state


def _fmt(data: Any, vtype: int) -> str:
    """Format a registry value for human-readable display."""
    if data is None:
        return ""
    if isinstance(data, (bytes, bytearray)):
        return data.hex()
    if isinstance(data, list):
        return " | ".join(str(x) for x in data)
    return str(data)[:500]


# ── Per-key watcher (runs its own background thread) ─────────────────────────

class _RegistryKeyWatcher:
    """Watches one registry key using RegNotifyChangeKeyValue."""

    def __init__(
        self,
        hive: int,
        subkey: str,
        severity: str,
        on_change,   # async coroutine: on_change(change_dict)
        loop: asyncio.AbstractEventLoop,
    ):
        self.hive = hive
        self.subkey = subkey
        self.severity = severity
        self._on_change = on_change
        self._loop = loop
        self.full_path = f"{_hive_name(hive)}\\{subkey}"

        self._snapshot: Dict[str, Any] = {}
        self._stop_event = None   # win32 manual-reset event
        self._thread: Optional[threading.Thread] = None
        self._active = False

    # ── Public ──────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._snapshot = _read_key_state(self.hive, self.subkey)
        self._stop_event = win32event.CreateEvent(None, True, False, None)
        self._active = True
        label = self.subkey.split("\\")[-1][:30]
        self._thread = threading.Thread(
            target=self._watch_loop,
            name=f"RegWatch-{label}",
            daemon=True,
        )
        self._thread.start()
        logger.info("Registry watcher started: %s", self.full_path)

    def stop(self) -> None:
        self._active = False
        if self._stop_event:
            win32event.SetEvent(self._stop_event)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        if self._stop_event:
            win32api.CloseHandle(self._stop_event)
            self._stop_event = None
        logger.debug("Registry watcher stopped: %s", self.full_path)

    # ── Background thread ────────────────────────────────────────────────────

    def _watch_loop(self) -> None:
        """Runs in a daemon thread; loops until stop() is called."""
        NOTIFY_FILTER = REG_NOTIFY_CHANGE_NAME | REG_NOTIFY_CHANGE_LAST_SET

        while self._active:
            key_handle = None
            notify_event = None
            try:
                # Open key with NOTIFY + READ access
                try:
                    key_handle = win32api.RegOpenKeyEx(
                        self.hive,
                        self.subkey,
                        0,
                        KEY_NOTIFY | KEY_READ,
                    )
                except Exception as exc:
                    logger.debug("Cannot open %s: %s — retrying in 5 s", self.full_path, exc)
                    result = win32event.WaitForSingleObject(self._stop_event, 5000)
                    if result == win32event.WAIT_OBJECT_0:
                        break
                    continue

                # Auto-reset notification event (one-shot)
                notify_event = win32event.CreateEvent(None, False, False, None)

                # Arm the notification (asynchronous so the thread isn't blocked
                # inside the kernel; we block on the event handle instead)
                win32api.RegNotifyChangeKeyValue(
                    key_handle,
                    True,           # watch entire subtree
                    NOTIFY_FILTER,
                    notify_event,
                    True,           # asynchronous
                )

                # Block until registry fires or stop is requested
                result = win32event.WaitForMultipleObjects(
                    [notify_event, self._stop_event],
                    False,                        # wait for any
                    win32event.INFINITE,
                )

                if result == win32event.WAIT_OBJECT_0 + 1:
                    # Stop event
                    break

                if result == win32event.WAIT_OBJECT_0 and self._active:
                    # Registry changed — diff and dispatch
                    new_snapshot = _read_key_state(self.hive, self.subkey)
                    changes = self._diff(self._snapshot, new_snapshot)
                    self._snapshot = new_snapshot
                    for change in changes:
                        asyncio.run_coroutine_threadsafe(
                            self._on_change(change), self._loop
                        )

            except Exception as exc:
                logger.error("Error in watcher for %s: %s", self.full_path, exc, exc_info=True)
                result = win32event.WaitForSingleObject(self._stop_event, 1000)
                if result == win32event.WAIT_OBJECT_0:
                    break
            finally:
                if notify_event:
                    try:
                        win32api.CloseHandle(notify_event)
                    except Exception:
                        pass
                if key_handle:
                    try:
                        win32api.RegCloseKey(key_handle)
                    except Exception:
                        pass

    # ── Snapshot diffing ─────────────────────────────────────────────────────

    def _diff(
        self,
        old: Dict[str, Any],
        new: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        changes: List[Dict[str, Any]] = []
        old_vals: Dict = old.get("values", {})
        new_vals: Dict = new.get("values", {})
        old_subs: Set[str] = old.get("subkeys", set())
        new_subs: Set[str] = new.get("subkeys", set())

        # Value additions and modifications
        for name, (data, vtype) in new_vals.items():
            if name not in old_vals:
                changes.append(self._make_change(
                    "value_create", name,
                    new_data=_fmt(data, vtype),
                ))
            elif old_vals[name] != (data, vtype):
                old_data, old_vtype = old_vals[name]
                changes.append(self._make_change(
                    "value_modify", name,
                    new_data=_fmt(data, vtype),
                    old_data=_fmt(old_data, old_vtype),
                ))

        # Value deletions
        for name in old_vals:
            if name not in new_vals:
                old_data, old_vtype = old_vals[name]
                changes.append(self._make_change(
                    "value_delete", name,
                    old_data=_fmt(old_data, old_vtype),
                ))

        # Subkey additions
        for name in new_subs - old_subs:
            changes.append(self._make_change(
                "key_create",
                registry_key=f"{self.full_path}\\{name}",
            ))

        # Subkey deletions
        for name in old_subs - new_subs:
            changes.append(self._make_change(
                "key_delete",
                registry_key=f"{self.full_path}\\{name}",
            ))

        # Generic catch-all: something changed but diffing found nothing
        # (e.g. deep subtree write; happens for large service key trees)
        if not changes:
            changes.append(self._make_change("subtree_change"))

        return changes

    def _make_change(
        self,
        operation: str,
        value_name: Optional[str] = None,
        new_data: Optional[str] = None,
        old_data: Optional[str] = None,
        registry_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "registry_operation": operation,
            "registry_key": registry_key or self.full_path,
            "registry_value": value_name,
            "registry_data": new_data,
            "old_registry_data": old_data,
            "severity_hint": self.severity,
        }


# ── Main monitor class ────────────────────────────────────────────────────────

class RegistryMonitor(BaseMonitor):
    """Windows registry monitor.

    Spawns one background thread per watched key.  Each thread uses
    RegNotifyChangeKeyValue so detection is instant — no polling interval.
    """

    # (hive, subkey, severity)  — ordered by security relevance
    DEFAULT_WATCHED_KEYS: List[Tuple[int, str, str]] = [
        # ── Autorun persistence (highest risk) ──────────────────────────────
        (HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",     "high"),
        (HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce", "high"),
        (HKEY_LOCAL_MACHINE, r"SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Run", "high"),
        (HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",     "high"),
        (HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce", "high"),

        # ── Winlogon hijacking ───────────────────────────────────────────────
        (HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon", "high"),

        # ── Image File Execution Options (debugger hijacking) ────────────────
        (HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options", "high"),

        # ── AppInit DLL injection ────────────────────────────────────────────
        (HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Windows", "high"),

        # ── LSA / credential providers ───────────────────────────────────────
        (HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Lsa", "critical"),

        # ── Windows Defender exclusions (AV evasion) ─────────────────────────
        (HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows Defender\Exclusions\Paths",     "critical"),
        (HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows Defender\Exclusions\Processes", "critical"),
        (HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows Defender\Exclusions\Extensions","critical"),

        # ── Services (persistence / lateral movement) ────────────────────────
        (HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services", "medium"),

        # ── Boot execute ─────────────────────────────────────────────────────
        (HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager", "medium"),

        # ── System environment variables ─────────────────────────────────────
        (HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment", "medium"),

        # ── Firewall policy ──────────────────────────────────────────────────
        (HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\SharedAccess\Parameters\FirewallPolicy", "medium"),
    ]

    def __init__(
        self,
        event_bus: EventBus,
        watched_keys: Optional[List[Tuple[int, str, str]]] = None,
    ):
        super().__init__(event_bus, "RegistryMonitor")
        self._watched_keys = watched_keys or self.DEFAULT_WATCHED_KEYS
        self._watchers: List[_RegistryKeyWatcher] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def get_capabilities(self) -> List[str]:
        return [
            "registry_value_create",
            "registry_value_modify",
            "registry_value_delete",
            "registry_key_create",
            "registry_key_delete",
        ]

    async def start(self) -> None:
        if self.running:
            logger.warning("%s already running", self.name)
            return

        if not PlatformDetector.is_windows():
            logger.info("%s: skipping — not Windows", self.name)
            return

        if not _winreg_ok:
            logger.warning("%s: 'winreg' not available — registry monitoring disabled", self.name)
            return

        if not _win32_ok:
            logger.warning(
                "%s: 'pywin32' not installed (pip install pywin32) — "
                "registry monitoring disabled",
                self.name,
            )
            return

        self.running = True
        self._loop = asyncio.get_running_loop()
        logger.info(
            "%s starting on %s — watching %d registry locations",
            self.name, PlatformDetector.get_platform_name(), len(self._watched_keys),
        )

        for hive, subkey, severity in self._watched_keys:
            watcher = _RegistryKeyWatcher(hive, subkey, severity, self._on_change, self._loop)
            try:
                watcher.start()
                self._watchers.append(watcher)
            except Exception as exc:
                logger.warning("Could not start watcher for %s\\%s: %s", _hive_name(hive), subkey, exc)

    async def stop(self) -> None:
        if not self.running:
            return
        self.running = False
        logger.info("%s stopping", self.name)
        for watcher in self._watchers:
            watcher.stop()
        self._watchers.clear()

    # ── Event dispatch ────────────────────────────────────────────────────────

    async def _on_change(self, change: Dict[str, Any]) -> None:
        """Called by a background thread (via run_coroutine_threadsafe)."""
        try:
            severity = self._determine_severity(change)
            operation = change["registry_operation"]

            logger.info(
                "RegistryMonitor [%s] %s | key=%s | value=%s | data=%s",
                severity.upper(),
                operation,
                change.get("registry_key"),
                change.get("registry_value"),
                change.get("registry_data"),
            )

            event = MonitorEvent(
                timestamp=get_local_time(),
                event_type="registry_change",
                platform=PlatformDetector.get_platform_name(),
                severity=severity,
                data={
                    "registry_key":       change.get("registry_key"),
                    "registry_operation": operation,
                    "registry_value":     change.get("registry_value"),
                    "registry_data":      change.get("registry_data"),
                    "old_registry_data":  change.get("old_registry_data"),
                },
            )
            await self.publish_event(event)
        except Exception as exc:
            logger.error("Error dispatching registry event: %s", exc, exc_info=True)

    def _determine_severity(self, change: Dict[str, Any]) -> str:
        hint      = change.get("severity_hint", "medium")
        operation = change.get("registry_operation", "")
        key_upper = (change.get("registry_key") or "").upper()

        # Defender exclusions added/changed → always critical
        if "DEFENDER" in key_upper and "EXCLUSION" in key_upper:
            if operation in ("value_create", "value_modify"):
                return "critical"

        # LSA providers modified → critical
        if r"CONTROL\LSA" in key_upper and operation in ("value_create", "value_modify"):
            return "critical"

        # Explicit critical hint from key table
        if hint == "critical":
            return "critical"

        # High-risk keys with write operations
        if hint == "high" and operation in ("value_create", "value_modify", "key_create"):
            return "high"

        # Deletions of high-risk entries
        if hint == "high" and operation in ("value_delete", "key_delete"):
            return "medium"

        # Medium-risk keys
        if hint == "medium" and operation in ("value_create", "value_modify", "key_create"):
            return "medium"

        # Generic subtree noise
        if operation == "subtree_change":
            return "low"

        return "low"
