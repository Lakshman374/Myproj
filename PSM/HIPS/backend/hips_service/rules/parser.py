"""YAML rule parser."""

import yaml
from pathlib import Path
from typing import List, Dict, Any
import logging

from hips_service.rules.schema import Rule

logger = logging.getLogger(__name__)


class RuleParser:
    """Parser for YAML rule files."""

    @staticmethod
    def parse_file(file_path: str) -> Rule:
        """Parse a single rule file.

        Args:
            file_path: Path to YAML rule file

        Returns:
            Parsed Rule object

        Raises:
            ValueError: If rule is invalid
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            if not data or 'rule' not in data:
                raise ValueError("Invalid rule file: missing 'rule' key")

            rule_data = data['rule']
            return Rule(**rule_data)

        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error in {file_path}: {e}")
            raise ValueError(f"Invalid YAML in {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error parsing rule file {file_path}: {e}")
            raise

    @staticmethod
    def parse_yaml_content(yaml_content: str) -> Rule:
        """Parse YAML content string.

        Args:
            yaml_content: YAML string content

        Returns:
            Parsed Rule object

        Raises:
            ValueError: If rule is invalid
        """
        try:
            data = yaml.safe_load(yaml_content)

            if not data or 'rule' not in data:
                raise ValueError("Invalid rule: missing 'rule' key")

            rule_data = data['rule']
            return Rule(**rule_data)

        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error: {e}")
            raise ValueError(f"Invalid YAML: {e}")
        except Exception as e:
            logger.error(f"Error parsing rule: {e}")
            raise

    @staticmethod
    def parse_directory(directory_path: str) -> List[Rule]:
        """Parse all rule files in a directory.

        Args:
            directory_path: Path to directory containing rule files

        Returns:
            List of parsed Rule objects
        """
        rules = []
        directory = Path(directory_path)

        if not directory.exists():
            logger.warning(f"Rule directory does not exist: {directory_path}")
            return rules

        # Find all YAML files
        for file_path in directory.glob('**/*.yaml'):
            try:
                rule = RuleParser.parse_file(str(file_path))
                rules.append(rule)
                logger.info(f"Loaded rule: {rule.id} from {file_path}")
            except Exception as e:
                logger.error(f"Failed to load rule from {file_path}: {e}")

        # Also check .yml extension
        for file_path in directory.glob('**/*.yml'):
            try:
                rule = RuleParser.parse_file(str(file_path))
                rules.append(rule)
                logger.info(f"Loaded rule: {rule.id} from {file_path}")
            except Exception as e:
                logger.error(f"Failed to load rule from {file_path}: {e}")

        logger.info(f"Loaded {len(rules)} rules from {directory_path}")
        return rules

    @staticmethod
    def rule_to_yaml(rule: Rule) -> str:
        """Convert Rule object to YAML string.

        Args:
            rule: Rule object to convert

        Returns:
            YAML string representation
        """
        data = {'rule': rule.model_dump(exclude_none=True)}
        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    @staticmethod
    def save_rule(rule: Rule, file_path: str):
        """Save rule to YAML file.

        Args:
            rule: Rule object to save
            file_path: Path to save file
        """
        yaml_content = RuleParser.rule_to_yaml(rule)

        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(yaml_content)

        logger.info(f"Saved rule {rule.id} to {file_path}")
