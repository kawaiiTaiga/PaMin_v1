# functions/topic_generation.py

import os
import json
import random
import traceback
import sqlite3 # dcagent.SQLiteHandler 내부에서 사용될 수 있음
from typing import Dict, Any, List, Optional, Tuple, Set, Literal, TypedDict

# LangChain 및 LangGraph 관련 임포트
from langchain_core.runnables import Runnable
from langchain_core.runnables.utils import Input, Output
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END

# --- dcagent 라이브러리 임포트 ---
try:
    from dcagent import (
        Idea, IdeaDBHandler, SQLiteHandler, BaseLLMDivergenceNode, BaseConvergenceNode,
        BaseFewShotLLMDivergenceNode, BasePerspectiveGeneratingNode,
        BasePerspectiveBasedNode, BaseLLMConvergenceNode, RandomConvergenceNode,
        SampleConvergenceNode
    )
    dcagent_available = True
except ImportError as e:
    print(f"[오류] dcagent 라이브러리 임포트 실패: {e}. 경로 및 설치를 확인하세요.")
    dcagent_available = False
except Exception as e:
    print(f"[오류] dcagent 임포트 중 오류: {e}")
    dcagent_available = False

# --- 로컬 상태 정의 ---
class FoodTmiGraphState(TypedDict):
    current_idea_ids: List[str]
    selected_idea_id: Optional[str]
    selected_idea_ids: List[str]
    step_counter: int
    error_message: Optional[str]
    final_output_path: Optional[str] # JSON 파일 경로 저장
    _route: Optional[Literal["PERSPECTIVE", "FEW_SHOT", "ERROR"]]
    unused_food_ids: List[str]
    _route_check_unused: Optional[Literal["SELECT_UNUSED", "PROCEED_TO_GENERATION", "ERROR"]]

# === 애플리케이션 특정 노드 클래스 정의 ===
# (FoodPerspectiveGenerator, PerspectiveBasedFoodGenerator, FewShotFoodGenerator,
#  TmiDivergenceNode, SelectShortsTMILLM 클래스 정의는 이전 코드와 동일하게 여기에 포함)
# --- Perspective Generation Node ---
class FoodPerspectiveGenerator(BasePerspectiveGeneratingNode):
    def _format_perspective_prompt(self, state: FoodTmiGraphState) -> Optional[Input]:
        count = 5; topic = ( f"음식/식재료 발상을 위한 '특징' {count}가지를 제안해주세요. 예: [\"빨간 채소\",\"탄산 음료\",\"러시아 음식\"]. JSON 문자열 리스트로 출력해주세요." )
        print("  음식 관점 생성 요청"); return {"topic": topic}
    def _parse_output(self, runnable_output: Output) -> List[Dict[str, Any]]:
        perspectives = []
        if isinstance(runnable_output, list): perspectives = [str(item).strip() for item in runnable_output if isinstance(item, str) and str(item).strip()]
        elif isinstance(runnable_output, str):
            try: parsed_list = json.loads(runnable_output); perspectives = [str(item).strip() for item in parsed_list if isinstance(item, str) and str(item).strip()]
            except json.JSONDecodeError: print("  [오류] 문자열 JSON 파싱 실패.")
        else: print(f"  [경고] 예상 못한 타입: {type(runnable_output)}")
        return [{"content": p, "item_type": "perspective"} for p in perspectives]

