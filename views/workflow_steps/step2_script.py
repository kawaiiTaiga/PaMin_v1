import streamlit as st
import json
import os
import datetime
import time

# 2단계 렌더링 함수
# workflow_output_base_dir 인자를 추가로 받습니다.
def render_step2_script_page(session_state, channels_root_dir, workflow_output_base_dir, steps, # steps 인자는 필요시 사용
                             generate_initial_script_func, process_stage2_func,
                             langchain_available, google_api_key, script_generation_available_flag):
    """워크플로우의 2단계 (스크립트 생성 및 처리) 페이지를 렌더링합니다."""

    st.write("여기에 **2단계**: 스크립트 생성 및 이를 기반으로 영상 제작하는 UI 요소가 들어갑니다.")


    # LLM 기능 사용 가능 여부 확인 및 경고 표시
    # 이 체크는 생성 시도 전에 미리 하는 것이 좋습니다.
    if not script_generation_available_flag or not google_api_key or not langchain_available:
         st.error("❌ 스크립트 생성 기능에 필요한 설정이 완료되지 않았습니다.")
         if not script_generation_available_flag:
              st.warning("`script_generation.py` 파일이 없거나 종속성이 누락되었습니다. 프로젝트 루트 및 라이브러리 설치를 확인하세요.")
         if not google_api_key:
              st.warning("Google API Key가 설정되지 않았습니다. `.env` 파일을 확인하세요.")
         if not langchain_available:
              st.warning("LangChain 라이브러리가 설치되지 않았습니다. `pip install langchain-google-genai`를 실행하세요.")

         if st.button("↩️ 1단계로 돌아가 토픽 다시 선택", key="back_to_step1_from_step2_llm_error"):
              session_state.current_step = 1
              session_state.selected_workflow_topic = None # 토픽 선택 초기화
              session_state.generated_script_data = None # 스크립트 데이터 초기화
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
        # workflow_output_base_dir 아래에 스크립트 고유 디렉토리 생성
        # 예: ./channels/채널이름/generated_data/워크플로우이름/scripts/토픽제목_타임스탬프/
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        # 토픽 제목에서 파일명으로 부적절한 문자 제거 및 길이 제한
        safe_title = "".join(c for c in topic_for_script.get('TOPIC', 'untitled') if c.isalnum() or c in (' ', '_')).rstrip()
        if not safe_title: safe_title = "untitled"

        script_specific_output_dir = os.path.join(workflow_output_base_dir, "scripts", f"script_{timestamp}_{safe_title[:30]}")
        # script_specific_output_dir는 generate_initial_script_func 내부에서 생성됩니다.


        # --- 스크립트 생성 및 처리 백엔드 함수 호출 ---
        # generate_initial_script_func (Stage 1: LLM 호출 및 초기 파싱)
        # process_stage2_func (Stage 2: 상세 처리 및 추가 세그먼트 결합)
        # generate_initial_script_func는 Stage 1 결과 raw 텍스트와 raw 파싱 결과를 파일로 저장합니다.
        # process_stage2_func 호출 후 반환된 데이터는 Stage 2 결과 파일로 저장합니다.

        raw_script_data = None
        processed_script_data = None
        generation_failed = False # 생성 실패 플래그

        try:
            with st.spinner("시나리오 초안 생성 중 (Stage 1: LLM 호출)... 잠시 기다려주세요."):
                 # generate_initial_script_func 호출 (인자로 최종 저장 경로 전달)
                 raw_script_data = generate_initial_script_func(topic_for_script, channel_def_path, script_specific_output_dir) # <-- 수정: output_root_dir 대신 최종 경로 전달

            if raw_script_data and raw_script_data.get("segments"):
                 st.success("✅ 시나리오 초안 생성 및 파싱 완료 (Stage 1).")
                 # st.write("---")
                 # st.write("📄 **생성된 시나리오 초안 (Raw 파싱):**") # Raw 파싱 결과 보여주기는 선택 사항
                 # st.json(raw_script_data)

                 st.info("⏳ 시나리오 상세 처리 중 (Stage 2)...")
                 with st.spinner("스크립트 세그먼트 처리, 시간 할당 등..."):
                     # 채널 정의 파일을 다시 로드하여 process_stage2_func에 전달
                     # generate_initial_script_func 내부에서 이미 로드했지만, 함수가 분리되어 있으므로 다시 로드
                     try:
                         with open(channel_def_path, 'r', encoding='utf-8') as f:
                              channel_def_for_stage2 = json.load(f)
                     except Exception as e:
                          st.error(f"❌ 스크립트 상세 처리를 위한 채널 정의 로드 중 오류 발생: {e}")
                          channel_def_for_stage2 = None
                          processed_script_data = None # 정의 로드 실패 시 상세 처리 불가

                     if channel_def_for_stage2:
                          # process_stage2_func 호출
                          processed_script_data = process_stage2_func(raw_script_data, channel_def_for_stage2)

                 if processed_script_data:
                      st.success("✅ 스크립트 상세 처리 완료 (Stage 2).")
                      # 최종 처리된 스크립트 데이터를 세션 상태에 저장
                      session_state.generated_script_data = processed_script_data
                      # TODO: Stage 2 처리 결과 파일 저장 로직 추가
                      # 현재 script_generation.py의 generate_initial_script는 Stage 1 파일만 저장
                      # process_stage2 결과 저장은 이 뷰 또는 workflow_view에서 별도로 수행해야 함
                      # 파일명은 script_specific_output_dir를 기반으로 생성
                      stage2_filename = f"script_stage2_{timestamp}_{safe_title[:50]}.json"
                      stage2_filepath = os.path.join(script_specific_output_dir, stage2_filename)
                      try:
                          os.makedirs(script_specific_output_dir, exist_ok=True) # 저장 디렉토리 다시 확인
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
        # 저장된 스크립트 데이터를 사용자에게 다시 보여줍니다.
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
            if st.button("➡️ 스크립트 확인 완료, 다음 단계 (영상 제작) 진행", key="manual_goto_step3_button_from_step2"):
                 st.session_state.current_step = 3
                 st.rerun()

        elif session_state.mode == 'AUTO':
            st.subheader("스크립트 자동 생성 완료")
            st.info("✅ 스크립트 생성이 완료되었습니다. 다음 단계(영상 제작)로 자동으로 진행합니다...")
            st.session_state.current_step = 3
            st.rerun()


    # --- 스크립트 생성 실패 등으로 session_state.generated_script_data가 None인 경우 ---
    # (생성 시도를 했으나 실패한 상태)
    # LLM 기능 사용 가능 여부 체크 후 이 블록에 도달했다는 것은 생성 시도 중 실제 오류가 발생했음을 의미
    elif session_state.selected_workflow_topic and session_state.generated_script_data is None:
         st.error("❌ 스크립트 생성에 실패했습니다. 다시 시도하거나 1단계로 돌아가 토픽을 변경해 보세요.")
         st.info("💡 오류 로그나 콘솔 메시지를 확인하여 실패 원인을 파악해 보세요.")
         if st.button("🔄 스크립트 생성 다시 시도", key="retry_script_generation"):
              session_state.generated_script_data = None # 명시적으로 다시 None 설정 (이미 None이지만)
              st.rerun()
         if st.button("↩️ 1단계로 돌아가 토픽 변경", key="back_to_step1_from_step2_failed"):
              session_state.current_step = 1
              session_state.selected_workflow_topic = None
              session_state.generated_script_data = None
              st.rerun()