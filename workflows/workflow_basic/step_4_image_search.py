# PaMin/workflows/workflow_basic/step_4_movie.py
import streamlit as st
import json
import os
import random
import time

# --- functions/image_processing.py 에서 백엔드 함수 임포트 ---
try:
    from functions import image_processing
    process_visual_plan_func = image_processing.process_visual_plan
    # MANUAL 모드 재선택 로직 위해 개별 분석 함수도 임포트
    analyze_image_relevance_func = image_processing.analyze_image_relevance_langchain
    image_processing_available = True
except ImportError:
    st.error("❌ 오류: 이미지 처리 백엔드 모듈(image_processing.py)을 로드할 수 없습니다.")
    process_visual_plan_func = lambda *args, **kwargs: None
    analyze_image_relevance_func = lambda *args, **kwargs: None
    image_processing_available = False

# --- 4단계(영상 제작 준비 - 이미지 최종 선택) 렌더링 함수 ---
def render_step(session_state, channels_root_dir, episode_info, workflow_definition):
    """
    워크플로우의 4단계 (이미지 최종 선택 및 영상 제작 준비) 페이지를 렌더링합니다.

    Args:
        session_state: Streamlit session_state
        channels_root_dir: 채널 루트 디렉토리 경로
        episode_info: 현재 에피소드 정보를 담은 딕셔너리 {"episode_id": "...", "episode_path": "..."}
        workflow_definition: 현재 워크플로우의 전체 정의 딕셔너리 (workflow.json 내용)
    """
    st.write("여기에 **4단계**: 다운로드된 이미지/GIF 확인 및 최종 선택, 영상 제작 준비 UI가 들어갑니다.")
    st.caption(f"에피소드 ID: `{episode_info.get('episode_id', 'N/A')}`")

    # --- 백엔드 기능 가용성 확인 ---
    if not image_processing_available:
        st.error("❌ 이미지 처리 기능을 사용할 수 없습니다. 관리자에게 문의하세요.")
        # 이전 단계로 돌아가는 버튼 제공 등 오류 처리
        return

    # --- 필요한 입력 데이터 경로 설정 ---
    episode_path = episode_info.get('episode_path')
    if not episode_path or not os.path.isdir(episode_path):
        st.error(f"❌ 오류: 에피소드 경로를 찾을 수 없습니다: {episode_path}")
        # 워크플로우 재시작 등 심각한 오류 처리
        return

    # 3단계 결과 파일 경로 (process_visual_plan 함수의 입력)
    visual_plan_step3_filepath = os.path.join(episode_path, "visual_plan_output.json") # 3단계 결과 파일명 가정
    # 4단계 처리 결과 파일 경로 (process_visual_plan 함수의 출력)
    visual_plan_final_filepath = os.path.join(episode_path, "visual_plan_with_selection.json")

    # --- 데이터 처리 상태 관리 ---
    # process_visual_plan 함수 실행 여부 및 결과를 session_state로 관리
    if 'processed_visual_plan_final' not in session_state:
         session_state.processed_visual_plan_final = None
    if 'image_processing_triggered' not in session_state:
         session_state.image_processing_triggered = False # 함수 실행 완료 플래그

    # --- 이미지 다운로드 및 초기 자동 선택 실행 (최초 1회 또는 재시도 시) ---
    # 아직 처리되지 않았거나, 사용자가 재시도를 원할 경우 실행
    # MANUAL 모드는 여기서 바로 실행하지 않고 버튼을 통해 실행할 수도 있음
    # 여기서는 일단 4단계 진입 시 자동으로 실행하도록 구현 (AUTO/MANUAL 공통)

    run_processing = False
    if not session_state.image_processing_triggered:
         run_processing = True
         if not os.path.exists(visual_plan_step3_filepath):
              st.error(f"❌ 오류: 3단계 시각 자료 계획 파일이 없습니다: {visual_plan_step3_filepath}")
              st.warning("3단계를 먼저 완료해주세요.")
              if st.button("↩️ 3단계로 돌아가기", key="back_to_step3_from_step4_no_input"):
                   session_state.current_step = 3 # 이전 단계 번호
                   st.rerun()
              run_processing = False # 파일 없으면 실행 불가

    # (MANUAL 모드) 이미지 처리 재시도 버튼
    if session_state.mode == 'MANUAL':
         if st.button("🔄 이미지 다운로드/자동선택 재실행", key="retry_image_processing"):
              run_processing = True
              session_state.processed_visual_plan_final = None # 이전 결과 초기화
              session_state.image_processing_triggered = False # 플래그 리셋

    if run_processing and image_processing_available:
        st.info("⏳ 이미지 다운로드 및 초기 자동 선택을 시작합니다...")
        with st.spinner("이미지/GIF 다운로드 및 Gemini 분석/선택 중..."):
             # image_processing.py의 메인 함수 호출
             final_json_path = process_visual_plan_func(
                 visual_plan_file_path=visual_plan_step3_filepath,
                 episode_path=episode_path,
                 images_per_item=3 # 다운로드할 이미지 개수
             )

        if final_json_path and os.path.exists(final_json_path):
             st.success("✅ 이미지 다운로드 및 초기 자동 선택 완료!")
             session_state.image_processing_triggered = True # 성공 시 플래그 설정
             # 성공적으로 처리된 최종 데이터를 로드하여 session_state에 저장
             try:
                  with open(final_json_path, 'r', encoding='utf-8') as f:
                       session_state.processed_visual_plan_final = json.load(f)
                  st.rerun() # 데이터 로드 후 화면 다시 그리기
             except Exception as e:
                  st.error(f"❌ 처리 결과 파일 로드 오류: {e}")
                  session_state.processed_visual_plan_final = None
                  session_state.image_processing_triggered = False # 실패 시 플래그 리셋

        else:
             st.error("❌ 이미지 다운로드 또는 자동 선택 처리에 실패했습니다.")
             session_state.processed_visual_plan_final = None
             session_state.image_processing_triggered = False # 실패 시 플래그 리셋

    # --- 처리된 데이터가 있을 경우 UI 표시 ---
    if session_state.processed_visual_plan_final:
         st.write("---")
         st.subheader("🖼️ Chunk별 이미지 확인 및 최종 선택")

         processed_data = session_state.processed_visual_plan_final
         # MANUAL 모드 선택 사항 저장을 위한 상태 초기화
         if 'manual_selections' not in session_state or len(session_state.manual_selections) != len(processed_data):
              # 초기값은 자동 선택된 경로 또는 첫번째 유효 경로
              session_state.manual_selections = [
                  item.get('visual', {}).get('selected_local_path') or next((p for p in item.get('visual', {}).get('downloaded_local_paths', []) if p), None)
                  for item in processed_data
              ]

         # MANUAL 모드: 이미지 선택 UI
         if session_state.mode == 'MANUAL':
              st.info("각 Chunk별로 다운로드된 이미지/GIF를 확인하고 영상에 사용할 최종 이미지를 선택하세요.")

              # 자동 선택 일괄 적용 버튼
              if st.button("✨ 모든 Chunk에 자동 선택 적용", key="apply_all_auto_select"):
                  # 여기서는 저장된 자동 선택 결과를 단순히 UI에 반영
                  # 재분석이 필요하면 analyze_image_relevance_func 호출 로직 추가 필요
                  new_selections = []
                  for i, item in enumerate(processed_data):
                      auto_selected = item.get('visual', {}).get('selected_local_path')
                      # 자동 선택 결과가 없으면 첫 유효 이미지 선택
                      if not auto_selected:
                           auto_selected = next((p for p in item.get('visual', {}).get('downloaded_local_paths', []) if p), None)
                      new_selections.append(auto_selected)
                  session_state.manual_selections = new_selections
                  st.success("자동 선택 결과가 적용되었습니다. (저장 버튼을 눌러 확정)")
                  st.rerun()


              # 각 Chunk별 선택 UI
              for i, item in enumerate(processed_data):
                  st.markdown("---")
                  st.markdown(f"**Chunk {i+1}:** `{item.get('chunk_text', '')}`")
                  visual_info = item.get('visual', {})
                  downloaded_paths = [p for p in visual_info.get('downloaded_local_paths', []) if p and os.path.exists(p)] # 유효한 경로만 필터링
                  auto_selected_path = visual_info.get('selected_local_path')

                  if not downloaded_paths:
                       st.warning("⚠️ 다운로드된 이미지가 없습니다.")
                       session_state.manual_selections[i] = None # 선택할 이미지 없음
                       continue

                  # 선택 옵션 준비 (파일 경로 리스트)
                  options = downloaded_paths
                  # 현재 수동 선택된 경로 (없으면 자동 선택 결과 또는 첫번째 이미지)
                  current_manual_selection = session_state.manual_selections[i]
                  # 현재 선택된 값이 options 리스트에 있는지 확인, 없으면 첫번째 옵션으로 강제
                  try:
                      default_index = options.index(current_manual_selection) if current_manual_selection in options else 0
                  except ValueError:
                       default_index = 0


                  # 이미지 표시 및 선택 (가로 정렬 시도)
                  cols = st.columns(len(options))
                  selected_path_radio = None # 라디오 버튼으로 선택된 경로 저장

                  for idx, path in enumerate(options):
                      with cols[idx]:
                           st.image(path, width=100, caption=f"이미지 {idx+1}" + (" (Auto)" if path == auto_selected_path else ""))
                           # 라디오 버튼 대신, 이미지 아래에 선택 버튼 만들기 (UI 개선 가능)
                           # if st.button(f"선택 {idx+1}", key=f"select_img_{i}_{idx}"):
                           #     session_state.manual_selections[i] = path
                           #     st.rerun() # 선택 즉시 반영

                  # 라디오 버튼으로 최종 선택 (이미지 아래 배치)
                  # 경로 대신 옵션 번호(1, 2, 3...) 또는 짧은 파일명 표시 고려 가능
                  selected_path_radio = st.radio(
                      "최종 사용할 이미지 선택:",
                      options=options,
                      index=default_index,
                      key=f"radio_select_img_{i}",
                      format_func=lambda p: os.path.basename(p) + (" (Auto)" if p == auto_selected_path else ""), # 파일명만 표시
                      horizontal=True
                  )
                  # 라디오 버튼 변경 시 즉시 세션 상태 업데이트
                  session_state.manual_selections[i] = selected_path_radio

         # AUTO 모드: 자동 선택 결과 표시
         elif session_state.mode == 'AUTO':
              st.info("AUTO 모드: 각 Chunk별로 자동 선택된 이미지가 사용됩니다.")
              for i, item in enumerate(processed_data):
                  st.markdown("---")
                  st.markdown(f"**Chunk {i+1}:** `{item.get('chunk_text', '')}`")
                  visual_info = item.get('visual', {})
                  selected_path = visual_info.get('selected_local_path')
                  if selected_path and os.path.exists(selected_path):
                       st.image(selected_path, width=150, caption=f"자동 선택됨: {os.path.basename(selected_path)}")
                  elif visual_info.get('type') == 'generation':
                       st.info("ℹ️ 'generation' 타입은 이미지가 생성되지 않았습니다.")
                  else:
                       st.warning("⚠️ 자동 선택된 이미지를 찾을 수 없습니다.")

         # --- 최종 확정 및 다음 단계 ---
         st.markdown("---")
         st.subheader("최종 선택 확정 및 다음 단계")

         # MANUAL 모드: 최종 선택 저장 버튼
         if session_state.mode == 'MANUAL':
              if st.button("💾 **수동 선택 결과 확정/저장**", key="save_manual_selections"):
                   # session_state.manual_selections 내용을 최종 데이터에 반영하고 파일 업데이트
                   updated_data_manual = []
                   for i, item in enumerate(session_state.processed_visual_plan_final):
                        new_item = item.copy()
                        if 'visual' not in new_item or not isinstance(new_item['visual'], dict):
                             new_item['visual'] = {}
                        # 수동 선택 결과로 'selected_local_path' 업데이트
                        new_item['visual']['selected_local_path'] = session_state.manual_selections[i]
                        updated_data_manual.append(new_item)

                   # 업데이트된 데이터로 세션 상태 갱신
                   session_state.processed_visual_plan_final = updated_data_manual
                   # 파일에도 저장
                   try:
                        with open(visual_plan_final_filepath, 'w', encoding='utf-8') as outfile:
                             json.dump(updated_data_manual, outfile, indent=2, ensure_ascii=False)
                        st.success(f"✅ 수동 선택 결과 저장 완료: `{visual_plan_final_filepath}`")
                   except Exception as e:
                        st.error(f"❌ 수동 선택 결과 파일 저장 중 오류 발생: {e}")
                   # 저장 후 다음 단계 버튼 활성화 등을 위해 rerun
                   st.rerun()

         # 다음 단계(영상 제작) 버튼 또는 자동 이동
         next_step_number = get_next_step_number(workflow_definition, session_state.current_step)
         if next_step_number:
              if session_state.mode == 'AUTO':
                   st.info("➡️ AUTO 모드: 다음 단계(영상 제작)로 자동 이동합니다...")
                   time.sleep(1)
                   session_state.current_step = next_step_number
                   st.rerun()
              elif session_state.mode == 'MANUAL':
                   # 수동 선택 결과가 최종 데이터에 반영되었는지 확인 후 버튼 활성화
                   button_disabled = True
                   if session_state.processed_visual_plan_final and session_state.manual_selections:
                        # 간단히 manual_selections가 processed_visual_plan_final의 selected 경로와 일치하는지 확인
                        # (더 확실하게는 저장 버튼 누른 후 플래그 관리)
                        is_synced = all(
                             session_state.manual_selections[i] == item.get('visual',{}).get('selected_local_path')
                             for i, item in enumerate(session_state.processed_visual_plan_final)
                        )
                        if is_synced: button_disabled = False


                   if st.button(f"🎬 다음 단계 ({get_step_name(workflow_definition, next_step_number)}) 진행", key="goto_next_step_from_step4", disabled=button_disabled):
                        session_state.current_step = next_step_number
                        st.rerun()
                   elif button_disabled:
                        st.warning("수동 선택 결과를 먼저 '확정/저장' 버튼을 눌러 저장해주세요.")

         else: # 마지막 단계일 경우
             st.info("✅ 워크플로우의 마지막 단계(이미지 선택)입니다.")
             # 워크플로우 완료 처리 버튼 (MANUAL 모드)
             if session_state.mode == 'MANUAL':
                  if st.button("🏁 워크플로우 완료", key="complete_workflow_step4"):
                       complete_workflow_manual_mode(session_state, channels_root_dir)


