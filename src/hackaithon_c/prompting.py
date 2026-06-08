from __future__ import annotations

from .schema import Problem


SYSTEM_PROMPT = """Bạn giải bài trắc nghiệm tiếng Việt.
Quy tắc bắt buộc:
- Chỉ dùng thông tin trong đề bài và các lựa chọn đã cho.
- Chọn đáp án đúng nhất trong các lựa chọn.
- Không giải thích.
- Trả về đúng một chữ cái in hoa trong tập lựa chọn hợp lệ."""


def build_user_prompt(problem: Problem) -> str:
    options = "\n".join(
        f"{letter}. {choice}"
        for letter, choice in zip(problem.allowed_letters, problem.choices, strict=False)
    )
    return (
        "Đề bài:\n"
        f"{problem.question}\n\n"
        "Các lựa chọn:\n"
        f"{options}\n\n"
        f"Chỉ trả về một chữ cái trong: {', '.join(problem.allowed_letters)}."
    )


def build_verifier_prompt(problem: Problem, candidate_answer: str) -> str:
    options = "\n".join(
        f"{letter}. {choice}"
        for letter, choice in zip(problem.allowed_letters, problem.choices, strict=False)
    )
    candidate_text = ""
    if candidate_answer in problem.allowed_letters:
        index = problem.allowed_letters.index(candidate_answer)
        candidate_text = problem.choices[index]
    return (
        "Bạn là bước kiểm định đáp án trắc nghiệm.\n"
        "Hãy đọc lại đề, so sánh đáp án ứng viên với các lựa chọn, rồi trả về "
        "một chữ cái đúng nhất. Nếu ứng viên đúng, giữ nguyên chữ cái đó.\n\n"
        "Đề bài:\n"
        f"{problem.question}\n\n"
        "Các lựa chọn:\n"
        f"{options}\n\n"
        f"Đáp án ứng viên: {candidate_answer}. {candidate_text}\n\n"
        f"Chỉ trả về một chữ cái trong: {', '.join(problem.allowed_letters)}."
    )
