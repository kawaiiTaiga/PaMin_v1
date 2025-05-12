# workflows/workflow_basic/step_2_script.py
import streamlit as st
import json
import os
import datetime
import time

# --- functions/script_generation.py에서 백엔드 함수 임포트 ---
# workflows 디렉토리에서 functions 디렉토리에 접근하기 위한 임포트 방식
# app.py에서 sys.path를 설정하거나 상대 경로 임포트 사용
try:
    # from ...functions import script_generation # 상대 경로 임포트
    from functions import script_generation # app.py에서 sys.path 설정 가정

    # script_generation 모듈에서 필요한 함수 및 변수 가져오기
    generate_initial_script_func = script_generation.generate_initial_script
    process_stage2_func = script_generation.process_stage2
    langchain_available = script_generation.langchain_available
    google_api_key = script_generation.GOOGLE_API_KEY
    script_generation_available_flag = True # 임포트 성공

except ImportError:
    st.error("❌ 오류: 스크립트 생성 백엔드 모듈을 로드할 수 없습니다.")
    st.warning("`functions/script_generation.py` 파일이 올바른 위치에 있는지, 필요한 라이브러리(LangChain 등)가 설치되었는지 확인하세요.")
    # 함수들을 더미 함수로 대체하고 사용 불가 플래그 설정
    generate_initial_script_func = lambda *args, **kwargs: None
    process_stage2_func = lambda *args, **kwargs: None
    langchain_available = False
    google_api_key = None # API 키 없음으로 설정
    script_generation_available_flag = False # 임포트 실패

