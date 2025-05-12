# PaMin/workflows/workflow_basic/step_6_video_generation.py
import streamlit as st
import os
import json
import time
import traceback

# --- functions/video_generation_basic.py 에서 백엔드 함수 임포트 ---
try:
    from functions import video_generation_basic
    generate_complete_video_func = video_generation_basic.generate_complete_video_with_processed_subs
    video_generation_available_flag = True # 실제로는 모듈 내 플래그 사용 권장
except ImportError:
    st.error("❌ 오류: 비디오 생성 백엔드 모듈(video_generation_basic.py)을 로드할 수 없습니다.")
    generate_complete_video_func = lambda *args, **kwargs: False
    video_generation_available_flag = False
except AttributeError:
     st.error("❌ 오류: 비디오 생성 백엔드 모듈(video_generation_basic.py) 로드 중 문제 발생.")
     generate_complete_video_func = lambda *args, **kwargs: False
     video_generation_available_flag = False


# --- 6단계(최종 영상 생성) 렌더링 함수 ---
def render_step(session_state, channels_root_dir, episode_info, workflow_definition):
    st.write("여기에 **6단계**: 모든 데이터를 종합하여 최종 숏츠 영상을 생성하는 UI가 들어갑니다.")
    st.caption(f"에피소드 ID: `{episode_info.get('episode_id', 'N/A')}`")

    if not video_generation_available_flag:
        st.error("❌ 비디오 생성에 필요한 라이브러리가 설치되지 않았거나 로드할 수 없습니다.")
        if st.button("↩️ 5단계로 돌아가기", key="back_to_step5_from_step6_no_libs"):
            session_state.current_step = 5
            st.rerun()
        return

    episode_path = episode_info.get('episode_path')
    channel_name = session_state.selected_channel_name
    if not episode_path or not os.path.isdir(episode_path):
        st.error(f"❌ 오류: 에피소드 경로를 찾을 수 없습니다: {episode_path}")
        return
    if not channel_name:
        st.error("❌ 오류: 채널 이름이 설정되지 않았습니다.")
        return

    processed_data_json_filename = "audio_timestamps_output.json" # 5단계 결과
    processed_data_json_path = os.path.join(episode_path, processed_data_json_filename)

    channel_dir = os.path.join(channels_root_dir, channel_name)
    channel_def_path = os.path.join(channel_dir, "channel_definition.json")
    video_config = None
    base_video_path_config = None
    bgm_path_config = None

    if os.path.exists(channel_def_path):
        try:
            with open(channel_def_path, 'r', encoding='utf-8') as f:
                channel_def = json.load(f)
            video_config = channel_def.get('videoTemplateConfig')
            if not video_config:
                 video_config = { # 기본값 설정
                    'resolution': (1080, 1920), 'fps': 30,
                    'background_color': (30, 30, 30),
                    'use_base_video_as_visual_background': True,
                    'image_frame_scale': (0.9, 0.65),
                    'image_frame_position': ('center', 1050),
                    'image_padding_within_frame': 0.98,
                    'font_path': 'C:/Users/gaterbelt/Downloads/fonts/NanumGothic.ttf',
                    'font_size': 70, 'font_color': 'white',
                    'text_position': ('center', 1550),
                    'text_highlight_color': (0, 0, 0, 172),
                    'subtitle_target_chars': 35,
                    'subtitle_debug': False,
                    # 'title_text'는 아래에서 스크립트 제목으로 덮어쓰거나 채널명 사용
                    'title_font_path': 'C:/Users/gaterbelt/Downloads/fonts/NanumGothic.ttf',
                    'title_font_size': 85, 'title_font_color': 'black',
                    'title_position': ('center', 285),
                    'bgm_volume_factor': 0.20,
                 }
                 st.info("채널 정의에 'videoTemplateConfig'가 없어 기본 설정을 사용합니다.")
            base_video_path_config = os.path.join(channel_dir, "base_video.mp4")
            bgm_path_config = os.path.join(channel_dir, "bgm.mp3")
        except Exception as e:
            st.error(f"채널 정의 파일({channel_def_path}) 로드 또는 처리 중 오류: {e}")
            video_config = None
    else:
        st.error(f"채널 정의 파일({channel_def_path})을 찾을 수 없습니다.")
        video_config = None

    # --- LLM 생성 제목 로드 ---
    script_stage2_filename = f"script_stage2_{episode_info.get('episode_id')}.json" # 2단계 결과 파일명
    script_stage2_filepath = os.path.join(episode_path, script_stage2_filename)
    llm_generated_title = "영상 제목" # 기본값

    if os.path.exists(script_stage2_filepath):
        try:
            with open(script_stage2_filepath, 'r', encoding='utf-8') as f_script:
                script_content_data = json.load(f_script)
            # script_content_data는 script_generation.py의 parse_marker_text 결과 (dict)
            # 또는 process_stage2 결과일 수 있음. 'title' 키를 찾음.
            title_from_file = script_content_data.get('title')
            if title_from_file and isinstance(title_from_file, str) and title_from_file.strip():
                llm_generated_title = title_from_file
                st.info(f"스크립트에서 제목 로드: '{llm_generated_title}'")
            else:
                st.warning(f"`{script_stage2_filename}` 파일에서 유효한 'title'을 찾을 수 없어 기본 제목을 사용합니다.")
                # 채널명 fallback (video_config가 있을 경우)
                if video_config and channel_def:
                     llm_generated_title = channel_def.get('channelInfo', {}).get('channelName', '영상 제목')

        except Exception as e:
            st.error(f"`{script_stage2_filename}` 파일 로드 또는 파싱 중 오류: {e}. 기본 제목을 사용합니다.")
            if video_config and channel_def: # 채널명 fallback
                 llm_generated_title = channel_def.get('channelInfo', {}).get('channelName', '영상 제목')
    else:
        st.error(f"스크립트 파일 `{script_stage2_filename}`을 찾을 수 없습니다. 제목을 가져올 수 없습니다.")
        if video_config and 'channel_def' in locals() and channel_def: # 채널명 fallback
             llm_generated_title = channel_def.get('channelInfo', {}).get('channelName', '영상 제목')
        st.warning(f"기본/채널명 제목 사용: '{llm_generated_title}'")


    final_video_filename = f"final_shorts_{episode_info.get('episode_id')}.mp4"
    final_video_output_path = os.path.join(episode_path, final_video_filename)

    if not os.path.exists(processed_data_json_path):
        st.error(f"❌ 오류: 비디오 생성을 위한 처리된 데이터 파일({processed_data_json_filename})을 찾을 수 없습니다.")
        if st.button("↩️ 5단계로 돌아가기", key="back_to_step5_from_step6_no_json"):
            session_state.current_step = 5
            st.rerun()
        return

    if not video_config:
        st.error("❌ 오류: 비디오 생성 설정을 로드할 수 없습니다. 채널 정의 파일을 확인하세요.")
        return

    use_base_video = video_config.get('use_base_video_as_visual_background', False)
    if use_base_video and (not base_video_path_config or not os.path.exists(base_video_path_config)):
         st.error(f"❌ 오류: 배경 비디오 파일({base_video_path_config})을 찾을 수 없습니다.")
         base_video_path_config = None
    if bgm_path_config and not os.path.exists(bgm_path_config):
        st.warning(f"⚠️ BGM 파일({bgm_path_config})을 찾을 수 없습니다. BGM 없이 진행됩니다.")
        bgm_path_config = None

    if 'video_generation_triggered' not in session_state:
        session_state.video_generation_triggered = False
    if 'video_generation_result' not in session_state:
        session_state.video_generation_result = None
    if 'final_video_path_state' not in session_state:
        session_state.final_video_path_state = None

    if session_state.mode == 'AUTO':
        if not session_state.video_generation_triggered or session_state.video_generation_result is False:
            st.info("⏳ AUTO 모드: 최종 비디오 생성을 자동으로 시작합니다...")
            with st.spinner("최종 숏츠 영상 생성 중... 시간이 매우 오래 걸릴 수 있습니다."):
                try:
                    success = generate_complete_video_func(
                        config=video_config,
                        json_data_path=processed_data_json_path,
                        base_video_path=base_video_path_config,
                        bgm_path=bgm_path_config,
                        output_path=final_video_output_path,
                        video_title_from_script=llm_generated_title # LLM 생성 제목 전달
                    )
                    session_state.video_generation_result = success
                    if success:
                         session_state.final_video_path_state = final_video_output_path
                    session_state.video_generation_triggered = True
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ AUTO 모드 비디오 생성 중 심각한 오류 발생: {e}")
                    st.exception(e)
                    session_state.video_generation_result = False
                    session_state.video_generation_triggered = True
        elif session_state.video_generation_result is True:
            st.success("✅ AUTO 모드: 최종 비디오 생성 완료!")
            st.info(f"결과 파일: `{session_state.final_video_path_state}`")
            if session_state.final_video_path_state and os.path.exists(session_state.final_video_path_state):
                 try:
                     st.video(session_state.final_video_path_state)
                 except Exception as e:
                      st.error(f"비디오 표시 중 오류: {e}")
            st.info("✅ 워크플로우의 마지막 단계(영상 생성)입니다. (AUTO 모드 완료)")
            if st.button("🎉 AUTO 워크플로우 완료", key="complete_auto_workflow"):
                 complete_workflow_manual_mode(session_state, channels_root_dir)

    elif session_state.mode == 'MANUAL':
        st.subheader("수동 최종 영상 생성")
        generate_button_label = "🔄 최종 영상 재생성" if session_state.video_generation_triggered else "▶️ 최종 영상 생성 시작"
        if st.button(generate_button_label, key="manual_generate_video_button"):
            st.info("⏳ 최종 비디오 생성을 시작합니다...")
            session_state.video_generation_triggered = True
            session_state.video_generation_result = None
            session_state.final_video_path_state = None
            with st.spinner("최종 숏츠 영상 생성 중... 시간이 매우 오래 걸릴 수 있습니다."):
                try:
                    success = generate_complete_video_func(
                        config=video_config,
                        json_data_path=processed_data_json_path,
                        base_video_path=base_video_path_config,
                        bgm_path=bgm_path_config,
                        output_path=final_video_output_path,
                        video_title_from_script=llm_generated_title # LLM 생성 제목 전달
                    )
                    session_state.video_generation_result = success
                    if success:
                        session_state.final_video_path_state = final_video_output_path
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ MANUAL 모드 비디오 생성 중 심각한 오류 발생: {e}")
                    st.exception(e)
                    session_state.video_generation_result = False
        st.markdown("---")
        if session_state.video_generation_result is True:
            st.success("✅ 최종 비디오 생성 완료!")
            st.info(f"결과 파일: `{session_state.final_video_path_state}`")
            if session_state.final_video_path_state and os.path.exists(session_state.final_video_path_state):
                try:
                    video_file = open(session_state.final_video_path_state, 'rb')
                    video_bytes = video_file.read()
                    st.video(video_bytes)
                    video_file.close()
                except Exception as e:
                    st.error(f"비디오 표시 중 오류: {e}")
            else:
                st.warning("생성된 비디오 파일을 찾을 수 없습니다.")
            st.info("✅ 워크플로우의 마지막 단계(영상 생성)입니다.")
            if st.button("🏁 워크플로우 완료", key="complete_workflow_step6"):
                complete_workflow_manual_mode(session_state, channels_root_dir)
        elif session_state.video_generation_result is False:
            st.error("❌ 최종 비디오 생성 중 오류가 발생했습니다.")
            st.info("오류 로그를 확인하고 '최종 영상 재생성' 버튼을 다시 눌러 시도해주세요.")
        else:
            st.info("MANUAL 모드: '최종 영상 생성 시작' 버튼을 눌러 프로세스를 시작하세요.")

