import streamlit as st
import os
import tempfile
from pydantic import BaseModel, Field
from google import genai
from google.genai import types


# ============================================================
# 0. 기본 설정
# ============================================================

MODEL_NAME = "gemini-3.6-flash"


# ============================================================
# 1. 페이지 설정
# ============================================================

st.set_page_config(
    page_title="건설 CM 제안서 기반 AI 면접 시스템",
    page_icon="🏗️",
    layout="wide"
)

st.title("🏗️ 건설사업관리(CM) 제안서 기반 AI 모의면접 시스템")

st.markdown(
    """
    **제안서(PDF) + 면접 녹음파일**을 활용하여
    실제 발주청 평가위원 관점에서 면접자의 기술답변과
    음성 전달력을 종합적으로 평가합니다.
    """
)


# ============================================================
# 2. 평가 결과 데이터 구조
# ============================================================

class QAPair(BaseModel):
    question: str = Field(
        description="면접관이 질문한 내용"
    )

    answer: str = Field(
        description="면접자가 답변한 내용"
    )

    technical_score: float = Field(
        description="해당 답변의 기술적 타당성 점수 1.0~5.0"
    )

    relevance_score: float = Field(
        description="제안서 내용 부합도 점수 1.0~5.0"
    )

    response_score: float = Field(
        description="질문 대응력 점수 1.0~5.0"
    )

    logic_score: float = Field(
        description="논리성 및 구체성 점수 1.0~5.0"
    )

    weakness: str = Field(
        description="해당 답변의 가장 중요한 부족사항"
    )

    improvement: str = Field(
        description="해당 답변을 개선하는 방법"
    )

    model_answer: str = Field(
        description="제안서와 연계한 고득점 모범답안"
    )


class AudioEvaluationSchema(BaseModel):

    transcript: str = Field(
        description="녹음파일 전체 음성의 텍스트 변환 결과"
    )

    qa_pairs: list[QAPair] = Field(
        description="녹음파일에서 추출한 질문과 답변 목록"
    )

    score_technical: float = Field(
        description="전체 기술적 타당성 점수 1.0~5.0"
    )

    score_relevance: float = Field(
        description="전체 제안서 내용 부합도 점수 1.0~5.0"
    )

    score_response: float = Field(
        description="전체 질문 대응력 점수 1.0~5.0"
    )

    score_logic: float = Field(
        description="전체 논리성 및 구체성 점수 1.0~5.0"
    )

    score_delivery: float = Field(
        description="전체 음성 전달력 점수 1.0~5.0"
    )

    total_score: float = Field(
        description="전체 종합점수 1.0~5.0"
    )

    delivery_analysis: str = Field(
        description=(
            "음성 전달력 분석. "
            "발화속도, 발음명료성, 반복표현, "
            "불필요한 추임새, 답변 구조, 자신감 있는 전달 등을 분석"
        )
    )

    strengths: list[str] = Field(
        description="면접자가 잘한 점 3~7개"
    )

    weaknesses: list[str] = Field(
        description="면접자가 개선해야 할 점 3~7개"
    )

    improvement_plan: list[str] = Field(
        description="실제 면접 전에 개선해야 할 구체적인 행동계획 3~7개"
    )

    overall_comment: str = Field(
        description="발주청 평가위원 관점의 종합평가 의견"
    )


# ============================================================
# 3. 세션 상태 초기화
# ============================================================

if "gemini_file_ref" not in st.session_state:
    st.session_state.gemini_file_ref = None

if "uploaded_file_name" not in st.session_state:
    st.session_state.uploaded_file_name = None

if "generated_questions" not in st.session_state:
    st.session_state.generated_questions = ""

if "audio_file_ref" not in st.session_state:
    st.session_state.audio_file_ref = None

if "audio_file_name" not in st.session_state:
    st.session_state.audio_file_name = None

if "audio_evaluation" not in st.session_state:
    st.session_state.audio_evaluation = None


# ============================================================
# 4. API Key 입력
# ============================================================

st.sidebar.header("🔑 Gemini API 설정")

api_key = st.sidebar.text_input(
    "Gemini API Key를 입력하세요",
    type="password"
)

if not api_key:

    st.info(
        "👈 왼쪽 사이드바에 Gemini API Key를 입력해 주세요."
    )

    st.stop()


