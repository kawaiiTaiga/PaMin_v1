import streamlit as st

def show_page(session_state):
    """AUTO 생성 설정 페이지를 렌더링합니다."""
    st.header("⚙️ AUTO 생성 설정")
    st.write("자동 숏츠 생성 시 사용될 설정을 관리합니다.")

    st.markdown("---")

    # --- 토픽 생성 조건 설정 (미구현) ---
    with st.container(border=True):
        st.subheader("토픽 생성 조건")
        st.write("AUTO 모드에서 기존 토픽이 모두 사용되었거나 특정 조건이 충족될 때, 새로운 토픽을 자동으로 생성하는 조건을 설정합니다.")
        st.info("💡 이 기능은 아직 미구현입니다.")
        # 예시: st.number_input("남은 토픽 수 기준", min_value=0, value=0, key="auto_topic_gen_threshold")
        # 예시: st.checkbox("모든 토픽 사용 시 자동 생성", value=True, key="auto_gen_on_all_used")


    st.markdown("---")

    # --- 토픽 선정 전략 설정 ---
    with st.container(border=True):
        st.subheader("토픽 선정 전략")
        st.write("AUTO 모드에서 사용되지 않은 토픽 중 하나를 선택하는 전략을 설정합니다.")

        # session_state에 저장된 auto_topic_selection_strategy 값을 기본값으로 사용
        current_strategy = session_state.get('auto_topic_selection_strategy', 'FIFO (가장 오래된 항목 먼저)') # 기본값 지정

        selection_strategy = st.radio(
            "선정 전략 선택:",
            ('FIFO (가장 오래된 항목 먼저)', 'FILO (가장 최신 항목 먼저)', 'RANDOM (무작위)'),
            index=('FIFO (가장 오래된 항목 먼저)', 'FILO (가장 최신 항목 먼저)', 'RANDOM (무작위)').index(current_strategy), # 현재 값의 인덱스로 기본값 설정
            key='auto_topic_selection_strategy' # 세션 상태에 저장
        )
        # 라디오 버튼 값은 세션 상태에 자동으로 저장됩니다. (키 이름 'auto_topic_selection_strategy' 사용)

        # 선택된 전략에 대한 설명 표시
        if selection_strategy == 'FIFO (가장 오래된 항목 먼저)':
            st.info("📁 FIFO 전략: Topics.json 파일 내에서 순서대로 가장 먼저 나오는 사용되지 않은 토픽을 선택합니다.")
        elif selection_strategy == 'FILO (가장 최신 항목 먼저)':
            st.info("📁 FILO 전략: Topics.json 파일 내에서 역순으로 가장 나중에 나오는 사용되지 않은 토픽을 선택합니다.")
        elif selection_strategy == 'RANDOM (무작위)':
            st.info("🎲 RANDOM 전략: 사용되지 않은 토픽 중에서 무작위로 하나를 선택합니다.")

        # 세션 상태에 저장된 값 확인 (디버깅용)
        # st.write(f"현재 선택된 전략 (session_state): {session_state.get('auto_topic_selection_strategy', '설정되지 않음')}")


    st.markdown("---")

    # --- 돌아가기 버튼 ---
    if st.button("🔙 메인 화면으로 돌아가기", key="auto_settings_back_button"):
        # 보통 설정 페이지에서는 메인 화면으로 돌아갑니다.
        session_state.current_view = 'welcome'
        st.rerun()