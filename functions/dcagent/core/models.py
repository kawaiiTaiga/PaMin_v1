from typing import TypedDict, List, Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid
from datetime import datetime, timezone

class Idea(BaseModel):
    content: str
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_node: Optional[str] = None
    generation_step: Optional[int] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)
    parent_id: Optional[str] = None
    usage_count: int = 0
    item_type: Optional[str] = None 

class GraphState(TypedDict):
    current_idea_ids: List[str]
    selected_idea_ids: List[str]
    selected_idea_id: Optional[str]
    step_counter: int
    error_message: Optional[str]
    final_selected_tmi_ids: List[str] 
    _route: Optional[str]