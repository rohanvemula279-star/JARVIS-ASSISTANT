import React, { useState, useEffect, useRef } from 'react';
import Webcam from 'react-webcam';
import { Camera, CameraOff, Scan, Loader2 } from 'lucide-react';
import { useAssistantStore } from '../state/assistantStore';

const CameraWidget = () => {
  const { cameraEnabled, addMessage } = useAssistantStore();
  const [hasPermission, setHasPermission] = useState(false);
  const [isDetecting, setIsDetecting] = useState(false);
  const [error, setError] = useState(null);
  const webcamRef = useRef(null);

  useEffect(() => {
    if (cameraEnabled) {
      // Request laptop camera (front-facing / user camera)
      navigator.mediaDevices.getUserMedia({
        video: {
          // Use laptop's built-in camera
          facingMode: 'user',
          width: { ideal: 1280 },
          height: { ideal: 720 }
        },
        audio: false
      })
        .then((stream) => {
          setHasPermission(true);
          setError(null);
          // Stop the stream immediately - we'll let Webcam handle it
          stream.getTracks().forEach(track => track.stop());
        })
        .catch((err) => {
          console.error('Camera permission error:', err);
          setHasPermission(false);
          setError(err.message);
        });
    } else {
      setHasPermission(false);
      setError(null);
    }
  }, [cameraEnabled]);

  const handleDetect = async () => {
    if (!webcamRef.current) return;
    
    setIsDetecting(true);
    const imageSrc = webcamRef.current.getScreenshot();
    
    try {
      const response = await fetch('http://127.0.0.1:8000/api/v1/vision/detect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: imageSrc })
      });
      
      const data = await response.json();
      
      if (data.status === 'success') {
        addMessage({
          id: Date.now().toString(),
          role: 'assistant',
          content: `Optics Analysis: ${data.analysis}`,
          createdAt: new Date().toISOString()
        });
      } else {
        console.error('Detection failed:', data.message);
      }
    } catch (error) {
      console.error('Detection error:', error);
    } finally {
      setIsDetecting(false);
    }
  };

  return (
    <div className="bg-jarvis-black/80 border border-white/10 rounded overflow-hidden backdrop-blur-md shadow-xl flex flex-col font-mono w-48">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-white/10 bg-jarvis-dark">
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-white/60">
           {cameraEnabled ? <Camera size={10} className="text-jarvis-cyan"/> : <CameraOff size={10} />}
           <span>Optics</span>
        </div>
        <div className="flex items-center gap-2">
          {cameraEnabled && hasPermission && (
            <button 
              onClick={handleDetect}
              disabled={isDetecting}
              className="text-jarvis-cyan hover:text-white transition-colors disabled:opacity-50"
              title="Run Detection"
            >
              {isDetecting ? <Loader2 size={10} className="animate-spin" /> : <Scan size={10} />}
            </button>
          )}
          <div className={`w-1.5 h-1.5 rounded-full ${cameraEnabled ? 'bg-jarvis-cyan animate-pulse' : 'bg-red-500/50'}`} />
        </div>
      </div>
      <div className="h-32 bg-black relative flex items-center justify-center">
        {cameraEnabled && hasPermission ? (
          <Webcam
            audio={false}
            ref={webcamRef}
            screenshotFormat="image/jpeg"
            className="absolute inset-0 w-full h-full object-cover opacity-60 grayscale contrast-125"
            mirrored={true}
            videoConstraints={{
              facingMode: 'user', // Use laptop camera (front-facing)
              width: 1280,
              height: 720
            }}
          />
        ) : (
          <div className="text-[10px] text-white/20 uppercase tracking-widest text-center px-4">
             {cameraEnabled && !hasPermission ? (error ? 'Camera Error' : 'Permission Denied') : 'Optics Offline'}
          </div>
        )}
        
        {/* HUD overlay */}
        {cameraEnabled && hasPermission && (
           <div className="absolute inset-0 pointer-events-none border border-jarvis-cyan/10">
              <div className="absolute top-2 left-2 w-2 h-2 border-t border-l border-jarvis-cyan/50" />
              <div className="absolute top-2 right-2 w-2 h-2 border-t border-r border-jarvis-cyan/50" />
              <div className="absolute bottom-2 left-2 w-2 h-2 border-b border-l border-jarvis-cyan/50" />
              <div className="absolute bottom-2 right-2 w-2 h-2 border-b border-r border-jarvis-cyan/50" />
           </div>
        )}
      </div>
    </div>
  );
};

export default CameraWidget;

