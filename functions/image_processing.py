# PaMin/functions/image_processing.py

import os
import json
import requests
import time
import random # 랜덤 선택을 위해 추가
import base64
import mimetypes
import re
from pathlib import Path
from typing import List, Optional, Dict, Any

# --- Dependencies ---
# pip install requests selenium webdriver-manager langchain-google-genai langchain-core pillow python-dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException, WebDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions
# from webdriver_manager.chrome import ChromeDriverManager # Consider using this for easier driver management

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()
# TODO: Load API keys securely from environment variables or config file
TENOR_API_KEY = 'api_key_here'
GEMINI_API_KEY = 'api_key_here'

if not TENOR_API_KEY or TENOR_API_KEY == "YOUR_TENOR_API_KEY_HERE":
    print("경고: Tenor API 키가 설정되지 않았습니다. Meme 다운로드 기능이 제한될 수 있습니다.")
if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
    print("경고: Gemini API 키(GOOGLE_API_KEY)가 설정되지 않았습니다. 이미지 분석 기능이 제한될 수 있습니다.")

# --- Helper Functions ---
# (_setup_chrome_driver 함수는 이전과 동일하게 유지)
def _setup_chrome_driver():
    """Sets up and returns a Chrome WebDriver instance (Headless by default)."""
    options = ChromeOptions()
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    options.add_argument(f'user-agent={user_agent}')
    options.add_argument("--start-maximized")
    # options.add_argument("--headless") # User-provided code doesn't use headless, comment out for now based on that code. Re-enable if needed.
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    try:
        # driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver = webdriver.Chrome(options=options) # Assumes chromedriver is in PATH or managed externally
        print("WebDriver 시작 완료.") # Removed (Headless) as it's commented out
        return driver
    except Exception as e:
        print(f"WebDriver 시작 오류: {e}")
        print("ChromeDriver가 시스템 PATH에 설치되어 있는지 또는 webdriver-manager를 사용하는지 확인하세요.")
        return None

# --- Image Download Functions ---
# (download_tenor_memes 함수는 이전과 동일하게 유지)
def download_tenor_memes(query: str, item_output_dir: str, max_results: int = 3) -> List[Optional[str]]:
    """Downloads GIFs from Tenor based on query and saves them to item_output_dir."""
    if not TENOR_API_KEY or TENOR_API_KEY == "YOUR_TENOR_API_KEY_HERE":
        print("Tenor API Key가 없어 Meme 다운로드를 건너<0xEB><0x81>니다.")
        return [None] * max_results
    search_url = f"https://tenor.googleapis.com/v2/search?q={query}&key={TENOR_API_KEY}&client_key=PaMin_App&limit={max_results}&media_filter=mediumgif"
    gif_paths = []
    Path(item_output_dir).mkdir(parents=True, exist_ok=True)
    print(f"  Tenor 검색 시작: '{query}' (최대 {max_results}개)")
    try:
        response = requests.get(search_url, timeout=15)
        response.raise_for_status(); data = response.json()
        if data.get('results'):
            for i, result in enumerate(data['results']):
                if len(gif_paths) >= max_results: break
                try:
                    gif_url = result['media_formats']['mediumgif']['url']; file_name = f"image_{i+1}.gif"; file_path = Path(item_output_dir) / file_name
                    gif_response = requests.get(gif_url, stream=True, timeout=10); gif_response.raise_for_status()
                    with open(file_path, 'wb') as f:
                        for chunk in gif_response.iter_content(chunk_size=8192): f.write(chunk)
                    gif_paths.append(str(file_path)); print(f"    -> Meme 다운로드 성공: {file_name}")
                except Exception as e: print(f"    (!) Meme 개별 다운로드 오류: {e}")
        while len(gif_paths) < max_results: gif_paths.append(None)
        print(f"  Tenor 검색 완료: {len([p for p in gif_paths if p])}개 다운로드.")
        return gif_paths
    except requests.exceptions.RequestException as e: print(f"  (!) Tenor API 요청 오류: {e}")
    except Exception as e: print(f"  (!) Tenor 처리 중 예상치 못한 오류: {e}")
    while len(gif_paths) < max_results: gif_paths.append(None)
    return gif_paths

