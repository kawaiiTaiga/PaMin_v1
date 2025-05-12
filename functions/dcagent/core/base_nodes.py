# core/base_nodes.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List # List 추가
# GraphState, IdeaDBHandler 는 __init__ 이나 메서드 타입 힌트용으로 필요
from .models import GraphState
from .db_interface import IdeaDBHandler
import traceback # 오류 로깅 위해 추가

class BaseDivergenceNode(ABC):
    """ [Core Base] 발산 노드의 가장 기본적인 추상 클래스 """
    def __init__(self, db_handler: IdeaDBHandler):
        self.db_handler = db_handler

    @abstractmethod
    def diverge(self, state: GraphState) -> Dict[str, Any]:
        """
        [필수 구현] 구체적인 발산 로직 (아이디어 생성 및 DB 저장)
        출력: 상태 업데이트 딕셔너리 (주로 {"current_idea_ids": [...]})
        """
        pass

    # __call__ 은 기본 실행 로직을 제공하므로 여기에 두는 것이 좋음
    def __call__(self, state: GraphState) -> Dict[str, Any]:
        try:
            # BaseLLMDivergenceNode 등 하위 클래스에서 구체화될 수 있음
            current_step = state.get('step_counter', 0) + 1 # 다음 스텝 번호 계산 (주의: BaseLLM에서 실제 증가 처리)
            class_name = self.__class__.__name__
            print(f"\n--- 발산 단계 {current_step} ({class_name}) 시작 ---") # 실제 스텝은 diverge 결과에 따름
            result = self.diverge(state)
            # step_counter 업데이트는 diverge 구현체가 반환해야 함
            if 'error_message' in result: result['error_message'] = None
            # step_counter가 결과에 없으면 상태 업데이트 X
            return result
        except Exception as e:
            error_msg = f"[오류] 발산 노드 {self.__class__.__name__} 실행 중 오류: {e}"
            print(error_msg); print(traceback.format_exc())
            # 오류 발생 시 step_counter는 유지됨
            return {"error_message": error_msg}

class BaseConvergenceNode(ABC):
    """ [Core Base] 수렴 노드의 가장 기본적인 추상 클래스 """
    def __init__(self, db_handler: IdeaDBHandler):
        self.db_handler = db_handler

    @abstractmethod
    def converge(self, state: GraphState) -> Dict[str, Any]:
        """ [필수 구현] 구체적인 수렴 로직 """
        pass

    def __call__(self, state: GraphState) -> Dict[str, Any]:
        try:
            class_name = self.__class__.__name__
            print(f"\n--- 수렴 단계 {state.get('step_counter', 'N/A')} ({class_name}) 시작 ---")
            if not state.get('current_idea_ids'):
                print("  [정보] 고려할 아이디어 ID가 없습니다.")
                return {"selected_idea_id": None, "selected_idea_ids": [], "current_idea_ids": []}

            result = self.converge(state) # converge 메소드 호출

            # 결과 정리 (converge 결과에 없으면 current_idea_ids 비우기 등)
            if 'current_idea_ids' not in result:
                result['current_idea_ids'] = []
            if 'error_message' in result: result['error_message'] = None

            # --- 다음 디버깅 코드 추가 ---
            print(f"  DEBUG: Returning state update from {class_name}: {result}")
            # ---------------------------

            return result # 최종 상태 업데이트 반환
        except Exception as e:
            # ... (기존 오류 처리) ...
            error_msg = f"[오류] 수렴 노드 {self.__class__.__name__} 실행 중 오류: {e}"
            print(error_msg); print(traceback.format_exc())
            return {"error_message": error_msg, "selected_idea_id": None, "selected_idea_ids": [], "current_idea_ids": []}
