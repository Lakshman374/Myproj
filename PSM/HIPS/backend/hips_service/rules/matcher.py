"""Rule matcher for checking if events match rule conditions."""

import re
from functools import lru_cache
from typing import Any, Dict
from datetime import datetime, timedelta
from collections import defaultdict, deque
import logging

from hips_service.rules.schema import Rule, RuleCondition
from hips_service.core.event_bus import MonitorEvent

logger = logging.getLogger(__name__)


class RuleMatcher:
    """Matches events against rule conditions."""

    def __init__(self):
        """Initialize rule matcher."""
        # Frequency tracking: rule_id -> {field_value -> [timestamps]}
        self._frequency_tracker = defaultdict(lambda: defaultdict(lambda: deque(maxlen=1000)))

    def matches(self, event: MonitorEvent, rule: Rule) -> bool:
        """Check if event matches rule.

        Args:
            event: Event to check
            rule: Rule to match against

        Returns:
            True if event matches rule, False otherwise
        """
        try:
            # Check if rule is enabled
            if not rule.enabled:
                return False

            # Check event type
            if event.event_type != rule.conditions.event_type:
                return False

            # Check platform
            if event.platform not in rule.conditions.platform:
                return False

            # Check 'all' conditions (AND logic)
            if rule.conditions.all:
                if not self._check_all_conditions(event, rule.conditions.all):
                    return False

            # Check 'any' conditions (OR logic)
            if rule.conditions.any:
                if not self._check_any_conditions(event, rule.conditions.any):
                    return False

            # Check frequency condition
            if rule.conditions.frequency:
                if not self._check_frequency_condition(event, rule):
                    return False

            return True

        except Exception as e:
            logger.error(f"Error matching event against rule {rule.id}: {e}", exc_info=True)
            return False

    def _check_all_conditions(self, event: MonitorEvent, conditions: list[RuleCondition]) -> bool:
        """Check if all conditions match (AND logic).

        Args:
            event: Event to check
            conditions: List of conditions

        Returns:
            True if all conditions match
        """
        for condition in conditions:
            if not self._check_condition(event, condition):
                return False
        return True

    def _check_any_conditions(self, event: MonitorEvent, conditions: list[RuleCondition]) -> bool:
        """Check if any condition matches (OR logic).

        Args:
            event: Event to check
            conditions: List of conditions

        Returns:
            True if any condition matches
        """
        for condition in conditions:
            if self._check_condition(event, condition):
                return True
        return False

    def _check_condition(self, event: MonitorEvent, condition: RuleCondition) -> bool:
        """Check if single condition matches.

        Args:
            event: Event to check
            condition: Condition to match

        Returns:
            True if condition matches
        """
        # Get field value from event
        field_value = self._get_field_value(event, condition.field)

        if field_value is None:
            logger.debug(f"Field '{condition.field}' not found in event data: {list(event.data.keys())}")
            return False

        # Apply operator
        operator = condition.operator
        expected = condition.value

        logger.debug(f"Checking: {condition.field}={field_value} {operator} {expected}")

        if operator == "equals":
            result = field_value == expected
            if not result:
                logger.debug(f"  Equals failed: '{field_value}' != '{expected}'")
            return result

        elif operator == "not_equals":
            return field_value != expected

        elif operator == "in":
            return field_value in expected if isinstance(expected, list) else False

        elif operator == "not_in":
            return field_value not in expected if isinstance(expected, list) else True

        elif operator == "contains":
            return str(expected) in str(field_value)

        elif operator == "not_contains":
            return str(expected) not in str(field_value)

        elif operator == "regex":
            pattern = self._get_regex_pattern(str(expected))
            return bool(pattern.search(str(field_value)))

        elif operator == "greater_than":
            return float(field_value) > float(expected)

        elif operator == "less_than":
            return float(field_value) < float(expected)

        elif operator == "greater_equal":
            return float(field_value) >= float(expected)

        elif operator == "less_equal":
            return float(field_value) <= float(expected)

        return False

    def _get_field_value(self, event: MonitorEvent, field_path: str) -> Any:
        """Get value from event using dot notation field path.

        Args:
            event: Event object
            field_path: Field path (e.g., 'process.name', 'file.extension')

        Returns:
            Field value or None if not found
        """
        # Split field path
        parts = field_path.split('.')

        # Start with event data
        value = event.data

        # Navigate through nested structure
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
                if value is None:
                    return None
            else:
                return None

        return value

    @staticmethod
    @lru_cache(maxsize=256)
    def _get_regex_pattern(pattern: str) -> re.Pattern:
        """Get compiled regex pattern, bounded cache of 256 entries (LRU eviction)."""
        try:
            return re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            logger.error(f"Invalid regex pattern '{pattern}': {e}")
            return re.compile(r'(?!.*)')

    def _check_frequency_condition(self, event: MonitorEvent, rule: Rule) -> bool:
        """Check frequency-based condition.

        Args:
            event: Event to check
            rule: Rule with frequency condition

        Returns:
            True if frequency threshold exceeded
        """
        freq = rule.conditions.frequency
        if not freq:
            return True

        # Parse timeframe
        timeframe_seconds = self._parse_timeframe(freq.timeframe)
        if timeframe_seconds is None:
            logger.error(f"Invalid timeframe in rule {rule.id}: {freq.timeframe}")
            return False

        # Get field value for grouping (e.g., process.pid)
        if freq.field:
            group_by = self._get_field_value(event, freq.field)
            if group_by is None:
                group_by = "default"
        else:
            group_by = "default"

        # Track this event
        tracker = self._frequency_tracker[rule.id][str(group_by)]
        tracker.append(event.timestamp)

        # Count events in time window
        cutoff = event.timestamp - timedelta(seconds=timeframe_seconds)
        recent_events = [ts for ts in tracker if ts >= cutoff]

        # Check if threshold exceeded
        if len(recent_events) >= freq.count:
            logger.info(f"Frequency threshold exceeded for rule {rule.id}: {len(recent_events)}/{freq.count} in {timeframe_seconds}s")
            return True

        return False

    def _parse_timeframe(self, timeframe: str) -> int:
        """Parse timeframe string to seconds.

        Args:
            timeframe: Timeframe string (e.g., '60s', '5m', '1h')

        Returns:
            Number of seconds or None if invalid
        """
        timeframe = timeframe.strip().lower()

        # Extract number and unit
        match = re.match(r'^(\d+)([smhd])$', timeframe)
        if not match:
            return None

        value = int(match.group(1))
        unit = match.group(2)

        if unit == 's':
            return value
        elif unit == 'm':
            return value * 60
        elif unit == 'h':
            return value * 3600
        elif unit == 'd':
            return value * 86400

        return None