# ============================================================
# 5. Gemini Client
# ============================================================

try:

    client = genai.Client(
        api_key=api_key
    )

except Exception as e:

    st.error(
        "Gemini Client 생성에 실패했습니다."
    )

    st.exception(e)

    st.stop()


# ============================================================
# 6. PDF 제안서 업로드
# ============================================================

st.sidebar.divider()

st.sidebar.header("📄 1. CM 제안서 업로드")

uploaded_file = st.sidebar.file_uploader(
    "사업수행능력제안서(SOQ/TP) PDF",
    type=["pdf"],
    key="proposal_uploader"
)


# ============================================================
# 7. PDF 업로드 처리
# ============================================================

if uploaded_file:

    if (
        st.session_state.uploaded_file_name
        != uploaded_file.name
    ):

        st.session_state.gemini_file_ref = None
        st.session_state.generated_questions = ""

        tmp_path = None

        with st.spinner(
            "📄 CM 제안서를 Gemini에 업로드하는 중입니다..."
        ):

            try:

                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=".pdf"
                ) as tmp_file:

                    tmp_file.write(
                        uploaded_file.getvalue()
                    )

                    tmp_path = tmp_file.name


                file_ref = client.files.upload(
                    file=tmp_path
                )


                st.session_state.gemini_file_ref = file_ref

                st.session_state.uploaded_file_name = (
                    uploaded_file.name
                )


                st.sidebar.success(
                    "✅ 제안서 업로드 완료"
                )


            except Exception as e:

                st.sidebar.error(
                    "❌ 제안서 업로드 실패"
                )

                st.sidebar.exception(e)


            finally:

                if (
                    tmp_path
                    and os.path.exists(tmp_path)
                ):

                    os.remove(tmp_path)


# ============================================================
# 8. 녹음파일 업로드
# ============================================================

st.sidebar.header("🎙️ 2. 면접 녹음파일 업로드")

audio_file = st.sidebar.file_uploader(
    "발표 및 질의응답 녹음파일",
    type=[
        "mp3",
        "wav",
        "m4a",
        "aac",
        "ogg",
        "flac",
        "webm"
    ],
    key="audio_uploader"
)


# ============================================================
# 9. 녹음파일 업로드 처리
# ============================================================

if audio_file:

    if (
        st.session_state.audio_file_name
        != audio_file.name
    ):

        st.session_state.audio_file_ref = None
        st.session_state.audio_evaluation = None

        audio_tmp_path = None

        with st.spinner(
            "🎙️ 면접 녹음파일을 Gemini에 업로드하는 중입니다..."
        ):

            try:

                file_extension = os.path.splitext(
                    audio_file.name
                )[1]

                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=file_extension
                ) as audio_tmp:

                    audio_tmp.write(
                        audio_file.getvalue()
                    )

                    audio_tmp_path = audio_tmp.name


                audio_ref = client.files.upload(
                    file=audio_tmp_path
                )


                st.session_state.audio_file_ref = (
                    audio_ref
                )

                st.session_state.audio_file_name = (
                    audio_file.name
                )


                st.sidebar.success(
                    "✅ 녹음파일 업로드 완료"
                )


            except Exception as e:

                st.sidebar.error(
                    "❌ 녹음파일 업로드 실패"
                )

                st.sidebar.exception(e)


            finally:

                if (
                    audio_tmp_path
                    and os.path.exists(audio_tmp_path)
                ):

                    os.remove(audio_tmp_path)


# ============================================================
# 10. 메인 화면
# ============================================================

if not st.session_state.gemini_file_ref:

    st.warning(
        "👈 먼저 왼쪽에서 **CM 제안서 PDF**를 업로드해 주세요."
    )

    st.stop()


st.success(
    f"📄 분석 대상 제안서: "
    f"{st.session_state.uploaded_file_name}"
)


# ============================================================
# 11. 면접 질문 자동 생성
# ============================================================

st.subheader("1️⃣ 제안서 기반 현장 특화 면접 질문")

