# PaMin: AI 기반 유튜브 숏츠 자동 생성 프로그램

## 📖 개요

PaMin은 딥러닝 및 다양한 자동화 기술을 활용하여 유튜브 숏츠 영상 제작 과정을 자동화하는 파이썬 기반 프로그램입니다. 채널 설정, 토픽 선정, 스크립트 및 시각 자료 생성, 음성 합성, 최종 영상 편집에 이르기까지 콘텐츠 제작의 전반적인 워크플로우를 지원합니다. Streamlit을 사용하여 사용자 인터페이스(UI)를 제공하며, 사용자는 이를 통해 각 단계를 수동으로 제어하거나 자동 모드로 실행할 수 있습니다.

## 🌟 PaMin의 핵심: 유연한 워크플로우와 맞춤 제작

유튜브 숏츠 콘텐츠는 그 특성상 매우 다양하며, 각 채널과 영상의 목적에 따라 최적화된 제작 방식이 필요합니다. PaMin은 이러한 다양성을 이해하고 유연하게 대응할 수 있도록 설계되었습니다.

* **다양한 워크플로우 지원**: 현재 PaMin은 숏츠 제작에 필요한 핵심적인 기능들을 중심으로 기본적인 워크플로우를 제공하고 있습니다.
* **맞춤형 제작 가능**: PaMin의 모듈화된 구조는 특정 채널의 고유한 스타일이나 콘텐츠 특성에 맞춰 워크플로우를 수정하거나 새로운 기능을 추가하는 등 맞춤형 제작이 용이하도록 되어 있습니다.
* **문의**: PaMin을 활용한 맞춤형 숏츠 제작 자동화 시스템 구축 및 기타 문의사항은 **gyeongmingim478@gmail.com** 으로 연락주시기 바랍니다.
* **사용** : STREAMLIT을 활용한 GUI - 백엔드는 현재 부끄럽게도 많은 하드코딩으로 작동되고 있습니다... 실사용에 엄청나게 많은 애로사항이 예상됩니다.... 업데이트를 기다려주세요
## ✨ 주요 기능

* **채널 관리**: 다수의 유튜브 채널을 등록하고 각 채널별 특성(채널명, 타겟 시청자, 톤앤매너 등) 및 설정을 `channel_definition.json` 파일을 통해 관리합니다.
* **토픽 관리 및 생성**:
    * 채널별 토픽 아이디어를 `Topics.json`에 저장하고 관리합니다.
    * LLM(Google Gemini)과 `dcagent` 프레임워크를 활용하여 새로운 토픽 아이디어를 자동으로 생성하고, 기존 토픽과 병합하여 중복을 방지합니다.
    * 수동 또는 자동(FIFO, FILO, RANDOM 전략)으로 영상 제작에 사용할 토픽을 선정합니다.
* **스크립트 자동 생성**:
    * 선정된 토픽과 채널 정의를 기반으로 LangChain 및 Google Gemini 모델을 활용하여 유튜브 숏츠용 스크립트를 자동으로 생성합니다.
    * 생성된 스크립트는 세그먼트(Hook, Trivia, CTA 등)별로 구조화되며, 각 세그먼트의 예상 시간 등을 포함하여 상세 처리됩니다.
* **시각 자료 계획 및 수집**:
    * 생성된 스크립트를 분석하여 각 구절(Chunk)에 가장 효과적인 시각 자료(밈, 참고 이미지/영상)의 타입과 검색 쿼리를 LLM을 통해 제안받습니다.
    * 제안된 쿼리를 바탕으로 Tenor (GIF/밈) 또는 Google 이미지 검색(Selenium 활용)을 통해 실제 시각 자료를 자동으로 다운로드합니다.
    * 다운로드된 여러 후보 이미지 중 영상 내용과 가장 관련성 높은 이미지를 Google Gemini Vision 모델을 통해 분석하고 자동으로 선택하거나, 사용자가 수동으로 선택할 수 있습니다.