# --- Perspective-Based Food Generation Node ---
class PerspectiveBasedFoodGenerator(BasePerspectiveBasedNode):
    def _get_selected_perspective_ids(self, state: FoodTmiGraphState) -> List[str]:
        selected_id = state.get('selected_idea_id'); return [selected_id] if selected_id else []
    def _format_perspective_based_prompt(self, perspective: Idea, state: FoodTmiGraphState) -> Optional[Input]:
        count = 5; topic = ( f"'{perspective.content}'에 해당하는 서로 다른 구체적인 음식 혹은 식재료 이름 {count}가지 제시(한국인이 완전 처음 들어봤을 법한 것은 제외).JSON 문자열 리스트 출력." )
        return {"topic": topic}
    def _parse_output(self, runnable_output: Output) -> List[Dict[str, Any]]:
        ideas_content = []
        if isinstance(runnable_output, list):
            for item in runnable_output:
                food_name = None
                if isinstance(item, dict): food_name = item.get('food') or item.get('음식') or item.get('음식/식재료') or item.get('name')
                elif isinstance(item, str): food_name = item
                if food_name and isinstance(food_name, str) and food_name.strip(): ideas_content.append(food_name.strip())
        elif isinstance(runnable_output, str):
             try:
                parsed_list = json.loads(runnable_output)
                if isinstance(parsed_list, list):
                     for item in parsed_list:
                        food_name = None
                        if isinstance(item, dict): food_name = item.get('food') or item.get('음식') or item.get('음식/식재료') or item.get('name')
                        elif isinstance(item, str): food_name = item
                        if food_name and isinstance(food_name, str) and food_name.strip(): ideas_content.append(food_name.strip())
             except json.JSONDecodeError: print("  [오류] 문자열 JSON 파싱 실패.")
        else: print(f"  [경고] 예상 못한 타입: {type(runnable_output)}")
        return [{"content": content, "item_type": "food_ingredient"} for content in ideas_content]

# --- Few-Shot Food Generation Node ---
class FewShotFoodGenerator(BaseFewShotLLMDivergenceNode):
    def __init__(self, db_handler: IdeaDBHandler, runnable: Runnable):
         super().__init__(db_handler, runnable, num_shots=5, shot_generation_step=1, select_shots_randomly=True, shot_item_type="food_ingredient")
    def _get_base_topic(self, state: FoodTmiGraphState) -> Optional[Dict[str, Any]]:
        count = 5; return {"topic": f"기존 예시와 다른 음식/식재료 이름 {count}가지 제시해주세요.(한국인이 완전 처음 들어봤을 법한 것은 제외)"}
    def _format_few_shot_prompt(self, base_topic_input: Dict[str, Any], examples: List[Idea]) -> Input:
        prompt = base_topic_input['topic']
        if examples:
            prompt += "\n\n기존 음식/식재료 예시:\n"; example_contents = [ex.content for ex in examples if ex.content]
            if example_contents: prompt += "\n".join([f"- {content}" for content in example_contents])
        prompt += "\n\n출력은 반드시 JSON 형식의 문자열 리스트로만 응답해야 합니다."
        return {"topic": prompt}
    def _parse_output(self, runnable_output: Output) -> List[Dict[str, Any]]:
        ideas_content = []
        if isinstance(runnable_output, list): ideas_content = [str(item).strip() for item in runnable_output if isinstance(item, (str, int, float)) and str(item).strip()]
        elif isinstance(runnable_output, str):
             try: parsed_list = json.loads(runnable_output); ideas_content = [str(item).strip() for item in parsed_list if isinstance(item, (str, int, float)) and str(item).strip()]
             except json.JSONDecodeError: print("  [오류] 문자열 JSON 파싱 실패.")
        else: print(f"  [경고] 예상 못한 타입: {type(runnable_output)}")
        return [{"content": content, "item_type": "food_ingredient"} for content in ideas_content]

# --- TMI Generation Node ---
class TmiDivergenceNode(BaseLLMDivergenceNode):
    def _prepare_input(self, state: FoodTmiGraphState) -> Optional[List[Input]]:
        selected_food_ids = state.get('selected_idea_ids');
        if not selected_food_ids: return None
        inputs_list = []; food_ideas = self.db_handler.get_ideas(selected_food_ids)
        if not food_ideas: return None
        food_idea = food_ideas[0]; count = 4; food_name = food_idea.content
        topic = ( f"'{food_name}에 관한 흥미롭거나 충격적인 역사적/문화적/과학적 사실 혹은 사람들이 오해하고 있는 사실 {count}가지를 생성해주세요. 가장 좋은 것은 들었을때... 진짜??? 소리가 나와야 하는 것입니다. 혹은 클릭하지 않고는 못배길 주제도 좋습니다."
                 f"당연한 소리를 하지는 마십시오. 예를 들어 딱 들어도 몸에 좋아 보일 것 같은 음식이 어떠한 성분 때문에 몸에 좋더라 이런 것들은 하지 마세요. 전혀 흥미롭지 않습니다.  "
                 f"약간의 과장은 가능합니다. 사실적 기반이 약간이라도 있으면 됩니다."
                  f"출력은 반드시 JSON 형식의 문자열 리스트로만 응답해야 합니다. 다른 어떤 설명도 붙이지 마세요." )
        return [{"topic": topic, "_parent_context": food_idea.id}]
    def _parse_output(self, runnable_output: Output) -> List[Dict[str, Any]]:
        tmi_content = []
        if isinstance(runnable_output, list):
            for item in runnable_output:
                fact = None
                if isinstance(item, dict): fact = item.get('fact') or item.get('tmi')
                elif isinstance(item, str): fact = item
                if fact and isinstance(fact, str) and fact.strip(): tmi_content.append(fact.strip())
        elif isinstance(runnable_output, str):
             try:
                parsed_list = json.loads(runnable_output)
                if isinstance(parsed_list, list):
                     for item in parsed_list:
                        fact = None
                        if isinstance(item, dict): fact = item.get('fact') or item.get('tmi')
                        elif isinstance(item, str): fact = item
                        if fact and isinstance(fact, str) and fact.strip(): tmi_content.append(fact.strip())
             except json.JSONDecodeError: print("  [오류] 문자열 JSON 파싱 실패.")
        else: print(f"  [경고] 예상 못한 타입: {type(runnable_output)}")
        return [{"content": content, "item_type": "tmi"} for content in tmi_content]

