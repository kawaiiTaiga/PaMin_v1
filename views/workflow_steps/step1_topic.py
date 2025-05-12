import streamlit as st
import json
import os
import random # 랜덤 선택을 위해 필요

# Step 1 렌더링 함수
# 필요한 데이터와 헬퍼 함수들을 인자로 받습니다.
# channels_root_dir만 필요하며 workflow_output_base_dir는 이 단계에서 사용하지 않습니다.
def render_step1_topic_page(session_state, channels_root_dir, load_topics_func, save_topics_func, mark_used_func, select_auto_func):
    """워크플로우의 1단계 (토픽 생성 및 선정) 페이지를 렌더링합니다."""

    st.write("여기에 **1단계**: 영상 아이디어 생성 및 스크립트 작성 관련 UI 요소가 들어갑니다.")

    # Topics.json 파일의 상대 경로 (선택된 채널 디렉토리 내)
    TOPICS_FILENAME = "Topics.json"
    current_channel_topics_path = os.path.join(channels_root_dir, session_state.selected_channel_name, TOPICS_FILENAME) # Topics.json 파일 경로

    # 1-1. 토픽 데이터 로드 (이 단계에 처음 진입했을 때만 로드)
    # 토픽 데이터는 session_state.channel_topics에 저장됩니다.
    if session_state.channel_topics is None:
        st.info(f"파일에서 토픽 데이터를 로드합니다: `{TOPICS_FILENAME}`")
        session_state.channel_topics = load_topics_func(channels_root_dir, session_state.selected_channel_name)
        # 로드 실패 시 (None 반환) 처리
        if session_state.channel_topics is None:
             st.error(f"❌ 토픽 데이터 로드에 실패했습니다. 채널 '{session_state.selected_channel_name}'의 `{TOPICS_FILENAME}` 파일을 확인해 주세요.")
             if st.button("⚙️ 채널 설정에서 Topics 파일 확인", key="goto_settings_from_step1_load_error"):
                  session_state.current_view = 'channel_settings'
                  st.rerun()
             # 로드 실패 시 여기서 더 이상 진행하지 않도록 return
             return


    # 토픽 데이터 로드 상태 확인 후 진행
    if session_state.channel_topics is not None:

        # 로드된 전체 토픽 수 및 사용 상태 요약 표시
        total_topics = len(session_state.channel_topics)
        used_count = sum(1 for topic in session_state.channel_topics if topic.get("USED") is True)
        unused_count = total_topics - used_count
        st.write(f"📊 전체 토픽: {total_topics}개 | 사용됨: {used_count}개 | 사용 가능: {unused_count}개")

        # 현재 선택된 토픽 표시 (이 단계에서 이미 선택되었다면)
        if session_state.selected_workflow_topic:
             st.write(f"✨ **선정된 토픽:** '{session_state.selected_workflow_topic.get('TOPIC', '제목 없음')}'")


        # --- 모드별 UI 분기 ---
        if session_state.mode == 'MANUAL':
            st.subheader("수동 토픽 생성 및 선정")

            # 1단계 MANUAL: 토픽 생성 (미구현)
            with st.container(border=True):
                 st.write("▶️ **토픽 생성:** (미구현) 키워드 등을 입력하여 새로운 토픽 아이디어를 생성합니다.")
                 st.info("💡 LLM을 활용한 자동 토픽 생성 기능은 아직 미구현입니다.")
                 # 예시: st.text_input("토픽 아이디어 생성 키워드")
                 # 예시: st.button("토픽 아이디어 생성", key="manual_generate_topic_button")


            st.markdown("---")

            # 1단계 MANUAL: 토픽 선정
            with st.container(border=True):
                st.write("▶️ **토픽 선정:** 아래 목록에서 작업할 토픽을 직접 선택하세요.")

                # 로드된 토픽 목록을 표 또는 라디오 버튼 등으로 표시
                if session_state.channel_topics:
                    # 사용자 선택을 받을 수 있는 UI (라디오 버튼 또는 selectbox)
                    topic_options = [f"[{'USED' if t.get('USED') else 'UNUSED'}] {t.get('TOPIC', '제목 없음')}" for t in session_state.channel_topics]

                    # 현재 session_state.selected_workflow_topic이 목록에 있다면 기본값으로 설정
                    default_index = 0
                    if session_state.selected_workflow_topic:
                         try:
                              current_topic_title = session_state.selected_workflow_topic.get('TOPIC')
                              # 제목이 일치하는 첫 번째 항목의 인덱스를 찾습니다.
                              default_index = next((i for i, t in enumerate(session_state.channel_topics) if isinstance(t, dict) and t.get('TOPIC') == current_topic_title), 0)
                         except Exception:
                              default_index = 0 # 찾지 못하면 첫 번째 항목

                    if topic_options: # 토픽 목록이 비어있지 않은 경우에만 라디오 버튼 표시
                         selected_topic_str = st.radio(
                             "토픽 목록:",
                             topic_options,
                             index=default_index,
                             key="manual_topic_selection_radio"
                         )

                         # 선택된 문자열에서 실제 토픽 객체 찾기 (인덱스 사용)
                         selected_topic_index = topic_options.index(selected_topic_str)
                         manual_selected_topic_obj = session_state.channel_topics[selected_topic_index]

                         # 선택된 토픽 정보 요약 표시
                         if manual_selected_topic_obj:
                              st.write("---")
                              st.write("**선택된 토픽 상세:**")
                              st.write(f"- 제목: {manual_selected_topic_obj.get('TOPIC', 'N/A')}")
                              st.write(f"- 사용 여부: {'사용됨' if manual_selected_topic_obj.get('USED') else '사용 가능'}")
                              keywords = manual_selected_topic_obj.get('keyword', [])
                              if isinstance(keywords, list):
                                   st.write("- 키워드:", ", ".join(keywords))
                              else:
                                   st.write("- 키워드: (형식 오류)")

                              st.write("- 상세 내용:")
                              details = manual_selected_topic_obj.get('DETAIL', [])
                              if isinstance(details, list):
                                   if details:
                                        for detail in details:
                                             st.write(f"  - {detail}")
                                   else:
                                        st.write("  - 상세 내용 없음")
                              else:
                                   st.write("  - 상세 내용 (형식 오류)")


                              # 선택된 토픽을 세션 상태에 저장
                              session_state.selected_workflow_topic = manual_selected_topic_obj
                         else:
                             st.warning("⚠️ 선택된 항목의 토픽 데이터를 찾을 수 없습니다.")


                    else: # 토픽 목록이 비어있을 경우
                        st.warning(f"⚠️ 현재 `{TOPICS_FILENAME}` 파일에 사용 가능한 토픽이 없습니다.")


                else: # session_state.channel_topics 자체가 빈 리스트인 경우
                    st.warning(f"⚠️ 로드된 토픽이 없습니다. 토픽 생성 기능을 사용하거나 채널 '{session_state.selected_channel_name}'의 `{TOPICS_FILENAME}` 파일을 확인해 주세요.")

        elif session_state.mode == 'AUTO':
            st.subheader("자동 토픽 선정")
            # 1단계 AUTO: 토픽 생성 (미구현)
            with st.container(border=True):
                 st.write("▶️ **토픽 생성:** (미구현) 모든 토픽 사용 등 조건 충족 시 자동 생성됩니다.")
                 st.info("💡 AUTO 모드에서의 토픽 자동 생성 기능은 아직 미구현입니다.")
                 # TODO: AUTO 설정에서 토픽 생성 조건 확인 로직 추가
            st.markdown("---")
            # 1단계 AUTO: 토픽 선정 로직 실행 및 결과 표시
            with st.container(border=True):
                st.write("▶️ **토픽 선정:** 설정된 전략에 따라 자동으로 토픽을 선정합니다.")
                # AUTO 모드에서는 이 페이지 로드 시 또는 새로고침 시 자동으로 토픽을 선정합니다.
                # 이미 토픽이 선정되어 세션 상태에 있다면 다시 선정하지 않습니다.
                if session_state.selected_workflow_topic is None:
                    st.info("⏳ 사용 가능한 토픽 중에서 자동으로 하나를 선정합니다...")
                    # select_auto_func 헬퍼 함수 호출
                    # Topics data와 선정 전략을 인자로 전달
                    auto_selected_topic_obj = select_auto_func(
                        session_state.channel_topics,
                        session_state.get('auto_topic_selection_strategy', 'FIFO (가장 오래된 항목 먼저)')
                    )
                    if auto_selected_topic_obj:
                         # 자동 선정된 토픽을 세션 상태에 저장
                         session_state.selected_workflow_topic = auto_selected_topic_obj
                         # --- AUTO 모드: 선정된 토픽 USED 표시 및 Topics.json 저장 ---
                         st.info(f"✅ 선정된 토픽 '{auto_selected_topic_obj.get('TOPIC', '제목 없음')}'을 사용됨으로 표시하고 저장합니다.")
                         # mark_used_func 헬퍼 함수 호출
                         save_success = mark_used_func(
                             session_state, # session_state 자체를 전달 (channel_topics 포함)
                             channels_root_dir, # Topics.json 저장을 위해 채널 루트 경로 전달
                             auto_selected_topic_obj.get("TOPIC") # 토픽 제목 전달
                         )
                         if save_success:
                              st.success("✅ Topics.json 파일 업데이트 완료.")
                         else:
                              st.error("❌ Topics.json 파일 업데이트 실패.")
                         # --- AUTO 모드: 다음 단계로 자동 이동 ---
                         st.write("---")
                         st.info("➡️ 다음 단계(스크립트 생성)로 자동으로 진행합니다...")
                         st.session_state.current_step = 2
                         # 2단계로 이동 시 스크립트 데이터는 초기화 상태 (None)여야 2단계 진입 시 스크립트 생성을 시도합니다.
                         # 현재 코드에서는 2단계 진입 시 None 상태로 시작하므로 추가 초기화는 불필요합니다.
                         st.rerun() # 다음 단계로 자동 이동
                    else:
                         # 선정 가능한 토픽이 없는 경우 (사용되지 않은 토픽 0개)
                         st.warning("⚠️ AUTO 모드에서 선정 가능한 토픽이 없습니다. (모두 사용되었거나 파일 로드/형식 오류)")
                         # 선정 실패 시 워크플로우 중단 또는 사용자 개입 필요 메시지 표시
                         st.info("💡 모든 토픽이 사용되었거나 선정 가능한 토픽이 없습니다. 수동으로 토픽을 추가하거나 채널 설정을 확인해 주세요.")
                         if st.button("⚙️ 채널 설정에서 Topics 파일 확인", key="auto_no_topic_goto_settings"):
                              session_state.current_view = 'channel_settings'
                              st.rerun()
                else:
                     # 이미 토픽이 선정되어 있는 경우 (이전 Rerun에서 이미 다음 단계로 이동 완료됨)
                     # 이 메시지는 일반적으로 빠르게 지나가거나 보이지 않아야 정상입니다.
                     st.info(f"✨ 이미 토픽이 선정되었습니다: '{session_state.selected_workflow_topic.get('TOPIC', '제목 없음')}' (다음 단계로 자동 이동 대기 중)")
                     # 여기서 추가적인 자동 이동 로직은 필요 없습니다.
                     # 2단계 진입 로직은 workflow_view.py에서 current_step == 2일 때 처리합니다.


            st.markdown("---")

            # --- 1단계 공통: 현재 로드된 토픽 데이터 관리 ---
            st.subheader("토픽 데이터 관리")
            st.write(f"현재 채널의 `{TOPICS_FILENAME}` 파일을 직접 편집합니다.")
            st.caption(f"파일 경로: `{current_channel_topics_path}`")


            # 로드된 토픽 데이터를 편집할 수 있는 텍스트 영역
            with st.expander("📊 로드된 토픽 데이터 (JSON 형식 보기/편집)", expanded=False):
                 if session_state.channel_topics is not None:
                      # 편집기 키를 채널 이름에 따라 동적으로 설정
                      topics_editor_key = f"topics_editor_{session_state.selected_channel_name}"
                      # session_state에 에디터 내용 초기화 (로드된 토픽이 변경되었을 때)
                      current_topics_json_string = json.dumps(session_state.channel_topics, indent=2, ensure_ascii=False)
                      # 현재 로드된 내용과 session state에 저장된 에디터 내용이 다르면 업데이트
                      # (예: 채널 변경, 파일 직접 수정 후 다시 로드 시)
                      # if session_state.get(topics_editor_key) != current_topics_json_string:
                      #      session_state[topics_editor_key] = current_topics_json_string

                      # 에디터의 초기값은 session_state에 저장된 내용 또는 로드된 내용
                      initial_editor_value = session_state.get(topics_editor_key, current_topics_json_string)


                      # JSON 편집기 또는 텍스트 영역 선택 (streamlit-ace는 여기서 사용하지 않음)
                      # 여기서는 단순 text_area 사용
                      edited_topics_json_string = st.text_area(
                          f"'{TOPICS_FILENAME}' 편집:",
                          initial_editor_value,
                          height=300,
                          key=topics_editor_key # 위젯 key (session_state 자동 업데이트)
                      )

                      # 저장 버튼 (편집기 내용이 로드된 내용과 다를 때만 저장 버튼 활성화 고려 가능)
                      # 현재 session_state[topics_editor_key] 값과 로드된 원본 JSON 문자열 비교
                      button_disabled_save_topics = session_state.get(topics_editor_key) == current_topics_json_string

                      if st.button(f"💾 '{TOPICS_FILENAME}' 저장", disabled=button_disabled_save_topics, key="save_topics_button"):
                           try:
                                parsed_topics = json.loads(edited_topics_json_string)
                                if isinstance(parsed_topics, list):
                                     # TODO: 저장 시에도 유효성 간단히 체크 (각 항목이 딕셔너리인지 등)
                                     if save_topics_func(channels_root_dir, session_state.selected_channel_name, parsed_topics):
                                          st.success(f"✅ `{TOPICS_FILENAME}` 파일이 저장되었습니다.")
                                          # 저장 후 세션 상태 업데이트 및 1단계 화면 새로고침하여 변경사항 반영
                                          session_state.channel_topics = parsed_topics # 저장된 내용으로 업데이트
                                          session_state.selected_workflow_topic = None # 토픽 목록 바뀌었으니 선택 초기화
                                          # session_state[topics_editor_key]는 위젯에 의해 이미 업데이트됨
                                          st.rerun()
                                     else:
                                          st.error("❌ 파일 저장 중 오류 발생.")
                                else:
                                     st.error("❌ 오류: JSON 데이터가 리스트 형태여야 합니다.")
                           except json.JSONDecodeError:
                                st.error("❌ 오류: 입력된 텍스트가 유효한 JSON 형식이 아닙니다.")
                           except Exception as e:
                                st.error(f"❌ 저장 중 알 수 없는 오류 발생: {e}")

                 else: # 토픽 데이터가 None인 경우 (로드 실패)
                      st.error("❌ 토픽 데이터를 로드할 수 없어 편집기를 표시할 수 없습니다.")


        # 로드 실패 등으로 토픽 데이터가 None인 경우 (위에서 처리하고 return 했지만, 안전 장치)
        elif session_state.channel_topics is None:
            # 이 블록은 위에 로드 실패 시 return 때문에 도달하지 않아야 정상
            st.error("❌ 토픽 데이터를 로드할 수 없습니다. 채널 설정을 확인하거나 Topics.json 파일을 채널 디렉토리에 추가해 주세요.")
            if st.button("⚙️ 채널 설정으로 이동", key="goto_settings_from_topic_error_fallback"):
                 session_state.current_view = 'channel_settings'
                 st.rerun()

    # --- MANUAL 모드에서 다음 단계로 이동 버튼 (토픽이 선택되었을 때만 활성화) ---
    # 이 버튼은 MANUAL 모드 1단계의 주요 액션이므로 여기에 배치
    if session_state.mode == 'MANUAL' and session_state.current_step == 1:
         st.markdown("---") # 구분선 추가
         # session_state.selected_workflow_topic가 설정되었는지 확인
         if st.button("➡️ 선택한 토픽으로 다음 단계 (스크립트 생성) 진행", disabled=(session_state.selected_workflow_topic is None), key="manual_goto_step2_button"):
             # MANUAL 모드에서는 여기서 USED 표시 및 저장하지 않고,
             # 워크플로우가 최종 완료되었을 때 USED로 표시하고 저장하는 것이 일반적입니다.
             # 현재는 단계 이동만 구현합니다.
             st.session_state.current_step = 2
             # 2단계로 이동 시 스크립트 데이터는 초기화 상태 (None)여야 2단계 진입 시 스크립트 생성을 시도합니다.
             # 현재 코드에서는 2단계 진입 시 None 상태로 시작하므로 추가 초기화는 불필요합니다.
             st.rerun() # 다음 단계로 이동