* **음성 생성 및 타임스탬프 매핑**:
    * Zonos TTS 모델을 활용하여 스크립트 각 문장에 대한 자연스러운 음성을 생성합니다.
    * 생성된 음성에 대해 OpenAI Whisper 모델을 사용하여 단어 수준의 타임스탬프를 추출합니다.
    * 추출된 타임스탬프를 원본 스크립트의 각 청크(chunk) 및 단어와 정교하게 매핑하여 자막 및 시각 자료 전환 타이밍의 정확도를 높입니다.
* **최종 영상 자동 편집**:
    * MoviePy 라이브러리를 사용하여 준비된 모든 요소(배경 영상, 선택된 시각 자료, 생성된 음성, 자막)를 종합하여 최종 숏츠 영상을 자동으로 편집 및 생성합니다.
    * 영상 제목, 자막 스타일, 배경음악 볼륨 등 다양한 요소를 설정할 수 있습니다.
* **워크플로우 기반 작업 진행**:
    * `workflow.json` 파일에 정의된 단계별 워크플로우에 따라 작업이 진행됩니다.
    * 각 단계는 Streamlit UI를 통해 시각적으로 표시되며, 사용자는 진행 상황을 확인하고 필요한 경우 수동으로 개입할 수 있습니다.
* **Streamlit 기반 사용자 인터페이스**:
    * 웹 브라우저를 통해 프로그램의 모든 기능을 손쉽게 사용하고 관리할 수 있는 UI를 제공합니다.

## 📂 프로젝트 구조

```
PaMin/
├── Pamin.py                     # 메인 Streamlit 애플리케이션 파일
├── channels/                    # 채널별 데이터 저장 디렉토리
│   └── [channel_name]/          # 특정 채널 작업 디렉토리
│       ├── channel_definition.json # 채널 기본 설정 (타겟, 톤앤매너 등)
│       ├── Topics.json             # 채널 토픽 목록 (아이디어)
│       ├── tts_config.json         # Zonos TTS, Whisper 설정
│       ├── base_video.mp4          # (선택) 영상 배경 기본 소스
│       ├── bgm.mp3                 # (선택) 영상 배경 음악
│       ├── thumbnail.png/jpg       # (선택) 채널 썸네일
│       ├── prompt/                 # LLM 프롬프트 저장 디렉토리
│       │   └── visual_planner_prompt.txt
│       └── episodes/               # 생성된 에피소드(영상 프로젝트) 저장 디렉토리
│           └── [episode_id]/       # 각 에피소드별 파일들 (스크립트, 이미지, 오디오, 최종 영상 등)
├── functions/                   # 핵심 로직 및 기능 모듈
│   ├── dcagent/                 # 아이디어 생성/수렴 에이전트 관련 모듈 (사용자 정의 라이브러리)
│   ├── audio_generation.py      # 음성 생성 및 타임스탬프
│   ├── image_processing.py    # 이미지 검색, 다운로드, 분석
│   ├── script_generation.py   # LLM 기반 스크립트 생성
│   ├── topic_generation.py    # LLM 기반 토픽 아이디어 생성
│   ├── topic_utils.py         # Topics.json 파일 처리 유틸리티
│   ├── video_generation_basic.py # 최종 영상 편집/생성
│   └── visual_generation.py   # LLM 기반 시각 자료 계획 생성
├── views/                       # Streamlit UI 뷰(페이지) 모듈
│   ├── auto_settings_view.py
│   ├── channel_settings_view.py
│   ├── welcome.py
│   └── workflow_view.py
├── workflows/                   # 워크플로우 정의 및 단계별 UI 렌더링
│   └── workflow_basic/          # 'basic' 워크플로우 예시
│       ├── step_1_topic.py
│       ├── step_2_script.py
│       ├── step_3_image_plan.py
│       ├── step_4_image_search.py
│       ├── step_5_audio.py
│       ├── step_6_video_generation.py
│       └── workflow.json        # 워크플로우 단계 정의
└── README.md                    # (현재 파일)
```

## 🚀 시작하기

### 1. 사전 준비 사항

