import streamlit as st

def show_page(session_state):
    """환영 페이지를 렌더링합니다."""
    st.header("환영합니다!")
    st.write("이 프로그램은 LLM과 다양한 라이브러리를 활용하여 유튜브 숏츠를 자동으로 생성합니다.")
    st.write("시작하기 전에 먼저 **채널 설정**에서 작업할 채널을 선택하거나 새로 생성해 주세요.")

    # 사이드바에 있는 '작업 시작' 버튼을 누르도록 유도합니다.
    if session_state.selected_channel_name:
         st.info(f"현재 채널이 **{session_state.selected_channel_name}**(으)로 설정되었습니다. 사이드바의 '작업 시작' 버튼을 눌러 다음 단계로 진행하세요.")
    else:
         st.warning("아직 선택된 채널이 없습니다. 사이드바의 '채널 설정' 버튼을 눌러 채널을 설정해주세요.")

    # 필요에 따라 이 페이지에 직접 '작업 시작' 버튼을 둘 수도 있습니다.
    # if session_state.selected_channel_name:
    #      if st.button("▶ 작업 시작", key="welcome_start_workflow_button"):
    #           session_state.current_view = 'workflow'
    #           session_state.current_step = 1
    #           st.rerun() # 상태 변경 후 화면 즉시 갱신