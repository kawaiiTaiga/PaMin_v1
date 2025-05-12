# views/workflow_view.py
import streamlit as st
import json
import os
import importlib # 모듈을 동적으로 임포트하기 위해 사용
import datetime # 에피소드 ID 생성을 위해 사용
import time # 필요시 로딩 시간 표시 등에 사용
from typing import Optional, Dict, Any # 타입 힌트용

# --- 워크플로우 디렉토리 및 파일 규약 상수 ---
WORKFLOWS_ROOT_DIR = "./workflows" # 모든 워크플로우 정의가 모여있는 루트 디렉토리
WORKFLOW_DEFINITION_FILE = "workflow.json" # 각 워크플로우 디렉토리 내의 정의 파일 이름
STEP_RENDER_FUNCTION_NAME = "render_step" # 각 스텝 파일 내의 렌더링 함수 이름 규약

# --- 사용 가능한 워크플로우 로딩 함수 ---
# 이 함수는 app.py에서 호출되어 사용 가능한 워크플로우 목록을 찾고 정의를 로드합니다.
def load_available_workflows():
    """
    './workflows/' 디렉토리를 탐색하여 사용 가능한 워크플로우를 찾고
    각 워크플로우의 workflow.json 정의를 로드합니다.

    Returns:
        워크플로우 이름(str)을 키로, 로드된 정의(dict)를 값으로 하는 딕셔너리
        오류 발생 시 빈 딕셔너리 반환.
    """
    available_workflows = {}
    if not os.path.exists(WORKFLOWS_ROOT_DIR):
        print(f"경고: 워크플로우 루트 디렉토리 '{WORKFLOWS_ROOT_DIR}'를 찾을 수 없습니다.")
        return available_workflows

    # workflows 루트 디렉토리 하위의 모든 항목 탐색
    for item_name in os.listdir(WORKFLOWS_ROOT_DIR):
        item_path = os.path.join(WORKFLOWS_ROOT_DIR, item_name)
        # 항목이 디렉토리인지 확인
        if os.path.isdir(item_path):
            workflow_name = item_name # 디렉토리 이름이 워크플로우 이름
            definition_file_path = os.path.join(item_path, WORKFLOW_DEFINITION_FILE)

            # 워크플로우 정의 파일(workflow.json)이 존재하는지 확인
            if os.path.exists(definition_file_path):
                try:
                    with open(definition_file_path, 'r', encoding='utf-8') as f:
                        workflow_definition = json.load(f)

                    # 로드된 정의가 유효한지 확인 (name 키 값과 디렉토리 이름 일치, steps 키 존재 및 리스트 타입)
                    if (isinstance(workflow_definition, dict) and
                        workflow_definition.get("name") == workflow_name and
                        isinstance(workflow_definition.get("steps"), list)):
                        available_workflows[workflow_name] = workflow_definition
                        print(f"DEBUG: 워크플로우 로드 성공: {workflow_name}") # 디버깅 로그
                    else:
                        print(f"경고: '{workflow_name}' 워크플로우 정의 파일 '{WORKFLOW_DEFINITION_FILE}' 형식이 올바르지 않습니다 (name 불일치 또는 steps 누락/형식 오류).")
                except json.JSONDecodeError:
                    print(f"경고: '{workflow_name}' 워크플로우 정의 파일 '{WORKFLOW_DEFINITION_FILE}'이 유효한 JSON 형식이 아닙니다.")
                except Exception as e:
                    print(f"경고: '{workflow_name}' 워크플로우 정의 로드 중 오류 발생: {e}")
            # else: # workflow.json 파일이 없는 디렉토리는 워크플로우로 인식 안함 (경고 불필요)
    return available_workflows


