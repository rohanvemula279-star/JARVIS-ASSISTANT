#!/usr/bin/env python3
"""Fresh face enrollment with proper signature extraction."""

import cv2
import numpy as np
import json
from pathlib import Path
from core.face_utils import extract_face_signature, cosine_similarity

PROJECT_ROOT = Path(__file__).parent

def enroll_fresh():
    """Capture face and create enrollment with correct method."""
    
    print("\n" + "="*60)
    print("🔐 FRESH FACE ENROLLMENT")
    print("="*60)
    
    # Open camera
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ Cannot open camera")
        return False
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    print("✅ Camera opened")
    
    signatures = []
    pose_labels = [
        "1/7: STRAIGHT (look at camera)",
        "2/7: LEFT (turn head left ~45°)",
        "3/7: RIGHT (turn head right ~45°)",
        "4/7: UP (tilt head up)",
        "5/7: DOWN (tilt head down)",
        "6/7: SMILE (smile at camera)",
        "7/7: BLINK (blink naturally 3 times)"
    ]
    
    captured = 0
    countdown = 3
    
    print("\n📸 CAPTURING FACE...")
    print("   Press SPACE to start, ESC to quit")
    
    for pose_idx, pose_label in enumerate(pose_labels):
        print(f"\n{pose_label}")
        pose_signatures = []
        pose_samples = 0
        start_capture = False
        countdown = 5
        
        while pose_samples < 4:  # 4 samples per pose
            ret, frame = cap.read()
            if not ret:
                print("❌ Camera read failed")
                cap.release()
                return False
            
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Try to extract signature
            try:
                sig = extract_face_signature(frame_rgb)
                if sig is not None:
                    pose_signatures.append(sig)
                    pose_samples += 1
                    captured += 1
                    print(f"    ✓ Sample {pose_samples}/4 (total: {captured}/28)")
            except:
                pass
            
            # Display
            h, w = frame.shape[:2]
            cv2.putText(frame, pose_label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, f"Captured: {pose_samples}/4 (Total: {captured}/28)", 
                       (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            cv2.imshow("Enrollment", frame)
            
            key = cv2.waitKey(30) & 0xFF
            if key == 27:  # ESC
                print("❌ Enrollment cancelled")
                cap.release()
                cv2.destroyAllWindows()
                return False
        
        if pose_signatures:
            avg_sig = np.mean(pose_signatures, axis=0)
            signatures.append(avg_sig)
            print(f"  ✅ Pose {pose_idx + 1} complete (averaged from {len(pose_signatures)} samples)")
    
    cap.release()
    cv2.destroyAllWindows()
    
    # Create final signature
    print("\n📊 Creating enrollment signature...")
    final_signature = np.mean(signatures, axis=0)
    final_signature = final_signature / (np.linalg.norm(final_signature) + 1e-8)  # Normalize
    
    # Test self-match
    self_scores = []
    for sig in signatures:
        sig_norm = sig / (np.linalg.norm(sig) + 1e-8)
        score = cosine_similarity(final_signature, sig_norm)
        self_scores.append(score)
    
    self_mean = np.mean(self_scores)
    self_std = np.std(self_scores)
    
    print(f"   Self-match scores: {[f'{s:.3f}' for s in self_scores]}")
    print(f"   Mean: {self_mean:.4f}, Std: {self_std:.4f}")
    
    # Save signature
    sig_path = PROJECT_ROOT / "data" / "authorized_faces" / "owner_signature.npy"
    sig_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(sig_path, final_signature)
    print(f"✅ Signature saved: {sig_path}")
    
    # Save calibration
    cal_path = PROJECT_ROOT / "data" / "authorized_faces" / "calibration.json"
    calibration = {
        "threshold": 0.70,
        "self_mean": float(self_mean),
        "self_std": float(self_std),
        "samples_count": len(signatures),
        "method": "extract_face_signature"
    }
    with open(cal_path, 'w') as f:
        json.dump(calibration, f, indent=2)
    print(f"✅ Calibration saved: {cal_path}")
    
    print("\n" + "="*60)
    print("✅ ENROLLMENT COMPLETE!")
    print(f"   Threshold: 0.70")
    print(f"   Self-match mean: {self_mean:.4f}")
    print("="*60)
    print("\nNow run: python main.py")
    print("And present your face for unlock")
    return True

if __name__ == "__main__":
    enroll_fresh()
