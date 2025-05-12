# workflows/workflow_basic/step_1_topic.py
import streamlit as st
import json
import os
import random
import time # 스피너 등 사용 시 필요

# --- functions/topic_utils.py에서 헬퍼 함수 임포트 ---
try:
    # app.py에서 sys.path 설정 가정하고 절대 경로 임포트
    from functions import topic_utils
    load_topics = topic_utils.load_topics
    save_topics = topic_utils.save_topics
    mark_topic_used_and_save = topic_utils.mark_topic_used_and_save
    select_auto_topic = topic_utils.select_auto_topic
    # 병합 함수 추가 (topic_utils.py에 merge_topics 함수가 있다고 가정)
    try:
        merge_topics = topic_utils.merge_topics
        merge_logic_available = True
    except AttributeError:
        st.warning("⚠️ 토픽 병합 함수(merge_topics)를 topic_utils.py에서 찾을 수 없습니다. 중복 토픽이 발생할 수 있습니다.")
        merge_topics = lambda l1, l2: (l1 + l2, len(l2) if isinstance(l2, list) else 0) # 간단 병합 더미
        merge_logic_available = False
except ImportError:
    st.error("❌ 오류: 토픽 유틸리티 함수(topic_utils.py)를 로드할 수 없습니다.")
    # 더미 함수 설정
    load_topics, save_topics, mark_topic_used_and_save, select_auto_topic = (lambda *a, **k: None,) * 4
    merge_topics = lambda l1, l2: (l1 + l2, len(l2) if isinstance(l2, list) else 0) # 간단한 병합 더미
    merge_logic_available = False


# --- functions/topic_generation.py에서 자동 생성 함수 임포트 ---
try:
    from functions import topic_generation
    generate_new_topics_func = topic_generation.generate_new_topics
    topic_generation_available = True
except ImportError:
    st.warning("⚠️ 자동 토픽 생성 기능(topic_generation.py)을 로드할 수 없습니다.")
    generate_new_topics_func = lambda *a, **k: (False, "자동 생성 기능을 로드할 수 없습니다.") # 더미 함수
    topic_generation_available = False

# --- functions/script_generation.py에서 API 키 가져오기 ---
# 스크립트 생성 모듈에서 이미 로드된 API 키를 사용
try:
    from functions import script_generation
    google_api_key = script_generation.GOOGLE_API_KEY
except ImportError:
    google_api_key = None # 스크립트 생성 모듈 없으면 API 키도 없음


