# pyre-ignore-all-errors
"""
core/face_utils.py — Pure math functions for face authentication.
No camera or threading — independently testable with synthetic data.
"""

import hashlib
import math
import os

import numpy as np  # pyre-ignore


# ──────────────────────────────────────────────
#  MediaPipe landmark index groups
# ──────────────────────────────────────────────

# 6-point eye contours for EAR computation (p1..p6 order)
LEFT_EYE_EAR = (33, 160, 158, 133, 153, 144)
RIGHT_EYE_EAR = (362, 385, 387, 263, 373, 380)

# Extended eye regions
LEFT_EYE = (33, 133, 160, 144, 153, 154, 155, 157, 158, 159, 161, 163)
RIGHT_EYE = (362, 263, 387, 373, 380, 381, 382, 384, 385, 386, 388, 390)

# Nose landmarks
NOSE = (1, 2, 4, 5, 6, 168, 195, 197)

# Mouth landmarks
MOUTH = (61, 291, 0, 17, 78, 308, 82, 312, 13, 14)

# Jawline landmarks
JAW = (10, 152, 234, 454, 323, 93, 132, 361, 58, 288)

# Forehead region
FOREHEAD = (10, 67, 109, 338, 297)

# Key landmarks for head pose
NOSE_TIP = 4
CHIN = 152
LEFT_EYE_CORNER = 33
RIGHT_EYE_CORNER = 263
LEFT_MOUTH_CORNER = 61
RIGHT_MOUTH_CORNER = 291
FOREHEAD_TOP = 10


def _get_point(landmarks, idx):
    """Extract (x, y, z) from a MediaPipe landmark by index."""
    lm = landmarks[idx]
    return np.array([lm.x, lm.y, lm.z])


def _get_point_2d(landmarks, idx):
    """Extract (x, y) from a MediaPipe landmark by index."""
    lm = landmarks[idx]
    return np.array([lm.x, lm.y])


def _dist(a, b):
    """Euclidean distance between two points."""
    return float(np.linalg.norm(a - b))


# ──────────────────────────────────────────────
#  Eye Aspect Ratio (EAR) — blink detection
# ──────────────────────────────────────────────

def compute_ear(landmarks, side="left"):
    """
    Compute Eye Aspect Ratio for one eye.

    EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)

    Normal open: ~0.25-0.30
    During blink: ~0.10-0.18

    Args:
        landmarks: MediaPipe face_landmarks object
        side: 'left' or 'right'

    Returns:
        float: EAR value
    """
    indices = LEFT_EYE_EAR if side == "left" else RIGHT_EYE_EAR
    pts = [_get_point_2d(landmarks, i) for i in indices]
    # p1=outer, p2=upper-outer, p3=upper-inner, p4=inner, p5=lower-inner, p6=lower-outer
    p1, p2, p3, p4, p5, p6 = pts

    vertical_1 = _dist(p2, p6)
    vertical_2 = _dist(p3, p5)
    horizontal = _dist(p1, p4)

    if horizontal < 1e-6:
        return 0.3  # fallback — eye is essentially a point

    return (vertical_1 + vertical_2) / (2.0 * horizontal)


# ──────────────────────────────────────────────
#  Head pose estimation
# ──────────────────────────────────────────────

def compute_head_pose(landmarks):
    """
    Estimate head yaw and pitch from landmark geometry.

    Returns:
        (yaw_degrees, pitch_degrees): positive yaw = looking right,
                                       positive pitch = looking up
    """
    nose = _get_point_2d(landmarks, NOSE_TIP)
    left_eye = _get_point_2d(landmarks, LEFT_EYE_CORNER)
    right_eye = _get_point_2d(landmarks, RIGHT_EYE_CORNER)
    chin = _get_point_2d(landmarks, CHIN)
    forehead = _get_point_2d(landmarks, FOREHEAD_TOP)

    # Yaw: ratio of nose-to-left-eye vs nose-to-right-eye distance
    d_left = _dist(nose, left_eye)
    d_right = _dist(nose, right_eye)
    if d_left + d_right < 1e-6:
        yaw = 0.0
    else:
        ratio = (d_right - d_left) / (d_right + d_left)
        yaw = ratio * 90.0  # rough degrees

    # Pitch: vertical position of nose relative to eye-line and chin
    eye_mid = (left_eye + right_eye) / 2.0
    face_height = _dist(forehead, chin)
    if face_height < 1e-6:
        pitch = 0.0
    else:
        nose_offset = (nose[1] - eye_mid[1]) / face_height
        pitch = (0.35 - nose_offset) * 120.0  # calibrated rough degrees

    return float(yaw), float(pitch)


