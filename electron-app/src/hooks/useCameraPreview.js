import { useState, useEffect, useCallback, useRef } from 'react';

export const useCameraPreview = () => {
  const [isActive, setIsActive] = useState(false);
  const [error, setError] = useState(null);
  const [stream, setStream] = useState(null);
  const [permission, setPermission] = useState(null);
  const videoRef = useRef(null);
  
  const startPreview = useCallback(async (videoElement) => {
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: 320, height: 240 }
      });
      setStream(mediaStream);
      setIsActive(true);
      setPermission('granted');
      
      if (videoElement) {
        videoElement.srcObject = mediaStream;
      }
    } catch (err) {
      setError(err.message);
      setPermission('denied');
      setIsActive(false);
    }
  }, []);
  
  const stopPreview = useCallback(() => {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      setStream(null);
    }
    setIsActive(false);
  }, [stream]);
  
  const captureFrame = useCallback(() => {
    if (!videoRef.current || !stream) return null;
    
    const canvas = document.createElement('canvas');
    canvas.width = videoRef.current.videoWidth;
    canvas.height = videoRef.current.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(videoRef.current, 0, 0);
    return canvas.toDataURL('image/jpeg').split(',')[1];
  }, [stream]);
  
  useEffect(() => {
    return () => {
      if (stream) {
        stream.getTracks().forEach(track => track.stop());
      }
    };
  }, [stream]);
  
  return {
    isActive,
    error,
    permission,
    startPreview,
    stopPreview,
    captureFrame,
    videoRef
  };
};