# -*- coding: utf-8 -*-
"""Виклик моделі зі структурованим виходом, валідацією та повторами (ЛР03 Р1).

Модель викликається через функцію-адаптер `ask`, щоб код не залежав від конкретного
постачальника. У цій роботі сесії виконувалися в інтерфейсі Claude Code (підзадачі), який не
дає програмного доступу до API, тому тут реалізовано два адаптери:

* `ReplayAsk`  — відтворює збережений сирий вихід із tmp/ (саме так отримані реальні дані роботи);
* `StubAsk`    — навмисно повертає невалідний JSON задану кількість разів, щоб показати повтори.

Запуск демонстрації:
    python tools/ask_model.py --demo
"""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
from typing import Callable, Type

from pydantic import BaseModel, ValidationError

HUB = pathlib.Path(__file__).resolve().parents[1]
FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class SchemaRetryError(RuntimeError):
    """Модель не повернула валідний JSON навіть після всіх повторів."""


def extract_json(text: str) -> str:
    """Моделі часто загортають JSON у markdown-огорожу — знімаємо її перед розбором."""
    m = FENCE.search(text)
    return (m.group(1) if m else text).strip()


def call_with_validation(ask: Callable[[str], str], prompt: str, schema: Type[BaseModel],
                         *, max_retries: int = 2, log_path: pathlib.Path | None = None,
                         model: str = "unknown", prompt_id: str = "unknown") -> BaseModel:
    """Викликає модель, валідує вихід за схемою і повторює до `max_retries` разів.

    При повторі до підказки додається опис помилки: модель бачить, що саме не підійшло,
    інакше вона з великою ймовірністю повторить ту саму помилку.
    """
    attempt, errors, current = 0, [], prompt
    while attempt <= max_retries:
        attempt += 1
        raw = ask(current)
        try:
            parsed = schema.model_validate_json(extract_json(raw))
        except (ValidationError, ValueError) as exc:
            msg = str(exc).splitlines()[0] if isinstance(exc, ValueError) else str(exc)
            errors.append(f"спроба {attempt}: {msg[:200]}")
            print(f"  [спроба {attempt}] невалідно: {msg[:120]}")
            if attempt > max_retries:
                break
            current = (prompt + "\n\n## ВИПРАВЛЕННЯ\nПопередня відповідь не пройшла валідацію "
                       f"схеми. Помилка: {msg[:300]}\nПоверни ВИПРАВЛЕНИЙ JSON тієї самої "
                       "структури, без пояснень.")
            continue

        print(f"  [спроба {attempt}] валідно")
        if log_path is not None:
            rec = {
                "date": dt.datetime.now().isoformat(timespec="seconds"),
                "model": model, "prompt_id": prompt_id,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16],
                "params": {"temperature": None, "seed": None},
                "attempts": attempt, "schema_errors": errors,
                "raw": raw, "parsed": json.loads(parsed.model_dump_json()),
                "human_decision": "очікує верифікації",
            }
            log_path.parent.mkdir(exist_ok=True)
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return parsed

    raise SchemaRetryError(f"не вдалося за {attempt} спроб: " + "; ".join(errors))


class ReplayAsk:
    """Адаптер, що повертає збережений сирий вихід реальної сесії."""

    def __init__(self, path: pathlib.Path):
        self.text = path.read_text(encoding="utf-8")

    def __call__(self, prompt: str) -> str:
        return self.text


class StubAsk:
    """Адаптер для демонстрації: спершу повертає зламані відповіді, потім справжню."""

    def __init__(self, good: pathlib.Path, broken_times: int = 2):
        self.good = good.read_text(encoding="utf-8")
        self.left = broken_times
        self.calls = 0

    def __call__(self, prompt: str) -> str:
        self.calls += 1
        if self.left > 0:
            self.left -= 1
            if self.left == 1:
                return "Ось терміни, які я пропоную:\n{ \"terms\": [ {\"id\": \"t01\","  # обрізаний JSON
            data = json.loads(self.good)
            data["terms"][0]["group"] = "невідома_група"      # порушення переліку
            data["terms"][1]["definition"] = "коротко"         # коротше за 20 символів
            return json.dumps(data, ensure_ascii=False)
        return self.good


def demo() -> None:
    import sys
    sys.path.insert(0, str(HUB))
    from schemas.glossary import GlossaryDraft as Glossary

    good = HUB / "tmp" / "raw_session03_glossary_A.json"
    print("Демонстрація 1: вихід валідний з першої спроби (відтворення реальної сесії)")
    call_with_validation(ReplayAsk(good), "prompt", Glossary, max_retries=2)

    print("\nДемонстрація 2: модель двічі повертає невалідний JSON, третя спроба успішна")
    ask = StubAsk(good, broken_times=2)
    call_with_validation(ask, "prompt", Glossary, max_retries=2)
    print(f"  усього викликів моделі: {ask.calls}")

    print("\nДемонстрація 3: ліміт повторів вичерпано")
    try:
        call_with_validation(StubAsk(good, broken_times=5), "prompt", Glossary, max_retries=2)
    except SchemaRetryError as exc:
        print(f"  піднято SchemaRetryError: {str(exc)[:110]}…")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    if ap.parse_args().demo:
        demo()