# --- LLM Based TMI Selection Node ---
class SelectShortsTMILLM(BaseLLMConvergenceNode):
    def _prepare_llm_input(self, candidate_ideas: List[Idea], state: FoodTmiGraphState) -> Optional[Input]:
        if not candidate_ideas: return None
        self.candidate_map = {idea.id: idea for idea in candidate_ideas}
        tmi_list_str = ""
        for i, idea in enumerate(candidate_ideas): tmi_list_str += f"후보 {i+1} (ID: {idea.id}): \"{idea.content}\"\n"
        prompt = ( "다음 음식 TMI 목록 중 유튜브 숏츠 영상으로 만들 때 가장 흥미로울 것 같은 TMI 2개를 골라 ID를 알려주세요.\n\n"
                   f"{tmi_list_str}\n"
                   "선택 기준: 반전성, 흥미 유발 여부, 팩트 여부\n"
                   "응답 형식 (JSON 객체): {\"selected_ids\": [\"선택한 ID 1\", \"선택한 ID 2\"]}" )
        return {"topic": prompt}
    def _parse_llm_output(self, llm_output: Output, candidate_ideas: List[Idea]) -> List[str]:
        selected_ids = []; candidate_id_set = {idea.id for idea in candidate_ideas}
        try:
            output_data = llm_output
            if isinstance(output_data, str):
                try: output_data = json.loads(output_data)
                except json.JSONDecodeError: output_data = {}
            if isinstance(output_data, dict):
                selected_ids_raw = output_data.get("selected_ids")
                if isinstance(selected_ids_raw, list) and len(selected_ids_raw) > 0:
                    valid_ids = [sid for sid in selected_ids_raw if isinstance(sid, str) and sid in candidate_id_set]
                    selected_ids = valid_ids[:2]
            else: print(f"  [경고] LLM 출력이 예상 dict 타입 아님: {type(output_data)}")
        except Exception as e: print(f"  [오류] LLM 출력 파싱 중 예외: {e}")
        return selected_ids


# --- 최종 결과를 JSON 파일에 저장하는 함수 노드 ---
def save_tmi_pair_to_json(state: FoodTmiGraphState, db_handler: IdeaDBHandler, filename: str) -> Dict[str, Optional[str]]:
    selected_tmi_ids = state.get('selected_idea_ids', [])
    output_path = None
    if len(selected_tmi_ids) == 2:
        try:
            tmi_ideas = db_handler.get_ideas(selected_tmi_ids)
            if len(tmi_ideas) == 2:
                tmi1, tmi2 = tmi_ideas[0], tmi_ideas[1]
                parent_food_id = tmi1.parent_id
                topic_name = "Unknown Food"
                if parent_food_id:
                    parent_food = db_handler.get_idea(parent_food_id)
                    if parent_food: topic_name = parent_food.content

                new_entry = { "TOPIC": topic_name, "DETAIL": sorted([tmi1.content, tmi2.content]), "USED": False }
                data = []
                if os.path.exists(filename):
                    try:
                        with open(filename, 'r', encoding='utf-8') as f: data = json.load(f)
                        if not isinstance(data, list): data = []
                    except (json.JSONDecodeError, IOError): data = []
                data.append(new_entry)
                try:
                    with open(filename, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)
                    output_path = filename
                except IOError as e: print(f"  [오류] '{filename}' 파일 쓰기 오류: {e}")
            else: print(f"  [오류] 선택된 TMI ID({selected_tmi_ids})로 DB 조회 실패.")
        except Exception as e: print(f"  [오류] 최종 결과 저장 중 오류 발생: {e}")
    return {"final_output_path": output_path}