# (download_google_images_final 함수는 이전과 동일하게 유지 - 사용자 제공 버전)
def download_google_images_final(query, output_dir, item_id, max_results=3):
    """
    Google 이미지 검색 후 (스크롤 없이) 라이선스 필터링하여 다운로드 (사용자 제공 버전)
    """
    print(f"--- 이미지 다운로드 시작 (스크롤 X, 라이선스 필터 O) --- [사용자 제공 버전] ---")
    if not query or not isinstance(query, str): print(f"오류: 'query'는 문자열이어야 합니다."); return []
    base_output_dir = output_dir
    item_path = os.path.join(base_output_dir)
    if not base_output_dir or not isinstance(base_output_dir, str): print(f"오류: 'output_dir'은 문자열이어야 합니다."); return []
    options = ChromeOptions()
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    options.add_argument(f'user-agent={user_agent}'); options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"]); options.add_experimental_option('useAutomationExtension', False)
    driver = None; image_paths = []; successful_fetches = 0; headers = {'User-Agent': user_agent}
    try:
        print("WebDriver 시작 중..."); driver = webdriver.Chrome(options=options); wait = WebDriverWait(driver, 15); print("WebDriver 시작 완료.")
        print(f"'{query}' 이미지 검색 페이지 접속 시도..."); driver.get(f'https://www.google.com/imghp?hl=ko'); time.sleep(random.uniform(1.0, 2.0)); print("페이지 접속 완료.")
        try:
            print("검색창 찾는 중..."); search_bar = wait.until(EC.presence_of_element_located((By.NAME, "q"))); search_bar.send_keys(query); time.sleep(random.uniform(0.5, 1.0)); search_bar.submit(); print("검색 실행 완료. 결과 로딩 대기...")
            first_thumbnail_selector = 'img.YQ4gaf:not([alt=""])'; wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, first_thumbnail_selector))); print("검색 결과 일부 로드됨."); time.sleep(random.uniform(1.0, 2.0))
        except Exception as e: print(f"오류: 검색 과정 실패: {e}"); raise # Re-raise to be caught by outer finally
        try:
            print("초기 로드된 썸네일 목록 찾는 중..."); thumbnails = driver.find_elements(By.CSS_SELECTOR, first_thumbnail_selector)
            if not thumbnails: print("오류: 검색 결과에서 썸네일을 찾을 수 없습니다."); raise ValueError("No thumbnails found")
            print(f"총 {len(thumbnails)}개의 초기 썸네일 찾음. 처리 시작...")
        except Exception as e: print(f"오류: 썸네일 목록 찾기 실패: {e}"); raise
        for i, thumbnail in enumerate(thumbnails):
            if successful_fetches >= max_results: print(f"목표한 {max_results}개 이미지 다운로드 완료."); break
            print(f"\n--- 썸네일 {i+1}/{len(thumbnails)} 처리 시작 ---")
            try:
                print(f"썸네일 {i+1}: 클릭 시도 (JS)..."); driver.execute_script("arguments[0].click();", thumbnail); print(f"썸네일 {i+1}: 클릭 완료. 큰 이미지 로딩 대기..."); time.sleep(random.uniform(2.5, 4.0))
                license_div_selector = "div.ippd7e"
                try:
                    license_divs = driver.find_elements(By.CSS_SELECTOR, license_div_selector)
                    if any(div.is_displayed() for div in license_divs): print(f"라이선스 정보 div ('{license_div_selector}') 발견/표시됨. 건너<0xEB><0x81>니다."); continue
                    else: print(f"라이선스 정보 div 없음 또는 숨겨짐. 다운로드 진행.")
                except Exception as e: print(f"경고: 라이선스 div 확인 중 오류 (무시하고 진행): {e}")
                img_src = None
                try:
                    print(f"썸네일 {i+1}: 큰 이미지 요소 기다리는 중..."); large_img_selector = 'img[jsname="kn3ccd"]'; img_element = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, large_img_selector))); print(f"썸네일 {i+1}: 큰 이미지 요소 찾음. 'src' 속성 가져오는 중...")
                    img_src_value = img_element.get_attribute('src')
                    if isinstance(img_src_value, str): img_src = img_src_value
                    else: print(f"경고: 썸네일 {i+1}: 'src' 값이 문자열이 아님.")
                except WebDriverException as e: print(f"WebDriver 오류 ('src' 가져오는 중): {e}")
                except (NoSuchElementException, TimeoutException): print(f"오류: 썸네일 {i+1}: 큰 이미지 요소를 찾거나 보이지 않음.")
                except Exception as e: print(f"오류: 썸네일 {i+1}: 'src' 속성 가져오는 중 예상치 못한 문제: {e}")
                if img_src and (img_src.startswith('http') or img_src.startswith('data:image')):
                    print(f"썸네일 {i+1}: 유효한 src 확인. 다운로드 시도...")
                    if img_src.startswith('data:image'):
                        try:
                            header, encoded = img_src.split(',', 1); mime_type = header.split(';')[0].split(':')[1]; extension = mimetypes.guess_extension(mime_type) or '.jpg'; file_name = f"image_{successful_fetches + 1}{extension}"
                            if not extension or len(extension) > 5: extension = '.jpg'
                            file_path = os.path.join(item_path, file_name);
                            with open(file_path, "wb") as f: f.write(base64.b64decode(encoded))
                            image_paths.append(str(file_path)); successful_fetches += 1; print(f"성공: 이미지 {successful_fetches}/{max_results} 저장 완료 (Base64): {file_path}")
                        except Exception as e: print(f"오류: Base64 이미지 처리 중 오류: {e}")
                    elif img_src.startswith('http'):
                        try:
                            time.sleep(random.uniform(0.5, 1.5)); response = requests.get(img_src, stream=True, timeout=15, headers=headers); response.raise_for_status(); content_type = response.headers.get('content-type'); extension = '.jpg'
                            if content_type: guessed_extension = mimetypes.guess_extension(content_type.split(';')[0]); extension = guessed_extension if guessed_extension and len(guessed_extension) <= 5 else '.jpg'
                            file_name = f"image_{successful_fetches + 1}{extension}"; file_path = os.path.join(item_path, file_name)
                            with open(file_path, "wb") as f:
                                for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
                            image_paths.append(str(file_path)); successful_fetches += 1; print(f"성공: 이미지 {successful_fetches}/{max_results} 저장 완료: {file_path}")
                        except requests.exceptions.RequestException as e: print(f"오류: 이미지 다운로드 실패 ({img_src[:50]}...): {e}")
                        except Exception as e: print(f"오류: 이미지 저장 실패: {e}")
                elif img_src: print(f"경고: 썸네일 {i+1}: 지원하지 않는 이미지 소스 형식.")
            except StaleElementReferenceException: print(f"오류: 썸네일 {i+1}: 처리 중 DOM 변경 감지.")
            except Exception as e: print(f"오류: 썸네일 {i+1}: 처리 중 예상치 못한 문제: {e}")
    except Exception as e: print(f"스크립트 실행 중 심각한 오류 발생: {e}")
    finally:
        if driver: print("WebDriver를 종료합니다."); driver.quit()
        print(f"--- 이미지 다운로드 종료 --- (총 {successful_fetches}개 이미지 다운로드)")
        while len(image_paths) < max_results: image_paths.append(None)
        return image_paths


