# app.py
import streamlit as st
import json
import os
import sys # sys.path 수정을 위해 필요
import datetime # 채널 정의 기본값 설정 등에 사용
# importlib # workflow_view에서 사용하므로 여기서 임포트 필요 없음

try:
    import streamlit_ace as st_ace
    json_editor_available = True
    st_ace_module = st_ace # 사용할 모듈 객체 저장
except ImportError:
    json_editor_available = False
    st_ace_module = None # 없으면 None



# --- sys.path 설정 ---
# 프로젝트 루트 디렉토리와 functions, workflows 디렉토리를 sys.path에 추가
# 이렇게 해야 다른 모듈에서 'functions.모듈명', 'workflows.워크플로우명.모듈명' 형태로 임포트 가능
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

functions_dir = os.path.join(project_root, "functions")
if functions_dir not in sys.path:
     sys.path.append(functions_dir)

workflows_dir = os.path.join(project_root, "workflows")
if workflows_dir not in sys.path:
     sys.path.append(workflows_dir)


# --- 뷰 모듈 임포트 ---
# workflow_view는 load_available_workflows 함수를 포함합니다.
from views import welcome, channel_settings_view, auto_settings_view, workflow_view


# --- 상수 정의 ---
CHANNELS_ROOT_DIR = "./channels" # 채널 디렉토리들이 저장될 루트 경로
# 앱 실행 시 채널 루트 디렉토리가 없으면 생성
os.makedirs(CHANNELS_ROOT_DIR, exist_ok=True)

# 기본 워크플로우 이름 설정 (채널 정의 파일에 없을 경우 사용)
DEFAULT_WORKFLOW_NAME = "basic"


# --- 가상(Simulated) 또는 실제 함수 정의 ---
# 이 함수들은 functions 디렉토리로 옮겨졌거나, 실제 로직으로 대체되어야 합니다.
# generate_initial_script, process_stage2 등은 functions/script_generation.py로 이동
# load_topics, save_topics 등은 functions/topic_utils.py로 이동

# 채널 생성 로직 시뮬레이션 함수 (functions/channel_utils.py 등으로 옮기는 것을 고려)
create_channel_logic_available = True # 이 함수가 사용 가능한지 여부
def create_channel_logic(channel_name, channels_root_dir):
    """
    새 채널 디렉토리 및 기본 설정 파일을 생성합니다.
    성공 시 (True, 성공 메시지), 실패 시 (False, 오류 메시지) 반환합니다.
    """
    channel_dir = os.path.join(channels_root_dir, channel_name)
    if os.path.exists(channel_dir):
        return False, f"'{channel_name}' 채널이 이미 존재합니다."

    try:
        os.makedirs(channel_dir)
        # 기본 channel_definition.json 파일 생성
        dummy_def = {
            "definitionVersion": "1.1", # 버전 관리
            "lastUpdated": datetime.datetime.now().isoformat(), # 마지막 업데이트 시간
            "channelInfo": {
                "channelName": channel_name,
                "niche": "",
                "coreMessage": "",
                "usp": ""
            },
            "targetAudience": {
                 "primaryAgeRange": ["all"],
                 "secondaryAgeRange": [],
                 "interests": [],
                 "needsOrPainPoints": [],
                 "preferredContentStyle": []
            },
            "channelIdentity": {
                 "personalityAdjectives": [],
                 "toneOfVoice": "standard",
                 "forbiddenTopicsOrTones": []
            },
            "contentStrategy": {
                 "contentPillars": [],
                 "primaryGoal": "",
                 "secondaryGoals": []
            },
            "shortsFormat": {
                "standardDurationSeconds": 30,
                "pacing": "normal",
                 "standardSegments": [ # 예시 세그먼트 (실제 채널에 맞게 수정 필요)
                     { "segmentName": "Hook & Intro", "purpose": "시청자 주의 끌기", "styleNotes": "흥미로운 질문이나 사실 제시", "estimatedDurationSeconds": 5 },
                     { "segmentName": "Main Point 1", "purpose": "첫 번째 핵심 정보 전달", "styleNotes": "간결하고 명확하게", "estimatedDurationSeconds": 10 },
                     { "segmentName": "Main Point 2", "purpose": "두 번째 핵심 정보 전달", "styleNotes": "시각 자료와 함께 설명", "estimatedDurationSeconds": 10 }
                 ],
                 "additionalSegments": [ # 예시 추가 세그먼트 (CTA 등)
                     {"segmentName": "CTA_Subscribe", "purpose": "구독 유도", "styleNotes": "구독, 좋아요, 알림 설정 부탁", "estimatedDurationSeconds": 3}
                 ],
                 "recurringElements": {}
            },
            "workflow": DEFAULT_WORKFLOW_NAME # 새 채널 생성 시 기본 워크플로우 설정
        }
        def_file_path = os.path.join(channel_dir, "channel_definition.json")
        with open(def_file_path, 'w', encoding='utf-8') as f:
            json.dump(dummy_def, f, indent=2, ensure_ascii=False)

        # TODO: 기본 썸네일 이미지를 복사하거나 생성하는 로직 추가 가능
        # TODO: 기본 Topics.json 파일을 복사하거나 생성하는 로직 추가 가능 (functions/topic_utils.py 사용 고려)

        return True, f"'{channel_name}' 채널 및 기본 설정 파일이 성공적으로 생성되었습니다."
    except Exception as e:
        if os.path.exists(channel_dir) and not os.listdir(channel_dir): # 디렉토리가 비어있으면 삭제
             try:
                 os.rmdir(channel_dir)
             except Exception:
                 pass # 삭제 실패는 무시

        return False, f"채널 생성 중 오류 발생: {e}"


