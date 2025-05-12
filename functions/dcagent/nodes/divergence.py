from __future__ import annotations

# dcagent/nodes/divergence.py
from abc import abstractmethod
from typing import Dict, Any, List, Optional, Union
from langchain_core.runnables import Runnable
from langchain_core.runnables.utils import Input, Output
import traceback # traceback 임포트 추가 (오류 로깅용)
import random
# 라이브러리 내부 임포트
from ..core.base_nodes import BaseDivergenceNode
from ..core.models import GraphState
from ..core.db_interface import IdeaDBHandler

class BaseLLMDivergenceNode(BaseDivergenceNode):
    """ [Applied Base] LLM Runnable을 사용하는 발산 노드의 기본 구조 """
    def __init__(self, db_handler: IdeaDBHandler, runnable: Runnable):
        super().__init__(db_handler)
        self.runnable = runnable

    @abstractmethod
    def _prepare_input(self, state: GraphState) -> Union[None, Input, List[Input]]:
        pass

    @abstractmethod
    def _parse_output(self, runnable_output: Output) -> List[Dict[str, Any]]:
        pass

    def diverge(self, state: GraphState) -> Dict[str, Any]:
        prepared_input = self._prepare_input(state)
        if prepared_input is None:
            print("  [정보] Runnable 입력 준비 결과가 없어 발산을 건너뜁니다.") # '뜁' 수정
            return {"current_idea_ids": [], "step_counter": state.get('step_counter', 0)}

        is_batch = isinstance(prepared_input, list)
        runnable_outputs: Union[Output, List[Output]] = None
        parent_contexts: Optional[List[Any]] = None

        try:
            if is_batch:
                if not prepared_input:
                     print("  [정보] Runnable 입력 리스트가 비어있어 발산을 건너뜁니다.") # '뜁' 수정
                     return {"current_idea_ids": [], "step_counter": state.get('step_counter', 0)}

                print(f"  Runnable ({self.runnable.__class__.__name__}) 배치 실행 시작 ({len(prepared_input)}개)...")
                parent_contexts = [item.pop('_parent_context', None) if isinstance(item, dict) else None for item in prepared_input]
                runnable_outputs = self.runnable.batch(prepared_input)
                print(f"  Runnable 배치 실행 완료.")
            else:
                print(f"  Runnable ({self.runnable.__class__.__name__}) 단일 실행 시작...")
                runnable_outputs = self.runnable.invoke(prepared_input)
                print(f"  Runnable 단일 실행 완료.")
        except Exception as e:
             error_msg = f"Runnable 실행 오류: {e}"
             print(f"  [오류] {error_msg}")
             print(traceback.format_exc()) # 상세 오류 출력 추가
             return {"error_message": error_msg, "current_idea_ids": [], "step_counter": state.get('step_counter', 0)}

        all_new_idea_ids = []
        current_step = state.get('step_counter', 0) + 1
        source_node_name = self.__class__.__name__
        parent_id_for_linking = state.get('selected_idea_id')
        if not parent_id_for_linking and state.get('selected_idea_ids'):
            pass # 여기서는 selected_idea_id가 없을 경우 별도 처리 안 함

        outputs_to_process = runnable_outputs if is_batch else [runnable_outputs]
        contexts_to_process = parent_contexts if is_batch else [None]

        for i, output_item in enumerate(outputs_to_process):
            context = contexts_to_process[i]
            effective_parent_id = context if context else parent_id_for_linking

            # --- 중복 검사 로직 추가 ---
            try:
                parsed_ideas_data = self._parse_output(output_item)
                if not parsed_ideas_data:
                    print(f"  항목 {i}: 파싱 결과 없음.")
                    continue

                print(f"  항목 {i}: 파싱 완료. 아이디어 {len(parsed_ideas_data)}개 추출.")

                # 저장할 후보 콘텐츠 추출
                contents_to_check = [
                    idea['content'] for idea in parsed_ideas_data
                    if 'content' in idea and isinstance(idea['content'], str) and idea['content'].strip()
                ]

                unique_ideas_data = parsed_ideas_data # 기본값은 모두 고유하다고 가정
                if contents_to_check:
                    # DB에서 이미 존재하는 콘텐츠 확인
                    existing_contents = self.db_handler.check_content_exists(contents_to_check)

                    if existing_contents:
                        # 중복되지 않은 아이디어만 필터링
                        unique_ideas_data = [
                            idea for idea in parsed_ideas_data
                            if idea.get('content') not in existing_contents
                        ]
                        num_skipped = len(parsed_ideas_data) - len(unique_ideas_data)
                        if num_skipped > 0:
                             print(f"  [정보] 항목 {i}: 중복 콘텐츠 {num_skipped}개 발견하여 저장 생략.")

                # --- 중복 검사 로직 끝 ---

                # 고유한 아이디어만 저장 준비
                ideas_to_save = []
                for idea_data in unique_ideas_data: # 필터링된 데이터 사용
                    # content가 비어있거나 None인 경우 제외 (파싱 오류 등 대비)
                    if not idea_data.get('content'):
                        continue
                    idea_data.setdefault('source_node', source_node_name)
                    idea_data.setdefault('generation_step', current_step)
                    idea_data.setdefault('parent_id', effective_parent_id)
                    ideas_to_save.append(idea_data)

                if ideas_to_save:
                    try:
                        new_idea_ids = self.db_handler.save_ideas(ideas_to_save)
                        print(f"  항목 {i}: DB에 고유 아이디어 {len(new_idea_ids)}개 저장 완료 (부모 컨텍스트: {context}). IDs: {new_idea_ids}")
                        all_new_idea_ids.extend(new_idea_ids)
                    except Exception as e:
                         print(f"  [오류] DB 저장 중 오류 발생 (항목 {i}): {e}")
                         print(traceback.format_exc()) # 상세 오류 출력 추가
                         # 오류 발생해도 일단 계속 진행 (부분 성공 가능성)
                         # 필요시 여기서 에러 상태를 반환하도록 수정 가능

            except Exception as e: # 파싱 또는 중복 검사 중 오류 처리
                print(f"  [오류] 항목 {i} 처리 중 오류 발생: {e}")
                print(traceback.format_exc()) # 상세 오류 출력 추가
                continue # 다음 항목 처리 시도

        # 최종 결과 반환
        return_state = {"current_idea_ids": all_new_idea_ids, "step_counter": current_step}
        # 만약 처리 중 오류가 있었다면 error_message 필드 추가 가능 (선택적)
        # if any_error_occurred: return_state["error_message"] = "..."
        return return_state
    