# === 라우팅 함수 정의 ===
def check_unused_food_ideas(state: FoodTmiGraphState, db_handler: IdeaDBHandler) -> Dict[str, Any]:
    unused_ids = []; route_decision = "PROCEED_TO_GENERATION"
    try:
        unused_ids = db_handler.get_idea_ids(generation_step=1, max_usage_count=1, item_type='food_ingredient')
        if len(unused_ids) > 0: route_decision = "SELECT_UNUSED"
    except Exception as e: print(f"  [오류] 사용되지 않은 아이디어 확인 중 오류: {e}"); route_decision = "ERROR"
    return {"_route_check_unused": route_decision, "unused_food_ids": unused_ids}

def route_check_unused(state: FoodTmiGraphState) -> Literal["SELECT_UNUSED", "PROCEED_TO_GENERATION", "ERROR"]:
    return state.get("_route_check_unused", "ERROR")

def route_food_generation_strategy(state: FoodTmiGraphState, db_handler: IdeaDBHandler) -> Literal["PERSPECTIVE", "FEW_SHOT", "ERROR"]:
    try:
        step1_food_count = db_handler.count_ideas(generation_step=1, item_type='food_ingredient')
        if step1_food_count < 5: return "PERSPECTIVE"
        else: return random.choice(["PERSPECTIVE", "FEW_SHOT"])
    except Exception as e: print(f"[오류] 음식 생성 전략 결정 중 오류: {e}"); return "ERROR"

def route_by_strategy(state: FoodTmiGraphState) -> Literal["PERSPECTIVE", "FEW_SHOT", "ERROR"]:
    return state.get("_route", "ERROR")

def select_one_unused_food(state: FoodTmiGraphState, db_handler: IdeaDBHandler) -> Dict[str, Any]:
    unused_ids = state.get("unused_food_ids", [])
    if not unused_ids: return {"selected_idea_ids": [], "error_message": "No unused food ideas found"}
    selected_id = random.choice(unused_ids)
    db_handler.increment_usage_count(selected_id)
    return {"selected_idea_id": None, "selected_idea_ids": [selected_id], "current_idea_ids": [], "unused_food_ids": []}