# --- 세션 상태 초기화 ---
# 앱 실행 시 한 번만 실행됩니다.
# session_state 변수는 Streamlit 앱의 현재 세션 동안 상태를 유지합니다.
if 'current_view' not in st.session_state:
    st.session_state.current_view = 'welcome' # 현재 보여줄 화면 ('welcome', 'channel_settings', 'workflow', 'auto_settings')
if 'mode' not in st.session_state:
    st.session_state.mode = 'MANUAL' # 작업 모드 ('MANUAL', 'AUTO')
if 'current_step' not in st.session_state:
    st.session_state.current_step = 1 # 워크플로우 중일 때의 현재 단계 번호 (시작 단계)
if 'selected_channel_name' not in st.session_state:
    st.session_state.selected_channel_name = None # 현재 작업 채널 이름
if 'current_channel_definition' not in st.session_state:
    st.session_state.current_channel_definition = None # 현재 작업 채널의 JSON 정의 내용
if 'current_channel_thumbnail_path' not in st.session_state:
     st.session_state.current_channel_thumbnail_path = None # 현재 작업 채널의 썸네일 이미지 파일 경로
if 'current_workflow_name' not in st.session_state: # 현재 선택된 워크플로우 이름 (채널 정의에서 로드)
     st.session_state.current_workflow_name = None # 채널 로드 시 업데이트
if 'channel_topics' not in st.session_state: # 현재 채널의 로드된 토픽 데이터 (list of dicts)
     st.session_state.channel_topics = None
if 'selected_workflow_topic' not in st.session_state: # 현재 워크플로우에서 선택된 토픽 (dict)
     st.session_state.selected_workflow_topic = None
if 'generated_script_data' not in st.session_state: # 워크플로우 2단계에서 생성된 스크립트 데이터
     st.session_state.generated_script_data = None
if 'auto_topic_selection_strategy' not in st.session_state: # AUTO 모드 토픽 선정 전략 (auto_settings_view에서 설정)
     st.session_state.auto_topic_selection_strategy = 'FIFO (가장 오래된 항목 먼저)' # 기본값
if 'current_episode_info' not in st.session_state: # 현재 진행 중인 워크플로우 에피소드 정보 {id, path}
     st.session_state.current_episode_info = None # 워크플로우 시작 시 생성
if 'generated_visual_plan' not in st.session_state:
     st.session_state.generated_visual_plan = None 
# json_editor_available과 st_ace_module은 app.py 상단 try/except 블록에서 정의됨