# ──────────────────────────────────────────────
#  Face signature extraction
# ──────────────────────────────────────────────

def extract_face_signature(landmarks):
    """
    Extract a geometric signature from 468 MediaPipe landmarks.

    Computes ~30 scale-invariant and position-invariant ratios:
    - Inter-eye distance / face width
    - Nose length / face height
    - Mouth width / face width
    - Eye height / eye width (both)
    - Jawline curvature points
    - Forehead / chin proportions
    - Lip thickness ratios
    - Nose-to-eye distances
    - Face symmetry score
    - etc.

    Returns:
        numpy.ndarray of shape (N,) — normalized to unit vector
    """
    # Key reference points
    left_eye = _get_point(landmarks, LEFT_EYE_CORNER)
    right_eye = _get_point(landmarks, RIGHT_EYE_CORNER)
    nose_tip = _get_point(landmarks, NOSE_TIP)
    chin = _get_point(landmarks, CHIN)
    forehead = _get_point(landmarks, FOREHEAD_TOP)
    left_mouth = _get_point(landmarks, LEFT_MOUTH_CORNER)
    right_mouth = _get_point(landmarks, RIGHT_MOUTH_CORNER)

    # Reference distances
    eye_dist = _dist(left_eye, right_eye)
    face_height = _dist(forehead, chin)
    face_width = eye_dist  # approximation

    if eye_dist < 1e-6 or face_height < 1e-6:
        return np.zeros(30)

    ratios = []

    # 1. Inter-eye distance / face height
    ratios.append(eye_dist / face_height)

    # 2. Nose tip to chin / face height
    ratios.append(_dist(nose_tip, chin) / face_height)

    # 3. Nose tip to forehead / face height
    ratios.append(_dist(nose_tip, forehead) / face_height)

    # 4. Mouth width / face width
    mouth_width = _dist(left_mouth, right_mouth)
    ratios.append(mouth_width / face_width)

    # 5-6. Nose tip to each eye corner / eye distance
    ratios.append(_dist(nose_tip, left_eye) / eye_dist)
    ratios.append(_dist(nose_tip, right_eye) / eye_dist)

    # 7-8. Eye height / eye width for each eye
    for eye_indices in [LEFT_EYE, RIGHT_EYE]:
        pts = [_get_point(landmarks, i) for i in eye_indices]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ew = max(xs) - min(xs)
        eh = max(ys) - min(ys)
        ratios.append(eh / (ew + 1e-6))

    # 9. Nose bridge length / face height
    nose_bridge_top = _get_point(landmarks, 168)  # bridge top
    nose_bridge_len = _dist(nose_bridge_top, nose_tip)
    ratios.append(nose_bridge_len / face_height)

    # 10-14. Jawline curvature (distances between jaw points / face width)
    jaw_pts = [_get_point(landmarks, i) for i in JAW[:5]]
    for i in range(len(jaw_pts) - 1):
        ratios.append(_dist(jaw_pts[i], jaw_pts[i + 1]) / face_width)

    # 15-17. Forehead landmarks spacing / face width
    fh_pts = [_get_point(landmarks, i) for i in FOREHEAD[:3]]
    for i in range(len(fh_pts) - 1):
        ratios.append(_dist(fh_pts[i], fh_pts[i + 1]) / face_width)

    # 18. Forehead height / face height
    eye_mid = (left_eye + right_eye) / 2.0
    ratios.append(_dist(forehead, eye_mid) / face_height)

    # 19. Chin to mouth / face height
    mouth_mid = (left_mouth + right_mouth) / 2.0
    ratios.append(_dist(chin, mouth_mid) / face_height)

    # 20. Mouth to nose / face height
    ratios.append(_dist(mouth_mid, nose_tip) / face_height)

    # 21-22. Lip thickness (upper/lower via specific landmarks)
    upper_lip = _get_point(landmarks, 13)
    lower_lip = _get_point(landmarks, 14)
    mouth_top = _get_point(landmarks, 0)
    mouth_bottom = _get_point(landmarks, 17)
    ratios.append(_dist(mouth_top, upper_lip) / face_height)
    ratios.append(_dist(lower_lip, mouth_bottom) / face_height)

    # 23. Face symmetry: left-half vs right-half nose distances
    sym_left = _dist(nose_tip, left_eye)
    sym_right = _dist(nose_tip, right_eye)
    ratios.append(sym_left / (sym_right + 1e-6))

    # 24-25. Cheekbone width approximation
    left_cheek = _get_point(landmarks, 234)
    right_cheek = _get_point(landmarks, 454)
    cheek_width = _dist(left_cheek, right_cheek)
    ratios.append(cheek_width / face_width)

    jaw_left = _get_point(landmarks, 58)
    jaw_right = _get_point(landmarks, 288)
    jaw_width = _dist(jaw_left, jaw_right)
    ratios.append(jaw_width / face_width)

    # 26. Temple width / jaw width
    ratios.append(cheek_width / (jaw_width + 1e-6))

    # 27-28. Ear-to-nose proxies (outer face points)
    ratios.append(_dist(left_cheek, nose_tip) / face_width)
    ratios.append(_dist(right_cheek, nose_tip) / face_width)

    # 29-30. Eyebrow arch heights
    left_brow = _get_point(landmarks, 67)
    right_brow = _get_point(landmarks, 297)
    ratios.append(_dist(left_brow, left_eye) / face_height)
    ratios.append(_dist(right_brow, right_eye) / face_height)

    sig = np.array(ratios, dtype=np.float64)

    # Normalize to unit vector
    norm = np.linalg.norm(sig)
    if norm > 1e-6:
        sig = sig / norm

    return sig