# --- Few-Shot 기능이 추가된 새로운 베이스 클래스 ---
class BaseFewShotLLMDivergenceNode(BaseLLMDivergenceNode):
    """
    [Applied Base] DB에서 가져온 아이디어를 Few-Shot 예시로 활용하여
    LLM 입력을 준비하는 발산 노드의 기본 구조.
    BaseLLMDivergenceNode를 상속받아 _prepare_input 동작을 확장합니다.
    """
    def __init__(self, db_handler: IdeaDBHandler, runnable: Runnable,
                 num_shots: int = 3, # 사용할 예시(Shot) 개수
                 shot_generation_step: Optional[int] = None, # 예시를 가져올 단계
                 shot_max_usage_count: Optional[int] = None, # 예시 최대 사용 횟수 필터
                 select_shots_randomly: bool = True,
                 shot_item_type: Optional[str] = None): # 예시 랜덤 선택 여부
        super().__init__(db_handler, runnable)
        if num_shots < 0:
            raise ValueError("num_shots는 0 이상이어야 합니다.")
        self.num_shots = num_shots
        self.shot_generation_step = shot_generation_step
        self.shot_max_usage_count = shot_max_usage_count
        self.select_shots_randomly = select_shots_randomly
        self.shot_item_type = shot_item_type


    @abstractmethod
    def _get_base_topic(self, state: GraphState) -> Optional[Dict[str, Any]]:
        """
        [구현 필요] Few-shot 예시 없이, 기본적인 생성 주제/지시사항을 반환합니다.
        Runnable의 기본 입력 형태(보통 딕셔너리)를 반환해야 합니다.
        예시: {"topic": "흥미로운 음식 이름 5가지 생성"}
        생성이 불가능하면 None을 반환할 수 있습니다.
        """
        pass

    @abstractmethod
    def _format_few_shot_prompt(self, base_topic_input: Dict[str, Any], examples: List[Idea]) -> Input:
        """
        [구현 필요] 기본 주제 입력과 선택된 예시(Idea 객체 리스트)를 받아
        최종 LLM 입력(프롬프트 포함)을 구성합니다.
        Runnable이 최종적으로 받을 Input 형태를 반환해야 합니다.
        """
        pass

    def _fetch_examples(self, state: GraphState) -> List[Idea]:
        """ DB에서 설정에 따라 Few-Shot 예시를 가져옵니다 (item_type 필터 적용). """
        if self.num_shots == 0: return []

        print(f"  Few-shot 예시 조회 시도 (type: {self.shot_item_type}, step: {self.shot_generation_step}, usage < {self.shot_max_usage_count})")
        # get_idea_ids 호출 시 item_type 파라미터 전달
        candidate_ids = self.db_handler.get_idea_ids(
            generation_step=self.shot_generation_step,
            max_usage_count=self.shot_max_usage_count,
            item_type=self.shot_item_type # <<< 추가
        )

        if not candidate_ids:
            print("  [정보] Few-shot 예시 후보 ID를 DB에서 찾을 수 없습니다.")
            return []

        num_to_fetch = min(self.num_shots, len(candidate_ids))
        if self.select_shots_randomly:
            selected_ids = random.sample(candidate_ids, num_to_fetch)
            print(f"  [정보] Few-shot 예시 ID {num_to_fetch}개 랜덤 선택: {selected_ids[:5]}...") # 너무 길면 일부만 출력
        else:
            selected_ids = candidate_ids[:num_to_fetch]
            print(f"  [정보] Few-shot 예시 ID {num_to_fetch}개 순차 선택: {selected_ids[:5]}...")

        examples = self.db_handler.get_ideas(selected_ids)
        print(f"  [정보] DB에서 Few-shot 예시 {len(examples)}개 로드 완료.")
        return examples

    # BaseLLMDivergenceNode의 _prepare_input을 오버라이드
    def _prepare_input(self, state: GraphState) -> Union[None, Input, List[Input]]:
        """
        Few-shot 예시를 가져와 최종 LLM 입력을 준비합니다.
        (주의: 현재 이 기본 구현은 단일 Input 생성만 지원합니다. 배치 처리가 필요하면 수정 필요)
        """
        # 1. 하위 클래스에서 기본 주제/지시사항 가져오기
        base_topic_input = self._get_base_topic(state)
        print(state)

        if base_topic_input is None:
            print("  [정보] 기본 주제 생성이 불가능하여 입력 준비 중단.")
            return None

        # 2. Few-shot 예시 가져오기
        examples = self._fetch_examples(state)

        # 3. 하위 클래스에서 최종 프롬프트 포맷팅
        # (예시가 없으면 base_topic_input 그대로 사용하거나, _format_few_shot_prompt가 처리)
        final_input = self._format_few_shot_prompt(base_topic_input, examples)

        return final_input
    
