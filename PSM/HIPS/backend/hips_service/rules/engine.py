"""Rule engine for processing events against rules."""

import asyncio
from collections import defaultdict, deque
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import json
import logging
import psutil

from hips_service.rules.schema import Rule, RuleAction
from hips_service.rules.parser import RuleParser
from hips_service.rules.matcher import RuleMatcher
from hips_service.core.event_bus import MonitorEvent, EventBus
from hips_service.database.models import Alert, BlockedAction, get_db
from hips_service.utils.time import get_local_time

logger = logging.getLogger(__name__)


class RuleEngine:
    """Rule engine for processing monitoring events."""

    def __init__(self, event_bus: EventBus, rules_directory: str):
        """Initialize rule engine.

        Args:
            event_bus: Event bus to subscribe to
            rules_directory: Directory containing rule files
        """
        self.event_bus = event_bus
        self.rules_directory = rules_directory
        self.matcher = RuleMatcher()
        self.rules: Dict[str, Rule] = {}
        self._running = False
        self._max_alerts_per_hour: int = 100
        self._alert_rate_tracker: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))

    def load_rules(self):
        """Load all rules from rules directory."""
        logger.info(f"Loading rules from {self.rules_directory}")

        # Parse rules
        rules_list = RuleParser.parse_directory(self.rules_directory)

        # Store in dictionary by ID
        self.rules = {rule.id: rule for rule in rules_list}

        logger.info(f"Loaded {len(self.rules)} rules")

    def reload_rules(self):
        """Reload rules from directory."""
        logger.info("Reloading rules")
        self.rules.clear()
        self.load_rules()

    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """Get rule by ID.

        Args:
            rule_id: Rule identifier

        Returns:
            Rule object or None
        """
        return self.rules.get(rule_id)

    def get_all_rules(self) -> List[Rule]:
        """Get all loaded rules.

        Returns:
            List of all rules
        """
        return list(self.rules.values())

    def update_max_alerts_per_hour(self, limit: int):
        """Update the per-rule alert rate limit at runtime.

        Args:
            limit: Maximum alerts per rule per hour (minimum 1)
        """
        self._max_alerts_per_hour = max(1, limit)
        logger.info(f"Alert rate limit updated to {self._max_alerts_per_hour}/hour per rule")

    def add_rule(self, rule: Rule):
        """Add or update a rule.

        Args:
            rule: Rule to add
        """
        self.rules[rule.id] = rule
        logger.info(f"Added/updated rule: {rule.id}")

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule.

        Args:
            rule_id: ID of rule to remove

        Returns:
            True if removed, False if not found
        """
        if rule_id in self.rules:
            del self.rules[rule_id]
            logger.info(f"Removed rule: {rule_id}")
            return True
        return False

    async def start(self):
        """Start rule engine."""
        if self._running:
            return

        self._running = True
        logger.info("Rule engine starting")

        # Load rules
        self.load_rules()

        # Subscribe to all events
        self.event_bus.subscribe('*', self.process_event)

        logger.info("Rule engine started")

    async def stop(self):
        """Stop rule engine."""
        self._running = False
        logger.info("Rule engine stopped")

    async def process_event(self, event: MonitorEvent):
        """Process an event against all rules.

        Args:
            event: Event to process
        """
        try:
            matched_rules = []

            # Debug logging
            logger.debug(f"Processing event: {event.event_type} with data keys: {list(event.data.keys())}")

            # Check event against all rules
            for rule in self.rules.values():
                if self.matcher.matches(event, rule):
                    matched_rules.append(rule)
                    logger.debug(f"Rule matched: {rule.id}")
                else:
                    # Debug: log why rule didn't match
                    if rule.conditions.event_type == event.event_type:
                        logger.debug(f"Rule {rule.id} has correct event_type but conditions didn't match")

            # Execute actions for matched rules
            for rule in matched_rules:
                await self._execute_actions(event, rule)

        except Exception as e:
            logger.error(f"Error processing event: {e}", exc_info=True)

    async def _execute_actions(self, event: MonitorEvent, rule: Rule):
        """Execute actions for a matched rule.

        Args:
            event: Triggering event
            rule: Matched rule
        """
        logger.info(f"Rule matched: {rule.id} - {rule.name}")

        for action in rule.actions:
            try:
                if action.type == "alert":
                    await self._create_alert(event, rule, action)

                elif action.type == "block_process":
                    await self._block_process(event, rule, action)

                elif action.type == "log":
                    await self._log_event(event, rule, action)

                elif action.type == "notify":
                    await self._send_notification(event, rule, action)

            except Exception as e:
                logger.error(f"Error executing action {action.type} for rule {rule.id}: {e}", exc_info=True)

    def _save_alert_sync(self, alert: Alert, rule_name: str):
        """Save alert to database synchronously (runs in thread pool)."""
        with get_db() as db:
            db.add(alert)
            db.commit()
            logger.info(f"Alert created: {rule_name} (severity: {alert.severity})")

    def _save_blocked_action_sync(self, blocked: BlockedAction, pid: int, rule_name: str):
        """Save blocked action to database synchronously (runs in thread pool)."""
        with get_db() as db:
            db.add(blocked)
            db.commit()
            logger.warning(f"Blocked process PID {pid} (rule: {rule_name})")

    async def _create_alert(self, event: MonitorEvent, rule: Rule, action: RuleAction):
        """Create an alert in the database.

        Args:
            event: Triggering event
            rule: Matched rule
            action: Alert action
        """
        # Enforce per-rule alert rate limit
        now = get_local_time()
        tracker = self._alert_rate_tracker[rule.id]
        tracker.append(now)
        cutoff = now - timedelta(hours=1)
        recent = sum(1 for t in tracker if t >= cutoff)
        if recent > self._max_alerts_per_hour:
            logger.warning(
                f"Alert rate limit: suppressing {rule.id} "
                f"({recent}/{self._max_alerts_per_hour} alerts/hr)"
            )
            return

        # Get message template or use default
        message = action.message or f"Rule {rule.name} triggered"

        # Template substitution (simple version)
        try:
            message = message.format(**event.data) if '{' in message else message
        except KeyError as e:
            logger.warning(f"Template variable not found in event data: {e}")
            message = action.message or f"Rule {rule.name} triggered"

        # Create alert
        alert = Alert(
            timestamp=event.timestamp,
            rule_id=rule.id,
            rule_name=rule.name,
            severity=action.priority or rule.severity,
            category=rule.category,
            message=message,
            event_data=json.dumps(event.to_dict()),
            status='new',
            platform=event.platform
        )

        # Save to database in thread pool to avoid blocking the event loop
        try:
            await asyncio.to_thread(self._save_alert_sync, alert, rule.name)
        except Exception as e:
            logger.error(f"Error saving alert to database: {e}")
            raise

    async def _block_process(self, event: MonitorEvent, rule: Rule, action: RuleAction):
        """Block a process.

        Args:
            event: Triggering event
            rule: Matched rule
            action: Block action
        """
        # Get target PID
        target_field = action.target or "process_pid"
        pid = event.data.get(target_field.replace('.', '_'))

        if not pid:
            logger.warning(f"Cannot block process: PID not found in event data (field: {target_field})")
            return

        try:
            # Terminate process (cross-platform)
            psutil.Process(int(pid)).kill()

            # Log blocked action
            blocked = BlockedAction(
                timestamp=get_local_time(),
                rule_id=rule.id,
                action_type="process_blocked",
                target=str(pid),
                reason=f"Blocked by rule: {rule.name}",
                event_data=json.dumps(event.to_dict()),
                platform=event.platform
            )

            # Save to database in thread pool to avoid blocking the event loop
            try:
                await asyncio.to_thread(self._save_blocked_action_sync, blocked, pid, rule.name)
            except Exception as e:
                logger.error(f"Error saving blocked action to database: {e}")

        except ProcessLookupError:
            logger.warning(f"Process {pid} not found (already terminated)")
        except Exception as e:
            logger.error(f"Error blocking process {pid}: {e}", exc_info=True)

    async def _log_event(self, event: MonitorEvent, rule: Rule, action: RuleAction):
        """Log event (already logged by activity logger).

        Args:
            event: Triggering event
            rule: Matched rule
            action: Log action
        """
        # Events are already logged by activity monitor
        logger.info(f"Rule {rule.id} triggered log action for event {event.event_type}")

    async def _send_notification(self, event: MonitorEvent, rule: Rule, action: RuleAction):
        """POST a JSON alert payload to the configured webhook URL (if set)."""
        try:
            from hips_service.api.routes.settings import load_settings
            webhook_url = load_settings().get("alerts", {}).get("webhook_url") or ""
            webhook_url = webhook_url.strip()
        except Exception:
            webhook_url = ""

        message = action.message or f"Rule '{rule.name}' triggered"
        try:
            message = message.format(**event.data) if '{' in message else message
        except KeyError:
            pass

        if not webhook_url:
            logger.info(f"Notification (no webhook configured): {rule.name} — {message}")
            return

        # Validate webhook URL — block SSRF and non-http(s) schemes
        try:
            from urllib.parse import urlparse as _urlparse
            _p = _urlparse(webhook_url)
            if _p.scheme not in ("http", "https"):
                logger.warning(f"Webhook rejected (scheme {_p.scheme!r}): {rule.id}")
                return
            _host = (_p.hostname or "").lower()
            if not _host or _host in ("localhost", "127.0.0.1", "0.0.0.0", "::1") \
                    or _host.startswith("169.254"):
                logger.warning(f"Webhook rejected (SSRF target {_host!r}): {rule.id}")
                return
        except Exception as _e:
            logger.warning(f"Webhook URL parse error for rule {rule.id}: {_e}")
            return

        payload = {
            "rule_id": rule.id,
            "rule_name": rule.name,
            "severity": action.priority or rule.severity,
            "category": rule.category,
            "message": message,
            "event_type": event.event_type,
            "platform": event.platform,
            "timestamp": event.timestamp.isoformat(),
        }

        def _post():
            import urllib.request
            import json as _json
            body = _json.dumps(payload).encode()
            req = urllib.request.Request(
                webhook_url,
                data=body,
                headers={"Content-Type": "application/json", "User-Agent": "CHIPS-HIPS/1.0"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status

        try:
            status = await asyncio.to_thread(_post)
            logger.info(f"Webhook delivered ({status}): {rule.name} → {webhook_url}")
        except Exception as e:
            logger.warning(f"Webhook delivery failed for rule {rule.id}: {e}")
