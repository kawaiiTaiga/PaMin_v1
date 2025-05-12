# PaMin/workflows/workflow_basic/step_5_audio.py
import streamlit as st
import os
import json
import time
import traceback

# --- functions/audio_generation.py 에서 백엔드 함수 임포트 ---
# app.py에서 sys.path 설정으로 functions 디렉토리가 접근 가능하다고 가정
try:
    from functions import audio_generation
    load_tts_config_func = audio_generation.load_tts_config
    generate_audio_and_timestamps_func = audio_generation.generate_audio_and_timestamps
    # 라이브러리 로드 상태 확인 (audio_generation 모듈 내부에 정의됨)
    libraries_available_flag = audio_generation._libraries_available
except ImportError:
    st.error("❌ 오류: 오디오 생성 백엔드 모듈(audio_generation.py)을 로드할 수 없습니다.")
    # 더미 함수 설정
    load_tts_config_func = lambda *args, **kwargs: None
    generate_audio_and_timestamps_func = lambda *args, **kwargs: False
    libraries_available_flag = False
except AttributeError: # _libraries_available 플래그가 없을 경우 대비
     st.error("❌ 오류: 오디오 생성 백엔드 모듈(audio_generation.py) 로드 중 문제 발생.")
     load_tts_config_func = lambda *args, **kwargs: None
     generate_audio_and_timestamps_func = lambda *args, **kwargs: False
     libraries_available_flag = False


