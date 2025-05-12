# functions/topic_utils.py
import json
import os
import random
import uuid # 고유 ID 생성을 위해 추가
import time # 고유 ID 생성 시 타임스탬프 사용 위해 추가
from typing import List, Dict, Any, Optional, Tuple

TOPICS_FILENAME = "Topics.json"

# --- Helper: 고유 Topic ID 생성 ---
def _generate_topic_id(existing_ids: set) -> str:
    """기존 ID와 충돌하지 않는 새 토픽 ID 생성"""
    for _ in range(5):
        new_id = f"topic_{uuid.uuid4().hex[:8]}"
        if new_id not in existing_ids:
            return new_id
    return f"topic_{int(time.time() * 1000)}_{random.randint(100, 999)}"


# --- Topics.json 파일 로드 함수 (ID 부여 로직 수정됨) ---
def load_topics(channels_root_dir: str, selected_channel_name: str) -> Optional[List[Dict[str, Any]]]:
    """
    선택된 채널의 Topics.json 파일을 로드하고, 각 토픽에 고유 ID('topic_id')가 없으면 부여합니다.
    파일이 없으면 빈 리스트를, 오류 발생 시 None을 반환합니다.
    ID가 새로 부여되거나 기본 필드가 추가된 경우, 파일에 즉시 업데이트합니다.
    """
    if not selected_channel_name:
        print("오류: 채널 이름이 제공되지 않아 토픽을 로드할 수 없습니다.")
        return None
    topics_path = os.path.join(channels_root_dir, selected_channel_name, TOPICS_FILENAME)
    if not os.path.exists(topics_path):
        print(f"정보: '{topics_path}' 파일이 없어 빈 토픽 목록을 반환합니다.")
        return []

    try:
        with open(topics_path, 'r', encoding='utf-8') as f:
            topics_data = json.load(f)

        if not isinstance(topics_data, list):
            print(f"오류: '{topics_path}' 파일의 내용이 리스트 형태가 아닙니다.")
            return None

        processed_topics = []
        # 현재 파일에 존재하는 모든 ID를 수집하여 새 ID 생성 시 중복을 피하도록 함
        all_ids_in_file = {topic.get("topic_id") for topic in topics_data if isinstance(topic, dict) and topic.get("topic_id")}
        needs_saving = False

        for topic in topics_data:
            if isinstance(topic, dict) and "TOPIC" in topic: # TOPIC 키가 있는 유효한 항목만 처리
                current_topic_id = topic.get("topic_id")

                # ID가 없는 경우 (None 또는 빈 문자열)에만 새로 생성
                if not current_topic_id:
                    new_id = _generate_topic_id(all_ids_in_file)
                    topic["topic_id"] = new_id
                    all_ids_in_file.add(new_id) # 새로 생성된 ID도 즉시 set에 추가
                    needs_saving = True
                    print(f"[정보] 토픽 '{topic.get('TOPIC', '')}'에 새 ID 부여: {new_id}")
                # else: ID가 이미 있으면 변경하지 않고 그대로 사용

                # USED 필드 기본값 설정
                if "USED" not in topic:
                    topic["USED"] = False
                    needs_saving = True # 필드 추가도 저장 필요

                processed_topics.append(topic)
            # else: 유효하지 않은 토픽 데이터 (예: TOPIC 필드 누락)는 무시하거나 로깅 가능

        if needs_saving:
            print(f"[정보] 일부 토픽에 ID 또는 기본 필드가 없어 '{topics_path}' 파일을 업데이트합니다.")
            if save_topics(channels_root_dir, selected_channel_name, processed_topics): # 수정된 processed_topics 저장
                 print(f"[정보] '{topics_path}' 파일 업데이트 완료.")
            else:
                 print(f"[경고] '{topics_path}' 파일 자동 업데이트 실패.")
        
        return processed_topics # 처리된 토픽 리스트 반환

    except json.JSONDecodeError as e:
        print(f"ERROR: Topics.json 파일 디코딩 오류 ({topics_path}): {e}")
        return None
    except Exception as e:
        print(f"ERROR: load_topics 함수 실행 중 예외 발생 ({topics_path}): {e}")
        traceback.print_exc()
        return None