# --- 사용 가능한 워크플로우 로딩 (앱 시작 시 한 번만) ---
# workflow_view 모듈의 load_available_workflows 함수를 호출합니다.
# 로드된 워크플로우 정의는 session_state에 저장됩니다.
if 'all_workflow_definitions' not in st.session_state:
    # load_available_workflows 함수는 오류 발생 시 UI 메시지를 출력할 수 있습니다.
    st.session_state.all_workflow_definitions = workflow_view.load_available_workflows()
    # 로드된 워크플로우가 없으면 사용자에게 안내
    if not st.session_state.all_workflow_definitions:
        st.error("❌ 사용 가능한 워크플로우 정의를 찾을 수 없습니다.")
        st.warning(f"`{workflow_view.WORKFLOWS_ROOT_DIR}` 디렉토리와 그 하위에 `workflow_[워크플로우 이름]/workflow.json` 파일이 올바르게 구성되었는지 확인하세요.")


# --- 사이드바 레이아웃 (전역 요소 및 조건부 워크플로우 단계) ---
with st.sidebar:
    st.subheader("현재 채널")
    # 현재 선택된 채널 이름, 워크플로우 이름, 썸네일 표시
    if st.session_state.selected_channel_name:
        col1, col2 = st.columns([1, 3]) # 썸네일과 이름/워크플로우를 위한 컬럼 분할
        with col1:
            if st.session_state.current_channel_thumbnail_path and os.path.exists(st.session_state.current_channel_thumbnail_path):
                 st.image(st.session_state.current_channel_thumbnail_path, caption="", width=50)
            else:
                 st.markdown("🖼️") # Placeholder
        with col2:
             st.write(f"**{st.session_state.selected_channel_name}**")
             # 현재 로드된 워크플로우 이름 표시
             if st.session_state.current_workflow_name:
                  st.caption(f"워크플로우: {st.session_state.current_workflow_name}")
             else:
                  st.caption("워크플로우: 미선택") # 채널 로드 전 또는 정의에 워크플로우 지정 안 됨

             # 현재 로드된 워크플로우 정의의 display_name을 표시
             current_wf_def = st.session_state.get('all_workflow_definitions', {}).get(st.session_state.current_workflow_name)
             if current_wf_def and current_wf_def.get("display_name"):
                  st.caption(f"({current_wf_def['display_name']})")


    else:
        st.warning("선택된 채널이 없습니다.")
        st.write("채널 설정을 통해 채널을 선택하거나 생성하세요.")

    st.markdown("---") # 구분선

    st.subheader("모드 선택")
    st.session_state.mode = st.radio(
        "원하는 작업 모드를 선택하세요:",
        ('MANUAL', 'AUTO'),
        horizontal=True,
        key="sidebar_mode_radio"
    )
    st.write(f"선택된 모드: **{st.session_state.mode}**")

    st.markdown("---") # 구분선

    # 채널 설정 버튼 (항상 표시)
    if st.button("⚙️ 채널 설정", key="goto_channel_settings_button"):
        st.session_state.current_view = 'channel_settings'
        st.rerun()

    # AUTO 생성 설정 버튼 (항상 표시, 채널 설정 버튼 아래)
    if st.button("⚙️ AUTO 설정", key="goto_auto_settings_button"):
        st.session_state.current_view = 'auto_settings'
        st.rerun()

    # --- 작업 시작 버튼 (워크플로우 선택 기능 포함 고려) ---
    # 현재는 채널 정의에 명시된 기본 워크플로우로 시작
    # TODO: 여러 워크플로우가 있을 때, 여기서 드롭다운 등으로 선택하게 할 수 있음.
    current_channel_workflow_name = st.session_state.current_channel_definition.get('workflow', DEFAULT_WORKFLOW_NAME) if st.session_state.current_channel_definition else DEFAULT_WORKFLOW_NAME
    available_workflows = st.session_state.get('all_workflow_definitions', {}) # 로드된 전체 워크플로우 정의
    workflow_exists = current_channel_workflow_name in available_workflows # 채널 정의의 워크플로우가 실제로 로드되었는지 확인

    # 작업 시작 버튼 레이블 결정
    start_button_label = "▶ 작업 시작 (채널 선택 필요)"
    if st.session_state.selected_channel_name:
         if workflow_exists:
              # 로드된 워크플로우의 display_name 사용
              wf_display_name = available_workflows[current_channel_workflow_name].get("display_name", current_channel_workflow_name)
              start_button_label = f"▶ '{wf_display_name}' 작업 시작"
         else:
              start_button_label = f"▶ 작업 시작 (워크플로우 '{current_channel_workflow_name}' 정의 없음)"
              # 워크플로우가 로드되지 않았다는 경고는 app.py 상단에서 출력됨


    # 작업 시작 버튼 활성화 조건
    start_button_disabled = not st.session_state.selected_channel_name or not workflow_exists or st.session_state.current_view == 'workflow' # 채널 선택됨, 워크플로우 로드됨, 현재 워크플로우 실행 중 아님

    # 작업 시작 버튼 표시
    if st.session_state.current_view != 'workflow' and st.session_state.selected_channel_name:
         if st.button(start_button_label, disabled=start_button_disabled, key="start_workflow_button"):
              # 워크플로우 시작 시 관련 세션 상태 설정
              st.session_state.current_view = 'workflow' # 뷰 상태를 워크플로우로 변경
              st.session_state.current_workflow_name = current_channel_workflow_name # 시작할 워크플로우 이름 설정
              # 워크플로우 정의에서 시작 단계 번호 찾기 (일반적으로 1이지만, 정의에 따라 다를 수 있음)
              start_step_number = 1 # 기본 시작 단계
              if workflow_exists:
                   steps_list = available_workflows[current_channel_workflow_name].get("steps", [])
                   if steps_list:
                        # 정의된 단계 목록에서 가장 작은 번호를 시작 단계로 사용
                        sorted_steps = sorted(steps_list, key=lambda x: x.get('number', float('inf')))
                        if sorted_steps[0].get("number") is not None:
                            start_step_number = sorted_steps[0].get("number")


              st.session_state.current_step = start_step_number # 워크플로우 첫 단계 번호로 이동 (정의 기반)
              # 이전 워크플로우 실행 관련 데이터 초기화
              st.session_state.selected_workflow_topic = None
              st.session_state.channel_topics = None # 토픽 데이터 다시 로드하도록 초기화
              st.session_state.generated_script_data = None
              st.session_state.current_episode_info = None # 새 에피소드 정보 생성 필요 상태로 변경 (workflow_view에서 생성됨)

              if 'generated_visual_plan' in st.session_state: st.session_state.generated_visual_plan = None
              if 'processed_visual_plan_final' in st.session_state: st.session_state.processed_visual_plan_final = None
              if 'image_processing_triggered' in st.session_state: st.session_state.image_processing_triggered = False
              if 'manual_selections' in st.session_state: st.session_state.manual_selections = None
              if 'audio_generation_triggered' in st.session_state: st.session_state.audio_generation_triggered = False
              if 'audio_generation_result' in st.session_state: st.session_state.audio_generation_result = None
              if 'audio_data_for_display' in st.session_state: st.session_state.audio_data_for_display = None
              if 'video_generation_triggered' in st.session_state: st.session_state.video_generation_triggered = False
              if 'video_generation_result' in st.session_state: st.session_state.video_generation_result = None
              if 'final_video_path_state' in st.session_state: st.session_state.final_video_path_state = None

              st.rerun() # 변경된 상태로 즉시 새로고침


    # 진행 단계와 단계 이동 버튼은 워크플로우 뷰일 때만 표시
    if st.session_state.current_view == 'workflow':
        # 현재 활성화된 워크플로우의 단계 정의를 로드된 전체 정의에서 가져옴
        current_workflow_definition = st.session_state.get('all_workflow_definitions', {}).get(st.session_state.current_workflow_name, {})
        current_workflow_steps_list = current_workflow_definition.get('steps', [])

        if not current_workflow_steps_list:
             # 알 수 없는 워크플로우 상태 (위에서 이미 처리될 가능성이 높음)
             st.warning(f"⚠️ 알 수 없는 워크플로우 '{st.session_state.current_workflow_name}' 이거나 정의된 단계가 없습니다.")
             if st.button("↩️ 메인 화면으로 돌아가기", key="unknown_workflow_goto_welcome"):
                  st.session_state.current_view = 'welcome'
                  st.session_state.current_workflow_name = None
                  st.rerun()
        else:
            st.subheader("진행 단계")
            # 현재 단계 번호
            current_step_number = st.session_state.get('current_step')
            # 현재 단계의 이름 찾기
            current_step_name = "알 수 없음"
            for step_def in current_workflow_steps_list:
                 if step_def.get('number') == current_step_number:
                      current_step_name = step_def.get('name', '이름 없음')
                      break

            st.write(f"현재 단계: **{current_step_number}. {current_step_name}**")

            # 각 단계로 이동할 수 있는 버튼
            st.write("단계 이동:")
            # 현재 워크플로우의 단계 목록만 사용
            # 단계를 번호 순서대로 정렬하여 표시하는 것이 좋습니다.
            sorted_steps = sorted(current_workflow_steps_list, key=lambda x: x.get('number', float('inf')))

            for step_def in sorted_steps:
                step_num = step_def.get('number')
                step_name = step_def.get('name', '이름 없음')
                if step_num is not None:
                    disabled_status = (st.session_state.current_step == step_num)
                    if st.button(f"단계 {step_num}: {step_name}", key=f"workflow_goto_{step_num}", disabled=disabled_status):
                        st.session_state.current_step = step_num
                        # Streamlit 버튼 클릭은 자체적으로 Rerun을 발생시킵니다.


