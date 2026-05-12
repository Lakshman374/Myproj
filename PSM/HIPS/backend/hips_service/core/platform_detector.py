"""Platform detection utility for cross-platform support."""

import platform
from enum import Enum
from typing import Optional


class Platform(Enum):
    """Supported platforms."""
    LINUX = "linux"
    WINDOWS = "windows"
    UNSUPPORTED = "unsupported"


class PlatformDetector:
    """Detects the current operating system platform."""

    _cached_platform: Optional[Platform] = None

    @classmethod
    def get_platform(cls) -> Platform:
        """Get the current platform.

        Returns:
            Platform enum value
        """
        if cls._cached_platform is None:
            system = platform.system().lower()
            if system == "linux":
                cls._cached_platform = Platform.LINUX
            elif system == "windows":
                cls._cached_platform = Platform.WINDOWS
            else:
                cls._cached_platform = Platform.UNSUPPORTED

        return cls._cached_platform

    @classmethod
    def is_linux(cls) -> bool:
        """Check if running on Linux.

        Returns:
            True if Linux, False otherwise
        """
        return cls.get_platform() == Platform.LINUX

    @classmethod
    def is_windows(cls) -> bool:
        """Check if running on Windows.

        Returns:
            True if Windows, False otherwise
        """
        return cls.get_platform() == Platform.WINDOWS

    @classmethod
    def is_supported(cls) -> bool:
        """Check if platform is supported.

        Returns:
            True if supported, False otherwise
        """
        return cls.get_platform() in (Platform.LINUX, Platform.WINDOWS)

    @classmethod
    def get_platform_name(cls) -> str:
        """Get human-readable platform name.

        Returns:
            Platform name string
        """
        return cls.get_platform().value
