def extract_final_line(llm_text: str) -> str:
    lines = llm_text.strip().split("\n")

    # reverse loop = last meaningful line
    for line in reversed(lines):
        line = line.strip()
        if line and not line.lower().startswith(("thinking", "...")):
            return line

    return ""