# --- Helper functions (다른 스텝 파일에서 복사 또는 공통 유틸리티로 분리 가능) ---
def get_next_step_number(workflow_definition, current_step_num):
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
     for step in workflow_definition.get("steps", []):
          if step.get("number") == step_num:
               return step.get("name", "이름 없음")
     return "알 수 없음"

def complete_workflow_manual_mode(session_state, channels_root_dir):
     try:
          from functions import topic_utils
          mark_topic_used_and_save = topic_utils.mark_topic_used_and_save
     except ImportError:
          st.error("❌ 오류: 토픽 유틸리티 함수를 로드할 수 없어 완료 처리를 할 수 없습니다.")
          return
     selected_topic = session_state.get('selected_workflow_topic')
     channel_topics_list = session_state.get('channel_topics')
     channel_name = session_state.get('selected_channel_name')
     topic_id_to_mark = selected_topic.get("topic_id") if selected_topic else None # ID 가져오기
     if selected_topic and topic_id_to_mark and channel_topics_list is not None and channel_name: # ID 존재 여부 확인
          st.info(f"토픽 '{selected_topic.get('TOPIC', '제목 없음')}' (ID: {topic_id_to_mark})을 사용 완료로 표시하고 저장합니다.")
          save_success = mark_topic_used_and_save(
              channels_root_dir,
              channel_name,
              topic_id_to_mark, # ID 전달
              channel_topics_list
          )
          if save_success:
               st.success("🎉 워크플로우 완료! Topics.json 파일 업데이트 완료.")
               keys_to_reset = [
                   'selected_workflow_topic', 'channel_topics', 'generated_script_data',
                   'current_episode_info', 'generated_visual_plan', 'processed_visual_plan_final',
                   'image_processing_triggered', 'manual_selections', 'audio_generation_triggered',
                   'audio_generation_result', 'audio_data_for_display', 'video_generation_triggered',
                   'video_generation_result', 'final_video_path_state'
               ]
               for key in keys_to_reset:
                    if key in session_state:
                         del session_state[key]
               session_state.current_workflow_name = None
               st.session_state.current_step = 1
               session_state.current_view = 'welcome'
               st.rerun()
          else:
               st.error("❌ Topics.json 파일 업데이트 실패.")
     else:
          missing = []
          if not selected_topic: missing.append("선택된 토픽 정보")
          elif not topic_id_to_mark: missing.append("선택된 토픽의 ID") # ID 누락 메시지 추가
          if channel_topics_list is None: missing.append("전체 토픽 목록")
          if not channel_name: missing.append("채널 이름")
          st.warning(f"⚠️ 워크플로우 완료 처리에 필요한 정보 부족: {', '.join(missing)}")