"""Ask the indexed Qwen 3B chatbot from the command line."""

import sys

from app.chatbot import answer_with_qwen_3b


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    question = " ".join(sys.argv[1:]).strip()
    if not question:
        try:
            question = input("Question: ").strip()
        except EOFError:
            question = ""

    if not question:
        print("Question is empty.")
        return

    result = answer_with_qwen_3b(question)
    print(result.content)
    if result.warnings:
        print()
        print("Warnings:")
        for warning in result.warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
