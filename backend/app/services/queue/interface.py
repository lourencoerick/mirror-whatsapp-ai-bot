from abc import ABC, abstractmethod


class IQueue(ABC):
    """Interface for message queue implementations."""

    @abstractmethod
    def enqueue(self, message: dict) -> None:
        """Add a message to the queue."""
        pass

    @abstractmethod
    def dequeue(self) -> dict:
        """Consume the next message from the queue."""
        pass