# dcagent/nodes/divergence.py (또는 새로운 파일) 에 추가

class BasePerspectiveGeneratingNode(BaseLLMDivergenceNode):
    """
    [Applied Base] 특정 주제에 대한 다양한 '관점'이나 '테마'를 생성하는
    발산 노드의 기본 구조. 생성된 관점은 다음 단계 노드의 입력으로 사용될 수 있습니다.
    """
    def __init__(self, db_handler: IdeaDBHandler, runnable: Runnable):
        super().__init__(db_handler, runnable)

    @abstractmethod
    def _format_perspective_prompt(self, state: GraphState) -> Optional[Input]:
        """
        [구현 필요] 주어진 상태(state)를 기반으로 '관점 생성'을 요청하는
        LLM 입력을 구성합니다. 생성이 불가능하면 None을 반환합니다.
        예: {"topic": "음식 아이디어 생성을 위한 다양한 관점 5가지 (지역, 맛, 재료 등) 제안"}
        """
        pass

    # BaseLLMDivergenceNode의 _prepare_input을 오버라이드
    def _prepare_input(self, state: GraphState) -> Union[None, Input, List[Input]]:
        # 하위 클래스에서 정의한 프롬프트 포맷팅 메소드 호출
        return self._format_perspective_prompt(state)

    # _parse_output은 BaseLLMDivergenceNode의 것을 그대로 사용하거나 필요시 오버라이드
    # (파싱 결과가 관점 문자열 리스트가 되도록 구현 필요)
    # 예: def _parse_output(...) -> List[Dict[str, Any]]: # [{"content": "지역별"}, {"content": "매운맛"}]


