"""Rules API routes."""

import io
import yaml
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from typing import List
from pydantic import BaseModel

from hips_service.rules.schema import Rule
from hips_service.rules.parser import RuleParser

router = APIRouter()

# This will be injected by main.py
_rule_engine = None


def set_rule_engine(engine):
    """Set rule engine instance."""
    global _rule_engine
    _rule_engine = engine


class RuleCreateRequest(BaseModel):
    """Rule creation request."""
    rule: Rule


@router.get("", response_model=List[Rule])
async def get_rules():
    """Get all rules."""
    if not _rule_engine:
        raise HTTPException(status_code=500, detail="Rule engine not initialized")

    return _rule_engine.get_all_rules()


@router.get("/export")
async def export_rules():
    """Export all rules as a multi-document YAML file."""
    if not _rule_engine:
        raise HTTPException(status_code=500, detail="Rule engine not initialized")

    rules = _rule_engine.get_all_rules()
    documents = [{"rule": rule.model_dump(exclude_none=True)} for rule in rules]
    content = yaml.dump_all(documents, default_flow_style=False, sort_keys=False, allow_unicode=True)

    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="application/x-yaml",
        headers={"Content-Disposition": "attachment; filename=hips-rules.yaml"},
    )


@router.get("/{rule_id}", response_model=Rule)
async def get_rule(rule_id: str):
    """Get specific rule by ID."""
    if not _rule_engine:
        raise HTTPException(status_code=500, detail="Rule engine not initialized")

    rule = _rule_engine.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    return rule


@router.post("", response_model=Rule)
async def create_rule(request: RuleCreateRequest):
    """Create a new rule."""
    if not _rule_engine:
        raise HTTPException(status_code=500, detail="Rule engine not initialized")

    rule = request.rule

    # Check if rule already exists
    if _rule_engine.get_rule(rule.id):
        raise HTTPException(status_code=409, detail="Rule with this ID already exists")

    # Add rule to engine
    _rule_engine.add_rule(rule)

    # Save to file
    file_path = f"{_rule_engine.rules_directory}/{rule.id}.yaml"
    RuleParser.save_rule(rule, file_path)

    return rule


@router.put("/{rule_id}", response_model=Rule)
async def update_rule(rule_id: str, request: RuleCreateRequest):
    """Update an existing rule."""
    if not _rule_engine:
        raise HTTPException(status_code=500, detail="Rule engine not initialized")

    rule = request.rule

    # Check if rule exists
    if not _rule_engine.get_rule(rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")

    # URL path parameter is authoritative — prevent body ID from silently
    # creating a different rule or leaving the original untouched.
    rule.id = rule_id

    # Update rule
    _rule_engine.add_rule(rule)

    # Save to file
    file_path = f"{_rule_engine.rules_directory}/{rule_id}.yaml"
    RuleParser.save_rule(rule, file_path)

    return rule


@router.delete("/{rule_id}")
async def delete_rule(rule_id: str):
    """Delete a rule."""
    import os
    if not _rule_engine:
        raise HTTPException(status_code=500, detail="Rule engine not initialized")

    if not _rule_engine.remove_rule(rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")

    file_path = os.path.join(_rule_engine.rules_directory, f"{rule_id}.yaml")
    if os.path.exists(file_path):
        os.remove(file_path)
        logger.info(f"Deleted rule file: {file_path}")

    return {"message": "Rule deleted", "rule_id": rule_id}


@router.put("/{rule_id}/toggle")
async def toggle_rule(rule_id: str):
    """Enable/disable a rule."""
    if not _rule_engine:
        raise HTTPException(status_code=500, detail="Rule engine not initialized")

    rule = _rule_engine.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    # Toggle enabled status
    rule.enabled = not rule.enabled

    # Update in engine
    _rule_engine.add_rule(rule)

    # Save to file
    file_path = f"{_rule_engine.rules_directory}/{rule.id}.yaml"
    RuleParser.save_rule(rule, file_path)

    return {"message": "Rule toggled", "rule_id": rule_id, "enabled": rule.enabled}


@router.post("/reload")
async def reload_rules():
    """Reload all rules from disk."""
    if not _rule_engine:
        raise HTTPException(status_code=500, detail="Rule engine not initialized")

    _rule_engine.reload_rules()

    return {"message": "Rules reloaded", "count": len(_rule_engine.rules)}


@router.post("/import", response_model=Rule)
async def import_rule(file: UploadFile = File(...)):
    """Import a rule from YAML file upload.

    Args:
        file: YAML file containing the rule

    Returns:
        Imported Rule object
    """
    if not _rule_engine:
        raise HTTPException(status_code=500, detail="Rule engine not initialized")

    # Check file extension
    if not file.filename.endswith(('.yaml', '.yml')):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only .yaml and .yml files are allowed"
        )

    try:
        # Read file content
        content = await file.read()
        yaml_content = content.decode('utf-8')

        # Parse YAML content
        rule = RuleParser.parse_yaml_content(yaml_content)

        # Check if rule already exists
        existing_rule = _rule_engine.get_rule(rule.id)
        if existing_rule:
            raise HTTPException(
                status_code=409,
                detail=f"Rule with ID '{rule.id}' already exists. Delete it first or use a different ID."
            )

        # Add rule to engine
        _rule_engine.add_rule(rule)

        # Save to file
        file_path = f"{_rule_engine.rules_directory}/{rule.id}.yaml"
        RuleParser.save_rule(rule, file_path)

        return rule

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error importing rule: {str(e)}")