# --- 5단계(음성 생성) 렌더링 함수 ---
def render_step(session_state, channels_root_dir, episode_info, workflow_definition):
    """
    워크플로우의 5단계 (음성 생성 및 타임스탬프 매핑) 페이지를 렌더링합니다.

    Args:
        session_state: Streamlit session_state
        channels_root_dir: 채널 루트 디렉토리 경로
        episode_info: 현재 에피소드 정보를 담은 딕셔너리 {"episode_id": "...", "episode_path": "..."}
        workflow_definition: 현재 워크플로우의 전체 정의 딕셔너리 (workflow.json 내용)
    """
    st.write("여기에 **5단계**: 생성된 스크립트 기반 음성 생성 및 타임스탬프 매핑 UI가 들어갑니다.")
    st.caption(f"에피소드 ID: `{episode_info.get('episode_id', 'N/A')}`")

    # --- 백엔드 기능 가용성 확인 ---
    if not libraries_available_flag:
        st.error("❌ 오디오 생성에 필요한 라이브러리가 설치되지 않았거나 로드할 수 없습니다.")
        st.warning("Zonos, Whisper, Torch, Librosa 등이 올바르게 설치되었는지 확인하세요.")
        # 이전 단계로 돌아가는 버튼 제공
        if st.button("↩️ 4단계로 돌아가기", key="back_to_step4_from_step5_no_libs"):
            session_state.current_step = 4 # 이전 단계 번호
            st.rerun()
        return

    # --- 필요한 입력 데이터 경로 설정 ---
    episode_path = episode_info.get('episode_path')
    channel_name = session_state.selected_channel_name
    if not episode_path or not os.path.isdir(episode_path):
        st.error(f"❌ 오류: 에피소드 경로를 찾을 수 없습니다: {episode_path}")
        return
    if not channel_name:
        st.error("❌ 오류: 채널 이름이 설정되지 않았습니다.")
        return

    # 이전 단계 결과 파일 경로
    # Script Stage 2 JSON (TTS 입력 텍스트)
    script_stage2_filename = f"script_stage2_{episode_info.get('episode_id')}.json"
    script_stage2_filepath = os.path.join(episode_path, script_stage2_filename)
    # Visual Plan with Selection JSON (청크 정보 참조)
    visual_plan_filepath = os.path.join(episode_path, "visual_plan_with_selection.json")

    # TTS 설정 파일 경로
    channel_dir = os.path.join(channels_root_dir, channel_name)
    tts_config_path = os.path.join(channel_dir, "tts_config.json")

    # 출력 파일/디렉토리 경로 (이 단계에서 생성될)
    tts_config_data = load_tts_config_func(channel_dir) # 설정 먼저 로드
    if tts_config_data is None:
         st.error(f"❌ 오류: TTS 설정 파일({tts_config_path})을 로드할 수 없습니다.")
         return

    audio_output_subdir_name = tts_config_data.get('audio_output_subdir', 'generated_audio')
    episode_audio_output_dir = os.path.join(episode_path, audio_output_subdir_name)
    final_output_json_filename = "audio_timestamps_output.json" # 최종 결과 파일 이름 고정
    final_output_json_path = os.path.join(episode_path, final_output_json_filename)

    # --- 입력 파일 존재 확인 ---
    if not os.path.exists(script_stage2_filepath):
        st.error(f"❌ 오류: TTS를 위한 스크립트 파일(Stage 2)을 찾을 수 없습니다: `{script_stage2_filepath}`")
        st.warning("2단계를 다시 실행하여 스크립트 파일을 생성해주세요.")
        if st.button("↩️ 2단계로 돌아가기", key="back_to_step2_from_step5_no_script"):
            session_state.current_step = 2
            st.rerun()
        return
    if not os.path.exists(visual_plan_filepath):
         st.error(f"❌ 오류: 시각 자료 계획 파일(4단계 결과)을 찾을 수 없습니다: `{visual_plan_filepath}`")
         st.warning("4단계를 다시 실행하여 시각 자료 계획 파일을 생성해주세요.")
         if st.button("↩️ 4단계로 돌아가기", key="back_to_step4_from_step5_no_visual"):
             session_state.current_step = 4
             st.rerun()
         return

    # --- 상태 관리 (Session State) ---
    # 오디오 생성 프로세스 시작/완료 여부 및 결과 상태
    if 'audio_generation_triggered' not in session_state:
        session_state.audio_generation_triggered = False # 프로세스 시작 여부
    if 'audio_generation_result' not in session_state:
        session_state.audio_generation_result = None # 결과 상태 (True: 성공, False: 실패, None: 미시작)
    # MANUAL 모드 표시용 데이터
    if 'audio_data_for_display' not in session_state:
         session_state.audio_data_for_display = None

    # --- 모드별 처리 ---

    # AUTO 모드
    if session_state.mode == 'AUTO':
        # 아직 생성이 시작되지 않았거나 실패했을 경우 자동으로 실행
        if not session_state.audio_generation_triggered or session_state.audio_generation_result is False:
            st.info("⏳ AUTO 모드: 음성 생성 및 타임스탬프 매핑을 자동으로 시작합니다...")
            with st.spinner("Zonos TTS, Whisper 타임스탬프 추출 및 매핑 진행 중... 시간이 걸릴 수 있습니다."):
                try:
                    # 백엔드 함수 호출
                    success = generate_audio_and_timestamps_func(
                        script_file_path=script_stage2_filepath,
                        visual_plan_file_path=visual_plan_filepath,
                        episode_audio_output_dir=episode_audio_output_dir,
                        final_output_json_path=final_output_json_path,
                        channel_dir=channel_dir,
                        tts_config=tts_config_data
                    )
                    session_state.audio_generation_result = success
                    session_state.audio_generation_triggered = True # 프로세스 완료 표시
                    session_state.audio_data_for_display = None # 결과 표시용 데이터 초기화 (재로드 필요)
                    st.rerun() # 상태 변경 후 UI 업데이트

                except Exception as e:
                    st.error(f"❌ AUTO 모드 오디오 생성 중 심각한 오류 발생: {e}")
                    st.exception(e)
                    session_state.audio_generation_result = False
                    session_state.audio_generation_triggered = True # 시도는 했으므로 True
                    # AUTO 모드 실패 시 워크플로우 중단 필요

        # 생성 성공 시 다음 단계로 자동 이동
        elif session_state.audio_generation_result is True:
            st.success("✅ AUTO 모드: 음성 생성 및 타임스탬프 매핑 완료!")
            st.info(f"결과 파일: `{final_output_json_path}`")
            st.info(f"생성된 오디오 파일 경로: `{episode_audio_output_dir}`")

            next_step_number = get_next_step_number(workflow_definition, session_state.current_step)
            if next_step_number:
                st.info(f"➡️ 다음 단계 ({get_step_name(workflow_definition, next_step_number)})로 자동 이동합니다...")
                time.sleep(2) # 메시지 확인 시간
                session_state.current_step = next_step_number
                st.rerun()
            else:
                st.info("✅ 워크플로우의 마지막 단계(음성 생성)입니다. (AUTO 모드 완료)")
                 # TODO: AUTO 모드 최종 완료 처리 (예: 요약 정보 표시, 상태 초기화 등)


    # MANUAL 모드
    elif session_state.mode == 'MANUAL':
        st.subheader("수동 음성 생성 및 확인")

        # 생성 시작/재생성 버튼
        generate_button_label = "🔄 음성 생성/재생성" if session_state.audio_generation_triggered else "▶️ 음성 생성 시작"
        if st.button(generate_button_label, key="manual_generate_audio_button"):
            st.info("⏳ 음성 생성 및 타임스탬프 매핑을 시작합니다...")
            session_state.audio_generation_triggered = True # 버튼 누르면 일단 Triggered
            session_state.audio_generation_result = None # 결과 초기화
            session_state.audio_data_for_display = None # 표시 데이터 초기화

            with st.spinner("Zonos TTS, Whisper 타임스탬프 추출 및 매핑 진행 중... 시간이 걸릴 수 있습니다."):
                try:
                    # 백엔드 함수 호출
                    success = generate_audio_and_timestamps_func(
                        script_file_path=script_stage2_filepath,
                        visual_plan_file_path=visual_plan_filepath,
                        episode_audio_output_dir=episode_audio_output_dir,
                        final_output_json_path=final_output_json_path,
                        channel_dir=channel_dir,
                        tts_config=tts_config_data
                    )
                    session_state.audio_generation_result = success
                    st.rerun() # 완료 후 UI 업데이트

                except Exception as e:
                    st.error(f"❌ MANUAL 모드 오디오 생성 중 심각한 오류 발생: {e}")
                    st.exception(e) # 전체 트레이스백 표시
                    session_state.audio_generation_result = False
                    # 실패해도 rerun하여 오류 메시지 표시

        # 결과 표시
        st.markdown("---")
        if session_state.audio_generation_result is True:
            st.success("✅ 음성 생성 및 타임스탬프 매핑 완료!")
            st.info(f"결과 파일: `{final_output_json_path}`")
            st.info(f"생성된 오디오 파일 경로: `{episode_audio_output_dir}`")

            # 결과 데이터 로드 및 표시
            if session_state.audio_data_for_display is None:
                 try:
                     with open(final_output_json_path, 'r', encoding='utf-8') as f:
                         # 전체 구조 {"total_estimated_audio_duration_seconds": ..., "sentences": [...]} 로드
                         loaded_data = json.load(f)
                         # 실제 표시에 필요한 것은 sentences 리스트
                         session_state.audio_data_for_display = loaded_data.get("sentences", [])
                 except FileNotFoundError:
                     st.error(f"❌ 결과 파일({final_output_json_path})을 찾을 수 없어 표시할 수 없습니다.")
                     session_state.audio_data_for_display = [] # 빈 리스트로 설정
                 except Exception as e:
                     st.error(f"❌ 결과 파일 로딩 중 오류: {e}")
                     session_state.audio_data_for_display = [] # 빈 리스트로 설정

            # 데이터 표시 (문장별 오디오 재생)
            if session_state.audio_data_for_display:
                 st.subheader("📄 문장별 생성 결과 확인")
                 for i, sentence_data in enumerate(session_state.audio_data_for_display):
                     st.markdown(f"**{i+1}. 문장:** `{sentence_data.get('sentence', '내용 없음')}`")
                     audio_path = sentence_data.get('audio_path')
                     if audio_path and os.path.exists(audio_path):
                         try:
                             # 오디오 파일 읽기 (st.audio는 파일 경로 또는 BytesIO 지원)
                             with open(audio_path, 'rb') as audio_file:
                                 audio_bytes = audio_file.read()
                             st.audio(audio_bytes, format='audio/wav') # WAV 형식 지정
                             st.caption(f"길이: {sentence_data.get('sentence_duration', 0):.2f}초 | 파일: {os.path.basename(audio_path)}")

                             # (선택 사항) 단어 타임스탬프 표시
                             with st.expander("단어별 타임스탬프 보기"):
                                 words_text = ""
                                 for chunk in sentence_data.get('chunks', []):
                                     for word_info in chunk.get('words', []):
                                         words_text += f"`{word_info['word']}`({word_info['start']:.2f}s-{word_info['end']:.2f}s) "
                                 st.write(words_text if words_text else "타임스탬프 정보 없음")

                         except Exception as e:
                              st.warning(f"⚠️ 오디오 파일({os.path.basename(audio_path)}) 재생 중 오류: {e}")
                     else:
                          st.warning(f"⚠️ 오디오 파일 경로를 찾을 수 없거나 유효하지 않습니다: {audio_path}")

                     # TODO: 특정 문장 재생성 기능 (구현 복잡도 높음)
                     # if st.button(f"문장 {i+1} 재생성", key=f"regen_sentence_{i}"):
                     #     st.info(f"문장 {i+1} 재생성 기능은 아직 구현되지 않았습니다.")
                     #     # 재생성 로직:
                     #     # 1. 해당 문장 텍스트 가져오기
                     #     # 2. 단일 문장 TTS 함수 호출 (generate_zonos_audio) - 기존 파일 덮어쓰기
                     #     # 3. 단일 문장 Whisper 함수 호출 (extract_whisper_timestamps)
                     #     # 4. 전체 결과 JSON 파일 업데이트 (해당 문장 부분만 교체)
                     #     # 5. session_state.audio_data_for_display 업데이트 및 st.rerun()

                     st.markdown("---") # 문장 구분선

            else:
                 # audio_data_for_display 로드 실패 또는 빈 경우
                 st.warning("표시할 오디오 데이터가 없습니다.")


            # 다음 단계 버튼 (성공적으로 생성된 경우에만 활성화)
            next_step_number = get_next_step_number(workflow_definition, session_state.current_step)
            if next_step_number:
                 if st.button(f"➡️ 다음 단계 ({get_step_name(workflow_definition, next_step_number)}) 진행", key="manual_goto_next_step_from_step5"):
                     session_state.current_step = next_step_number
                     st.rerun()
            else: # 마지막 단계일 경우
                 st.info("✅ 워크플로우의 마지막 단계(음성 생성)입니다.")
                 if st.button("🏁 워크플로우 완료", key="complete_workflow_step5"):
                     complete_workflow_manual_mode(session_state, channels_root_dir)


        elif session_state.audio_generation_result is False:
            st.error("❌ 음성 생성 또는 처리 중 오류가 발생했습니다.")
            st.info("오류 로그를 확인하고 '음성 생성/재생성' 버튼을 다시 눌러 시도해주세요.")
        else: # None (미시작 상태)
            st.info("MANUAL 모드: '음성 생성 시작' 버튼을 눌러 프로세스를 시작하세요.")