# --- Image Analysis Function ---
# (analyze_image_relevance_langchain 함수는 이전과 동일하게 유지)
def analyze_image_relevance_langchain(image_paths: List[Optional[str]], chunk_text: str) -> Optional[str]:
    """Uses LangChain/Gemini to select the best image path based on relevance to chunk_text."""
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
        print("Gemini API Key가 없어 이미지 분석을 건너<0xEB><0x81>니다.")
        return next((p for p in image_paths if p and os.path.exists(p)), None)
    valid_image_paths = [p for p in image_paths if p and os.path.exists(p)]
    if not valid_image_paths: print("  분석할 유효한 이미지가 없습니다."); return None
    print(f"  Gemini 분석 시작: '{chunk_text[:30]}...' (이미지 {len(valid_image_paths)}개)")
    try:
        model = ChatGoogleGenerativeAI(model="models/gemini-1.5-flash", google_api_key=GEMINI_API_KEY)
        prompt_text = (
             f"다음 이미지들을 주어진 텍스트 '{chunk_text}'와 비교하여, 유튜브 숏츠 영상에 사용하기에 가장 적합한 이미지 **하나**를 선택하고, "
             f"그 이유를 간략히 설명해주세요. 관련성, 흥미 유발, 품질, 명확성 등을 고려하여 각 이미지에 100점 만점 점수를 부여하고 "
             f"가장 높은 점수의 이미지 번호와 점수를 명확히 제시해주세요.\n\n"
             f"주의: 이미지에 워터마크(로고, 텍스트 오버레이 등)가 명확히 보인다면, 해당 이미지는 선택하지 말고 낮은 점수를 주세요.\n\n"
             f"### 중요 출력 형식 ###\n"
             f"1. 각 이미지(Image 1, Image 2, ...)에 대한 평가와 점수를 간략히 서술합니다.\n"
             f"2. 답변의 **가장 마지막 줄**에는, 당신이 최종 선택한 이미지의 번호(N)만을 **'image : N'** 형식으로 **정확히** 작성해주세요.\n"
             f"   (예시: 만약 3번 이미지를 선택했다면, 마지막 줄은 'image : 3' 이어야 합니다.)\n"
             f"3. 마지막 줄 ('image : N') 뒤에는 **어떠한 추가 텍스트, 설명, 줄바꿈도 절대 포함하지 마세요.**"
         )
        content_list = [{"type": "text", "text": prompt_text}]
        original_indices_map = {}
        processed_image_count = 0
        for i, path in enumerate(valid_image_paths):
            try:
                with open(path, "rb") as image_file: image_data = image_file.read()
                base64_image = base64.b64encode(image_data).decode("utf-8")
                mime_type, _ = mimetypes.guess_type(path); mime_type = mime_type or "image/jpeg"
                content_list.append({"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}})
                content_list.append({"type": "text", "text": f"\nImage {processed_image_count + 1}:"})
                original_indices_map[processed_image_count] = i; processed_image_count += 1
            except FileNotFoundError: print(f"    (!) 분석용 이미지 로드 실패 (파일 없음): {os.path.basename(path)}")
            except Exception as e: print(f"    (!) 분석용 이미지 처리 오류: {os.path.basename(path)} ({e})")
        if processed_image_count == 0: print("  분석 가능한 이미지를 처리하지 못했습니다."); return None
        message = HumanMessage(content=content_list); response = model.invoke([message]); llm_response_text = response.content.strip()
        print(f"    -> Gemini 응답 받음 (일부): {llm_response_text[:100]}...")
        selected_original_index = None
        try:
            lines = llm_response_text.split('\n'); last_line = lines[-1].strip(); match = re.match(r"image\s*:\s*(\d+)", last_line, re.IGNORECASE)
            if match:
                response_image_index_1_based = int(match.group(1)); response_image_index_0_based = response_image_index_1_based - 1
                if response_image_index_0_based in original_indices_map:
                    selected_original_index = original_indices_map[response_image_index_0_based]; print(f"    -> 분석 결과: 이미지 {response_image_index_1_based} 선택됨 (원본 인덱스: {selected_original_index})")
                else: print(f"    (!) Gemini가 유효하지 않은 이미지 번호({response_image_index_1_based})를 반환했습니다.")
            else: print(f"    (!) Gemini 응답 마지막 줄 형식이 'image : N'이 아닙니다: '{last_line}'")
        except Exception as e: print(f"    (!) Gemini 응답 파싱 오류: {e}")
        if selected_original_index is not None and selected_original_index < len(valid_image_paths): return valid_image_paths[selected_original_index]
        else: print("    -> 최종 선택 실패 또는 무효. 첫 번째 유효 이미지로 대체합니다."); return valid_image_paths[0] if valid_image_paths else None
    except Exception as e: print(f"  (!) 이미지 분석 함수 오류: {e}"); return next((p for p in valid_image_paths), None)


# --- Main Processing Function ---
def process_visual_plan(visual_plan_file_path: str, episode_path: str, images_per_item: int = 3) -> Optional[str]:
    """
    Processes a visual plan JSON, downloads images/memes, selects the best one
    (Gemini for reference, Random for meme), and saves the updated plan.
    """
    print(f"\n--- 시각 자료 계획 처리 시작 (Meme: Random, Reference: Gemini) ---")
    print(f"  입력 파일: {visual_plan_file_path}")
    print(f"  에피소드 경로: {episode_path}")

    try:
        with open(visual_plan_file_path, 'r', encoding='utf-8') as f: visual_plan_data = json.load(f)
        if not isinstance(visual_plan_data, list): print("  (!) 오류: 시각 자료 계획 파일이 리스트 형태가 아닙니다."); return None
    except FileNotFoundError: print(f"  (!) 오류: 시각 자료 계획 파일을 찾을 수 없습니다: {visual_plan_file_path}"); return None
    except json.JSONDecodeError: print(f"  (!) 오류: 시각 자료 계획 JSON 파싱 오류: {visual_plan_file_path}"); return None
    except Exception as e: print(f"  (!) 오류: 시각 자료 계획 파일 로딩 중 오류: {e}"); return None

    visuals_output_base_dir = Path(episode_path) / "downloaded_visuals"; visuals_output_base_dir.mkdir(parents=True, exist_ok=True)
    print(f"  이미지 저장 기본 경로: {visuals_output_base_dir}")
    processed_data = []

    for index, item in enumerate(visual_plan_data):
        item_id = f"chunk_{index + 1}"; chunk_text = item.get('chunk_text', ''); visual_info = item.get('visual')
        print(f"\n--- Chunk {index + 1}/{len(visual_plan_data)} 처리: '{chunk_text[:40]}...' ---")
        updated_item = item.copy(); downloaded_paths: List[Optional[str]] = [None] * images_per_item; selected_path: Optional[str] = None

        if visual_info and isinstance(visual_info, dict):
            query = visual_info.get('query'); visual_type = visual_info.get('type')
            if query and visual_type:
                item_output_dir = visuals_output_base_dir / item_id; item_output_dir.mkdir(parents=True, exist_ok=True)
                if visual_type == 'reference':
                    downloaded_paths = download_google_images_final(query, str(item_output_dir), item_id, max_results=images_per_item)
                elif visual_type == 'meme':
                    downloaded_paths = download_tenor_memes(query, str(item_output_dir), max_results=images_per_item)
                elif visual_type == 'generation': print("  -> 'generation' 타입은 현재 다운로드/선택을 지원하지 않습니다.")
                else: print(f"  -> 알 수 없는 visual 타입: '{visual_type}'")

                # --- Selection Logic ---
                valid_downloaded_paths = [p for p in downloaded_paths if p and os.path.exists(p)]
                if valid_downloaded_paths:
                    if visual_type == 'reference':
                        print(f"  -> 'reference' 타입: Gemini 분석으로 최적 이미지 선택 시도...")
                        selected_path = analyze_image_relevance_langchain(valid_downloaded_paths, chunk_text)
                        if selected_path: print(f"  -> Gemini 선택: {os.path.basename(selected_path)}")
                        else: print(f"  -> Gemini 분석/선택 실패.")
                    elif visual_type == 'meme':
                        print(f"  -> 'meme' 타입: 다운로드된 이미지 중 랜덤 선택...")
                        selected_path = random.choice(valid_downloaded_paths) # 랜덤 선택
                        print(f"  -> 랜덤 선택: {os.path.basename(selected_path)}")
                    # else: generation or unknown type - selected_path remains None
                else:
                    print("  -> 다운로드된 유효 이미지가 없어 선택을 건너<0xEB><0x81>니다.")
                # --- End Selection Logic ---

            else: print(f"  (!) 경고: 필수 정보(query 또는 type) 누락됨.")
        else: print(f"  (!) 경고: 'visual' 정보 누락 또는 형식 오류.")

        if 'visual' not in updated_item or not isinstance(updated_item['visual'], dict): updated_item['visual'] = {}
        updated_item['visual']['downloaded_local_paths'] = downloaded_paths
        updated_item['visual']['selected_local_path'] = selected_path # Store the final selected path

        processed_data.append(updated_item)

    output_json_filename = "visual_plan_with_selection.json"; output_json_filepath = Path(episode_path) / output_json_filename
    try:
        with open(output_json_filepath, 'w', encoding='utf-8') as outfile: json.dump(processed_data, outfile, indent=2, ensure_ascii=False)
        print(f"\n--- 시각 자료 계획 처리 완료 ---"); print(f"  최종 결과 저장됨: {output_json_filepath}"); return str(output_json_filepath)
    except Exception as e: print(f"  (!) 오류: 최종 결과 JSON 저장 실패: {e}"); return None

# --- Example Usage (for testing this module directly) ---
if __name__ == "__main__":
    # (이전과 동일하게 유지)
    print("--- image_processing.py 실행 (테스트 목적) ---")
    TEST_CHANNEL_ROOT = "./test_channels"; TEST_CHANNEL = "test_channel"; TEST_EPISODE_ID = "test_episode_001_meme_random"
    test_episode_path = Path(TEST_CHANNEL_ROOT) / TEST_CHANNEL / "episodes" / TEST_EPISODE_ID; test_episode_path.mkdir(parents=True, exist_ok=True)
    dummy_plan_path = test_episode_path / "visual_plan_output.json"
    dummy_plan_data = [
        {"chunk_text": "재미있는 고양이 밈", "visual": {"type": "meme", "query": "funny cat"}, "segment": {"index": 0, "type": "Hook"}, "_match_info": {}},
        {"chunk_text": "파리의 에펠탑 사진", "visual": {"type": "reference", "query": "Eiffel Tower Paris"}, "segment": {"index": 1, "type": "Trivia_1"}, "_match_info": {}},
        {"chunk_text": "대한민국 서울의 모습", "visual": {"type": "reference", "query": "Seoul South Korea"}, "segment": {"index": 1, "type": "Trivia_1"}, "_match_info": {}},
        {"chunk_text": "웃는 강아지 밈", "visual": {"type": "meme", "query": "smiling dog"}, "segment": {"index": 2, "type": "Wrap-up"}, "_match_info": {}}
    ]
    try:
        with open(dummy_plan_path, 'w', encoding='utf-8') as f: json.dump(dummy_plan_data, f, indent=2, ensure_ascii=False)
        print(f"테스트용 입력 파일 생성: {dummy_plan_path}")
        final_json_path = process_visual_plan(str(dummy_plan_path), str(test_episode_path), images_per_item=2)
        if final_json_path: print(f"\n테스트 실행 성공. 최종 결과 파일: {final_json_path}")
        else: print("\n테스트 실행 실패.")
    except Exception as e: print(f"테스트 실행 중 오류: {e}")
    # import shutil; shutil.rmtree(TEST_CHANNEL_ROOT)