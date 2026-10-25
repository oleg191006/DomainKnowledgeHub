# -*- coding: utf-8 -*-
"""Схема тверджень LLM-експерта (ЛР01 Р4, розширюється в ЛР03).

Схема навмисно сувора: вона має ловити саме ті помилки, які модель робить найчастіше —
неправильний тип твердження, confidence поза діапазоном, порожній scope, дублікати id.
"""
from enum import Enum
from typing import List

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Kind(str, Enum):
    FACT = "fact"
    RULE = "rule"
    HYPOTHESIS = "hypothesis"


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^c\d{2,3}$", description="ідентифікатор виду c01")
    statement: str = Field(min_length=20, max_length=600)
    kind: Kind
    sources: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    scope: str = Field(min_length=3, max_length=300)

    @field_validator("sources")
    @classmethod
    def no_urls(cls, v: List[str]) -> List[str]:
        # правило 2 підказки: модель не має наводити посилання, їх перевіряє людина
        for s in v:
            if "http://" in s or "https://" in s:
                raise ValueError(f"джерело не має містити URL: {s}")
        return v

    @model_validator(mode="after")
    def hypothesis_without_source(self):
        # правило 1 підказки: факт або правило без джерела має бути позначене як гіпотеза
        if self.kind in (Kind.FACT, Kind.RULE) and not self.sources and self.confidence > 0.7:
            raise ValueError(
                f"{self.id}: {self.kind.value} без джерела не може мати confidence > 0.7")
        return self


class ExpertAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: List[Claim] = Field(min_length=10)

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [c.id for c in self.claims]
        dup = {i for i in ids if ids.count(i) > 1}
        if dup:
            raise ValueError(f"неунікальні id: {sorted(dup)}")
        return self
