# generate_script.py

import os
import json
import re
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
import datetime

# --- LangChain 관련 모듈 임포트 ---
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.runnables import RunnableSequence
    langchain_available = True
except ImportError:
    print("오류: LangChain 또는 google-generativeai 라이브러리가 설치되지 않았습니다.")
    print("`pip install langchain-google-genai python-dotenv` 명령으로 설치해주세요.")
    langchain_available = False

# --- 설정 ---
load_dotenv()
# 환경 변수에서 API 키 로드 (우선 순위 높음)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# 환경 변수가 설정되지 않았을 경우에만 코드 내 임시 키 사용 (보안 매우 취약)
if not GOOGLE_API_KEY:
    # 경고: 실제 환경에서는 이 코드를 사용하지 마세요. 환경 변수를 설정하세요.
    GOOGLE_API_KEY = 'api_key_here'
    if GOOGLE_API_KEY == 'api_key_here':
         print("경고: GOOGLE_API_KEY 환경 변수가 설정되지 않았습니다. 코드 내 임시 키를 사용합니다. (보안 취약)")


# --- Stage 1: 시나리오 생성 관련 함수 ---

def build_stage1_prompt(channel_def: Dict[str, Any]) -> ChatPromptTemplate:
    """채널 정의를 바탕으로 Stage 1 프롬프트 템플릿을 구성합니다."""
    # 채널 정의는 함수 인자로 받으므로 전역 channel_definition 사용 안 함
    guidelines_summary = f"""
- 채널명: {channel_def['channelInfo']['channelName']}
- 타겟 주 연령대: {channel_def['targetAudience']['primaryAgeRange'][0]}
- 타겟 관심사: {', '.join(channel_def['targetAudience']['interests'])}
- 채널 톤앤매너: {channel_def['channelIdentity']['toneOfVoice']} ({', '.join(channel_def['channelIdentity']['personalityAdjectives'])})
- 목표 길이: 약 {channel_def['shortsFormat']['standardDurationSeconds']}초 ({channel_def['shortsFormat']['pacing']} 템포)
- 금지 표현/주제: {', '.join(channel_def['channelIdentity']['forbiddenTopicsOrTones'])}
"""

    segments_to_include = []
    segment_guide_lines = []
    # Stage 1 LLM 생성에서 제외할 세그먼트 이름 (CTA 등)
    segments_to_exclude_from_stage1 = ["CTA_Engage", "CTA_Subscribe"]

    # Standard Segments만 Stage 1 생성 대상에 포함
    for seg in channel_def['shortsFormat']['standardSegments']:
        segment_name = seg['segmentName']
        if segment_name not in segments_to_exclude_from_stage1:
            segments_to_include.append(segment_name)
            segment_guide_lines.append(
                f"- {segment_name} ({seg['purpose']}): {seg['styleNotes']}"
            )

    segment_guide = "\n".join(segment_guide_lines)
    included_segment_names_str = ', '.join(segments_to_include)

    # --- 프롬프트 템플릿 정의 (```, 예시, KEYWORDS, MUSIC 제거) ---
    prompt_template_stage1 = f"""
당신은 '{channel_def['channelInfo']['channelName']}' 채널의 전문 숏츠 시나리오 작가입니다. 주어진 채널 가이드라인과 토픽 상세 내용을 바탕으로, **지정된 핵심 콘텐츠 세그먼트**에 대한 시나리오를 작성해야 합니다.

[채널 가이드라인]
{guidelines_summary}

[생성할 세그먼트 가이드]
{segment_guide}
**주의: 오직 다음 세그먼트들만 순서대로 생성해주세요: {included_segment_names_str}**

[TMI 주제 제목]
{{TOPIC}}

[TMI 상세 내용]
{{DETAIL}}

**[출력 형식 지침 (매우 중요)]**
다음 마커 기반 형식을 정확히 따라서, 텍스트로만 응답해주세요.
- 영상 제목은 `TITLE:` 마커로 시작해야 합니다.
- 각 세그먼트는 `==SEGMENT_START==`와 `==SEGMENT_END==` 마커 사이에 작성합니다.
- 각 세그먼트 내에는 `TYPE:` (세그먼트 이름)과 `SCRIPT:` (스크립트 내용) 마커만 포함합니다.
- **다른 어떤 설명, 인사, 요약 등도 절대 추가하지 마세요.** 오직 요청된 형식의 텍스트만 출력해야 합니다.
- **KEYWORDS: 또는 MUSIC: 마커는 포함하지 마세요.**

**정확한 출력 형식 예시:**

TITLE: 예시 제목 (topic_title 기반으로 어그로 끌기/ 문장형태 X)

==SEGMENT_START==
TYPE: Type 내용
SCRIPT: 타입에 목적에 맞는 내용

==SEGMENT_END==

==SEGMENT_START==
...


(위와 같이 `{included_segment_names_str}` 순서대로 모든 요청된 세그먼트를 작성)
"""
    return ChatPromptTemplate.from_template(prompt_template_stage1)

