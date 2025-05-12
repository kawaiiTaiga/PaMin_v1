from __future__ import annotations

# food_tmi_library/nodes/gates.py
# 조건부 발산 게이트 및 관련 유틸리티

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Literal
import random
import traceback

# 라이브러리 내부 임포트
from ..core.models import GraphState
from ..core.db_interface import IdeaDBHandler

# --- 조건부 발산 게이트 ABC ---
class BaseConditionalDivergenceGate(ABC):
    """ [Applied Base] 조건부 발산 게이트의 기본 구조 """
    def __init__(self, db_handler: IdeaDBHandler): self.db_handler = db_handler
    @abstractmethod
    def _check_condition(self, state: GraphState) -> bool: pass
    @abstractmethod
    def _fetch_existing_ids(self, state: GraphState) -> List[str]: pass
    def __call__(self, state: GraphState) -> Dict[str, Any]:
        class_name = self.__class__.__name__
        print(f"\n--- 조건 검사 게이트 ({class_name}) 실행 ---")
        try:
            if self._check_condition(state):
                print("  조건 충족: 기존 아이디어 사용 경로로 진행합니다.")
                existing_ids = self._fetch_existing_ids(state)
                print(f"  선택 가능한 기존 아이디어 ID: {existing_ids}")
                # 기존 아이디어 사용 시 step_counter는 변경하지 않음
                return {"current_idea_ids": existing_ids, "_route": "SELECT_EXISTING", "step_counter": state.get('step_counter', 0)}
            else:
                print("  조건 불충족: 신규 아이디어 생성 경로로 진행합니다.")
                # 신규 생성 시에도 step_counter는 변경하지 않음 (다음 발산 노드가 할 일)
                return {"_route": "GENERATE_NEW", "step_counter": state.get('step_counter', 0)}
        except Exception as e:
            error_msg = f"[오류] 조건 검사 게이트 {class_name} 실행 중 오류: {e}"
            print(error_msg); print(traceback.format_exc())
            return {"error_message": error_msg, "_route": "GENERATE_NEW", "step_counter": state.get('step_counter', 0)}

# --- 라우팅 함수 ---
def route_generate_or_select(state: GraphState) -> Literal["GENERATE_NEW", "SELECT_EXISTING"]:
    """ 상태의 '_route' 값에 따라 경로를 반환합니다. """
    route = state.get("_route", "GENERATE_NEW")
    print(f"  라우팅 결정: '{route}' 경로")
    # 여기서 상태를 변경하지 않음 (예: _route 제거)
    return route

# --- 구체적인 게이트 구현체 예시 ---
class StepUsageGate(BaseConditionalDivergenceGate):
    """ 특정 단계/사용횟수 조건 게이트 """
    def __init__(self, db_handler: IdeaDBHandler, generation_step: int, max_usage: int):
        super().__init__(db_handler)
        self.generation_step = generation_step
        self.max_usage = max_usage
    def _check_condition(self, state: GraphState) -> bool:
        print(f"  DB 확인: 단계={self.generation_step}, 사용횟수<{self.max_usage} 인 아이디어 존재 여부?")
        return self.db_handler.check_ideas_exist(
            generation_step=self.generation_step, max_usage_count=self.max_usage)
    def _fetch_existing_ids(self, state: GraphState) -> List[str]:
        print(f"  DB 조회: 단계={self.generation_step}, 사용횟수<{self.max_usage} 인 아이디어 ID 목록")
        return self.db_handler.get_idea_ids(
            generation_step=self.generation_step, max_usage_count=self.max_usage)

class RandomSkipGate(BaseConditionalDivergenceGate):
    """ 랜덤 확률 조건 게이트 """
    def __init__(self, db_handler: IdeaDBHandler, skip_threshold: float = 0.8,
                 fallback_step: int = 1, fallback_max_usage: int = 3):
        super().__init__(db_handler);
        if not 0.0 <= skip_threshold <= 1.0: raise ValueError("skip_threshold는 0.0과 1.0 사이 값")
        self.skip_threshold = skip_threshold; self.fallback_step = fallback_step; self.fallback_max_usage = fallback_max_usage
    def _check_condition(self, state: GraphState) -> bool:
        chance = random.random(); skip = chance >= self.skip_threshold
        print(f"  랜덤 조건 확인: 생성값={chance:.4f}, 임계값={self.skip_threshold}, 건너뛰기={skip}")
        return skip
    def _fetch_existing_ids(self, state: GraphState) -> List[str]:
        print(f"  DB 조회 (Fallback): 단계={self.fallback_step}, 사용횟수<{self.fallback_max_usage} 인 아이디어 ID 목록")
        return self.db_handler.get_idea_ids(
            generation_step=self.fallback_step, max_usage_count=self.fallback_max_usage)