# ──────────────────────────────────────────────
#  Similarity computation
# ──────────────────────────────────────────────

def cosine_similarity(a, b):
    """Fast cosine similarity between two signature vectors (mean-centered)."""
    # Mean-centering converts this to Pearson Correlation for better separation
    a_c = a - np.mean(a)
    b_c = b - np.mean(b)
    norm_a = np.linalg.norm(a_c)
    norm_b = np.linalg.norm(b_c)
    if norm_a < 1e-6 or norm_b < 1e-6:
        return 0.0
    return float(np.dot(a_c, b_c) / (norm_a * norm_b))


# ──────────────────────────────────────────────
#  Signature file integrity
# ──────────────────────────────────────────────

def hash_signature_file(npy_path):
    """Compute SHA-256 hex digest of a .npy file."""
    sha = hashlib.sha256()
    with open(npy_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def save_signature_with_hash(signature, npy_path, hash_path):
    """Save signature .npy and its SHA-256 hash."""
    os.makedirs(os.path.dirname(npy_path), exist_ok=True)
    np.save(npy_path, signature)
    digest = hash_signature_file(npy_path)
    with open(hash_path, "w") as f:
        f.write(digest)


def verify_signature_integrity(npy_path, hash_path):
    """Verify .npy file matches its stored SHA-256 hash."""
    if not os.path.exists(npy_path) or not os.path.exists(hash_path):
        return False
    try:
        current = hash_signature_file(npy_path)
        with open(hash_path, "r") as f:
            stored = f.read().strip()
        return current == stored
    except Exception:
        return False


# ──────────────────────────────────────────────
#  Anti-Spoofing: Texture Analysis (Layer 1)
# ──────────────────────────────────────────────

def compute_texture_score(frame_gray, face_box):
    """
    Compute texture richness of the face region using Laplacian variance.

    Real faces have high texture variance (skin pores, shadows, contours).
    Photos/screens tend to have lower variance due to print/pixel smoothing.

    Args:
        frame_gray: Grayscale numpy array (H, W)
        face_box: (x, y, w, h) bounding box in pixel coords

    Returns:
        float: Laplacian variance score (higher = more textured = more likely real)
    """
    import cv2  # pyre-ignore

    x, y, w, h = face_box
    fh, fw = frame_gray.shape[:2]

    # Clamp to frame bounds
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(fw, x + w)
    y2 = min(fh, y + h)

    if x2 - x1 < 20 or y2 - y1 < 20:
        return 0.0  # Face region too small

    face_crop = frame_gray[y1:y2, x1:x2]

    # Resize to consistent size for comparable scores
    face_crop = cv2.resize(face_crop, (128, 128))

    # Laplacian edge detection → variance measures texture richness
    laplacian = cv2.Laplacian(face_crop, cv2.CV_64F)
    score = float(laplacian.var())

    return score


# ──────────────────────────────────────────────
#  Anti-Spoofing: Depth Estimation (Layer 3)
# ──────────────────────────────────────────────

def compute_depth_score(landmarks):
    """
    Analyze Z-coordinate distribution of face landmarks.

    A real 3D face has a characteristic Z-distribution: the nose protrudes
    significantly while ears/jawline recede. A flat photo/screen has near-zero
    Z variation.

    NOTE: MediaPipe Z is estimated (monocular), not measured. This is a
    SUPPLEMENTARY signal only — it can hallucinate plausible Z for photos.

    Args:
        landmarks: MediaPipe face landmarks (468 points)

    Returns:
        (z_range, nose_protrusion): Both floats.
            z_range: max(z) - min(z) across all landmarks
            nose_protrusion: z-distance of nose tip relative to ear-line midpoint
    """
    # Extract Z values from all landmarks
    z_values = np.array([landmarks[i].z for i in range(len(landmarks))])

    z_range = float(z_values.max() - z_values.min())

    # Nose protrusion: compare nose tip Z to average of lateral landmarks
    nose_z = landmarks[NOSE_TIP].z
    # Use cheekbone landmarks as lateral reference
    lateral_z = (landmarks[234].z + landmarks[454].z) / 2.0
    nose_protrusion = float(abs(nose_z - lateral_z))

    return z_range, nose_protrusion


# ──────────────────────────────────────────────
#  Anti-Spoofing: Micro-Movement Analysis (Layer 2)
# ──────────────────────────────────────────────

# Key landmarks to track for micro-movement (diverse face regions)
STABILITY_LANDMARKS = [
    NOSE_TIP, CHIN, LEFT_EYE_CORNER, RIGHT_EYE_CORNER,
    FOREHEAD_TOP, LEFT_MOUTH_CORNER, RIGHT_MOUTH_CORNER,
    234, 454,  # Cheekbones
]


def extract_stability_points(landmarks):
    """
    Extract key landmark positions for micro-movement tracking.

    Returns:
        numpy.ndarray of shape (N, 2) — (x, y) positions of key landmarks
    """
    points = np.array([
        [landmarks[idx].x, landmarks[idx].y]
        for idx in STABILITY_LANDMARKS
    ], dtype=np.float64)
    return points


def compute_landmark_stability(history):
    """
    Analyze micro-movement patterns from a history of landmark positions.

    Two-check system:
    1. VARIANCE CHECK: If variance too low → static photo on a stand
    2. CORRELATION CHECK: If all landmarks move in lockstep (same direction
       and magnitude) → rigid-body motion (phone/tablet being moved)

    Real faces have DIFFERENTIAL movement: nose stays relatively still while
    jaw moves, eyebrows shift independently, etc.

    Args:
        history: list of numpy arrays, each shape (N, 2) from extract_stability_points()
                 Should contain at least 10 frames.

    Returns:
        (variance, correlation):
            variance: float — average spatial variance of landmarks across frames
            correlation: float — 0..1, how uniformly all landmarks move together
                         (1.0 = perfect rigid-body, 0.0 = fully independent)
    """
    if len(history) < 10:
        return 0.0, 0.0  # Not enough data

    positions = np.array(history)  # shape: (T, N, 2)
    T, N, _ = positions.shape

    # ── Variance check (Welford-style per-landmark) ──
    # Compute variance of each landmark's position over time
    per_landmark_var = np.var(positions, axis=0)  # (N, 2)
    avg_variance = float(np.mean(per_landmark_var))

    # ── Correlation check (rigid-body detection) ──
    # Compute frame-to-frame displacements
    deltas = np.diff(positions, axis=0)  # (T-1, N, 2)

    if deltas.shape[0] < 2:
        return avg_variance, 0.0

    # For each frame, compute pairwise similarity of landmark movements
    # If all landmarks move the same way, it's rigid-body motion
    correlations = []
    for t in range(deltas.shape[0]):
        frame_deltas = deltas[t]  # (N, 2)
        magnitudes = np.linalg.norm(frame_deltas, axis=1)

        # Skip frames with negligible movement
        if np.max(magnitudes) < 1e-6:
            continue

        # Normalize each landmark's delta to unit vector
        nonzero = magnitudes > 1e-6
        if np.sum(nonzero) < 3:
            continue

        unit_deltas = frame_deltas[nonzero] / magnitudes[nonzero, np.newaxis]

        # Compute mean direction
        mean_dir = np.mean(unit_deltas, axis=0)
        mean_dir_norm = np.linalg.norm(mean_dir)

        if mean_dir_norm < 1e-6:
            correlations.append(0.0)
        else:
            # How aligned are all landmarks to the mean direction?
            mean_dir_unit = mean_dir / mean_dir_norm
            alignment = np.dot(unit_deltas, mean_dir_unit)
            # Also check magnitude uniformity
            mag_nonzero = magnitudes[nonzero]
            mag_cv = float(np.std(mag_nonzero) / (np.mean(mag_nonzero) + 1e-8))
            # High alignment + low magnitude variation = rigid body
            dir_score = float(np.mean(alignment))
            mag_score = max(0.0, 1.0 - mag_cv)
            correlations.append(dir_score * 0.7 + mag_score * 0.3)

    if not correlations:
        return avg_variance, 0.0

    avg_correlation = float(np.mean(correlations))
    return avg_variance, avg_correlation


# ──────────────────────────────────────────────
#  Enrollment PIN Security
# ──────────────────────────────────────────────

def hash_pin(pin):
    """Hash a PIN string with SHA-256."""
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


def save_pin(pin, hash_path):
    """Save hashed PIN to file."""
    os.makedirs(os.path.dirname(hash_path), exist_ok=True)
    digest = hash_pin(pin)
    with open(hash_path, "w") as f:
        f.write(digest)


def verify_pin(pin, hash_path):
    """Verify a PIN against stored hash."""
    if not os.path.exists(hash_path):
        return False
    try:
        with open(hash_path, "r") as f:
            stored = f.read().strip()
        return hash_pin(pin) == stored
    except Exception:
        return False


# ──────────────────────────────────────────────
#  Deep Face Embedding (OpenCV SFace)
# ──────────────────────────────────────────────

import cv2  # pyre-ignore


class DeepFaceEmbedder:
    """
    128-dim deep face embeddings using OpenCV's FaceRecognizerSF (SFace model).

    Two different people typically score 0.3–0.6 cosine similarity.
    The same person scores 0.85–0.99. This massive separation makes
    threshold-based discrimination reliable — unlike 30-ratio geometric signatures.

    Usage:
        embedder = DeepFaceEmbedder("models/face_recognition_sface_2021dec.onnx")
        embedding = embedder.extract_embedding(frame_rgb, face_landmarks)
        score = embedder.cosine_similarity(embedding, owner_embedding)
    """

    def __init__(self, model_path):
        """
        Args:
            model_path: path to face_recognition_sface_2021dec.onnx
        """
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"SFace model not found at {model_path}. "
                "Download from https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface"
            )
        self.recognizer = cv2.FaceRecognizerSF.create(model_path, "")
        print("[DeepFaceEmbedder] ✅ SFace model loaded (128-dim embeddings)")

    def extract_embedding(self, frame_rgb, face_landmarks):
        """
        Extract 128-dim deep face embedding from an RGB frame + MediaPipe landmarks.

        Args:
            frame_rgb: numpy array (H, W, 3) in RGB format
            face_landmarks: MediaPipe face landmarks (468 points, normalized 0–1)

        Returns:
            numpy.ndarray of shape (128,) — L2-normalized embedding, or None on failure
        """
        h, w = frame_rgb.shape[:2]

        # Convert MediaPipe normalized landmarks → pixel bounding box
        x_coords = [lm.x * w for lm in face_landmarks]
        y_coords = [lm.y * h for lm in face_landmarks]

        x_min = min(x_coords)
        y_min = min(y_coords)
        box_w = max(x_coords) - x_min
        box_h = max(y_coords) - y_min

        # Add 15% padding — SFace works better with margin around the face
        pad = int(0.15 * max(box_w, box_h))
        x_min = max(0, int(x_min) - pad)
        y_min = max(0, int(y_min) - pad)
        box_w = min(w - x_min, int(box_w) + 2 * pad)
        box_h = min(h - y_min, int(box_h) + 2 * pad)

        if box_w < 30 or box_h < 30:
            return None  # Face too small for reliable embedding

        # SFace expects BGR input
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

        # Crop and resize face region to SFace input size (112x112)
        face_crop = frame_bgr[y_min:y_min + box_h, x_min:x_min + box_w]
        if face_crop.size == 0:
            return None

        face_resized = cv2.resize(face_crop, (112, 112))

        # Extract 128-dim embedding
        embedding = self.recognizer.feature(face_resized)
        return embedding.flatten()

    @staticmethod
    def cosine_similarity(a, b):
        """
        Cosine similarity between two 128-dim face embeddings.
        Returns float in range [-1, 1]. Higher = more similar.
        """
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a < 1e-6 or norm_b < 1e-6:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    @staticmethod
    def match_against_gallery(embedding, gallery):
        """
        Compare a single embedding against a gallery of N enrolled embeddings.

        Args:
            embedding: (128,) query embedding
            gallery: (N, 128) array of enrolled embeddings

        Returns:
            (best_score, avg_score): best match and average across gallery
        """
        if gallery is None or len(gallery) == 0:
            return 0.0, 0.0

        if gallery.ndim == 1:
            # Single embedding stored as 1D
            score = DeepFaceEmbedder.cosine_similarity(embedding, gallery)
            return score, score

        scores = []
        for ref in gallery:
            scores.append(DeepFaceEmbedder.cosine_similarity(embedding, ref))

        return float(max(scores)), float(np.mean(scores))

    @staticmethod
    def save_gallery(gallery, npy_path, hash_path):
        """Save embedding gallery (N, 128) with integrity hash."""
        os.makedirs(os.path.dirname(npy_path), exist_ok=True)
        np.save(npy_path, gallery)
        digest = hash_signature_file(npy_path)
        with open(hash_path, "w") as f:
            f.write(digest)

    @staticmethod
    def load_gallery(npy_path, hash_path):
        """Load embedding gallery with integrity check. Returns (N, 128) or None."""
        if not os.path.exists(npy_path):
            return None
        if not verify_signature_integrity(npy_path, hash_path):
            print("[DeepFaceEmbedder] ⚠️ Embedding file tampered or hash missing!")
            return None
        try:
            gallery = np.load(npy_path)
            print(f"[DeepFaceEmbedder] ✅ Loaded {len(gallery)} owner embeddings")
            return gallery
        except Exception as e:
            print(f"[DeepFaceEmbedder] ❌ Failed to load embeddings: {e}")
            return None

