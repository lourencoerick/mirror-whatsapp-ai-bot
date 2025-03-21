from abc import ABC, abstractmethod


class IQueue(ABC):

    @abstractmethod
    def enqueue(self, message: dict) -> None:
        pass

    @abstractmethod
    def dequeue(self) -> dict:
        pass
