# PaMin/workflows/workflow_basic/step_3_image_plan.py
import streamlit as st
import json
import os
import time # To prevent rapid reruns in AUTO mode if needed

# --- functions/visual_generation.py에서 백엔드 함수 임포트 ---
try:
    from functions import visual_generation
    generate_visual_plan_func = visual_generation.generate_visual_plan_from_json_file
    load_prompt_func = visual_generation.load_prompt_from_file # 프롬프트 로드 함수도 임포트
    visual_generation_available = True
except ImportError:
    st.error("❌ 오류: 시각 자료 생성 백엔드 모듈(visual_generation.py)을 로드할 수 없습니다.")
    generate_visual_plan_func = lambda *args, **kwargs: [] # Dummy function
    load_prompt_func = lambda *args: None # Dummy function
    visual_generation_available = False

# --- streamlit-ace 임포트 (app.py에서 전달받아야 함) ---
# 이 파일에서는 직접 임포트하지 않고, app.py에서 확인된 모듈을 사용한다고 가정합니다.
# render_step 함수 시그니처에 st_ace_module 및 json_editor_available 추가 필요
# def render_step(session_state, channels_root_dir, episode_info, workflow_definition, st_ace_module, json_editor_available):

# --- 3단계(시각 자료 계획 생성) 렌더링 함수 ---
# TODO: app.py에서 이 함수를 호출할 때 st_ace_module, json_editor_available 인자를 추가해야 합니다.
# 임시로 함수 내에서 사용 가능 여부를 체크하는 방식으로 작성 (추후 수정 필요)
def render_step(session_state, channels_root_dir, episode_info, workflow_definition):
    """
    워크플로우의 3단계 (시각 자료 계획 생성) 페이지를 렌더링합니다.

    Args:
        session_state: Streamlit session_state
        channels_root_dir: 채널 루트 디렉토리 경로
        episode_info: 현재 에피소드 정보를 담은 딕셔너리 {"episode_id": "...", "episode_path": "..."}
        workflow_definition: 현재 워크플로우의 전체 정의 딕셔너리 (workflow.json 내용)
    """
    st.write("여기에 **3단계**: 스크립트 기반 시각 자료 계획 생성 UI 요소가 들어갑니다.")
    st.caption(f"에피소드 ID: `{episode_info.get('episode_id', 'N/A')}`")

    # --- 백엔드 기능 가용성 확인 ---
    if not visual_generation_available:
        st.error("❌ 시각 자료 생성 기능을 사용할 수 없습니다. 관리자에게 문의하세요.")
        # 여기서 중단하거나, 이전 단계로 돌아가는 버튼 제공
        if st.button("↩️ 2단계로 돌아가기", key="back_to_step2_from_step3_no_backend"):
             session_state.current_step = 2 # 이전 단계 번호 (하드코딩보다는 workflow_definition 기반이 좋음)
             st.rerun()
        return

    # --- 필요한 입력 데이터 확인 ---
    # 1. 이전 단계(스크립트 생성) 결과 확인
    script_data_stage2 = session_state.get('generated_script_data')
    if not script_data_stage2 or not script_data_stage2.get('segments'):
        st.warning("⚠️ 이전 단계(스크립트 생성) 결과가 없습니다. 2단계부터 다시 진행해주세요.")
        if st.button("↩️ 2단계로 돌아가기", key="back_to_step2_from_step3_no_script"):
            session_state.current_step = 2
            # 생성된 시각 자료 계획도 초기화
            if 'generated_visual_plan' in session_state:
                 session_state.generated_visual_plan = None
            st.rerun()
        return

    # 2. 에피소드 경로 확인
    episode_path = episode_info.get('episode_path')
    if not episode_path or not os.path.isdir(episode_path):
         st.error(f"❌ 오류: 에피소드 경로를 찾을 수 없거나 유효하지 않습니다: {episode_path}")
         # 복구 어려움. 워크플로우 재시작 유도
         if st.button("🔄 워크플로우 재시작 (1단계로)", key="restart_workflow_from_step3_no_path"):
              session_state.current_step = 1
              session_state.selected_workflow_topic = None
              session_state.generated_script_data = None
              session_state.current_episode_info = None
              if 'generated_visual_plan' in session_state:
                   session_state.generated_visual_plan = None
              st.rerun()
         return

    # 3. 스크립트 JSON 파일 경로 및 프롬프트 파일 경로 설정
    # step_2_script.py에서 저장한 파일명을 기반으로 경로 구성
    script_json_filename = f"script_stage2_{episode_info.get('episode_id')}.json"
    script_json_filepath = os.path.join(episode_path, script_json_filename)

    # 프롬프트 파일 경로 구성
    prompt_filename = "visual_planner_prompt.txt" # 고정된 파일명 사용
    prompt_filepath = os.path.join(channels_root_dir, session_state.selected_channel_name, "prompt", prompt_filename)

    # 입력 파일 존재 여부 확인
    if not os.path.exists(script_json_filepath):
         st.error(f"❌ 오류: 시각 자료 생성을 위한 스크립트 파일(Stage 2)을 찾을 수 없습니다: `{script_json_filepath}`")
         st.warning("2단계를 다시 실행하여 스크립트 파일을 생성해주세요.")
         if st.button("↩️ 2단계로 돌아가기", key="back_to_step2_from_step3_no_script_file"):
              session_state.current_step = 2
              if 'generated_visual_plan' in session_state:
                   session_state.generated_visual_plan = None
              st.rerun()
         return
    if not os.path.exists(prompt_filepath):
         st.error(f"❌ 오류: 시각 자료 생성을 위한 프롬프트 파일을 찾을 수 없습니다: `{prompt_filepath}`")
         st.warning(f"채널 폴더 내 'prompt' 디렉토리에 '{prompt_filename}' 파일을 생성해주세요.")
         # 프롬프트 편집 기능을 제공하므로 일단 진행은 가능하게 둘 수 있음 (MANUAL 모드)
         # AUTO 모드는 여기서 중단 필요
         if session_state.mode == 'AUTO':
              st.error("AUTO 모드는 프롬프트 파일 없이는 진행할 수 없습니다.")
              # 워크플로우 중단 또는 사용자 개입 유도
              return


    # --- 시각 자료 계획 생성 로직 ---
    # 세션 상태에 계획이 없으면 생성 시도
    if 'generated_visual_plan' not in session_state or session_state.generated_visual_plan is None:
        if session_state.mode == 'AUTO':
            st.info("⏳ AUTO 모드: 시각 자료 계획을 자동으로 생성합니다...")
            with st.spinner("LLM 호출 및 시각 자료 계획 생성 중..."):
                visual_plan = generate_visual_plan_func(script_json_filepath, prompt_filepath)
                session_state.generated_visual_plan = visual_plan # 결과 저장
            if visual_plan:
                 st.success("✅ 시각 자료 계획 자동 생성 완료!")
                 # 결과 파일 저장
                 output_filename = os.path.join(episode_path, "visual_plan_output.json")
                 try:
                      with open(output_filename, 'w', encoding='utf-8') as outfile:
                           json.dump(visual_plan, outfile, indent=2, ensure_ascii=False)
                      st.info(f"💾 생성된 계획 저장 완료: `{output_filename}`")
                 except Exception as e:
                      st.warning(f"⚠️ 계획 파일 저장 중 오류 발생: {e}")

                 # AUTO 모드는 성공 시 다음 단계로 자동 이동
                 # 다음 단계 번호 찾기
                 next_step_number = get_next_step_number(workflow_definition, session_state.current_step)
                 if next_step_number:
                      st.info("➡️ 다음 단계로 자동 이동합니다...")
                      time.sleep(1) # 메시지 확인 시간
                      session_state.current_step = next_step_number
                      st.rerun()
                 else:
                      st.info("✅ 워크플로우의 마지막 단계입니다. (AUTO 모드 완료)")
            else:
                 st.error("❌ AUTO 모드: 시각 자료 계획 생성에 실패했습니다.")
                 # AUTO 모드 실패 시 처리 (예: 중단, 알림 등)

        elif session_state.mode == 'MANUAL':
            # MANUAL 모드는 사용자가 버튼을 누를 때 생성 (아래 UI 부분에서 처리)
            st.info("MANUAL 모드: 아래 '시각 자료 계획 생성/재생성' 버튼을 눌러주세요.")

    # --- 생성된 시각 자료 계획 출력 ---
    if 'generated_visual_plan' in session_state and session_state.generated_visual_plan is not None:
          st.write("---")
          st.subheader("📊 생성된 시각 자료 계획 편집")
          st.write(f"총 {len(session_state.generated_visual_plan)}개의 Chunk에 대한 계획입니다.")

          # 변경 사항을 임시 저장할 딕셔너리 (세션 상태 활용)
          if 'edited_visual_plan' not in session_state:
              # 초기 로드 시 원본 계획 복사
              session_state.edited_visual_plan = [item.copy() for item in session_state.generated_visual_plan]
          elif len(session_state.edited_visual_plan) != len(session_state.generated_visual_plan):
               # 원본 계획의 길이가 변경된 경우 (재생성 등) 편집본도 동기화
               session_state.edited_visual_plan = [item.copy() for item in session_state.generated_visual_plan]


          # 각 Chunk 편집 UI 생성
          for i, chunk_data in enumerate(session_state.edited_visual_plan):
              st.markdown("---")
              st.markdown(f"**Chunk {i+1}**")

              # Chunk Text 표시 (수정 불필요 시 st.markdown 또는 st.text 사용)
              # chunk_text_key = f"chunk_text_display_{i}" # 키는 필요 없을 수 있음
              st.text_area(f"Chunk Text:", value=chunk_data.get("chunk_text", ""), key=f"chunk_text_area_{i}", disabled=True, height=70)

              # Visual Type 편집 (Selectbox 사용)
              visual_types = ['meme', 'reference', 'generation']
              current_type = chunk_data.get("visual", {}).get("type", visual_types[0])
              # 현재 타입이 visual_types 리스트에 없으면 첫 번째 옵션으로 강제
              if current_type not in visual_types:
                  current_type = visual_types[0]
                  # session_state.edited_visual_plan[i]['visual']['type'] = current_type # 필요시 즉시 반영

              type_key = f"chunk_type_select_{i}"
              new_type = st.selectbox(
                  "Visual Type:",
                  options=visual_types,
                  index=visual_types.index(current_type), # 현재 값으로 기본 선택
                  key=type_key
              )
              # 변경 시 임시 저장 데이터 업데이트
              session_state.edited_visual_plan[i]['visual']['type'] = new_type


              # Visual Query 편집 (Text Input 사용)
              query_key = f"chunk_query_input_{i}"
              current_query = chunk_data.get("visual", {}).get("query", "")
              new_query = st.text_input(
                  "Visual Query:",
                  value=current_query,
                  key=query_key
              )
              # 변경 시 임시 저장 데이터 업데이트
              session_state.edited_visual_plan[i]['visual']['query'] = new_query

              # (선택 사항) Chunk 삭제 버튼
              # if st.button("🗑️ 이 Chunk 삭제", key=f"delete_chunk_{i}"):
              #     del session_state.edited_visual_plan[i]
              #     st.rerun()

          # (선택 사항) Chunk 추가 버튼
          # if st.button("➕ Chunk 추가", key="add_chunk_button"):
          #      session_state.edited_visual_plan.append({"chunk_text": "새 Chunk 내용", "visual": {"type": "meme", "query": ""}, "segment": {"index": -1, "type": "new"}})
          #      st.rerun()


          # 변경 사항 저장 버튼
          st.markdown("---")
          if st.button("💾 **수정된 시각 자료 계획 저장**", key="save_edited_plan"):
              # 임시 편집본(edited_visual_plan)을 실제 계획(generated_visual_plan)에 반영
              session_state.generated_visual_plan = [item.copy() for item in session_state.edited_visual_plan]

              # 파일에도 저장
              output_filename = os.path.join(episode_path, "visual_plan_output.json")
              try:
                  with open(output_filename, 'w', encoding='utf-8') as outfile:
                      json.dump(session_state.generated_visual_plan, outfile, indent=2, ensure_ascii=False)
                  st.success(f"✅ 수정된 계획 저장 완료: `{output_filename}`")
              except Exception as e:
                  st.error(f"❌ 수정된 계획 파일 저장 중 오류 발생: {e}")
              # 저장 후 rerun하여 UI 업데이트 (선택 사항, 저장 성공 메시지만으로 충분할 수도 있음)
              # st.rerun()
    # --- MANUAL 모드 추가 기능 ---
    if session_state.mode == 'MANUAL':
        st.write("---")
        st.subheader("🔧 MANUAL 모드 옵션")

        # 1. 프롬프트 수정 기능
        with st.expander("📝 프롬프트 내용 보기/수정", expanded=False):
             current_prompt_content = load_prompt_func(prompt_filepath)
             if current_prompt_content is None:
                  current_prompt_content = "프롬프트 파일을 찾을 수 없습니다. 파일을 생성하거나 경로를 확인하세요."
                  st.error(current_prompt_content)

             # st_ace 사용 가능 여부 확인 (app.py 로직 필요)
             # 임시로 직접 체크
             try:
                  import streamlit_ace as st_ace
                  json_editor_available = True
                  st_ace_module = st_ace
             except ImportError:
                  json_editor_available = False
                  st_ace_module = None

             # editor_key = f"prompt_editor_{session_state.selected_channel_name}" # 고유 키 사용
             if json_editor_available and st_ace_module:
                  edited_prompt = st_ace_module.st_ace(
                      current_prompt_content,
                      language="text", # 일반 텍스트
                      theme="github",
                      height=300,
                      key="manual_prompt_editor_ace" # 위젯 키
                  )
             else:
                  if not json_editor_available:
                       st.warning("⚠️ JSON 편집기(streamlit-ace) 미설치. 기본 텍스트 영역 사용.")
                  edited_prompt = st.text_area(
                      "프롬프트 수정:",
                      current_prompt_content,
                      height=300,
                      key="manual_prompt_editor_text" # 위젯 키
                  )

             # 프롬프트 저장 버튼
             if st.button("💾 프롬프트 저장", key="save_prompt_button"):
                  try:
                       with open(prompt_filepath, 'w', encoding='utf-8') as f:
                            f.write(edited_prompt)
                       st.success(f"✅ 프롬프트 파일 저장 완료: `{prompt_filepath}`")
                       # 저장 후에는 재생성 필요 메시지 표시 또는 자동 재생성 X
                       st.info("프롬프트가 저장되었습니다. 변경사항을 적용하려면 '계획 재생성' 버튼을 누르세요.")
                  except Exception as e:
                       st.error(f"❌ 프롬프트 파일 저장 중 오류 발생: {e}")


        # 2. 재생성 버튼
        st.write("---")
        if st.button("🔄 시각 자료 계획 생성/재생성", key="regenerate_plan_button"):
            st.info("⏳ 시각 자료 계획을 생성/재생성합니다...")
            visual_plan = None # 결과 초기화
            generation_success = False # 성공 플래그
            with st.spinner("LLM 호출 및 시각 자료 계획 생성 중..."):
                try:
                    # 백엔드 함수 호출
                    visual_plan = generate_visual_plan_func(script_json_filepath, prompt_filepath)
                    if visual_plan: # 함수 호출이 성공하고 결과가 비어있지 않다면
                        generation_success = True
                    else:
                        # 함수는 성공했으나 결과가 비어있는 경우도 실패로 간주
                        st.error("❌ 시각 자료 계획 생성 결과가 비어 있습니다.")
                        generation_success = False
                except Exception as e:
                    st.error(f"❌ 시각 자료 계획 생성 중 오류 발생: {e}")
                    generation_success = False
            # --- 결과 처리 ---
            if generation_success and visual_plan:
                st.success("✅ 시각 자료 계획 생성/재생성 완료!")
                # 성공 시, 세션 상태 업데이트
                session_state.generated_visual_plan = visual_plan
                # 성공 시, 반드시 파일로 저장 (덮어쓰기)
                output_filename = os.path.join(episode_path, "visual_plan_output.json")
                try:
                    with open(output_filename, 'w', encoding='utf-8') as outfile:
                        json.dump(visual_plan, outfile, indent=2, ensure_ascii=False)
                    st.info(f"💾 생성된 계획 저장 완료: `{output_filename}`")
                    # 4단계에서 사용할 최종 처리 결과 상태는 초기화 (4단계 진입 시 다시 생성됨)
                    if 'processed_visual_plan_final' in session_state:
                        session_state.processed_visual_plan_final = None
                    if 'image_processing_triggered' in session_state:
                        session_state.image_processing_triggered = False
                    if 'manual_selections' in session_state:
                         session_state.manual_selections = None
                    st.rerun() # 성공 및 저장 후 화면 새로고침
                except Exception as e:
                    st.error(f"❌ 생성된 계획 파일 저장 중 오류 발생: {e}")
                    # 파일 저장 실패 시, 성공으로 간주하지 않도록 처리 (선택적)
                    session_state.generated_visual_plan = None # 불일치 방지 위해 세션 상태도 초기화
            elif not generation_success:
                 # 생성 실패 시, 관련 세션 상태 명시적 초기화
                 st.error("❌ 시각 자료 계획 생성/재생성에 실패했습니다.")
                 session_state.generated_visual_plan = None
                 # 실패한 경우, 이전 결과 파일 삭제 시도 (선택적)
                 # output_filename = os.path.join(episode_path, "visual_plan_output.json")
                 # if os.path.exists(output_filename):
                 #     try:
                 #         os.remove(output_filename)
                 #         st.warning("이전에 생성된 (실패 가능성 있는) 계획 파일을 삭제했습니다.")
                 #     except Exception as e:
                 #         st.warning(f"이전 계획 파일 삭제 중 오류: {e}")
                # 3. 다음 단계 이동 버튼 (계획이 생성된 경우에만 활성화)
        st.write("---")
        next_step_number = get_next_step_number(workflow_definition, session_state.current_step)
        if next_step_number:
            st.button(
                f"➡️ 다음 단계 ({get_step_name(workflow_definition, next_step_number)}) 진행",
                key="manual_goto_next_step_from_step3",
                disabled=(session_state.generated_visual_plan is None), # 계획 없으면 비활성화
                on_click=lambda: setattr(st.session_state, 'current_step', next_step_number) # 클릭 시 단계 변경
                # 버튼 클릭 시 자동으로 rerun됨
            )
        else:
             st.info("✅ 워크플로우의 마지막 단계입니다.")
             # MANUAL 모드 완료 버튼 (step_3_movie.py 에서 가져옴)
             if st.button("✅ 워크플로우 완료 (사용된 토픽 USED 표시/저장)", key="manual_complete_workflow_button_step3_plan"):
                  complete_workflow_manual_mode(session_state, channels_root_dir)


# --- Helper functions ---
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
          # topic_utils 임포트 시도 (이미 했을 수 있지만 안전하게)
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
              session_state.channel_topics # 현재 로드된 전체 토픽 목록 전달
          )
          if save_success:
               st.success("🎉 워크플로우 완료! Topics.json 파일 업데이트 완료.")
               # 워크플로우 완료 시 관련 세션 상태 초기화
               session_state.selected_workflow_topic = None
               session_state.channel_topics = None
               session_state.generated_script_data = None
               session_state.current_episode_info = None
               if 'generated_visual_plan' in session_state:
                    session_state.generated_visual_plan = None
               session_state.current_workflow_name = None
               st.session_state.current_step = 1
               session_state.current_view = 'welcome' # 메인 화면으로
               st.rerun()
          else:
               st.error("❌ Topics.json 파일 업데이트 실패.")
     else:
          st.warning("⚠️ 완료할 토픽 정보가 없거나 토픽 목록이 로드되지 않았습니다.")