if st.button(
    "🎲 제안서 기반 면접 질문 3개 추출하기"
):

    with st.spinner(
        "Gemini가 제안서의 핵심 기술 및 위험요소를 분석 중입니다..."
    ):

        question_prompt = """
        첨부된 건설사업관리(CM) 제안서 PDF를 면밀하게 분석하세요.

        실제 발주청 평가위원이 면접에서 질문한다고 가정하고,
        제안서 내용과 직접 연결되는 핵심 기술질문 3개를 작성하세요.

        다음 항목을 중점적으로 검토하세요.

        1. 주요 공법
        2. 고위험 공종
        3. 공정관리
        4. 품질관리
        5. 안전관리
        6. 민원관리
        7. 인접구조물 관리
        8. 공사비 관리
        9. 설계 VE
        10. 공기단축
        11. 특수공법
        12. 제안서의 차별화 전략

        질문은 실제 면접에서 평가위원이 사용할 수 있는
        구체적인 질문으로 작성하세요.

        단순한 일반론적 질문은 제외하세요.

        반드시 다음 형식으로 3개만 출력하세요.

        1. 질문
        2. 질문
        3. 질문
        """

        try:

            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[
                    st.session_state.gemini_file_ref,
                    question_prompt
                ]
            )

            st.session_state.generated_questions = (
                response.text
                if response.text
                else "질문 생성 결과가 없습니다."
            )

        except Exception as e:

            st.error(
                "❌ 질문 생성 중 오류가 발생했습니다."
            )

            st.exception(e)


if st.session_state.generated_questions:

    st.info(
        st.session_state.generated_questions
    )


# ============================================================
# 12. 텍스트 답변 평가
# ============================================================

st.divider()

st.subheader("2️⃣ 텍스트 답변 평가")

st.markdown(
    "녹음파일을 사용하지 않고 특정 질문과 답변을 직접 입력하여 평가할 수도 있습니다."
)

selected_q = st.text_area(
    "면접 질문",
    height=100
)

user_a = st.text_area(
    "면접자 답변",
    height=180
)


if st.button(
    "📊 텍스트 답변 평가하기"
):

    if not selected_q.strip():

        st.warning(
            "질문을 입력해 주세요."
        )

    elif not user_a.strip():

        st.warning(
            "답변을 입력해 주세요."
        )

    else:

        with st.spinner(
            "제안서와 답변을 비교하여 평가 중입니다..."
        ):

            text_eval_prompt = f"""
            당신은 건설사업관리(CM) 발주청 면접 평가위원입니다.

            첨부된 제안서 내용을 기준으로 지원자의 답변을 평가하세요.

            [면접 질문]
            {selected_q}

            [지원자 답변]
            {user_a}

            다음 항목을 평가하세요.

            1. 기술적 타당성
            2. 제안서 내용 부합도
            3. 질문 대응력
            4. 논리성 및 구체성

            각각 1~5점으로 평가하세요.

            답변의 부족한 부분과 개선방법을 구체적으로 작성하세요.

            제안서 내용을 활용한 고득점 모범답안도 작성하세요.
            """

            try:

                text_eval_response = client.models.generate_content(

                    model=MODEL_NAME,

                    contents=[
                        st.session_state.gemini_file_ref,
                        text_eval_prompt
                    ],

                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=AudioEvaluationSchema,
                        system_instruction="""
                        건설사업관리(CM) 발주청 면접 평가위원의
                        관점에서 객관적으로 평가하세요.

                        제안서에 실제로 존재하지 않는 내용을
                        제안서 내용인 것처럼 만들지 마세요.

                        기술적으로 부적절한 답변은 명확하게
                        감점하세요.
                        """
                    )
                )


                text_result = text_eval_response.parsed


                if text_result:

                    st.success(
                        "🎯 평가가 완료되었습니다."
                    )

                    c1, c2, c3, c4, c5 = st.columns(5)

                    c1.metric(
                        "종합",
                        f"{text_result.total_score:.1f}"
                    )

                    c2.metric(
                        "기술성",
                        f"{text_result.score_technical:.1f}"
                    )

                    c3.metric(
                        "제안서 부합",
                        f"{text_result.score_relevance:.1f}"
                    )

                    c4.metric(
                        "질문 대응",
                        f"{text_result.score_response:.1f}"
                    )

                    c5.metric(
                        "논리성",
                        f"{text_result.score_logic:.1f}"
                    )

                    st.subheader(
                        "💡 개선사항"
                    )

                    for item in text_result.weaknesses:

                        st.write(
                            f"- ⚠️ {item}"
                        )

                    st.subheader(
                        "📝 추천 모범답안"
                    )

                    st.info(
                        text_result.qa_pairs[0].model_answer
                        if text_result.qa_pairs
                        else text_result.overall_comment
                    )

                else:

                    st.error(
                        "AI 평가 결과를 받지 못했습니다."
                    )


            except Exception as e:

                st.error(
                    "❌ 텍스트 답변 평가 중 오류가 발생했습니다."
                )

                st.exception(e)


