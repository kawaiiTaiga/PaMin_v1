# PaMin/functions/visual_generation.py
import os
import json
import random # Not used currently
import datetime # Not used currently
import pytz # Not used currently
import re
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional

# --- Required libraries ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableSequence
from pydantic import BaseModel, Field, ValidationError
from thefuzz import fuzz # For fuzzy matching

# --- Configuration ---
load_dotenv()
# TODO: Use os.getenv("GOOGLE_API_KEY") for better security
GOOGLE_API_KEY = 'api_key_here' # User requested to keep this for now
if GOOGLE_API_KEY is None:
    print("경고: GOOGLE_API_KEY 환경 변수를 설정해주세요.")
    # Consider appropriate error handling if key is missing

# --- Pydantic models definition (Stage 2 LLM output) ---
class VisualSuggestionData(BaseModel):
    type: str = Field(description="'meme' or 'reference' or 'generation'") # Added 'generation' based on prompt
    query: str = Field(description="검색 쿼리 또는 키워드")

class VisualChunkOutput(BaseModel):
    chunk_text: str = Field(description="LLM이 나눈 스크립트 구(chunk), 최소 4단어 이상")
    visual: VisualSuggestionData = Field(description="해당 구에 대한 시각 자료 제안 객체")

# --- Helper function to load prompt ---
def load_prompt_from_file(prompt_file_path: str) -> Optional[str]:
    """Loads the prompt template from a specified file."""
    try:
        with open(prompt_file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"    오류: 프롬프트 파일을 찾을 수 없습니다: {prompt_file_path}")
        return None
    except Exception as e:
        print(f"    프롬프트 파일 로딩 중 오류 발생: {e}")
        return None