# --- 1단계 렌더링 함수 ---
def render_step(session_state, channels_root_dir, episode_info, workflow_definition):
    """
    워크플로우의 1단계 (토픽 생성 및 선정) 페이지를 렌더링합니다.

    Args:
        session_state: Streamlit session_state
        channels_root_dir: 채널 루트 디렉토리 경로
        episode_info: 현재 에피소드 정보 (1단계에서는 보통 None).
        workflow_definition: 현재 워크플로우의 전체 정의 딕셔너리.
    """
    st.write("여기에 **1단계**: 영상 아이디어 생성 및 스크립트 작성 관련 UI 요소가 들어갑니다.")
    # 1단계에서는 에피소드 ID가 아직 확정되지 않았으므로 '미정' 표시
    st.caption(f"에피소드 ID: `{episode_info.get('episode_id') if episode_info else '미정'}`")


    TOPICS_FILENAME = "Topics.json"
    GENERATED_TOPICS_FILENAME = "generated_topics.json" # 새로 생성된 토픽 저장 파일명
    TOPIC_GEN_DB_FILENAME = "topic_gen_temp.db" # 토픽 생성 시 사용할 임시 DB 파일명

    # 현재 선택된 채널 경로 구성
    current_channel_path = os.path.join(channels_root_dir, session_state.selected_channel_name)
    current_channel_topics_path = os.path.join(current_channel_path, TOPICS_FILENAME)
    generated_topics_output_path = os.path.join(current_channel_path, GENERATED_TOPICS_FILENAME)
    topic_gen_db_path = os.path.join(current_channel_path, TOPIC_GEN_DB_FILENAME)

    # --- 토픽 데이터 로드 (세션 상태에 없으면) ---
    # load_topics 함수는 이제 ID를 자동으로 부여하고 파일을 업데이트할 수 있음
    if 'channel_topics' not in session_state or session_state.channel_topics is None:
        st.info(f"파일에서 토픽 데이터를 로드합니다: `{TOPICS_FILENAME}`")
        session_state.channel_topics = load_topics(channels_root_dir, session_state.selected_channel_name)
        if session_state.channel_topics is None:
             st.error(f"❌ 토픽 데이터 로드 실패. 채널 '{session_state.selected_channel_name}'의 `{TOPICS_FILENAME}` 확인 필요.")
             if st.button("⚙️ 채널 설정에서 Topics 파일 확인", key="goto_settings_from_step1_load_error"):
                  session_state.current_view = 'channel_settings'
                  st.rerun()
             return

    # --- 토픽 데이터 로드 상태 확인 후 진행 ---
    if session_state.channel_topics is not None:

        # 로드된 전체 토픽 수 및 사용 상태 요약 표시
        total_topics = len(session_state.channel_topics)
        used_count = sum(1 for topic in session_state.channel_topics if topic.get("USED") is True)
        unused_count = total_topics - used_count
        st.write(f"📊 전체 토픽: {total_topics}개 | 사용됨: {used_count}개 | 사용 가능: {unused_count}개")

        # 현재 선택된 토픽 표시 (ID 포함)
        if session_state.selected_workflow_topic:
             selected_topic_obj = session_state.selected_workflow_topic
             st.write(f"✨ **선정된 토픽:** '{selected_topic_obj.get('TOPIC', '제목 없음')}' (ID: `{selected_topic_obj.get('topic_id', 'N/A')}`)")

        # --- 모드별 UI 분기 ---
        if session_state.mode == 'MANUAL':
            st.subheader("수동 토픽 생성 및 선정")

            # --- 토픽 생성 섹션 ---
            with st.container(border=True):
                st.write("▶️ **토픽 생성:**")
                if not topic_generation_available:
                    st.warning("자동 토픽 생성 기능을 사용할 수 없습니다. (topic_generation.py 로드 실패)")
                elif not google_api_key:
                    st.error("자동 토픽 생성을 위한 Google API Key가 설정되지 않았습니다.")
                else:
                    num_to_generate = st.number_input(
                        "자동으로 생성할 새 토픽 개수:", min_value=1, max_value=10, value=3, step=1,
                        key="num_topics_to_generate_input"
                    )
                    if st.button(f"🤖 새 토픽 {num_to_generate}개 자동 생성 (LLM)", key="manual_generate_topic_button"):
                        with st.spinner(f"{num_to_generate}개의 새 토픽 생성 중... 시간이 걸릴 수 있습니다."):
                            success, message = generate_new_topics_func(
                                api_key=google_api_key,
                                num_topics_to_generate=num_to_generate,
                                db_file_path=topic_gen_db_path, # 채널 폴더 내 임시 DB 사용
                                output_json_path=generated_topics_output_path # 채널 폴더 내 결과 파일
                            )

                        if success:
                            st.success(f"✅ {message}")
                            st.info("생성된 토픽을 기존 목록과 병합합니다...")
                            try:
                                newly_generated_topics = []
                                if os.path.exists(generated_topics_output_path):
                                    with open(generated_topics_output_path, 'r', encoding='utf-8') as f:
                                        newly_generated_topics = json.load(f)
                                    # 임시 생성 파일 삭제 (선택적)
                                    try: os.remove(generated_topics_output_path)
                                    except OSError: pass

                                if isinstance(newly_generated_topics, list):
                                    current_topics = session_state.channel_topics
                                    # 병합 (topic_utils.merge_topics 사용)
                                    merged_topics, added_count = merge_topics(current_topics, newly_generated_topics)

                                    if added_count > 0:
                                        st.write(f"➡️ 기존 목록에 새로운 토픽 {added_count}개를 추가했습니다.")
                                        # 최종 병합된 목록 저장
                                        if save_topics(channels_root_dir, session_state.selected_channel_name, merged_topics):
                                            st.success(f"✅ 병합된 토픽 목록을 `{TOPICS_FILENAME}`에 저장했습니다.")
                                            # 세션 상태 업데이트 및 새로고침
                                            session_state.channel_topics = merged_topics # 업데이트
                                            session_state.selected_workflow_topic = None # 선택 초기화
                                            st.rerun() # UI 새로고침
                                        else:
                                            st.error("❌ 병합된 토픽 목록 저장에 실패했습니다.")
                                    else:
                                        st.info("ℹ️ 생성된 토픽이 이미 모두 존재하거나 유효하지 않아 추가된 항목이 없습니다.")
                                else:
                                    st.error("❌ 생성된 토픽 파일 형식이 잘못되었습니다 (리스트가 아님).")
                            except Exception as e:
                                st.error(f"❌ 생성된 토픽 병합 중 오류 발생: {e}")
                                st.exception(e) # 디버깅 위해 전체 오류 출력
                        else: # 생성 실패
                            st.error(f"❌ 자동 토픽 생성 실패: {message}")

            st.markdown("---")

            # --- 토픽 선정 섹션 ---
            with st.container(border=True):
                st.write("▶️ **토픽 선정:** 아래 목록에서 작업할 토픽을 직접 선택하세요.")
                if session_state.channel_topics:
                    # 라디오 버튼 옵션: (표시 텍스트, topic_id) 튜플 리스트
                    topic_options = []
                    for topic in session_state.channel_topics:
                        topic_id = topic.get("topic_id")
                        if topic_id: # ID가 있는 토픽만 옵션에 추가
                            # ID를 표시 텍스트에 포함 (선택 사항)
                            # display_text = f"[{'USED' if topic.get('USED') else 'UNUSED'}] {topic.get('TOPIC', '제목 없음')} (ID: ...{topic_id[-4:]})"
                            display_text = f"[{'USED' if topic.get('USED') else 'UNUSED'}] {topic.get('TOPIC', '제목 없음')}"
                            topic_options.append((display_text, topic_id))
                        else:
                            # ID가 없는 데이터 경고 (이론상 load_topics에서 처리됨)
                             st.warning(f"토픽 '{topic.get('TOPIC')}'에 ID가 없습니다. 목록에서 제외됩니다.")

                    if topic_options:
                        # 현재 선택된 토픽 ID 찾기
                        current_selected_id = session_state.selected_workflow_topic.get("topic_id") if session_state.selected_workflow_topic else None
                        # 현재 ID에 해당하는 인덱스 찾기
                        default_index = 0
                        if current_selected_id:
                             try: default_index = next(i for i, (_, tid) in enumerate(topic_options) if tid == current_selected_id)
                             except StopIteration: default_index = 0

                        # 라디오 버튼 값으로 topic_id 사용
                        selected_topic_id = st.radio(
                             "토픽 목록 (클릭하여 선택):",
                             options=[tid for _, tid in topic_options], # topic_id 리스트 전달
                             index=default_index,
                             format_func=lambda tid: next((disp for disp, topicid in topic_options if topicid == tid), tid), # 표시 텍스트 함수
                             key="manual_topic_id_selection_radio"
                        )

                        # 선택된 ID로 전체 토픽 객체 찾기
                        manual_selected_topic_obj = next((t for t in session_state.channel_topics if t.get("topic_id") == selected_topic_id), None)

                        if manual_selected_topic_obj:
                             # 선택된 토픽 상세 정보 표시
                             st.write("---"); st.write("**선택된 토픽 상세:**")
                             st.write(f"- 제목: {manual_selected_topic_obj.get('TOPIC', 'N/A')}")
                             st.write(f"- ID: `{manual_selected_topic_obj.get('topic_id', 'N/A')}`") # ID 표시
                             st.write(f"- 사용 여부: {'사용됨' if manual_selected_topic_obj.get('USED') else '사용 가능'}")
                             keywords = manual_selected_topic_obj.get('keyword', [])
                             st.write("- 키워드:", ", ".join(keywords) if isinstance(keywords, list) else "(형식 오류)")
                             st.write("- 상세 내용:")
                             details = manual_selected_topic_obj.get('DETAIL', [])
                             if isinstance(details, list):
                                 for detail in details or ["상세 내용 없음"]: st.write(f"  - {detail}")
                             else: st.write("  - 상세 내용 (형식 오류)")

                             # 세션 상태에 전체 토픽 객체 저장 (ID 포함)
                             session_state.selected_workflow_topic = manual_selected_topic_obj
                        else:
                             st.warning("⚠️ 선택된 ID의 토픽 데이터를 찾을 수 없습니다.")
                    else:
                        st.warning(f"⚠️ `{TOPICS_FILENAME}`에 유효한 토픽(ID 포함)이 없습니다.")
                else:
                    st.warning(f"⚠️ 로드된 토픽이 없습니다. 토픽 생성 기능을 사용하거나 `{TOPICS_FILENAME}` 파일을 확인하세요.")


        elif session_state.mode == 'AUTO':
            st.subheader("자동 토픽 선정")

            # AUTO 모드 토픽 생성 조건 체크 (사용 가능한 토픽 0개일 때)
            unused_count = sum(1 for topic in session_state.channel_topics if topic.get("USED") is False)
            if unused_count == 0:
                st.info("ℹ️ 사용 가능한 토픽이 없습니다. AUTO 모드 토픽 생성을 시도합니다.")
                if not topic_generation_available or not google_api_key:
                    st.error("❌ AUTO 모드 토픽 생성을 위한 기능 또는 API 키가 없어 중단합니다.")
                    if st.button("⚙️ 채널 설정/API 키 확인", key="auto_topic_gen_fail_settings"):
                        session_state.current_view = 'channel_settings'
                        st.rerun()
                    return # 중단

                num_auto_generate = 3 # AUTO 모드에서 생성할 기본 개수
                st.info(f"🤖 새 토픽 {num_auto_generate}개 자동 생성 시도...")
                with st.spinner(f"{num_auto_generate}개의 새 토픽 생성 중..."):
                     success, message = generate_new_topics_func(
                         api_key=google_api_key,
                         num_topics_to_generate=num_auto_generate,
                         db_file_path=topic_gen_db_path,
                         output_json_path=generated_topics_output_path
                     )
                if success:
                    st.success(f"✅ {message}")
                    # 생성 성공 후 병합 및 재로드 (MANUAL 모드와 동일 로직)
                    try:
                        newly_generated_topics = []
                        if os.path.exists(generated_topics_output_path):
                            with open(generated_topics_output_path, 'r', encoding='utf-8') as f:
                                newly_generated_topics = json.load(f)
                            try: os.remove(generated_topics_output_path)
                            except OSError: pass
                        if isinstance(newly_generated_topics, list):
                            current_topics = session_state.channel_topics
                            merged_topics, added_count = merge_topics(current_topics, newly_generated_topics)
                            if added_count > 0:
                                if save_topics(channels_root_dir, session_state.selected_channel_name, merged_topics):
                                     st.success(f"✅ {added_count}개 토픽 추가 후 저장 완료. AUTO 모드 재시작...")
                                     session_state.channel_topics = merged_topics # 업데이트
                                     session_state.selected_workflow_topic = None # 선택 초기화
                                     st.rerun() # 재실행하여 자동 선정 로직 다시 타도록 함
                                else: st.error("❌ 병합된 토픽 목록 저장 실패. AUTO 모드 중단.") ; return
                            else: st.info("ℹ️ 생성된 토픽이 이미 존재하거나 유효하지 않음. AUTO 모드 중단."); return
                        else: st.error("❌ 생성된 토픽 파일 형식 오류. AUTO 모드 중단."); return
                    except Exception as e: st.error(f"❌ 생성 토픽 병합 오류: {e}. AUTO 모드 중단."); return
                else:
                    st.error(f"❌ AUTO 모드 토픽 생성 실패: {message}. AUTO 모드 중단.")
                    return # 중단
            else: # unused_count > 0, 자동 선정 진행
                with st.container(border=True):
                    st.write("▶️ **토픽 선정:** 설정된 전략에 따라 자동으로 토픽을 선정합니다.")
                    # 아직 토픽이 선택되지 않았을 때만 자동 선정 시도
                    if session_state.selected_workflow_topic is None:
                        st.info("⏳ 사용 가능한 토픽 중에서 자동으로 하나를 선정합니다...")
                        auto_selected_topic_obj = select_auto_topic(
                            session_state.channel_topics,
                            session_state.get('auto_topic_selection_strategy', 'FIFO (가장 오래된 항목 먼저)')
                        )
                        if auto_selected_topic_obj:
                            session_state.selected_workflow_topic = auto_selected_topic_obj
                            topic_id_to_mark = auto_selected_topic_obj.get("topic_id") # ID 가져오기
                            if topic_id_to_mark: # ID가 있을 때만 진행
                                st.info(f"✅ 토픽 '{auto_selected_topic_obj.get('TOPIC')}' (ID: {topic_id_to_mark}) 선정 및 USED 표시/저장 시도...")
                                save_success = mark_topic_used_and_save(
                                    channels_root_dir,
                                    session_state.selected_channel_name,
                                    topic_id_to_mark, # ID 전달
                                    session_state.channel_topics # 전체 토픽 리스트 전달
                                )
                                if save_success:
                                    st.success("✅ Topics.json 업데이트 완료.")
                                    st.info("➡️ 다음 단계(스크립트 생성)로 자동으로 진행합니다...")
                                    # 다음 단계 번호 찾기 및 이동
                                    next_step_num = get_next_step_number(workflow_definition, session_state.current_step)
                                    if next_step_num:
                                        session_state.current_step = next_step_num
                                        # episode_info는 다음 단계에서 생성됨
                                        st.rerun()
                                    else:
                                        st.warning("워크플로우 정의에 다음 단계 정보가 없습니다.")
                                else:
                                    st.error("❌ Topics.json 파일 업데이트 실패. AUTO 모드 중단.")
                                    session_state.selected_workflow_topic = None # 실패 시 선택 취소
                            else:
                                 st.error("❌ 선정된 토픽에 ID가 없습니다. AUTO 모드 중단.")
                                 session_state.selected_workflow_topic = None
                        else:
                            st.warning("⚠️ AUTO 모드에서 선정 가능한 토픽이 없습니다. (모두 사용되었거나 오류)")
                            if st.button("⚙️ 채널 설정에서 Topics 파일 확인", key="auto_no_topic_goto_settings"):
                                session_state.current_view = 'channel_settings'
                                st.rerun()
                    else:
                         # 이미 토픽이 선정되어 있는 경우 (이전 Rerun에서 다음 단계로 이동 완료됨)
                         selected_topic_obj = session_state.selected_workflow_topic
                         st.info(f"✨ 이미 토픽 선정됨: '{selected_topic_obj.get('TOPIC')}' (ID: {selected_topic_obj.get('topic_id')}) (다음 단계 진행 대기)")

        st.markdown("---")

        # --- 1단계 공통: 토픽 데이터 관리 UI ---
        st.subheader("토픽 데이터 관리")
        st.write(f"현재 채널의 `{TOPICS_FILENAME}` 파일을 직접 편집합니다.")
        st.caption(f"파일 경로: `{current_channel_topics_path}`")

        with st.expander("📊 로드된 토픽 데이터 (JSON 형식 보기/편집)", expanded=False):
             if session_state.channel_topics is not None:
                  topics_editor_key = f"topics_editor_{session_state.selected_channel_name}"
                  # topic_utils.load_topics/save_topics에서 ID 부여/확인을 하므로
                  # 편집기 내용은 최신 상태의 ID 포함 데이터를 보여줌
                  current_topics_json_string = json.dumps(session_state.channel_topics, indent=2, ensure_ascii=False)
                  initial_editor_value = session_state.get(topics_editor_key, current_topics_json_string)

                  # JSON 편집기 (streamlit-ace 사용 가능 시) 또는 text_area
                  # (st_ace 사용 로직은 channel_settings_view.py 참조하여 추가 가능)
                  edited_topics_json_string = st.text_area(
                      f"'{TOPICS_FILENAME}' 편집:", initial_editor_value, height=300, key=topics_editor_key
                  )

                  button_disabled_save_topics = edited_topics_json_string == current_topics_json_string

                  if st.button(f"💾 '{TOPICS_FILENAME}' 저장", disabled=button_disabled_save_topics, key="save_topics_button"):
                       try:
                            parsed_topics = json.loads(edited_topics_json_string)
                            if isinstance(parsed_topics, list):
                                 # save_topics 함수는 내부적으로 ID 부여/확인 로직 포함
                                 if save_topics(channels_root_dir, session_state.selected_channel_name, parsed_topics):
                                      st.success(f"✅ `{TOPICS_FILENAME}` 저장 완료.")
                                      # 저장 후 세션 상태 업데이트 및 UI 새로고침
                                      session_state.channel_topics = load_topics(channels_root_dir, session_state.selected_channel_name) # ID 포함하여 다시 로드
                                      session_state.selected_workflow_topic = None
                                      # 편집기 내용도 업데이트
                                      session_state[topics_editor_key] = json.dumps(session_state.channel_topics, indent=2, ensure_ascii=False)
                                      st.rerun()
                                 else: st.error("❌ 파일 저장 실패.")
                            else: st.error("❌ JSON 데이터가 리스트여야 함.")
                       except json.JSONDecodeError: st.error("❌ 유효한 JSON 아님.")
                       except Exception as e: st.error(f"❌ 저장 중 오류: {e}")
             else:
                  st.error("❌ 토픽 데이터 로드 불가.")

    # 로드 실패 시
    elif session_state.channel_topics is None:
        st.error("❌ 토픽 데이터를 로드할 수 없습니다. 채널 설정을 확인하거나 Topics.json 파일을 채널 디렉토리에 추가해 주세요.")
        if st.button("⚙️ 채널 설정으로 이동", key="goto_settings_from_topic_error_fallback"):
             session_state.current_view = 'channel_settings'
             st.rerun()

    # --- MANUAL 모드 다음 단계 이동 버튼 ---
    if session_state.mode == 'MANUAL':
        next_step_num = get_next_step_number(workflow_definition, session_state.current_step)
        if next_step_num is not None:
            st.markdown("---")
            next_step_name = get_step_name(workflow_definition, next_step_num)
            if st.button(f"➡️ 다음 단계 ({next_step_name}) 진행",
                         disabled=(session_state.selected_workflow_topic is None), # 토픽 선택 필수
                         key="manual_goto_next_step_from_step1"):
                 # 다음 단계로 이동 (episode_info 생성은 workflow_view에서 처리)
                 session_state.current_step = next_step_num
                 st.rerun()
        else: # 다음 단계가 없을 경우
             st.info("✅ 워크플로우 정의에 다음 단계 정보 없음.")


# --- Helper Functions ---
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