# --- 그래프 빌드 함수 ---
def build_food_tmi_graph(db_handler: SQLiteHandler,
                         idea_runnable: Runnable,
                         tmi_runnable: Runnable,
                         selector_runnable: Runnable,
                         output_json_file: str) -> StateGraph:
    """ 음식 TMI 생성 그래프 V4 JSON Output 버전 빌드 """
    if not dcagent_available: raise ImportError("dcagent 라이브러리를 사용할 수 없습니다.")

    # 노드 인스턴스
    food_perspective_generator = FoodPerspectiveGenerator(db_handler=db_handler, runnable=idea_runnable)
    perspective_selector = RandomConvergenceNode(db_handler=db_handler)
    perspective_food_generator = PerspectiveBasedFoodGenerator(db_handler=db_handler, runnable=idea_runnable)
    few_shot_food_generator = FewShotFoodGenerator(db_handler=db_handler, runnable=idea_runnable)
    food_selector = SampleConvergenceNode(db_handler=db_handler, k=1)
    tmi_diverger = TmiDivergenceNode(db_handler=db_handler, runnable=tmi_runnable)
    tmi_selector = SelectShortsTMILLM(db_handler=db_handler, runnable=selector_runnable)

    # Helper Function Nodes
    check_unused_food_node = lambda state: check_unused_food_ideas(state, db_handler)
    select_unused_food_node = lambda state: select_one_unused_food(state, db_handler)
    decide_food_strategy_node = lambda state: {"_route": route_food_generation_strategy(state, db_handler)}
    save_to_json_node = lambda state: save_tmi_pair_to_json(state, db_handler, output_json_file)

    # 그래프 정의
    workflow = StateGraph(FoodTmiGraphState)
    workflow.add_node("check_unused_food", check_unused_food_node)
    workflow.add_node("select_unused_food", select_unused_food_node)
    workflow.add_node("decide_food_strategy", decide_food_strategy_node)
    workflow.add_node("generate_perspectives", food_perspective_generator)
    workflow.add_node("select_perspective", perspective_selector)
    workflow.add_node("generate_food_from_perspective", perspective_food_generator)
    workflow.add_node("generate_food_few_shot", few_shot_food_generator)
    workflow.add_node("select_food", food_selector)
    workflow.add_node("generate_tmi", tmi_diverger)
    workflow.add_node("select_tmi", tmi_selector)
    workflow.add_node("save_result_to_json", save_to_json_node)

    # 엣지 연결
    workflow.set_entry_point("check_unused_food")
    workflow.add_conditional_edges("check_unused_food", route_check_unused, {
        "SELECT_UNUSED": "select_unused_food", "PROCEED_TO_GENERATION": "decide_food_strategy", "ERROR": END
    })
    workflow.add_edge("select_unused_food", "generate_tmi")
    workflow.add_conditional_edges("decide_food_strategy", route_by_strategy, {
        "PERSPECTIVE": "generate_perspectives", "FEW_SHOT": "generate_food_few_shot", "ERROR": END
    })
    workflow.add_edge("generate_perspectives", "select_perspective")
    workflow.add_edge("select_perspective", "generate_food_from_perspective")
    workflow.add_edge("generate_food_from_perspective", "select_food")
    workflow.add_edge("generate_food_few_shot", "select_food")
    workflow.add_edge("select_food", "generate_tmi")
    workflow.add_edge("generate_tmi", "select_tmi")
    workflow.add_edge("select_tmi", "save_result_to_json")
    workflow.add_edge("save_result_to_json", END)

    return workflow.compile()