def get_llm_chain(api_key: str, channel_def: Dict[str, Any]) -> Optional[RunnableSequence[dict, str]]:
    """LangChain Chain을 반환합니다."""
    if not api_key:
        print("오류: API 키가 제공되지 않았습니다.")
        return None
    if not langchain_available:
         print("오류: LangChain 관련 라이브러리가 설치되지 않았습니다.")
         return None

    try:
        llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash', api_key=api_key,
                                     temperature=0.7, # 창의성 조절
                                     convert_system_message_to_human=True)
        prompt = build_stage1_prompt(channel_def)
        output_parser = StrOutputParser()
        chain: RunnableSequence[dict, str] = prompt | llm | output_parser
        return chain
    except Exception as e:
        print(f"오류: LLM 초기화 또는 Chain 생성 중 오류 발생: {e}")
        print("API 키가 유효한지, 또는 모델 접근 권한이 있는지 확인해주세요.")
        return None

# --- Stage 1 결과 파싱 함수 (Keywords, Music 파싱 제거) ---
def parse_marker_text(text: str) -> Dict[str, Any]:
    """마커 기반 텍스트를 파싱하여 딕셔너리로 변환하는 함수"""
    # Keywords, Music 필드 삭제
    output = {"title": None, "segments": []}
    lines = text.splitlines()
    print(lines)
    # 메타데이터 파싱 (TITLE만 남음)
    meta_section_lines = []
    for line in lines:
        if line.strip().startswith("==SEGMENT_START=="):
             break # 첫 번째 세그먼트 시작 전에 메타데이터 섹션 종료
        meta_section_lines.append(line)
    meta_text = "\n".join(meta_section_lines)

    title_match = re.search(r"^TITLE:\s*(.*)", meta_text, re.IGNORECASE | re.MULTILINE)
    # keywords_match = re.search(r"^KEYWORDS:\s*(.*)", meta_text, re.IGNORECASE | re.MULTILINE) # 삭제
    # music_match = re.search(r"^MUSIC:\s*(.*)", meta_text, re.IGNORECASE | re.MULTILINE) # 삭제

    if title_match: output["title"] = title_match.group(1).strip()
    # Keywords, Music 파싱 및 할당 로직 삭제
    # if keywords_match: output["keywords"] = [k.strip() for k in keywords_match.group(1).split(',') if k.strip()]
    # if music_match: output["music"] = music_match.group(1).strip()

    # 세그먼트 파싱
    segment_pattern = re.compile(r"==SEGMENT_START==\s*(.*?)\s*==SEGMENT_END==", re.DOTALL)

    for match in segment_pattern.finditer(text):
        segment_content = match.group(1).strip()

        segment_data = {"type": None, "script": None, "visuals": []} # visuals 필드 미리 추가

        type_match = re.search(r"^\s*TYPE:\s*(\S+)", segment_content, re.IGNORECASE | re.MULTILINE)
        script_match = re.search(r"^\s*SCRIPT:\s*(.*)", segment_content, re.DOTALL | re.IGNORECASE | re.MULTILINE)

        if type_match:
            segment_data["type"] = type_match.group(1).strip()

        if script_match:
            script_text = script_match.group(1).strip()
            # 문장 분리 (Stage 2에서 활용 가능)
            sentences = re.split(r'(?<=[.?!])\s+', script_text)
            sentences = [s.strip() for s in sentences if s.strip()]

            segment_data["script"] = script_text
            segment_data["sentences"] = sentences

        # type과 script 마커가 모두 정상적으로 있고 type 내용이 비어있지 않은 경우 유효 세그먼트로 간주
        if segment_data.get("type") and script_match is not None and segment_data.get("type"):
             output["segments"].append(segment_data)
        else:
             # 파싱 실패 경고 (디버깅용)
             # print(f"경고(parse_marker_text): 세그먼트 파싱 오류 - TYPE 또는 SCRIPT 마커 문제 또는 내용 부족. 내용:\n---\n{segment_content}\n---")
             pass # Streamlit UI에서 사용자에게 보여주므로 백엔드 로그는 좀 더 조용하게


    # 세그먼트가 하나도 파싱되지 않았다면 LLM 응답 형식 오류일 가능성 높음
    if not output["segments"] and "==SEGMENT_START==" in text:
         print("경고(parse_marker_text): LLM 응답에서 세그먼트 형식이 제대로 파싱되지 않았습니다.")


    return output


