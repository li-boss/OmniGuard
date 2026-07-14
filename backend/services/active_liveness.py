"""Randomised active liveness challenge state machine for access terminals."""

from __future__ import annotations

import secrets
import threading
import time


ALLOWED_ACTIONS = ("turn_left", "turn_right", "blink", "open_mouth")


class ActiveLivenessChallenges:
    def __init__(self, ttl_seconds=20.0):
        self.ttl_seconds = float(ttl_seconds)
        self._items = {}
        self._lock = threading.RLock()

    def create(self, subject_id, length=3):
        length = max(2, min(4, int(length)))
        actions = []
        while len(actions) < length:
            action = secrets.choice(ALLOWED_ACTIONS)
            if not actions or action != actions[-1]:
                actions.append(action)
        challenge_id = secrets.token_urlsafe(18)
        now = time.time()
        item = {
            "challenge_id": challenge_id,
            "subject_id": str(subject_id),
            "actions": actions,
            "current_index": 0,
            "created_at": now,
            "expires_at": now + self.ttl_seconds,
            "status": "pending",
        }
        with self._lock:
            self._items[challenge_id] = item
        return self._public(item)

    def observe(self, challenge_id, action, confidence=1.0):
        with self._lock:
            item = self._require(challenge_id)
            if item["status"] != "pending":
                return self._public(item)
            if time.time() > item["expires_at"]:
                item["status"] = "expired"
                return self._public(item)
            expected = item["actions"][item["current_index"]]
            if action == expected and float(confidence) >= 0.7:
                item["current_index"] += 1
                if item["current_index"] == len(item["actions"]):
                    item["status"] = "passed"
            return self._public(item)

    def get(self, challenge_id):
        with self._lock:
            item = self._require(challenge_id)
            if item["status"] == "pending" and time.time() > item["expires_at"]:
                item["status"] = "expired"
            return self._public(item)

    def _require(self, challenge_id):
        if challenge_id not in self._items:
            raise KeyError("challenge not found")
        return self._items[challenge_id]

    @staticmethod
    def _public(item):
        result = dict(item)
        index = result["current_index"]
        result["next_action"] = result["actions"][index] if index < len(result["actions"]) else None
        return result


active_liveness_challenges = ActiveLivenessChallenges()