# --- 에피소드 ID 및 경로 생성 함수 (topic_id 기반으로 수정됨) ---
def generate_episode_info(session_state, channels_root_dir: str, workflow_name: str, topic_dict: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    """
    선택된 토픽의 ID를 기반으로 에피소드 ID와 저장 경로를 생성/확인합니다.
    해당 경로가 이미 존재하면 기존 경로를 사용합니다. 실패 시 None 반환.
    """
    # 필수 정보 체크 (채널 이름, 루트 경로, 워크플로우 이름, 토픽 딕셔너리)
    if not session_state.selected_channel_name or not channels_root_dir or not workflow_name or not topic_dict:
        error_msg = "오류: 에피소드 정보 생성을 위한 필수 정보(채널, 루트, 워크플로우, 토픽 객체) 부족."
        print(error_msg)
        st.error(error_msg) # UI에도 에러 표시
        return None

    topic_id = topic_dict.get('topic_id')
    if not topic_id:
         error_msg = "오류: 선택된 토픽에 'topic_id'가 없습니다. 토픽 데이터 또는 선택 과정을 확인하세요."
         print(error_msg)
         st.error(error_msg) # UI에도 에러 표시
         return None

    # 에피소드 ID는 토픽 ID 자체 사용 (문자열 변환)
    episode_id = str(topic_id)
    # 에피소드 저장 경로 생성 (./channels/[채널 이름]/episodes/[토픽 ID]/)
    episode_path = os.path.join(channels_root_dir, session_state.selected_channel_name, "episodes", episode_id)

    # 디렉토리 생성 시도 (이미 존재해도 OK)
    try:
        os.makedirs(episode_path, exist_ok=True)
        print(f"DEBUG: 에피소드 디렉토리 확인/생성 완료: {episode_path}")
        return {"episode_id": episode_id, "episode_path": episode_path}
    except Exception as e:
        error_msg = f"오류: 에피소드 디렉토리 '{episode_path}' 생성 중 오류 발생: {e}"
        print(error_msg)
        st.error(error_msg) # UI에도 에러 표시
        return None


# --- 워크플로우 단계별 UI 및 로직을 호출하는 메인 함수 ---
def show_page(session_state, all_workflow_definitions, channels_root_dir):
    """
    현재 워크플로우 뷰를 렌더링합니다. (에피소드 정보 생성 시점 변경됨)
    """
    # --- 초기 상태 및 정의 유효성 검사 ---
    if not session_state.selected_channel_name or session_state.selected_channel_name == "-- 채널 선택 --":
         st.error("❌ 오류: 작업할 채널이 선택되지 않았습니다. 채널 설정을 확인해 주세요.")
         session_state.current_view = 'welcome' # 안전 장치: 메인으로 돌려보냅니다.
         st.rerun() # 상태 변경 후 즉시 새로고침
         return

    current_workflow_name = session_state.get('current_workflow_name')
    if current_workflow_name is None:
         st.error(f"❌ 오류: 채널 정의에 명시된 워크플로우 이름이 유효하지 않습니다 (None).")
         st.warning(f"채널 '{session_state.selected_channel_name}'의 `channel_definition.json` 파일을 확인하여 'workflow' 키에 유효한 워크플로우 이름이 설정되었는지 확인하세요.")
         st.info("채널 설정 페이지에서 채널을 다시 로드하거나 워크플로우를 선택/설정해 주세요.")
         session_state.current_view = 'welcome' ; st.rerun(); return

    workflow_definition = all_workflow_definitions.get(current_workflow_name)
    if not workflow_definition:
         st.error(f"❌ 오류: 로드된 워크플로우 정의 목록에 '{current_workflow_name}' 워크플로우가 없습니다.")
         st.warning(f"`workflows/{current_workflow_name}/workflow.json` 파일이 존재하고 형식이 올바른지 확인하세요.")
         st.info("채널 설정을 확인하거나 `workflows/` 디렉토리를 점검하고 앱을 다시 시작해 주세요.")
         session_state.current_view = 'welcome' ; st.rerun(); return

    # --- 에피소드 정보 관리 (수정됨) ---
    current_step_number = session_state.get('current_step', 1) # 현재 단계 번호
    episode_info = session_state.get('current_episode_info') # 현재 에피소드 정보

    # 1단계 이후이고, episode_info가 아직 설정되지 않았다면 생성 시도
    if current_step_number > 1 and episode_info is None:
        selected_topic = session_state.get('selected_workflow_topic')
        if selected_topic:
            st.info("✨ 선택된 토픽 기반으로 에피소드 정보 생성/확인 중...")
            # generate_episode_info 호출 시 선택된 토픽 객체 전달
            new_episode_info = generate_episode_info(
                session_state, channels_root_dir, current_workflow_name, selected_topic
            )
            if new_episode_info:
                session_state.current_episode_info = new_episode_info
                episode_info = new_episode_info # 현재 렌더링에 바로 사용
                # 에피소드 정보가 성공적으로 설정되었음을 알림 (최초 1회)
                if st.session_state.get(f'episode_info_msg_shown_{episode_info["episode_id"]}') is None:
                     st.success(f"✅ 에피소드 준비 완료 (ID: `{episode_info.get('episode_id')}`) `{episode_info.get('episode_path')}`")
                     st.session_state[f'episode_info_msg_shown_{episode_info["episode_id"]}'] = True # 메시지 표시 플래그 설정
                # st.rerun() # 여기서 rerun하면 무한 루프 가능성 있음. 상태 변경만 하고 진행.
            else:
                # generate_episode_info 내부에서 이미 에러 메시지 출력됨
                st.warning("워크플로우 진행을 중단합니다.")
                # 필요시 사용자에게 이전 단계로 돌아가거나 재시작 안내
                if st.button("↩️ 1단계로 돌아가기", key="gen_episode_fail_back_to_1"):
                     session_state.current_step = 1
                     session_state.current_episode_info = None
                     st.rerun()
                return # 진행 중단
        else:
             # 1단계는 완료했는데 토픽이 없는 경우 (비정상 상태)
             st.error("❌ 오류: 다음 단계를 위한 토픽 정보가 없습니다. 1단계로 돌아갑니다.")
             session_state.current_step = 1
             session_state.current_episode_info = None # 에피소드 정보 확실히 초기화
             st.rerun()
             return

    # --- 현재 단계 정보 찾기 ---
    current_step_definition = None
    if isinstance(workflow_definition.get("steps"), list):
        for step in workflow_definition["steps"]:
            if isinstance(step, dict) and step.get("number") == current_step_number:
                current_step_definition = step
                break

    if not current_step_definition:
        st.error(f"❌ 오류: 워크플로우 '{current_workflow_name}'에 정의되지 않은 단계 번호 '{current_step_number}'.")
        if st.button("↩️ 1단계로 돌아가기", key="invalid_step_back_to_1"):
             session_state.current_step = 1
             session_state.current_episode_info = None
             st.rerun()
        return

    # --- 공통 헤더 정보 표시 ---
    step_display_name = current_step_definition.get('name', '이름 없음')
    st.header(f"단계 {current_step_number}: {step_display_name}")
    st.write(f"현재 작업 채널: **{session_state.selected_channel_name}** (워크플로우: {current_workflow_name})")
    st.write(f"선택된 모드: **{session_state.mode}**")
    # episode_info가 설정된 이후에만 ID와 경로 표시
    if episode_info:
        st.caption(f"에피소드 ID (토픽 ID): `{episode_info.get('episode_id', 'N/A')}`")
        st.caption(f"저장 경로: `{episode_info.get('episode_path', 'N/A')}`")
    else: # 1단계 상태
        st.caption("에피소드 ID: (토픽 선정 후 결정됩니다)")

    st.markdown("---") # 단계 내용 시작 전 구분선

    # --- 단계 렌더링 함수 동적 로딩 및 호출 ---
    render_file_name = current_step_definition.get("render_file")
    render_function_name = current_step_definition.get("render_function", STEP_RENDER_FUNCTION_NAME)

    if not render_file_name:
        st.error(f"❌ 오류: 단계 {current_step_number} 정의에 'render_file' 정보가 없습니다.")
        if st.button("↩️ 워크플로우 중단 및 초기 화면으로", key="workflow_render_no_file_back_to_welcome"):
             # 워크플로우 상태 초기화
             session_state.current_episode_info = None
             session_state.selected_workflow_topic = None
             session_state.generated_script_data = None
             # ... 다른 워크플로우 상태 초기화 ...
             session_state.current_workflow_name = None
             session_state.current_step = 1
             session_state.current_view = 'welcome'
             st.rerun()
        return

    # 모듈 이름 생성 (예: workflows.workflow_basic.step_1_topic)
    module_name = f"workflows.{current_workflow_name}.{os.path.splitext(render_file_name)[0]}"

    try:
        # 모듈 동적 임포트 (app.py에서 sys.path 설정 필요)
        step_module = importlib.import_module(module_name)

        # 렌더링 함수 가져오기
        if hasattr(step_module, render_function_name):
            render_func = getattr(step_module, render_function_name)

            # 렌더링 함수 호출 (episode_info 전달 - 1단계에서는 None일 수 있음)
            render_func(
                session_state,
                channels_root_dir,
                episode_info, # 여기서는 None이거나 유효한 dict
                workflow_definition
            )
        else:
            st.error(f"❌ 오류: 모듈 '{module_name}'에 렌더링 함수 '{render_function_name}'가 없습니다.")
            # 정의 파일 문제 시 복구 어려움 -> 재시작 유도
            if st.button("↩️ 워크플로우 중단 및 초기 화면으로", key="workflow_render_no_func_back_to_welcome"):
                 # 상태 초기화 ...
                 session_state.current_view = 'welcome'
                 st.rerun()

    except ImportError:
         st.error(f"❌ 오류: 단계 {current_step_number}의 렌더링 파일 '{render_file_name}' (모듈: {module_name})을 임포트할 수 없습니다.")
         st.warning(f"워크플로우 디렉토리 '{current_workflow_name}' 구조와 파일 이름, 내부 코드 오류 여부를 확인하세요.")
         st.info("특히 `workflows/` 및 하위 디렉토리에 `__init__.py` 파일이 있는지 확인하세요.")
         if st.button("↩️ 워크플로우 중단 및 초기 화면으로", key="workflow_render_import_error_back_to_welcome"):
              # 상태 초기화 ...
              session_state.current_view = 'welcome'
              st.rerun()

    except Exception as e:
         st.error(f"❌ 오류: 단계 {current_step_number} 렌더링 중 알 수 없는 오류 발생: {e}")
         st.exception(e) # 상세 오류 스택 트레이스 표시
         if st.button("🔄 워크플로우 재시작 (1단계로)", key="render_exception_restart"):
             # 상태 초기화 (에피소드 정보 포함)
             session_state.current_step = 1
             session_state.selected_workflow_topic = None
             session_state.generated_script_data = None
             session_state.current_episode_info = None
             # ... 다른 워크플로우 상태 초기화 ...
             st.rerun()