# --- Helper functions (step_3_image_plan.py에서 가져옴) ---
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
     """MANUAL 모드 워크플로우 완료 처리 (토픽 저장 및 상태 초기화)"""
     try:
          from functions import topic_utils
          mark_topic_used_and_save = topic_utils.mark_topic_used_and_save
     except ImportError:
          st.error("❌ 오류: 토픽 유틸리티 함수를 로드할 수 없어 완료 처리를 할 수 없습니다.")
          return

     if session_state.selected_workflow_topic and session_state.channel_topics:
          st.info(f"토픽 '{session_state.selected_workflow_topic.get('TOPIC', '제목 없음')}'을 사용 완료로 표시하고 저장합니다.")
          save_success = mark_topic_used_and_save(
              channels_root_dir,
              session_state.selected_channel_name,
              session_state.selected_workflow_topic.get("TOPIC"),
              session_state.channel_topics
          )
          if save_success:
               st.success("🎉 워크플로우 완료! Topics.json 파일 업데이트 완료.")
               # 관련 세션 상태 초기화
               session_state.selected_workflow_topic = None
               session_state.channel_topics = None
               session_state.generated_script_data = None
               session_state.current_episode_info = None
               if 'generated_visual_plan' in session_state:
                    session_state.generated_visual_plan = None
               if 'processed_visual_plan_final' in session_state:
                    session_state.processed_visual_plan_final = None
               if 'image_processing_triggered' in session_state:
                    session_state.image_processing_triggered = False
               if 'manual_selections' in session_state:
                    session_state.manual_selections = None
               session_state.current_workflow_name = None
               st.session_state.current_step = 1
               session_state.current_view = 'welcome'
               st.rerun()
          else:
               st.error("❌ Topics.json 파일 업데이트 실패.")
     else:
          st.warning("⚠️ 완료할 토픽 정보가 없거나 토픽 목록이 로드되지 않았습니다.")