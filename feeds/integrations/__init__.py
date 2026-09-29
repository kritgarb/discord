"""Registro das integrações disponíveis. Para adicionar uma nova, crie a subclasse de
Integration num subpacote e inclua a classe em INTEGRATIONS."""

from feeds.integrations.compilado import Compilado
from feeds.integrations.sebrae import SebraeMissoes

INTEGRATIONS = {cls.slug: cls for cls in (SebraeMissoes, Compilado)}

__all__ = ["INTEGRATIONS", "Compilado", "SebraeMissoes"]
