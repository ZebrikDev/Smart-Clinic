"""Select one of the already-valid slots without changing availability or state."""

from abc import ABC, abstractmethod


class SlotSelectionStrategy(ABC):
    @abstractmethod
    def select(self, slots, preferred_start):
        """Return a supplied slot or None; inputs use clinic-local naive times."""
        raise NotImplementedError


class EarliestAvailableStrategy(SlotSelectionStrategy):
    def select(self, slots, preferred_start):
        return min(slots, key=lambda slot: slot[0], default=None)


class ClosestToRequestedStrategy(SlotSelectionStrategy):
    def select(self, slots, preferred_start):
        """Rank by distance, then earlier start, without sorting the input."""
        return min(
            slots,
            key=lambda slot: (abs(slot[0] - preferred_start), slot[0]),
            default=None,
        )