# --- 2단계 렌더링 함수 ---
# 새로운 시그니처에 맞게 수정: episode_info, workflow_definition 인자 추가
# episode_info는 {"episode_id": "...", "episode_path": "..."} 형태
def render_step(session_state, channels_root_dir, episode_info, workflow_definition):
    """
    워크플로우의 2단계 (스크립트 생성 및 처리) 페이지를 렌더링합니다.

    Args:
        session_state: Streamlit session_state
        channels_root_dir: 채널 루트 디렉토리 경로
        episode_info: 현재 에피소드 정보를 담은 딕셔너리 {"episode_id": "...", "episode_path": "..."}
        workflow_definition: 현재 워크플로우의 전체 정의 딕셔너리 (workflow.json 내용)
    """

    st.write("여기에 **2단계**: 스크립트 생성 및 이를 기반으로 영상 제작하는 UI 요소가 들어갑니다.")
    st.caption(f"에피소드 ID: `{episode_info.get('episode_id', 'N/A')}`")
    st.caption(f"에피소드 경로: `{episode_info.get('episode_path', 'N/A')}`")


    # LLM 기능 사용 가능 여부 확인 및 경고 표시
    # 스크립트 생성 시도 전에 미리 체크
    if not script_generation_available_flag:
         st.error("❌ 스크립트 생성 기능을 사용할 수 없습니다 (`script_generation.py` 모듈 로드 실패).")
         st.warning("`functions/script_generation.py` 파일이 올바른 위치에 있는지 확인하고 앱을 다시 시작하세요.")
         # 스크립트 생성이 불가능하므로 여기서 더 이상 진행할 수 없음을 알림
         if st.button("↩️ 1단계로 돌아가 토픽 다시 선택", key="back_to_step1_from_step2_no_scriptgen"):
              session_state.current_step = 1
              session_state.selected_workflow_topic = None # 토픽 선택 초기화
              session_state.generated_script_data = None # 스크립트 데이터 초기화
              st.rerun()
         return # 기능 사용 불가 시 렌더링 중단
    
    if not google_api_key:
         st.error("❌ Google API Key가 설정되지 않아 LLM 기반 스크립트 생성을 할 수 없습니다.")
         st.warning(".env 파일에 `GOOGLE_API_KEY='YOUR_API_KEY'` 형식으로 API 키를 설정하거나 `functions/script_generation.py` 파일에서 키를 확인해 주세요.")
         if st.button("↩️ 1단계로 돌아가 토픽 다시 선택", key="back_to_step1_from_step2_no_apikey"):
              session_state.current_step = 1
              session_state.selected_workflow_topic = None
              session_state.generated_script_data = None
              st.rerun()
         return # 기능 사용 불가 시 렌더링 중단

    if not langchain_available:
         st.error("❌ LangChain 라이브러리가 설치되지 않아 LLM 기반 스크립트 생성을 할 수 없습니다.")
         st.warning("터미널에서 `pip install langchain-google-genai`를 실행하여 라이브러리를 설치해 주세요.")
         if st.button("↩️ 1단계로 돌아가 토픽 다시 선택", key="back_to_step1_from_step2_no_langchain"):
              session_state.current_step = 1
              session_state.selected_workflow_topic = None
              session_state.generated_script_data = None
              st.rerun()
         return # 기능 사용 불가 시 렌더링 중단


    # 2-1. 스크립트 데이터 생성 (이 단계에 처음 진입했거나 데이터가 없을 때만 생성 시도)
    # 스크립트 데이터는 session_state.generated_script_data에 저장됩니다.
    if session_state.generated_script_data is None:
        st.info("⏳ 스크립트 생성을 시작합니다...")

        # 1단계에서 선정된 토픽을 가져옵니다.
        topic_for_script = session_state.selected_workflow_topic

        if not topic_for_script:
             st.warning("⚠️ 스크립트 생성을 위한 토픽이 선정되지 않았습니다. 1단계로 돌아가 토픽을 선정해주세요.")
             if st.button("↩️ 1단계로 돌아가기", key="back_to_step1_from_step2_no_topic"):
                  session_state.current_step = 1
                  st.rerun()
             return # 토픽 없으면 여기서 중단

        # 채널 정의 파일 경로 설정
        channel_def_path = os.path.join(channels_root_dir, session_state.selected_channel_name, "channel_definition.json")
        if not os.path.exists(channel_def_path):
             st.error(f"❌ 오류: 채널 정의 파일 '{channel_def_path}'을 찾을 수 없습니다. 채널 설정을 확인해 주세요.")
             if st.button("⚙️ 채널 설정으로 이동", key="goto_settings_from_step2_no_def"):
                  session_state.current_view = 'channel_settings'
                  st.rerun()
             return # 정의 파일 없으면 중단

        # --- 스크립트 결과물을 저장할 최종 디렉토리 설정 ---
        # episode_info에서 에피소드별 고유 경로를 가져옵니다.
        # script_specific_output_dir는 이 에피소드의 스크립트 결과가 저장될 하위 디렉토리입니다.
        # 예: ./channels/채널이름/episodes/에피소드ID/scripts/
        episode_path = episode_info.get('episode_path')
        if not episode_path:
             st.error("❌ 오류: 현재 에피소드의 저장 경로가 설정되지 않았습니다.")
             # 이 에러는 workflow_view에서 episode_info 설정에 문제가 있을 때 발생합니다.
             if st.button("↩️ 1단계로 돌아가 다시 시작", key="back_to_step1_from_step2_no_episode_path"):
                  session_state.current_step = 1
                  session_state.selected_workflow_topic = None
                  session_state.generated_script_data = None
                  session_state.current_episode_info = None # 에피소드 정보 초기화
                  st.rerun()
             return

        # 스크립트 결과만 모아둘 에피소드 하위 디렉토리
        script_output_dir = os.path.join(episode_path, "scripts")
        # generate_initial_script_func 내부에서 이 디렉토리가 생성됩니다.


        # --- 스크립트 생성 및 처리 백엔드 함수 호출 ---
        # generate_initial_script_func (Stage 1: LLM 호출 및 초기 파싱)
        # process_stage2_func (Stage 2: 상세 처리 및 추가 세그먼트 결합)

        raw_script_data = None
        processed_script_data = None
        generation_failed = False

        try:
            with st.spinner("시나리오 초안 생성 중 (Stage 1: LLM 호출)... 잠시 기다려주세요."):
                 # generate_initial_script_func 호출 (인자로 최종 저장 경로 전달)
                 # script_generation.py의 generate_initial_script 함수는 output_dir에 파일을 저장하도록 되어 있습니다.
                 # episode_path를 output_dir의 베이스로 사용합니다.
                 raw_script_data = generate_initial_script_func(topic_for_script, channel_def_path, episode_path) # <-- 수정: episode_path 자체를 전달

            if raw_script_data and raw_script_data.get("segments"):
                 st.success("✅ 시나리오 초안 생성 및 파싱 완료 (Stage 1).")
                 st.info("⏳ 시나리오 상세 처리 중 (Stage 2)...")
                 with st.spinner("스크립트 세그먼트 처리, 시간 할당 등..."):
                     try:
                         with open(channel_def_path, 'r', encoding='utf-8') as f:
                              channel_def_for_stage2 = json.load(f)
                     except Exception as e:
                          st.error(f"❌ 스크립트 상세 처리를 위한 채널 정의 로드 중 오류 발생: {e}")
                          channel_def_for_stage2 = None
                          processed_script_data = None

                     if channel_def_for_stage2:
                          # process_stage2_func 호출
                          processed_script_data = process_stage2_func(raw_script_data, channel_def_for_stage2)

                 if processed_script_data:
                      st.success("✅ 스크립트 상세 처리 완료 (Stage 2).")
                      # 최종 처리된 스크립트 데이터를 세션 상태에 저장
                      session_state.generated_script_data = processed_script_data
                      # TODO: Stage 2 처리 결과 파일 저장 로직 추가 (script_generation.py의 process_stage2 함수에 저장 로직이 없다면 여기서)
                      # script_generation.py의 generate_initial_script 함수는 raw 결과를 저장하지만 process_stage2 결과는 저장하지 않습니다.
                      # 여기서 Stage 2 결과 JSON 파일을 에피소드 경로 아래에 저장합니다.
                      stage2_filename = f"script_stage2_{episode_info.get('episode_id')}.json" # 에피소드 ID를 파일명에 포함
                      stage2_filepath = os.path.join(episode_path, stage2_filename) # 에피소드 루트 경로 아래 저장

                      try:
                          os.makedirs(episode_path, exist_ok=True) # 에피소드 루트 디렉토리 생성 확인
                          with open(stage2_filepath, 'w', encoding='utf-8') as f:
                              json.dump(processed_script_data, f, indent=2, ensure_ascii=False)
                          st.info(f"💾 Stage 2 결과 파일 저장 완료: `{stage2_filepath}`")
                      except Exception as e:
                          st.warning(f"⚠️ Stage 2 결과 파일 저장 중 오류 발생: {e}")


                 else:
                      st.error("❌ 스크립트 상세 처리 중 오류가 발생했습니다.")
                      session_state.generated_script_data = None
                      generation_failed = True

            else: # Stage 1 실패 (raw_script_data is None or no segments)
                st.error("❌ 시나리오 초안 생성 또는 초기 파싱 중 오류가 발생했거나 유효한 세그먼트가 없습니다.")
                session_state.generated_script_data = None
                generation_failed = True

        except Exception as e: # 생성/처리 시도 중 예상치 못한 예외 발생
            st.error(f"❌ 스크립트 생성/처리 과정 중 알 수 없는 오류 발생: {e}")
            session_state.generated_script_data = None
            generation_failed = True


    # --- 생성된 스크립트 데이터가 이미 있거나, 방금 성공적으로 생성된 경우 ---
    if session_state.generated_script_data is not None:
        st.write("---")
        st.write("✨ **생성 및 처리 완료된 스크립트:**")
        processed_script_data = session_state.generated_script_data
        st.write(f"**영상 제목:** {processed_script_data.get('title', '제목 없음')}")
        st.write(f"**예상 총 길이:** {processed_script_data.get('total_estimated_duration_seconds', 0):.1f} 초")
        st.write("**세그먼트:**")
        if processed_script_data.get('segments'):
             for i, seg in enumerate(processed_script_data['segments']):
                  st.write(f"**{i+1}. {seg.get('type', '알 수 없음')}** ({seg.get('duration_seconds', 0):.1f}초 예상)")
                  with st.expander(f"스크립트 내용 보기 (클릭)", expanded=False):
                       st.write(seg.get('script', '스크립트 없음'))

        else:
             st.warning("로드된 스크립트 데이터에 유효한 세그먼트가 없습니다.")

        st.write("---")

        # --- 모드별 다음 단계 진행 로직 ---
        if session_state.mode == 'MANUAL':
            st.subheader("스크립트 확인 및 다음 단계 진행")
            # 다음 단계 번호를 workflow_definition에서 찾아서 이동
            current_step_number = None
            for step in workflow_definition.get("steps", []):
                if step.get("render_file") == "step_2_script.py": # 현재 파일을 참조
                    current_step_number = step.get("number")
                    break

            next_step_number = None
            if current_step_number is not None:
                current_step_index = -1
                for i, step in enumerate(workflow_definition.get("steps", [])):
                    if step.get("number") == current_step_number:
                        current_step_index = i
                        break
                if current_step_index != -1 and current_step_index + 1 < len(workflow_definition.get("steps", [])):
                     next_step_number = workflow_definition["steps"][current_step_index + 1].get("number")

            if next_step_number is not None:
                 if st.button("➡️ 스크립트 확인 완료, 다음 단계 진행", key="manual_goto_next_step_button_from_step2"):
                      st.session_state.current_step = next_step_number
                      st.rerun() # 다음 단계로 이동
            else:
                 st.info("✅ 현재 워크플로우의 마지막 단계 스크립트까지 생성했습니다.")
                 # 워크플로우 완료를 위한 별도 버튼 또는 안내 필요

        elif session_state.mode == 'AUTO':
            st.subheader("스크립트 자동 생성 완료")
            st.info("✅ 스크립트 생성이 완료되었습니다. 다음 단계로 자동으로 진행합니다...")
            # 다음 단계 번호를 workflow_definition에서 찾아서 이동
            current_step_number = None
            for step in workflow_definition.get("steps", []):
                if step.get("render_file") == "step_2_script.py": # 현재 파일을 참조
                    current_step_number = step.get("number")
                    break

            next_step_number = None
            if current_step_number is not None:
                current_step_index = -1
                for i, step in enumerate(workflow_definition.get("steps", [])):
                    if step.get("number") == current_step_number:
                        current_step_index = i
                        break
                if current_step_index != -1 and current_step_index + 1 < len(workflow_definition.get("steps", [])):
                     next_step_number = workflow_definition["steps"][current_step_index + 1].get("number")

            if next_step_number is not None:
                 st.session_state.current_step = next_step_number
                 st.rerun() # 다음 단계로 자동 이동
            else:
                 st.info("✅ 현재 워크플로우의 마지막 단계 스크립트까지 자동으로 생성했습니다.")
                 # TODO: AUTO 워크플로우 최종 완료 처리 (예: 완료 메시지 표시, 1단계로 돌아가기 등)
                 # 여기서는 일단 상태를 유지하고 다음 Rerun 때 다시 이 메시지를 표시


    # --- 스크립트 생성 실패 등으로 session_state.generated_script_data가 None인 경우 ---
    # (생성 시도를 했으나 실패한 상태)
    elif session_state.selected_workflow_topic and session_state.generated_script_data is None:
         st.error("❌ 스크립트 생성에 실패했습니다. 다시 시도하거나 1단계로 돌아가 토픽을 변경해 보세요.")
         st.info("💡 오류 로그나 콘솔 메시지를 확인하여 실패 원인을 파악해 보세요.")
         if st.button("🔄 스크립트 생성 다시 시도", key="retry_script_generation"):
              session_state.generated_script_data = None
              st.rerun()
         if st.button("↩️ 1단계로 돌아가 토픽 변경", key="back_to_step1_from_step2_failed"):
              session_state.current_step = 1
              session_state.selected_workflow_topic = None
              session_state.generated_script_data = None
              # episode_info는 유지 (같은 에피소드에서 재시도)
              st.rerun()