# ============================================================
# 13. 음성 면접 평가
# ============================================================

st.divider()

st.subheader("3️⃣ 🎙️ 면접 녹음파일 종합평가")

if not st.session_state.audio_file_ref:

    st.info(
        """
        👈 왼쪽 사이드바에서 면접 녹음파일을 업로드하면
        음성 기반 종합평가를 진행할 수 있습니다.

        지원 형식:
        MP3 / WAV / M4A / AAC / OGG / FLAC / WebM
        """
    )

else:

    st.success(
        f"🎙️ 현재 녹음파일: "
        f"{st.session_state.audio_file_name}"
    )


    st.markdown(
        """
        **평가 대상**

        - 제안서 이해도
        - 기술적 타당성
        - 질문 대응력
        - 논리성
        - 구체성
        - 제안서 연계성
        - 음성 전달력
        - 발화 속도
        - 반복 표현
        - 답변 구조
        """
    )


    if st.button(
        "🎧 녹음파일 전체 면접 평가하기"
    ):

        with st.spinner(
            "🎙️ 녹음 내용을 분석하고 있습니다. "
            "녹음 길이에 따라 시간이 걸릴 수 있습니다..."
        ):

            audio_prompt = """
            당신은 건설사업관리(CM) 용역의
            발주청 면접 평가위원입니다.

            첨부된 PDF는 해당 사업의 CM 제안서입니다.

            첨부된 오디오 파일은 실제 면접자의
            발표 및 질의응답 녹음입니다.

            PDF와 오디오를 함께 분석하여
            면접자의 실제 면접수행능력을 평가하세요.


            ====================================================
            1. 음성 전체를 정확하게 텍스트로 변환
            ====================================================

            먼저 오디오의 내용을 가능한 정확하게 전사하세요.

            면접자의 말투를 임의로 수정하지 말고
            실제 발화 내용을 최대한 유지하세요.

            "어...", "음...", "그러니까..." 등의
            반복 표현도 가능하면 유지하세요.


            ====================================================
            2. 질문과 답변 구분
            ====================================================

            녹음에 면접관과 면접자의 음성이 함께 있다면
            가능한 범위에서 질문과 답변을 구분하세요.

            면접관의 질문을 question으로,
            면접자의 답변을 answer로 작성하세요.

            명확하게 구분하기 어려운 경우에는
            문맥을 기준으로 합리적으로 구분하되
            추측을 사실처럼 표현하지 마세요.


            ====================================================
            3. 기술적 평가
            ====================================================

            각 답변에 대해 다음을 평가하세요.

            - 기술적 타당성
            - 제안서 내용 부합도
            - 질문 대응력
            - 논리성
            - 구체성

            각각 1~5점입니다.


            ====================================================
            4. 제안서 연계성 평가
            ====================================================

            면접자가 실제 제안서에 포함된

            - 공법
            - 공정관리 방안
            - 품질관리 방안
            - 안전관리 방안
            - 민원관리
            - 특수공법
            - VE
            - 공기단축 방안
            - CM 차별화 전략

            등을 얼마나 정확하게 활용했는지 평가하세요.


            ====================================================
            5. 음성 전달력 평가
            ====================================================

            오디오에서 확인할 수 있는 범위 내에서
            다음을 평가하세요.

            - 말하는 속도
            - 지나치게 빠른 발화
            - 지나치게 느린 발화
            - 발음의 명료성
            - 반복적인 추임새
            - "어", "음", "저희가", "그러니까" 등의
              불필요한 반복
            - 답변의 시작과 끝이 명확한지
            - 핵심부터 말하는지
            - 답변 구조가 명확한지
            - 장황한 설명이 많은지

            실제 오디오에서 확인할 수 없는 요소는
            임의로 평가하지 마세요.


            ====================================================
            6. 강점
            ====================================================

            면접자가 실제로 잘한 부분을
            구체적으로 3~7개 작성하세요.


            ====================================================
            7. 약점
            ====================================================

            실제 답변에서 부족했던 부분을
            구체적으로 3~7개 작성하세요.

            예:

            "구체성이 부족함"

            대신

            "인접 구조물 변위 발생 시 계측값 확인 이후
            어떤 기준으로 작업중지 및 발주처 보고를
            실시할지 설명하지 못함"

            처럼 작성하세요.


            ====================================================
            8. 개선계획
            ====================================================

            실제 면접 전에 바로 연습할 수 있는
            구체적인 개선방법을 작성하세요.


            ====================================================
            9. 모범답안
            ====================================================

            각각의 질문에 대해

            해당 제안서의 실제 내용을 활용한
            1~2분 분량의 고득점 모범답안을 작성하세요.

            일반적인 건설기술 설명보다
            해당 사업의 제안서와 연결된 답변을 우선하세요.


            ====================================================
            10. 종합평가
            ====================================================

            전체 면접을 발주청 평가위원의 관점에서
            종합적으로 평가하세요.

            특히 다음 질문에 답이 되도록 작성하세요.

            - 기술적으로 신뢰할 수 있는 답변을 했는가?
            - 제안서를 제대로 이해하고 있는가?
            - 질문에 정확하게 대응했는가?
            - 실제 CM 업무를 수행할 수 있는 답변인가?
            - 답변이 논리적인가?
            - 발표 및 답변 전달력이 적절한가?


            반드시 구조화된 평가 결과로 작성하세요.
            """


            try:

                audio_response = client.models.generate_content(

                    model=MODEL_NAME,

                    contents=[
                        st.session_state.gemini_file_ref,
                        st.session_state.audio_file_ref,
                        audio_prompt
                    ],

                    config=types.GenerateContentConfig(

                        response_mime_type="application/json",

                        response_schema=AudioEvaluationSchema,

                        system_instruction="""
                        당신은 건설사업관리(CM) 분야의
                        전문 면접 평가위원입니다.

                        첨부된 제안서와 실제 면접 녹음내용을
                        근거로 평가하세요.

                        제안서에 없는 내용을
                        제안서에 있었다고 추정하지 마세요.

                        음성에서 확인할 수 없는 내용을
                        임의로 판단하지 마세요.

                        평가점수는 반드시 1.0~5.0 범위로
                        작성하세요.

                        모든 평가는 구체적인 근거를 중심으로
                        작성하세요.
                        """
                    )
                )


                audio_result = audio_response.parsed


                if audio_result is None:

                    st.error(
                        "❌ 음성 평가 결과를 구조화된 형식으로 "
                        "받지 못했습니다."
                    )

                    st.text(
                        audio_response.text
                    )

                else:

                    st.session_state.audio_evaluation = (
                        audio_result
                    )


                    st.success(
                        "🎯 음성 면접 종합평가가 완료되었습니다!"
                    )


            except Exception as e:

                st.error(
                    "❌ 음성 면접 평가 중 오류가 발생했습니다."
                )

                st.exception(e)


