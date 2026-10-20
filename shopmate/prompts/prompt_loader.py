from pathlib import Path


def load_prompt(file_name: str) -> str:
    """读取 shopmate/prompts/jinja2 下的提示词文件。"""
    prompt_path = (
        Path(__file__).parent / "jinja2" / f"{file_name}.jinja2"
    )
    return prompt_path.read_text(encoding="utf-8")
