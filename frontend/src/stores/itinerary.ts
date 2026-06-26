import { defineStore } from "pinia";
import { ref } from "vue";
import type { Itinerary } from "../types";

/** Central store for the current itinerary, shared across all components. */
export const useItineraryStore = defineStore("itinerary", () => {
  const current = ref<Itinerary | null>(null);

  function set(itinerary: Itinerary) {
    current.value = itinerary;
  }

  function clear() {
    current.value = null;
  }

  /** Expose candidate itineraries from the current plan, if any. */
  function candidates() {
    return current.value?.candidate_itineraries || [];
  }

  return { current, set, clear, candidates };
});