# --- Topics.json 파일 저장 함수 (ID 부여 로직은 ID 없는 경우에만 작동하도록 유지 또는 load_topics에 위임) ---
def save_topics(channels_root_dir: str, selected_channel_name: str, topics_data: List[Dict[str, Any]]) -> bool:
    """
    수정된 토픽 데이터를 Topics.json 파일로 저장합니다.
    저장 전, ID가 없는 항목에 대해서만 ID를 부여합니다. (load_topics에서 이미 처리되었을 수 있음)
    성공 시 True, 실패 시 False 반환.
    """
    if not selected_channel_name or not isinstance(topics_data, list):
        print("오류: 채널 이름이 없거나 토픽 데이터가 리스트 형태가 아니어서 저장할 수 없습니다.")
        return False

    final_topics_to_save = []
    all_ids = {topic.get("topic_id") for topic in topics_data if isinstance(topic, dict) and topic.get("topic_id")}

    for topic in topics_data:
        if isinstance(topic, dict) and "TOPIC" in topic:
            current_topic_id = topic.get("topic_id")
            if not current_topic_id: # ID가 없는 경우에만 새로 생성
                new_id = _generate_topic_id(all_ids)
                topic["topic_id"] = new_id
                all_ids.add(new_id)
                # print(f"[정보] 저장 중 토픽 '{topic.get('TOPIC', '')}'에 새 ID 부여: {new_id}") # 필요시 로깅

            if "USED" not in topic: # USED 필드 기본값
                topic["USED"] = False
            
            final_topics_to_save.append(topic)

    topics_path = os.path.join(channels_root_dir, selected_channel_name, TOPICS_FILENAME)
    try:
        channel_dir = os.path.join(channels_root_dir, selected_channel_name)
        os.makedirs(channel_dir, exist_ok=True)
        with open(topics_path, 'w', encoding='utf-8') as f:
            json.dump(final_topics_to_save, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"ERROR: save_topics 함수 실행 중 예외 발생 ({topics_path}): {e}")
        return False


# --- 특정 토픽을 USED로 표시하고 파일 저장 (ID 기반) ---
def mark_topic_used_and_save(channels_root_dir: str, selected_channel_name: str, topic_id_to_mark: str, topics_data: List[Dict[str, Any]]) -> bool:
    """
    주어진 ID의 토픽을 제공된 topics_data 리스트 내에서 USED로 표시하고 Topics.json 파일을 저장합니다.
    성공 시 True, 실패 시 False 반환. topics_data는 load_topics를 통해 이미 ID가 부여된 리스트여야 합니다.
    """
    if not topics_data or not topic_id_to_mark: # topics_data가 None이거나 비어있는 경우도 처리
        print("오류: 토픽 데이터가 없거나 변경할 토픽 ID가 제공되지 않았습니다.")
        return False

    found_and_changed = False
    topic_exists = False

    for topic in topics_data:
        if isinstance(topic, dict) and topic.get("topic_id") == topic_id_to_mark:
            topic_exists = True
            if topic.get("USED") is not True: # 실제 변경이 있을 때만
                 topic["USED"] = True
                 found_and_changed = True
            break

    if found_and_changed:
        print(f"[정보] 토픽 ID '{topic_id_to_mark}'를 USED로 표시하고 저장합니다.")
        return save_topics(channels_root_dir, selected_channel_name, topics_data)
    elif topic_exists: # 토픽은 찾았으나 이미 USED=True인 경우
         print(f"[정보] 토픽 ID '{topic_id_to_mark}'는 이미 USED 상태입니다. 저장을 건너<0xEB><0x8A>니다.")
         return True # 변경사항이 없으므로 성공으로 간주
    else: # topic_id_to_mark를 찾지 못한 경우
        print(f"WARNING: 토픽 ID '{topic_id_to_mark}'를 찾을 수 없어 USED 표시 실패.")
        return False