* **Python**: 버전 3.9 이상 권장
* **FFmpeg**: MoviePy 및 오디오 처리를 위해 시스템에 설치 및 PATH 설정 필요 ([FFmpeg 다운로드](https://ffmpeg.org/download.html))
* **eSpeak NG**: Zonos TTS의 Phonemizer가 의존하는 라이브러리입니다. Windows 사용자의 경우, `C:\Program Files\eSpeak NG\libespeak-ng.dll` 경로에 설치하거나 `PHONEMIZER_ESPEAK_LIBRARY` 환경 변수를 설정해야 할 수 있습니다. ([eSpeak NG 다운로드](https://github.com/espeak-ng/espeak-ng/releases))
* **Google Chrome 및 ChromeDriver**: Selenium을 통한 이미지 스크래핑에 필요합니다. ChromeDriver는 시스템 PATH에 있거나 `webdriver-manager`를 통해 관리될 수 있습니다.

### 2. 설치

1.  **저장소 복제**:
    ```bash
    git clone [https://github.com/your-username/PaMin.git](https://github.com/your-username/PaMin.git)
    cd PaMin
    ```

2.  **가상 환경 생성 및 활성화** (권장):
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **필수 라이브러리 설치**:
    `requirements.txt` 파일이 있다면 해당 파일을 사용합니다. 없다면, 주요 라이브러리는 다음과 같습니다 (정확한 버전은 각 Python 파일의 import 문 확인 필요):
    ```bash
    pip install streamlit streamlit-ace langchain langchain-google-genai python-dotenv moviepy torch torchaudio openai-whisper librosa soundfile rapidfuzz zonos phonemizer Pillow requests selenium webdriver-manager thefuzz python-Levenshtein imageio
    ```
    * **torch/torchaudio**: 시스템(CPU/CUDA)에 맞는 버전을 설치하는 것이 중요합니다. [PyTorch 공식 웹사이트](https://pytorch.org/) 참고.
    * **dcagent**: 사용자 정의 라이브러리입니다. `functions/dcagent` 경로에 위치하며, 필요시 별도의 설치 과정이나 경로 설정이 필요할 수 있습니다. (링크: `[여기에 dcagent 라이브러리 GitHub 저장소 또는 관련 문서 링크 삽입]`)

4.  **API 키 설정**:
    프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 다음과 같이 API 키를 입력합니다.
    ```env
    GOOGLE_API_KEY="YOUR_GOOGLE_GEMINI_API_KEY"
    TENOR_API_KEY="YOUR_TENOR_API_KEY"
    ```
    * `script_generation.py` 및 `image_processing.py` 등에서 직접 API 키를 문자열로 넣는 부분은 보안상 `.env` 파일을 사용하도록 수정하는 것이 좋습니다.

### 3. 실행

1.  **Streamlit 앱 실행**:
    프로젝트 루트 디렉토리에서 다음 명령을 실행합니다.
    ```bash
    streamlit run Pamin.py
    ```
2.  웹 브라우저에서 Streamlit UI가 열리면 안내에 따라 채널을 설정하고 워크플로우를 시작합니다.

## 🛠️ 설정 및 사용법

1.  **채널 설정**:
    * UI의 '채널 설정' 메뉴에서 새로운 채널을 생성하거나 기존 채널을 선택합니다.
    * 채널 생성 시 `channels/[채널이름]` 디렉토리가 생성되며, 내부에 `channel_definition.json`, `Topics.json`, `tts_config.json` 등의 기본 설정 파일이 준비됩니다.
    * `channel_definition.json`: 채널의 성격, 타겟, 톤앤매너, 사용할 워크플로우 등을 정의합니다. UI에서 직접 편집 가능합니다.
    * `Topics.json`: 해당 채널에서 다룰 영상 토픽 아이디어 목록입니다. UI에서 직접 편집 및 LLM을 통한 자동 생성이 가능합니다.
    * `tts_config.json`: Zonos TTS 모델, Whisper 모델, 참조 음성 경로, 음성 속도 등을 설정합니다.
    * `prompt/visual_planner_prompt.txt`: 시각 자료 계획 생성 시 LLM에 전달될 프롬프트입니다.
    * 필요에 따라 채널 디렉토리(`channels/[채널이름]/`)에 `base_video.mp4`(배경용), `bgm.mp3`(배경음악) 파일을 직접 추가할 수 있습니다.

2.  **워크플로우 실행**:
    * 사이드바에서 'MANUAL' 또는 'AUTO' 모드를 선택합니다.
    * '작업 시작' 버튼을 누르면 `channel_definition.json`에 정의된 워크플로우가 시작됩니다. (기본: `workflow_basic`)
    * **1단계 (토픽 선정)**: MANUAL 모드에서는 기존 토픽 목록에서 직접 선택하거나 새 토픽을 LLM으로 생성하여 선택합니다. AUTO 모드에서는 설정된 전략(FIFO, FILO, Random)에 따라 미사용 토픽이 자동 선정됩니다.
    * **2단계 (스크립트 생성)**: 선택된 토픽을 기반으로 LLM이 숏츠 스크립트를 생성하고 세그먼트별로 처리합니다.
    * **3단계 (시각 자료 계획)**: 생성된 스크립트의 각 구절(Chunk)에 적합한 시각 자료(밈, 이미지 등) 타입과 검색 쿼리를 LLM이 제안합니다. MANUAL 모드에서 프롬프트 및 계획 수정이 가능합니다.
    * **4단계 (이미지 검색 및 선정)**: 계획된 쿼리로 이미지를 검색/다운로드하고, LLM(Gemini Vision) 또는 랜덤 선택을 통해 최종 이미지를 선정합니다. MANUAL 모드에서 사용자가 직접 이미지를 선택할 수 있습니다.
    * **5단계 (음성 생성)**: 스크립트 내용을 Zonos TTS로 음성 합성하고, Whisper로 타임스탬프를 추출하여 스크립트와 매핑합니다.
    * **6단계 (최종 영상 생성)**: 모든 요소를 종합하여 MoviePy로 최종 숏츠 영상을 만듭니다.

3.  **AUTO 모드 설정**:
    * UI의 'AUTO 설정' 메뉴에서 토픽 선정 전략(FIFO, FILO, RANDOM) 등을 설정할 수 있습니다.

## 🤖 주요 기술 스택

* **UI**: Streamlit
* **LLM 연동**: LangChain, Google Generative AI (Gemini)
* **TTS (Text-to-Speech)**: Zonos TTS
* **STT (Speech-to-Text) & 타임스탬핑**: OpenAI Whisper
* **영상 처리**: MoviePy, FFmpeg
* **이미지 검색/처리**: Selenium, Requests, Pillow, Gemini Vision
* **아이디어/데이터 관리**: `dcagent`(자체 제작한 라이브러리입니다. 토픽의 다양화를 위해 사용됩니다.https://github.com/kawaiiTaiga/dc_agent/tree/main))
* **기타**: fuzzywuzzy, rapidfuzz (유사도 매칭), python-dotenv (환경변수)

## 📄 라이선스

이 프로젝트는 [MIT 라이선스](https://opensource.org/licenses/MIT) 하에 배포됩니다. 이 라이선스는 매우 허용적인 라이선스로, 코드의 사용, 복제, 수정, 병합, 게시, 배포, 서브라이선스 부여 및 판매를 허용하며, 이러한 행위를 하는 모든 사람에게 소프트웨어를 제공할 수 있도록 합니다. 자세한 내용은 링크된 라이선스 전문을 참고하시기 바랍니다.

## 🙌 기여하기

xxx

(추가적인 기여 가이드라인이나 연락처 정보를 원하시면 이 부분을 수정해주세요. 예를 들어, "버그 리포트나 기능 제안은 GitHub 이슈를 통해 제출해주시면 감사하겠습니다. 기타 문의는 gyeongmingim478@gmail.com으로 연락주세요.")
```