# --- Main Function to Generate Visual Plan ---
def generate_visual_plan_from_json_file(
    json_file_path: str,
    prompt_file_path: str # Path to the visual planner prompt file
    ) -> List[Dict[str, Any]]:
    """
    Load video script data from a JSON file, generate visual suggestions using an LLM
    (with prompt loaded from file), map chunks back to segments using fuzzy matching,
    and return the validated visual plan as a flat list.

    Args:
        json_file_path: Path to the JSON file containing the script data
                        (expected structure: {"title": "...", "segments": [...]}).
        prompt_file_path: Path to the text file containing the visual planner prompt.

    Returns:
        A list of dictionaries, where each dictionary contains a script chunk,
        its suggested visual material, and mapping info to the original segment.
        Returns an empty list if processing fails.
    """
    print(f"\n--- Visual Plan Generation Started from file: {json_file_path} ---")

    # --- 1. Load and Parse Input JSON ---
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            parsed_data_stage1 = json.load(f)
        print("    Input JSON file loaded successfully.")
    except FileNotFoundError:
        print(f"    오류: 스크립트 파일을 찾을 수 없습니다: {json_file_path}")
        return []
    except json.JSONDecodeError:
        print(f"    오류: 스크립트 JSON 파일을 파싱할 수 없습니다: {json_file_path}")
        return []
    except Exception as e:
        print(f"    스크립트 파일 로딩 중 예상치 못한 오류 발생: {e}")
        return []

    if not isinstance(parsed_data_stage1, dict) or "title" not in parsed_data_stage1 or "segments" not in parsed_data_stage1:
        print("    오류: 스크립트 JSON 파일 형식이 예상과 다릅니다 ('title' 또는 'segments' 키가 없습니다).")
        return []

    selected_tmi_topic = parsed_data_stage1.get("title", "알 수 없는 TMI")
    original_segments_list = parsed_data_stage1.get("segments", [])

    if not original_segments_list:
        print("    경고: 'segments' 리스트가 비어 있습니다. 처리할 스크립트가 없습니다.")
        return []

    # --- 2. Prepare Full Script with Markers ---
    full_script_with_marker = ""
    segment_start_marker_template = "[{segment_type}]"
    segment_end_marker_template = "[{segment_type} END]"
    hook_end_marker = " `` "

    for i, segment in enumerate(original_segments_list):
        segment_script = segment.get("script", "")
        segment_type = segment.get("type", "unknown")
        full_script_with_marker += f"{segment_start_marker_template.format(segment_type=segment_type)}\n{segment_script}\n{segment_end_marker_template.format(segment_type=segment_type)}"
        if i == 0:
            full_script_with_marker += f"\n{hook_end_marker}\n"
        if i < len(original_segments_list) - 1:
            full_script_with_marker += "\n\n"

    full_script_with_marker = full_script_with_marker.strip()
    print(f"--- 전체 스크립트 준비 완료 (마커 포함) ---")

    # --- 3. Load Prompt ---
    visual_planner_prompt_template = load_prompt_from_file(prompt_file_path)
    if visual_planner_prompt_template is None:
        print("    오류: 프롬프트 로딩 실패로 시각 계획 생성을 중단합니다.")
        return []
    print("    Visual planner prompt loaded successfully.")

    # --- 4. LLM and Parser Setup ---
    if GOOGLE_API_KEY is None:
        print("    오류: GOOGLE_API_KEY가 설정되지 않아 LLM을 초기화할 수 없습니다.")
        return []

    try:
        llm_stage2 = ChatGoogleGenerativeAI(
            model='models/gemini-2.0-flash', # Using 1.5 Pro as requested in prompt analysis
            api_key=GOOGLE_API_KEY,
            temperature=0.8,
            convert_system_message_to_human=True
        )
        print("    Stage 2 LLM 초기화 완료 (gemini-2.0-flash).")
    except Exception as e:
        print(f"    Stage 2 LLM 초기화 오류: {e}")
        return []

    output_parser_stage2 = StrOutputParser()
    visual_planner_prompt = ChatPromptTemplate.from_template(visual_planner_prompt_template)

    # --- 5. Define Chain ---
    visual_planner_chain: RunnableSequence[dict, str] = visual_planner_prompt | llm_stage2 | output_parser_stage2

    # --- 6. Execute LLM Call ---
    final_visual_plan_list_raw = [] # LLM raw output parsed as list
    print(f"\n--- Stage 2: LLM 호출 시작 ---")
    try:
        response_str: str = visual_planner_chain.invoke({
            "full_script_with_marker": full_script_with_marker,
            "tmi_topic": selected_tmi_topic,
        })
        print(f"    LLM 응답 수신 완료.")

        # Parse LLM response (JSON list string)
        try:
            # Clean potential markdown code block markers
            if response_str.strip().startswith("```json"):
                response_str = re.sub(r"^```json\s*", "", response_str.strip(), flags=re.IGNORECASE)
                response_str = re.sub(r"\s*```$", "", response_str.strip())
            elif response_str.strip().startswith("```"): # Handle cases with just ```
                 response_str = re.sub(r"^```\s*", "", response_str.strip())
                 response_str = re.sub(r"\s*```$", "", response_str.strip())


            suggestions_list_raw = json.loads(response_str)

            if isinstance(suggestions_list_raw, list):
                for item_raw in suggestions_list_raw:
                    # Validate each item using Pydantic
                    try:
                        visual_chunk = VisualChunkOutput(**item_raw)
                        final_visual_plan_list_raw.append(visual_chunk.dict())
                    except ValidationError as pydantic_err:
                        print(f"    경고: LLM 응답 항목 Pydantic 검증 실패: {item_raw} - 오류: {pydantic_err}")
                    except Exception as item_parse_err:
                        print(f"    경고: LLM 응답 항목 처리 중 오류: {item_raw} - 오류: {item_parse_err}")
                print(f"\n    -> 총 {len(final_visual_plan_list_raw)}개 시각 자료 제안 파싱/검증 완료.")
            else:
                print(f"    오류: LLM 응답이 유효한 JSON 리스트 형태가 아닙니다.")

        except json.JSONDecodeError as json_err:
            print(f"    오류: LLM 응답 JSON 파싱 실패 - {json_err}")
            print(f"    LLM 원본 출력 (일부):\n{response_str[:500]}...")
        except Exception as parse_err:
            print(f"    오류: 제안 데이터 처리/검증 중 오류 - {parse_err}")

    except Exception as e:
        print(f"    오류: LLM 호출 또는 처리 중 오류 발생 - {e}")
        return [] # LLM call failed, cannot proceed

    # --- 7. Map LLM Chunks back to Original Segments (Fuzzy Matching) ---
    print("\n--- Chunk 매핑 시작 (Fuzzy Matching) ---")
    if not final_visual_plan_list_raw:
        print("    LLM으로부터 유효한 시각 자료 제안을 받지 못해 매핑을 건너<0xEB><0x8A>니다.")
        return []

    # Prepare original script (concatenated) and segment boundaries
    full_script_concatenated = ""
    segment_boundaries = [] # List of (start_char_index, end_char_index, segment_index)
    current_char_index = 0
    for i, segment in enumerate(original_segments_list):
        script = segment.get("script", "")
        segment_start_index = current_char_index
        full_script_concatenated += script # Only concatenate the script text itself
        current_char_index += len(script)
        segment_end_index = current_char_index
        segment_boundaries.append((segment_start_index, segment_end_index, i))
        # Add a small separator to handle potential issues with chunks spanning segments exactly at the boundary
        if i < len(original_segments_list) - 1:
             full_script_concatenated += " " # Add space between original segments
             current_char_index += 1


    final_chunk_plan_with_segments = []
    current_search_pos = 0
    fuzzy_score_threshold = 75 # Adjusted threshold
    search_window_multiplier = 2.0 # Increased window size

    print(f"    원본 스크립트 길이: {len(full_script_concatenated)}, 매핑할 청크 수: {len(final_visual_plan_list_raw)}")
    print(f"    Fuzzy 매칭 임계값: {fuzzy_score_threshold}, 검색 창 배율: {search_window_multiplier}")

    for i, visual_chunk in enumerate(final_visual_plan_list_raw):
        chunk_text = visual_chunk.get("chunk_text", "")
        visual_suggestion = visual_chunk.get("visual")

        if not chunk_text or not visual_suggestion:
            print(f"    경고: 건너뛰는 청크 (텍스트 또는 시각 제안 없음): {visual_chunk} ({i+1}/{len(final_visual_plan_list_raw)})")
            continue

        # Normalize whitespace for better matching
        chunk_text_normalized = ' '.join(chunk_text.split())
        if not chunk_text_normalized:
             print(f"    경고: 정규화 후 청크 텍스트 비어있음 ({i+1}/{len(final_visual_plan_list_raw)})")
             continue


        best_match_pos = -1
        best_match_score = -1
        best_match_type = "None"
        best_match_end_pos = -1

        # Define search window more carefully
        # Start searching from current_search_pos
        window_start = current_search_pos
        # End search roughly where the chunk *might* end based on multiplier, bounded by script length
        window_end = min(current_search_pos + int(len(chunk_text_normalized) * search_window_multiplier) + 10, len(full_script_concatenated)) # Added buffer

        # --- Attempt 1: Exact match within window ---
        exact_pos = full_script_concatenated.find(chunk_text_normalized, window_start, window_end)
        if exact_pos != -1:
            best_match_pos = exact_pos
            best_match_score = 100 # Exact match score
            best_match_type = "Exact"
            best_match_end_pos = exact_pos + len(chunk_text_normalized)
            # print(f"     -> Exact Match Found for chunk \"{chunk_text_normalized[:20]}...\" at pos {best_match_pos}")

        # --- Attempt 2: Fuzzy match within window if exact failed ---
        if best_match_pos == -1:
            highest_fuzzy_score = -1
            best_fuzzy_pos = -1

            # Iterate within the calculated window
            # Ensure we don't go out of bounds when slicing
            for check_pos in range(window_start, window_end - len(chunk_text_normalized) + 1):
                 # Slice the concatenated script for comparison
                 segment_to_compare = full_script_concatenated[check_pos : check_pos + len(chunk_text_normalized)]
                 segment_to_compare_normalized = ' '.join(segment_to_compare.split()) # Normalize slice too

                 if not segment_to_compare_normalized: continue # Skip empty slices

                 # Use partial_ratio as LLM might slightly alter phrasing or length
                 current_score = fuzz.partial_ratio(chunk_text_normalized, segment_to_compare_normalized)

                 if current_score > highest_fuzzy_score:
                      highest_fuzzy_score = current_score
                      best_fuzzy_pos = check_pos

            if best_fuzzy_pos != -1 and highest_fuzzy_score >= fuzzy_score_threshold:
                best_match_pos = best_fuzzy_pos
                best_match_score = highest_fuzzy_score
                best_match_type = "Fuzzy"
                # Estimate end position based on original chunk length (less reliable)
                best_match_end_pos = best_match_pos + len(chunk_text_normalized)
                # print(f"     -> Fuzzy Match Found (Score: {best_match_score}) for chunk \"{chunk_text_normalized[:20]}...\" at pos {best_match_pos}")
            # else:
                 # No good match found within window
                 # print(f"     -> Match Failed (Best Fuzzy: {highest_fuzzy_score}) for chunk \"{chunk_text_normalized[:20]}...\"")
                 # pass # Keep best_match_pos as -1

        # --- Assign Segment based on best match start position ---
        assigned_segment_index = -1
        if best_match_pos != -1:
            for seg_start, seg_end, seg_idx in segment_boundaries:
                # Check if the *start* of the match falls within the segment boundaries
                if seg_start <= best_match_pos < seg_end:
                    assigned_segment_index = seg_idx
                    break
            # If match starts exactly at segment boundary due to added space, check previous segment end
            if assigned_segment_index == -1:
                 for seg_start, seg_end, seg_idx in segment_boundaries:
                      if seg_end == best_match_pos: # Match might start right after a segment ends
                           assigned_segment_index = seg_idx
                           break


        # --- Create and Append Output Item ---
        if assigned_segment_index != -1:
            original_segment = original_segments_list[assigned_segment_index]
            output_item = {
                "chunk_text": chunk_text, # Use original LLM chunk text
                "visual": visual_suggestion,
                "segment": {
                    "index": assigned_segment_index,
                    "type": original_segment.get("type", "unknown")
                },
                "_match_info": { # Optional debug info
                    "type": best_match_type,
                    "score": best_match_score,
                    "start_pos": best_match_pos,
                    "end_pos": best_match_end_pos,
                    "search_window": (window_start, window_end)
                }
            }
            final_chunk_plan_with_segments.append(output_item)

            # Update search position based on match end
            # Only advance if match_end_pos is valid and greater than current_search_pos
            if best_match_end_pos > current_search_pos:
                 current_search_pos = best_match_end_pos
            else:
                 # Fallback: advance by chunk length if end pos is weird or match failed
                 current_search_pos += len(chunk_text_normalized) + 1 # Add 1 to prevent getting stuck

            # print(f"     -> 매핑 완료: 청크 {i+1} -> 세그먼트 {assigned_segment_index} ({original_segment.get('type')}, Score: {best_match_score}). 다음 검색 위치: {current_search_pos}")

        else: # Match failed or segment assignment failed
            print(f"    오류: 청크 {i+1} \"{chunk_text_normalized[:30]}...\" 를 원본 스크립트에 매핑하지 못했습니다 (Type: {best_match_type}, Score: {best_match_score}).")
            # Advance search position by chunk length to avoid getting stuck
            current_search_pos += len(chunk_text_normalized) + 1


    print("\n--- Chunk 매핑 완료 ---")
    print(f"    최종 매핑된 청크 수: {len(final_chunk_plan_with_segments)}")


    # --- 8. Return the final list ---
    return final_chunk_plan_with_segments


