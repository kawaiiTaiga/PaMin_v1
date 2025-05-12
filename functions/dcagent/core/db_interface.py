# dcagent/core/db_interface.py
from __future__ import annotations # 파일 맨 위 필수

from typing import Protocol, List, Dict, Any, Optional, Set
from .models import Idea # Idea 임포트

class IdeaDBHandler(Protocol):
    """ 아이디어 DB 상호작용을 위한 인터페이스 정의 """
    def save_ideas(self, ideas_data: List[Dict[str, Any]]) -> List[str]: ...
    def get_ideas(self, idea_ids: List[str]) -> List[Idea]: ...
    def get_idea(self, idea_id: str) -> Optional[Idea]: ...
    def increment_usage_count(self, idea_id: str) -> bool: ...
    def clear_all_ideas(self) -> None: ...
    def get_ideas_by_step(self, step: int) -> List[Idea]: ... # V2에서 추가됨
    def check_content_exists(self, contents: List[str]) -> Set[str]: ... # 중복 확인용

    # --- 수정된 메소드 시그니처 (item_type 파라미터 추가) ---
    def check_ideas_exist(self,
                          generation_step: Optional[int] = None,
                          max_usage_count: Optional[int] = None,
                          item_type: Optional[str] = None # 추가
                          ) -> bool: ...

    def get_idea_ids(self,
                     generation_step: Optional[int] = None,
                     max_usage_count: Optional[int] = None,
                     item_type: Optional[str] = None # 추가
                     ) -> List[str]: ...

    def count_ideas(self,
                    generation_step: Optional[int] = None,
                    item_type: Optional[str] = None # 추가
                    ) -> int: ...