# --- 핵심 백엔드 함수: 스크립트 생성 및 저장 (JSON 반환, output_dir 입력) ---

def generate_initial_script(topic: Dict[str, Any], channel_definition_path: str, output_dir: str) -> Optional[Dict[str, Any]]:
    """
    Stage 1: 초기 스크립트(마커 기반 텍스트)를 생성하고 파싱하여 JSON(Dict) 형태로 반환합니다.
    raw 텍스트 및 파싱된 JSON 결과는 지정된 디렉토리에 파일로 저장합니다.

    Args:
        topic: {"title": str, "detail": List[str]} 형태의 토픽 정보.
        channel_definition_path: 채널 정의 JSON 파일 경로.
        output_dir: 생성된 파일들을 저장할 디렉토리 경로.

    Returns:
        파싱된 스크립트 데이터 (Dict) 또는 실패 시 None.
    """
    # 입력 유효성 검사
    if not os.path.exists(channel_definition_path):
        print(f"오류: 채널 정의 파일 경로를 찾을 수 없습니다: {channel_definition_path}")
        return None

    if not output_dir:
        print("오류: 결과를 저장할 output_dir 경로가 지정되지 않았습니다.")
        return None

    # output_dir 생성
    try:
        os.makedirs(output_dir, exist_ok=True)
    except Exception as e:
        print(f"오류: 결과 디렉토리 '{output_dir}'를 생성하는 중 오류 발생: {e}")
        return None

    try:
        with open(channel_definition_path, 'r', encoding='utf-8') as f:
            channel_def = json.load(f)
    except Exception as e:
        print(f"오류: 채널 정의 파일을 읽는 중 오류 발생: {e}")
        return None

    if not GOOGLE_API_KEY:
        print("오류: GOOGLE_API_KEY가 설정되지 않았습니다. LLM 호출 불가.")
        return None

    chain = get_llm_chain(GOOGLE_API_KEY, channel_def)
    if not chain:
        print("오류: LLM Chain 생성에 실패했습니다.")
        return None

    try:
        # LLM 호출
        print(f"Stage 1: 시나리오 생성 시작 - 토픽: {topic.get('title', '제목 없음')}")
        generated_text: str = chain.invoke(topic)
        print("Stage 1: LLM 응답 수신 완료.")

        # 응답 파싱
        parsed_data = parse_marker_text(generated_text)

        # 파일명 생성 (raw 텍스트와 JSON 파일에 공통으로 사용)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        # 토픽 제목에서 파일명으로 부적절한 문자 제거 및 길이 제한
        safe_title = re.sub(r'[\\/*?:"<>|\s]', '_', topic.get('title', 'untitled'))[:50].strip('_') # 공백 처리 후 앞뒤 _ 제거
        if not safe_title: safe_title = "untitled" # 제목이 비어있거나 부적절 문자만 있는 경우
        base_filename = f"script_stage1_{timestamp}_{safe_title}"

        raw_filepath = os.path.join(output_dir, f"{base_filename}.txt")
        json_filepath = os.path.join(output_dir, f"{base_filename}.json")

        # raw 텍스트 파일 저장
        try:
            with open(raw_filepath, 'w', encoding='utf-8') as f:
                f.write(generated_text)
            print(f"Stage 1: Raw 시나리오 파일 저장 완료 - 경로: {raw_filepath}")
        except Exception as e:
             print(f"경고: Raw 시나리오 파일 저장 중 오류 발생: {e}")

        # 파싱된 JSON 데이터 파일 저장
        try:
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump(parsed_data, f, indent=2, ensure_ascii=False)
            print(f"Stage 1: 파싱된 JSON 파일 저장 완료 - 경로: {json_filepath}")
            # 저장된 파일 경로들을 반환 데이터에 추가 (선택 사항)
            # parsed_data['__raw_filepath__'] = raw_filepath
            # parsed_data['__json_filepath__'] = json_filepath
        except Exception as e:
             print(f"경고: 파싱된 JSON 파일 저장 중 오류 발생: {e}")


        return parsed_data # 파싱된 딕셔너리 반환

    except Exception as e:
        print(f"오류: Stage 1 시나리오 생성, 파싱 또는 저장 중 오류 발생: {e}")
        # 상세 에러 로깅 필요시 추가
        return None