# --- Example Usage ---
if __name__ == "__main__":
    # NOTE: These paths are examples and need to be adjusted for your environment
    # Example assuming the script runs from the PaMin root directory
    example_script_file = './channels/쿰쿰파민/episodes/workflow_basic_no_topic_20250425_142103/script_stage2_workflow_basic_no_topic_20250425_142103.json'
    example_prompt_file = './channels/쿰쿰파민/prompt/visual_planner_prompt.txt' # Assumes prompt file exists here

    print(f"--- Example Usage ---")
    print(f"Input Script JSON: {example_script_file}")
    print(f"Prompt File: {example_prompt_file}")

    # Ensure example files exist before running
    if not os.path.exists(example_script_file):
         print(f"오류: 예제 스크립트 파일을 찾을 수 없습니다: {example_script_file}")
    elif not os.path.exists(example_prompt_file):
         print(f"오류: 예제 프롬프트 파일을 찾을 수 없습니다: {example_prompt_file}")
    else:
        # Call the function with both file paths
        final_visual_chunk_plan = generate_visual_plan_from_json_file(
            example_script_file,
            example_prompt_file
        )

        # Print the final result structure
        print("\n--- 최종 시각 자료 계획 (매핑 포함) ---")
        # Use ensure_ascii=False to correctly display Korean characters
        print(json.dumps(final_visual_chunk_plan, indent=2, ensure_ascii=False))

        # Optionally save the output to a file
        if final_visual_chunk_plan:
             output_filename = os.path.join(os.path.dirname(example_script_file), "visual_plan_output.json")
             try:
                  with open(output_filename, 'w', encoding='utf-8') as outfile:
                       json.dump(final_visual_chunk_plan, outfile, indent=2, ensure_ascii=False)
                  print(f"\n✅ 결과가 다음 파일에 저장되었습니다: {output_filename}")
             except Exception as e:
                  print(f"\n❌ 결과를 파일에 저장하는 중 오류 발생: {e}")