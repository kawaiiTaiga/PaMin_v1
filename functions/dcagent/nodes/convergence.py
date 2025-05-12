from __future__ import annotations

# nodes/convergence.py
import random
import traceback
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

# LangChain/LangGraph 관련 임포트
from langchain_core.runnables import Runnable
from langchain_core.runnables.utils import Input, Output

# 라이브러리 내부 임포트
from ..core.db_interface import IdeaDBHandler
from ..core.base_nodes import BaseConvergenceNode
from ..core.models import GraphState, Idea # Idea 모델 임포트



class RandomConvergenceNode(BaseConvergenceNode):
    """ [기존] 아이디어 ID 목록에서 무작위로 하나를 선택하는 일반적인 수렴 노드 """
    def converge(self, state: GraphState) -> Dict[str, Any]:
        idea_ids_to_consider = state.get('current_idea_ids', [])
        if not idea_ids_to_consider:
             # Base __call__ 에서 처리하지만 명시적으로 추가 (일관성)
            return {"selected_idea_id": None, "selected_idea_ids": [], "current_idea_ids": []}

        selected_id = random.choice(idea_ids_to_consider)
        print(f"  무작위 선택된 아이디어 ID: {selected_id}")
        success = self.db_handler.increment_usage_count(selected_id)
        if success: print(f"  DB 사용 횟수 증가 완료.")
        else: print(f"  [경고] DB 사용 횟수 증가 실패 (ID: {selected_id}).")

        # 상태 업데이트: 선택된 ID, 빈 current_idea_ids 반환. step_counter는 변경 안 함.
        # selected_idea_ids 는 빈 리스트로 설정하거나 생략 (상태 병합 방식에 따라 다름)
        return {"selected_idea_id": selected_id, "selected_idea_ids": [], "current_idea_ids": []}


# --- 새로 추가된 노드 ---
class SampleConvergenceNode(BaseConvergenceNode):
    """
    [신규] 아이디어 ID 목록(`current_idea_ids`)에서 지정된 개수(k)만큼
    무작위로 샘플링하여 `selected_idea_ids`로 반환하는 수렴 노드.
    """
    def __init__(self, db_handler: IdeaDBHandler, k: int = 3):
        super().__init__(db_handler)
        if k < 1:
            raise ValueError("k는 1 이상이어야 합니다.")
        self.k = k

    def converge(self, state: GraphState) -> Dict[str, Any]:
        idea_ids_to_consider = state.get('current_idea_ids', [])
        if not idea_ids_to_consider:
            # 선택할 ID가 없으면 빈 리스트 반환
            return {"selected_idea_id": None, "selected_idea_ids": [], "current_idea_ids": []}

        # 실제 샘플링할 개수 (k와 현재 ID 개수 중 작은 값)
        num_to_sample = min(self.k, len(idea_ids_to_consider))

        # 리스트에서 k개의 ID를 중복 없이 무작위 샘플링
        selected_ids = random.sample(idea_ids_to_consider, num_to_sample)
        print(f"  무작위 샘플링된 아이디어 IDs (요청 k={self.k}, 실제 선택={num_to_sample}): {selected_ids}")

        # (선택적) 선택된 모든 아이디어의 사용 횟수 증가
        success_count = 0
        for idea_id in selected_ids:
            if self.db_handler.increment_usage_count(idea_id):
                success_count += 1
        if success_count > 0:
            print(f"  DB 사용 횟수 증가 완료 ({success_count}/{len(selected_ids)}).")
        # 실패 로그는 필요에 따라 추가

        # 결과를 새로운 상태 필드 'selected_idea_ids'에 리스트로 반환
        # selected_idea_id 는 None 또는 첫번째 값 등으로 설정 가능하나, 여기선 None으로 둠
        # BaseConvergenceNode의 __call__ 기본 동작에 따라 current_idea_ids는 비워짐
        return {"selected_idea_id": None, "selected_idea_ids": selected_ids, "current_idea_ids": []}
    

