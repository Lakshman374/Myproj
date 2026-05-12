"""Rule schema definitions using Pydantic."""

from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Any, Union
from datetime import datetime


class RuleCondition(BaseModel):
    """Single rule condition."""

    field: str = Field(..., description="Field path to check (e.g., 'process.name')")
    operator: Literal[
        "equals", "not_equals", "in", "not_in",
        "contains", "not_contains", "regex",
        "greater_than", "less_than", "greater_equal", "less_equal"
    ] = Field(..., description="Comparison operator")
    value: Union[str, int, float, List[str], List[int]] = Field(..., description="Value to compare against")


class FrequencyCondition(BaseModel):
    """Frequency-based condition for detecting patterns over time."""

    count: int = Field(..., ge=1, description="Number of events to trigger")
    timeframe: str = Field(..., description="Time window (e.g., '60s', '5m', '1h')")
    field: Optional[str] = Field(None, description="Field to group by (e.g., 'process.pid')")


class RuleConditions(BaseModel):
    """Rule conditions container."""

    event_type: str = Field(..., description="Type of event to match")
    platform: List[str] = Field(
        default_factory=lambda: ["linux", "windows"],
        description="Platforms this rule applies to"
    )
    all: Optional[List[RuleCondition]] = Field(None, description="All conditions must match (AND)")
    any: Optional[List[RuleCondition]] = Field(None, description="Any condition must match (OR)")
    frequency: Optional[FrequencyCondition] = Field(None, description="Frequency-based detection")


class RuleAction(BaseModel):
    """Action to take when rule matches."""

    type: Literal["block_process", "alert", "log", "notify"] = Field(..., description="Action type")
    priority: Optional[Literal["low", "medium", "high", "critical"]] = Field(None, description="Alert priority")
    message: Optional[str] = Field(None, description="Custom message template")
    target: Optional[str] = Field(None, description="Target field for action (e.g., 'process.pid')")


class RuleMetadata(BaseModel):
    """Rule metadata."""

    author: str = Field(default="user", description="Rule author")
    created: Optional[str] = Field(None, description="Creation date")
    updated: Optional[str] = Field(None, description="Last update date")
    references: List[str] = Field(default_factory=list, description="Reference URLs")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")


class Rule(BaseModel):
    """Complete rule definition."""

    id: str = Field(..., description="Unique rule identifier")
    name: str = Field(..., description="Human-readable rule name")
    description: str = Field(..., description="Rule description")
    enabled: bool = Field(default=True, description="Whether rule is active")
    severity: Literal["low", "medium", "high", "critical"] = Field(..., description="Rule severity")
    category: str = Field(..., description="Rule category (e.g., 'ransomware', 'privilege_escalation')")
    conditions: RuleConditions = Field(..., description="Rule conditions")
    actions: List[RuleAction] = Field(..., description="Actions to take on match")
    metadata: Optional[RuleMetadata] = Field(default_factory=RuleMetadata, description="Rule metadata")

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "id": "ransomware-rapid-encryption",
                "name": "Ransomware Rapid File Encryption Detection",
                "description": "Detects rapid file modifications with encryption-like behavior",
                "enabled": True,
                "severity": "critical",
                "category": "ransomware",
                "conditions": {
                    "event_type": "file_modify",
                    "platform": ["linux", "windows"],
                    "all": [
                        {
                            "field": "file.extension",
                            "operator": "in",
                            "value": [".encrypted", ".locked", ".crypto"]
                        }
                    ],
                    "frequency": {
                        "count": 50,
                        "timeframe": "60s",
                        "field": "process.pid"
                    }
                },
                "actions": [
                    {"type": "block_process", "target": "process.pid"},
                    {"type": "alert", "priority": "critical", "message": "Ransomware detected"}
                ],
                "metadata": {
                    "author": "system",
                    "tags": ["ransomware", "file-encryption"]
                }
            }
        }
