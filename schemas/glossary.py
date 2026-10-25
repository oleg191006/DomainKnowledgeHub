# -*- coding: utf-8 -*-
"""Схема словника предметної області (ЛР03 Р2)."""
from enum import Enum
from typing import List

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Group(str, Enum):
    OBJECT = "object"
    DOCUMENT = "document"
    CONDITION = "condition"
    PROCESS = "process"
    ACTOR = "actor"
    DESCRIPTOR = "descriptor"


class Term(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^t\d{2,3}$")
    label: str = Field(min_length=2, max_length=120)
    definition: str = Field(min_length=20, max_length=400)
    alt_labels: List[str] = Field(default_factory=list)
    group: Group
    disputed: bool = False
    question_for_expert: str = ""
    source_v1: str = ""
    source_note: str = ""

    @model_validator(mode="after")
    def disputed_needs_question(self):
        # спірний термін без запитання до експерта марний: він не породжує дії
        if self.disputed and not self.question_for_expert.strip():
            raise ValueError(f"{self.id}: disputed=true, але немає question_for_expert")
        if not self.disputed and self.question_for_expert.strip():
            raise ValueError(f"{self.id}: question_for_expert заданий, але disputed=false")
        return self

    @model_validator(mode="after")
    def definition_not_circular(self):
        # визначення не має починатися з самого терміна («реставрація — це реставрування»)
        head = self.definition.strip().lower()[:len(self.label)]
        if head == self.label.lower():
            raise ValueError(f"{self.id}: визначення повторює термін на початку")
        return self

    @model_validator(mode="after")
    def alt_labels_differ(self):
        if any(a.strip().lower() == self.label.strip().lower() for a in self.alt_labels):
            raise ValueError(f"{self.id}: alt_labels дублює канонічну назву")
        return self


class GlossaryDraft(BaseModel):
    """Чернетка від моделі. Джерел не вимагає: підказка прямо забороняє їх наводити,
    бо посилання додає людина на етапі верифікації V1."""

    model_config = ConfigDict(extra="forbid")

    terms: List[Term] = Field(min_length=30)

    @model_validator(mode="after")
    def unique_ids_and_labels(self):
        ids = [t.id for t in self.terms]
        dup_id = {i for i in ids if ids.count(i) > 1}
        if dup_id:
            raise ValueError(f"неунікальні id: {sorted(dup_id)}")
        labels = [t.label.lower() for t in self.terms]
        dup_lab = {l for l in labels if labels.count(l) > 1}
        if dup_lab:
            raise ValueError(f"неунікальні терміни: {sorted(dup_lab)}")
        return self


class Glossary(GlossaryDraft):
    """Куратований словник: те саме, що чернетка, плюс вимога джерел рівня V1."""

    @model_validator(mode="after")
    def enough_sources(self):
        # вимога ЛР03 Р2 C3: щонайменше 10 термінів мають джерело рівня V1
        with_src = sum(1 for t in self.terms if t.source_v1.strip())
        if with_src < 10:
            raise ValueError(f"лише {with_src} термінів мають джерело V1, потрібно ≥10")
        return self