class BaseLLMConvergenceNode(BaseConvergenceNode):
    """
    [Applied Base] LLM Runnable을 사용하여 후보 아이디어 목록에서
    아이디어를 지능적으로 선택(수렴)하는 노드의 기본 구조.
    """
    def __init__(self, db_handler: IdeaDBHandler, runnable: Runnable):
        """
        Args:
            db_handler: 데이터베이스 핸들러 인스턴스.
            runnable: LLM 호출에 사용될 LangChain Runnable 인스턴스.
        """
        super().__init__(db_handler)
        if runnable is None: # Runnable이 필수임을 명시
             raise ValueError("BaseLLMConvergenceNode requires a valid Runnable instance.")
        self.runnable = runnable

    @abstractmethod
    def _prepare_llm_input(self, candidate_ideas: List[Idea], state: GraphState) -> Optional[Input]:
        """
        [구현 필요] 후보 아이디어 목록과 현재 상태를 기반으로
        LLM Runnable에 전달할 입력을 준비합니다.
        입력 준비가 불가능하면 None을 반환합니다.
        """
        pass

    @abstractmethod
    def _parse_llm_output(self, llm_output: Output, candidate_ideas: List[Idea]) -> List[str]:
        """
        [구현 필요] LLM Runnable의 출력을 파싱하여 선택된 아이디어들의
        *ID 목록*을 반환합니다. LLM 출력이 ID를 직접 반환하지 않는 경우,
        출력 내용과 후보 아이디어 목록을 비교하여 ID를 찾아야 할 수 있습니다.
        """
        pass

    # BaseConvergenceNode의 converge 메소드를 오버라이드
    def converge(self, state: GraphState) -> Dict[str, Any]:
        """ 후보 아이디어 목록을 LLM으로 평가/선택하여 상태를 업데이트합니다. """
        class_name = self.__class__.__name__
        idea_ids_to_consider = state.get('current_idea_ids', [])
        if not idea_ids_to_consider:
            print(f"  [{class_name}] 선택할 후보 아이디어가 없습니다.")
            return {"selected_idea_id": None, "selected_idea_ids": [], "current_idea_ids": []}

        print(f"  [{class_name}] 후보 아이디어 {len(idea_ids_to_consider)}개 로드 중...")
        candidate_ideas = self.db_handler.get_ideas(idea_ids_to_consider)
        if not candidate_ideas:
            print(f"  [{class_name}][오류] 후보 아이디어 ID({idea_ids_to_consider})로 DB에서 내용을 찾을 수 없습니다.")
            return {"selected_idea_id": None, "selected_idea_ids": [], "current_idea_ids": [], "error_message": "Failed to load candidate ideas"}

        # 1. LLM 입력 준비 (하위 클래스에 위임)
        try:
            llm_input = self._prepare_llm_input(candidate_ideas, state)
        except Exception as e:
            error_msg = f"LLM 입력 준비 중 오류: {e}"
            print(f"  [{class_name}][오류] {error_msg}")
            print(traceback.format_exc())
            # 입력 준비 실패 시 비상 로직 또는 에러 반환
            return {"selected_idea_id": None, "selected_idea_ids": [], "current_idea_ids": [], "error_message": error_msg}

        if llm_input is None:
            print(f"  [{class_name}][정보] LLM 입력 준비 불가. 아이디어를 선택할 수 없습니다.")
            return {"selected_idea_id": None, "selected_idea_ids": [], "current_idea_ids": []}

        # 2. LLM 실행
        print(f"  [{class_name}] LLM 실행 시작...")
        try:
            llm_output = self.runnable.invoke(llm_input)
            print(f"  [{class_name}] LLM 실행 완료.")
            # 상세 출력이 필요하면 주석 해제
            # print(f"  [{class_name}] LLM Output: {llm_output}")
        except Exception as e:
            error_msg = f"LLM Runnable 실행 오류: {e}"
            print(f"  [{class_name}][오류] {error_msg}")
            print(traceback.format_exc())
            return {"selected_idea_id": None, "selected_idea_ids": [], "current_idea_ids": [], "error_message": error_msg}

        # 3. LLM 출력 파싱 (하위 클래스에 위임)
        selected_idea_ids: List[str] = []
        try:
            selected_idea_ids = self._parse_llm_output(llm_output, candidate_ideas)
            print(f"  [{class_name}] LLM 출력 파싱 완료. 선택된 ID: {selected_idea_ids}")
        except Exception as e:
             error_msg = f"LLM 출력 파싱 오류: {e}"
             print(f"  [{class_name}][오류] {error_msg}")
             print(traceback.format_exc())
             return {"selected_idea_id": None, "selected_idea_ids": [], "current_idea_ids": [], "error_message": error_msg}

        if not selected_idea_ids:
            print(f"  [{class_name}][정보] LLM이 아이디어를 선택하지 않았거나 파싱에 실패했습니다.")
            return {"selected_idea_id": None, "selected_idea_ids": [], "current_idea_ids": []}

        # 4. 선택된 아이디어 사용 횟수 증가
        success_count = 0
        for idea_id in selected_idea_ids:
            # 선택된 ID가 실제로 후보 목록에 있었는지 재확인 (파싱 오류 방지)
            if idea_id in idea_ids_to_consider:
                if self.db_handler.increment_usage_count(idea_id):
                    success_count += 1
            else:
                 print(f"  [{class_name}][경고] 파싱된 ID '{idea_id}'가 원본 후보 목록에 없습니다.")
        if success_count > 0:
            print(f"  [{class_name}] 선택된 아이디어 DB 사용 횟수 증가 완료 ({success_count}/{len(selected_idea_ids)}).")

        # 5. 상태 업데이트 반환
        # 유효하게 선택된 (원본 후보에 있던) ID들만 최종 결과로 사용
        valid_selected_ids = [id for id in selected_idea_ids if id in idea_ids_to_consider]

        final_selected_id = valid_selected_ids[0] if len(valid_selected_ids) == 1 else None
        final_selected_ids = valid_selected_ids # 실제 유효한 ID 리스트

        print(f"  [{class_name}] 최종 상태 업데이트: selected_id='{final_selected_id}', selected_ids={final_selected_ids}")
        return {
            "selected_idea_id": final_selected_id,
            "selected_idea_ids": final_selected_ids,
            "current_idea_ids": [] # 다음 단계로 넘길 후보는 없음
        }