# ============================================================
# 14. 음성 평가 결과 표시
# ============================================================

if st.session_state.audio_evaluation:

    result = st.session_state.audio_evaluation


    st.divider()

    st.header(
        "🏆 음성 면접 종합평가 결과"
    )


    # --------------------------------------------------------
    # 종합점수
    # --------------------------------------------------------

    c1, c2, c3, c4, c5, c6 = st.columns(6)


    c1.metric(
        "종합점수",
        f"{result.total_score:.1f} / 5.0"
    )


    c2.metric(
        "기술성",
        f"{result.score_technical:.1f}"
    )


    c3.metric(
        "제안서 부합",
        f"{result.score_relevance:.1f}"
    )


    c4.metric(
        "질문 대응",
        f"{result.score_response:.1f}"
    )


    c5.metric(
        "논리성",
        f"{result.score_logic:.1f}"
    )


    c6.metric(
        "전달력",
        f"{result.score_delivery:.1f}"
    )


    # --------------------------------------------------------
    # 종합평가
    # --------------------------------------------------------

    st.subheader(
        "📌 평가위원 종합의견"
    )

    st.info(
        result.overall_comment
    )


    # --------------------------------------------------------
    # 음성 전달력 분석
    # --------------------------------------------------------

    st.subheader(
        "🎙️ 음성 전달력 분석"
    )

    st.write(
        result.delivery_analysis
    )


    # --------------------------------------------------------
    # 강점
    # --------------------------------------------------------

    st.subheader(
        "👍 잘한 점"
    )

    for strength in result.strengths:

        st.write(
            f"✅ {strength}"
        )


    # --------------------------------------------------------
    # 약점
    # --------------------------------------------------------

    st.subheader(
        "⚠️ 개선이 필요한 점"
    )

    for weakness in result.weaknesses:

        st.write(
            f"🔸 {weakness}"
        )


    # --------------------------------------------------------
    # 개선계획
    # --------------------------------------------------------

    st.subheader(
        "🎯 면접 전 개선계획"
    )

    for plan in result.improvement_plan:

        st.write(
            f"➡️ {plan}"
        )


    # --------------------------------------------------------
    # 전체 녹음 텍스트
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "📝 녹음파일 전체 전사내용"
    )

    with st.expander(
        "전사내용 보기 / 숨기기"
    ):

        st.text_area(
            "음성 전사",
            result.transcript,
            height=400
        )


    # --------------------------------------------------------
    # 질문별 평가
    # --------------------------------------------------------

    st.divider()

    st.header(
        "🔍 질문별 상세 평가"
    )


    for index, qa in enumerate(
        result.qa_pairs,
        start=1
    ):

        with st.expander(
            f"질문 {index} | "
            f"기술성 {qa.technical_score:.1f} | "
            f"제안서 부합 {qa.relevance_score:.1f}"
        ):

            st.markdown(
                "### 🎤 면접관 질문"
            )

            st.write(
                qa.question
            )


            st.markdown(
                "### 🗣️ 면접자 답변"
            )

            st.write(
                qa.answer
            )


            st.markdown(
                "### 📊 세부점수"
            )

            q1, q2, q3, q4 = st.columns(4)


            q1.metric(
                "기술성",
                f"{qa.technical_score:.1f}"
            )


            q2.metric(
                "제안서 부합",
                f"{qa.relevance_score:.1f}"
            )


            q3.metric(
                "질문 대응",
                f"{qa.response_score:.1f}"
            )


            q4.metric(
                "논리성",
                f"{qa.logic_score:.1f}"
            )


            st.markdown(
                "### ⚠️ 부족한 부분"
            )

            st.warning(
                qa.weakness
            )


            st.markdown(
                "### 💡 개선방법"
            )

            st.write(
                qa.improvement
            )


            st.markdown(
                "### 🏆 고득점 모범답안"
            )

            st.info(
                qa.model_answer
            )