# --- 메인 콘텐츠 영역 ---
st.title("AI 기반 숏츠 자동 생성 프로그램")
# st.write(f"현재 뷰: {st.session_state.current_view}") # 디버깅용 현재 뷰 상태 표시

# 현재 뷰 상태에 따라 해당 뷰(페이지) 렌더링 함수 호출
if st.session_state.current_view == 'welcome':
    welcome.show_page(st.session_state)

elif st.session_state.current_view == 'channel_settings':
    # 채널 설정 뷰에는 사용 가능한 워크플로우 목록을 전달하여
    # 채널의 기본 워크플로우를 선택하게 합니다.
    available_workflows = st.session_state.get('all_workflow_definitions', {}) # 로드된 전체 워크플로우 정의
    channel_settings_view.show_page(
        st.session_state,
        CHANNELS_ROOT_DIR,
        create_channel_logic, # app.py에 정의된 함수 전달
        json_editor_available, # app.py에 정의된 변수 전달
        st_ace_module, # app.py에 정의된 변수 전달
        list(available_workflows.keys()) # 워크플로우 이름 목록만 전달
    )

elif st.session_state.current_view == 'auto_settings':
    auto_settings_view.show_page(st.session_state) # 세션 상태 전달

elif st.session_state.current_view == 'workflow':
    # 워크플로우 뷰는 로드된 전체 워크플로우 정의와 채널 루트 경로만 전달받습니다.
    # 나머지(현재 워크플로우 정의, 에피소드 정보)는 workflow_view 내부에서 session_state 참조/관리
    workflow_view.show_page(
        st.session_state,
        st.session_state.get('all_workflow_definitions', {}), # 로드된 전체 워크플로우 정의 전달
        CHANNELS_ROOT_DIR # 채널 루트 경로 전달
    )

else:
    st.error("❌ 알 수 없는 프로그램 상태입니다. 초기 화면으로 돌아갑니다.")
    # 알 수 없는 상태 진입 시 안전하게 초기화
    st.session_state.current_view = 'welcome'
    st.session_state.current_step = 1
    st.session_state.selected_channel_name = None
    st.session_state.current_channel_definition = None
    st.session_state.current_channel_thumbnail_path = None
    st.session_state.current_workflow_name = None
    st.session_state.channel_topics = None
    st.session_state.selected_workflow_topic = None
    st.session_state.generated_script_data = None
    st.session_state.current_episode_info = None

    st.rerun()


# --- Streamlit Ace 라이브러리 설치 안내 (선택 사항) ---
# JSON 편집기 사용 안내를 메인 화면 하단에 표시
# json_editor_available 변수는 app.py 상단에서 체크됨
if not json_editor_available:
    st.info("💡 **JSON 편집기 안내:** 채널 정의 편집 시 더 편리한 JSON 편집기를 사용하려면 `streamlit-ace` 라이브러리 설치를 권장합니다.\n\n터미널에서 다음 명령어를 실행하세요:\n`pip install streamlit-ace`")
