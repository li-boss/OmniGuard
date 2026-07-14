import pytest

from app import create_app
from models import db
from services.active_liveness import ActiveLivenessChallenges
import io
import wave

import numpy as np

from services.multimodal_fusion import MultimodalFusionEngine, YamnetAudioClassifier


@pytest.fixture
def client():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "JWT_SECRET_KEY": "test-secret",
    })
    with app.test_client() as test_client:
        yield test_client
    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_angry_person_in_zone_triggers_fusion_alarm():
    engine = MultimodalFusionEngine()
    engine.add_emotion_event("cam-test", 7, "angry", 0.95)
    decision = engine.evaluate("cam-test", 7, in_zone=True)
    assert decision.triggered is True
    assert decision.score >= 0.65
    assert "electronic_fence" in decision.reasons


def test_weak_single_audio_cue_does_not_trigger():
    engine = MultimodalFusionEngine()
    engine.add_audio_event("cam-test", "shout", 0.4)
    assert engine.evaluate("cam-test").triggered is False


def test_strong_scream_can_trigger_without_zone():
    engine = MultimodalFusionEngine()
    engine.add_audio_event("cam-test", "screaming", 0.95)
    decision = engine.evaluate("cam-test")
    assert decision.triggered is True
    assert decision.severity == "critical"


@pytest.mark.parametrize(
    ("label", "confidence"),
    [
        ("gunshot", 0.15),
        ("explosion", 0.18),
        ("glass_breaking", 0.18),
    ],
)
def test_detected_critical_sound_triggers_immediately(label, confidence):
    engine = MultimodalFusionEngine()
    engine.add_audio_event("cam-test", label, confidence)

    decision = engine.evaluate("cam-test")

    assert decision.triggered is True
    assert decision.severity == "critical"


def test_lightweight_impact_candidate_does_not_trigger_by_itself():
    engine = MultimodalFusionEngine()
    engine.add_audio_event("cam-test", "impact_candidate", 1.0)

    assert engine.evaluate("cam-test").triggered is False


def test_random_action_sequence_requires_correct_order():
    challenges = ActiveLivenessChallenges(ttl_seconds=10)
    challenge = challenges.create("person-1", length=2)
    first, second = challenge["actions"]
    unchanged = challenges.observe(challenge["challenge_id"], second, 0.99)
    assert unchanged["current_index"] == 0
    progressed = challenges.observe(challenge["challenge_id"], first, 0.99)
    assert progressed["current_index"] == 1
    passed = challenges.observe(challenge["challenge_id"], second, 0.99)
    assert passed["status"] == "passed"


def test_multimodal_api_creates_alarm(client):
    camera_id = "cam-multimodal-api"
    response = client.post("/api/multimodal/emotion-events", json={
        "camera_id": camera_id,
        "object_id": 12,
        "emotion": "angry",
        "confidence": 0.95,
        "create_alarm": False,
    })
    assert response.status_code == 201
    result = client.post("/api/multimodal/evaluate", json={
        "camera_id": camera_id,
        "object_id": 12,
        "zone_id": 3,
        "in_zone": True,
    })
    assert result.status_code == 200
    assert result.json["data"]["triggered"] is True
    assert result.json["data"]["alarm_id"] is not None


def test_realtime_wav_endpoint_detects_acoustic_candidate(client):
    sample_rate = 16000
    time_axis = np.arange(sample_rate, dtype=np.float32) / sample_rate
    samples = (0.8 * np.sin(2 * np.pi * 2000 * time_axis) * 32767).astype("<i2")
    payload = io.BytesIO()
    with wave.open(payload, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(samples.tobytes())
    payload.seek(0)

    response = client.post(
        "/api/multimodal/analyze-wav",
        data={
            "camera_id": "cam-audio-test",
            "create_alarm": "false",
            "audio": (payload, "chunk.wav"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    data = response.json["data"]
    assert data["sample_rate"] == sample_rate
    assert data["duration_seconds"] == 1.0
    assert data["events"][0]["label"] == "acoustic_distress_candidate"
    assert data["detectors"]["lightweight"]["loaded"] is True


def test_yamnet_maps_relevant_audioset_label_without_loading_tensorflow():
    class TensorResult:
        def numpy(self):
            return np.asarray([[0.92]], dtype=np.float32)

    classifier = YamnetAudioClassifier(enabled=True)
    classifier._model = lambda waveform: (TensorResult(), None, None)
    classifier._class_names = ["Screaming"]

    events = classifier.analyze(np.ones(16000, dtype=np.float32) * 0.1, 16000)

    assert events == [{
        "label": "screaming",
        "score": 0.92,
        "raw_label": "Screaming",
        "classifier": "yamnet",
    }]


def test_yamnet_preserves_explosion_as_semantic_alarm_label():
    class TensorResult:
        def numpy(self):
            return np.asarray([[0.61]], dtype=np.float32)

    classifier = YamnetAudioClassifier(enabled=True)
    classifier._model = lambda waveform: (TensorResult(), None, None)
    classifier._class_names = ["Explosion"]

    events = classifier.analyze(np.ones(16000, dtype=np.float32) * 0.1, 16000)

    assert events[0]["label"] == "explosion"


@pytest.mark.parametrize("raw_label", ["Artillery fire", "Cap gun", "Firecracker"])
def test_yamnet_maps_gunshot_like_labels(raw_label):
    class TensorResult:
        def numpy(self):
            return np.asarray([[0.25]], dtype=np.float32)

    classifier = YamnetAudioClassifier(enabled=True)
    classifier._model = lambda waveform: (TensorResult(), None, None)
    classifier._class_names = [raw_label]

    events = classifier.analyze(np.ones(16000, dtype=np.float32) * 0.1, 16000)

    assert events[0]["label"] == "gunshot"


def test_yamnet_amplifies_quiet_non_silent_audio_for_inference():
    samples = np.sin(np.linspace(0, 20 * np.pi, 16000, dtype=np.float32)) * 0.004

    normalized = YamnetAudioClassifier._normalize_for_inference(samples)

    assert np.sqrt(np.mean(np.square(normalized))) > 0.07
    assert np.max(np.abs(normalized)) <= 0.95


def test_yamnet_does_not_amplify_silence_or_tiny_noise():
    samples = np.ones(16000, dtype=np.float32) * 0.0001

    normalized = YamnetAudioClassifier._normalize_for_inference(samples)

    assert np.array_equal(normalized, samples)


def test_audio_status_reports_both_detectors(client):
    response = client.get("/api/multimodal/audio-status")
    assert response.status_code == 200
    detectors = response.json["data"]["detectors"]
    assert detectors["lightweight"]["enabled"] is True
    assert detectors["semantic"]["model"] == "YAMNet"
