---
id: chk-001-novyi-dokument
type: checklist
owner: інженер знань
reviewed: 2026-10-25
sources:
  - tools/lint_meta.py
sensitivity: public
---

# CHK-001. Чек-ліст нового документа знань

- [ ] Заповнено front matter: id, type, owner, reviewed, sources, sensitivity
- [ ] id унікальний і збігається з іменем файлу
- [ ] Дата reviewed не старша за 12 місяців
- [ ] Зазначено щонайменше одне джерело
- [ ] Гриф доступу відповідає змісту (внутрішні дані не позначені як public)
- [ ] Документ проходить `python tools/lint_meta.py kb/`