# --- Stage 2: 스크립트 상세 처리 함수 (백엔드 유틸리티로 포함) ---
# 이 함수는 Stage 1 파싱 결과를 받아 후처리하는 로직입니다.
# 논리적으로는 별도 파일(process_script.py 등)에 분리하는 것이 더 좋지만,
# 현재는 generate_script.py에 유틸리티 함수로 함께 둡니다.
def process_stage2(stage1_data: Dict[str, Any], channel_def: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stage 1 결과를 바탕으로 Stage 2 처리를 수행합니다.
    - Stage 1 결과가 잘 파싱되었는지 확인
    - Stage 1 세그먼트에 예상 시간 할당
    - Stage 1 세그먼트에 visuals 리스트 초기화 (빈 리스트)
    - channel_definition의 추가 세그먼트(CTA 등) 추가 및 시간/visuals 초기화
    - (선택 사항) 전체 예상 시간 계산
    """
    if not stage1_data or not stage1_data.get("segments"):
        print("오류(process_stage2): Stage 1 파싱 데이터가 유효하지 않거나 세그먼트가 없습니다.")
        return None # 유효하지 않은 입력에 대해 None 반환

    # 얕은 복사 대신 깊은 복사가 안전할 수 있으나, 여기서는 세그먼트 리스트만 새로 만들므로 얕은 복사 + 세그먼트 리스트 재생성으로 충분
    stage2_data = stage1_data.copy()
    stage2_data['segments'] = [] # 새 리스트로 시작

    # 채널 정의에서 세그먼트별 예상 시간 정보 가져오기
    segment_durations = {}
    for seg_list in ['standardSegments', 'additionalSegments']:
        if seg_list in channel_def['shortsFormat']:
            for seg in channel_def['shortsFormat'][seg_list]:
                 segment_durations[seg['segmentName']] = seg.get('estimatedDurationSeconds', 0)


    # Stage 1에서 생성된 세그먼트 처리
    if stage1_data.get('segments'): # segments 키가 존재하고 비어있지 않은 경우만 처리
        for segment in stage1_data['segments']:
            segment_type = segment.get('type')
            processed_segment = segment.copy() # 세그먼트 복사
            processed_segment['duration_seconds'] = segment_durations.get(segment_type, 0) # 정의된 시간 사용, 없으면 기본값 0
            processed_segment['visuals'] = [] # Stage 3에서 채울 빈 리스트 추가

            # 스크립트 문장 분리가 안되어있다면 여기서 다시 시도 (parse_marker_text에서 했지만 안전 장치)
            if 'sentences' not in processed_segment or not isinstance(processed_segment['sentences'], list) or not processed_segment['sentences']:
                 script_text = processed_segment.get('script', '')
                 sentences = re.split(r'(?<=[.?!])\s+', script_text)
                 processed_segment['sentences'] = [s.strip() for s in sentences if s.strip()]

            stage2_data['segments'].append(processed_segment)


    # channel_definition에 정의된 추가 세그먼트(CTA 등) 추가
    # Stage 1 결과에 이미 포함된 세그먼트는 추가하지 않음 (Stage 1 프롬프트가 CTA를 제외하므로 중복 없을 것으로 예상하지만 안전 장치)
    existing_types = {seg.get('type') for seg in stage2_data['segments']}

    if 'additionalSegments' in channel_def['shortsFormat']:
        for additional_seg_def in channel_def['shortsFormat']['additionalSegments']:
             cta_segment_type = additional_seg_def['segmentName']
             if cta_segment_type not in existing_types:
                 # TODO: 실제 CTA 스크립트는 LLM 등으로 생성하거나 정해진 템플릿을 사용해야 함.
                 # 현재는 임시로 styleNotes 또는 purpose 필드의 내용을 스크립트로 사용.
                 cta_script_content = additional_seg_def.get('styleNotes', additional_seg_def.get('purpose', '')).strip() or f"[{cta_segment_type} 스크립트 필요]"

                 cta_segment = {
                     "type": cta_segment_type,
                     "script": cta_script_content,
                     "duration_seconds": segment_durations.get(cta_segment_type, 0),
                     "visuals": [], # 빈 리스트로 초기화
                     "sentences": [s.strip() for s in re.split(r'(?<=[.?!])\s+', cta_script_content) if s.strip()] # 간단하게 문장 분리
                 }
                 stage2_data['segments'].append(cta_segment)
                 existing_types.add(cta_segment_type) # 추가했으니 기존 타입에 반영

    # 전체 영상 예상 길이 계산
    total_duration = sum(seg.get('duration_seconds', 0) for seg in stage2_data['segments'])
    stage2_data['total_estimated_duration_seconds'] = total_duration

    return stage2_data # 처리된 딕셔너리 반환


# --- 예시 사용 (이 파일 자체를 직접 실행할 경우 - 테스트 목적) ---
if __name__ == "__main__":
    # 이 예제에서는 채널 정의를 별도 파일로 저장하고 사용합니다.
    # 실제 사용 시 여러분의 channel_definition.json 파일 경로를 지정해야 합니다.

    # 임시 채널 정의 파일을 생성하거나 기존 경로 사용
    EXAMPLE_CHANNEL_DEF_PATH = "./example_channel_definition.json" # 현재 디렉토리에 생성
    if not os.path.exists(EXAMPLE_CHANNEL_DEF_PATH):
         EXAMPLE_CHANNEL_DEF_DATA = {
           "definitionVersion": "1.1", "lastUpdated": "2025-04-23T15:07:19+09:00",
           "channelInfo": { "channelName": "예시 채널", "niche": "테스트 니치", "coreMessage": "테스트 메시지", "usp": "테스트 USP" },
            "targetAudience": { "primaryAgeRange": ["all"], "secondaryAgeRange": [], "interests": [], "needsOrPainPoints": [], "preferredContentStyle": [] },
            "channelIdentity": { "personalityAdjectives": [], "toneOfVoice": "존댓말", "forbiddenTopicsOrTones": [] },
            "contentStrategy": { "contentPillars": [], "primaryGoal": "", "secondaryGoals": [] },
           "shortsFormat": {
             "standardDurationSeconds": 30, "pacing": "빠름",
             "standardSegments": [
               { "segmentName": "Hook & Intro", "purpose": "소개", "styleNotes": "간결하게", "estimatedDurationSeconds": 5 },
               { "segmentName": "Main Point", "purpose": "핵심 내용", "styleNotes": "자세히", "estimatedDurationSeconds": 20 }
             ],
             "additionalSegments": [
                 {"segmentName": "CTA_Subscribe", "purpose": "구독 유도", "styleNotes": "구독해주세요!", "estimatedDurationSeconds": 3}
             ],
             "recurringElements": {}
            }
         }
         try:
             with open(EXAMPLE_CHANNEL_DEF_PATH, 'w', encoding='utf-8') as f:
                 json.dump(EXAMPLE_CHANNEL_DEF_DATA, f, indent=2, ensure_ascii=False)
             print(f"예시 채널 정의 파일 생성: {EXAMPLE_CHANNEL_DEF_PATH}")
         except Exception as e:
              print(f"오류: 예시 채널 정의 파일 생성 중 오류: {e}")
              EXAMPLE_CHANNEL_DEF_PATH = None # 파일 생성 실패 시 경로 무효화


    # 결과를 저장할 임시 디렉토리
    TEST_OUTPUT_DIR = "./test_generated_data"


    example_topic = {
        "title": "고양이가 그르렁거리는 놀라운 이유 3가지",
        "detail": [
            "고양이가 그르렁거리는 이유가 뭘까요? 행복할 때만 그르렁거리는 것은 아닙니다.",
            "통증을 완화하는 효과도 있습니다. 낮은 주파수의 진동이 치유를 돕는다는 연구 결과가 있습니다.",
            "새끼 고양이와 어미 고양이의 소통 수단입니다. 어미는 그르렁거려 새끼를 안심시키고, 새끼는 어미에게 자신의 위치나 상태를 알립니다.",
            "사람에게도 스트레스 감소 효과가 있다고 알려져 있습니다."
        ]
    }

    print("\n--- generate_initial_script 함수 테스트 ---")
    if EXAMPLE_CHANNEL_DEF_PATH:
        # output_dir 인자 추가하여 호출
        parsed_script_data = generate_initial_script(example_topic, EXAMPLE_CHANNEL_DEF_PATH, TEST_OUTPUT_DIR)

        if parsed_script_data:
            print(f"\n성공: 생성 및 파싱 완료. 반환된 데이터:")
            print(json.dumps(parsed_script_data, indent=2, ensure_ascii=False))

            print("\n--- process_stage2 함수 테스트 ---")
            # Stage 2 처리 함수 호출 (로드된 channel_def 사용)
            try:
                with open(EXAMPLE_CHANNEL_DEF_PATH, 'r', encoding='utf-8') as f:
                     channel_def_for_stage2 = json.load(f)
            except Exception as e:
                 channel_def_for_stage2 = None
                 print(f"경고: Stage 2 테스트를 위해 채널 정의 파일 다시 로드 중 오류 발생: {e}")


            if channel_def_for_stage2:
                 stage2_result = process_stage2(parsed_script_data, channel_def_for_stage2)
                 print("\nStage 2 처리 결과:")
                 print(json.dumps(stage2_result, indent=2, ensure_ascii=False))
            else:
                 print("Stage 2 테스트를 위한 채널 정의 로드 실패.")

        else:
            print("\n실패: 스크립트 생성/파싱에 실패했습니다.")
    else:
         print("예시 채널 정의 파일이 없어 테스트를 건너뜀.")

    # 테스트 후 생성된 디렉토리 및 파일 정리 (선택 사항)
    # import shutil
    # if os.path.exists(TEST_OUTPUT_DIR):
    #      shutil.rmtree(TEST_OUTPUT_DIR)
    #      print(f"테스트 디렉토리 삭제: {TEST_OUTPUT_DIR}")
    # if os.path.exists(EXAMPLE_CHANNEL_DEF_PATH):
    #      os.remove(EXAMPLE_CHANNEL_DEF_PATH)
    #      print(f"예시 채널 정의 파일 삭제: {EXAMPLE_CHANNEL_DEF_PATH}")