# --- Helper functions (다른 스텝 파일에서 복사 또는 공통 유틸리티로 분리 가능) ---
def get_next_step_number(workflow_definition, current_step_num):
    """워크플로우 정의에서 현재 단계 다음 단계의 번호를 찾습니다."""
    steps_list = workflow_definition.get("steps", [])
    current_index = -1
    for i, step in enumerate(steps_list):
        if step.get("number") == current_step_num:
            current_index = i
            break
    if current_index != -1 and current_index + 1 < len(steps_list):
        return steps_list[current_index + 1].get("number")
    return None

def get_step_name(workflow_definition, step_num):
     """워크플로우 정의에서 해당 번호의 단계 이름을 찾습니다."""
     for step in workflow_definition.get("steps", []):
          if step.get("number") == step_num:
               return step.get("name", "이름 없음")
     return "알 수 없음"

def complete_workflow_manual_mode(session_state, channels_root_dir):
     """MANUAL 모드 워크플로우 완료 처리 (토픽 저장 및 상태 초기화) - step_4에서 가져옴"""
     try:
          from functions import topic_utils
          mark_topic_used_and_save = topic_utils.mark_topic_used_and_save
     except ImportError:
          st.error("❌ 오류: 토픽 유틸리티 함수를 로드할 수 없어 완료 처리를 할 수 없습니다.")
          return

     # 완료 처리 시 필요한 정보 확인
     selected_topic = session_state.get('selected_workflow_topic')
     channel_topics_list = session_state.get('channel_topics') # 로드된 전체 토픽 목록
     channel_name = session_state.get('selected_channel_name')

     if selected_topic and channel_topics_list is not None and channel_name:
          st.info(f"토픽 '{selected_topic.get('TOPIC', '제목 없음')}'을 사용 완료로 표시하고 저장합니다.")
          # mark_topic_used_and_save 함수 호출 시 전체 topics_data 전달 필요
          save_success = mark_topic_used_and_save(
              channels_root_dir,
              channel_name,
              selected_topic.get("TOPIC"),
              channel_topics_list # 현재 로드된 전체 토픽 목록 전달
          )
          if save_success:
               st.success("🎉 워크플로우 완료! Topics.json 파일 업데이트 완료.")
               # 워크플로우 관련 세션 상태 초기화 (새로운 에피소드 준비)
               keys_to_reset = [
                   'selected_workflow_topic', 'channel_topics', 'generated_script_data',
                   'current_episode_info', 'generated_visual_plan', 'processed_visual_plan_final',
                   'image_processing_triggered', 'manual_selections', 'audio_generation_triggered',
                   'audio_generation_result', 'audio_data_for_display'
               ]
               for key in keys_to_reset:
                    if key in session_state:
                         del session_state[key] # 또는 session_state[key] = None

               session_state.current_workflow_name = None # 현재 실행중인 워크플로우 이름 초기화
               st.session_state.current_step = 1 # 다음 실행을 위해 1단계로 초기화
               session_state.current_view = 'welcome' # 환영 화면으로 이동
               st.rerun()
          else:
               st.error("❌ Topics.json 파일 업데이트 실패.")
     else:
          missing = []
          if not selected_topic: missing.append("선택된 토픽 정보")
          if channel_topics_list is None: missing.append("전체 토픽 목록")
          if not channel_name: missing.append("채널 이름")
          st.warning(f"⚠️ 워크플로우 완료 처리에 필요한 정보 부족: {', '.join(missing)}")