# --- 메인 토픽 생성 함수 ---
def generate_new_topics(
    api_key: str,
    num_topics_to_generate: int,
    db_file_path: str,
    output_json_path: str,
    recursion_limit: int = 20
    ) -> Tuple[bool, str]:
    """
    지정된 수만큼 새로운 음식 TMI 토픽을 생성하고 JSON 파일에 추가합니다.

    Args:
        api_key: Google Generative AI API 키.
        num_topics_to_generate: 생성할 토픽의 개수.
        db_file_path: LangGraph 실행 중 사용할 SQLite DB 파일 경로.
        output_json_path: 생성된 토픽을 추가할 JSON 파일 경로.
        recursion_limit: LangGraph 실행 시 최대 재귀 깊이.

    Returns:
        Tuple[bool, str]: (성공 여부, 메시지)
    """
    if not dcagent_available:
        return False, "dcagent 라이브러리가 설치되지 않았거나 임포트할 수 없습니다."

    # --- LLM 및 Runnable 초기화 ---
    llm, idea_chain, llm2, tmi_chain, selector_chain = None, None, None, None, None
    try:
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=1.2, api_key=api_key)
        general_prompt = ChatPromptTemplate.from_template("{topic}")
        json_parser = JsonOutputParser()
        idea_chain = general_prompt | llm | json_parser
        llm2_model = "gemini-2.0-flash" # 모델명 확인 필요
        llm2 = ChatGoogleGenerativeAI(model=llm2_model, temperature=1.1, api_key=api_key)
        tmi_chain = general_prompt | llm2 | json_parser
        selector_chain = general_prompt | llm | json_parser
    except Exception as e:
        return False, f"LLM 또는 Runnable 초기화 실패: {e}"

    if not all([llm, llm2, idea_chain, tmi_chain, selector_chain]):
        return False, "필요한 LLM 또는 Runnable을 초기화하지 못했습니다."

    # --- DB 핸들러 및 그래프 빌드 ---
    try:
        # DB 파일 디렉토리 생성
        db_dir = os.path.dirname(db_file_path)
        if db_dir: # 디렉토리 경로가 있다면 생성 시도
            os.makedirs(db_dir, exist_ok=True)
        db_handler = SQLiteHandler(db_file=db_file_path)
        app = build_food_tmi_graph(db_handler, idea_chain, tmi_chain, selector_chain, output_json_path)
    except Exception as e:
        return False, f"DB 핸들러 또는 그래프 빌드 실패: {e}"

    # --- 그래프 실행 ---
    initial_state: FoodTmiGraphState = {
        "current_idea_ids": [], "selected_idea_id": None, "selected_idea_ids": [],
        "step_counter": 0, "error_message": None, "final_output_path": None,
        "_route": None, "unused_food_ids": [], "_route_check_unused": None,
    }

    successful_generations = 0
    error_messages = []

    print(f"\n======= 자동 토픽 생성 시작 (목표: {num_topics_to_generate}개) =======")
    for i in range(num_topics_to_generate):
        print(f"\n--- 토픽 생성 시도 {i+1}/{num_topics_to_generate} ---")
        current_run_state = initial_state.copy()
        try:
            final_state = app.invoke(current_run_state, config={"recursion_limit": recursion_limit})
            output_file = final_state.get('final_output_path')
            if output_file:
                successful_generations += 1
                print(f"  -> 생성 성공 ({successful_generations}/{num_topics_to_generate})")
            else:
                error_msg = final_state.get('error_message', '알 수 없는 이유로 결과 저장 안됨')
                print(f"  -> 생성 실패: {error_msg}")
                error_messages.append(error_msg)
                # 너무 많은 오류 발생 시 중단 로직 추가 가능

        except Exception as e:
            error_msg = f"그래프 실행 중 예외 발생: {e}"
            print(f"  -> 생성 실패: {error_msg}")
            print(traceback.format_exc())
            error_messages.append(error_msg)
            # 너무 많은 오류 발생 시 중단 로직 추가 가능

    print(f"\n======= 자동 토픽 생성 종료 (성공: {successful_generations}/{num_topics_to_generate}) =======")

    if successful_generations > 0:
        # 최종 생성된 파일 내용 확인 (옵션)
        if os.path.exists(output_json_path):
             print(f"\n--- 최종 생성된 '{os.path.basename(output_json_path)}' 내용 (마지막 3개) ---")
             try:
                 with open(output_json_path, 'r', encoding='utf-8') as f:
                     final_data = json.load(f)
                     print(json.dumps(final_data[-min(3, len(final_data)):], ensure_ascii=False, indent=2))
             except Exception as e: print(f"  [오류] 최종 JSON 파일 읽기 실패: {e}")

        success_message = f"총 {num_topics_to_generate}개 중 {successful_generations}개의 새 토픽을 생성하여 '{output_json_path}'에 추가했습니다."
        if error_messages:
             success_message += f"\n일부 생성 실패: {len(error_messages)}건"
        return True, success_message
    else:
        failure_message = f"새 토픽 생성에 모두 실패했습니다."
        if error_messages:
             failure_message += f"\n주요 오류 메시지: {error_messages[:2]}" # 처음 2개 오류만 표시
        return False, failure_message

# --- 직접 실행 테스트 (선택 사항) ---
# if __name__ == "__main__":
#     print("functions/topic_generation.py 직접 실행 테스트")
#     test_api_key = "YOUR_GOOGLE_API_KEY" # 실제 키로 대체 필요
#     test_num_topics = 2
#     test_db_path = "./temp_topic_gen.db"
#     test_output_path = "./generated_topics_test.json"
#
#     # 기존 테스트 파일 삭제
#     if os.path.exists(test_db_path): os.remove(test_db_path)
#     if os.path.exists(test_output_path): os.remove(test_output_path)
#
#     success, message = generate_new_topics(
#         api_key=test_api_key,
#         num_topics_to_generate=test_num_topics,
#         db_file_path=test_db_path,
#         output_json_path=test_output_path
#     )
#
#     print("\n--- 테스트 결과 ---")
#     print(f"성공 여부: {success}")
#     print(f"메시지: {message}")
#
#     # 생성된 파일 확인 (선택적)
#     if os.path.exists(test_output_path):
#         print(f"\n'{test_output_path}' 파일 내용:")
#         try:
#             with open(test_output_path, 'r', encoding='utf-8') as f:
#                 print(f.read())
#         except Exception as e:
#             print(f"파일 읽기 오류: {e}")