# dcagent/nodes/divergence.py (또는 새로운 파일) 에 추가

class BasePerspectiveBasedNode(BaseLLMDivergenceNode):
    """
    [Applied Base] 이전에 선택된 '관점' 아이디어를 기반으로
    구체적인 아이디어를 생성하는 발산 노드의 기본 구조.
    상태(state)에 선택된 관점 ID(들)가 포함되어 있다고 가정합니다.
    """
    def __init__(self, db_handler: IdeaDBHandler, runnable: Runnable):
        super().__init__(db_handler, runnable)

    @abstractmethod
    def _get_selected_perspective_ids(self, state: GraphState) -> List[str]:
        """
        [구현 필요] 상태(state)에서 현재 기반으로 삼을 '관점' 아이디어의 ID 리스트를 추출합니다.
        예: return state.get('selected_perspective_ids', [])
        """
        pass

    @abstractmethod
    def _format_perspective_based_prompt(self, perspective: Idea, state: GraphState) -> Optional[Input]:
        """
        [구현 필요] 선택된 '관점' 아이디어(perspective)와 현재 상태(state)를 기반으로
        최종 아이디어 생성을 요청하는 LLM 입력을 구성합니다.
        생성이 불가능하면 None을 반환합니다.
        예: {"topic": f"'{perspective.content}' 관점에서 흥미로운 음식 아이디어 5가지 생성"}
        """
        pass

    # BaseLLMDivergenceNode의 _prepare_input을 오버라이드

    def _prepare_input(self, state: GraphState) -> Union[None, Input, List[Input]]:
        """ 선택된 관점들을 기반으로 LLM 입력(들)을 준비합니다. (배치 처리 지원) """
        # --- 디버깅 코드 추가 ---
        print(f"  DEBUG: Incoming state for {self.__class__.__name__}: {state}")
        # ---------------------
        """ 선택된 관점들을 기반으로 LLM 입력(들)을 준비합니다. (배치 처리 지원) """
        perspective_ids = self._get_selected_perspective_ids(state)
        if not perspective_ids:
            print("  [오류] 기반으로 삼을 관점 ID가 상태에 없습니다.")
            return None

        inputs_list = []
        perspectives = self.db_handler.get_ideas(perspective_ids) # ID로 실제 관점 Idea 로드
        print(f"  선택된 관점 {len(perspectives)}개 로드 완료.")

        for p_idea in perspectives:
            # 하위 클래스에서 정의한 프롬프트 포맷팅 메소드 호출
            single_input = self._format_perspective_based_prompt(p_idea, state)
            if single_input:
                # 배치 처리 시 원래 관점 ID를 context로 전달 (부모 ID 설정용)
                if isinstance(single_input, dict):
                     single_input['_parent_context'] = p_idea.id
                inputs_list.append(single_input)
            else:
                 print(f"  [경고] 관점 '{p_idea.content}' (ID: {p_idea.id})에 대한 입력 생성 실패.")

        # 입력 리스트가 비어있으면 None 반환, 아니면 리스트 반환 (자동 배치 처리)
        return inputs_list if inputs_list else None

    # _parse_output은 BaseLLMDivergenceNode의 것을 그대로 사용하거나 필요시 오버라이드