# --- 토픽 병합 함수 (ID 기반 중복 체크) ---
def merge_topics(existing_topics: List[Dict[str, Any]], new_topics: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """
    기존 토픽 리스트와 새로운 토픽 리스트를 병합합니다.
    topic_id 필드를 기준으로 중복을 제거합니다. ID가 없는 항목은 새로 부여합니다.
    """
    if not isinstance(existing_topics, list): existing_topics = []
    if not isinstance(new_topics, list): new_topics = []

    # 병합된 결과를 저장할 리스트와 모든 ID를 추적할 집합
    merged_list = []
    all_merged_ids = set()
    added_count = 0

    # 1. 기존 토픽 처리: ID 부여 및 all_merged_ids에 추가
    for topic in existing_topics:
        if isinstance(topic, dict) and "TOPIC" in topic:
            topic_id = topic.get("topic_id")
            if not topic_id: # ID가 없으면 생성
                topic_id = _generate_topic_id(all_merged_ids)
                topic["topic_id"] = topic_id
            
            if topic_id not in all_merged_ids: # 중복 ID가 아닌 경우에만 추가
                all_merged_ids.add(topic_id)
                if "USED" not in topic: topic["USED"] = False
                merged_list.append(topic)
            # else: 중복 ID 가진 기존 토픽은 무시 (첫 번째 것만 유지)

    # 2. 새 토픽 처리: ID 부여 및 기존 목록에 없으면 추가
    for new_topic in new_topics:
        if isinstance(new_topic, dict) and "TOPIC" in new_topic and "DETAIL" in new_topic: # 필수 필드 확인
            topic_id = new_topic.get("topic_id")
            
            # 새 토픽에 ID가 없거나, 있더라도 이미 병합된 ID 목록에 있다면 (중복 방지) 새로 생성
            if not topic_id or topic_id in all_merged_ids:
                 topic_id = _generate_topic_id(all_merged_ids)
                 new_topic["topic_id"] = topic_id

            # 최종 ID 기준으로 기존 목록에 없으면 추가
            if topic_id not in all_merged_ids:
                 all_merged_ids.add(topic_id)
                 if "USED" not in new_topic: new_topic["USED"] = False
                 merged_list.append(new_topic)
                 added_count += 1
            # else: 중복된 새 토픽은 추가하지 않음

    return merged_list, added_count

# --- AUTO 모드 토픽 선정 함수 (ID 기반으로 반환) ---
def select_auto_topic(topics_data: Optional[List[Dict[str, Any]]], selection_strategy: str) -> Optional[Dict[str, Any]]:
    """
    AUTO 모드 설정에 따라 사용되지 않은 토픽을 자동으로 선정합니다.
    선정 성공 시 선정된 토픽 딕셔너리(ID 포함)를, 실패 시 None을 반환합니다.
    topics_data는 load_topics를 통해 이미 ID가 부여된 리스트여야 합니다.
    """
    if not isinstance(topics_data, list) or not topics_data:
        print("정보: 토픽 데이터가 없거나 비어있어 자동 선택할 수 없습니다.")
        return None
        
    unused_topics = [topic for topic in topics_data if isinstance(topic, dict) and topic.get("USED") is False and "topic_id" in topic] # ID 있는 미사용 토픽만
    
    if not unused_topics:
        print("정보: 사용 가능한 (미사용) 토픽이 없습니다.")
        return None

    selected_topic = None
    if selection_strategy == 'FIFO (가장 오래된 항목 먼저)':
        selected_topic = unused_topics[0]
    elif selection_strategy == 'FILO (가장 최신 항목 먼저)':
        selected_topic = unused_topics[-1]
    elif selection_strategy == 'RANDOM (무작위)':
        selected_topic = random.choice(unused_topics)
    else: # 알 수 없는 전략
        print(f"경고: 알 수 없는 토픽 선정 전략 '{selection_strategy}'. FIFO를 사용합니다.")
        selected_topic = unused_topics[0]
        
    if selected_topic:
        print(f"자동 선정된 토픽: '{selected_topic.get('TOPIC')}' (ID: {selected_topic.get('topic_id')})")
    return selected_topic