# ============================================================
# 15. 사용방법 안내
# ============================================================

st.divider()

with st.expander(
    "ℹ️ 사용방법"
):

    st.markdown(
        """
        ### ① CM 제안서 업로드

        왼쪽 사이드바에서 사업수행능력제안서(SOQ/TP)
        PDF를 업로드합니다.


        ### ② 면접질문 생성

        「제안서 기반 면접 질문 3개 추출하기」를 누르면
        제안서의 핵심 공법과 위험요소를 분석하여
        실전 면접 질문을 생성합니다.


        ### ③ 면접 녹음

        실제 발표 및 질의응답을 녹음합니다.


        ### ④ 녹음파일 업로드

        MP3, WAV, M4A, AAC, OGG, FLAC, WebM 파일을
        업로드합니다.


        ### ⑤ AI 면접 평가

        「녹음파일 전체 면접 평가하기」를 누르면

        - 음성 전사
        - 질문/답변 분석
        - 기술성 평가
        - 제안서 부합도 평가
        - 질문 대응력
        - 논리성
        - 음성 전달력
        - 강점
        - 약점
        - 개선계획
        - 질문별 모범답안

        을 자동으로 생성합니다.
        """
    )


# ============================================================
# 16. 하단 정보
# ============================================================

st.divider()

st.caption(
    f"🏗️ 건설사업관리(CM) 제안서 기반 AI 모의면접 시스템 | "
    f"Gemini Model: {MODEL_NAME}"
)