from __future__ import annotations

from abc import ABC, abstractmethod


class BaseRepository(ABC):
    @abstractmethod
    def create(self, *args, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, *args, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def list(self, *args, **kwargs):
        raise NotImplementedError
