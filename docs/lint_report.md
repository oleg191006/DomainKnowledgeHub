---
id: doc-lint-report
type: analysis
owner: Чапля О.
reviewed: 2026-10-25
sources: [tools/lint_meta.py, kb/]
sensitivity: internal
lab: ЛР02 / Результат 4
---

# Звіт лінтера метаданих

## Правила, які перевіряє `tools/lint_meta.py`

| Код | Правило |
|---|---|
| R1 | Документ має front matter (блок між `---` на початку файлу) |
| R2 | Усі обов'язкові поля заповнені: `id`, `type`, `owner`, `reviewed`, `sources`, `sensitivity` |
| R3 | `id` унікальний у межах каталогу і збігається з іменем файлу |
| R4 | `reviewed` у форматі `YYYY-MM-DD`, не в майбутньому, не старша за 365 днів |
| R5 | `type` належить переліку: adr, runbook, glossary, policy, checklist, howto |
| R6 | `sensitivity` належить переліку: public, internal, restricted, personal |
| R7 | Указано щонайменше одне джерело |

Лінтер повертає код `0`, якщо порушень немає, і `1`, якщо є, — тому придатний для CI та pre-commit.

## Прогін 1: чистий каталог

```
$ python tools/lint_meta.py kb/
перевірено документів: 12; правил: 7
порушень немає
код повернення: 0
```

## Прогін 2: два навмисно зламані документи

Для перевірки роботи лінтера внесено п'ять помилок у два документи:

- `adr-001-klimat-norma.md` — вилучено поле `owner`, дату змінено на формат `25.10.2026`;
- `rb-001-vyhid-vologosti.md` — `id` скорочено до `rb-001` (не збігається з іменем файлу),
  `type` замінено на «інструкція», `sensitivity` — на «секретно».

```
$ python tools/lint_meta.py kb/
перевірено документів: 12; правил: 7
знайдено порушень: 5
  ✗ adr-001-klimat-norma.md: [R2] відсутнє або порожнє обов'язкове поле «owner»
  ✗ adr-001-klimat-norma.md: [R4] дата reviewed не у форматі YYYY-MM-DD: «25.10.2026»
  ✗ rb-001-vyhid-vologosti.md: [R3] id «rb-001» не збігається з іменем файлу «rb-001-vyhid-vologosti»
  ✗ rb-001-vyhid-vologosti.md: [R5] невідомий type «інструкція»; дозволені: adr, checklist, glossary, howto, policy, runbook
  ✗ rb-001-vyhid-vologosti.md: [R6] невідомий sensitivity «секретно»; дозволені: internal, personal, public, restricted
код повернення: 1
```

Усі п'ять внесених помилок виявлено, жодного хибного спрацювання на інших десяти документах не
було. Після прогону документи відновлено, повторний запуск знову дає код `0`.

## Автоматичний запуск

Лінтер запускається у GitHub Actions (`.github/workflows/lint.yml`) на кожен `push` і
`pull_request`, що змінює `kb/**` або `tools/**`, а також локально через pre-commit
(`.pre-commit-config.yaml`). Ненульовий код повернення зупиняє збірку, тому документ із
неповними метаданими не потрапляє до головної гілки.
