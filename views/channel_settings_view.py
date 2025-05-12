import streamlit as st
import json
import os
import datetime # 채널 정의 lastUpdated 필드에 사용
# streamlit_ace 임포트는 app.py에서 가용성 체크 후 모듈 자체를 인자로 받습니다.
# from streamlit_ace import st_ace # 직접 임포트하지 않습니다.

def show_page(session_state, channels_root_dir, create_channel_logic, json_editor_available, st_ace_module, available_workflows):
    """채널 설정 페이지를 렌더링합니다."""
    st.header("⚙️ 채널 설정")
    st.write("작업할 채널을 선택하거나, 새로운 채널을 생성하고 채널 정의를 편집할 수 있습니다.")

    st.markdown("---")

    # --- 채널 선택 섹션 ---
    with st.container(border=True):
         st.subheader("채널 선택")
         st.write(f"채널 루트 디렉토리: `{channels_root_dir}`")

         # 사용 가능한 채널 목록 (디렉토리 이름 기준)
         try:
             available_channels = [d for d in os.listdir(channels_root_dir) if os.path.isdir(os.path.join(channels_root_dir, d))]
         except FileNotFoundError:
             available_channels = []

         # Selectbox에 기본 옵션 추가
         display_channels = ["-- 채널 선택 --"] + available_channels
         # 현재 로드된 채널이 있다면 selectbox의 기본값으로 설정
         default_channel_index = display_channels.index(session_state.selected_channel_name) if session_state.selected_channel_name in display_channels else 0

         selected_channel_for_load = st.selectbox(
             "기존 채널 선택:",
             display_channels,
             index=default_channel_index,
             key="settings_channel_select"
         )

         # 채널 로드 버튼 (선택된 채널이 '-- 채널 선택 --'이 아니고, 현재 로드된 채널과 다를 때 또는 현재 로드된 채널이지만 정의가 로드 안됐을 때 활성화)
         # 이미 로드된 채널인데 다시 로드 버튼을 누르는 경우는 정의 파일이 수정되었을 수 있으므로 허용
         button_disabled_load = (selected_channel_for_load == "-- 채널 선택 --") # "-- 채널 선택 --" 선택 시 비활성화

         if st.button("✅ 채널 로드", disabled=button_disabled_load, key="load_channel_button"):
              channel_dir = os.path.join(channels_root_dir, selected_channel_for_load)
              channel_def_path = os.path.join(channel_dir, "channel_definition.json")
              thumbnail_path_png = os.path.join(channel_dir, "thumbnail.png")
              thumbnail_path_jpg = os.path.join(channel_dir, "thumbnail.jpg")
              thumbnail_path_jpeg = os.path.join(channel_dir, "thumbnail.jpeg")

              channel_def = None
              thumbnail_path = None

              # 1. 채널 정의 로드 시도
              if os.path.exists(channel_def_path):
                   try:
                        with open(channel_def_path, 'r', encoding='utf-8') as f:
                             channel_def = json.load(f)
                        session_state.selected_channel_name = selected_channel_for_load
                        session_state.current_channel_definition = channel_def
                        # 채널 정의에서 워크플로우 이름 로드, 없으면 기본값 사용
                        session_state.current_workflow_name = channel_def.get('workflow', st.session_state.get('DEFAULT_WORKFLOW_NAME', 'basic')) # app.py의 DEFAULT_WORKFLOW_NAME 사용 고려
                        st.success(f"✨ 채널 '{selected_channel_for_load}' 정의가 로드되었습니다. (워크플로우: {session_state.current_workflow_name})")

                   except json.JSONDecodeError:
                        st.error(f"❌ 오류: '{channel_def_path}' 파일이 유효한 JSON 형식이 아닙니다.")
                        session_state.selected_channel_name = selected_channel_for_load # 이름은 선택됨
                        session_state.current_channel_definition = None # 정의는 None
                        session_state.current_workflow_name = None # 워크플로우 이름도 알 수 없음

                   except Exception as e:
                        st.error(f"❌ 채널 정의 로드 중 오류 발생: {e}")
                        session_state.selected_channel_name = selected_channel_for_load # 이름은 선택됨
                        session_state.current_channel_definition = None # 정의는 None
                        session_state.current_workflow_name = None # 워크플로우 이름도 알 수 없음
              else:
                   st.warning(f"⚠️ 주의: '{channel_def_path}' 파일이 존재하지 않습니다. 새 정의로 시작합니다.")
                   session_state.selected_channel_name = selected_channel_for_load
                   session_state.current_channel_definition = {} # 빈 딕셔너리로 시작 (편집 가능)
                   session_state.current_workflow_name = st.session_state.get('DEFAULT_WORKFLOW_NAME', 'basic') # 파일 없으면 기본 워크플로우 이름 사용

              # 2. 썸네일 로드 시도
              if os.path.exists(thumbnail_path_png):
                   thumbnail_path = thumbnail_path_png
              elif os.path.exists(thumbnail_path_jpg):
                    thumbnail_path = thumbnail_path_jpg
              elif os.path.exists(thumbnail_path_jpeg):
                    thumbnail_path = thumbnail_path_jpeg

              session_state.current_channel_thumbnail_path = thumbnail_path
              if thumbnail_path:
                   st.info(f"🖼️ 썸네일 파일 로드됨: `{os.path.basename(thumbnail_path)}`")
              elif session_state.selected_channel_name != "-- 채널 선택 --":
                   st.info("이 채널에는 썸네일 파일이 없습니다. 아래에서 업로드하세요.")

              # 3. 채널 로드 시 Topics 관련 상태 초기화 (워크플로우 뷰에서 로드할 예정)
              session_state.channel_topics = None
              session_state.selected_workflow_topic = None

              st.rerun() # 로드된 정보가 사이드바 등에 즉시 반영되게 새로고침


         # 현재 선택된 채널 정보와 썸네일 표시 (로드된 후에만)
         if session_state.selected_channel_name and session_state.selected_channel_name != "-- 채널 선택 --":
              st.write(f"**현재 로드된 채널:** {session_state.selected_channel_name}")
              if session_state.current_workflow_name:
                   st.write(f"**로드된 워크플로우:** {session_state.current_workflow_name}")
              if session_state.current_channel_thumbnail_path and os.path.exists(session_state.current_channel_thumbnail_path):
                   st.image(session_state.current_channel_thumbnail_path, caption="현재 썸네일", width=100)
              else:
                   st.info("현재 로드된 채널의 썸네일이 없습니다.")
         # 채널 목록은 있는데 아무것도 로드 안된 상태
         elif not session_state.selected_channel_name:
              st.info("채널을 선택하여 로드하거나 새로 생성해 주세요.")


    st.markdown("---")

    # --- 새 채널 생성 섹션 ---
    with st.container(border=True):
        st.subheader("새 채널 생성")
        st.write("새로운 채널 디렉토리와 기본 설정 파일들을 생성합니다.")

        if create_channel_logic:
            new_channel_name = st.text_input(
                "새 채널 이름 입력:",
                value=session_state.get('settings_new_channel_name_input', ''),
                key='settings_new_channel_name_input'
            )
            is_valid_name = bool(new_channel_name) and not any(c in '\\/:*?"<>|' for c in new_channel_name)
            button_disabled_create = not is_valid_name

            if st.button("➕ 채널 생성", disabled=button_disabled_create, key="settings_create_channel_button"):
                 with st.spinner(f"'{new_channel_name}' 채널 생성 중..."):
                    # create_channel_logic 호출 시 기본 워크플로우는 함수 내부에서 channel_definition에 추가
                    success, message = create_channel_logic(
                        channel_name=new_channel_name,
                        channels_root_dir=channels_root_dir
                    )

                    if success:
                        st.success(f"✅ {message}")
                        session_state['settings_new_channel_name_input'] = ""
                        # 생성 후 자동으로 로드된 채널로 설정 (선택 사항)
                        # session_state.selected_channel_name = new_channel_name
                        # session_state.current_channel_definition = # 새로 생성된 정의 로드 필요
                        # session_state.current_workflow_name = # 새로 생성된 정의에서 로드
                        st.rerun() # 목록 업데이트 및 입력 필드 초기화
                    else:
                        st.error(f"❌ {message}")

        else:
            st.warning("⚠️ 경고: 채널 생성 로직을 사용할 수 없습니다. `app.py`에서 `create_channel_logic` 함수가 올바르게 정의되었는지 확인하세요.")


    st.markdown("---")

    # --- 현재 채널 정의 및 썸네일 편집 섹션 ---
    # 이 섹션은 채널이 로드된 후에만 표시
    if session_state.selected_channel_name and session_state.selected_channel_name != "-- 채널 선택 --" and session_state.current_channel_definition is not None:

         with st.container(border=True):
            st.subheader(f"'{session_state.selected_channel_name}' 채널 정의 편집")
            st.write("아래 JSON 데이터를 수정하고 '저장' 버튼을 누르세요.")
            st.write("⚠️ 정의를 저장해도 워크플로우의 이전 단계 결과는 초기화되지 않습니다. 필요에 따라 수동으로 다시 실행해야 합니다.")

            # --- 워크플로우 선택 드롭다운 추가 ---
            # 채널 정의에 저장될 기본 워크플로우를 여기서 선택하게 함
            if available_workflows and isinstance(available_workflows, list):
                 default_wf_index = available_workflows.index(session_state.get('current_workflow_name', 'basic')) if session_state.get('current_workflow_name', 'basic') in available_workflows else 0
                 selected_workflow_for_definition = st.selectbox(
                     "이 채널의 기본 워크플로우 설정:",
                     available_workflows,
                     index=default_wf_index,
                     key=f"settings_channel_workflow_select_{session_state.selected_channel_name}" # 채널별 고유 키
                 )
                 # 사용자가 선택한 워크플로우 이름을 세션 상태에도 업데이트 (로드된 정의와 일치시킴)
                 session_state.current_workflow_name = selected_workflow_for_definition
            else:
                 st.warning("⚠️ 정의된 워크플로우가 없습니다. `app.py`의 `ALL_WORKFLOW_DEFINITIONS`를 확인하세요.")
                 selected_workflow_for_definition = session_state.get('current_workflow_name', 'basic') # 임시 값 유지


            # 초기 편집기 값 설정
            current_def = session_state.get('current_channel_definition', {})
            # 현재 선택된 워크플로우 이름을 정의 데이터에 반영 (저장 시 사용)
            current_def['workflow'] = selected_workflow_for_definition
            # 마지막 업데이트 시간 업데이트
            current_def['lastUpdated'] = datetime.datetime.now().isoformat()

            current_def_json_string = json.dumps(current_def, indent=2, ensure_ascii=False)

            editor_key = f"settings_channel_def_editor_{session_state.selected_channel_name}"

            if json_editor_available and st_ace_module:
                 edited_definition_text = st_ace_module.st_ace(
                     session_state.get(editor_key, current_def_json_string),
                     language="json",
                     theme="github",
                     height=400,
                     key=editor_key
                 )
            else:
                 if not json_editor_available:
                      st.warning("⚠️ JSON 편집기 라이브러리(streamlit-ace)가 설치되지 않아 기본 텍스트 영역이 표시됩니다. `pip install streamlit-ace` 설치를 권장합니다.")

                 edited_definition_text = st.text_area(
                     "JSON 형식으로 수정하세요:",
                     session_state.get(editor_key, current_def_json_string),
                     height=400,
                     key=f"{editor_key}_textarea"
                 )

            # 채널 정의 저장 버튼
            # 편집기 내용이 로드된 내용과 다를 때만 저장 버튼 활성화 고려 가능
            # button_disabled_save_def = session_state.get(editor_key, current_def_json_string) == current_def_json_string

            if st.button("✅ 채널 정의 저장", key="settings_save_definition_button"): # , disabled=button_disabled_save_def):
                save_path = os.path.join(
                    channels_root_dir,
                    session_state.selected_channel_name,
                    "channel_definition.json"
                )
                try:
                    parsed_json = json.loads(edited_definition_text)

                    # 저장 시 현재 선택된 워크플로우 이름을 정의에 명시적으로 추가 (편집기 내용 덮어쓰기)
                    # 이는 편집기에서 workflow 값을 잘못 수정하는 경우를 방지하기 위함입니다.
                    parsed_json['workflow'] = selected_workflow_for_definition
                    parsed_json['lastUpdated'] = datetime.datetime.now().isoformat()


                    with open(save_path, 'w', encoding='utf-8') as f:
                        json.dump(parsed_json, f, indent=2, ensure_ascii=False)

                    session_state.current_channel_definition = parsed_json # 저장된 정의로 세션 상태 업데이트
                    st.success(f"🔥 채널 정의가 성공적으로 저장되었습니다: `{save_path}`")

                    # 저장 후 사이드바 정보 갱신을 위해 rerun 필요
                    st.rerun()

                except json.JSONDecodeError:
                    st.error(f"❌ 오류: 입력된 텍스트가 유효한 JSON 형식이 아닙니다.")
                except Exception as e:
                    st.error(f"❌ 채널 정의 저장 중 오류 발생: {e}")

            st.markdown("---")

            # --- 썸네일 관리 섹션 ---
            st.subheader(f"'{session_state.selected_channel_name}' 썸네일 관리")

            if session_state.current_channel_thumbnail_path and os.path.exists(session_state.current_channel_thumbnail_path):
                 st.image(session_state.current_channel_thumbnail_path, caption="현재 썸네일", width=150)
            else:
                 st.info("현재 로드된 채널에 설정된 썸네일 파일이 없습니다.")

            uploaded_file = st.file_uploader(
                "새 썸네일 이미지 업로드 (.png, .jpg, .jpeg)",
                type=['png', 'jpg', 'jpeg'],
                key=f"settings_thumbnail_uploader_{session_state.selected_channel_name}"
            )

            if uploaded_file is not None:
                 file_extension = uploaded_file.name.split('.')[-1].lower()
                 save_filename = f"thumbnail.{file_extension}"
                 save_path = os.path.join(
                     channels_root_dir,
                     session_state.selected_channel_name,
                     save_filename
                 )

                 if st.button("💾 썸네일 저장", key=f"settings_save_thumbnail_button_{session_state.selected_channel_name}"):
                      try:
                           old_thumb_base = os.path.join(channels_root_dir, session_state.selected_channel_name, "thumbnail")
                           for ext in ['png', 'jpg', 'jpeg']:
                                old_path = f"{old_thumb_base}.{ext}"
                                if os.path.exists(old_path):
                                     os.remove(old_path)

                           with open(save_path, "wb") as f:
                                f.write(uploaded_file.getvalue())

                           session_state.current_channel_thumbnail_path = save_path
                           st.success(f"✅ 썸네일이 성공적으로 저장되었습니다: `{save_filename}`")
                           st.rerun()
                      except Exception as e:
                           st.error(f"❌ 썸네일 저장 중 오류 발생: {e}")

         # --- 돌아가기 버튼 (설정 페이지에서 벗어나기) ---
         st.markdown("---")
         if st.button("🔙 메인 화면으로 돌아가기", key="settings_back_to_main_button"):
             session_state.current_view = 'welcome'
             st.rerun()

    # 채널이 로드되지 않았을 때 표시
    elif session_state.selected_channel_name is None:
         st.info("채널 설정을 시작하려면 먼저 기존 채널을 선택하거나 새로운 채널을 생성해야 합니다.")